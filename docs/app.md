📂 推奨するコード配置（`/app` ディレクトリ内）
プロジェクトの `/app` ディレクトリ内に、サーバー機能と通知用クライアント機能をモジュール化して配置します。

```
/app
├── main.py          # 全体を統括するメインスクリプト（センサー・カメラ監視ループ）
├── web_server.py    # Python標準ライブラリによる軽量Webサーバー（状態・売上確認用）
└── web_client.py    # urllibを使った外部へのデータ・画像送信クライアント
```

🛠 1. サーバー側の実装 (`web_server.py`)
外部のスマートフォンやPCから、現在の売上状況やシステムの稼働ステータスを確認するためのGET/POST要求を処理するサーバーです。講義に準拠し、スレッドや余計な依存関係を排除したクリーンな構成にします。

```python
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
```

📡 2. クライアント側の実装 (`web_client.py`)
カメラ画像でお金や野菜を認識した際、あるいは万引き（購入通知なしの重量変化など）を検知した際に、管理者のシステムや外部API（LINE Notifyなど）に `urllib` を使ってデータをPOST送信するモジュールです。

```python
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
```

🔄 3. メイン制御ループへの統合イメージ (`main.py`)
実際の運用時は、センサーの数値を監視するメインループの中で、条件を満たしたときに上記のクライアント関数を呼び出します。

```python
import time
import web_client

def main_loop():
	print("Unmanned Sales Monitoring System started...")
	while True:
		# ここに磁気・重量センサーの読み取りロジックを配置
		# 例: 重量センサーが変化し、カメラが購入を認識した場合
		purchase_detected = False # センサーやAIの判定結果を入れる
        
		if purchase_detected:
			print("Purchase event detected. Sending data via urllib...")
			web_client.send_notification("Item purchased successfully.")
            
		time.sleep(1)

if __name__ == "__main__":
	main_loop()
```

📊 Python標準Webシステムのライフサイクル・シミュレーター
以下は、Python標準の `BaseHTTPRequestHandler` が、送信されたリクエストのヘッダーやボディ（`Content-Length`）をどのように解析し、内部ロジックへマッピングしていくかの処理フローを視覚的に体験できるインタラクティブ・シミュレーターです。各イベントを発生させて、サーバー内部の挙動を確認してみてください。

