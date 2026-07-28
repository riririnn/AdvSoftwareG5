"""
LED・ブザー・確認ボタン・LCD電子値札制御

仕様:
- normal判定: 緑LED ON、赤LED OFF、ブザー停止
- theft判定 : 赤LED ON、緑LED OFF、確認ボタンが押されるまでブザー鳴動
- 確認ボタンを押すと、ブザーだけ停止する
- LCDには sensor_1 に設定された商品名を半角カタカナで表示する
- 1行目には「1ｺ 商品名」、2行目には「100ｸﾞﾗﾑ 150ｴﾝ」の形式で表示する

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

# I2C LCDのアドレス。多くは0x27または0x3f。
# 実機で「sudo i2cdetect -y 1」を実行して確認する。
LCD_ADDRESS = int(os.getenv("LCD_ADDRESS", "0x3f"), 0)
LCD_COLS = 16
LCD_ROWS = 2
LCD_CHARMAP = os.getenv("LCD_CHARMAP", "A00")


# YOLOの商品ラベルから、LCD表示用の半角カタカナへ変換する。
# 濁点・半濁点もLCD上では1文字分を使用する。
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
PRODUCT_SETTINGS_PATH = BASE_DIR.parent / "product_settings.py"

red_led = None
green_led = None
buzzer = None
confirm_button = None
lcd = None

# Web処理などからLCDへ同時に書き込まないようにする。
_lcd_lock = threading.RLock()


def setup_hardware():
    """Flask起動時に1回だけ呼び出す。"""
    global red_led, green_led, buzzer, confirm_button, lcd

    # LED・ブザー・確認ボタン
    if LED is None or Buzzer is None or Button is None:
        print(
            "gpiozero が使えないため、"
            "LED・ブザー・確認ボタン制御は無効です。"
        )
    else:
        try:
            red_led = LED(RED_LED_PIN)
            green_led = LED(GREEN_LED_PIN)
            buzzer = Buzzer(BUZZER_PIN)

            confirm_button = Button(
                CONFIRM_BUTTON_PIN,
                pull_up=True,
                bounce_time=0.1,
            )
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
            print(
                "LED・ブザー・確認ボタンの初期化に失敗しました:",
                error,
            )

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

                # 自動改行と手動のカーソル移動が競合しないようにする。
                auto_linebreaks=False,
            )

            lcd.clear()

            print(
                "LCD電子値札を初期化しました。"
                f"I2Cアドレス: {hex(LCD_ADDRESS)}, "
                f"charmap: {LCD_CHARMAP}"
            )

        except Exception as error:
            print("LCD電子値札の初期化に失敗しました:", error)
            lcd = None


def show_idle():
    """待機状態にする。"""
    if red_led:
        red_led.off()

    if green_led:
        green_led.off()

    if buzzer:
        buzzer.off()


def show_paid():
    """支払い完了時にLEDとブザーだけを制御する。"""
    if red_led:
        red_led.off()

    if green_led:
        green_led.on()

    if buzzer:
        buzzer.off()

    # LCDは商品名・単重量・価格を表示し続けるため更新しない。
    print("支払い完了: 緑LED ON、ブザー停止")


def show_unpaid(shortage=0):
    """未払い判定時にLEDとブザーだけを制御する。"""
    if red_led:
        red_led.on()

    if green_led:
        green_led.off()

    if buzzer:
        buzzer.on()

    try:
        shortage = max(0, int(shortage))
    except (TypeError, ValueError):
        shortage = 0

    # LCDは商品名・単重量・価格を表示し続けるため更新しない。
    print(
        f"万引き・未払い判定: 不足金額 {shortage}円。"
        "確認ボタンでブザー停止。"
    )


def stop_buzzer():
    """
    確認ボタン押下時にブザーだけを停止する。

    赤LEDは警告状態として残す。
    """
    if buzzer:
        buzzer.off()

    print("確認ボタンが押されたため、ブザーを停止しました。")


def _lcd_text(value):
    """
    LCDへ送信できる文字だけを残す。

    使用を許可する文字:
    - ASCIIの表示可能文字
    - Unicodeの半角カタカナ（U+FF61～U+FF9F）

    それ以外のひらがな・漢字・全角カタカナなどは
    「?」へ置き換える。

    半角カタカナを全角へ変換してしまうため、
    NFKC正規化は行わない。
    """
    text = str(value or "")
    result = []

    for character in text:
        code_point = ord(character)

        # 半角英数字・半角記号
        if 0x20 <= code_point <= 0x7E:
            result.append(character)

        # 半角カタカナ
        elif 0xFF61 <= code_point <= 0xFF9F:
            result.append(character)

        # 改行・タブは空白に置き換える。
        elif character in "\r\n\t":
            result.append(" ")

        # LCDで表示できない文字
        else:
            result.append("?")

    return "".join(result)


def _fit_lcd_line(value):
    """
    LCDの1行を16文字に整形する。

    16文字を超えた部分は切り捨て、
    短い場合は右側を空白で埋める。
    """
    return _lcd_text(value)[:LCD_COLS].ljust(LCD_COLS)


def _format_weight_price_line(weight, price):
    """
    1個当たりの重量と価格をLCDの2行目用に整形する。

    標準表示:
        100ｸﾞﾗﾑ 150ｴﾝ

    1000g・1000円の場合:
        1000ｸﾞﾗﾑ 1000ｴﾝ

    「1ｺ」は1行目へ移動しているため、
    重量と価格に使用できる文字数を増やしている。

    さらに大きな数値で16文字を超える場合は、
    単位を段階的に短くする。
    """
    candidates = [
        f"{weight}ｸﾞﾗﾑ {price}ｴﾝ",
        f"{weight}g {price}ｴﾝ",
        f"{weight}g {price}Y",
    ]

    for candidate in candidates:
        if len(candidate) <= LCD_COLS:
            return candidate

    # 最後の候補でも16文字を超える場合は、
    # 16文字で切り詰める。
    return candidates[-1][:LCD_COLS]


def write_lcd(line1, line2=""):
    """
    LCDへ2行の文字列を表示する。

    crlf()は使用せず、各行の先頭座標へ
    カーソルを直接移動する。

    以前表示していた長い文字が残らないよう、
    各行を16文字分の空白で埋める。
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
    """商品が設定されていない場合は、その状態だけを表示する。"""
    write_lcd(
        "ｼｮｳﾋﾝ ﾐｾｯﾃｲ",
        "",
    )

    print("電子値札: 商品未設定")


def show_product(label, price=0, count=0, weight=0):
    """
    商品情報を電子値札へ表示する。

    1行目:
        商品名 1コ

    2行目:
        重量 グラム 価格 エン

    在庫数はWeb管理画面で管理し、
    電子値札には表示しない。
    """
    label_key = str(label or "").strip().lower()
    lcd_name = LCD_KATAKANA_NAMES.get(label_key)

    if not lcd_name:
        lcd_name = _lcd_text(label_key).strip() or "ｼｮｳﾋﾝ"

    try:
        price = max(0, int(price))
    except (TypeError, ValueError):
        price = 0

    try:
        count = max(0, int(count))
    except (TypeError, ValueError):
        count = 0

    try:
        weight = max(0, int(weight))
    except (TypeError, ValueError):
        weight = 0

    # 1行目：商品名の後ろに「1コ」
    product_line = f"{lcd_name} 1ｺ"

    # 2行目：1個当たりの重量と価格
    detail_line = _format_weight_price_line(
        weight=weight,
        price=price,
    )

    write_lcd(
        product_line,
        detail_line,
    )

    print(
        f"電子値札表示: {lcd_name} 1個 / "
        f"{weight}グラム {price}円 "
        f"（登録在庫: {count}個）"
    )


def show_current_product_from_store():
    """
    現在ロード済みのWeb管理データから、
    sensor_1の商品をLCDへ表示する。

    data_storeは遅延importし、
    循環importを避ける。
    """
    try:
        try:
            from . import data_store
        except ImportError:
            import data_store

        settings = data_store.get_weight_sensor_settings()
        targets = settings.get(
            "weight_sensor_targets",
            {},
        ) or {}

        product_id = str(
            targets.get("sensor_1", "") or ""
        ).strip()

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
        print(
            "Web管理データからLCD表示を更新できませんでした:",
            error,
        )
        return False


def load_config_module():
    """app/product_settings.pyを直接読み込む。"""
    if not PRODUCT_SETTINGS_PATH.exists():
        print("product_settings.pyが見つかりません:", PRODUCT_SETTINGS_PATH)
        return None

    try:
        spec = importlib.util.spec_from_file_location(
            "mujin_runtime_product_settings",
            PRODUCT_SETTINGS_PATH,
        )

        if spec is None or spec.loader is None:
            print("product_settings.pyの読み込み設定を作成できませんでした。")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module

    except Exception as error:
        print("product_settings.pyの読み込みに失敗しました:", error)
        return None


def show_current_product_from_config():
    """
    起動直後など、Web管理データがまだ選択されていない場合に、
    product_settings.pyから商品情報を取得して表示する。

    通常の商品登録・削除・センサー変更後は、
    show_current_product_from_store()を使用する。
    """
    module = load_config_module()

    if module is None:
        show_no_product()
        return False

    target_label = str(
        getattr(module, "TARGET_VEGETABLE", "") or ""
    ).strip()

    prices = getattr(
        module,
        "VEGETABLE_PRICES",
        {},
    ) or {}

    weights = getattr(
        module,
        "VEGETABLE_WEIGHTS",
        {},
    ) or {}

    if not target_label:
        show_no_product()
        return False

    try:
        if isinstance(prices, dict):
            price = int(prices.get(target_label, 0))
        else:
            price = int(prices)
    except (TypeError, ValueError):
        price = 0

    try:
        if isinstance(weights, dict):
            weight = int(weights.get(target_label, 0))
        else:
            weight = int(weights)
    except (TypeError, ValueError):
        weight = 0

    # config.pyには在庫数がないため、count=0を渡す。
    # LCDには在庫数を表示しない。
    show_product(
        label=target_label,
        price=price,
        count=0,
        weight=weight,
    )

    return True
