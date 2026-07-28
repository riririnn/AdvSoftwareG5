"""
監視カメラ録画モジュール

【役割】
OpenCVのVideoWriterを利用して録画を行う。

【設計】
録画は専用スレッドが1/RECORD_FPS秒周期で frame_source（最新フレームを返す
callable）から取り出して書き込む。メインループから write() を呼ぶ方式は
廃止した。メインループは推論サーバーへのネットワーク往復で数秒単位で
ブロックするため、ループ周回に依存すると「44秒のセッションなのに動画は
1秒」のように再生時間が実時間から大きくズレることが実機で確認された。
スレッドが実時間基準で書き込むことで、再生時間=実時間が構造的に保証される。

現在は controller.py から

    recorder.start(session_dir, frame_source)
    recorder.stop()

で利用することを想定している。frame_source には _FrameGrabber.read など
「呼ぶと最新フレーム(未取得ならNone)を返す関数」を渡す。
"""

from pathlib import Path
import threading
import time

import cv2

from config import (
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    RECORD_FPS,
    VIDEO_FILENAME,
)


class Recorder:
    """
    録画クラス
    """

    def __init__(self):
        self.writer = None
        self.is_recording = False
        self._thread = None
        self._frame_source = None

    def start(self, session_dir: Path, frame_source):
        """
        録画開始

        Parameters
        ----------
        session_dir : Path
            セッションディレクトリ（この中に VIDEO_FILENAME で保存）
        frame_source : callable
            呼ぶと最新フレーム(numpy配列)を返す関数。未取得なら None。
        """

        if self.is_recording:
            return

        video_path = session_dir / VIDEO_FILENAME

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]

        self.writer = cv2.VideoWriter(
            str(video_path),
            fourcc,
            RECORD_FPS,
            (CAMERA_WIDTH, CAMERA_HEIGHT),
        )

        self._frame_source = frame_source
        self.is_recording = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

        print(f"[Recorder] Recording started -> {video_path}")

    def _loop(self):
        """
        録画スレッド本体。1/RECORD_FPS秒周期で最新フレームを書き込む。

        VideoWriterはスレッドセーフではないため、write/releaseは
        このスレッド内でのみ行う（stop()はフラグ操作とjoinのみ）。
        """
        interval = 1.0 / RECORD_FPS
        size_warned = False

        while self.is_recording:
            start = time.monotonic()

            frame = self._frame_source()
            if frame is not None:
                # 万一フレームサイズがwriterの設定と食い違うと、OpenCVは
                # エラーを出さずに壊れた/空のmp4を作るため、ここで防御する
                h, w = frame.shape[:2]
                if (w, h) != (CAMERA_WIDTH, CAMERA_HEIGHT):
                    if not size_warned:
                        size_warned = True
                        print(f"[Recorder] 警告: フレームサイズ {w}x{h} が設定"
                              f"({CAMERA_WIDTH}x{CAMERA_HEIGHT})と異なるためリサイズします")
                    frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
                self.writer.write(frame)

            elapsed = time.monotonic() - start
            wait = interval - elapsed
            if wait > 0:
                time.sleep(wait)

        self.writer.release()

    def stop(self):
        """
        録画終了（二重呼び出し・未開始での呼び出しも安全）
        """

        if not self.is_recording:
            return

        self.is_recording = False  # スレッドがこれを見てreleaseして終わる
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self.writer = None
        self._frame_source = None

        print("[Recorder] Recording finished")
