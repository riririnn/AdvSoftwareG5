"""
後処理起動モジュール

【ダミー実装】

セッション終了後に万引き判定プログラムを起動するためのモジュール。

現在は後任のプログラムが未実装のため、
ダミーとしてメッセージを表示するのみ。

将来的には subprocess などを用いて
万引き判定プログラムを起動する。
"""

from pathlib import Path
# import subprocess   # 将来使用予定


def launch(session_dir: Path):
    """
    万引き判定プログラムを起動する。

    Parameters
    ----------
    session_dir : Path
        セッションフォルダへのパス
    """

    print()
    print("=" * 50)
    print(" Theft Check Launcher")
    print("=" * 50)
    print(f"Session Directory : {session_dir}")
    print("Launching theft checker...")

    # ==================================================
    # ダミー実装
    #
    # 将来的には以下のように後任のプログラムを起動する。
    #
    # subprocess.run([
    #     "python",
    #     "theft_checker.py",
    #     str(session_dir)
    # ])
    #
    # session_dir 内の
    #   - coin.csv
    #   - vegetable.csv
    #   - weight.csv
    #   - session.json
    # を後任プログラムへ渡して万引き判定を行う。
    # ==================================================

    print("Dummy launcher executed.")
    print("Theft checker is not implemented yet.")

    print("=" * 50)
    print()