# 🔴 一番最初にGPIOをインポートしてモードを設定します！
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

# 🔴 その後に他のライブラリをインポートします
import time
import sys
from hx711 import HX711 

def setup_sensors():
    print("GPIOのナンバリングモード（BCM）は設定済みです。")

    # --------------------------------------------------
    # 1. コイン用センサーの設定 (元のピンを指定してください)
    # --------------------------------------------------
    COIN_DT_PIN = 16
    COIN_SCK_PIN = 20
    
    hx_coin = HX711(dout_pin=COIN_DT_PIN, pd_sck_pin=COIN_SCK_PIN)
    hx_coin.set_scale_ratio(1880) 
    hx_coin.zero()
    print("コイン用センサーのゼロ点調整が完了しました。")

    # --------------------------------------------------
    # 2. 野菜用センサーの設定 (新設: DT=12, SCK=21)
    # --------------------------------------------------
    VEGE_DT_PIN = 12
    VEGE_SCK_PIN = 21
    
    hx_vegetable = HX711(dout_pin=VEGE_DT_PIN, pd_sck_pin=VEGE_SCK_PIN)
    hx_vegetable.set_scale_ratio(1000) 
    #hx_vegetable.zero()
    print("野菜用センサーのゼロ点調整が完了しました。")
    
    return hx_coin, hx_vegetable

def main():
    try:
        hx_coin, hx_vegetable = setup_sensors()
        print("\n計測を開始します... (Ctrl+C で終了)")
       # 基準となる台の重さを定義（144.0グラム）
        TARE_VEGE_PLATFORM = 148.0

        while True:
            # コイン用はそのまま計測
            weight_coin = hx_coin.get_weight_mean(15)
            
            # 野菜用の計測
            try:
                # センサーが感知した「総重量（台 ＋ 野菜）」を取得
                total_vege_weight = hx_vegetable.get_weight_mean(15)
                
                # 総重量から「台の重さ」を引いて、純粋な【野菜だけの重さ】を計算する
                pure_vegetable_weight = total_vege_weight - TARE_VEGE_PLATFORM
                
                # 表示用に整形（マイナスに振れた場合は0.0gにする処理を入れておくと綺麗です）
                if pure_vegetable_weight < 0.5: # わずかなノイズ対策
                    pure_vegetable_weight = 0.0
                    
                vege_display = f"{pure_vegetable_weight:6.1f} g"
                
            except Exception:
                vege_display = "エラー（信号なし）"
            
            # 画面に表示
            print(f"【コイン】: {weight_coin:5.1f} g  ||  【野菜】: {vege_display}")
            
            time.sleep(0.5)            
    except KeyboardInterrupt:
        print("\n計測を終了しました。")
    finally:
        GPIO.cleanup()
        print("GPIOをクリーンアップしました。")

if __name__ == "__main__":
    main()
