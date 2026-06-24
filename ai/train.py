"""
YOLO学習スクリプト（タスク2）
ultralytics YOLOv8 を使用。

【Roboflowデータセットを使う場合（推奨）】
    python ai/train.py --data ai/dataset/data.yaml

【自前データを使う場合】
    python ai/train.py  # デフォルト: ai/configs/vegetables.yaml

【検証のみ】
    python ai/train.py --mode val --data ai/dataset/data.yaml
"""
import argparse
from pathlib import Path

import yaml
from ultralytics import YOLO

# ---- デフォルト設定 ----
DEFAULT_CONFIG_YAML = Path(__file__).parent / "configs" / "vegetables.yaml"
BASE_MODEL  = "yolov8n.pt"  # nano: 軽量。精度重視なら yolov8s.pt / yolov8m.pt
EPOCHS      = 100
IMG_SIZE    = 640
BATCH_SIZE  = 16            # ラズパイCPU運用なら 4〜8 を推奨
PATIENCE    = 20            # early stopping: 改善なしで止まるエポック数
PROJECT_DIR = Path(__file__).parent / "runs"
RUN_NAME    = "vegetables_v1"

# データ拡張（照明変化・遮蔽・重なり対策）
AUGMENT_PARAMS = {
    "hsv_h": 0.015,    # 色相変化（照明色温度の変動を模擬）
    "hsv_s": 0.7,      # 彩度変化
    "hsv_v": 0.4,      # 明度変化（影・逆光を模擬）
    "degrees": 10.0,   # 回転
    "translate": 0.1,  # 平行移動
    "scale": 0.5,      # スケール変化
    "shear": 2.0,
    "flipud": 0.0,     # 上下反転なし（野菜の向きが概ね固定のため）
    "fliplr": 0.5,
    "mosaic": 1.0,     # Mosaic（複数野菜が重なる状況を模擬）
    "mixup": 0.1,
    "copy_paste": 0.1, # Copy-Paste（一部遮蔽を模擬）
}


def check_class_alignment(data_yaml: Path) -> None:
    """
    ⚠️ クラスID整合チェック
    Roboflowデータ付属の data.yaml と自前の vegetables.yaml で
    クラス順が異なる場合は警告を出す。学習前に必ず確認する。
    """
    own_yaml = DEFAULT_CONFIG_YAML
    if not own_yaml.exists() or data_yaml == own_yaml:
        return

    with open(data_yaml, encoding="utf-8") as f:
        ext = yaml.safe_load(f)
    with open(own_yaml, encoding="utf-8") as f:
        own = yaml.safe_load(f)

    ext_names = ext.get("names", {})
    own_names = own.get("names", {})

    # dict形式 {0: "tomato", ...} またはリスト形式 ["tomato", ...] に対応
    if isinstance(ext_names, list):
        ext_names = {i: v for i, v in enumerate(ext_names)}
    if isinstance(own_names, list):
        own_names = {i: v for i, v in enumerate(own_names)}

    mismatches = [
        f"  id={k}: データ={ext_names.get(k)!r} ≠ 自前={own_names.get(k)!r}"
        for k in set(ext_names) | set(own_names)
        if ext_names.get(k) != own_names.get(k)
    ]
    if mismatches:
        print("⚠️  [クラスID不一致] データ付属の data.yaml をそのまま使います（vegetables.yaml は学習に使いません）")
        for m in mismatches:
            print(m)
    else:
        print("✅ [クラスID整合] 問題なし")


def train(data_yaml: Path = DEFAULT_CONFIG_YAML):
    if not data_yaml.exists():
        raise FileNotFoundError(
            f"データセット設定ファイルが見つかりません: {data_yaml}\n"
            "Roboflow からダウンロードした data.yaml を --data で指定するか、\n"
            "ai/dataset/ に画像とラベルを配置してください。"
        )

    check_class_alignment(data_yaml)

    with open(data_yaml, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    nc = cfg.get("nc", "?")
    names = cfg.get("names", [])
    print(f"\n[Train] データセット: {data_yaml}")
    print(f"[Train] クラス数: {nc}  クラス: {names}")
    print(f"[Train] モデル: {BASE_MODEL}  エポック: {EPOCHS}  バッチ: {BATCH_SIZE}\n")

    model = YOLO(BASE_MODEL)
    results = model.train(
        data=str(data_yaml),
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        patience=PATIENCE,
        project=str(PROJECT_DIR),
        name=RUN_NAME,
        exist_ok=True,
        device="cpu",   # ラズパイはCPU。GPU環境なら "0" に変更
        workers=2,
        **AUGMENT_PARAMS,
    )

    best_weights = PROJECT_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n✅ 学習完了。最良モデル: {best_weights}")
    return results


def validate(data_yaml: Path = DEFAULT_CONFIG_YAML):
    """学習済みモデルを検証データで評価する。"""
    best_weights = PROJECT_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_weights.exists():
        print("先に train を実行してください。")
        return
    model = YOLO(str(best_weights))
    metrics = model.val(data=str(data_yaml), imgsz=IMG_SIZE)
    print(f"mAP50:    {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_CONFIG_YAML,
        help="データセットyamlのパス（Roboflow付属のdata.yamlを推奨）",
    )
    parser.add_argument(
        "--mode",
        choices=["train", "val"],
        default="train",
    )
    args = parser.parse_args()

    if args.mode == "train":
        train(args.data)
        validate(args.data)
    else:
        validate(args.data)
