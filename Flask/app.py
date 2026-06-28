from flask import Flask, render_template, request, jsonify
from data_store import (
    get_inventory,
    get_products,
    get_sales_history,
    get_notification_history,
    get_ai_history,
    update_inventory,
    set_inventory,
    add_sales_record,
    add_or_update_product,
    delete_product,
    add_notification_record,
    add_ai_history_record,
    get_product_price,
)
from line_notify import send_line_message

app = Flask(__name__)


@app.route("/")
def index():
    """
    管理画面を表示する
    """
    return render_template(
        "index.html",
        inventory=get_inventory(),
        products=get_products(),
        sales_history=get_sales_history(),
        notification_history=get_notification_history(),
        ai_history=get_ai_history(),
    )


@app.route("/api/inventory", methods=["GET"])
def api_get_inventory():
    """
    現在の在庫情報を返すAPI
    """
    return jsonify(get_inventory())


@app.route("/api/products", methods=["GET"])
def api_get_products():
    """
    商品情報を返すAPI
    """
    return jsonify(get_products())


@app.route("/api/sales", methods=["GET"])
def api_get_sales():
    """
    売上履歴を返すAPI
    """
    return jsonify(get_sales_history())


@app.route("/api/notifications", methods=["GET"])
def api_get_notifications():
    """
    通知履歴を返すAPI
    """
    return jsonify(get_notification_history())


@app.route("/api/ai_history", methods=["GET"])
def api_get_ai_history():
    """
    AI認識履歴を返すAPI
    """
    return jsonify(get_ai_history())


@app.route("/api/product", methods=["POST"])
def api_add_or_update_product():
    """
    管理画面から商品情報を登録・更新するAPI
    """
    data = request.json

    item_name = data.get("item_name")
    price = int(data.get("price", 0))
    count = int(data.get("count", 0))

    if not item_name or price < 0 or count < 0:
        return jsonify({
            "status": "error",
            "message": "Invalid product data"
        }), 400

    add_or_update_product(item_name, price, count)

    return jsonify({
        "status": "success",
        "message": "Product added or updated"
    })


@app.route("/api/product/delete", methods=["POST"])
def api_delete_product():
    """
    管理画面から商品を削除するAPI
    """
    data = request.json

    item_name = data.get("item_name")

    if not item_name:
        return jsonify({
            "status": "error",
            "message": "Invalid product name"
        }), 400

    delete_product(item_name)

    return jsonify({
        "status": "success",
        "message": "Product deleted"
    })


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
            "message": "Invalid inventory data"
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
            add_ai_history_record(item_name, count)

    return jsonify({
        "status": "success",
        "message": "AI inventory updated"
    })


@app.route("/api/purchase", methods=["POST"])
def api_purchase():
    """
    正常に購入された場合に呼び出すAPI
    """
    data = request.json

    item_name = data.get("item_name")
    quantity = int(data.get("quantity", 0))

    if not item_name or quantity <= 0:
        return jsonify({
            "status": "error",
            "message": "Invalid purchase data"
        }), 400

    price = get_product_price(item_name)
    amount = price * quantity

    if amount <= 0:
        amount = int(data.get("amount", 0))

    if amount <= 0:
        return jsonify({
            "status": "error",
            "message": "Invalid amount"
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

    add_notification_record(
        notification_type="購入通知",
        item_name=item_name,
        quantity=quantity,
        amount=amount
    )

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
            "message": "Invalid shoplifting data"
        }), 400

    if shortage_amount <= 0:
        price = get_product_price(item_name)
        shortage_amount = price * quantity

    message = (
        "【万引き通知】\n"
        f"商品: {item_name}\n"
        f"個数: {quantity}\n"
        f"不足金額: {shortage_amount}円"
    )

    send_line_message(message)

    add_notification_record(
        notification_type="万引き通知",
        item_name=item_name,
        quantity=quantity,
        amount=shortage_amount
    )

    return jsonify({
        "status": "success",
        "message": "Shoplifting alert sent"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)