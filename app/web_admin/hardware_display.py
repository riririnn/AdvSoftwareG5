"""
LED・ブザー・確認ボタン・LCD電子値札制御

仕様:
- normal判定: 緑LED ON、赤LED OFF、ブザー停止
- theft判定 : 赤LED ON、緑LED OFF、確認ボタンが押されるまでブザー鳴動
- 確認ボタンを押すと、ブザーだけ停止する
- LCDには sensor_1 に設定された商品の英語ラベル、価格、在庫数、単重量を表示する

1602 LCDは日本語を直接表示できないため、LCDへ送る文字列はASCIIへ制限する。
WindowsやGPIO未接続環境ではエラーでWebを止めない。
"""

from pathlib import Path
import importlib.util
import os
import threading
import unicodedata

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
# 実機で `sudo i2cdetect -y 1` を実行して確認する。
LCD_ADDRESS = int(os.getenv("LCD_ADDRESS", "0x3f"), 0)
LCD_COLS = 16
LCD_ROWS = 2
LCD_CHARMAP = os.getenv("LCD_CHARMAP", "A00")

BASE_DIR = Path(__file__).resolve().parent
APP_CONFIG_PATH = BASE_DIR.parent / "config.py"

red_led = None
green_led = None
buzzer = None
confirm_button = None
lcd = None
_lcd_lock = threading.RLock()


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
                cols=LCD_COLS,
                rows=LCD_ROWS,
                charmap=LCD_CHARMAP,
                # 自動改行と手動改行を併用すると表示位置がずれるため無効化する。
                auto_linebreaks=False,
            )
            lcd.clear()
            print(
                "LCD電子値札を初期化しました。"
                f"I2Cアドレス: {hex(LCD_ADDRESS)}, charmap: {LCD_CHARMAP}"
            )
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

    try:
        shortage = max(0, int(shortage))
    except Exception:
        shortage = 0

    write_lcd("Payment NG", f"Short {shortage}Y")
    print(f"万引き・未払い判定: 不足金額 {shortage}円。確認ボタンでブザー停止。")


def stop_buzzer():
    """確認ボタン押下時にブザーだけ止める。赤LEDは警告状態として残す。"""
    if buzzer:
        buzzer.off()
    print("確認ボタンが押されたため、ブザーを停止しました。")


def _ascii_text(value):
    """
    LCDへ送れるASCII文字列へ変換する。

    日本語や全角記号が誤って渡っても、LCDコントローラへUTF-8の複数バイトを
    送らないようにする。英数字・半角記号以外は安全な '?' に置き換える。
    """
    text = unicodedata.normalize("NFKC", str(value or ""))
    return text.encode("ascii", errors="replace").decode("ascii")


def _fit_lcd_line(value):
    """16文字に切り詰め、残りを空白で埋める。"""
    return _ascii_text(value)[:LCD_COLS].ljust(LCD_COLS)


def write_lcd(line1, line2=""):
    """
    LCDに2行表示する。

    crlf()は使用せず、各行の先頭座標へ直接カーソルを移動する。
    以前の長い文字が残らないよう、各行を16文字分の空白で埋める。
    """
    if not lcd:
        return

    first = _fit_lcd_line(line1)
    second = _fit_lcd_line(line2)

    try:
        with _lcd_lock:
            lcd.clear()
            lcd.cursor_pos = (0, 0)
            lcd.write_string(first)
            lcd.cursor_pos = (1, 0)
            lcd.write_string(second)
    except Exception as error:
        print("LCD表示に失敗しました:", error)


def show_no_product():
    """sensor_1に商品が設定されていないときの表示。"""
    write_lcd("No Product", "Set sensor_1")
    print("電子値札: sensor_1の商品が未設定です。")


def show_product(label, price=0, count=0, weight=0):
    """商品情報を電子値札へ表示する。"""
    label = _ascii_text(label).strip() or "Product"

    try:
        price = max(0, int(price))
    except Exception:
        price = 0

    try:
        count = max(0, int(count))
    except Exception:
        count = 0

    try:
        weight = max(0, int(weight))
    except Exception:
        weight = 0

    # 例: 1行目 "tomato"、2行目 "150Y 10pc 100g"
    write_lcd(label, f"{price}Y {count}pc {weight}g")
    print(f"電子値札表示: {label} {price}円 在庫{count}個 {weight}g")


def show_current_product_from_store():
    """
    現在ロード済みのWeb管理データからsensor_1の商品をLCDへ表示する。

    data_storeは遅延importし、循環importを避ける。
    """
    try:
        try:
            from . import data_store
        except ImportError:
            import data_store

        settings = data_store.get_weight_sensor_settings()
        targets = settings.get("weight_sensor_targets", {}) or {}
        product_id = str(targets.get("sensor_1", "") or "").strip()
        products = data_store.get_products()
        inventory = data_store.get_inventory()

        product = products.get(product_id)
        if not product or product_id not in inventory:
            show_no_product()
            return False

        show_product(
            label=product.get("label", "Product"),
            price=product.get("price", 0),
            count=inventory.get(product_id, 0),
            weight=product.get("weight", 0),
        )
        return True
    except Exception as error:
        print("Web管理データからLCD表示を更新できませんでした:", error)
        return False


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
    起動直後など、Web管理データがまだ選択されていないときにconfig.pyから表示する。

    通常の登録・削除・センサー変更後は show_current_product_from_store() を使う。
    """
    module = load_config_module()
    if module is None:
        show_no_product()
        return False

    target_label = str(getattr(module, "TARGET_VEGETABLE", "") or "").strip()
    prices = getattr(module, "VEGETABLE_PRICES", {}) or {}
    weights = getattr(module, "VEGETABLE_WEIGHTS", {}) or {}

    if not target_label:
        show_no_product()
        return False

    try:
        price = int(prices.get(target_label, 0) if isinstance(prices, dict) else prices)
    except Exception:
        price = 0

    try:
        weight = int(weights.get(target_label, 0) if isinstance(weights, dict) else weights)
    except Exception:
        weight = 0

    # config.pyには在庫数がないため、起動直後だけ0個として表示する。
    show_product(target_label, price=price, count=0, weight=weight)
    return True
