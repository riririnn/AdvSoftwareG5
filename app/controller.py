"""
controller.py

システム全体を制御するコントローラ

【役割】
・人検知待ち
・セッション開始
・録画開始
・コインログ保存
・人が3秒いなくなったら終了
・野菜・重量ログ保存
・万引き判定プログラム起動
"""

from pathlib import Path
from datetime import datetime
import argparse
import json
import threading
import time

import cv2

import web_client
from config import (
    SESSION_DIR,
    PERSON_DISAPPEAR_TIME,
    COIN_DETECT_INTERVAL,
    PAYMENT_LED_UPDATE_INTERVAL,
    PREDICT_SERVER_URL,
    PERSON_CONF_THRESHOLD,
    COIN_CONF_THRESHOLD,
    VEGETABLE_CONF_THRESHOLD,
    MONITOR_CAMERA_INDEX,
    COIN_CAMERA_INDEX,
    VEGETABLE_CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_FPS,
    NO_MJPG_CAMERA_INDEXES,
    VEGETABLE_BEFORE_IMAGE,
    VEGETABLE_AFTER_IMAGE,
    VEGETABLE_NONE_MARKER,
    SESSION_INFO_FILENAME,
    TARGET_VEGETABLE,
    VEGETABLE_PRICES,
    VEGETABLE_WEIGHTS,
    VEGETABLE_WEIGHT_MARGIN,
    COIN_WEIGHTS,
    COIN_WEIGHT_MARGIN,
)

from csv_logger import (
    create_session,
    create_session_info,
    finish_session_info,
    log_coin,
    log_vegetable,
    log_weight,
)

from recorder import Recorder
from raspberry_pi import (
    WeightReadError,
    get_weights,
    get_vegetable_weight,
    get_coin_weight,
)
from launcher import launch
from payment_indicator import (
    setup as setup_payment_indicator,
    show_idle as indicator_show_idle,
    show_pending as indicator_show_pending,
    show_paid as indicator_show_paid,
    show_theft as indicator_show_theft,
    show_unconfirmed as indicator_show_unconfirmed,
    show_live_status as indicator_show_live_status,
    cleanup as cleanup_payment_indicator,
)

# ==========================================
# AI認識（GPUサーバーの /predict を利用）
#
# --dummy オプション付きで起動するとキーボード入力の
# ダミー実装に切り替わる（サーバー・カメラなしで制御フローを試す用）
# ==========================================

# --dummy 指定時に True になる（main() で設定）
USE_DUMMY_AI = False

# 硬貨クラス名 → 金額。紙幣(1000yen等)や野菜・personはここに無いので自然に無視される
COIN_VALUES = {
    "1yen": 1,
    "5yen": 5,
    "10yen": 10,
    "50yen": 50,
    "100yen": 100,
    "500yen": 500,
}

# 野菜集計から除外するクラス名（硬貨・紙幣・人間）
NON_VEGETABLE_CLASSES = set(COIN_VALUES) | {"1000yen", "5000yen", "10000yen", "person"}

# 前回のコイン検出枚数（増えた分だけを新規投入と判定するための状態）
_last_coin_counts: dict[str, int] = {}

# 1フレームだけの誤検出で新規投入と確定しないための状態。
# 同じ検出結果が連続してCOIN_STABLE_FRAMES回続いたときだけ確定させる。
_pending_coin_counts: dict[str, int] = {}
_pending_coin_streak = 0
COIN_STABLE_FRAMES = 2


def _open_camera(camera_index: int) -> cv2.VideoCapture:
    # バックエンドを明示的にV4L2に固定する。
    # 未指定だとOpenCVがGStreamerバックエンドを先に試みて失敗し
    # V4L2にフォールバックする（起動ログの warning はこれ）。
    # バックエンドが曖昧だとCAP_PROP_BUFFERSIZE等の設定が効かない
    # ことがあるため、明示的にV4L2を指定して挙動を確定させる。
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)

    # 【重要】MJPG(圧縮)モードを必ず指定する。
    # UVCカメラの既定は無圧縮YUYVで、640x480@30fpsで1台約18MB/s消費する。
    # Raspberry Pi 3は全USBポートが1本のUSB2.0バス(実効〜35MB/s)を共有する
    # ため、カメラ2台の同時使用で帯域が飽和し、約10秒周期の
    # select() timeout が発生することを実機で確認した。
    # MJPGなら1台あたり1〜3MB/s程度に収まり、2台同時でも余裕がある。
    #
    # ただし NO_MJPG_CAMERA_INDEXES に含まれるカメラ(video0, video2, video4)は
    # 例外的にMJPGを使わずYUYVのまま開く。これらのカメラはPC直結では正常に
    # 動作するにもかかわらず、このラズパイ実機でMJPG転送時のみ
    # "Corrupt JPEG data"警告が高頻度で発生することを診断で確認しており
    # (config.py参照)、JPEGデコードを行わないYUYVに切り替えることで
    # 原理的に回避する。
    # ※ FOURCCは解像度設定より先に指定する（V4L2の作法）。
    if camera_index not in NO_MJPG_CAMERA_INDEXES:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    # バッファ1枚だとMJPGフレームの受信完了前に読み出してしまい、
    # 「Corrupt JPEG data」警告（デコード時のバイト単位の欠損）が
    # 頻発することを実機で確認した。2枚に緩めて解消を図る。
    # フレームは専用スレッド(_FrameGrabber)が常時ドレインするため、
    # 2枚程度なら「読み取り間隔が空いて古いフレームが溜まる」問題
    # （そもそもの1に絞った理由）は再発しない。
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    return cap


class _FrameGrabber:
    """
    カメラを専用スレッドで継続的に読み続け、最新フレームを保持するクラス。

    実機検証で、メインループがネットワーク通信(サーバーへの推論
    リクエスト)で待っている間 cap.read() の呼び出し間隔が空くと、
    その間もカメラは送信を続けるため内部状態がズレてタイムアウトに
    陥ることを確認した（録画のみ・通信なしの連続読み取りでは
    問題が一切起きなかった）。カメラの読み取りをメインループの
    タイミングから完全に切り離し、常に途切れず読み続けることで解消する。
    """

    def __init__(self, camera_index: int):
        self.camera_index = camera_index
        self._cap = _open_camera(camera_index)
        self._lock = threading.Lock()
        self._latest_frame = None
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        # 読み取り周期の下限。通常はドライバのFPS設定(CAP_PROP_FPS)で
        # ブロックされるため効かないが、設定が効かないカメラでの
        # CPU全力ループを防ぐ保険として入れている。
        min_interval = 1.0 / CAMERA_FPS

        while self._running:
            if not self._cap.isOpened():
                print(f"[Controller] カメラ {self.camera_index} を開けません。再接続を試みます...")
                self._cap = _open_camera(self.camera_index)
                time.sleep(0.5)
                continue

            start = time.monotonic()
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._latest_frame = frame
            else:
                print(f"[Controller] カメラ {self.camera_index} の読み取りに失敗。再接続を試みます...")
                self._cap.release()
                self._cap = _open_camera(self.camera_index)
                continue

            elapsed = time.monotonic() - start
            wait = min_interval - elapsed
            if wait > 0:
                time.sleep(wait)

    def read(self):
        """最新のフレームを返す（まだ1枚も取得できていなければ None）。"""
        with self._lock:
            return self._latest_frame

    def stop(self):
        self._running = False
        self._thread.join(timeout=2)
        self._cap.release()


# カメラは最初に使うときにグラバースレッドを起動し、以後使い回す
_grabbers: dict[int, _FrameGrabber] = {}


def release_cameras():
    """
    起動中の全カメラグラバーを解放する。

    Ctrl+C等での終了時に呼ばないと、カメラのハンドルやバックグラウンド
    スレッドが残留し、次回起動時に「カメラを開けません」
    (can't open camera by index) となることがある。
    """
    for grabber in _grabbers.values():
        grabber.stop()
    _grabbers.clear()


def _get_grabber(camera_index: int) -> _FrameGrabber:
    """指定カメラのグラバーを取得する（未起動なら起動する）。"""
    grabber = _grabbers.get(camera_index)
    if grabber is None:
        grabber = _FrameGrabber(camera_index)
        _grabbers[camera_index] = grabber
        time.sleep(0.5)  # 最初の1枚が取れるまで少し待つ
    return grabber


def _read_frame(camera_index: int):
    """指定カメラの最新フレームを取得する。まだ取得できていなければ None。"""
    return _get_grabber(camera_index).read()


def _predict_frame(frame, conf_threshold: float) -> list[dict]:
    """
    フレームをGPUサーバーに送り、信頼度がしきい値以上の検出だけを返す。
    通信の失敗時は空リスト。
    """
    _, encoded = cv2.imencode(".jpg", frame)
    result = web_client.send_image_for_prediction(
        encoded.tobytes(), PREDICT_SERVER_URL
    )
    if result is None:
        return []

    return [
        det for det in result.get("detections", [])
        if det["confidence"] >= conf_threshold
    ]


def _predict(camera_index: int, conf_threshold: float) -> list[dict]:
    """
    カメラ画像をGPUサーバーに送り、信頼度がしきい値以上の検出だけを返す。
    カメラ・通信の失敗時は空リスト。
    """
    frame = _read_frame(camera_index)
    if frame is None:
        return []
    return _predict_frame(frame, conf_threshold)


def detect_person(frame=None):
    """
    人検知（監視カメラ + person YOLO）

    Parameters
    ----------
    frame : numpy配列 or None
        判定に使うフレーム。None の場合は監視カメラから新規取得する。
        （録画用に取得済みのフレームを使い回すことでカメラ読み出しを1回にする）

    Returns
    -------
    bool
        True : 人がいる
        False: 人がいない
    """
    if USE_DUMMY_AI:
        answer = input("人はいますか？ (y/n): ")
        return answer.lower() == "y"

    if frame is None:
        frame = _read_frame(MONITOR_CAMERA_INDEX)
        if frame is None:
            return False

    detections = _predict_frame(frame, PERSON_CONF_THRESHOLD)
    return any(det["class_name"] == "person" for det in detections)


def detect_coin():
    """
    コイン認識（コインカメラ + coin YOLO）

    前回確定した枚数より増えた分を「新規投入」、減った分を「取り除かれた」
    として返す。（同じ硬貨がトレイに置かれたままでも重複カウントしない）

    1フレームだけの誤検出（反射・影・重なりなどによる瞬間的な
    誤検出）で投入額が誤って加算・減算されないよう、同じ検出結果が
    COIN_STABLE_FRAMES回連続してから初めて確定させる。

    Returns
    -------
    tuple(list[int], list[int])
        (新規投入された硬貨のリスト, 取り除かれた硬貨のリスト)

    例
    ----
    ([], [])

    ([100], [])

    ([10, 10], [])

    ([], [100])

    """
    global _last_coin_counts, _pending_coin_counts, _pending_coin_streak

    if USE_DUMMY_AI:
        answer = input("コイン(空ならEnter): ")
        if answer == "":
            return [], []
        return [int(answer)], []

    detections = _predict(COIN_CAMERA_INDEX, COIN_CONF_THRESHOLD)

    counts: dict[str, int] = {}
    for det in detections:
        name = det["class_name"]
        if name in COIN_VALUES:
            counts[name] = counts.get(name, 0) + 1

    if counts == _pending_coin_counts:
        _pending_coin_streak += 1
    else:
        _pending_coin_counts = counts
        _pending_coin_streak = 1

    if _pending_coin_streak < COIN_STABLE_FRAMES:
        # まだ安定して検出できていないため、今回は確定させない。
        return [], []

    # 前回確定分より増えた/減った枚数分だけを、それぞれ投入・除去とみなす
    new_coins = []
    removed_coins = []
    for name in set(counts) | set(_last_coin_counts):
        diff = counts.get(name, 0) - _last_coin_counts.get(name, 0)
        if diff > 0:
            new_coins.extend([COIN_VALUES[name]] * diff)
        elif diff < 0:
            removed_coins.extend([COIN_VALUES[name]] * (-diff))

    _last_coin_counts = counts
    return new_coins, removed_coins


def _draw_detections(frame, detections):
    """
    検出結果（bbox付き）を描き込んだフレームのコピーを返す。
    元フレームはグラバーと共有しているため直接書き込まない。
    """
    annotated = frame.copy()
    for det in detections:
        bbox = det.get("bbox")
        if not bbox:
            continue
        x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f'{det["class_name"]} {det["confidence"]:.2f}'
        cv2.putText(annotated, label, (x1, max(y1 - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return annotated


def detect_vegetables(save_path=None):
    """
    野菜認識（野菜カメラ + vegetable YOLO）

    Parameters
    ----------
    save_path : Path or None
        指定すると、判定に使った画像を検出枠つきで保存する
        （万引き判定の根拠を後から確認するため）。
        検出0件でも「何も映っていなかった」証拠として素の画像を保存する。

    Returns
    -------
    dict

    {
        "eggplant":4,
        "tomato":2
    }
    """
    if USE_DUMMY_AI:
        return {
            "eggplant": 4,
            "tomato": 2,
        }

    frame = _read_frame(VEGETABLE_CAMERA_INDEX)
    if frame is None:
        return {}

    detections = _predict_frame(frame, VEGETABLE_CONF_THRESHOLD)

    counts: dict[str, int] = {}
    vegetable_detections = []
    for det in detections:
        name = det["class_name"]
        if name in NON_VEGETABLE_CLASSES:
            continue
        counts[name] = counts.get(name, 0) + 1
        vegetable_detections.append(det)

    if save_path is not None:
        # 保存に失敗しても判定処理（CSV記録・万引き判定）は続行する
        try:
            cv2.imwrite(str(save_path), _draw_detections(frame, vegetable_detections))
        except Exception as e:
            print(f"[Controller] 警告: 判定根拠画像を保存できませんでした: {e}")

    return counts


def reset_coin_tracking():
    """コインの新規投入判定をリセットする（セッション開始時に呼ぶ）。"""
    global _last_coin_counts, _pending_coin_counts, _pending_coin_streak
    _last_coin_counts = {}
    _pending_coin_counts = {}
    _pending_coin_streak = 0


# ==========================================
# 来客中のリアルタイム支払い状態
# ==========================================


def _calculate_live_purchase_amount(
    before_vegetable_weight: float,
    current_vegetable_weight: float,
) -> tuple[int, bool, float, float]:
    """
    重量減少から、現在支払うべき金額と、重量判定が確定できたかを
    最終判定と同じ方式で計算する。

    Returns
    -------
    tuple(int, bool, float, float)
        (支払うべき金額, 重量判定が確定できたか, 減少重量g, 丸め誤差g)
        重量判定は「1個以上減っている」かつ「丸め誤差が
        VEGETABLE_WEIGHT_MARGIN以内」の場合にTrueとなる。
    """
    try:
        unit_weight = float(VEGETABLE_WEIGHTS[TARGET_VEGETABLE])
        unit_price = int(VEGETABLE_PRICES[TARGET_VEGETABLE])
    except (KeyError, TypeError, ValueError):
        return 0, False, 0.0, 0.0

    if unit_weight <= 0 or unit_price < 0:
        return 0, False, 0.0, 0.0

    decreased_weight = max(
        0.0,
        float(before_vegetable_weight) - float(current_vegetable_weight),
    )
    estimated_count = max(0, round(decreased_weight / unit_weight))
    rounding_error = abs(decreased_weight - (estimated_count * unit_weight))
    weight_judged = estimated_count > 0 and rounding_error <= VEGETABLE_WEIGHT_MARGIN

    return int(estimated_count * unit_price), weight_judged, decreased_weight, rounding_error


class _LivePaymentMonitor:
    """
    野菜重量と投入硬貨を監視し、来客中のLEDを赤/緑へ切り替える。

    GPIOはcontroller.py内のpayment_indicatorだけが所有するため、
    FlaskとのGPIO競合やroot所有の状態ファイルは発生しない。
    """

    def __init__(self, before_vegetable_weight: float, before_coin_weight: float | None = None):
        self.before_vegetable_weight = float(before_vegetable_weight)
        self.before_coin_weight = (
            float(before_coin_weight) if before_coin_weight is not None else None
        )
        self._paid_amount = 0
        self._paid_coins: list[int] = []
        self._required_amount = 0
        self._weight_judged = False

        # コイン重量チェックが使えない(入店時重量が取れなかった)場合は、
        # STEP3をスキップしてSTEP2完了後すぐ確定できるようTrueにしておく。
        self._coin_weight_ok = self.before_coin_weight is None

        # STEP1: 商品を取ったこと（重量減少）を検知したか。
        # ここが確定するまでコイン認識は行わない。取引確定前に商品を棚へ
        # 戻す（重量が入店時相当に戻る）と、STEP1〜3の状態ごとFalseへ戻す。
        self._item_taken = False

        # STEP2: 画像認識（コイン投入）で必要金額以上の支払いを確認できたか。
        self._image_payment_confirmed = False

        # STEP3: コイン用重量センサーの増加分が、画像認識した硬貨の想定重量と
        # 一致することを確認できたか。
        self._coin_weight_confirmed = False

        # STEP4: 重量判定を最終確認し、取引を確定したか（一度Trueになったら戻さない。
        # 以降はコイン認識自体を止める。1回の支払いで1回分の取引とみなす）。
        self._transaction_confirmed = False

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._last_error = None

    def start(self):
        indicator_show_live_status(
            item_taken=False, payment_ok=False, weight_ok=False, required_amount=0, paid_amount=0
        )
        self._thread.start()

    def is_item_taken(self) -> bool:
        """STEP1: 商品を取ったこと（重量減少）を検知したか。"""
        with self._lock:
            return self._item_taken

    def is_image_payment_confirmed(self) -> bool:
        """STEP2: 画像認識による支払い確認が完了したか。"""
        with self._lock:
            return self._image_payment_confirmed

    def is_transaction_confirmed(self) -> bool:
        """STEP4: 重量判定による取引確定が完了したか。"""
        with self._lock:
            return self._transaction_confirmed

    def add_coins(self, coins: list[int]):
        if not coins:
            return

        with self._lock:
            if not self._item_taken or self._image_payment_confirmed:
                # STEP1(商品を取る)が終わっていない、またはSTEP2まで完了済みの
                # 場合は、コイン投入を受け付けない
                # （商品を取る→支払う→重量判定、の順番を守るため）。
                return

            self._paid_amount += sum(int(coin) for coin in coins)
            self._paid_coins.extend(int(coin) for coin in coins)
            self._check_progress_locked()

            required = self._required_amount
            paid = self._paid_amount
            item_missing = self._weight_judged
            image_payment_confirmed = self._image_payment_confirmed
            confirmed = self._transaction_confirmed

        self._apply_indicator(required, paid, item_missing, image_payment_confirmed, confirmed)

    def remove_coins(self, coins: list[int]):
        """トレイから取り除かれた硬貨の分だけ、投入済み金額を減らす。"""
        if not coins:
            return

        with self._lock:
            if not self._item_taken or self._image_payment_confirmed:
                return

            self._paid_amount = max(0, self._paid_amount - sum(int(coin) for coin in coins))
            for coin in coins:
                try:
                    self._paid_coins.remove(int(coin))
                except ValueError:
                    pass
            required = self._required_amount
            paid = self._paid_amount
            item_missing = self._weight_judged
            image_payment_confirmed = self._image_payment_confirmed
            confirmed = self._transaction_confirmed

        self._apply_indicator(required, paid, item_missing, image_payment_confirmed, confirmed)

    def _check_progress_locked(self):
        """
        ロック取得済みの状態で呼ぶこと。
        STEP2(画像認識で支払い確認)→STEP3(コイン重量で確認)→
        STEP4(重量判定で最終確認・取引確定)の順に進める。
        """
        if self._transaction_confirmed:
            return

        if not self._image_payment_confirmed:
            if self._required_amount > 0 and self._paid_amount >= self._required_amount:
                self._image_payment_confirmed = True
                print(
                    "[Controller] STEP2 画像認識で支払いを確認しました。"
                    f"必要{self._required_amount}円 / 投入{self._paid_amount}円 "
                    "→ コイン重量の確認へ進みます。"
                )

        if (
            self._image_payment_confirmed
            and not self._coin_weight_confirmed
            and self._paid_coins
            and self._coin_weight_ok
        ):
            self._coin_weight_confirmed = True
            print(
                "[Controller] STEP3 コイン用重量センサーで、投入されたコインの"
                "重量増加を確認しました → 重量判定（野菜側）へ進みます。"
            )

        if self._coin_weight_confirmed and not self._transaction_confirmed:
            # STEP4: 支払い確認できた時点の重量が、引き続き有効な判定のままか
            # 最終確認する（商品を戻す等の不正operationを弾くため）。
            if self._weight_judged:
                self._transaction_confirmed = True
                print(
                    "[Controller] STEP4 重量判定: 支払った金額と重量減少分が"
                    f"一致しました。必要{self._required_amount}円 / "
                    f"投入{self._paid_amount}円 → 取引確定。"
                )

    def _apply_indicator(self, required: int, paid: int, item_missing: bool, image_payment_confirmed: bool, confirmed: bool):
        # 白LED: 現在の重量が入店時と変わらない（商品を持っていない）間ON。
        # 商品を取って重量が減っている間はOFF（戻せば白に戻る、STEP1の確定とは別判定）。
        # 赤LED: 商品を持ち出している間、STEP2(画像認識で支払い確認)まではON。
        # 黄LED: 支払い確認済み・重量判定待ちの間ON。緑LED: STEP4(取引確定)でON。
        indicator_show_live_status(
            item_taken=item_missing,
            payment_ok=image_payment_confirmed,
            weight_ok=confirmed,
            required_amount=required,
            paid_amount=paid,
        )

    def _loop(self):
        while not self._stop_event.wait(PAYMENT_LED_UPDATE_INTERVAL):
            try:
                current_weight = get_vegetable_weight()
                required, weight_judged, decreased_weight, rounding_error = (
                    _calculate_live_purchase_amount(
                        self.before_vegetable_weight,
                        current_weight,
                    )
                )

                # 重量が減っているのに判定が確定しない場合の原因調査用ログ。
                if decreased_weight > 0 and not weight_judged:
                    print(
                        "[Controller] 重量判定デバッグ: "
                        f"減少重量={decreased_weight:.1f}g / "
                        f"丸め誤差={rounding_error:.1f}g "
                        f"(許容={VEGETABLE_WEIGHT_MARGIN}g) / 判定OK=False"
                    )

                # コイン用重量センサーで、画像認識したコインが物理的にも
                # 投入されているかを検証する（入店時重量が取れた場合のみ）。
                current_coin_weight = None
                if self.before_coin_weight is not None:
                    try:
                        current_coin_weight = get_coin_weight()
                    except WeightReadError as error:
                        print(
                            "[Controller] コイン重量の取得に失敗しました。"
                            f"コイン重量チェックは前回の結果を維持します: {error}"
                        )

                with self._lock:
                    if not self._transaction_confirmed:
                        self._weight_judged = weight_judged

                        if self._item_taken and not weight_judged:
                            # 商品を棚に戻した（重量が入店時相当に戻った）ので、
                            # STEP1〜3の状態をリセットする。再び取ったときは
                            # 画像認識による支払い確認からやり直しになる。
                            self._item_taken = False
                            self._image_payment_confirmed = False
                            self._paid_amount = 0
                            self._paid_coins = []
                            self._coin_weight_confirmed = False
                            self._coin_weight_ok = self.before_coin_weight is None
                            self._required_amount = 0
                            print(
                                "[Controller] 商品を棚に戻しました。"
                                "支払い確認状態をリセットします。"
                            )

                        if not self._item_taken:
                            if weight_judged:
                                self._item_taken = True
                                self._required_amount = required
                                print(
                                    "[Controller] STEP1 商品を検知しました"
                                    f"（重量減少を確認）。必要{required}円。"
                                    "画像認識（コイン投入）を受け付けます。"
                                )
                        else:
                            # 商品検知後に追加で取られた分も必要金額へ反映する。
                            self._required_amount = required

                        if current_coin_weight is not None:
                            expected_coin_weight = sum(
                                COIN_WEIGHTS.get(coin, 0) for coin in self._paid_coins
                            )
                            actual_increase = max(
                                0.0, current_coin_weight - self.before_coin_weight
                            )
                            coin_weight_diff = actual_increase - expected_coin_weight
                            # コインが1枚も投入されていない間は、想定重量・実測増加が
                            # どちらも0gで「一致」扱いになってしまうため、Trueにしない。
                            new_coin_weight_ok = (
                                bool(self._paid_coins)
                                and abs(coin_weight_diff) <= COIN_WEIGHT_MARGIN
                            )

                            if self._paid_coins and not new_coin_weight_ok:
                                print(
                                    "[Controller] コイン重量デバッグ: "
                                    f"投入コイン={self._paid_coins} / "
                                    f"想定重量={expected_coin_weight:.1f}g / "
                                    f"現在コイン重量={current_coin_weight:.1f}g / "
                                    f"入店時コイン重量={self.before_coin_weight:.1f}g / "
                                    f"実測増加={actual_increase:.1f}g / "
                                    f"差={coin_weight_diff:+.1f}g "
                                    f"(許容±{COIN_WEIGHT_MARGIN}g) / 判定OK={new_coin_weight_ok}"
                                )

                            self._coin_weight_ok = new_coin_weight_ok

                        self._check_progress_locked()

                    required = self._required_amount
                    paid = self._paid_amount
                    item_missing = self._weight_judged
                    image_payment_confirmed = self._image_payment_confirmed
                    confirmed = self._transaction_confirmed

                self._apply_indicator(required, paid, item_missing, image_payment_confirmed, confirmed)
                self._last_error = None

            except Exception as error:
                message = str(error)
                if message != self._last_error:
                    print(
                        "[Controller] 支払い状態の重量取得に失敗しました。"
                        f"赤LEDを維持します: {error}"
                    )
                    self._last_error = message

    def snapshot(self) -> tuple[int, int]:
        with self._lock:
            return self._required_amount, self._paid_amount

    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=PAYMENT_LED_UPDATE_INTERVAL + 2.0)


WEIGHT_MEASUREMENT_ERROR = "MEASUREMENT_ERROR"


def _measure_and_log_weights(session_dir: Path, phase: str) -> dict:
    """重量を安定測定してCSVへ保存する。

    全リトライに失敗したセンサーは0.0gではなく
    MEASUREMENT_ERRORとして記録する。theft_checkerはこれを判定不能として
    扱うため、測定失敗を未払いと誤認してブザーを鳴らさない。
    """
    try:
        weights = get_weights()
    except WeightReadError as error:
        weights = {
            "vegetable": error.partial_weights.get("vegetable"),
            "coinbox": error.partial_weights.get("coinbox"),
        }
        print(
            f"[Controller] {phase}重量の測定に失敗しました: {error}"
        )

    for target in ("vegetable", "coinbox"):
        value = weights.get(target)
        log_weight(
            session_dir,
            phase,
            target,
            value if value is not None else WEIGHT_MEASUREMENT_ERROR,
        )

    return weights


def _load_theft_check_result(session_dir: Path) -> dict:
    """theft_checker実行後のsession.jsonから最終判定を読み取る。"""
    path = session_dir / SESSION_INFO_FILENAME
    try:
        with open(path, "r", encoding="utf-8") as file:
            session_data = json.load(file)
        theft_check = session_data.get("theft_check")
        return theft_check if isinstance(theft_check, dict) else {}
    except (OSError, json.JSONDecodeError) as error:
        print(f"[Controller] 最終判定の読み込みに失敗しました: {error}")
        return {}


# ==========================================
# Controller
# ==========================================


class Controller:

    def __init__(self):

        self.recorder = Recorder()
        self.payment_monitor = None

    def run(self):

        print("===================================")
        print("Unmanned Sales System")
        print("Waiting for customer...")
        print("===================================")

        indicator_show_idle(reset_buzzer=True)

        while True:

            # -----------------------------
            # 人待ち
            # -----------------------------

            if not detect_person():
                time.sleep(1)
                continue

            print("\nCustomer detected.")

            # 人を検知した時点から、商品を取るまでは白LEDを点灯する。
            indicator_show_pending(0, 0)

            # コインの新規投入判定をセッションごとにリセット
            reset_coin_tracking()

            # -----------------------------
            # セッション作成
            # -----------------------------

            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

            session_dir = SESSION_DIR / session_id

            create_session(session_dir)
            create_session_info(session_dir)

            # -----------------------------
            # 入店時の野菜数保存
            # -----------------------------

            before_vegetables = detect_vegetables(
                save_path=session_dir / VEGETABLE_BEFORE_IMAGE
            )

            for name, count in before_vegetables.items():
                log_vegetable(
                    session_dir,
                    "before",
                    name,
                    count,
                )

            # 検出0件でも「計測は実施した」ことを記録する。
            # 行が無いと theft_checker が「データ欠損」と区別できない
            if not before_vegetables:
                log_vegetable(session_dir, "before", VEGETABLE_NONE_MARKER, 0)

            # -----------------------------
            # 入店時重量取得
            # -----------------------------

            before_weights = _measure_and_log_weights(
                session_dir,
                "before",
            )

            # 野菜の入店時重量を取得できた場合だけ、
            # 重量減少と投入硬貨から来客中のLEDを更新する。
            before_vegetable_weight = before_weights.get("vegetable")
            before_coin_weight = before_weights.get("coinbox")
            if before_vegetable_weight is not None:
                self.payment_monitor = _LivePaymentMonitor(
                    before_vegetable_weight,
                    before_coin_weight,
                )
                self.payment_monitor.start()
            else:
                print(
                    "[Controller] 入店時の野菜重量が取得できないため、"
                    "リアルタイム支払いLEDは赤のまま維持します。"
                )

            # -----------------------------
            # 録画開始
            # -----------------------------
            # 録画はRecorder内の専用スレッドが実時間基準(RECORD_FPS周期)で
            # 監視カメラの最新フレームを書き込む。メインループは推論の
            # ネットワーク往復で数秒ブロックするため、ループから書き込むと
            # 動画の再生時間が実時間より大幅に短くなる（実機で確認済み）。

            if not USE_DUMMY_AI:
                self.recorder.start(
                    session_dir, _get_grabber(MONITOR_CAMERA_INDEX).read
                )

            print("Session started.")
            print()
            # -----------------------------
            # セッション中
            # -----------------------------

            disappeared_time = None

            while True:

                # -------------------------
                # 監視カメラのフレーム取得
                # （録画はRecorderのスレッドが行う。ここでの取得は人検知用）
                # -------------------------

                monitor_frame = None

                if not USE_DUMMY_AI:
                    monitor_frame = _read_frame(MONITOR_CAMERA_INDEX)

                # -------------------------
                # コイン認識
                # （商品を取る(STEP1)より前はコイン認識を行わない。
                #   画像認識で支払いを確認できたら(STEP2)、それ以降は画像認識を
                #   やり直さず、コインカメラの呼び出し自体を止める。
                #   CPU負荷軽減も兼ねる。）
                # -------------------------

                item_taken = (
                    self.payment_monitor is not None
                    and self.payment_monitor.is_item_taken()
                )
                image_payment_confirmed = (
                    self.payment_monitor is not None
                    and self.payment_monitor.is_image_payment_confirmed()
                )

                if item_taken and not image_payment_confirmed:
                    new_coins, removed_coins = detect_coin()

                    for coin in new_coins:
                        log_coin(session_dir, coin)

                    if self.payment_monitor is not None:
                        self.payment_monitor.add_coins(new_coins)
                        self.payment_monitor.remove_coins(removed_coins)

                # -------------------------
                # 人検知
                # -------------------------

                if detect_person(monitor_frame):

                    disappeared_time = None

                else:

                    if disappeared_time is None:
                        disappeared_time = time.time()

                    elif (
                        time.time() - disappeared_time
                        >= PERSON_DISAPPEAR_TIME
                    ):
                        print("Customer left.")
                        break

                time.sleep(COIN_DETECT_INTERVAL)

            # -----------------------------
            # リアルタイム支払い監視・録画終了
            # -----------------------------

            if self.payment_monitor is not None:
                self.payment_monitor.stop()
                self.payment_monitor = None

            self.recorder.stop()

            # -----------------------------
            # 退店後の野菜数保存
            # -----------------------------

            after_vegetables = detect_vegetables(
                save_path=session_dir / VEGETABLE_AFTER_IMAGE
            )

            for name, count in after_vegetables.items():

                log_vegetable(
                    session_dir,
                    "after",
                    name,
                    count,
                )

            # 全品持ち去り（検出0件）でも after の計測実施を記録する
            if not after_vegetables:
                log_vegetable(session_dir, "after", VEGETABLE_NONE_MARKER, 0)

            # -----------------------------
            # 退店後重量取得
            # -----------------------------

            _measure_and_log_weights(
                session_dir,
                "after",
            )

            # -----------------------------
            # session.json更新
            # -----------------------------

            finish_session_info(session_dir)

            # -----------------------------
            # 万引き判定プログラム起動
            # -----------------------------

            launch(session_dir)

            # 最終判定に合わせてLED・ブザーを確定する。
            theft_check = _load_theft_check_result(session_dir)
            judgement = str(theft_check.get("judgement") or "").lower()
            purchase_amount = int(theft_check.get("purchase_amount") or 0)
            paid_amount = int(theft_check.get("paid_amount") or 0)
            shortage = int(theft_check.get("shortage") or 0)

            if judgement in {"normal", "nomal"}:
                if purchase_amount > 0:
                    indicator_show_paid(purchase_amount, paid_amount)
                else:
                    indicator_show_idle()
            elif judgement == "no_purchase":
                # 何も取らず・買わずに立ち去った場合は、待機状態に戻すだけ。
                indicator_show_idle()
            elif judgement == "theft":
                indicator_show_theft(shortage)
            else:
                # 判定不能時は誤って緑にしない。赤LEDで要確認を示すが、
                # 万引き確定ではないためブザーは鳴らさない。
                indicator_show_unconfirmed(purchase_amount, paid_amount)

            print()
            print("Session finished.")
            print("Waiting for next customer...")
            print()


def main():

    global USE_DUMMY_AI

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dummy",
        action="store_true",
        help="AI認識を使わずキーボード入力のダミーで動かす（制御フロー単体テスト用）",
    )
    args = parser.parse_args()

    USE_DUMMY_AI = args.dummy
    if USE_DUMMY_AI:
        print("[Controller] ダミーモードで起動します（AI認識・カメラ不使用）")
    else:
        print(f"[Controller] AIモードで起動します（推論サーバー: {PREDICT_SERVER_URL}）")

    setup_payment_indicator()
    controller = Controller()

    try:
        controller.run()
    except KeyboardInterrupt:
        print("\n[Controller] 終了処理中...")
    finally:
        # セッション中にCtrl+Cされた場合、録画スレッドを止めてから
        # カメラを解放する（順序が逆だと解放済みカメラへ書き込みに行く）
        if controller.payment_monitor is not None:
            controller.payment_monitor.stop()
            controller.payment_monitor = None
        controller.recorder.stop()
        release_cameras()
        cleanup_payment_indicator()
        try:
            from raspberry_pi import cleanup as cleanup_sensors
            cleanup_sensors()
        except Exception:
            pass
        print("[Controller] 終了しました。")


if __name__ == "__main__":
    main()