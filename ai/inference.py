"""
推論モジュール（野菜・硬貨・人間）

【使い方】
    from ai.inference import load_model, load_person_model, predict_all

    model = load_model()                # 野菜・硬貨（自前学習済み）
    person_model = load_person_model()  # 人間（COCO事前学習済み）
    result = predict_all(model, person_model, "path/to/image.jpg")  # またはnumpy配列

    野菜・硬貨だけでよい場合は predict(model, source) を使う。

【戻り値（predict / predict_all 共通）】
    {
        "image": "image.jpg",          # ファイル名（numpy配列の場合は "frame"）
        "width": 640,                  # 元画像の幅(px)
        "height": 480,                 # 元画像の高さ(px)
        "detections": [
            {
                "class_id": 2,         # クラスID（ai/dataset/data.yaml の names と対応。人間のみ -1）
                "class_name": "100yen",
                "confidence": 0.85,    # 信頼度（0.0〜1.0）
                "bbox": {
                    "x1": 229,         # 左上X(px)
                    "y1": 226,         # 左上Y(px)
                    "x2": 341,         # 右下X(px)
                    "y2": 288          # 右下Y(px)
                }
            }
        ]
    }
"""

from pathlib import Path

from ultralytics import YOLO

DEFAULT_WEIGHTS = Path(__file__).parent / "runs" / "vegetables_v1" / "weights" / "best.pt"
PERSON_WEIGHTS = "yolov8s.pt"  # COCO事前学習済み（初回実行時に自動ダウンロード）
PERSON_CLASS_ID = 0            # COCOの person クラス
DEFAULT_CONF = 0.25
DEFAULT_IMGSZ = 640


def load_model(weights: Path = DEFAULT_WEIGHTS) -> YOLO:
    if not weights.exists():
        raise FileNotFoundError(
            f"モデルが見つかりません: {weights}\n"
            "先に ai/train.py を実行して学習を完了させてください。"
        )
    return YOLO(str(weights))


def load_person_model(weights: str = PERSON_WEIGHTS) -> YOLO:
    """人間検出用のCOCO事前学習済みモデルをロードする（学習不要）。"""
    return YOLO(weights)


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


def predict_all(model: YOLO, person_model: YOLO, source, conf: float = DEFAULT_CONF) -> dict:
    """
    野菜・硬貨モデルと人間検出モデルの両方で推論し、結果をマージして返す。

    人間の検出は class_name="person" として detections に追加される。
    class_id は自前データセットのIDと衝突しないよう -1 とする。
    """
    result = predict(model, source, conf)

    person_results = person_model.predict(
        source=source, imgsz=DEFAULT_IMGSZ, conf=conf,
        classes=[PERSON_CLASS_ID], verbose=False,
    )
    for box in person_results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        result["detections"].append({
            "class_id":   -1,
            "class_name": "person",
            "confidence": round(float(box.conf), 4),
            "bbox": {
                "x1": round(x1),
                "y1": round(y1),
                "x2": round(x2),
                "y2": round(y2),
            },
        })

    return result
