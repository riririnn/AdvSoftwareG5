"""
重量取得モジュール

【ダミー実装】

後で重量担当者がこのファイルだけ差し替えれば
controller.py は変更不要になることを想定している。
"""

import random


def get_weights():
    """
    ラズパイから重量情報を取得

    Returns
    -------
    dict

    {
        "vegetable": 1840,
        "coinbox": 950
    }
    """

    # ===== ダミー実装 =====

    return {
        "vegetable": random.randint(1800, 2000),
        "coinbox": random.randint(900, 1000),
    }