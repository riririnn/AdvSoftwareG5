"""
野菜認識推論モジュール

【使い方】
    from ai.inference import load_model, predict

    model = load_model()                         # 起動時に1度だけ呼ぶ
    result = predict(model, "path/to/image.jpg") # 画像パスまたはnumpy配列

【戻り値（predict）】
    {
        "image": "image.jpg",          # ファイル名（パスのbasename）
        "width": 640,                  # 元画像の幅(px)
        "height": 480,                 # 元画像の高さ(px)
        "detections": [
            {
                "class_id": 4,         # クラスID（vegetables.yaml の names と対応）
                "class_name": "broccoli",
                "confidence": 0.78,    # 信頼度（0.0〜1.0）
                "bbox": {
                    "x1": 120,         # 左上X(px)
                    "y1":  45,         # 左上Y(px)
                    "x2": 380,         # 右下X(px)
                    "y2": 290          # 右下Y(px)
                }
            }
        ]
    }
"""

from pathlib import Path

from ultralytics import YOLO

DEFAULT_WEIGHTS = Path(__file__).parent / "runs" / "vegetables_v1" / "weights" / "best.pt"
DEFAULT_CONF = 0.25
DEFAULT_IMGSZ = 640


def load_model(weights: Path = DEFAULT_WEIGHTS) -> YOLO:
    if not weights.exists():
        raise FileNotFoundError(
            f"モデルが見つかりません: {weights}\n"
            "先に ai/train.py を実行して学習を完了させてください。"
        )
    return YOLO(str(weights))


def predict(model: YOLO, source, conf: float = DEFAULT_CONF) -> dict:
    """
    画像1枚を推論してJSON互換のdictを返す。

    Args:
        model:  load_model() で取得したYOLOインスタンス
        source: 画像パス(str/Path)またはnumpy配列(OpenCV形式)
        conf:   信頼度しきい値（これ以下の検出は除外）

    Returns:
        上記docstringの形式のdict
    """
    results = model.predict(source=source, imgsz=DEFAULT_IMGSZ, conf=conf, verbose=False)
    r = results[0]

    h, w = r.orig_shape
    image_name = Path(r.path).name if isinstance(source, (str, Path)) else "frame"

    detections = []
    for box in r.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        detections.append({
            "class_id":   int(box.cls),
            "class_name": model.names[int(box.cls)],
            "confidence": round(float(box.conf), 4),
            "bbox": {
                "x1": round(x1),
                "y1": round(y1),
                "x2": round(x2),
                "y2": round(y2),
            },
        })

    return {
        "image":      image_name,
        "width":      w,
        "height":     h,
        "detections": detections,
    }
