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
"""

import random

# ---- センサー設定 ----
COIN_DT_PIN  = 16
COIN_SCK_PIN = 20
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

# ---- センサーの実体（初回呼び出し時に1度だけ初期化）----
_hx_coin = None
_hx_vegetable = None
_sensor_available = None  # None=未判定, True=実機, False=ダミー


def _init_sensors() -> bool:
    """
    センサーを初期化する。成功したら True。
    RPi.GPIO / hx711 がない環境（PC等）では False を返しダミー動作にする。
    """
    global _hx_coin, _hx_vegetable

    try:
        import RPi.GPIO as GPIO
        from hx711 import HX711
    except ImportError:
        print("[raspberry_pi] RPi.GPIO/hx711 が見つかりません。ダミー値で動作します。")
        return False

    GPIO.setmode(GPIO.BCM)

    # ゼロ点調整(zero)は起動時の1回だけ行う。
    # 計測のたびに行うと、物が乗った状態が基準になってしまうため厳禁。
    _hx_coin = HX711(dout_pin=COIN_DT_PIN, pd_sck_pin=COIN_SCK_PIN)
    _hx_coin.set_scale_ratio(COIN_SCALE_RATIO)
    _hx_coin.zero()
    print("[raspberry_pi] コイン用センサーのゼロ点調整が完了しました。")

    _hx_vegetable = HX711(dout_pin=VEGE_DT_PIN, pd_sck_pin=VEGE_SCK_PIN)
    _hx_vegetable.set_scale_ratio(VEGE_SCALE_RATIO)
    # 野菜用は台＋商品が常時乗っているため zero() せず、風袋(TARE)を差し引く方式
    print("[raspberry_pi] 野菜用センサーの初期化が完了しました。")

    return True


def get_weights():
    """
    ラズパイから重量情報を取得

    Returns
    -------
    dict

    {
        "vegetable": 1840,   # 野菜の重量(g)。台の重さは差し引き済み
        "coinbox": 950       # コインボックスの重量(g)
    }
    """
    global _sensor_available

    if _sensor_available is None:
        _sensor_available = _init_sensors()

    if not _sensor_available:
        # ===== ダミー実装（PC・センサー未接続時）=====
        return {
            "vegetable": random.randint(1800, 2000),
            "coinbox": random.randint(900, 1000),
        }

    coin_weight = _hx_coin.get_weight_mean(SAMPLES_PER_READ)

    total_vege = _hx_vegetable.get_weight_mean(SAMPLES_PER_READ)
    vege_weight = total_vege - TARE_VEGE_PLATFORM
    if vege_weight < 0.5:  # わずかなノイズ対策
        vege_weight = 0.0

    return {
        "vegetable": round(vege_weight, 1),
        "coinbox": round(coin_weight, 1),
    }


def cleanup():
    """終了時にGPIOを解放する（controller終了時に呼ぶことを推奨）。"""
    if _sensor_available:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
        print("[raspberry_pi] GPIOをクリーンアップしました。")


if __name__ == "__main__":
    # 単体動作確認: 0.5秒間隔で計測値を表示（Ctrl+C で終了）
    import time
    try:
        while True:
            w = get_weights()
            print(f"【コイン】: {w['coinbox']:6.1f} g  ||  【野菜】: {w['vegetable']:6.1f} g")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n計測を終了しました。")
    finally:
        cleanup()
