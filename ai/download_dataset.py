"""
Roboflow データセットのダウンロード・展開スクリプト

使い方:
    1. Roboflow でデータセットを選び
       「Download → YOLOv8 → show download code」で表示されるコードを確認する
    2. 以下の WORKSPACE / PROJECT / VERSION / API_KEY を書き換えて実行:
       python ai/download_dataset.py

必要パッケージ:
    pip install roboflow
"""
import sys
import yaml
from pathlib import Path

# ---- ここを Roboflow の「show download code」に合わせて書き換える ----
API_KEY   = "YOUR_API_KEY"    # Roboflow の Settings → API Key
WORKSPACE = "YOUR_WORKSPACE"  # 例: "my-workspace"
PROJECT   = "YOUR_PROJECT"    # 例: "vegetables-test-on9hk"
VERSION   = 1                 # データセットのバージョン番号
# ----------------------------------------------------------------------

DATASET_DIR = Path(__file__).parent / "dataset"


def download():
    if API_KEY == "YOUR_API_KEY":
        print("❌ API_KEY を設定してください（download_dataset.py の先頭部分）")
        sys.exit(1)

    try:
        from roboflow import Roboflow
    except ImportError:
        print("❌ roboflow がインストールされていません: pip install roboflow")
        sys.exit(1)

    rf = Roboflow(api_key=API_KEY)
    dataset = (
        rf.workspace(WORKSPACE)
        .project(PROJECT)
        .version(VERSION)
        .download("yolov8", location=str(DATASET_DIR))
    )
    print(f"\n✅ ダウンロード完了: {DATASET_DIR}")
    _verify(DATASET_DIR)


def _verify(dataset_dir: Path):
    """
    ダウンロード後の整合チェック:
    - data.yaml の存在確認
    - クラス一覧の表示（自前の vegetables.yaml との照合用）
    """
    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.exists():
        print("⚠️  data.yaml が見つかりません。展開先を確認してください。")
        return

    with open(data_yaml, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    names = cfg.get("names", [])
    nc    = cfg.get("nc", len(names))
    print(f"\n--- data.yaml のクラス情報 ---")
    print(f"クラス数: {nc}")
    if isinstance(names, list):
        for i, n in enumerate(names): print(f"  {i}: {n}")
    else:
        for k, v in sorted(names.items()): print(f"  {k}: {v}")

    # 自前 vegetables.yaml との差分表示
    own_yaml = Path(__file__).parent / "configs" / "vegetables.yaml"
    if own_yaml.exists():
        with open(own_yaml, encoding="utf-8") as f:
            own = yaml.safe_load(f)
        own_names = own.get("names", {})
        if isinstance(own_names, list):
            own_names = {i: v for i, v in enumerate(own_names)}

        ext_names = names if isinstance(names, dict) else {i: v for i, v in enumerate(names)}
        diffs = {k for k in set(ext_names) | set(own_names) if ext_names.get(k) != own_names.get(k)}
        if diffs:
            print(f"\n⚠️  vegetables.yaml とのクラスID不一致: id={sorted(diffs)}")
            print("   → 学習は data.yaml を直接使ってください:")
            print(f"   python ai/train.py --data {data_yaml}")
        else:
            print("\n✅ vegetables.yaml とクラスIDが一致しています。")

    print(f"\n学習を始めるには:")
    print(f"  python ai/train.py --data {data_yaml}")


if __name__ == "__main__":
    download()
