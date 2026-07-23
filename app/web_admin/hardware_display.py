"""
LED・ブザー・確認ボタン・LCD電子値札制御

仕様:
- normal判定: 緑LED ON、赤LED OFF、ブザー停止
- theft判定 : 赤LED ON、緑LED OFF、確認ボタンが押されるまでブザー鳴動
- 確認ボタンを押すと、ブザーだけ停止する
- LCDには app/config.py の TARGET_VEGETABLE, VEGETABLE_PRICES, VEGETABLE_WEIGHTS を表示する

WindowsやGPIO未接続環境ではエラーでWebを止めない。
"""

from pathlib import Path
import importlib.util

try:
    from gpiozero import LED, Buzzer, Button
except Exception:
    LED = None
    Buzzer = None
    Button = None

try:
    from RPLCD.i2c import CharLCD
except Exception:
    CharLCD = None


# BCM番号。配線に合わせて変更してください。
RED_LED_PIN = 17
GREEN_LED_PIN = 27
BUZZER_PIN = 22
CONFIRM_BUTTON_PIN = 23

# I2C LCDのアドレス。多くは 0x27 または 0x3f。
# 実機で `sudo i2cdetect -y 1` を実行し 0x3f で応答することを確認済み。
LCD_ADDRESS = 0x3f

BASE_DIR = Path(__file__).resolve().parent
# app/web_admin/hardware_display.py から見た制御側共通設定ファイル
APP_CONFIG_PATH = BASE_DIR.parent / "config.py"

red_led = None
green_led = None
buzzer = None
confirm_button = None
lcd = None


def setup_hardware():
    """Flask起動時に1回だけ呼ぶ。"""
    global red_led, green_led, buzzer, confirm_button, lcd

    # LED・ブザー・確認ボタン
    if LED is None or Buzzer is None or Button is None:
        print("gpiozero が使えないため、LED・ブザー・確認ボタン制御は無効です。")
    else:
        try:
            red_led = LED(RED_LED_PIN)
            green_led = LED(GREEN_LED_PIN)
            buzzer = Buzzer(BUZZER_PIN)
            confirm_button = Button(CONFIRM_BUTTON_PIN, pull_up=True, bounce_time=0.1)
            confirm_button.when_pressed = stop_buzzer

            show_idle()
            print("LED・ブザー・確認ボタンを初期化しました。")
            print(
                f"赤LED: GPIO{RED_LED_PIN}, "
                f"緑LED: GPIO{GREEN_LED_PIN}, "
                f"ブザー: GPIO{BUZZER_PIN}, "
                f"確認ボタン: GPIO{CONFIRM_BUTTON_PIN}"
            )
        except Exception as error:
            print("LED・ブザー・確認ボタンの初期化に失敗しました:", error)
            red_led = None
            green_led = None
            buzzer = None
            confirm_button = None

    # 電子値札LCD
    if CharLCD is None:
        print("RPLCD が使えないため、LCD電子値札は無効です。")
    else:
        try:
            lcd = CharLCD(
                i2c_expander="PCF8574",
                address=LCD_ADDRESS,
                port=1,
                cols=16,
                rows=2,
                charmap="A00",
                auto_linebreaks=True,
            )
            print(f"LCD電子値札を初期化しました。I2Cアドレス: {hex(LCD_ADDRESS)}")
        except Exception as error:
            print("LCD電子値札の初期化に失敗しました:", error)
            lcd = None


def show_idle():
    """待機状態。"""
    if red_led:
        red_led.off()
    if green_led:
        green_led.off()
    if buzzer:
        buzzer.off()


def show_paid():
    """支払い完了。"""
    if red_led:
        red_led.off()
    if green_led:
        green_led.on()
    if buzzer:
        buzzer.off()

    write_lcd("Payment OK", "Thank you")
    print("支払い完了: 緑LED ON、ブザー停止")


def show_unpaid(shortage=0):
    """万引き・未払い判定。確認ボタンが押されるまで鳴り続ける。"""
    if red_led:
        red_led.on()
    if green_led:
        green_led.off()
    if buzzer:
        buzzer.on()

    write_lcd("Payment NG", f"Short:{shortage}yen")
    print(f"万引き・未払い判定: 不足金額 {shortage}円。確認ボタンでブザー停止。")


def stop_buzzer():
    """確認ボタン押下時にブザーだけ止める。赤LEDは警告状態として残す。"""
    if buzzer:
        buzzer.off()
    print("確認ボタンが押されたため、ブザーを停止しました。")


def write_lcd(line1, line2=""):
    """LCDに2行表示する。16文字を超える分は切り捨てる。"""
    if not lcd:
        return

    try:
        lcd.clear()
        lcd.write_string(str(line1)[:16])
        lcd.crlf()
        lcd.write_string(str(line2)[:16])
    except Exception as error:
        print("LCD表示に失敗しました:", error)


def load_config_module():
    """app/config.py を直接読み込む。"""
    if not APP_CONFIG_PATH.exists():
        print("config.py が見つかりません:", APP_CONFIG_PATH)
        return None

    try:
        spec = importlib.util.spec_from_file_location("mujin_runtime_config", APP_CONFIG_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as error:
        print("config.py の読み込みに失敗しました:", error)
        return None


def show_current_product_from_config():
    """
    電子値札に現在のsensor_1商品を表示する。
    Webの重量センサー設定で sensor_1 を変更すると config.py が更新されるため、
    その内容を読み直してLCDに反映する。
    """
    module = load_config_module()
    if module is None:
        return

    target_label = str(getattr(module, "TARGET_VEGETABLE", "") or "")
    prices = getattr(module, "VEGETABLE_PRICES", {}) or {}
    weights = getattr(module, "VEGETABLE_WEIGHTS", {}) or {}

    if not target_label:
        write_lcd("No item", "Set sensor_1")
        print("電子値札: sensor_1の商品が未設定です。")
        return

    try:
        if isinstance(prices, dict):
            price = int(prices.get(target_label, 0) or 0)
        else:
            price = int(prices or 0)
    except Exception:
        price = 0

    try:
        if isinstance(weights, dict):
            weight = int(weights.get(target_label, 0) or 0)
        else:
            weight = int(weights or 0)
    except Exception:
        weight = 0

    # 1602 LCDは日本語表示が難しいため、YOLOラベルを表示する。
    write_lcd(f"{target_label} {price}Y", f"{weight}g Ready")
    print(f"電子値札表示: {target_label} {price}円 {weight}g")
