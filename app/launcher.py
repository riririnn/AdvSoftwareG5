"""
launcher.py

後処理起動モジュール

セッション終了後に万引き判定プログラム（theft_checker.py）を起動する。
"""

from pathlib import Path
import subprocess


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
    print("=" * 50)
    print()

    subprocess.run(
        [
            "python",
            "theft_checker.py",
            str(session_dir),
        ],
        check=True,
    )