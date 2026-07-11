"""
launcher.py

後処理起動モジュール

セッション終了後に万引き判定プログラム（theft_checker.py）を起動する。
"""

from pathlib import Path
import subprocess
import sys

# theft_checker.py の絶対パス（カレントディレクトリに依存せず起動できるように）
THEFT_CHECKER_PATH = Path(__file__).parent / "theft_checker.py"


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
            sys.executable,  # 実行中のPythonと同じインタプリタを使う
            str(THEFT_CHECKER_PATH),
            str(session_dir),
        ],
        check=True,
    )