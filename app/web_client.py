"""
ラズパイ側クライアント（urllibのみ使用、講義要件準拠）

【役割】
  - カメラ画像をサーバーの POST /predict に送り、推論結果JSONを受け取る
  - 購入イベント・アラートをサーバーの POST /update_sales に通知する
"""
import urllib.request
import json

SERVER_URL = "http://localhost:8080"


def send_image_for_prediction(image_bytes: bytes, server_url: str = SERVER_URL) -> dict | None:
    """
    カメラで撮影した画像をサーバーに送り、YOLO推論結果を受け取る。

    Args:
        image_bytes: cv2.imencode() 等で得た画像のバイナリデータ
        server_url:  サーバーのベースURL（例: "http://192.168.1.10:8080"）

    Returns:
        推論結果の dict、または失敗時 None
        例: {"image": "frame", "width": 640, "height": 480, "detections": [...]}
    """
    req = urllib.request.Request(
        f"{server_url}/predict",
        data=image_bytes,
        headers={"Content-Type": "image/jpeg"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[Client] 推論リクエスト失敗: {e}")
        return None


def send_notification(message: str, server_url: str = SERVER_URL) -> bool:
    """
    urllibを使用した最小限のHTTP POST送信（講義要件に完全準拠）
    購入イベントやアラートをサーバーに通知する。
    """
    payload = {
        "event": "alert",
        "message": message,
        "price": 100,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{server_url}/update_sales",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            response_body = response.read().decode("utf-8")
            print(f"[Client] Server Response: {response_body}")
            return True
    except Exception as e:
        print(f"[Client] 通知送信失敗: {e}")
        return False


if __name__ == "__main__":
    # テスト送信
    send_notification("Test notification from Raspberry Pi client")