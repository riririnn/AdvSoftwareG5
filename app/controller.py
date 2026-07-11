"""
controller.py

システム全体を制御するコントローラ

【役割】
・人検知待ち
・セッション開始
・録画開始
・コインログ保存
・人が3秒いなくなったら終了
・野菜・重量ログ保存
・万引き判定プログラム起動
"""

from pathlib import Path
from datetime import datetime
import argparse
import time

import cv2

import web_client
from config import (
    SESSION_DIR,
    PERSON_DISAPPEAR_TIME,
    COIN_DETECT_INTERVAL,
    PREDICT_SERVER_URL,
    PERSON_CONF_THRESHOLD,
    COIN_CONF_THRESHOLD,
    VEGETABLE_CONF_THRESHOLD,
    MONITOR_CAMERA_INDEX,
    COIN_CAMERA_INDEX,
    VEGETABLE_CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
)

from csv_logger import (
    create_session,
    create_session_info,
    finish_session_info,
    log_coin,
    log_vegetable,
    log_weight,
)

from recorder import Recorder
from raspberry_pi import get_weights
from launcher import launch

# ==========================================
# AI認識（GPUサーバーの /predict を利用）
#
# --dummy オプション付きで起動するとキーボード入力の
# ダミー実装に切り替わる（サーバー・カメラなしで制御フローを試す用）
# ==========================================

# --dummy 指定時に True になる（main() で設定）
USE_DUMMY_AI = False

# 硬貨クラス名 → 金額。紙幣(1000yen等)や野菜・personはここに無いので自然に無視される
COIN_VALUES = {
    "1yen": 1,
    "5yen": 5,
    "10yen": 10,
    "50yen": 50,
    "100yen": 100,
    "500yen": 500,
}

# 野菜集計から除外するクラス名（硬貨・紙幣・人間）
NON_VEGETABLE_CLASSES = set(COIN_VALUES) | {"1000yen", "5000yen", "10000yen", "person"}

# カメラは最初に使うときに開き、以後使い回す
_cameras: dict[int, cv2.VideoCapture] = {}

# 前回のコイン検出枚数（増えた分だけを新規投入と判定するための状態）
_last_coin_counts: dict[str, int] = {}


def _read_frame(camera_index: int):
    """指定カメラから1フレーム取得する。失敗時は None。"""
    cap = _cameras.get(camera_index)
    if cap is None:
        cap = cv2.VideoCapture(camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        _cameras[camera_index] = cap

    if not cap.isOpened():
        print(f"[Controller] カメラ {camera_index} を開けません")
        return None

    ret, frame = cap.read()
    return frame if ret else None


def _predict(camera_index: int, conf_threshold: float) -> list[dict]:
    """
    カメラ画像をGPUサーバーに送り、信頼度がしきい値以上の検出だけを返す。
    カメラ・通信の失敗時は空リスト。
    """
    frame = _read_frame(camera_index)
    if frame is None:
        return []

    _, encoded = cv2.imencode(".jpg", frame)
    result = web_client.send_image_for_prediction(
        encoded.tobytes(), PREDICT_SERVER_URL
    )
    if result is None:
        return []

    return [
        det for det in result.get("detections", [])
        if det["confidence"] >= conf_threshold
    ]


def detect_person():
    """
    人検知（監視カメラ + person YOLO）

    Returns
    -------
    bool
        True : 人がいる
        False: 人がいない
    """
    if USE_DUMMY_AI:
        answer = input("人はいますか？ (y/n): ")
        return answer.lower() == "y"

    detections = _predict(MONITOR_CAMERA_INDEX, PERSON_CONF_THRESHOLD)
    return any(det["class_name"] == "person" for det in detections)


def detect_coin():
    """
    コイン認識（コインカメラ + coin YOLO）

    前回検出より枚数が増えた分だけを「新規投入」として返す。
    （同じ硬貨がトレイに置かれたままでも重複カウントしない）

    Returns
    -------
    list[int]

    例
    ----
    []

    [100]

    [10,10]

    """
    global _last_coin_counts

    if USE_DUMMY_AI:
        answer = input("コイン(空ならEnter): ")
        if answer == "":
            return []
        return [int(answer)]

    detections = _predict(COIN_CAMERA_INDEX, COIN_CONF_THRESHOLD)

    counts: dict[str, int] = {}
    for det in detections:
        name = det["class_name"]
        if name in COIN_VALUES:
            counts[name] = counts.get(name, 0) + 1

    # 前回より増えた枚数分だけを新規投入とみなす
    new_coins = []
    for name, n in counts.items():
        added = n - _last_coin_counts.get(name, 0)
        new_coins.extend([COIN_VALUES[name]] * max(added, 0))

    _last_coin_counts = counts
    return new_coins


def detect_vegetables():
    """
    野菜認識（野菜カメラ + vegetable YOLO）

    Returns
    -------
    dict

    {
        "eggplant":4,
        "tomato":2
    }
    """
    if USE_DUMMY_AI:
        return {
            "eggplant": 4,
            "tomato": 2,
        }

    detections = _predict(VEGETABLE_CAMERA_INDEX, VEGETABLE_CONF_THRESHOLD)

    counts: dict[str, int] = {}
    for det in detections:
        name = det["class_name"]
        if name in NON_VEGETABLE_CLASSES:
            continue
        counts[name] = counts.get(name, 0) + 1
    return counts


def reset_coin_tracking():
    """コインの新規投入判定をリセットする（セッション開始時に呼ぶ）。"""
    global _last_coin_counts
    _last_coin_counts = {}


# ==========================================
# Controller
# ==========================================


class Controller:

    def __init__(self):

        self.recorder = Recorder()

    def run(self):

        print("===================================")
        print("Unmanned Sales System")
        print("Waiting for customer...")
        print("===================================")

        while True:

            # -----------------------------
            # 人待ち
            # -----------------------------

            if not detect_person():
                time.sleep(1)
                continue

            print("\nCustomer detected.")

            # コインの新規投入判定をセッションごとにリセット
            reset_coin_tracking()

            # -----------------------------
            # セッション作成
            # -----------------------------

            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

            session_dir = SESSION_DIR / session_id

            create_session(session_dir)
            create_session_info(session_dir)

            # -----------------------------
            # 入店時の野菜数保存
            # -----------------------------

            before_vegetables = detect_vegetables()

            for name, count in before_vegetables.items():
                log_vegetable(
                    session_dir,
                    "before",
                    name,
                    count,
                )

            # -----------------------------
            # 入店時重量取得
            # -----------------------------

            weights = get_weights()

            log_weight(
                session_dir,                    
                "before",
                "vegetable",
                weights["vegetable"],
            )

            log_weight(
                session_dir,
                "before",
                "coinbox",
                weights["coinbox"],
            )

            # -----------------------------
            # 録画開始
            # -----------------------------

            self.recorder.start(session_dir)

            print("Session started.")
            print()
            # -----------------------------
            # セッション中
            # -----------------------------

            disappeared_time = None

            while True:

                #
                # 本来はここで CameraCapture から
                # フレームを取得して Recorder.write(frame)
                # を呼び出す想定
                #
                # （現在はCamera担当実装待ち）
                #

                # -------------------------
                # コイン認識
                # -------------------------

                coins = detect_coin()

                for coin in coins:
                    log_coin(session_dir, coin)

                # -------------------------
                # 人検知
                # -------------------------

                if detect_person():

                    disappeared_time = None

                else:

                    if disappeared_time is None:
                        disappeared_time = time.time()

                    elif (
                        time.time() - disappeared_time
                        >= PERSON_DISAPPEAR_TIME
                    ):
                        print("Customer left.")
                        break

                time.sleep(COIN_DETECT_INTERVAL)

            # -----------------------------
            # 録画終了
            # -----------------------------

            self.recorder.stop()

            # -----------------------------
            # 退店後の野菜数保存
            # -----------------------------

            after_vegetables = detect_vegetables()

            for name, count in after_vegetables.items():

                log_vegetable(
                    session_dir,
                    "after",
                    name,
                    count,
                )

            # -----------------------------
            # 退店後重量取得
            # -----------------------------

            weights = get_weights()

            log_weight(
                session_dir,
                "after",
                "vegetable",
                weights["vegetable"],
            )

            log_weight(
                session_dir,
                "after",
                "coinbox",
                weights["coinbox"],
            )

            # -----------------------------
            # session.json更新
            # -----------------------------

            finish_session_info(session_dir)

            # -----------------------------
            # 万引き判定プログラム起動
            # -----------------------------

            launch(session_dir)

            print()
            print("Session finished.")
            print("Waiting for next customer...")
            print()


def main():

    global USE_DUMMY_AI

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dummy",
        action="store_true",
        help="AI認識を使わずキーボード入力のダミーで動かす（制御フロー単体テスト用）",
    )
    args = parser.parse_args()

    USE_DUMMY_AI = args.dummy
    if USE_DUMMY_AI:
        print("[Controller] ダミーモードで起動します（AI認識・カメラ不使用）")
    else:
        print(f"[Controller] AIモードで起動します（推論サーバー: {PREDICT_SERVER_URL}）")

    controller = Controller()

    controller.run()


if __name__ == "__main__":
    main()