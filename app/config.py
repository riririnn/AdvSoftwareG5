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

# カメラ2台構成: 監視=UVC Camera(video0) / コイン・野菜=C922(video2, 共用)
# ※ USBカメラは1台につき2つのデバイス番号を占有し、偶数番のみ撮影可能。
#   実機の番号は `v4l2-ctl --list-devices` で確認する（結合テスト機は 0 と 2）。
# 監視カメラ
MONITOR_CAMERA_INDEX = 0

# コインカメラ
COIN_CAMERA_INDEX = 2

# 野菜カメラ（コインカメラと共用）
VEGETABLE_CAMERA_INDEX = 2

# 共通設定
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10

# ==========================================
# AI推論サーバー設定
# ==========================================

# GPU推論サーバー（app/web_server.py）のURL。
# 別マシンで動かす場合はそのIPに変更する（例: "http://192.168.1.10:8080"）
PREDICT_SERVER_URL = "http://localhost:8080"

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
COIN_DETECT_INTERVAL = 1.0

# ==========================================
# ログ設定
# ==========================================

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

VIDEO_FILENAME = "monitor.mp4"

SESSION_INFO_FILENAME = "session.json"

COIN_LOG_FILENAME = "coin.csv"

VEGETABLE_LOG_FILENAME = "vegetable.csv"

WEIGHT_LOG_FILENAME = "weight.csv"

# ==========================================
# 商品設定
# ==========================================

# 野菜の単価（円）
# 万引き判定（theft_checker.py）の購入金額算出に使用
VEGETABLE_PRICES = {
    "tomato": 50,
    "eggplant": 100
}


# 対象とする野菜の名称
TARGET_VEGETABLE = "eggplant"

# 野菜の重量（g）
VEGETABLE_WEIGHTS = 100

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


