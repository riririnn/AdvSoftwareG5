"""
YOLO学習スクリプト雛形（タスク2）
ultralytics YOLOv8 を使用。
使い方: python ai/train.py
"""
from pathlib import Path
from ultralytics import YOLO

# ---- 設定 ----
CONFIG_YAML = Path(__file__).parent / "configs" / "vegetables.yaml"
BASE_MODEL = "yolov8n.pt"   # nano: 軽量。精度重視なら yolov8s.pt / yolov8m.pt
EPOCHS = 100
IMG_SIZE = 640
BATCH_SIZE = 16             # GPU VRAM に合わせて調整（ラズパイCPU運用なら8以下）
PATIENCE = 20               # early stopping: 改善なしで何エポック待つか
PROJECT_DIR = Path(__file__).parent / "runs"
RUN_NAME = "vegetables_v1"

# データ拡張パラメータ（照明変化・遮蔽・重なり対策）
AUGMENT_PARAMS = {
    "hsv_h": 0.015,     # 色相ランダム変化（照明色温度の変動を模擬）
    "hsv_s": 0.7,       # 彩度ランダム変化
    "hsv_v": 0.4,       # 明度ランダム変化（照明強度の変動・影を模擬）
    "degrees": 10.0,    # 回転
    "translate": 0.1,   # 平行移動
    "scale": 0.5,       # スケール変化（個体サイズのばらつきを模擬）
    "shear": 2.0,       # せん断
    "flipud": 0.0,      # 上下反転（野菜は通常上下が決まっているので無効化）
    "fliplr": 0.5,      # 左右反転
    "mosaic": 1.0,      # モザイク拡張（複数野菜が重なる状況を模擬）
    "mixup": 0.1,       # MixUp（重なりへの耐性向上）
    "copy_paste": 0.1,  # Copy-Paste（一部が隠れた状態を模擬）
}


def train():
    model = YOLO(BASE_MODEL)

    results = model.train(
        data=str(CONFIG_YAML),
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        patience=PATIENCE,
        project=str(PROJECT_DIR),
        name=RUN_NAME,
        exist_ok=True,
        device="cpu",           # ラズパイはCPU。GPU環境なら "0" に変更
        workers=2,
        **AUGMENT_PARAMS,
    )

    best_weights = PROJECT_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n学習完了。最良モデル: {best_weights}")
    return results


def validate():
    """学習済みモデルの検証（精度評価）"""
    best_weights = PROJECT_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_weights.exists():
        print("先に train() を実行してください。")
        return
    model = YOLO(str(best_weights))
    metrics = model.val(data=str(CONFIG_YAML), imgsz=IMG_SIZE)
    print(f"mAP50: {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")
    return metrics


if __name__ == "__main__":
    train()
    validate()
