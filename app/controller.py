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
import time

from config import (
    SESSION_DIR,
    PERSON_DISAPPEAR_TIME,
    COIN_DETECT_INTERVAL,
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
# ↓↓↓ ダミー実装（後でAI担当のプログラムへ差し替える）
# ==========================================


def detect_person():
    """
    人検知（ダミー）

    Returns
    -------
    bool
        True : 人がいる
        False: 人がいない
    """

    # TODO:
    # AI担当の person YOLO に差し替える

    answer = input("人はいますか？ (y/n): ")

    return answer.lower() == "y"


def detect_coin():
    """
    コイン認識（ダミー）

    Returns
    -------
    list[int]

    例
    ----
    []

    [100]

    [10,10]

    """

    # TODO:
    # AI担当の coin YOLO に差し替える

    answer = input("コイン(空ならEnter): ")

    if answer == "":
        return []

    return [int(answer)]


def detect_vegetables():
    """
    野菜認識（ダミー）

    Returns
    -------
    dict

    {
        "eggplant":4,
        "tomato":2
    }
    """

    # TODO:
    # AI担当の vegetable YOLO に差し替える

    return {
        "eggplant": 4,
        "tomato": 2,
    }


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

    controller = Controller()

    controller.run()


if __name__ == "__main__":
    main()