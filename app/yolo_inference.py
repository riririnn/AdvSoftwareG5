"""
YOLOリアルタイム推論・集計モジュール（タスク3）
検出した野菜の「種類」「バウンディングボックス座標」「信頼度スコア」を取得し、
種類ごとの個数をリアルタイムで集計する。
結果はJSONで出力可能（重量センサー担当・万引き検知担当との連携用）。
"""
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from ultralytics import YOLO

from camera_capture import CameraCapture

DEFAULT_WEIGHTS = Path(__file__).parent.parent / "ai" / "runs" / "vegetables_v1" / "weights" / "best.pt"
FALLBACK_WEIGHTS = "yolov8n.pt"   # 学習済み重みがない場合の仮モデル

CLASS_NAMES = {
    0: "tomato",
    1: "cucumber",
    2: "eggplant",
    3: "pepper",
}
CLASS_NAMES_JA = {
    "tomato": "トマト",
    "cucumber": "きゅうり",
    "eggplant": "なす",
    "pepper": "ピーマン",
}


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: dict  # {x1, y1, x2, y2, cx, cy, w, h} — 絶対座標


@dataclass
class InferenceResult:
    timestamp: float
    detections: list[Detection] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)  # {"tomato": 2, ...}

    def to_json(self) -> str:
        """重量センサー・万引き検知担当との連携用JSON出力。"""
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "counts": self.counts,
                "detections": [asdict(d) for d in self.detections],
            },
            ensure_ascii=False,
            indent=2,
        )


class VegetableDetector:
    def __init__(
        self,
        weights_path: str | Path | None = None,
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
    ):
        path = weights_path or (
            DEFAULT_WEIGHTS if DEFAULT_WEIGHTS.exists() else FALLBACK_WEIGHTS
        )
        print(f"[Detector] モデル読み込み: {path}")
        self.model = YOLO(str(path))
        self.conf = confidence_threshold
        self.iou = iou_threshold

    def infer(self, frame: np.ndarray) -> InferenceResult:
        """1フレームを推論し InferenceResult を返す。"""
        results = self.model.predict(
            source=frame,
            conf=self.conf,
            iou=self.iou,
            verbose=False,
        )

        detections: list[Detection] = []
        counts: dict[str, int] = {name: 0 for name in CLASS_NAMES.values()}

        for r in results:
            for box in r.boxes:
                class_id = int(box.cls[0])
                class_name = CLASS_NAMES.get(class_id, f"class_{class_id}")
                confidence = float(box.conf[0])

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                w = x2 - x1
                h = y2 - y1

                detections.append(
                    Detection(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=round(confidence, 4),
                        bbox={
                            "x1": round(x1), "y1": round(y1),
                            "x2": round(x2), "y2": round(y2),
                            "cx": round(cx), "cy": round(cy),
                            "w": round(w),  "h": round(h),
                        },
                    )
                )
                if class_name in counts:
                    counts[class_name] += 1

        return InferenceResult(
            timestamp=time.time(),
            detections=detections,
            counts=counts,
        )

    def draw(self, frame: np.ndarray, result: InferenceResult) -> np.ndarray:
        """検出結果をフレームに描画して返す（デバッグ・プレビュー用）。"""
        vis = frame.copy()
        COLORS = {
            "tomato":   (0, 0, 255),
            "cucumber": (0, 255, 0),
            "eggplant": (128, 0, 128),
            "pepper":   (0, 165, 255),
        }
        for det in result.detections:
            b = det.bbox
            color = COLORS.get(det.class_name, (200, 200, 200))
            cv2.rectangle(vis, (b["x1"], b["y1"]), (b["x2"], b["y2"]), color, 2)
            label = f"{CLASS_NAMES_JA.get(det.class_name, det.class_name)} {det.confidence:.0%}"
            cv2.putText(vis, label, (b["x1"], b["y1"] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # 個数サマリ
        y_offset = 20
        for name, count in result.counts.items():
            text = f"{CLASS_NAMES_JA.get(name, name)}: {count}"
            cv2.putText(vis, text, (10, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 22

        return vis


def run_realtime(
    camera_index: int = 0,
    width: int = 640,
    height: int = 480,
    fps: int = 10,
    weights_path: str | None = None,
    result_callback: Callable[[InferenceResult], None] | None = None,
    show_preview: bool = True,
):
    """
    カメラ映像をリアルタイム推論するメインループ。
    result_callback に最新の InferenceResult が渡される。
    """
    detector = VegetableDetector(weights_path=weights_path)
    cam = CameraCapture(camera_index=camera_index, width=width, height=height, fps=fps)

    def on_frame(frame):
        result = detector.infer(frame)

        if result_callback:
            result_callback(result)
        else:
            # デフォルト: 個数をターミナルに表示
            counts_str = ", ".join(
                f"{CLASS_NAMES_JA.get(k, k)}:{v}"
                for k, v in result.counts.items() if v > 0
            ) or "検出なし"
            print(f"\r[推論] {counts_str}  ", end="", flush=True)

        if show_preview:
            vis = detector.draw(frame, result)
            cv2.imshow("Vegetable Detection", vis)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return False  # ストリーム停止

        return True

    cam.stream(on_frame, show_preview=False)
    if show_preview:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_realtime(show_preview=True)
