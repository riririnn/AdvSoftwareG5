from http.server import HTTPServer, BaseHTTPRequestHandler
import json

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
        if self.path == "/update_sales":
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
    print(bind_address := f"Starting minimal web server on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()