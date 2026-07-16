"""
カメラ診断用 統一テストスクリプト（Corrupt JPEG data 原因特定用）

本体コード(app/)には一切依存しない診断専用ツール。
すべてのテストをこの1本で行い、条件の与え方の違いによる結果の揺れを排除する。

【使い方（必ず 2> でstderrをファイルに落とすこと）】

  # 2台同時・FPS10（ステップ1・基準測定）
  python3 scripts/camera_diagnosis.py --cameras 0 2 --fps 10 2> /tmp/stderr.log

  # video0のみ（ステップ2）
  python3 scripts/camera_diagnosis.py --cameras 0 --fps 10 2> /tmp/stderr.log

  # video2のみ（ステップ2）
  python3 scripts/camera_diagnosis.py --cameras 2 --fps 10 2> /tmp/stderr.log

  # 2台同時・FPS5（ステップ3）
  python3 scripts/camera_diagnosis.py --cameras 0 2 --fps 5 2> /tmp/stderr.log

  # YUYV(無圧縮)比較用（--no-mjpg。Corrupt JPEGはMJPG時のみ出る点に注意）
  python3 scripts/camera_diagnosis.py --cameras 0 2 --fps 10 --no-mjpg 2> /tmp/stderr.log

実行後、必ず以下で警告数を数えて記録表に記入する:

  grep -c "Corrupt JPEG" /tmp/stderr.log
"""

import argparse
import threading
import time

import cv2

DURATION_SEC = 60  # すべてのテストで固定（比較可能性のため変更しない）


def watch(camera_index: int, fps: int, use_mjpg: bool, results: dict):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    if use_mjpg:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, fps)

    if not cap.isOpened():
        print(f"[video{camera_index}] エラー: カメラを開けません")
        results[camera_index] = None
        return

    ok_count = 0
    fail_count = 0
    start = time.time()
    while time.time() - start < DURATION_SEC:
        ret, _ = cap.read()
        if ret:
            ok_count += 1
        else:
            fail_count += 1
            print(f"[video{camera_index}] {time.time()-start:.1f}s read失敗")

    cap.release()
    results[camera_index] = (ok_count, fail_count)


def main():
    parser = argparse.ArgumentParser(description="カメラ診断（60秒固定）")
    parser.add_argument("--cameras", type=int, nargs="+", required=True,
                        help="テストするカメラ番号（例: --cameras 0 2）")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--no-mjpg", action="store_true",
                        help="MJPGを指定せず既定フォーマット(YUYV)で読む")
    args = parser.parse_args()

    mode = "YUYV(無圧縮)" if args.no_mjpg else "MJPG"
    print(f"=== カメラ診断開始: cameras={args.cameras} fps={args.fps} mode={mode} {DURATION_SEC}秒 ===")
    print("※ stderr をリダイレクトし忘れていないか確認（使い方はスクリプト冒頭参照）")

    results: dict = {}
    threads = [
        threading.Thread(target=watch, args=(idx, args.fps, not args.no_mjpg, results))
        for idx in args.cameras
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("=== 結果（この数値を記録表に記入） ===")
    for idx in sorted(results):
        r = results[idx]
        if r is None:
            print(f"video{idx}: オープン失敗")
        else:
            ok, ng = r
            print(f"video{idx}: 総フレーム={ok + ng} 成功={ok} read失敗={ng}")
    print("次に実行: grep -c \"Corrupt JPEG\" /tmp/stderr.log  ← 警告数を記録")


if __name__ == "__main__":
    main()
