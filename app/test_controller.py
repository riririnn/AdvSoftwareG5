"""
システム全体のダミーテスト

カメラ・AI・ラズパイを使用せず、
CSV・録画・Launcherまでの流れを確認する。
"""

import time
from pathlib import Path
from datetime import datetime

from config import SESSION_DIR

from csv_logger import (
    create_session,
    create_session_info,
    finish_session_info,
    log_coin,
    log_vegetable,
    log_weight,
)

from recorder import Recorder
from launcher import launch


def main():

    print("=" * 60)
    print(" Dummy System Test Start ")
    print("=" * 60)

    # -----------------------------
    # セッション作成
    # -----------------------------

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = SESSION_DIR / session_id

    create_session(session_dir)
    create_session_info(session_dir)

    print("[OK] Session Created")

    # -----------------------------
    # 録画開始
    # -----------------------------

    recorder = Recorder()
    recorder.start(session_dir)

    print("[OK] Recording Started")

    # -----------------------------
    # 入店時野菜（ダミー）
    # -----------------------------

    vegetables_before = {
        "eggplant": 5,
        "tomato": 8,
    }

    for name, count in vegetables_before.items():
        log_vegetable(
            session_dir,
            "before",
            name,
            count,
        )

    print("[OK] Before Vegetables Logged")

    # -----------------------------
    # 入店時重量（ダミー）
    # -----------------------------

    weights_before = {
        "vegetable": 1850,
        "coinbox": 900,
    }

    for target, weight in weights_before.items():
        log_weight(
            session_dir,
            "before",
            target,
            weight,
        )

    print("[OK] Before Weight Logged")

    # -----------------------------
    # コイン投入（ダミー）
    # -----------------------------

    coins = [
        100,
        100,
        500,
        10,
    ]

    for coin in coins:

        log_coin(
            session_dir,
            coin,
        )

        print(f"[Coin] {coin}円")

        time.sleep(0.2)

    # -----------------------------
    # 退店待機
    # -----------------------------

    print("[INFO] Customer Left")

    time.sleep(1)

    # -----------------------------
    # 退店後野菜（ダミー）
    # -----------------------------

    vegetables_after = {
        "eggplant": 4,
        "tomato": 8,
    }

    for name, count in vegetables_after.items():

        log_vegetable(
            session_dir,
            "after",
            name,
            count,
        )

    print("[OK] After Vegetables Logged")

    # -----------------------------
    # 退店後重量（ダミー）
    # -----------------------------

    weights_after = {
        "vegetable": 1600,
        "coinbox": 1510,
    }

    for target, weight in weights_after.items():

        log_weight(
            session_dir,
            "after",
            target,
            weight,
        )

    print("[OK] After Weight Logged")

    # -----------------------------
    # 録画終了
    # -----------------------------

    recorder.stop()

    print("[OK] Recording Finished")

    # -----------------------------
    # session.json更新
    # -----------------------------

    finish_session_info(session_dir)

    print("[OK] Session Finished")

    # -----------------------------
    # 万引き判定起動
    # -----------------------------

    launch(session_dir)

    print("[OK] Launcher Called")

    print("=" * 60)
    print(" Dummy Test Completed ")
    print("=" * 60)


if __name__ == "__main__":
    main()