"""
Roboflow データセットのダウンロード・展開スクリプト

使い方:
    ROBOFLOW_API_KEY="<自分のAPIキー>" python ai/download_dataset.py

    APIキーは Roboflow の Settings → API Keys で確認できる。
    ※ APIキーはパスワードと同じ。コードに直接書いてコミットしないこと。

データセットを差し替える場合:
    Roboflow の「Download → YOLOv8 → show download code」に表示される
    workspace / project / version に合わせて下の定数を書き換える。

必要パッケージ:
    pip install roboflow
"""
import os
import sys
from pathlib import Path

import yaml

# ---- ダウンロード対象（Roboflow の「show download code」に合わせる）----
WORKSPACE = "rin-yokoyama"
PROJECT   = "unattended_sales_place"
VERSION   = 4
# ----------------------------------------------------------------------

API_KEY     = os.environ.get("ROBOFLOW_API_KEY", "")
DATASET_DIR = Path(__file__).parent / "dataset"


def download():
    if not API_KEY:
        print('❌ APIキーを環境変数で渡してください:')
        print('   ROBOFLOW_API_KEY="<自分のAPIキー>" python ai/download_dataset.py')
        sys.exit(1)

    try:
        from roboflow import Roboflow
    except ImportError:
        print("❌ roboflow がインストールされていません: pip install roboflow")
        sys.exit(1)

    rf = Roboflow(api_key=API_KEY)
    (
        rf.workspace(WORKSPACE)
        .project(PROJECT)
        .version(VERSION)
        .download("yolov8", location=str(DATASET_DIR))
    )
    print(f"\n✅ ダウンロード完了: {DATASET_DIR}")
    _show_classes(DATASET_DIR)


def _show_classes(dataset_dir: Path):
    """ダウンロードした data.yaml のクラス一覧を表示する。"""
    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.exists():
        print("⚠️  data.yaml が見つかりません。展開先を確認してください。")
        return

    with open(data_yaml, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    names = cfg.get("names", [])
    if isinstance(names, dict):
        names = [v for _, v in sorted(names.items())]

    print(f"\n--- data.yaml のクラス情報 ---")
    print(f"クラス数: {cfg.get('nc', len(names))}")
    for i, n in enumerate(names):
        print(f"  {i}: {n}")

    print(f"\n学習を始めるには:")
    print(f"  python ai/train.py")


if __name__ == "__main__":
    download()
