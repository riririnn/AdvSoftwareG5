"""
ラズパイ模擬クライアント（Windows / Ubuntu ホストで実行）

実機ラズパイの代わりに、画像ファイルまたはPCのWebカメラから
フレームをサーバーに送り続けて推論結果を受け取る。

【依存ライブラリ（Windows側にインストール）】
  pip install opencv-python

【使い方】
  # 画像ファイルを1枚送る
  python app/simulate_raspi.py --image unattended_sales_place_images/selfsellingstation.jpg

  # 画像ファイルをループ送信（カメラの代わりに繰り返し送る）
  python app/simulate_raspi.py --image unattended_sales_place_images/selfsellingstation.jpg --loop

  # PCのWebカメラからリアルタイム送信
  python app/simulate_raspi.py --camera 0

【サーバーURLの指定】
  python app/simulate_raspi.py --image xxx.jpg --server http://<UbuntuのIP>:8080
"""

import argparse
import json
import time
import urllib.request

import cv2


SERVER_URL = "http://localhost:8080"


def send_frame(frame, server_url: str) -> dict | None:
    """1フレームをJPEGエンコードしてサーバーに送り、推論結果を返す。"""
    _, encoded = cv2.imencode(".jpg", frame)
    req = urllib.request.Request(
        f"{server_url}/predict",
        data=encoded.tobytes(),
        headers={"Content-Type": "image/jpeg"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[SimRPi] 送信失敗: {e}")
        return None


def print_result(result: dict):
    detections = result.get("detections", [])
    if not detections:
        print("[SimRPi] 検出なし")
        return
    for det in detections:
        print(
            f"  {det['class_name']}  conf={det['confidence']:.2%}"
            f"  bbox=({det['bbox']['x1']},{det['bbox']['y1']})"
            f"-({det['bbox']['x2']},{det['bbox']['y2']})"
        )


def run_image(image_path: str, server_url: str, loop: bool):
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"[SimRPi] 画像を読み込めません: {image_path}")
        return

    print(f"[SimRPi] 画像モード: {image_path} → {server_url}/predict")
    while True:
        result = send_frame(frame, server_url)
        if result:
            print_result(result)
        if not loop:
            break
        time.sleep(1.0)


def run_camera(camera_index: int, server_url: str, fps: int):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[SimRPi] カメラ {camera_index} を開けません")
        return

    print(f"[SimRPi] カメラモード: camera={camera_index} → {server_url}/predict  (qで終了)")
    interval = 1.0 / fps
    try:
        while True:
            start = time.monotonic()
            ret, frame = cap.read()
            if not ret:
                break

            cv2.imshow("SimRPi - Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            result = send_frame(frame, server_url)
            if result:
                print_result(result)

            elapsed = time.monotonic() - start
            wait = interval - elapsed
            if wait > 0:
                time.sleep(wait)
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ラズパイ模擬クライアント")
    parser.add_argument("--server", default=SERVER_URL, help="サーバーURL")
    parser.add_argument("--image", help="送信する画像ファイルのパス")
    parser.add_argument("--loop", action="store_true", help="画像を繰り返し送信する")
    parser.add_argument("--camera", type=int, default=-1, help="Webカメラのインデックス（0など）")
    parser.add_argument("--fps", type=int, default=5, help="カメラ送信のフレームレート")
    args = parser.parse_args()

    if args.image:
        run_image(args.image, args.server, args.loop)
    elif args.camera >= 0:
        run_camera(args.camera, args.server, args.fps)
    else:
        parser.print_help()
