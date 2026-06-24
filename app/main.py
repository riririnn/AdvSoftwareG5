import time
import web_client
from yolo_inference import run_realtime, InferenceResult


_latest_result: InferenceResult | None = None


def on_inference_result(result: InferenceResult):
    """YOLOの推論結果を受け取るコールバック。"""
    global _latest_result
    _latest_result = result

    # 重量センサー担当（三井）との連携: JSON出力
    # 必要に応じてソケット・キュー・ファイル等で渡す
    # print(result.to_json())


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
            print(f"[Alert] {item}: AI={ai_n} vs 重量={weight_n} — 個数不一致")
            return True
    return False


def main_loop():
    print("Unmanned Sales Monitoring System started...")

    # カメラ推論を別スレッドで常時実行する場合はここで起動
    # run_realtime は show_preview=False でバックグラウンド動作可
    # （今は単純にブロッキングで呼び出す例を示す）

    run_realtime(
        camera_index=0,
        width=640,
        height=480,
        fps=10,
        result_callback=on_inference_result,
        show_preview=True,
    )


if __name__ == "__main__":
    main_loop()