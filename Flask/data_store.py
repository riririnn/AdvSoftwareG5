from datetime import datetime
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SHARED_DIR = BASE_DIR / "shared"
PRODUCT_CONFIG_PATH = SHARED_DIR / "product_config.json"


# 初期状態では、Web上で設定された商品がない状態にする
# 商品登録・更新画面から追加すると、この辞書に商品情報が登録される
products = {}


# 初期表示では、現在の在庫を空にする
# 商品を登録・更新すると、この辞書に在庫情報が追加される
inventory = {}


sales_history = []
notification_history = []
ai_history = []


def export_product_config():
    """
    Web管理画面で登録された商品情報を、app側のconfig.pyから参照できるJSONとして書き出す

    出力内容:
    - vegetable_prices: 商品ごとの価格
    - vegetable_weights: 商品ごとの単重量
    - target_vegetables: 判定対象の商品名一覧
    """
    SHARED_DIR.mkdir(exist_ok=True)

    product_config = {
        "vegetable_prices": {},
        "vegetable_weights": {},
        "target_vegetables": []
    }

    for item_name, product in products.items():
        if not product.get("active", True):
            continue

        product_config["vegetable_prices"][item_name] = product["price"]
        product_config["vegetable_weights"][item_name] = product["weight"]
        product_config["target_vegetables"].append(item_name)

    with open(PRODUCT_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(product_config, f, ensure_ascii=False, indent=4)

    print("商品設定を書き出しました:", PRODUCT_CONFIG_PATH)
    return product_config


# 起動時にも空の設定ファイルを作成する
export_product_config()


def get_products():
    """
    商品情報を取得する
    """
    return products


def get_inventory():
    """
    現在の在庫情報を取得する
    """
    return inventory


def get_sales_history():
    """
    売上履歴を取得する
    """
    return sales_history


def get_notification_history():
    """
    通知履歴を取得する
    """
    return notification_history


def get_ai_history():
    """
    AI認識履歴を取得する
    """
    return ai_history


def get_product_price(item_name):
    """
    商品価格を取得する
    """
    if item_name in products:
        return products[item_name]["price"]

    return 0


def get_product_weight(item_name):
    """
    商品の単重量を取得する
    """
    if item_name in products:
        return products[item_name]["weight"]

    return 0


def add_or_update_product(item_name, price, count, weight):
    """
    商品情報を登録・更新する

    商品名・価格・在庫数・単重量をまとめて登録または更新する
    登録・更新後、app側で参照する product_config.json も更新する
    """
    products[item_name] = {
        "price": price,
        "weight": weight,
        "active": True
    }

    inventory[item_name] = count

    export_product_config()


def delete_product(item_name):
    """
    商品情報と在庫情報から商品を削除する
    削除後、app側で参照する product_config.json も更新する
    """
    if item_name in products:
        del products[item_name]

    if item_name in inventory:
        del inventory[item_name]

    export_product_config()

    return True


def update_inventory(item_name, change):
    """
    在庫数を増減する

    購入時などに在庫を減らすために使用する
    """
    if item_name not in products:
        print("未登録商品のため在庫更新を無視:", item_name)
        return False

    if item_name not in inventory:
        inventory[item_name] = 0

    inventory[item_name] += change

    if inventory[item_name] < 0:
        inventory[item_name] = 0

    return True


def set_inventory(item_name, count):
    """
    AI認識結果などをもとに在庫数を上書きする

    削除済みの商品や未登録の商品は再追加しない
    """
    if item_name not in products:
        print("未登録または削除済み商品のためAI在庫更新を無視:", item_name)
        return False

    if count < 0:
        count = 0

    inventory[item_name] = count

    return True


def add_sales_record(item_name, quantity, amount):
    """
    売上履歴を追加する
    """
    record = {
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "item_name": item_name,
        "quantity": quantity,
        "amount": amount
    }

    sales_history.insert(0, record)


def add_notification_record(notification_type, item_name, quantity, amount):
    """
    通知履歴を追加する
    """
    record = {
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "type": notification_type,
        "item_name": item_name,
        "quantity": quantity,
        "amount": amount
    }

    notification_history.insert(0, record)


def add_ai_history_record(item_name, count):
    """
    AI認識履歴を追加する
    """
    record = {
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "item_name": item_name,
        "count": count
    }

    ai_history.insert(0, record)
