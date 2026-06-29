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

# 野菜の単価（円）
# 万引き判定（theft_checker.py）の購入金額算出に使用
VEGETABLE_PRICES = {
    "eggplant": 710,
    "tomato": 100,
}