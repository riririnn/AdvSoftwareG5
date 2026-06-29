"""
theft_checker.py

万引き判定プログラム

【役割】
・vegetable.csv の before/after 個数差分から購入金額を算出
・coin.csv の合計から支払金額を算出
・購入金額と支払金額を比較し、万引き／正常を判定
・結果を session.json に追記保存

【判定ロジック】
1. 野菜ごとに before の個数 - after の個数 = 減少数 を計算
   （個数が増えている場合は矛盾データとみなし 0 として扱う＝無視）
2. 減少数 × VEGETABLE_PRICES[野菜名] の合計 = 購入すべき金額（合計金額）
3. coin.csv の coin 列の合計 = 実際に支払われた金額
4. 不足（支払金額 < 購入すべき金額）していれば "theft"
   一致（支払金額 >= 購入すべき金額）していれば "normal"
   ※ 多く支払っている場合（おつり等は対象外システムのため）も正常扱いとする
"""

import csv
import json
from pathlib import Path

from config import (
    VEGETABLE_PRICES,
    COIN_LOG_FILENAME,
    VEGETABLE_LOG_FILENAME,
    SESSION_INFO_FILENAME,
)


# ==========================================
# 野菜ログ読み込み・集計
# ==========================================

def _load_vegetable_counts(session_dir: Path):
    """
    vegetable.csv を読み込み、phase別の個数を集計する。

    Returns
    -------
    dict
        {
            "before": {"eggplant": 4, "tomato": 2},
            "after":  {"eggplant": 2, "tomato": 2},
        }

    Notes
    -----
    同一 phase・同一野菜の行が複数回記録されている場合は
    最後に記録された値を採用する（最新の個数を正とする）。
    """

    counts = {
        "before": {},
        "after": {},
    }

    path = session_dir / VEGETABLE_LOG_FILENAME

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:

            phase = row["phase"]
            vegetable = row["vegetable"]
            count = int(row["count"])

            if phase not in counts:
                # before/after 以外の想定外フェーズは無視
                continue

            counts[phase][vegetable] = count

    return counts


def _calc_purchase_amount(before: dict, after: dict):
    """
    before/after の個数差分から購入金額（合計金額）を算出する。

    Parameters
    ----------
    before : dict
        {"eggplant": 4, "tomato": 2}
    after : dict
        {"eggplant": 2, "tomato": 2}

    Returns
    -------
    tuple(int, dict)
        (合計金額, 野菜ごとの減少数 {"eggplant": 2, "tomato": 0})

    Notes
    -----
    ・個数が増えている（返品/補充など）場合や、
      在庫データに矛盾がある場合は、増加分は無視し
      0個減として扱う。
    ・VEGETABLE_PRICES に存在しない野菜名は
      価格不明のため金額計算から除外する。
    """

    total_amount = 0
    decreased = {}

    # before/after どちらかにしか登場しない野菜名も
    # 漏れなく扱うため、両方のキーをまとめて走査する
    all_vegetables = set(before.keys()) | set(after.keys())

    for vegetable in all_vegetables:

        before_count = before.get(vegetable, 0)
        after_count = after.get(vegetable, 0)

        diff = before_count - after_count

        if diff < 0:
            # 個数が増えている＝矛盾データ。無視（0個減）
            diff = 0

        decreased[vegetable] = diff

        if diff == 0:
            continue

        price = VEGETABLE_PRICES.get(vegetable)

        if price is None:
            # 価格不明の野菜は金額計算から除外
            continue

        total_amount += price * diff

    return total_amount, decreased


# ==========================================
# コインログ読み込み・集計
# ==========================================

def _calc_paid_amount(session_dir: Path):
    """
    coin.csv を読み込み、支払われた合計金額を算出する。

    Returns
    -------
    int
        支払合計金額
    """

    path = session_dir / COIN_LOG_FILENAME

    paid_amount = 0

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            paid_amount += int(row["coin"])

    return paid_amount


# ==========================================
# session.json 更新
# ==========================================

def _update_session_info(
    session_dir: Path,
    judgement: str,
    purchase_amount: int,
    paid_amount: int,
    shortage: int,
    decreased: dict,
):
    """
    判定結果を session.json に追記する。
    """

    path = session_dir / SESSION_INFO_FILENAME

    with open(path, "r", encoding="utf-8") as f:
        session = json.load(f)

    session["theft_check"] = {
        "judgement": judgement,
        "purchase_amount": purchase_amount,
        "paid_amount": paid_amount,
        "shortage": shortage,
        "decreased_vegetables": decreased,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            session,
            f,
            indent=4,
            ensure_ascii=False,
        )


# ==========================================
# 判定メイン処理
# ==========================================

def check_theft(session_dir: Path):
    """
    万引き判定を実行する。

    Parameters
    ----------
    session_dir : Path
        セッションフォルダへのパス

    Returns
    -------
    dict
        {
            "judgement": "theft" or "normal",
            "purchase_amount": int,
            "paid_amount": int,
            "shortage": int,
            "decreased_vegetables": dict,
        }
    """

    session_dir = Path(session_dir)

    # -----------------------------
    # 野菜個数の集計・購入金額の算出
    # -----------------------------

    counts = _load_vegetable_counts(session_dir)

    purchase_amount, decreased = _calc_purchase_amount(
        counts["before"],
        counts["after"],
    )

    # -----------------------------
    # 支払金額の算出
    # -----------------------------

    paid_amount = _calc_paid_amount(session_dir)

    # -----------------------------
    # 差分判定
    # -----------------------------

    shortage = purchase_amount - paid_amount

    if shortage > 0:
        judgement = "theft"
    else:
        judgement = "normal"
        shortage = 0

    result = {
        "judgement": judgement,
        "purchase_amount": purchase_amount,
        "paid_amount": paid_amount,
        "shortage": shortage,
        "decreased_vegetables": decreased,
    }

    # -----------------------------
    # session.json への結果保存
    # -----------------------------

    _update_session_info(
        session_dir,
        judgement,
        purchase_amount,
        paid_amount,
        shortage,
        decreased,
    )

    return result


def _print_result(session_dir: Path, result: dict):
    """
    判定結果をコンソールに表示する。
    """

    print()
    print("=" * 50)
    print(" Theft Check Result")
    print("=" * 50)
    print(f"Session Directory : {session_dir}")
    print(f"Decreased vegetables : {result['decreased_vegetables']}")
    print(f"Purchase amount (should pay) : {result['purchase_amount']}")
    print(f"Paid amount                  : {result['paid_amount']}")
    print(f"Shortage                     : {result['shortage']}")
    print("-" * 50)

    if result["judgement"] == "theft":
        print(" Judgement : THEFT DETECTED")
    else:
        print(" Judgement : NORMAL PURCHASE")

    print("=" * 50)
    print()


def main():

    import sys

    if len(sys.argv) < 2:
        print("Usage: python theft_checker.py <session_dir>")
        sys.exit(1)

    session_dir = Path(sys.argv[1])

    result = check_theft(session_dir)

    _print_result(session_dir, result)


if __name__ == "__main__":
    main()
