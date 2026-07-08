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

# 監視カメラ
MONITOR_CAMERA_INDEX = 0

# コインカメラ
COIN_CAMERA_INDEX = 1

# 野菜カメラ
VEGETABLE_CAMERA_INDEX = 2

# 共通設定
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10

# ==========================================
# 判定設定
# ==========================================

# 人が映らなくなってから退店とみなす時間（秒）
PERSON_DISAPPEAR_TIME = 3.0

# コイン認識周期（秒）
COIN_DETECT_INTERVAL = 0.2

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

# 商品の単価（円）
# 管理画面から更新されます
VEGETABLE_PRICES = {
    "asparagus": 150,
}


# 対象とする商品ラベル一覧
TARGET_VEGETABLES = [
    "asparagus",
]


# 現在ロードセルの上に置いている商品のラベル
TARGET_VEGETABLE = "asparagus"

# 商品の単重量（g）
VEGETABLE_WEIGHTS = {
    "asparagus": 100,
}


# 重量センサーの個数
WEIGHT_SENSOR_COUNT = 1

# 各重量センサーの上に置いている商品のラベル
WEIGHT_SENSOR_TARGETS = {
    "sensor_1": "asparagus",
}

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