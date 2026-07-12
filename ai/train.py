"""
YOLO学習スクリプト
ultralytics YOLOv8 を使用。データセットは Roboflow からダウンロードした
ai/dataset/data.yaml（クラス定義込み）を使う。

【学習】
    python ai/train.py

【中断したチェックポイント(last.pt)から再開】
    python ai/train.py --resume

【検証のみ】
    python ai/train.py --mode val

※ 学習は必ず tmux 内で実行すること（SSH切断で学習が止まるのを防ぐ）
"""
import argparse
from pathlib import Path

import torch
import yaml
from ultralytics import YOLO

# ---- デフォルト設定 ----
DEFAULT_DATA_YAML = Path(__file__).parent / "dataset" / "data.yaml"
BASE_MODEL  = "yolov8m.pt"  # medium: 精度重視。RTX5060Ti なら十分動く
EPOCHS      = 100
IMG_SIZE    = 640
BATCH_SIZE  = 16
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


def train(data_yaml: Path = DEFAULT_DATA_YAML, resume: bool = False):
    weights_dir = PROJECT_DIR / RUN_NAME / "weights"

    if resume:
        last_weights = weights_dir / "last.pt"
        if not last_weights.exists():
            raise FileNotFoundError(f"再開用チェックポイントが見つかりません: {last_weights}")
        print(f"\n[Train] チェックポイントから再開します: {last_weights}\n")
        model = YOLO(str(last_weights))
        results = model.train(resume=True)
    else:
        if not data_yaml.exists():
            raise FileNotFoundError(
                f"データセット設定ファイルが見つかりません: {data_yaml}\n"
                "先に ai/download_dataset.py でデータセットをダウンロードしてください。"
            )

        with open(data_yaml, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        print(f"\n[Train] データセット: {data_yaml}")
        print(f"[Train] クラス数: {cfg.get('nc', '?')}")
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
            device="0" if torch.cuda.is_available() else "cpu",
            amp=False,  # AMPチェックがRTX 5060 Ti環境でハングするため無効化
            workers=2,
            **AUGMENT_PARAMS,
        )

    print(f"\n✅ 学習完了。最良モデル: {weights_dir / 'best.pt'}")
    return results


def validate(data_yaml: Path = DEFAULT_DATA_YAML):
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
        default=DEFAULT_DATA_YAML,
        help="データセットyamlのパス（デフォルト: ai/dataset/data.yaml）",
    )
    parser.add_argument(
        "--mode",
        choices=["train", "val"],
        default="train",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="直前のチェックポイント(last.pt)から学習を再開する",
    )
    args = parser.parse_args()

    if args.mode == "train":
        train(args.data, resume=args.resume)
        validate(args.data)
    else:
        validate(args.data)
