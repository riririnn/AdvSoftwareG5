"""
重量取得モジュール

【役割】
  HX711ロードセル2台（コイン用・野菜用）から重量を取得し、
  controller.py へ dict で返す。

【動作環境による自動切り替え】
  - ラズパイ実機: 実センサーから計測（RPi.GPIO + hx711 が必要）
  - PC等（センサーなし）: ダミー値（乱数）を返す
    → PC上での結合テストはダミーのまま実施できる

【ハードウェア構成】
  コイン用: DT=GPIO16, SCK=GPIO20, scale_ratio=1880
  野菜用:   DT=GPIO12, SCK=GPIO21, scale_ratio=1000
  野菜台の風袋: TARE_VEGE_PLATFORM（要実測。台だけ乗せた状態の表示値に合わせる）

【必要パッケージ（ラズパイのみ）】
  pip install RPi.GPIO hx711

【hx711パッケージについての注意】
  PyPIの `hx711` は実装違いのパッケージが複数存在し、API が異なる。
  本モジュールは `get_raw_data()` のみを提供する版（mpibpc-mroose/hx711,
  1.1.2.3で確認）に対応しており、ゼロ点調整・グラム換算は自前で実装している。
  `set_scale_ratio` 等の高レベルAPIを持つ版が入っている場合は動作しないため、
  `pip3 show hx711` でバージョンを確認すること。

【既知の不具合と対策（重要）】
  このライブラリの get_raw_data() は、内部の _read() が失敗(False)を
  返し続けると無限ループしてフリーズする。_read() はSCKパルスが
  60マイクロ秒を超えると失敗扱いになる仕様で、Python製の
  ソフトウェアビットバンギング実装ではラズパイ実機（特にPi 3など非力な
  機種、カメラ等で負荷が高い状況）で頻繁にこの制限を超える。
  そのため本モジュールは get_raw_data() を直接使わず、内部の _read() を
  こちらで有限回数だけリトライする _read_raw_mean() を実装している。
  配線・電源が正常でも発生しうる、ライブラリ側の既知の弱点であり
  ハードウェア故障ではない。
"""

import random
import statistics
import threading
import time

# ---- センサー設定 ----
COIN_DT_PIN  = 16
COIN_SCK_PIN = 20
# raw値(ADCカウント) → グラム の変換係数。おもり等で校正した実測値に置き換える。
# weight_g = (raw - オフセット) / SCALE_RATIO
COIN_SCALE_RATIO = 1880

VEGE_DT_PIN  = 12
VEGE_SCK_PIN = 21
VEGE_SCALE_RATIO = 1000

# 野菜台の重さ(g)。台だけを乗せた状態で計測して調整する
TARE_VEGE_PLATFORM = 148.0

# 1回の計測で平均するサンプル数。
# HX711は約10Hz読み取りのため、大きくすると get_weights() が遅くなる
# （5サンプル×2センサー ≈ 1秒）。精度が足りない場合のみ増やす。
SAMPLES_PER_READ = 5

# ゼロ点調整（起動時のオフセット計測）に使うサンプル数
ZERO_SAMPLES = 10

# _read()の最大リトライ回数と時間予算。
# 以前は全サンプル取得失敗時に0.0を返していたため、
# 『測定失敗』と『本当に0g』を区別できなかった。
# 現在は失敗をWeightReadErrorとして呼び出し元へ通知する。
MAX_READ_ATTEMPTS = 100
READ_TIME_BUDGET_SEC = 2.0

# セッション開始・終了時の重量は複数回測定し、中央値を採用する。
# 瞬間的なGPIOタイミング失敗や外乱の影響を抑えるための設定。
STABLE_MEASUREMENT_COUNT = 3
STABLE_MEASUREMENT_DELAY_SEC = 0.15
MIN_VALID_STABLE_MEASUREMENTS = 2

# ---- センサーの実体（初回呼び出し時に1度だけ初期化）----
_hx_coin = None
_hx_vegetable = None
_coin_offset = 0.0     # 起動時（無負荷）のraw平均値
_sensor_available = None  # None=未判定, True=実機, False=ダミー
_sensor_lock = threading.RLock()


class WeightReadError(RuntimeError):
    """HX711から有効な重量を取得できなかった場合の例外。"""

    def __init__(self, message: str, partial_weights: dict | None = None):
        super().__init__(message)
        self.partial_weights = partial_weights or {}


def _read_raw_mean(hx, samples: int) -> float | None:
    """
    指定回数センサーを読み、raw値(ADCカウント)の平均を返す。

    ライブラリ標準の get_raw_data() は失敗時に無限リトライしてフリーズする
    ため使わず、内部の _read() を有限回数だけ自前でリトライする。
    時間予算・試行回数の上限に達した場合、取得済みの値があれば
    その平均を返す。1件も取得できなかった場合はNoneを返す。

    重要:
        Noneを0.0gへ変換しないこと。0.0gは正常な測定値にもなり得るため、
        測定失敗と区別する必要がある。
    """
    values = []
    attempts = 0
    start = time.monotonic()

    while len(values) < samples:
        if attempts >= MAX_READ_ATTEMPTS or (time.monotonic() - start) >= READ_TIME_BUDGET_SEC:
            print(f"[raspberry_pi] 警告: 規定時間内に十分なサンプルが取れませんでした"
                  f"（取得できた数: {len(values)}/{samples}）。取得できた値のみで計算します。")
            break
        attempts += 1
        data = hx._read()  # ライブラリの内部メソッド。失敗時 False を返す
        if data not in (False, -1):
            values.append(data)

    if not values:
        return None
    return statistics.mean(values)


def _read_stable_raw(
    hx,
    sensor_name: str,
    *,
    measurements: int = STABLE_MEASUREMENT_COUNT,
    samples: int = SAMPLES_PER_READ,
) -> float:
    """複数回のraw平均値を取得し、その中央値を返す。

    一時的にHX711読み取りが失敗しても、規定回数のうち
    MIN_VALID_STABLE_MEASUREMENTS回以上成功すれば中央値を採用する。
    成功数が不足した場合はWeightReadErrorを発生させる。
    """
    valid_values: list[float] = []

    for measurement_index in range(measurements):
        with _realtime_priority():
            raw = _read_raw_mean(hx, samples)

        if raw is None:
            print(
                f"[raspberry_pi] 警告: {sensor_name}の測定"
                f" {measurement_index + 1}/{measurements} に失敗しました。"
            )
        else:
            valid_values.append(float(raw))

        if measurement_index + 1 < measurements:
            time.sleep(STABLE_MEASUREMENT_DELAY_SEC)

    if len(valid_values) < MIN_VALID_STABLE_MEASUREMENTS:
        raise WeightReadError(
            f"{sensor_name}の有効な測定回数が不足しています"
            f"（成功: {len(valid_values)}/{measurements}）"
        )

    stable_raw = float(statistics.median(valid_values))
    print(
        f"[raspberry_pi] {sensor_name}の安定測定: "
        f"成功 {len(valid_values)}/{measurements}, raw中央値={stable_raw:.1f}"
    )
    return stable_raw


class _realtime_priority:
    """
    with文で囲んだ区間だけリアルタイムスケジューリング(SCHED_FIFO)にする
    コンテキストマネージャ。

    HX711読み取りはSCKパルスを60マイクロ秒以内に収める必要があるが、
    通常優先度のPythonプロセスはOSのスケジューラに割り込まれてこれを
    頻繁に超過し、読み取りが100%失敗することが実機(Raspberry Pi 3)で
    確認された。一方でプロセス全体を常時SCHED_FIFOにすると、
    カメラ読み取りスレッド等の他の処理を圧迫するリスクがあるため、
    **センサー読み取りの間だけ**昇格し、終わったら通常優先度に戻す。

    root権限が無い場合は何もしない（通常優先度のまま計測する。
    読み取り失敗が増える可能性があるため sudo での実行を推奨）。
    """

    _warned = False

    def __enter__(self):
        import os
        self._elevated = False
        try:
            os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(50))
            self._elevated = True
        except (PermissionError, OSError):
            if not _realtime_priority._warned:
                _realtime_priority._warned = True
                print(
                    "[raspberry_pi] 警告: リアルタイム優先度を設定できません（root権限が必要）。\n"
                    "                HX711の読み取りが不安定になる可能性があります。\n"
                    "                'sudo python3 controller.py' のように root で実行してください。"
                )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        import os
        if self._elevated:
            os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
        return False


def _init_sensors() -> bool:
    """
    センサーを初期化する。成功したら True。
    RPi.GPIO / hx711 がない環境（PC等）では False を返しダミー動作にする。
    """
    global _hx_coin, _hx_vegetable, _coin_offset

    try:
        import RPi.GPIO as GPIO
        from hx711 import HX711
    except ImportError:
        print("[raspberry_pi] RPi.GPIO/hx711 が見つかりません。ダミー値で動作します。")
        return False

    # 2台目のHX711初期化時に出る「This channel is already in use」警告を抑制
    # （同一プロセス内でSCKピンを複数セットアップするための無害な警告）
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    with _realtime_priority():
        # ゼロ点調整は起動時の1回だけ行う。
        # 計測のたびに行うと、物が乗った状態が基準になってしまうため厳禁。
        _hx_coin = HX711(dout_pin=COIN_DT_PIN, pd_sck_pin=COIN_SCK_PIN)

    # ゼロ点も複数回測定し、読み取り失敗を0として採用しない。
    _coin_offset = _read_stable_raw(
        _hx_coin,
        "コイン用センサーのゼロ点",
        measurements=STABLE_MEASUREMENT_COUNT,
        samples=ZERO_SAMPLES,
    )
    print(
        "[raspberry_pi] コイン用センサーのゼロ点調整が完了しました。"
        f"(offset={_coin_offset:.0f})"
    )

    with _realtime_priority():

        _hx_vegetable = HX711(dout_pin=VEGE_DT_PIN, pd_sck_pin=VEGE_SCK_PIN)
        # 野菜用は台＋商品が常時乗っているため raw offsetは取らず、
        # グラム換算後に風袋(TARE_VEGE_PLATFORM)を差し引く方式にする。
        print("[raspberry_pi] 野菜用センサーの初期化が完了しました。")

    return True


def _ensure_sensor_state() -> bool:
    """センサー初期化状態を返す。呼び出し元は_sensor_lockを保持すること。"""
    global _sensor_available

    if _sensor_available is None:
        _sensor_available = _init_sensors()

    return bool(_sensor_available)


def _convert_vegetable_raw_to_grams(vege_raw: float) -> float:
    total_vege = vege_raw / VEGE_SCALE_RATIO
    vege_weight = total_vege - TARE_VEGE_PLATFORM
    if vege_weight < 0.5:
        vege_weight = 0.0
    return round(max(vege_weight, 0.0), 1)


def get_vegetable_weight():
    """
    野菜用ロードセルだけを読み取る。

    来客中のLED更新ではコイン用ロードセルまで毎回読む必要がないため、
    get_weights()より短時間・低負荷で現在の野菜重量を取得する。
    """
    with _sensor_lock:
        if not _ensure_sensor_state():
            return float(random.randint(1800, 2000))

        with _realtime_priority():
            vege_raw = _read_raw_mean(_hx_vegetable, SAMPLES_PER_READ)

        if vege_raw is None:
            raise WeightReadError(
                "野菜用センサーから有効な値を取得できませんでした"
            )

        return _convert_vegetable_raw_to_grams(vege_raw)


def get_coin_weight():
    """
    コイン用ロードセルだけを読み取る。

    来客中のライブ判定で、コイン投入の画像認識結果を重量面からも
    検証するために使う。get_weights()より短時間・低負荷で
    現在のコイン重量を取得する。
    """
    with _sensor_lock:
        if not _ensure_sensor_state():
            return float(random.randint(900, 1000))

        with _realtime_priority():
            coin_raw = _read_raw_mean(_hx_coin, SAMPLES_PER_READ)

        if coin_raw is None:
            raise WeightReadError(
                "コイン用センサーから有効な値を取得できませんでした"
            )

        coin_weight = (coin_raw - _coin_offset) / COIN_SCALE_RATIO
        return round(max(coin_weight, 0.0), 1)


def get_weights():
    """
    ラズパイから重量情報を取得

    Returns
    -------
    dict

    {
        "vegetable": 1840,
        "coinbox": 950
    }
    """
    with _sensor_lock:
        if not _ensure_sensor_state():
            return {
                "vegetable": random.randint(1800, 2000),
                "coinbox": random.randint(900, 1000),
            }

        # セッション開始・終了時は各センサーを複数回測定し、
        # 中央値を採用する。片方だけ失敗した場合も、成功した側の値は
        # partial_weightsとして呼び出し元へ返す。
        partial_weights = {
            "vegetable": None,
            "coinbox": None,
        }
        errors = []

        try:
            coin_raw = _read_stable_raw(_hx_coin, "コイン用センサー")
            coin_weight = (coin_raw - _coin_offset) / COIN_SCALE_RATIO
            partial_weights["coinbox"] = round(max(coin_weight, 0.0), 1)
        except WeightReadError as error:
            errors.append(str(error))

        try:
            vege_raw = _read_stable_raw(_hx_vegetable, "野菜用センサー")
            partial_weights["vegetable"] = (
                _convert_vegetable_raw_to_grams(vege_raw)
            )
        except WeightReadError as error:
            errors.append(str(error))

        if errors:
            raise WeightReadError(
                " / ".join(errors),
                partial_weights=partial_weights,
            )

        print(
            "[raspberry_pi] 安定重量: "
            f"コイン={partial_weights['coinbox']:.1f} g, "
            f"野菜={partial_weights['vegetable']:.1f} g"
        )
        return partial_weights


def cleanup():
    """終了時にGPIOを解放する（controller終了時に呼ぶことを推奨）。"""
    if _sensor_available:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
        print("[raspberry_pi] GPIOをクリーンアップしました。")


if __name__ == "__main__":
    # 単体動作確認: 0.5秒間隔で計測値を表示（Ctrl+C で終了）
    try:
        while True:
            w = get_weights()
            print(f"【コイン】: {w['coinbox']:6.1f} g  ||  【野菜】: {w['vegetable']:6.1f} g")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n計測を終了しました。")
    finally:
        cleanup()
