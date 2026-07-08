from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sys
from pathlib import Path

# ai/ モジュールをインポートできるようにパスを通す
sys.path.insert(0, str(Path(__file__).parent.parent))
from ai.inference import load_model, load_person_model, predict_all

# 起動時にモデルを1度だけロード
_model = load_model()               # 野菜・硬貨（自前学習済み）
_person_model = load_person_model() # 人間（COCO事前学習済み）

# システムの現在の状態を保持するダミーデータ（実際のセンサー値や売上と連動させます）
system_status = {
    "sales_count": 0,
    "total_amount": 0,
    "latest_event": "None"
}

class UnmannedSalesRequestHandler(BaseHTTPRequestHandler):
    # 1. 状態確認用のGETリクエスト処理
    def do_GET(self):
        if self.path == "/status":
            # 成功レスポンスヘッダーの設定（講義準拠）
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            # 現在のステータスをJSON形式で返却
            response_json = json.dumps(system_status).encode("utf-8")
            self.wfile.write(response_json)
        else:
            # パスが見つからない場合の404エラー
            self.send_error(404, "Page Not Found")

    # 2. 外部システムからの制御やデータ更新用のPOSTリクエスト処理
    def do_POST(self):
        if self.path == "/predict":
            self._handle_predict()
        elif self.path == "/update_sales":
            self._handle_update_sales()
        else:
            self.send_error(404, "Page Not Found")

    def _handle_predict(self):
        """
        ラズパイから送られた画像を受け取り、YOLO推論結果をJSONで返す。

        リクエスト: Content-Type: image/jpeg (または image/png)
                    ボディ: 画像のバイナリデータ
        レスポンス: { "image": "frame", "width": 640, "height": 480, "detections": [...] }
        """
        content_length = int(self.headers.get("Content-Length", 0))
        image_bytes = self.rfile.read(content_length)

        if not image_bytes:
            self.send_error(400, "Bad Request: no image data")
            return

        try:
            import numpy as np
            import cv2
            # バイナリデータをOpenCV形式のnumpy配列に変換
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                self.send_error(400, "Bad Request: could not decode image")
                return

            result = predict_all(_model, _person_model, frame)
            response_json = json.dumps(result, ensure_ascii=False).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response_json)

        except Exception as e:
            self.send_error(500, f"Inference error: {e}")

    def _handle_update_sales(self):
        # リクエストボディのサイズを取得（講義準拠の必須処理）
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        try:
            data = json.loads(post_data)
            # 売上データの更新
            system_status["sales_count"] += 1
            system_status["total_amount"] += data.get("price", 0)
            system_status["latest_event"] = "Purchase confirmed"

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"result": "success"}).encode("utf-8"))
        except Exception as e:
            self.send_error(400, f"Bad Request: {str(e)}")

def run_server(port=8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, UnmannedSalesRequestHandler)
    print(f"Starting minimal web server on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()