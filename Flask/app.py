from flask import Flask, render_template, request, jsonify
from data_store import (
    get_inventory,
    get_sales_history,
    update_inventory,
    set_inventory,
    add_sales_record,
)
from line_notify import send_line_message

app = Flask(__name__)


@app.route("/")
def index():
    """
    管理画面を表示する
    """
    inventory = get_inventory()
    sales_history = get_sales_history()

    return render_template(
        "index.html",
        inventory=inventory,
        sales_history=sales_history
    )


@app.route("/api/inventory", methods=["GET"])
def api_get_inventory():
    """
    現在の在庫情報を返すAPI
    """
    return jsonify(get_inventory())


@app.route("/api/sales", methods=["GET"])
def api_get_sales():
    """
    売上履歴を返すAPI
    """
    return jsonify(get_sales_history())


@app.route("/api/add_inventory", methods=["POST"])
def api_add_inventory():
    """
    管理画面から在庫を追加するAPI
    """
    data = request.json

    item_name = data.get("item_name")
    quantity = int(data.get("quantity", 0))

    if not item_name or quantity <= 0:
        return jsonify({
            "status": "error",
            "message": "Invalid data"
        }), 400

    update_inventory(item_name, quantity)

    return jsonify({
        "status": "success",
        "message": "Inventory added"
    })


@app.route("/api/ai_inventory", methods=["POST"])
def api_ai_inventory():
    """
    AI画像認識の結果を受け取り、在庫数を更新するAPI
    AI担当から商品名と個数を送ってもらう想定
    """
    data = request.json

    detected_items = data.get("items", [])

    if not detected_items:
        return jsonify({
            "status": "error",
            "message": "No items detected"
        }), 400

    for item in detected_items:
        item_name = item.get("item_name")
        count = int(item.get("count", 0))

        if item_name:
            set_inventory(item_name, count)

    return jsonify({
        "status": "success",
        "message": "AI inventory updated"
    })


@app.route("/api/purchase", methods=["POST"])
def api_purchase():
    """
    正常に購入された場合に呼び出すAPI
    支払い補助システム・野菜認識システムから呼び出す想定
    """
    data = request.json

    item_name = data.get("item_name")
    quantity = int(data.get("quantity", 0))
    amount = int(data.get("amount", 0))

    if not item_name or quantity <= 0 or amount <= 0:
        return jsonify({
            "status": "error",
            "message": "Invalid data"
        }), 400

    update_inventory(item_name, -quantity)
    add_sales_record(item_name, quantity, amount)

    message = (
        "【購入通知】\n"
        f"商品: {item_name}\n"
        f"個数: {quantity}\n"
        f"支払金額: {amount}円"
    )
    send_line_message(message)

    return jsonify({
        "status": "success",
        "message": "Purchase recorded"
    })


@app.route("/api/shoplifting", methods=["POST"])
def api_shoplifting():
    """
    万引き・未払い疑いが発生した場合に呼び出すAPI
    """
    data = request.json

    item_name = data.get("item_name")
    quantity = int(data.get("quantity", 0))
    shortage_amount = int(data.get("shortage_amount", 0))

    if not item_name or quantity <= 0:
        return jsonify({
            "status": "error",
            "message": "Invalid data"
        }), 400

    message = (
        "【万引き通知】\n"
        f"商品: {item_name}\n"
        f"個数: {quantity}\n"
        f"不足金額: {shortage_amount}円"
    )
    send_line_message(message)

    return jsonify({
        "status": "success",
        "message": "Shoplifting alert sent"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)