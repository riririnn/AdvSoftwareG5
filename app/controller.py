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
import threading
import time

import cv2

import web_client
from config import (
    SESSION_DIR,
    PERSON_DISAPPEAR_TIME,
    COIN_DETECT_INTERVAL,
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
from raspberry_pi import get_weights
from launcher import launch

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
    # ただし NO_MJPG_CAMERA_INDEXES に含まれるカメラ(video0)は例外的に
    # MJPGを使わずYUYVのまま開く。このカメラはPC直結では正常に動作する
    # にもかかわらず、このラズパイ実機でMJPG転送時のみ"Corrupt JPEG data"
    # 警告が高頻度で発生することを診断で確認しており(config.py参照)、
    # JPEGデコードを行わないYUYVに切り替えることで原理的に回避する。
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

    前回検出より枚数が増えた分だけを「新規投入」として返す。
    （同じ硬貨がトレイに置かれたままでも重複カウントしない）

    Returns
    -------
    list[int]

    例
    ----
    []

    [100]

    [10,10]

    """
    global _last_coin_counts

    if USE_DUMMY_AI:
        answer = input("コイン(空ならEnter): ")
        if answer == "":
            return []
        return [int(answer)]

    detections = _predict(COIN_CAMERA_INDEX, COIN_CONF_THRESHOLD)

    counts: dict[str, int] = {}
    for det in detections:
        name = det["class_name"]
        if name in COIN_VALUES:
            counts[name] = counts.get(name, 0) + 1

    # 前回より増えた枚数分だけを新規投入とみなす
    new_coins = []
    for name, n in counts.items():
        added = n - _last_coin_counts.get(name, 0)
        new_coins.extend([COIN_VALUES[name]] * max(added, 0))

    _last_coin_counts = counts
    return new_coins


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
    global _last_coin_counts
    _last_coin_counts = {}


# ==========================================
# Controller
# ==========================================


class Controller:

    def __init__(self):

        self.recorder = Recorder()

    def run(self):

        print("===================================")
        print("Unmanned Sales System")
        print("Waiting for customer...")
        print("===================================")

        while True:

            # -----------------------------
            # 人待ち
            # -----------------------------

            if not detect_person():
                time.sleep(1)
                continue

            print("\nCustomer detected.")

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

            # -----------------------------
            # 入店時重量取得
            # -----------------------------

            weights = get_weights()

            log_weight(
                session_dir,                    
                "before",
                "vegetable",
                weights["vegetable"],
            )

            log_weight(
                session_dir,
                "before",
                "coinbox",
                weights["coinbox"],
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
                # -------------------------

                coins = detect_coin()

                for coin in coins:
                    log_coin(session_dir, coin)

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
            # 録画終了
            # -----------------------------

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

            # -----------------------------
            # 退店後重量取得
            # -----------------------------

            weights = get_weights()

            log_weight(
                session_dir,
                "after",
                "vegetable",
                weights["vegetable"],
            )

            log_weight(
                session_dir,
                "after",
                "coinbox",
                weights["coinbox"],
            )

            # -----------------------------
            # session.json更新
            # -----------------------------

            finish_session_info(session_dir)

            # -----------------------------
            # 万引き判定プログラム起動
            # -----------------------------

            launch(session_dir)

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

    controller = Controller()

    try:
        controller.run()
    except KeyboardInterrupt:
        print("\n[Controller] 終了処理中...")
    finally:
        # セッション中にCtrl+Cされた場合、録画スレッドを止めてから
        # カメラを解放する（順序が逆だと解放済みカメラへ書き込みに行く）
        controller.recorder.stop()
        release_cameras()
        try:
            from raspberry_pi import cleanup as cleanup_sensors
            cleanup_sensors()
        except Exception:
            pass
        print("[Controller] 終了しました。")


if __name__ == "__main__":
    main()