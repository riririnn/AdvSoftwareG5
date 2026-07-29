from datetime import datetime, timedelta
from pathlib import Path
import json
import importlib.util
import os
import shutil
import uuid


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
RUNTIME_STORE_DIR = PROJECT_ROOT / "runtime" / "web_admin"
RUNTIME_STORE_DIR.mkdir(parents=True, exist_ok=True)

# 商品設定ファイルの場所（<repo>/app/product_settings.py）。
# 価格・単重量・重量センサー割り当ては実機ごとに異なるため、
# config.py ではなく git管理外のこのファイルを読み書きする。
PRODUCT_SETTINGS_PATH = BASE_DIR.parent / "product_settings.py"

# Web管理画面用の保存ファイル。
# 1台のRaspberry Piを1販売所として扱うため、常にこの1ファイルを使う。
DATA_STORE_PATH = RUNTIME_STORE_DIR / "data_store.json"

# ログイン・複数販売所版で使用していた旧保存先。
# 初回起動時にdata_store.jsonが無い場合だけ、既存データを自動移行する。
LEGACY_SHOP_DATA_DIR = RUNTIME_STORE_DIR / "shop_data"


def migrate_legacy_shop_store_if_needed():
    """旧shop_data/*.jsonから単一端末用data_store.jsonへ移行する。

    権限や所有者は変更せず、JSONファイルをコピーするだけにする。
    複数候補がある場合は環境変数LEGACY_SHOP_DATA_FILEで指定できる。
    未指定時は最終更新日時が最も新しいファイルを採用する。
    """
    if DATA_STORE_PATH.exists():
        return None

    override = str(os.getenv("LEGACY_SHOP_DATA_FILE", "") or "").strip()
    source = None

    if override:
        candidate = Path(override).expanduser()
        if candidate.exists() and candidate.is_file():
            source = candidate
        else:
            print("旧販売所データの指定ファイルが見つかりません:", candidate)

    if source is None and LEGACY_SHOP_DATA_DIR.exists():
        candidates = [
            path for path in LEGACY_SHOP_DATA_DIR.glob("*.json")
            if path.is_file()
        ]
        if candidates:
            source = max(candidates, key=lambda path: path.stat().st_mtime)
            if len(candidates) > 1:
                print(
                    "旧販売所データが複数あるため、最終更新が最も新しいファイルを移行します:",
                    source,
                )

    if source is None:
        return None

    try:
        DATA_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, DATA_STORE_PATH)
    except OSError as error:
        print("旧販売所データの移行に失敗しました:", source, error)
        return None

    print("旧販売所データを単一端末用へ移行しました:", source, "->", DATA_STORE_PATH)
    return source


products = {}
inventory = {}

sales_history = []
notification_history = []
ai_history = []

weight_sensor_count = 1
weight_sensor_targets = {
    "sensor_1": ""
}

line_settings = {
    "line_enabled": True,
    "recipients": []
}

# このRaspberry Piに設置されている販売所の表示設定。
# ログインや複数販売所切替には使用せず、管理画面上の表示名としてのみ使用する。
store_settings = {
    "farm_name": "このRaspberry Piの無人販売所"
}

# 通知履歴の自動削除設定。
# ラズパイの容量を圧迫しないよう、一定日数より古い通知履歴は自動で削除する。
# 0以下を指定すると自動削除を無効化する。
DEFAULT_NOTIFICATION_RETENTION_DAYS = 30
history_settings = {
    "notification_retention_days": DEFAULT_NOTIFICATION_RETENTION_DAYS
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

    productsは「商品登録画面の候補マスタ」と「登録済みの価格・重量別商品」を
    兼ねているため、未登録の商品候補も常に残しておく。
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


def merge_with_default_product_master(current_products):
    """
    保存済み商品へ47クラスの商品候補を補完する。

    config.pyは登録済み商品だけへ書き換えられるため、config.pyだけを元に
    productsを作ると、最初に登録したトマトなど1種類しか商品登録画面へ
    表示されなくなる。商品候補マスタを先に作り、保存済みの価格・重量別商品を
    上書き・追加することで、常に全商品を選択できるようにする。
    """
    merged = create_default_products()
    if isinstance(current_products, dict):
        merged.update(current_products)
    return merged


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
    migrate_legacy_shop_store_if_needed()

    global products, inventory, weight_sensor_count, weight_sensor_targets, line_settings, store_settings
    global sales_history, notification_history, ai_history, history_settings

    if not DATA_STORE_PATH.exists():
        load_from_config_py()
        return

    try:
        with open(DATA_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        loaded_products = data.get("products", {})
        loaded_inventory = data.get("inventory", {})

        # 保存済み商品だけでなく、47クラス分の商品候補を常に残す。
        # これにより、一度config.pyがトマトだけへ書き換えられても、
        # 商品登録画面では他の商品を引き続き選択できる。
        products = merge_with_default_product_master(
            normalize_products(loaded_products)
        )

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

        # 旧データにはidが無いため、削除機能のために補完する。
        for record in notification_history:
            if isinstance(record, dict) and not record.get("id"):
                record["id"] = uuid.uuid4().hex

        for record in sales_history:
            if isinstance(record, dict) and not record.get("id"):
                record["id"] = uuid.uuid4().hex

        line_settings = normalize_line_settings(data.get("line_settings", {}))
        store_settings = normalize_store_settings(data.get("store_settings", {}))
        history_settings = normalize_history_settings(data.get("history_settings", {}))

        purge_expired_notification_history()

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
        line_settings = {"line_enabled": True, "recipients": []}
        store_settings = {"farm_name": "このRaspberry Piの無人販売所"}
        history_settings = {"notification_retention_days": DEFAULT_NOTIFICATION_RETENTION_DAYS}
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
        line_settings = {"line_enabled": True, "recipients": []}
        store_settings = {"farm_name": "このRaspberry Piの無人販売所"}
        history_settings = {"notification_retention_days": DEFAULT_NOTIFICATION_RETENTION_DAYS}
        save_web_store()


def save_web_store():
    data = {
        "products": products,
        "inventory": inventory,
        "weight_sensor_count": weight_sensor_count,
        "weight_sensor_targets": weight_sensor_targets,
        "sales_history": sales_history,
        "notification_history": notification_history,
        "ai_history": ai_history,
        "line_settings": line_settings,
        "store_settings": store_settings,
        "history_settings": history_settings
    }

    with open(DATA_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ==========================================
# config.py から初期読み込み
# ==========================================

def load_from_config_py():
    global products, inventory, weight_sensor_count, weight_sensor_targets, line_settings, store_settings

    if not PRODUCT_SETTINGS_PATH.exists():
        print("product_settings.py が見つからないため、デフォルト商品マスタを使います:", PRODUCT_SETTINGS_PATH)
        products = create_default_products()
        inventory = {}
        weight_sensor_count = 1
        weight_sensor_targets = {"sensor_1": ""}
        line_settings = {"line_enabled": True, "recipients": []}
        store_settings = {"farm_name": "このRaspberry Piの無人販売所"}
        save_web_store()
        return

    try:
        spec = importlib.util.spec_from_file_location("app_product_settings", PRODUCT_SETTINGS_PATH)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)

        vegetable_prices = getattr(config_module, "VEGETABLE_PRICES", {})
        vegetable_weights_raw = getattr(config_module, "VEGETABLE_WEIGHTS", {})
        config_sensor_count = getattr(config_module, "WEIGHT_SENSOR_COUNT", 1)
        config_sensor_targets = getattr(config_module, "WEIGHT_SENSOR_TARGETS", {})

        if not isinstance(vegetable_prices, dict):
            vegetable_prices = {}

        # 旧config.pyではVEGETABLE_WEIGHTSが単一数値のことがある。
        if isinstance(vegetable_weights_raw, dict):
            vegetable_weights = vegetable_weights_raw
            scalar_weight = None
        else:
            vegetable_weights = {}
            try:
                scalar_weight = int(vegetable_weights_raw)
            except Exception:
                scalar_weight = None

        # config.pyには登録済み商品だけが書かれていても、商品登録候補は47種類残す。
        products = create_default_products()

        for label, price in vegetable_prices.items():
            label = normalize_label(label)
            display_name = get_japanese_name(label)
            weight = vegetable_weights.get(label)
            if weight is None:
                weight = scalar_weight if scalar_weight is not None else DEFAULT_WEIGHTS.get(label, 100)
            weight = int(weight)
            price = int(price)
            product_id = make_product_id(label, price, weight)

            products[product_id] = {
                "display_name": display_name,
                "label": label,
                "price": price,
                "weight": weight,
                "active": True
            }

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
    Web管理画面で登録された商品情報と重量センサー設定を
    app/product_settings.py に反映する（無ければ新規作成する）。

    重要:
    - products には47種類の商品候補が入っている。
    - そのため products 全体を書き出すと、未登録の商品まで書き出されてしまう。
    - 「現在の在庫 inventory に存在する商品だけ」を書き出す。
    - TARGET_VEGETABLE には sensor_1 に設定している商品のYOLOラベルを書き出す。
    """
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

    # product_settings.py は商品設定専用のファイルなので、丸ごと書き出す。
    new_product_setting = f'''"""
商品設定（価格・単重量・重量センサーの割り当て）。

このファイルはWeb管理画面（app/web_admin）の操作により自動生成される。
実機ごとに内容が異なるため、実機側では以下を1回実行して、
ローカルの書き換えが git の追跡対象にならないようにすること:

    git update-index --skip-worktree app/product_settings.py

手で編集してもよいが、次にWeb管理画面から操作した時点で上書きされる。
"""

# 商品の単価（円）
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
'''

    try:
        with open(PRODUCT_SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.write(new_product_setting)

        print("product_settings.py を書き換えました:", PRODUCT_SETTINGS_PATH)
        return True

    except Exception as error:
        print("product_settings.py への商品設定反映に失敗しました:", error)
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
# 販売所表示設定
# ==========================================

def normalize_store_settings(settings):
    """販売所表示設定を安全な形式へ正規化する。"""
    if not isinstance(settings, dict):
        settings = {}

    farm_name = str(settings.get("farm_name", "") or "").strip()
    if not farm_name:
        farm_name = "このRaspberry Piの無人販売所"

    # ヘッダー表示が崩れないよう、極端に長い値は保存時と同じ上限に揃える。
    return {"farm_name": farm_name[:60]}


def get_store_settings():
    global store_settings
    store_settings = normalize_store_settings(store_settings)
    return dict(store_settings)


def set_farm_name(farm_name):
    """この端末の管理画面に表示する農園名を保存する。"""
    global store_settings

    farm_name = str(farm_name or "").strip()
    if not farm_name:
        return False

    store_settings = {"farm_name": farm_name[:60]}
    save_web_store()
    return True


# ==========================================
# 通知履歴の自動削除設定
# ==========================================

def normalize_history_settings(raw_settings):
    """通知履歴の自動削除設定を安全な形式へ正規化する。"""
    if not isinstance(raw_settings, dict):
        raw_settings = {}

    try:
        retention_days = int(raw_settings.get("notification_retention_days", DEFAULT_NOTIFICATION_RETENTION_DAYS))
    except Exception:
        retention_days = DEFAULT_NOTIFICATION_RETENTION_DAYS

    # 0以下は無効化（自動削除しない）とみなす。
    if retention_days < 0:
        retention_days = 0

    return {"notification_retention_days": retention_days}


def get_history_settings():
    global history_settings
    history_settings = normalize_history_settings(history_settings)
    return dict(history_settings)


def set_notification_retention_days(days):
    """通知履歴の保存日数を設定する。0を指定すると自動削除を無効化する。"""
    global history_settings

    try:
        days = int(days)
    except Exception:
        return False

    if days < 0:
        return False

    history_settings = {"notification_retention_days": days}
    save_web_store()
    purge_expired_notification_history()
    return True


def purge_expired_notification_history():
    """保存日数を過ぎた通知履歴を自動で削除する。

    ラズパイの容量を圧迫し続けないよう、設定日数より古い通知履歴を削除する。
    notification_retention_daysが0の場合は削除しない。
    """
    global notification_history

    settings = normalize_history_settings(history_settings)
    retention_days = settings.get("notification_retention_days", DEFAULT_NOTIFICATION_RETENTION_DAYS)

    if retention_days <= 0:
        return False

    cutoff = datetime.now() - timedelta(days=retention_days)
    before = len(notification_history)
    kept = []

    for record in notification_history:
        if not isinstance(record, dict):
            continue

        try:
            record_time = datetime.strptime(record.get("time", ""), "%Y/%m/%d %H:%M:%S")
        except Exception:
            # 時刻が読み取れない古い形式のデータは、念のため残しておく。
            kept.append(record)
            continue

        if record_time >= cutoff:
            kept.append(record)

    notification_history = kept

    if len(notification_history) != before:
        save_web_store()
        print(f"通知履歴の自動削除: {before - len(notification_history)}件を削除しました（保存期間 {retention_days}日）")
        return True

    return False


# ==========================================
# メール通知設定
# ==========================================

def normalize_line_settings(raw_settings):
    """Webで登録するメール通知設定を正規化する。

    以前のLINE版との互換性のため、関数名と保存キーは line_settings のまま残す。
    ただし、通知先IDは user_id ではなく email を使用する。
    """
    if not isinstance(raw_settings, dict):
        raw_settings = {}

    recipients = raw_settings.get("recipients", [])
    if not isinstance(recipients, list):
        recipients = []

    normalized_recipients = []
    seen_emails = set()

    for recipient in recipients:
        if not isinstance(recipient, dict):
            continue

        email = str(recipient.get("email", "") or "").strip()

        # 旧LINE版のデータが残っている場合、user_idはメールではないため無視する。
        if not email:
            continue

        email_key = email.lower()
        if email_key in seen_emails:
            continue

        seen_emails.add(email_key)
        normalized_recipients.append({
            "name": str(recipient.get("name", "") or "").strip() or "通知先",
            "email": email,
            # 有効/動画/システム通知はUIから設定させず、常に有効にする。
            # 万引き通知を受け取る通知先には、動画も自動的に添付される。
            "enabled": True,
            "purchase_notice": bool(recipient.get("purchase_notice", True)),
            "theft_notice": bool(recipient.get("theft_notice", True)),
            "system_notice": True,
            "video_notice": True,
        })

    return {
        "line_enabled": True,
        "recipients": normalized_recipients
    }


def get_line_settings():
    global line_settings
    line_settings = normalize_line_settings(line_settings)
    return line_settings


def set_line_enabled(enabled):
    global line_settings
    line_settings = normalize_line_settings(line_settings)
    line_settings["line_enabled"] = True
    save_web_store()
    return line_settings


def save_line_recipient(recipient):
    global line_settings
    line_settings = normalize_line_settings(line_settings)

    if not isinstance(recipient, dict):
        return None

    email = str(recipient.get("email", "") or "").strip()
    if not email:
        return None

    new_recipient = {
        "name": str(recipient.get("name", "") or "").strip() or "通知先",
        "email": email,
        # 有効/動画/システム通知はUIから設定させず、常に有効にする。
        # 万引き通知を受け取る通知先には、動画も自動的に添付される。
        "enabled": True,
        "purchase_notice": bool(recipient.get("purchase_notice", True)),
        "theft_notice": bool(recipient.get("theft_notice", True)),
        "system_notice": True,
        "video_notice": True,
    }

    recipients = []
    updated = False
    for current in line_settings.get("recipients", []):
        if str(current.get("email", "") or "").strip().lower() == email.lower():
            recipients.append(new_recipient)
            updated = True
        else:
            recipients.append(current)

    if not updated:
        recipients.append(new_recipient)

    line_settings["recipients"] = recipients
    save_web_store()
    return new_recipient


def delete_line_recipient(email):
    global line_settings
    email = str(email or "").strip()
    line_settings = normalize_line_settings(line_settings)
    before = len(line_settings.get("recipients", []))
    line_settings["recipients"] = [
        recipient for recipient in line_settings.get("recipients", [])
        if str(recipient.get("email", "") or "").strip().lower() != email.lower()
    ]
    save_web_store()
    return len(line_settings.get("recipients", [])) < before

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

    # LCD・重量センサーが1台だけの構成では、最初に登録した商品をsensor_1へ
    # 自動設定する。2件目以降は管理画面で選択中の商品を勝手に変更しない。
    if not str(weight_sensor_targets.get("sensor_1", "") or "").strip():
        weight_sensor_targets["sensor_1"] = product_id

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
        "id": uuid.uuid4().hex,
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "item_name": display_name,
        "quantity": int(quantity),
        "amount": int(amount)
    }

    sales_history.insert(0, record)
    save_web_store()


def delete_sales_record(sales_id):
    """指定したIDの売上履歴を1件だけ削除する。"""
    global sales_history

    sales_id = str(sales_id or "").strip()
    if not sales_id:
        return False

    before = len(sales_history)
    sales_history = [
        record for record in sales_history
        if str(record.get("id", "")) != sales_id
    ]

    if len(sales_history) == before:
        return False

    save_web_store()
    return True


def clear_sales_history():
    """売上履歴を全件削除する。"""
    global sales_history
    sales_history = []
    save_web_store()
    return True


def add_notification_record(notification_type, item_name, quantity, amount):
    product_id = get_display_name_by_label(item_name)
    display_name = get_product_display_name(product_id)

    record = {
        "id": uuid.uuid4().hex,
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "type": notification_type,
        "item_name": display_name,
        "quantity": int(quantity),
        "amount": int(amount)
    }

    notification_history.insert(0, record)
    save_web_store()


def delete_notification_record(notification_id):
    """指定したIDの通知履歴を1件だけ削除する。"""
    global notification_history

    notification_id = str(notification_id or "").strip()
    if not notification_id:
        return False

    before = len(notification_history)
    notification_history = [
        record for record in notification_history
        if str(record.get("id", "")) != notification_id
    ]

    if len(notification_history) == before:
        return False

    save_web_store()
    return True


def clear_notification_history():
    """通知履歴を全件削除する。"""
    global notification_history
    notification_history = []
    save_web_store()
    return True


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
