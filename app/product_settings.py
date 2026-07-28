"""
商品設定（価格・単重量・重量センサーの割り当て）。

Web管理画面（app/web_admin）で商品を登録・削除したり重量センサーの対象を
変更すると、その内容がこのファイルへ自動的に書き戻される。
そのため実機ごとに内容が異なり、config.py のように全環境で
同一に保つことはできない。

git には初期値としてコミットしてあるが、実機側では以下を1回実行して、
ローカルの書き換えが git の追跡対象にならないようにすること:

    git update-index --skip-worktree app/product_settings.py

手で編集してもよいが、次にWeb管理画面から操作した時点で上書きされる。
"""

# 商品の単価（円）
# 管理画面から更新されます
VEGETABLE_PRICES = {
    "tomato": 50,
    "eggplant": 100,
}


# 対象とする商品ラベル一覧
TARGET_VEGETABLES = [
    "tomato",
    "eggplant",
]


# 現在ロードセルの上に置いている商品のラベル
TARGET_VEGETABLE = "eggplant"

# 商品の単重量（g）
VEGETABLE_WEIGHTS = {
    "tomato": 100,
    "eggplant": 100,
}


# 重量センサーの個数
WEIGHT_SENSOR_COUNT = 1

# 各重量センサーの上に置いている商品のラベル
WEIGHT_SENSOR_TARGETS = {
    "sensor_1": "eggplant",
}
