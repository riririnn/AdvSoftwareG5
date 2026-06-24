from datetime import datetime


# 初期在庫
inventory = {
    "Tomato": 10,
    "Cucumber": 8,
    "Eggplant": 6,
    "Bell Pepper": 5
}


# 売上履歴
sales_history = []


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


def update_inventory(item_name, change):
    """
    在庫数を増減する
    change がプラスなら追加、マイナスなら減少
    """
    if item_name not in inventory:
        inventory[item_name] = 0

    inventory[item_name] += change

    if inventory[item_name] < 0:
        inventory[item_name] = 0


def set_inventory(item_name, count):
    """
    AI認識結果などをもとに在庫数を上書きする
    """
    if count < 0:
        count = 0

    inventory[item_name] = count


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