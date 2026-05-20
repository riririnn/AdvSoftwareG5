import urllib.request
import urllib.parse
import json

def send_notification(message, target_url="http://localhost:8080/update_sales"):
    """
    urllibを使用した最小限のHTTP POST送信（講義要件に完全準拠）
    """
    # 送信するデータを辞書型で定義
    payload = {
        "event": "alert",
        "message": message,
        "price": 100  # 例として100円の商品の購入イベント
    }
    
    # データをJSON文字列に変換し、バイトデータにエンコード
    data = json.dumps(payload).encode("utf-8")
    
    # リクエストオブジェクトの作成
    req = urllib.request.Request(
        target_url, 
        data=data, 
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        # 通信の実行
        with urllib.request.urlopen(req) as response:
            response_body = response.read().decode("utf-8")
            print(f"Server Response: {response_body}")
            return True
    except Exception as e:
        print(f"HTTP Request Failed: {e}")
        return False

if __name__ == "__main__":
    # テスト送信
    send_notification("Test notification from Raspberry Pi client")