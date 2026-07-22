from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
from urllib.parse import quote
import json
import os
import shutil
import threading
import time
from datetime import datetime

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from .data_store import (
        get_inventory,
        get_products,
        get_sales_history,
        get_notification_history,
        update_inventory,
        set_inventory,
        add_sales_record,
        add_or_update_product,
        delete_product,
        add_notification_record,
        get_product_price,
        get_display_name_by_label,
        get_product_display_name,
        get_weight_sensor_settings,
        set_weight_sensor_count,
        set_weight_sensor_target,
        delete_weight_sensor,
        replace_histories_from_sessions,
    )
    from .line_notify import send_line_message, send_line_video_message
except ImportError:
    from data_store import (
        get_inventory,
        get_products,
        get_sales_history,
        get_notification_history,
        update_inventory,
        set_inventory,
        add_sales_record,
        add_or_update_product,
        delete_product,
        add_notification_record,
        get_product_price,
        get_display_name_by_label,
        get_product_display_name,
        get_weight_sensor_settings,
        set_weight_sensor_count,
        set_weight_sensor_target,
        delete_weight_sensor,
        replace_histories_from_sessions,
    )
    from line_notify import send_line_message, send_line_video_message

try:
    from .hardware_display import (
        setup_hardware,
        show_paid,
        show_unpaid,
        show_current_product_from_config,
        stop_buzzer,
    )
except ImportError:
    try:
        from hardware_display import (
            setup_hardware,
            show_paid,
            show_unpaid,
            show_current_product_from_config,
            stop_buzzer,
        )
    except Exception as error:
        print("hardware_display.py を読み込めませんでした:", error)

        def setup_hardware():
            pass

        def show_paid():
            pass

        def show_unpaid(shortage=0):
            pass

        def show_current_product_from_config():
            pass

        def stop_buzzer():
            pass


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
# app/web_admin/web_app.py から見たプロジェクトルート
PROJECT_ROOT = BASE_DIR.parent.parent
# controller.py の保存先（<リポジトリルート>/sessions）と同じ場所を監視する。
# 別の場所を見る場合は環境変数 SESSIONS_DIR で上書きする。
SESSIONS_DIR = Path(os.getenv("SESSIONS_DIR", str(PROJECT_ROOT / "sessions")))
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
LINE_VIDEO_PREVIEW_URL = os.getenv("LINE_VIDEO_PREVIEW_URL", "").strip()

WATCH_INTERVAL_SEC = float(os.getenv("WATCH_INTERVAL_SEC", "5"))
FILE_STABLE_SEC = float(os.getenv("FILE_STABLE_SEC", "2"))
RUNTIME_DIR = PROJECT_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_SESSIONS_FILE = RUNTIME_DIR / "processed_sessions.json"

# sessionフォルダに必ず入れるデフォルト動画
# 例: /home/pi/mujin_web/monitor.mp4 を置くと、各sessionフォルダにコピーして使う
TEST_VIDEO_SOURCE = Path(os.getenv("TEST_VIDEO_SOURCE", str(RUNTIME_DIR / "monitor.mp4")))
TEST_PREVIEW_SOURCE = Path(os.getenv("TEST_PREVIEW_SOURCE", str(RUNTIME_DIR / "monitor_preview.jpg")))


# =========================================================
# 処理済みsession管理
# =========================================================

def load_processed_session_ids():
    if not PROCESSED_SESSIONS_FILE.exists():
        return set()

    try:
        with open(PROCESSED_SESSIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(data)

        if isinstance(data, dict):
            return set(data.keys())

    except Exception:
        pass

    return set()


def save_processed_session_ids():
    data = {session_id: True for session_id in sorted(processed_session_ids)}
    tmp_path = PROCESSED_SESSIONS_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    tmp_path.replace(PROCESSED_SESSIONS_FILE)


processed_session_ids = load_processed_session_ids()


# =========================================================
# session.json検索・読込
# =========================================================

def is_file_stable(path):
    path = Path(path)

    if not path.exists():
        return False

    elapsed = time.time() - path.stat().st_mtime
    return elapsed >= FILE_STABLE_SEC


def find_all_session_jsons():
    if not SESSIONS_DIR.exists():
        return []

    session_files = list(SESSIONS_DIR.glob("*/session.json"))
    return sorted(session_files, key=lambda path: path.stat().st_mtime)


def find_latest_session_json():
    session_files = find_all_session_jsons()

    if not session_files:
        return None

    return session_files[-1]


def load_session_json(session_path):
    with open(session_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_session_id(session_path, session_data):
    return str(session_data.get("session_id") or session_path.parent.name)


def get_theft_check(session_data):
    theft_check = session_data.get("theft_check", {})
    return theft_check if isinstance(theft_check, dict) else {}


def normalize_judgement(judgement):
    judgement = str(judgement or "").strip().lower()

    if judgement in ["normal", "nomal"]:
        return "normal"

    if judgement == "theft":
        return "theft"

    if judgement == "error":
        return "error"

    return judgement


def get_decreased_items(theft_check):
    decreased_items = theft_check.get("decreased_vegetables_weight", {})
    return decreased_items if isinstance(decreased_items, dict) else {}


# =========================================================
# Web画面からのテスト用session生成
# =========================================================

def make_current_session_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_unique_session_dir():
    base_session_id = make_current_session_id()
    session_id = base_session_id
    session_dir = SESSIONS_DIR / session_id

    index = 1
    while session_dir.exists():
        session_id = f"{base_session_id}_{index:02d}"
        session_dir = SESSIONS_DIR / session_id
        index += 1

    session_dir.mkdir(parents=True, exist_ok=False)
    return session_id, session_dir


def select_item_from_current_inventory():
    """
    管理画面の「現在の在庫」にある商品から、テスト用に1商品を選ぶ。
    在庫数が1以上の商品だけを使う。
    """
    inventory = get_inventory()
    products = get_products()

    for item_name, count in inventory.items():
        try:
            count = int(count)
        except Exception:
            count = 0

        if count <= 0:
            continue

        product = products.get(item_name)
        if not product:
            continue

        item_label = product.get("label", item_name)
        price = int(product.get("price", 0) or 0)
        quantity = 1

        return {
            "item_name": item_name,
            "item_label": item_label,
            "display_name": product.get("display_name", item_name),
            "quantity": quantity,
            "price": price,
            "stock": count
        }

    return None


def find_reusable_test_video():
    """
    万引きテスト用に再利用する動画を探す。
    優先順位:
    1. 環境変数 TEST_VIDEO_SOURCE、または BASE_DIR/monitor.mp4
    2. 既存sessions内のmonitor.mp4
    3. 既存sessions内の任意のmp4
    """
    if TEST_VIDEO_SOURCE.exists():
        return TEST_VIDEO_SOURCE

    monitor_videos = sorted(
        SESSIONS_DIR.glob("*/monitor.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    if monitor_videos:
        return monitor_videos[0]

    mp4_videos = sorted(
        SESSIONS_DIR.rglob("*.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    if mp4_videos:
        return mp4_videos[0]

    return None



def find_reusable_test_preview():
    """
    万引きテスト用に再利用するプレビュー画像を探す。
    優先順位:
    1. 環境変数 TEST_PREVIEW_SOURCE、または BASE_DIR/monitor_preview.jpg
    2. 既存sessions内のmonitor_preview.jpg
    3. 既存sessions内のpreview画像
    """
    if TEST_PREVIEW_SOURCE.exists():
        return TEST_PREVIEW_SOURCE

    preview_images = sorted(
        SESSIONS_DIR.glob("*/monitor_preview.jpg"),
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    if preview_images:
        return preview_images[0]

    image_candidates = []

    for pattern in ["*preview*.jpg", "*preview*.jpeg", "*preview*.png"]:
        image_candidates.extend(SESSIONS_DIR.rglob(pattern))

    image_candidates = sorted(
        image_candidates,
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    if image_candidates:
        return image_candidates[0]

    return None




def ensure_default_video_in_session(session_dir):
    """
    各sessionフォルダに monitor.mp4 が必ず存在するようにする。

    優先順位:
    1. sessionフォルダ内にすでに monitor.mp4 があればそのまま使う
    2. BASE_DIR/monitor.mp4 または TEST_VIDEO_SOURCE をコピーする
    3. 既存sessions内の動画を再利用する

    preview画像も、あればコピーし、なければmonitor.mp4から自動生成する。
    """
    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    destination_video = session_dir / "monitor.mp4"
    destination_preview = session_dir / "monitor_preview.jpg"

    if destination_video.exists():
        preview_path = destination_preview if destination_preview.exists() else create_video_preview_image(destination_video)
        return {
            "video_path": destination_video,
            "preview_path": preview_path,
            "copied": False
        }

    source_video = find_reusable_test_video()

    if source_video is None or not source_video.exists():
        print("session用のデフォルト動画が見つかりません。", TEST_VIDEO_SOURCE)
        return {
            "video_path": None,
            "preview_path": None,
            "copied": False
        }

    try:
        if source_video.resolve() != destination_video.resolve():
            shutil.copy2(source_video, destination_video)
            print("sessionフォルダにmonitor.mp4をコピーしました:", destination_video)

        source_preview = find_reusable_test_preview()

        if source_preview is not None and source_preview.exists():
            if source_preview.resolve() != destination_preview.resolve():
                shutil.copy2(source_preview, destination_preview)
                preview_path = destination_preview
            else:
                preview_path = source_preview
        else:
            preview_path = create_video_preview_image(destination_video)

        return {
            "video_path": destination_video,
            "preview_path": preview_path,
            "copied": True
        }

    except Exception as error:
        print("sessionフォルダへの動画コピー中にエラーが発生しました:", error)
        return {
            "video_path": None,
            "preview_path": None,
            "copied": False
        }


def create_generated_session_json(judgement="normal"):
    """
    管理画面からデモ用のsessionフォルダを生成する。

    生成例:
    sessions/
    └─ 20260703_132045/
       ├─ session.json
       ├─ monitor.mp4          # normal/theft どちらでも必ずコピー
       └─ monitor_preview.jpg  # あればコピー、なければ自動生成

    session.json の形式は、制御側プログラムが出力する形式に合わせる。
    """
    judgement = normalize_judgement(judgement)

    if judgement not in ["normal", "theft"]:
        judgement = "normal"

    selected_item = select_item_from_current_inventory()

    if selected_item is None:
        return {
            "status": "error",
            "message": "現在の在庫に1個以上の商品がありません。先に在庫数を登録してください。"
        }

    session_id, session_dir = build_unique_session_dir()

    item_name = selected_item["item_name"]
    quantity = selected_item["quantity"]
    price = selected_item["price"]

    purchase_amount = price * quantity
    if purchase_amount <= 0:
        purchase_amount = 100 * quantity

    if judgement == "normal":
        paid_amount = purchase_amount
        shortage = 0
    else:
        paid_amount = 0
        shortage = purchase_amount

    session_data = {
        "session_id": session_id,
        "status": "finished",
        "theft_check": {
            "judgement": judgement,
            "purchase_amount": purchase_amount,
            "paid_amount": paid_amount,
            "shortage": shortage,
            "decreased_vegetables_weight": {
                item_name: quantity
            }
        }
    }

    session_path = session_dir / "session.json"

    with open(session_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    video_result = ensure_default_video_in_session(session_dir)
    copied_video = video_result.get("video_path")
    copied_preview = video_result.get("preview_path")

    return {
        "status": "success",
        "message": "デモ用sessionフォルダを生成しました。",
        "session_id": session_id,
        "session_dir": str(session_dir),
        "session_file": str(session_path),
        "copied_video": str(copied_video) if copied_video else "",
        "copied_preview": str(copied_preview) if copied_preview else "",
        "selected_item": selected_item,
        "session_data": session_data
    }

# =========================================================
# 動画通知用処理
# =========================================================

def find_session_video(session_dir):
    session_dir = Path(session_dir)

    preferred_video = session_dir / "monitor.mp4"
    if preferred_video.exists():
        return preferred_video

    nested_preferred_videos = list(session_dir.rglob("monitor.mp4"))
    if nested_preferred_videos:
        return nested_preferred_videos[0]

    for pattern in ["*.mp4", "*.mov", "*.avi", "*.mkv"]:
        videos = list(session_dir.rglob(pattern))
        if videos:
            return videos[0]

    return None


def create_video_preview_image(video_path):
    if cv2 is None:
        print("opencv-python がインストールされていません。")
        print("ラズパイでは sudo apt install -y python3-opencv を実行してください。")
        return None

    video_path = Path(video_path)
    preview_path = video_path.with_name(video_path.stem + "_preview.jpg")

    if preview_path.exists():
        return preview_path

    try:
        capture = cv2.VideoCapture(str(video_path))

        if not capture.isOpened():
            print("動画ファイルを開けませんでした:", video_path)
            return None

        success, frame = capture.read()
        capture.release()

        if not success or frame is None:
            print("動画の1フレーム目を取得できませんでした:", video_path)
            return None

        saved = cv2.imwrite(str(preview_path), frame)

        if saved and preview_path.exists():
            print("動画プレビュー画像を作成しました:", preview_path)
            return preview_path

    except Exception as error:
        print("動画プレビュー画像の作成中にエラーが発生しました:", error)

    return None


def build_session_file_url(file_path):
    if not PUBLIC_BASE_URL:
        return ""

    file_path = Path(file_path)

    try:
        relative_path = file_path.relative_to(SESSIONS_DIR)
    except ValueError:
        return ""

    relative_url = "/".join(quote(part) for part in relative_path.parts)
    url = f"{PUBLIC_BASE_URL}/session_files/{relative_url}"

    if (
        "ngrok-free" in PUBLIC_BASE_URL
        or "ngrok-free.dev" in PUBLIC_BASE_URL
        or "ngrok.app" in PUBLIC_BASE_URL
    ):
        url += "?ngrok-skip-browser-warning=true"

    return url


# =========================================================
# 履歴・在庫反映
# =========================================================

def build_items_text(decreased_items):
    lines = []

    for item_label, quantity in decreased_items.items():
        item_name = get_display_name_by_label(item_label)

        try:
            quantity = int(quantity)
        except Exception:
            quantity = 0

        display_name = get_product_display_name(item_name)
        lines.append(f"{display_name}: {quantity}個")

    return "\n".join(lines) if lines else "商品情報なし"


def update_inventory_from_session(decreased_items):
    updated_items = []
    ignored_items = []

    for item_label, quantity in decreased_items.items():
        item_name = get_display_name_by_label(item_label)

        try:
            quantity = int(quantity)
        except Exception:
            quantity = 0

        if quantity <= 0:
            ignored_items.append(get_product_display_name(item_name))
            continue

        updated = update_inventory(item_name, -quantity)

        if updated:
            updated_items.append({
                "item_name": get_product_display_name(item_name),
                "quantity": quantity
            })
        else:
            ignored_items.append(get_product_display_name(item_name))

    return {
        "updated_items": updated_items,
        "ignored_items": ignored_items
    }


def add_sales_records_from_session(decreased_items, purchase_amount):
    item_count = len(decreased_items)

    for item_label, quantity in decreased_items.items():
        item_name = get_display_name_by_label(item_label)

        try:
            quantity = int(quantity)
        except Exception:
            quantity = 0

        price = get_product_price(item_name)
        amount = price * quantity

        if amount <= 0 and item_count == 1:
            amount = purchase_amount

        add_sales_record(
            item_name=item_name,
            quantity=quantity,
            amount=amount
        )


def add_notification_records_from_session(notification_type, decreased_items, amount):
    for item_label, quantity in decreased_items.items():
        item_name = get_display_name_by_label(item_label)

        try:
            quantity = int(quantity)
        except Exception:
            quantity = 0

        add_notification_record(
            notification_type=notification_type,
            item_name=item_name,
            quantity=quantity,
            amount=amount
        )


# =========================================================
# session.json処理本体
# =========================================================

def process_session_path(session_path, ignore_stability=False, force_reprocess=False):
    session_path = Path(session_path)

    if not session_path.exists():
        return {
            "status": "not_found",
            "message": "session.jsonが見つかりません。",
            "session_file": str(session_path)
        }

    if not ignore_stability and not is_file_stable(session_path):
        return {
            "status": "waiting",
            "message": "session.jsonが書き込み直後のため、次回監視で処理します。",
            "session_file": str(session_path)
        }

    try:
        session_data = load_session_json(session_path)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "session.jsonの形式が正しくありません。",
            "session_file": str(session_path)
        }
    except OSError as error:
        return {
            "status": "error",
            "message": f"session.jsonの読み込みに失敗しました: {error}",
            "session_file": str(session_path)
        }

    session_id = get_session_id(session_path, session_data)

    # 取込対象のsessionフォルダには、判定結果に関係なくmonitor.mp4を必ず用意する
    ensure_default_video_in_session(session_path.parent)

    if session_id in processed_session_ids and not force_reprocess:
        return {
            "status": "skipped",
            "message": "このsession.jsonはすでに反映済みです。",
            "session_id": session_id
        }

    status = session_data.get("status", "")
    theft_check = get_theft_check(session_data)

    if status != "finished":
        return {
            "status": "waiting",
            "message": "sessionがfinishedではないため、まだ処理しません。",
            "session_id": session_id,
            "current_status": status
        }

    if not theft_check:
        return {
            "status": "waiting",
            "message": "theft_checkがまだ存在しないため、まだ処理しません。",
            "session_id": session_id
        }

    judgement = normalize_judgement(theft_check.get("judgement", ""))

    purchase_amount = int(theft_check.get("purchase_amount") or 0)
    paid_amount = int(theft_check.get("paid_amount") or 0)
    shortage = int(theft_check.get("shortage") or 0)
    decreased_items = get_decreased_items(theft_check)

    if not decreased_items:
        return {
            "status": "error",
            "message": "減少した商品情報がありません。",
            "session_id": session_id
        }

    items_text = build_items_text(decreased_items)
    line_results = []

    if judgement == "normal":
        # 支払い完了判定の瞬間に緑LEDを点灯し、ブザーを停止する
        show_paid()

        inventory_result = update_inventory_from_session(decreased_items)

        add_sales_records_from_session(
            decreased_items=decreased_items,
            purchase_amount=purchase_amount
        )

        add_notification_records_from_session(
            notification_type="購入通知",
            decreased_items=decreased_items,
            amount=paid_amount
        )

        message = (
            "【購入通知】\n"
            f"セッションID: {session_id}\n"
            f"商品:\n{items_text}\n"
            f"購入金額: {purchase_amount}円\n"
            f"支払金額: {paid_amount}円"
        )

        line_results.append(send_line_message(message))

    elif judgement == "theft":
        # 万引き・未払い判定の瞬間に赤LEDを点灯し、確認ボタンが押されるまでブザーを鳴らす
        show_unpaid(shortage)

        inventory_result = update_inventory_from_session(decreased_items)

        add_notification_records_from_session(
            notification_type="万引き通知",
            decreased_items=decreased_items,
            amount=shortage
        )

        message = (
            "【万引き通知】\n"
            f"セッションID: {session_id}\n"
            f"商品:\n{items_text}\n"
            f"購入金額: {purchase_amount}円\n"
            f"支払金額: {paid_amount}円\n"
            f"不足金額: {shortage}円"
        )

        video_path = find_session_video(session_path.parent)

        if video_path:
            if not ignore_stability and not is_file_stable(video_path):
                return {
                    "status": "waiting",
                    "message": "monitor.mp4が書き込み直後のため、次回監視で処理します。",
                    "session_id": session_id,
                    "video_file": str(video_path)
                }

            video_url = build_session_file_url(video_path)
            preview_path = create_video_preview_image(video_path)

            if preview_path:
                preview_image_url = build_session_file_url(preview_path)
            else:
                preview_image_url = LINE_VIDEO_PREVIEW_URL

            print("LINE送信用 video_url:", video_url)
            print("LINE送信用 preview_image_url:", preview_image_url)

            if video_url and preview_image_url:
                line_result = send_line_video_message(
                    text_message=message,
                    video_url=video_url,
                    preview_image_url=preview_image_url
                )
            else:
                fallback_message = (
                    message
                    + "\n\n動画ファイルはありますが、LINE送信用URLまたはプレビュー画像URLが作成できませんでした。"
                    + f"\n動画パス: {video_path}"
                    + "\nPUBLIC_BASE_URL と LINE_VIDEO_PREVIEW_URL を確認してください。"
                )
                line_result = send_line_message(fallback_message)

        else:
            fallback_message = (
                message
                + "\n\nこのセッションフォルダに動画ファイルが見つかりませんでした。"
            )
            line_result = send_line_message(fallback_message)

        line_results.append(line_result)

    elif judgement == "error":
        inventory_result = {
            "updated_items": [],
            "ignored_items": []
        }

        error_message = theft_check.get("error_message", "判定エラーが発生しました。")

        add_notification_records_from_session(
            notification_type="判定エラー",
            decreased_items=decreased_items,
            amount=0
        )

        message = (
            "【判定エラー】\n"
            f"セッションID: {session_id}\n"
            f"商品:\n{items_text}\n"
            f"内容: {error_message}"
        )

        line_results.append(send_line_message(message))

    else:
        return {
            "status": "error",
            "message": f"不明な判定結果です: {judgement}",
            "session_id": session_id
        }

    processed_session_ids.add(session_id)
    save_processed_session_ids()

    return {
        "status": "success",
        "message": "session.jsonの内容を履歴に反映し、LINE通知を送信しました。",
        "session_id": session_id,
        "judgement": judgement,
        "session_file": str(session_path),
        "inventory_result": inventory_result,
        "line_results": line_results
    }


def scan_sessions_once():
    results = []

    for session_path in find_all_session_jsons():
        results.append(process_session_path(session_path))

    return results


# =========================================================
# sessionsフォルダとWeb履歴の同期
# =========================================================

def parse_session_time_for_history(session_id, session_path):
    """
    session_id からWeb履歴用の時刻文字列を作る。
    例: 20260703_181909 -> 2026/07/03 18:19:09
    形式が合わない場合は session.json の更新時刻を使う。
    """
    session_id = str(session_id or "")

    try:
        dt = datetime.strptime(session_id[:15], "%Y%m%d_%H%M%S")
        return dt.strftime("%Y/%m/%d %H:%M:%S")
    except Exception:
        pass

    try:
        dt = datetime.fromtimestamp(Path(session_path).stat().st_mtime)
        return dt.strftime("%Y/%m/%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def build_history_records_from_session(session_path):
    """
    1つのsession.jsonから、Web表示用の売上履歴・通知履歴を作る。

    ここでは在庫変更やLINE送信は行わない。
    sessionsフォルダの中身とWeb履歴を一致させるためだけの処理。
    """
    session_path = Path(session_path)

    try:
        session_data = load_session_json(session_path)
    except Exception as error:
        print("履歴同期用session.json読込失敗:", session_path, error)
        return [], []

    if session_data.get("status") != "finished":
        return [], []

    theft_check = get_theft_check(session_data)
    if not theft_check:
        return [], []

    judgement = normalize_judgement(theft_check.get("judgement", ""))

    # UIから判定エラーは消しているため、Web履歴同期でも除外する
    if judgement not in ["normal", "theft"]:
        return [], []

    decreased_items = get_decreased_items(theft_check)
    if not decreased_items:
        return [], []

    session_id = get_session_id(session_path, session_data)
    record_time = parse_session_time_for_history(session_id, session_path)

    try:
        purchase_amount = int(theft_check.get("purchase_amount") or 0)
    except Exception:
        purchase_amount = 0

    try:
        paid_amount = int(theft_check.get("paid_amount") or 0)
    except Exception:
        paid_amount = 0

    try:
        shortage = int(theft_check.get("shortage") or 0)
    except Exception:
        shortage = 0

    sales_records = []
    notification_records = []
    item_count = len(decreased_items)

    for item_label, quantity in decreased_items.items():
        product_id = get_display_name_by_label(item_label)
        display_name = get_product_display_name(product_id)

        try:
            quantity = int(quantity)
        except Exception:
            quantity = 0

        if quantity <= 0:
            continue

        price = get_product_price(product_id)
        amount = price * quantity

        if amount <= 0 and item_count == 1:
            amount = purchase_amount

        base_record = {
            "time": record_time,
            "session_id": session_id,
            "item_name": display_name,
            "quantity": quantity,
        }

        if judgement == "normal":
            sales_record = dict(base_record)
            sales_record["amount"] = amount
            sales_records.append(sales_record)

            notification_record = dict(base_record)
            notification_record["type"] = "購入通知"
            notification_record["amount"] = paid_amount if item_count == 1 else amount
            notification_records.append(notification_record)

        elif judgement == "theft":
            notification_record = dict(base_record)
            notification_record["type"] = "万引き通知"
            notification_record["amount"] = shortage
            notification_records.append(notification_record)

    return sales_records, notification_records


def sync_web_histories_from_sessions():
    """
    sessionsフォルダ内のsession.jsonを基準に、Webの売上履歴・通知履歴を作り直す。

    これにより、ラズパイの電源断後やdata_store.jsonの履歴消失後でも、
    sessionsフォルダに残っているsession.jsonとWeb表示内容を一致させる。
    """
    all_sales_records = []
    all_notification_records = []

    for session_path in find_all_session_jsons():
        sales_records, notification_records = build_history_records_from_session(session_path)
        all_sales_records.extend(sales_records)
        all_notification_records.extend(notification_records)

    all_sales_records.sort(key=lambda record: record.get("time", ""), reverse=True)
    all_notification_records.sort(key=lambda record: record.get("time", ""), reverse=True)

    replace_histories_from_sessions(
        new_sales_history=all_sales_records,
        new_notification_history=all_notification_records
    )

    print(
        "sessionsフォルダからWeb履歴を同期しました:",
        f"売上 {len(all_sales_records)}件,",
        f"通知 {len(all_notification_records)}件"
    )

    return {
        "status": "success",
        "sales_count": len(all_sales_records),
        "notification_count": len(all_notification_records)
    }


def watch_sessions_loop():
    print("sessions自動監視を開始しました:", SESSIONS_DIR)

    while True:
        try:
            results = scan_sessions_once()

            for result in results:
                if result.get("status") == "success":
                    print("session自動取込完了:", result.get("session_id"), result.get("judgement"))
                elif result.get("status") == "error":
                    print("session自動取込エラー:", result)

        except Exception as error:
            print("sessions監視中にエラーが発生しました:", error)

        time.sleep(WATCH_INTERVAL_SEC)


# =========================================================
# Flask画面
# =========================================================

@app.route("/")
def index():
    return render_template(
        "index.html",
        inventory=get_inventory(),
        products=get_products(),
        sales_history=get_sales_history(),
        notification_history=get_notification_history(),
    )


@app.route("/session_files/<path:filename>", methods=["GET"])
def serve_session_file(filename):
    return send_from_directory(SESSIONS_DIR, filename)


# =========================================================
# 管理画面用API
# =========================================================

@app.route("/api/inventory", methods=["GET"])
def api_get_inventory():
    return jsonify(get_inventory())


@app.route("/api/inventory/update", methods=["POST"])
def api_update_inventory_count():
    """
    現在の在庫に表示されている商品の在庫数だけを変更するAPI。
    商品名・価格・単重量は変更せず、在庫数だけを上書きする。
    """
    data = request.json or {}

    item_name = data.get("item_name")

    try:
        count = int(data.get("count", 0))
    except Exception:
        return jsonify({
            "status": "error",
            "message": "在庫数は数値で入力してください。"
        }), 400

    if not item_name:
        return jsonify({
            "status": "error",
            "message": "商品名が指定されていません。"
        }), 400

    if count < 0:
        return jsonify({
            "status": "error",
            "message": "在庫数は0以上で入力してください。"
        }), 400

    result = set_inventory(item_name, count)

    if not result:
        return jsonify({
            "status": "error",
            "message": "在庫数の変更に失敗しました。"
        }), 400

    return jsonify({
        "status": "success",
        "message": "在庫数を変更しました。",
        "inventory": get_inventory()
    })


@app.route("/api/products", methods=["GET"])
def api_get_products():
    return jsonify(get_products())


@app.route("/api/sales", methods=["GET"])
def api_get_sales():
    return jsonify(get_sales_history())


@app.route("/api/notifications", methods=["GET"])
def api_get_notifications():
    return jsonify(get_notification_history())


@app.route("/api/product", methods=["POST"])
def api_add_or_update_product():
    data = request.json or {}

    item_name = data.get("item_name")
    item_label = data.get("item_label")

    try:
        price = int(data.get("price", 0))
        count = int(data.get("count", 0))
        weight = int(data.get("weight", 0))
    except Exception:
        return jsonify({
            "status": "error",
            "message": "価格・在庫数・単重量は数値で入力してください。"
        }), 400

    if not item_name or not item_label or price < 0 or count < 0 or weight <= 0:
        return jsonify({
            "status": "error",
            "message": "商品名・価格・在庫数・単重量を正しく入力してください。"
        }), 400

    result = add_or_update_product(
        item_name=item_name,
        item_label=item_label,
        price=price,
        count=count,
        weight=weight
    )

    if isinstance(result, dict):
        if result.get("status") == "success":
            show_current_product_from_config()
            return jsonify(result)

        if result.get("status") == "exists":
            return jsonify(result), 409

        return jsonify({
            "status": "error",
            "message": result.get("message", "商品登録に失敗しました。")
        }), 400

    if not result:
        return jsonify({
            "status": "error",
            "message": "商品登録に失敗しました。"
        }), 400

    return jsonify({
        "status": "success",
        "message": "商品を登録しました。"
    })


@app.route("/api/product/delete", methods=["POST"])
def api_delete_product():
    data = request.json or {}
    item_name = data.get("item_name")

    if not item_name:
        return jsonify({
            "status": "error",
            "message": "商品名が指定されていません。"
        }), 400

    delete_product(item_name)
    show_current_product_from_config()

    return jsonify({
        "status": "success",
        "message": "商品を削除しました。",
        "inventory": get_inventory()
    })


@app.route("/api/weight_sensors", methods=["GET"])
def api_get_weight_sensors():
    return jsonify({
        "status": "success",
        "settings": get_weight_sensor_settings()
    })


@app.route("/api/weight_sensors/count", methods=["POST"])
def api_set_weight_sensor_count():
    data = request.json or {}
    try:
        count = int(data.get("count", 0))
    except Exception:
        return jsonify({"status": "error", "message": "重量センサーの個数は数値で入力してください。"}), 400

    if count <= 0:
        return jsonify({
            "status": "error",
            "message": "重量センサーの個数を正しく入力してください。"
        }), 400

    result = set_weight_sensor_count(count)

    if not result:
        return jsonify({
            "status": "error",
            "message": "重量センサー数の設定に失敗しました。"
        }), 400

    return jsonify({
        "status": "success",
        "message": "重量センサー数を設定しました。",
        "settings": get_weight_sensor_settings()
    })


@app.route("/api/weight_sensors/target", methods=["POST"])
def api_set_weight_sensor_target():
    data = request.json or {}

    sensor_id = data.get("sensor_id")
    item_name = data.get("item_name", "")

    if not sensor_id:
        return jsonify({
            "status": "error",
            "message": "重量センサーIDが指定されていません。"
        }), 400

    result = set_weight_sensor_target(sensor_id, item_name)

    if not result:
        return jsonify({
            "status": "error",
            "message": "重量センサー対象の設定に失敗しました。"
        }), 400

    show_current_product_from_config()

    return jsonify({
        "status": "success",
        "message": "重量センサー対象を設定しました。",
        "settings": get_weight_sensor_settings()
    })


@app.route("/api/weight_sensors/delete", methods=["POST"])
def api_delete_weight_sensor():
    data = request.json or {}
    sensor_id = data.get("sensor_id")

    if not sensor_id:
        return jsonify({
            "status": "error",
            "message": "重量センサーIDが指定されていません。"
        }), 400

    if sensor_id == "sensor_1":
        return jsonify({
            "status": "error",
            "message": "sensor_1 は削除できません。"
        }), 400

    result = delete_weight_sensor(sensor_id)

    if not result:
        return jsonify({
            "status": "error",
            "message": "重量センサーの削除に失敗しました。"
        }), 400

    return jsonify({
        "status": "success",
        "message": f"{sensor_id} を削除しました。",
        "settings": get_weight_sensor_settings()
    })


@app.route("/api/hardware/stop-buzzer", methods=["POST"])
def api_stop_buzzer():
    """Web画面側から確認済みとしてブザーを止める補助API。物理確認ボタンが基本だが、デモ時にも使える。"""
    stop_buzzer()
    return jsonify({
        "status": "success",
        "message": "ブザーを停止しました。"
    })


# =========================================================
# session取込API
# =========================================================

@app.route("/api/session/generate-and-import", methods=["POST"])
def api_generate_and_import_session():
    data = request.json or {}
    judgement = data.get("judgement", "normal")

    generated = create_generated_session_json(judgement=judgement)

    if generated.get("status") != "success":
        return jsonify(generated), 400

    result = process_session_path(
        generated["session_file"],
        ignore_stability=True,
        force_reprocess=False
    )

    status_code = 200
    if result.get("status") == "error":
        status_code = 400

    return jsonify({
        "status": result.get("status", "success"),
        "message": result.get("message", "テスト用session.jsonを生成して取り込みました。"),
        "generated": generated,
        "import_result": result
    }), status_code


@app.route("/api/session/import/latest", methods=["POST"])
def api_import_latest_session():
    session_path = find_latest_session_json()

    if session_path is None:
        return jsonify({
            "status": "not_found",
            "message": "sessionsフォルダ内にsession.jsonが見つかりません。"
        }), 404

    result = process_session_path(
        session_path,
        ignore_stability=True,
        force_reprocess=False
    )

    status_code = 200

    if result.get("status") == "not_found":
        status_code = 404
    elif result.get("status") == "error":
        status_code = 400

    return jsonify(result), status_code


@app.route("/api/session/import/all", methods=["POST"])
def api_import_all_sessions():
    results = scan_sessions_once()

    success_count = sum(
        1 for result in results
        if result.get("status") == "success"
    )

    return jsonify({
        "status": "success",
        "message": f"{success_count}件のsession.jsonを処理しました。",
        "results": results
    })


@app.route("/api/session/sync-histories", methods=["POST"])
def api_sync_web_histories_from_sessions():
    result = sync_web_histories_from_sessions()

    return jsonify({
        "status": "success",
        "message": "sessionsフォルダの内容からWebの売上履歴・通知履歴を同期しました。",
        "result": result
    })


@app.route("/api/session/processed/clear", methods=["POST"])
def api_clear_processed_sessions():
    processed_session_ids.clear()
    save_processed_session_ids()

    return jsonify({
        "status": "success",
        "message": "処理済みsession記録を削除しました。"
    })


if __name__ == "__main__":
    # LED・ブザー・確認ボタン・LCD電子値札を初期化する
    setup_hardware()
    show_current_product_from_config()

    # 起動時に sessions フォルダの内容を基準にWeb履歴を復元する
    sync_web_histories_from_sessions()

    watcher_thread = threading.Thread(
        target=watch_sessions_loop,
        daemon=True
    )
    watcher_thread.start()

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
