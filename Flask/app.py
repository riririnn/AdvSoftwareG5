from flask import Flask, render_template, request, jsonify
import json
from pathlib import Path
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


BASE_DIR = Path(__file__).resolve().parent

# app側のcontroller.pyやtheft_checker.pyが出力するsession.jsonを探す場所
# 環境によって sessions フォルダの位置が異なる可能性があるため、複数候補を確認する
SESSION_DIR_CANDIDATES = [
    BASE_DIR / "app" / "sessions",
    BASE_DIR / "sessions",
]

# 同じsession.jsonを何度も履歴に反映しないための記録
processed_session_ids = set()


def find_latest_session_json():
    """
    sessionsフォルダ内から最新のsession.jsonを探す

    想定パス:
    - app/sessions/<session_id>/session.json
    - sessions/<session_id>/session.json

    念のため、sessions.jsonというファイル名も探索対象に含める
    """
    session_files = []

    for sessions_dir in SESSION_DIR_CANDIDATES:
        if not sessions_dir.exists():
            continue

        session_files.extend(sessions_dir.glob("*/session.json"))
        session_files.extend(sessions_dir.glob("*/sessions.json"))

    if not session_files:
        return None

    return max(session_files, key=lambda path: path.stat().st_mtime)


def load_latest_session():
    """
    最新のsession.jsonを読み込む
    """
    latest_session_path = find_latest_session_json()

    if latest_session_path is None:
        return None, None

    with open(latest_session_path, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    return session_data, latest_session_path


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


@app.route("/api/session/latest", methods=["GET"])
def api_get_latest_session():
    """
    app側で作成された最新のsession.jsonを読み込んで返すAPI

    Web管理画面から、購入結果や万引き判定結果を確認するために使用する
    """
    try:
        session_data, session_path = load_latest_session()
    except json.JSONDecodeError:
        return jsonify({
            "status": "error",
            "message": "session.jsonの形式が正しくありません。"
        }), 500
    except OSError as error:
        return jsonify({
            "status": "error",
            "message": f"session.jsonの読み込みに失敗しました: {error}"
        }), 500

    if session_data is None:
        return jsonify({
            "status": "not_found",
            "message": "session.jsonが見つかりません。",
            "searched_paths": [str(path) for path in SESSION_DIR_CANDIDATES]
        }), 404

    return jsonify({
        "status": "success",
        "session_file": str(session_path),
        "session": session_data
    })


@app.route("/api/session/import", methods=["POST"])
def api_import_latest_session():
    """
    最新のsession.jsonを読み込み、
    判定結果を売上履歴・通知履歴・LINE通知に反映するAPI
    """
    try:
        session_data, session_path = load_latest_session()
    except json.JSONDecodeError:
        return jsonify({
            "status": "error",
            "message": "session.jsonの形式が正しくありません。"
        }), 500
    except OSError as error:
        return jsonify({
            "status": "error",
            "message": f"session.jsonの読み込みに失敗しました: {error}"
        }), 500

    if session_data is None:
        return jsonify({
            "status": "not_found",
            "message": "session.jsonが見つかりません。"
        }), 404

    session_id = session_data.get("session_id")

    if not session_id:
        return jsonify({
            "status": "error",
            "message": "session_idがありません。"
        }), 400

    if session_id in processed_session_ids:
        return jsonify({
            "status": "skipped",
            "message": "このsession.jsonはすでに履歴へ反映済みです。",
            "session_id": session_id
        })

    theft_check = session_data.get("theft_check", {})
    judgement = theft_check.get("judgement")

    purchase_amount = int(theft_check.get("purchase_amount") or 0)
    paid_amount = int(theft_check.get("paid_amount") or 0)
    shortage = int(theft_check.get("shortage") or 0)

    decreased_items = theft_check.get("decreased_vegetables_weight", {})

    if not decreased_items:
        return jsonify({
            "status": "error",
            "message": "減少した商品情報がありません。"
        }), 400

    line_results = []

    for item_name, quantity in decreased_items.items():
        quantity = int(quantity)

        if judgement in ["normal", "nomal"]:
            add_sales_record(
                item_name=item_name,
                quantity=quantity,
                amount=purchase_amount
            )

            add_notification_record(
                notification_type="購入通知",
                item_name=item_name,
                quantity=quantity,
                amount=paid_amount
            )

            message = (
                "【購入通知】\n"
                f"セッションID: {session_id}\n"
                f"商品: {item_name}\n"
                f"個数: {quantity}\n"
                f"購入金額: {purchase_amount}円\n"
                f"支払金額: {paid_amount}円"
            )

            line_result = send_line_message(message)
            line_results.append(line_result)

        elif judgement == "theft":
            add_notification_record(
                notification_type="万引き通知",
                item_name=item_name,
                quantity=quantity,
                amount=shortage
            )

            message = (
                "【万引き通知】\n"
                f"セッションID: {session_id}\n"
                f"商品: {item_name}\n"
                f"個数: {quantity}\n"
                f"購入金額: {purchase_amount}円\n"
                f"支払金額: {paid_amount}円\n"
                f"不足金額: {shortage}円"
            )

            line_result = send_line_message(message)
            line_results.append(line_result)

        elif judgement == "error":
            error_message = theft_check.get("error_message", "判定エラーが発生しました。")

            add_notification_record(
                notification_type="判定エラー",
                item_name=item_name,
                quantity=quantity,
                amount=0
            )

            message = (
                "【判定エラー】\n"
                f"セッションID: {session_id}\n"
                f"商品: {item_name}\n"
                f"個数: {quantity}\n"
                f"内容: {error_message}"
            )

            line_result = send_line_message(message)
            line_results.append(line_result)

        else:
            return jsonify({
                "status": "error",
                "message": f"不明な判定結果です: {judgement}"
            }), 400

    processed_session_ids.add(session_id)

    return jsonify({
        "status": "success",
        "message": "session.jsonの内容を履歴に反映し、LINE通知を送信しました。",
        "session_id": session_id,
        "judgement": judgement,
        "line_results": line_results,
        "session_file": str(session_path)
    })


@app.route("/api/product", methods=["POST"])
def api_add_or_update_product():
    """
    管理画面から商品情報を登録・更新するAPI

    商品名・価格・在庫数・単重量をまとめて登録または更新する
    """
    data = request.json

    item_name = data.get("item_name")
    price = int(data.get("price", 0))
    count = int(data.get("count", 0))
    weight = int(data.get("weight", 0))

    if not item_name or price < 0 or count < 0 or weight <= 0:
        return jsonify({
            "status": "error",
            "message": "Invalid product data"
        }), 400

    add_or_update_product(item_name, price, count, weight)

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

    print("削除対象:", item_name)

    delete_product(item_name)

    print("削除後の在庫:", get_inventory())

    return jsonify({
        "status": "success",
        "message": "Product deleted",
        "inventory": get_inventory()
    })


@app.route("/api/ai_inventory", methods=["POST"])
def api_ai_inventory():
    """
    AI画像認識の結果を受け取り、在庫数を更新するAPI

    削除済みの商品や未登録の商品は再登録せず、無視する
    """
    data = request.json

    detected_items = data.get("items", [])

    if not detected_items:
        return jsonify({
            "status": "error",
            "message": "No items detected"
        }), 400

    updated_items = []
    ignored_items = []

    for item in detected_items:
        item_name = item.get("item_name")
        count = int(item.get("count", 0))

        if item_name:
            updated = set_inventory(item_name, count)

            if updated:
                add_ai_history_record(item_name, count)
                updated_items.append({
                    "item_name": item_name,
                    "count": count
                })
            else:
                ignored_items.append(item_name)

    print("AI在庫更新:", updated_items)
    print("AI更新で無視した商品:", ignored_items)
    print("AI更新後の在庫:", get_inventory())

    return jsonify({
        "status": "success",
        "message": "AI inventory updated",
        "updated_items": updated_items,
        "ignored_items": ignored_items,
        "inventory": get_inventory()
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

    updated = update_inventory(item_name, -quantity)

    if not updated:
        return jsonify({
            "status": "error",
            "message": "商品が未登録です。"
        }), 400

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