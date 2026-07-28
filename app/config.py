"""
システム全体で使用する設定値
"""

from pathlib import Path

# ==========================================
# パス設定
# ==========================================

# app/
APP_DIR = Path(__file__).parent

# プロジェクトルート
PROJECT_ROOT = APP_DIR.parent

# セッション保存先
SESSION_DIR = PROJECT_ROOT / "sessions"

# ==========================================
# カメラ設定
# ==========================================

# カメラ3台構成:
#   監視  = UVC Camera(046d:0821, video4)
#   コイン = C922 Pro Stream Webcam(video2)
#   野菜  = UVC Camera(046d:081b, Logicool C310, video0)
# ※ USBカメラは1台につき2つのデバイス番号を占有し、偶数番のみ撮影可能。
#   実機の番号は `v4l2-ctl --list-devices` で確認する。
#
# コインカメラは必ずC922を使うこと。C310は認識モデルが硬貨を検出できない
# （検出0件。モデルの学習データやC922との画角・焦点距離の違いが原因と推測）
# ことを実機テストで確認している。一方、野菜(vegetable)の検出はC310でも
# 問題なく機能することを確認済みのため、野菜カメラにはC310を使っている。
# 監視カメラ
MONITOR_CAMERA_INDEX = 4

# コインカメラ
COIN_CAMERA_INDEX = 2

# 野菜カメラ（コインカメラとは別、C310を単独使用）
VEGETABLE_CAMERA_INDEX = 0

# 共通設定
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10

# MJPGで開かないカメラのインデックス一覧（無圧縮YUYVで開く）。
#
# ⚠️ ここは「監視カメラ/コインカメラ」という役割ではなく、
# 「そのカメラ個体が挿さっている物理デバイス番号」を直接指定すること。
# 役割(MONITOR_CAMERA_INDEX等)が入れ替わっても、このカメラ個体固有の問題は
# 物理デバイス番号についてまわるため。
#
# 対象:
#  - video0: UVC Camera(046d:081b, Logicool C310)
#  - video4: UVC Camera(046d:0821, 監視カメラ)
#
# どちらも、PC直結では正常に撮影できるにもかかわらず、このラズパイ実機で
# MJPG転送時のみ"Corrupt JPEG data"警告が高頻度（実測ほぼ100%のフレーム）で
# 発生することを診断・実機テストで確認した。C310についてはUSBポート交換・
# 電源電圧(vcgencmd get_throttled=0x0)確認でも解消せず、ケーブルはカメラ
# 一体型で交換不可。カメラ個体・ケーブル・ポート・電源のいずれでもなく、
# Pi 3の非力なUSBコントローラとこれらカメラのMJPG転送特性との相性問題と
# 判断した(docs/corrupt_jpeg_diagnosis.md 参照)。046d:0821でも実機で同様の
# 大量警告を確認したため、同じ対策(YUYV化)を適用する。
# JPEGデコード自体を行わないYUYVに切り替えることで原理的に解消する。
# 帯域は単体なら10fps・640x480で問題にならない（コインカメラのC922は
# MJPGのまま=対策済みの帯域負荷のみ）。2台同時にYUYV化した場合の帯域は
# 未検証のため、select() timeoutが再発しないか実機で確認すること。
#
# v4l2-ctl --list-devices で上記2機種が指しているデバイス番号を確認し、
# 挿し替え等で番号が変わった場合はここも合わせて変更すること。
NO_MJPG_CAMERA_INDEXES = {0, 4}

# 録画(monitor.mp4)のフレームレート。カメラ取得のCAMERA_FPSとは独立。
# 録画は専用スレッドがこの周期で最新フレームを書き込む方式のため、
# この値がそのまま動画の時間解像度になる。
# Pi 3ではmp4vエンコードのCPU負荷が高く、高くしすぎると推論・HX711読み取り
# （60マイクロ秒制約）と競合するため、防犯映像として人の行動を視認できる
# 最低限の3fpsに抑えている。
RECORD_FPS = 3

# ==========================================
# AI推論サーバー設定
# ==========================================

# GPU推論サーバー（app/web_server.py）のURL。
# 別マシンで動かす場合はそのIPに変更する（例: "http://192.168.1.10:8080"）
PREDICT_SERVER_URL = "http://100.98.67.33:8080"

# 検出として採用する信頼度の下限（これ未満の検出は無視）
PERSON_CONF_THRESHOLD = 0.5
COIN_CONF_THRESHOLD = 0.5
VEGETABLE_CONF_THRESHOLD = 0.4

# ==========================================
# 判定設定
# ==========================================

# 人が映らなくなってから退店とみなす時間（秒）
PERSON_DISAPPEAR_TIME = 3.0

# コイン認識周期（秒）
# 0.2秒だとUSBカメラ2台+サーバーへのネットワーク推論が間に合わず、
# Raspberry Pi 3の共有USBバスが逼迫してカメラのread()がタイムアウトする
# ことを実機で確認したため、余裕を持たせている。
COIN_DETECT_INTERVAL = 0.5

# 来客中の支払い状態（重量→必要額、硬貨→投入額）を更新する周期（秒）。
# HX711読み取りとカメラ推論の負荷が競合しないよう、短くしすぎないこと。
PAYMENT_LED_UPDATE_INTERVAL = 1.5

# ==========================================
# LED・ブザー・確認ボタン設定
# ==========================================

# GPIOはcontroller.pyだけが所有する。Web管理画面から同じGPIOを開かない。
RED_LED_PIN = 17
GREEN_LED_PIN = 27
BUZZER_PIN = 22
CONFIRM_BUTTON_PIN = 23

# ==========================================
# ログ設定
# ==========================================

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

VIDEO_FILENAME = "monitor.mp4"

SESSION_INFO_FILENAME = "session.json"

COIN_LOG_FILENAME = "coin.csv"

VEGETABLE_LOG_FILENAME = "vegetable.csv"

# 野菜認識の判定根拠画像（検出枠つき）。before/afterを見比べることで
# 「AIが何を見て野菜数を判定したか」を後から確認できる
VEGETABLE_BEFORE_IMAGE = "vegetable_before.jpg"
VEGETABLE_AFTER_IMAGE = "vegetable_after.jpg"

# 野菜検出が0件だったフェーズに書く「計測済みマーカー」の品目名。
# 行が1つも無いと theft_checker が「データ欠損」と「0個だった」を
# 区別できず、全品持ち去り（最重要の万引きケース）がERRORになるため必須。
# 括弧付きにして実在のYOLOクラス名（英数字）と衝突しないようにしている。
VEGETABLE_NONE_MARKER = "(none)"

WEIGHT_LOG_FILENAME = "weight.csv"

# ==========================================
# 商品設定
# ==========================================

# 商品の価格・単重量・重量センサーの割り当ては、Web管理画面(app/web_admin)が
# 実行中に書き換えるためサーバーとラズパイで一致しない。
# config.py は両者で同一に保つファイルなので、product_settings.py へ分離している。
# product_settings.py は初期値をgitにコミットしてあるが、実機側では
# `git update-index --skip-worktree app/product_settings.py` を1回実行して、
# ローカルの書き換えが追跡対象にならないようにする。
from product_settings import (  # noqa: E402
    VEGETABLE_PRICES,
    TARGET_VEGETABLE,
    VEGETABLE_WEIGHTS,
    WEIGHT_SENSOR_COUNT,
    WEIGHT_SENSOR_TARGETS,
)

# 硬貨の重量 (g)
COIN_WEIGHTS = {
    1: 1,
    5: 3.75,
    10: 4.5,
    50: 4,
    100: 4.8,
    500: 7,
} 

# 重量許容誤差

VEGETABLE_WEIGHT_MARGIN = 10
COIN_WEIGHT_MARGIN = 1.0


