"""
監視カメラ録画モジュール

【役割】
OpenCVのVideoWriterを利用して録画を行う。

現在は controller.py から

    recorder.start(...)
    recorder.write(...)
    recorder.stop()

で利用することを想定している。
"""

from pathlib import Path
import cv2

from config import (
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_FPS,
    VIDEO_FILENAME,
)


class Recorder:
    """
    録画クラス
    """

    def __init__(self):
        self.writer = None
        self.is_recording = False

    def start(self, session_dir: Path):
        """
        録画開始
        """

        video_path = session_dir / VIDEO_FILENAME

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]

        self.writer = cv2.VideoWriter(
            str(video_path),
            fourcc,
            CAMERA_FPS,
            (CAMERA_WIDTH, CAMERA_HEIGHT),
        )

        self.is_recording = True

        print(f"[Recorder] Recording started -> {video_path}")

    def write(self, frame):
        """
        フレームを書き込む
        """

        if self.is_recording and self.writer is not None:
            self.writer.write(frame)

    def stop(self):
        """
        録画終了
        """

        if self.writer is not None:
            self.writer.release()

        self.writer = None
        self.is_recording = False

        print("[Recorder] Recording finished")