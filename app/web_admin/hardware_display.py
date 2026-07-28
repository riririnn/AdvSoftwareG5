"""
LED・ブザー・確認ボタン・LCD電子値札制御

仕様:
- normal判定: 緑LED ON、赤LED OFF、ブザー停止
- theft判定 : 赤LED ON、緑LED OFF、確認ボタンが押されるまでブザー鳴動
- 確認ボタンを押すと、ブザーだけ停止する
- LCDには sensor_1 に設定された商品名を半角カタカナで表示する
- 2行目には「1ｺ 100ｸﾞﾗﾑ 150ｴﾝ」の形式で、1個当たりの重量と価格を表示する

1602 LCDのA00文字マップで表示できるASCIIと半角カタカナだけを送る。
WindowsやGPIO未接続環境ではエラーでWebを止めない。
"""

from pathlib import Path
import importlib.util
import os
import threading

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


# YOLOの商品ラベルから、LCD表示用の半角カタカナへ変換する。
# 濁点・半濁点はLCD上で1文字分を使用するため、全て16文字以内に収めている。
LCD_KATAKANA_NAMES = {
    "almond": "ｱｰﾓﾝﾄﾞ",
    "apple": "ﾘﾝｺﾞ",
    "asparagus": "ｱｽﾊﾟﾗｶﾞｽ",
    "avocado": "ｱﾎﾞｶﾄﾞ",
    "banana": "ﾊﾞﾅﾅ",
    "beans": "ﾏﾒ",
    "beet": "ﾋﾞｰﾂ",
    "bell pepper": "ﾊﾟﾌﾟﾘｶ",
    "blackberry": "ﾌﾞﾗｯｸﾍﾞﾘｰ",
    "blueberry": "ﾌﾞﾙｰﾍﾞﾘｰ",
    "broccoli": "ﾌﾞﾛｯｺﾘｰ",
    "brussels sprouts": "ﾒｷｬﾍﾞﾂ",
    "cabbage": "ｷｬﾍﾞﾂ",
    "carrot": "ﾆﾝｼﾞﾝ",
    "cauliflower": "ｶﾘﾌﾗﾜｰ",
    "celery": "ｾﾛﾘ",
    "cherry": "ｻｸﾗﾝﾎﾞ",
    "corn": "ﾄｳﾓﾛｺｼ",
    "cucumber": "ｷｭｳﾘ",
    "egg": "ﾀﾏｺﾞ",
    "eggplant": "ﾅｽ",
    "garlic": "ﾆﾝﾆｸ",
    "grape": "ﾌﾞﾄﾞｳ",
    "green bean": "ｲﾝｹﾞﾝ",
    "green onion": "ﾈｷﾞ",
    "hot pepper": "ﾄｳｶﾞﾗｼ",
    "kiwi": "ｷｳｲ",
    "lemon": "ﾚﾓﾝ",
    "lettuce": "ﾚﾀｽ",
    "lime": "ﾗｲﾑ",
    "mandarin": "ﾐｶﾝ",
    "mushroom": "ｷﾉｺ",
    "onion": "ﾀﾏﾈｷﾞ",
    "orange": "ｵﾚﾝｼﾞ",
    "pattypan squash": "ﾊﾟﾃｨﾊﾟﾝｶﾎﾞﾁｬ",
    "pea": "ｴﾝﾄﾞｳﾏﾒ",
    "peach": "ﾓﾓ",
    "pear": "ﾅｼ",
    "pineapple": "ﾊﾟｲﾅｯﾌﾟﾙ",
    "potato": "ｼﾞｬｶﾞｲﾓ",
    "pumpkin": "ｶﾎﾞﾁｬ",
    "radish": "ﾗﾃﾞｨｯｼｭ",
    "raspberry": "ﾗｽﾞﾍﾞﾘｰ",
    "strawberry": "ｲﾁｺﾞ",
    "tomato": "ﾄﾏﾄ",
    "vegetable marrow": "ﾍﾞｼﾞﾀﾌﾞﾙﾏﾛｰ",
    "watermelon": "ｽｲｶ",
}

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


def _lcd_text(value):
    """
    LCDへ送信できる文字だけを残す。

    使用を許可する文字:
    - ASCIIの表示可能文字
    - Unicodeの半角カタカナ（U+FF61～U+FF9F）

    それ以外のひらがな・漢字・全角カタカナなどは「?」へ置き換える。
    半角カタカナを全角へ変換してしまうため、NFKC正規化は行わない。
    """
    text = str(value or "")
    result = []

    for character in text:
        code_point = ord(character)

        if 0x20 <= code_point <= 0x7E:
            result.append(character)
        elif 0xFF61 <= code_point <= 0xFF9F:
            result.append(character)
        elif character in "\r\n\t":
            result.append(" ")
        else:
            result.append("?")

    return "".join(result)


def _fit_lcd_line(value):
    """LCDの1行を16文字に切り詰め、残りを空白で埋める。"""
    return _lcd_text(value)[:LCD_COLS].ljust(LCD_COLS)


def _format_unit_price_line(weight, price):
    """
    1個当たりの重量と価格をLCDの2行目用に整形する。

    標準表示例: 「1ｺ 100ｸﾞﾗﾑ 150ｴﾝ」
    16文字を超える場合は、末尾の単位が欠けないよう段階的に短縮する。
    """
    candidates = [
        f"1ｺ {weight}ｸﾞﾗﾑ {price}ｴﾝ",
        f"1ｺ {weight}g {price}ｴﾝ",
        f"{weight}g {price}ｴﾝ",
    ]

    for candidate in candidates:
        if len(candidate) <= LCD_COLS:
            return candidate

    return candidates[-1][:LCD_COLS]


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
    write_lcd("ｼｮｳﾋﾝ ﾅｼ", "ｾﾝｻｰ ﾐｾｯﾃｲ")
    print("電子値札: sensor_1の商品が未設定です。")


def show_product(label, price=0, count=0, weight=0):
    """
    商品情報を電子値札へ表示する。

    在庫数はWeb管理画面で管理し、電子値札には1個当たりの重量と価格を表示する。
    """
    label_key = str(label or "").strip().lower()
    lcd_name = LCD_KATAKANA_NAMES.get(label_key)

    # 未登録ラベルは英数字のラベルをそのまま使用する。
    if not lcd_name:
        lcd_name = _lcd_text(label_key).strip() or "ｼｮｳﾋﾝ"

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

    # 例: 1行目「ｱｰﾓﾝﾄﾞ」、2行目「1ｺ 100ｸﾞﾗﾑ 150ｴﾝ」
    detail_line = _format_unit_price_line(weight, price)
    write_lcd(lcd_name, detail_line)
    print(
        f"電子値札表示: {lcd_name} / "
        f"1個 {weight}グラム {price}円（登録在庫: {count}個）"
    )


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

    # config.pyには在庫数がないため、互換性維持のためcount=0を渡す。LCDには在庫数を表示しない。
    show_product(target_label, price=price, count=0, weight=weight)
    return True
