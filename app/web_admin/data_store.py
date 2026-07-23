from datetime import datetime
from pathlib import Path
import json
import importlib.util


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
RUNTIME_DIR = PROJECT_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# 制御側と同じ app/config.py をWeb管理画面から更新する
APP_CONFIG_PATH = BASE_DIR.parent / "config.py"

# Web管理画面用の保存ファイル（Git管理外のruntimeへ保存）
DATA_STORE_PATH = RUNTIME_DIR / "data_store.json"


products = {}
inventory = {}

sales_history = []
notification_history = []
ai_history = []

weight_sensor_count = 1
weight_sensor_targets = {
    "sensor_1": ""
}


# ==========================================
# 新データセットの商品ラベル
# ==========================================

DATASET_LABELS = ['almond', 'apple', 'asparagus', 'avocado', 'banana', 'beans', 'beet', 'bell pepper', 'blackberry', 'blueberry', 'broccoli', 'brussels sprouts', 'cabbage', 'carrot', 'cauliflower', 'celery', 'cherry', 'corn', 'cucumber', 'egg', 'eggplant', 'garlic', 'grape', 'green bean', 'green onion', 'hot pepper', 'kiwi', 'lemon', 'lettuce', 'lime', 'mandarin', 'mushroom', 'onion', 'orange', 'pattypan squash', 'pea', 'peach', 'pear', 'pineapple', 'potato', 'pumpkin', 'radish', 'raspberry', 'strawberry', 'tomato', 'vegetable marrow', 'watermelon']


# YOLOラベル（英語）から管理画面用の商品名（日本語）へ変換する
LABEL_TO_DISPLAY_NAME = {
    "almond": "アーモンド",
    "apple": "りんご",
    "asparagus": "アスパラガス",
    "avocado": "アボカド",
    "banana": "バナナ",
    "beans": "豆",
    "beet": "ビーツ",
    "bell pepper": "パプリカ",
    "blackberry": "ブラックベリー",
    "blueberry": "ブルーベリー",
    "broccoli": "ブロッコリー",
    "brussels sprouts": "芽キャベツ",
    "cabbage": "キャベツ",
    "carrot": "にんじん",
    "cauliflower": "カリフラワー",
    "celery": "セロリ",
    "cherry": "さくらんぼ",
    "corn": "とうもろこし",
    "cucumber": "きゅうり",
    "egg": "卵",
    "eggplant": "なす",
    "garlic": "にんにく",
    "grape": "ぶどう",
    "green bean": "いんげん",
    "green onion": "ねぎ",
    "hot pepper": "唐辛子",
    "kiwi": "キウイ",
    "lemon": "レモン",
    "lettuce": "レタス",
    "lime": "ライム",
    "mandarin": "みかん",
    "mushroom": "きのこ",
    "onion": "玉ねぎ",
    "orange": "オレンジ",
    "pattypan squash": "パティパンスカッシュ",
    "pea": "えんどう豆",
    "peach": "桃",
    "pear": "梨",
    "pineapple": "パイナップル",
    "potato": "じゃがいも",
    "pumpkin": "かぼちゃ",
    "radish": "ラディッシュ",
    "raspberry": "ラズベリー",
    "strawberry": "いちご",
    "tomato": "トマト",
    "vegetable marrow": "ベジタブルマロー",
    "watermelon": "すいか"
}

DISPLAY_NAME_TO_LABEL = {
    display_name: label
    for label, display_name in LABEL_TO_DISPLAY_NAME.items()
}


DEFAULT_PRICES = {
    "almond": 150,
    "apple": 150,
    "asparagus": 100,
    "avocado": 100,
    "banana": 120,
    "beans": 100,
    "beet": 100,
    "bell pepper": 100,
    "blackberry": 100,
    "blueberry": 100,
    "broccoli": 100,
    "brussels sprouts": 100,
    "cabbage": 100,
    "carrot": 100,
    "cauliflower": 100,
    "celery": 100,
    "cherry": 100,
    "corn": 100,
    "cucumber": 100,
    "egg": 100,
    "eggplant": 100,
    "garlic": 100,
    "grape": 100,
    "green bean": 100,
    "green onion": 100,
    "hot pepper": 100,
    "kiwi": 100,
    "lemon": 100,
    "lettuce": 100,
    "lime": 100,
    "mandarin": 100,
    "mushroom": 100,
    "onion": 100,
    "orange": 120,
    "pattypan squash": 100,
    "pea": 100,
    "peach": 100,
    "pear": 100,
    "pineapple": 100,
    "potato": 80,
    "pumpkin": 100,
    "radish": 100,
    "raspberry": 100,
    "strawberry": 100,
    "tomato": 150,
    "vegetable marrow": 100,
    "watermelon": 100
}


DEFAULT_WEIGHTS = {
    "almond": 100,
    "apple": 200,
    "asparagus": 100,
    "avocado": 100,
    "banana": 120,
    "beans": 100,
    "beet": 100,
    "bell pepper": 100,
    "blackberry": 100,
    "blueberry": 100,
    "broccoli": 100,
    "brussels sprouts": 100,
    "cabbage": 100,
    "carrot": 100,
    "cauliflower": 100,
    "celery": 100,
    "cherry": 100,
    "corn": 100,
    "cucumber": 100,
    "egg": 60,
    "eggplant": 80,
    "garlic": 100,
    "grape": 100,
    "green bean": 100,
    "green onion": 100,
    "hot pepper": 100,
    "kiwi": 100,
    "lemon": 100,
    "lettuce": 100,
    "lime": 100,
    "mandarin": 100,
    "mushroom": 100,
    "onion": 100,
    "orange": 180,
    "pattypan squash": 100,
    "pea": 100,
    "peach": 100,
    "pear": 100,
    "pineapple": 100,
    "potato": 150,
    "pumpkin": 100,
    "radish": 100,
    "raspberry": 100,
    "strawberry": 100,
    "tomato": 100,
    "vegetable marrow": 100,
    "watermelon": 100
}


# ==========================================
# 基本変換・商品ID生成
# ==========================================

def get_japanese_name(label):
    """YOLOラベルを日本語の商品名に変換する。"""
    return LABEL_TO_DISPLAY_NAME.get(label, label)


def strip_variant_suffix(item_name):
    """
    旧形式の商品名から日本語名だけ取り出す。
    例:
    トマト（100g・150円） -> トマト
    """
    item_name = str(item_name or "")

    if "（" in item_name and item_name.endswith("）"):
        return item_name.split("（", 1)[0]

    return item_name


def normalize_label(value):
    """
    英語YOLOラベル・日本語商品名・旧バリエーション名からYOLOラベルを取得する。
    """
    value = str(value or "").strip()

    if value in DATASET_LABELS:
        return value

    base_name = strip_variant_suffix(value)

    if base_name in DISPLAY_NAME_TO_LABEL:
        return DISPLAY_NAME_TO_LABEL[base_name]

    if value in DISPLAY_NAME_TO_LABEL:
        return DISPLAY_NAME_TO_LABEL[value]

    if value in products:
        return products[value].get("label", value)

    for product in products.values():
        if product.get("display_name") == value:
            return product.get("label", value)

    return value


def make_product_id(label, price, weight):
    """
    内部管理用の商品IDを作る。
    画面には表示しない。

    例:
    almond__100g__150yen
    tomato__200g__250yen
    """
    label = normalize_label(label)

    try:
        price = int(price)
    except Exception:
        price = 0

    try:
        weight = int(weight)
    except Exception:
        weight = 0

    safe_label = str(label).strip().replace(" ", "_")
    return f"{safe_label}__{weight}g__{price}yen"


def format_variant_text(display_name, price, weight):
    """
    メッセージ用の表示文字列。
    商品名の列には使わず、登録結果や重複警告でだけ使う。
    """
    return f"{display_name}（{weight}g・{price}円）"


def get_product_display_name(item_name):
    """
    内部商品IDから、画面表示用の商品名だけを返す。
    """
    item_name = str(item_name or "")

    if item_name in products:
        return products[item_name].get("display_name", item_name)

    label = normalize_label(item_name)
    return get_japanese_name(label)


def get_product_variant_text(item_name):
    """
    内部商品IDから、商品名・単重量・価格を含む説明文字列を返す。
    重複警告などで使う。
    """
    item_name = str(item_name or "")

    if item_name in products:
        product = products[item_name]
        return format_variant_text(
            product.get("display_name", item_name),
            int(product.get("price", 0) or 0),
            int(product.get("weight", 0) or 0)
        )

    return item_name


def find_product_id_by_label(label, prefer_in_stock=True):
    """
    YOLOラベルから登録済みの商品IDを探す。
    同じラベルの商品が複数ある場合は、在庫がある商品を優先する。
    """
    label = normalize_label(label)
    candidates = []

    for product_id, product in products.items():
        if product.get("label") == label:
            candidates.append(product_id)

    if not candidates:
        return None

    if prefer_in_stock:
        for product_id in candidates:
            try:
                count = int(inventory.get(product_id, 0))
            except Exception:
                count = 0

            if count > 0:
                return product_id

    return candidates[0]


def get_display_name_by_label(item_label):
    """
    互換性のため名前は残しているが、戻り値は内部商品ID。

    session.jsonでは以下を受け取れる。
    - 内部商品ID: tomato__100g__150yen
    - 旧バリエーション名: トマト（100g・150円）
    - 日本語商品名: トマト
    - 英語YOLOラベル: tomato
    """
    item_label = str(item_label or "").strip()

    if item_label in products:
        return item_label

    label = normalize_label(item_label)
    matched = find_product_id_by_label(label, prefer_in_stock=True)
    if matched:
        return matched

    return item_label


# ==========================================
# config.py 書き込み用フォーマット
# ==========================================

def format_python_dict(data):
    if not data:
        return "{}"

    lines = ["{"]

    for key, value in data.items():
        if isinstance(value, str):
            lines.append(f'    "{key}": "{value}",')
        else:
            lines.append(f'    "{key}": {value},')

    lines.append("}")
    return "\n".join(lines)


def format_python_list(data):
    if not data:
        return "[]"

    lines = ["["]

    for value in data:
        lines.append(f'    "{value}",')

    lines.append("]")
    return "\n".join(lines)


def normalize_weight_sensor_target_value(value):
    """
    重量センサーの設定値を内部商品IDへ変換する。

    旧形式では weight_sensor_targets に YOLOラベルが入っていたため、
    その場合は現在登録されている在庫の中から該当する商品IDへ変換する。
    """
    value = str(value or "").strip()

    if value == "":
        return ""

    if value in products:
        return value

    label = normalize_label(value)
    matched_product_id = find_product_id_by_label(label, prefer_in_stock=True)

    if matched_product_id:
        return matched_product_id

    return ""


def normalize_weight_sensor_targets(count, targets):
    normalized = {}

    for i in range(1, count + 1):
        sensor_id = f"sensor_{i}"
        normalized[sensor_id] = normalize_weight_sensor_target_value(
            targets.get(sensor_id, "")
        )

    return normalized


# ==========================================
# 商品・在庫データの正規化
# ==========================================

def create_default_products():
    """
    47クラス分の商品候補を作る。
    初期在庫は空にするため、inventoryには入れない。
    """
    default_products = {}

    for label in DATASET_LABELS:
        display_name = get_japanese_name(label)
        price = int(DEFAULT_PRICES.get(label, 100))
        weight = int(DEFAULT_WEIGHTS.get(label, 100))
        product_id = make_product_id(label, price, weight)

        default_products[product_id] = {
            "display_name": display_name,
            "label": label,
            "price": price,
            "weight": weight,
            "active": True
        }

    return default_products


def merge_with_default_products(loaded_products):
    """
    Webの商品選択欄には、常に47種類の商品候補を表示する。

    app/config.py には、結合テスト用に tomato / eggplant だけが
    書かれている場合がある。
    その内容だけを products にすると、Webの商品選択欄も
    トマト・なすだけになってしまう。

    そこで、まず47種類のデフォルト商品マスタを作成し、
    data_store.json や config.py から読み込んだ登録済み商品を
    その上に重ねる。
    これにより、商品選択欄は47種類を維持しつつ、
    登録済み商品の価格・単重量のバリエーションも保持できる。
    """
    merged_products = create_default_products()

    if isinstance(loaded_products, dict):
        for product_id, product in loaded_products.items():
            if not isinstance(product, dict):
                continue
            merged_products[product_id] = product

    return merged_products


def normalize_products(raw_products):
    """
    既存のdata_store.jsonから商品情報を読み込む。
    古い形式の商品名キーは、内部商品IDへ変換する。
    """
    normalized = {}

    if not isinstance(raw_products, dict):
        return normalized

    for item_name, product in raw_products.items():
        if not isinstance(product, dict):
            continue

        label = product.get("label") or normalize_label(item_name)
        display_name = product.get("display_name") or get_japanese_name(label)
        display_name = strip_variant_suffix(display_name)

        try:
            price = int(product.get("price", DEFAULT_PRICES.get(label, 100)) or 0)
        except Exception:
            price = DEFAULT_PRICES.get(label, 100)

        try:
            weight = int(product.get("weight", DEFAULT_WEIGHTS.get(label, 100)) or 0)
        except Exception:
            weight = DEFAULT_WEIGHTS.get(label, 100)

        product_id = make_product_id(label, price, weight)

        normalized[product_id] = {
            "display_name": display_name,
            "label": label,
            "price": price,
            "weight": weight,
            "active": bool(product.get("active", True))
        }

    return normalized


def normalize_inventory(raw_inventory, current_products):
    """
    在庫情報を内部商品IDに変換する。
    古い形式の「トマト」や「トマト（100g・150円）」も可能な範囲で移行する。
    """
    normalized = {}

    if not isinstance(raw_inventory, dict):
        return normalized

    for item_name, count in raw_inventory.items():
        try:
            count = int(count)
        except Exception:
            count = 0

        if count < 0:
            count = 0

        if item_name in current_products:
            normalized[item_name] = count
            continue

        label = normalize_label(item_name)
        matched_id = None

        for product_id, product in current_products.items():
            if product.get("label") == label:
                matched_id = product_id
                break

        if matched_id:
            normalized[matched_id] = normalized.get(matched_id, 0) + count

    return normalized


# ==========================================
# data_store.json 読み込み・保存
# ==========================================

def load_web_store():
    global products, inventory, weight_sensor_count, weight_sensor_targets
    global sales_history, notification_history, ai_history

    if not DATA_STORE_PATH.exists():
        load_from_config_py()
        return

    try:
        with open(DATA_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        loaded_products = data.get("products", {})
        loaded_inventory = data.get("inventory", {})

        # data_store.jsonに保存されている商品だけでなく、
        # 47種類の商品候補も必ず保持する。
        # これにより、既存のdata_store.jsonがトマト・なすだけでも、
        # Webの商品登録プルダウンには全商品が表示される。
        loaded_normalized_products = normalize_products(loaded_products)
        products = merge_with_default_products(loaded_normalized_products)

        inventory = normalize_inventory(loaded_inventory, products)

        weight_sensor_count = int(data.get("weight_sensor_count", 1))
        if weight_sensor_count <= 0:
            weight_sensor_count = 1

        saved_targets = data.get("weight_sensor_targets", {})
        if not isinstance(saved_targets, dict):
            saved_targets = {}

        weight_sensor_targets = normalize_weight_sensor_targets(
            weight_sensor_count,
            saved_targets
        )

        loaded_sales_history = data.get("sales_history", [])
        loaded_notification_history = data.get("notification_history", [])
        loaded_ai_history = data.get("ai_history", [])

        sales_history = loaded_sales_history if isinstance(loaded_sales_history, list) else []
        notification_history = loaded_notification_history if isinstance(loaded_notification_history, list) else []
        ai_history = loaded_ai_history if isinstance(loaded_ai_history, list) else []

        save_web_store()

    except json.JSONDecodeError:
        print("data_store.json の形式が正しくありません。初期化します。")
        products = create_default_products()
        inventory = {}
        weight_sensor_count = 1
        weight_sensor_targets = {"sensor_1": ""}
        sales_history = []
        notification_history = []
        ai_history = []
        save_web_store()

    except Exception as error:
        print("data_store.json の読み込みに失敗しました:", error)
        products = create_default_products()
        inventory = {}
        weight_sensor_count = 1
        weight_sensor_targets = {"sensor_1": ""}
        sales_history = []
        notification_history = []
        ai_history = []
        save_web_store()


def save_web_store():
    data = {
        "products": products,
        "inventory": inventory,
        "weight_sensor_count": weight_sensor_count,
        "weight_sensor_targets": weight_sensor_targets,
        "sales_history": sales_history,
        "notification_history": notification_history,
        "ai_history": ai_history
    }

    with open(DATA_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ==========================================
# config.py から初期読み込み
# ==========================================

def load_from_config_py():
    global products, inventory, weight_sensor_count, weight_sensor_targets

    if not APP_CONFIG_PATH.exists():
        print("config.py が見つからないため、デフォルト商品マスタを使います:", APP_CONFIG_PATH)
        products = create_default_products()
        inventory = {}
        weight_sensor_count = 1
        weight_sensor_targets = {"sensor_1": ""}
        save_web_store()
        return

    try:
        spec = importlib.util.spec_from_file_location("app_config", APP_CONFIG_PATH)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)

        vegetable_prices = getattr(config_module, "VEGETABLE_PRICES", {})
        vegetable_weights = getattr(config_module, "VEGETABLE_WEIGHTS", {})
        config_sensor_count = getattr(config_module, "WEIGHT_SENSOR_COUNT", 1)
        config_sensor_targets = getattr(config_module, "WEIGHT_SENSOR_TARGETS", {})

        if not isinstance(vegetable_prices, dict):
            vegetable_prices = {}
        if not isinstance(vegetable_weights, dict):
            vegetable_weights = {}

        # app/config.py に書かれている商品が一部だけでも、
        # Webの商品選択欄には47種類の候補を表示したい。
        # そのため、まずデフォルト商品マスタを作り、
        # config.py の商品設定を上書き・追加する。
        loaded_config_products = {}

        if vegetable_prices:
            for label, price in vegetable_prices.items():
                label = normalize_label(label)
                display_name = get_japanese_name(label)
                weight = int(vegetable_weights.get(label, DEFAULT_WEIGHTS.get(label, 100)))
                price = int(price)
                product_id = make_product_id(label, price, weight)

                loaded_config_products[product_id] = {
                    "display_name": display_name,
                    "label": label,
                    "price": price,
                    "weight": weight,
                    "active": True
                }

        products = merge_with_default_products(loaded_config_products)

        inventory = {}

        weight_sensor_count = int(config_sensor_count)
        if weight_sensor_count <= 0:
            weight_sensor_count = 1

        if not isinstance(config_sensor_targets, dict):
            config_sensor_targets = {}

        weight_sensor_targets = normalize_weight_sensor_targets(
            weight_sensor_count,
            config_sensor_targets
        )

        save_web_store()

    except Exception as error:
        print("config.py からの商品情報読み込みに失敗しました:", error)
        products = create_default_products()
        inventory = {}
        weight_sensor_count = 1
        weight_sensor_targets = {"sensor_1": ""}
        save_web_store()


# ==========================================
# config.py への反映
# ==========================================

def get_label_for_weight_sensor_target(target_value):
    """
    data_store.json では重量センサー対象を内部商品IDで保持する。
    app/config.py へ書き出すときは制御側が使いやすいようにYOLOラベルへ変換する。
    """
    target_value = str(target_value or "").strip()

    if target_value == "":
        return ""

    if target_value in products:
        return products[target_value].get("label", "")

    return normalize_label(target_value)


def export_to_config_py():
    """
    Web管理画面で登録された商品情報と重量センサー設定を app/config.py に反映する。

    重要:
    - products には47種類の商品候補が入っている。
    - そのため products 全体を書き出すと、未登録の商品まで config.py に出てしまう。
    - config.py へは「現在の在庫 inventory に存在する商品だけ」を書き出す。
    - TARGET_VEGETABLE には sensor_1 に設定している商品のYOLOラベルを書き出す。
    """
    if not APP_CONFIG_PATH.exists():
        print("config.py が見つかりません:", APP_CONFIG_PATH)
        return False

    # =====================================================
    # 現在の在庫に登録されている商品だけを抽出する
    # =====================================================
    registered_products = {}

    for product_id in inventory.keys():
        if product_id not in products:
            continue

        product = products[product_id]

        if not product.get("active", True):
            continue

        registered_products[product_id] = product

    vegetable_prices = {}
    vegetable_weights = {}
    target_vegetables = []

    for product in registered_products.values():
        label = product.get("label")

        if not label:
            continue

        vegetable_prices[label] = int(product.get("price", 0) or 0)
        vegetable_weights[label] = int(product.get("weight", 0) or 0)

        if label not in target_vegetables:
            target_vegetables.append(label)

    # =====================================================
    # sensor_1 の設置商品だけを TARGET_VEGETABLE に反映する
    # =====================================================
    sensor_1_target = str(weight_sensor_targets.get("sensor_1", "") or "").strip()

    if sensor_1_target in registered_products:
        target_vegetable = get_label_for_weight_sensor_target(sensor_1_target)
    else:
        target_vegetable = ""

    # =====================================================
    # 各重量センサーの設定も、登録済み在庫にある商品だけを書き出す
    # =====================================================
    config_weight_sensor_targets = {}

    for sensor_id, target_product_id in weight_sensor_targets.items():
        target_product_id = str(target_product_id or "").strip()

        if target_product_id in registered_products:
            config_weight_sensor_targets[sensor_id] = get_label_for_weight_sensor_target(target_product_id)
        else:
            config_weight_sensor_targets[sensor_id] = ""

    new_product_setting = f"""# 商品の単価（円）
# 管理画面から更新されます
VEGETABLE_PRICES = {format_python_dict(vegetable_prices)}


# 対象とする商品ラベル一覧
TARGET_VEGETABLES = {format_python_list(target_vegetables)}


# 現在ロードセルの上に置いている商品のラベル
TARGET_VEGETABLE = "{target_vegetable}"

# 商品の単重量（g）
VEGETABLE_WEIGHTS = {format_python_dict(vegetable_weights)}


# 重量センサーの個数
WEIGHT_SENSOR_COUNT = {weight_sensor_count}

# 各重量センサーの上に置いている商品のラベル
WEIGHT_SENSOR_TARGETS = {format_python_dict(config_weight_sensor_targets)}
"""

    try:
        with open(APP_CONFIG_PATH, "r", encoding="utf-8") as f:
            config_text = f.read()

        start_markers = [
            "# 商品の単価（円）",
            "# 野菜の単価（円）",
        ]

        start_index = -1
        for marker in start_markers:
            index = config_text.find(marker)
            if index != -1:
                start_index = index
                break

        end_marker = "# 硬貨の重量"
        end_index = config_text.find(end_marker)

        if start_index == -1 or end_index == -1:
            print("config.py の商品設定部分を見つけられませんでした。")
            return False

        updated_config_text = (
            config_text[:start_index]
            + new_product_setting
            + "\n"
            + config_text[end_index:]
        )

        with open(APP_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(updated_config_text)

        print("config.py の商品設定を書き換えました:", APP_CONFIG_PATH)
        return True

    except Exception as error:
        print("config.py への商品設定反映に失敗しました:", error)
        return False


# ==========================================
# Getter
# ==========================================

def get_products():
    return products


def get_inventory():
    return inventory


def get_sales_history():
    return sales_history


def get_notification_history():
    return notification_history


def get_ai_history():
    return ai_history


def get_product_price(item_name):
    product_id = get_display_name_by_label(item_name)

    if product_id in products:
        return int(products[product_id].get("price", 0))

    return 0


def get_product_weight(item_name):
    product_id = get_display_name_by_label(item_name)

    if product_id in products:
        return int(products[product_id].get("weight", 0))

    return 0


def get_weight_sensor_settings():
    """
    重量センサー設定を返す。
    古い形式でYOLOラベルが保存されている場合や、削除済みの商品IDが残っている場合に備えて、
    返す直前に現在の在庫に存在する内部商品IDへ正規化する。
    """
    global weight_sensor_targets

    normalized_targets = normalize_weight_sensor_targets(
        weight_sensor_count,
        weight_sensor_targets
    )

    if normalized_targets != weight_sensor_targets:
        weight_sensor_targets = normalized_targets
        save_web_store()

    return {
        "weight_sensor_count": weight_sensor_count,
        "weight_sensor_targets": weight_sensor_targets
    }


# ==========================================
# 重量センサー設定
# ==========================================

def set_weight_sensor_count(count):
    global weight_sensor_count, weight_sensor_targets

    count = int(count)
    if count <= 0:
        return False

    weight_sensor_count = count
    weight_sensor_targets = normalize_weight_sensor_targets(
        weight_sensor_count,
        weight_sensor_targets
    )

    save_web_store()

    config_updated = export_to_config_py()
    if not config_updated:
        print("警告: config.py への重量センサー数反映には失敗しましたが、data_store.json には保存しました。")

    return True


def set_weight_sensor_target(sensor_id, item_name):
    global weight_sensor_targets

    if sensor_id not in weight_sensor_targets:
        print("存在しない重量センサーです:", sensor_id)
        return False

    item_name = str(item_name or "").strip()

    if item_name == "":
        weight_sensor_targets[sensor_id] = ""
        save_web_store()

        config_updated = export_to_config_py()
        if not config_updated:
            print("警告: config.py への重量センサー対象反映には失敗しましたが、data_store.json には保存しました。")

        return True

    # 画面からは内部商品IDが送られる想定だが、
    # 古い画面や手動API呼び出しでYOLOラベル・日本語名が送られても内部商品IDへ変換する。
    product_id = normalize_weight_sensor_target_value(item_name)

    if product_id not in products:
        print("未登録商品のため、重量センサー対象に設定できません:", item_name)
        return False

    if product_id not in inventory:
        print("現在の在庫にない商品のため、重量センサー対象に設定できません:", item_name)
        return False

    # data_store.json では内部商品IDを保存する。
    # これにより、同じ商品名でも価格・単重量が違う在庫を区別できる。
    weight_sensor_targets[sensor_id] = product_id

    save_web_store()

    config_updated = export_to_config_py()
    if not config_updated:
        print("警告: config.py への重量センサー対象反映には失敗しましたが、data_store.json には保存しました。")

    return True


def delete_weight_sensor(sensor_id):
    """
    重量センサーを削除する。

    仕様:
    - sensor_1 は削除しない。
    - sensor_2 以降を削除できる。
    - 削除後は sensor_1, sensor_2, ... のように番号を詰め直す。
    - data_store.json と app/config.py に反映する。
    """
    global weight_sensor_count, weight_sensor_targets

    sensor_id = str(sensor_id or "").strip()

    if sensor_id == "sensor_1":
        print("sensor_1 は削除できません。")
        return False

    if sensor_id not in weight_sensor_targets:
        print("存在しない重量センサーです:", sensor_id)
        return False

    try:
        delete_index = int(sensor_id.replace("sensor_", ""))
    except Exception:
        print("重量センサーIDの形式が正しくありません:", sensor_id)
        return False

    if delete_index <= 1 or delete_index > weight_sensor_count:
        print("削除できない重量センサーです:", sensor_id)
        return False

    remaining_targets = []

    for i in range(1, weight_sensor_count + 1):
        current_sensor_id = f"sensor_{i}"

        if current_sensor_id == sensor_id:
            continue

        remaining_targets.append(weight_sensor_targets.get(current_sensor_id, ""))

    weight_sensor_count = max(1, len(remaining_targets))
    weight_sensor_targets = {
        f"sensor_{i + 1}": remaining_targets[i]
        for i in range(weight_sensor_count)
    }

    save_web_store()

    config_updated = export_to_config_py()
    if not config_updated:
        print("警告: config.py への重量センサー削除反映には失敗しましたが、data_store.json には保存しました。")

    return True


# ==========================================
# 商品登録・削除・在庫更新
# ==========================================

def add_or_update_product(item_name, item_label, price, count, weight):
    """
    商品を新規登録する。

    仕様:
    - 商品名が同じでも、価格または単重量が違えば別在庫として登録する。
    - 商品名・価格・単重量がすべて同じものは、すでに登録済みとして扱う。
    - 内部では商品IDで区別するが、画面の商品名列には日本語名だけ表示する。
    """
    label = normalize_label(item_label)
    display_name = strip_variant_suffix(item_name) or get_japanese_name(label)

    price = int(price)
    count = int(count)
    weight = int(weight)

    product_id = make_product_id(label, price, weight)
    variant_text = format_variant_text(display_name, price, weight)

    # inventoryにあるものだけを「登録済み在庫」とみなす。
    # productsには47クラスの商品候補が入っているため、productsに存在するだけでは重複扱いにしない。
    if product_id in inventory:
        return {
            "status": "exists",
            "message": f"{variant_text} はすでに登録されています。在庫数を変更する場合は、現在の在庫欄から変更してください。",
            "product_name": display_name,
            "product_id": product_id
        }

    same_name_variant_exists = False
    for registered_product_id, registered_product in products.items():
        if registered_product_id not in inventory:
            continue

        if registered_product.get("display_name") == display_name:
            registered_price = int(registered_product.get("price", 0) or 0)
            registered_weight = int(registered_product.get("weight", 0) or 0)
            if registered_price != price or registered_weight != weight:
                same_name_variant_exists = True
                break

    products[product_id] = {
        "display_name": display_name,
        "label": label,
        "price": price,
        "weight": weight,
        "active": True
    }

    inventory[product_id] = count

    save_web_store()

    config_updated = export_to_config_py()
    if not config_updated:
        print("警告: config.py への商品設定反映には失敗しましたが、data_store.json には保存しました。")

    if same_name_variant_exists:
        message = f"{variant_text} を別在庫として登録しました。"
    else:
        message = f"{display_name} を登録しました。"

    return {
        "status": "success",
        "message": message,
        "product_name": display_name,
        "product_id": product_id,
        "is_variant": same_name_variant_exists
    }


def delete_product(item_name):
    if item_name in products:
        deleted_label = products[item_name]["label"]
        del products[item_name]
    else:
        deleted_label = None

    if item_name in inventory:
        del inventory[item_name]

    if deleted_label:
        for sensor_id, target_value in weight_sensor_targets.items():
            if target_value == item_name or target_value == deleted_label:
                weight_sensor_targets[sensor_id] = ""

    save_web_store()

    config_updated = export_to_config_py()
    if not config_updated:
        print("警告: config.py への商品削除反映には失敗しましたが、data_store.json からは削除しました。")

    return True


def update_inventory(item_name, change):
    product_id = get_display_name_by_label(item_name)

    if product_id not in products:
        print("未登録商品のため在庫更新を無視:", item_name)
        return False

    if product_id not in inventory:
        inventory[product_id] = 0

    inventory[product_id] += int(change)

    if inventory[product_id] < 0:
        inventory[product_id] = 0

    save_web_store()
    return True


def set_inventory(item_name, count):
    product_id = item_name if item_name in products else get_display_name_by_label(item_name)

    if product_id not in products:
        print("未登録または削除済み商品のため在庫更新を無視:", item_name)
        return False

    count = int(count)
    if count < 0:
        count = 0

    inventory[product_id] = count
    save_web_store()
    return True


# ==========================================
# 履歴追加
# ==========================================

def add_sales_record(item_name, quantity, amount):
    product_id = get_display_name_by_label(item_name)
    display_name = get_product_display_name(product_id)

    record = {
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "item_name": display_name,
        "quantity": int(quantity),
        "amount": int(amount)
    }

    sales_history.insert(0, record)
    save_web_store()


def add_notification_record(notification_type, item_name, quantity, amount):
    product_id = get_display_name_by_label(item_name)
    display_name = get_product_display_name(product_id)

    record = {
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "type": notification_type,
        "item_name": display_name,
        "quantity": int(quantity),
        "amount": int(amount)
    }

    notification_history.insert(0, record)
    save_web_store()


def add_ai_history_record(item_name, count):
    product_id = get_display_name_by_label(item_name)
    display_name = get_product_display_name(product_id)

    record = {
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "item_name": display_name,
        "count": int(count)
    }

    ai_history.insert(0, record)
    save_web_store()


# ==========================================
# 履歴の一括更新（sessions同期用）
# ==========================================

def replace_histories_from_sessions(new_sales_history, new_notification_history, new_ai_history=None):
    """
    sessionsフォルダ内のsession.jsonを基準に、Web表示用の履歴を作り直す。

    用途:
    - ラズパイ再起動後に、sessionsフォルダの内容とWebの通知・売上履歴を一致させる。
    - data_store.json の履歴が消えた場合でも、sessions/session.json から復元する。

    注意:
    - 在庫数は変更しない。
    - LINE通知は送らない。
    - 売上履歴・通知履歴だけをWeb表示用に同期する。
    """
    global sales_history, notification_history, ai_history

    sales_history = new_sales_history if isinstance(new_sales_history, list) else []
    notification_history = new_notification_history if isinstance(new_notification_history, list) else []

    if new_ai_history is not None:
        ai_history = new_ai_history if isinstance(new_ai_history, list) else []

    save_web_store()
    return True


# 起動時に保存済みの商品・在庫・重量センサー設定を読み込む
load_web_store()
