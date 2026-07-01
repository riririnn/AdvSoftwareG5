"""
ラズパイ側メインスクリプト

【役割】
  カメラでフレームを取得 → サーバーに送信して推論 → 結果を受け取り万引き判定
  重いYOLO推論はサーバー側（Ubuntu + GPU）で行い、ラズパイは画像送信に徹する。

【起動方法】
  python app/main.py --server http://<サーバーIP>:8080
"""
import argparse
import cv2
import web_client
from camera_capture import CameraCapture


def check_purchase_or_theft(
    ai_counts: dict,
    weight_counts: dict | None = None,
) -> bool:
    """
    AIの個数カウントと重量センサーの個数を照合する。
    weight_counts が None の場合は AI単体で判定。
    戻り値: 異常（万引き等）が疑われる場合 True
    """
    if weight_counts is None:
        return False

    for item, ai_n in ai_counts.items():
        weight_n = weight_counts.get(item, 0)
        if abs(ai_n - weight_n) >= 2:
            print(f"[Alert] {item}: AI={ai_n} vs 重量={weight_n} — 個��不一致")
            return True
    return False


def main_loop(server_url: str):
    print(f"Unmanned Sales Monitoring System started. Server: {server_url}")
    cam = CameraCapture(camera_index=0, width=640, height=480, fps=10)

    def on_frame(frame):
        # フレームをJPEGバイト列に変換してサーバーへ送信
        _, encoded = cv2.imencode(".jpg", frame)
        result = web_client.send_image_for_prediction(encoded.tobytes(), server_url)

        if result is None:
            return True  # 通信失敗は無視して継続

        detections = result.get("detections", [])
        ai_counts: dict[str, int] = {}
        for det in detections:
            name = det["class_name"]
            ai_counts[name] = ai_counts.get(name, 0) + 1

        if ai_counts:
            print(f"[推論結果] {ai_counts}")

        # 重量センサー担当（三井）からのデータと照合（連携実装後に有効化）
        # weight_counts = get_weight_counts()
        # if check_purchase_or_theft(ai_counts, weight_counts):
        #     web_client.send_notification("万引き疑い検知", server_url)

        return True

    cam.stream(on_frame)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://localhost:8080", help="推論サーバーのURL")
    args = parser.parse_args()
    main_loop(args.server)