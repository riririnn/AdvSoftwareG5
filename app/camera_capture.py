"""
カメラ映像の取得・フレーム切り出しモジュール（タスク1）
OpenCVを用いて指定した解像度・フレームレートでカメラ映像を取得し、
フレームごとに処理コールバックへ渡す。防犯用画像の保存にも対応。
"""
import cv2
import time
import os
from datetime import datetime
from pathlib import Path


EVIDENCE_DIR = Path(__file__).parent.parent / "ai" / "collected_images"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


class CameraCapture:
    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            print(f"[CameraCapture] カメラ {self.camera_index} を開けませんでした。")
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        print(
            f"[CameraCapture] カメラ起動: {self.width}x{self.height} @ {self.fps}fps"
        )
        return True

    def release(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()

    def read_frame(self):
        """1フレームを取得して返す。失敗時は None。"""
        if not self.cap or not self.cap.isOpened():
            return None
        ret, frame = self.cap.read()
        return frame if ret else None

    def save_evidence(self, frame, prefix: str = "evidence") -> str:
        """防犯用画像をタイムスタンプ付きで保存し、保存先パスを返す。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = EVIDENCE_DIR / f"{prefix}_{timestamp}.jpg"
        cv2.imwrite(str(filename), frame)
        print(f"[CameraCapture] 証拠画像を保存: {filename}")
        return str(filename)

    def stream(self, frame_callback, show_preview: bool = False):
        """
        フレームを連続取得してコールバックへ渡す。
        frame_callback(frame) -> bool  ※ False を返すと停止
        """
        if not self.open():
            return

        interval = 1.0 / self.fps
        try:
            while True:
                start = time.monotonic()
                frame = self.read_frame()
                if frame is None:
                    print("[CameraCapture] フレーム取得失敗、終了します。")
                    break

                if show_preview:
                    cv2.imshow("Camera Preview", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                should_continue = frame_callback(frame)
                if should_continue is False:
                    break

                elapsed = time.monotonic() - start
                wait = interval - elapsed
                if wait > 0:
                    time.sleep(wait)
        finally:
            self.release()
            if show_preview:
                cv2.destroyAllWindows()


def collect_training_images(
    output_dir: Path = EVIDENCE_DIR,
    camera_index: int = 0,
    width: int = 640,
    height: int = 480,
    capture_interval_sec: float = 1.0,
):
    """
    データセット収集用: Enterで保存、qで終了。
    学習データを手動で効率よく集めるためのユーティリティ。
    """
    cap = CameraCapture(camera_index=camera_index, width=width, height=height)
    if not cap.open():
        return

    print("[DataCollect] Enterキーで画像保存 / 'q'で終了")
    saved_count = 0
    try:
        while True:
            frame = cap.read_frame()
            if frame is None:
                break
            cv2.imshow("Data Collection", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == 13:  # Enter
                path = cap.save_evidence(frame, prefix="train_sample")
                saved_count += 1
                print(f"  保存済: {saved_count}枚 -> {path}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(f"[DataCollect] 合計 {saved_count}枚 保存しました。")


if __name__ == "__main__":
    collect_training_images()
