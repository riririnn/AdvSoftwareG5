"""
theft_checker.py

万引き判定プログラム

【役割】
・vegetable.csv の before/after 個数差分から、参考情報としての
  個数ベース減少数（YOLO検知）を算出
・weight.csv の野菜重量変化から、購入合計金額を算出（今回は
  なす（eggplant）のみを対象とした重量ベースの判定）
・coin.csv の合計から投入金額を算出
・weight.csv の coinbox 重量増加と、coin.csv から想定される
  硬貨重量を比較し、コイン重量の整合性をチェック
・上記をもとに万引き／正常を判定し、結果を session.json に追記保存

【判定ロジック】
1. 購入合計金額（重量ベース）
   weight.csv の vegetable 重量の減少量（before - after）を
   VEGETABLE_WEIGHTS（なす1個あたりの重量）で割り、
   推定減少個数を算出する（今回はなすのみを対象とする）。
   重量センサーの誤差を考慮し、VEGETABLE_WEIGHT_MARGIN を
   許容誤差の目安として、最も近い整数個数に丸める。
   丸めた個数 × VEGETABLE_PRICES["eggplant"] = 購入合計金額。

2. 投入金額
   coin.csv の coin 列の合計をそのまま採用する。

3. コイン重量の整合性チェック
   coin.csv の硬貨の種類・枚数から、投入されたはずの
   硬貨の総重量を COIN_WEIGHTS を用いて算出する。
   weight.csv の coinbox 重量増加分と比較し、
   想定重量との差が WEIGHT_MARGIN を超える場合を異常とする。
       ・実測重量が想定より重すぎる場合
         （余分な金属片や不正な物の混入の可能性）
         → coin_weight_status = "too_heavy"
       ・実測重量が想定より軽すぎる場合
         （画像認識上は投入されたことになっているが、
           実際には軽い偽物・代用品である可能性、
           またはカメラの誤検知の可能性）
         → coin_weight_status = "too_light"
       ・差がマージン以内
         → coin_weight_status = "ok"

4. 最終判定
   ・購入合計金額（重量ベース） > 投入金額（coin.csv） → "theft"
   ・または coin_weight_status が "too_heavy" / "too_light" → "theft"
   ・上記いずれにも該当しない → "normal"

   ※ 多く支払っている場合（おつり等は対象外システムのため）は
     それ単体では正常扱いとする。

【YOLO個数検知について】
・vegetable.csv の個数（before/after）は、今回の判定には使用せず、
  decreased_vegetables_yolo として参考情報としてのみ出力する。

【異常系の扱い】
・vegetable.csv / coin.csv / weight.csv が存在しない、列が壊れている、
  数値に変換できない値が入っているなど、CSVの値が正常でない場合は
  判定不能として judgement = "error" とする。
・config.py の TARGET_VEGETABLE が VEGETABLE_PRICES に
  登録されていない（綴りミスなどの設定不整合）場合も、
  同様に判定不能として judgement = "error" とする。
・error の場合、金額・重量関連の値は誤った値を出さないために
  None とし、エラー内容を error_message に記録する。
"""

import csv
import json
from pathlib import Path

from config import (
    VEGETABLE_PRICES,
    VEGETABLE_WEIGHTS,
    TARGET_VEGETABLE,
    COIN_WEIGHTS,
    VEGETABLE_WEIGHT_MARGIN,
    COIN_WEIGHT_MARGIN,
    COIN_LOG_FILENAME,
    VEGETABLE_LOG_FILENAME,
    WEIGHT_LOG_FILENAME,
    SESSION_INFO_FILENAME,
)


# ==========================================
# CSV値の正常性チェック用エラー
# ==========================================

class CsvValidationError(Exception):
    """
    CSVファイルの内容が不正で、判定に使用できない場合に発生させる例外。

    対象:
    ・ファイルが存在しない
    ・想定する列（ヘッダー）が存在しない
    ・count / coin / weight の値が数値に変換できない場合
    """
    pass


# ==========================================
# config.py の設定不整合チェック用エラー
# ==========================================

class ConfigValidationError(Exception):
    """
    config.py の設定値が不整合で、判定に使用できない場合に
    発生させる例外。

    対象:
    ・TARGET_VEGETABLE が VEGETABLE_PRICES に登録されていない
      （綴りミスなどによりキーが一致しない）場合
    """
    pass


def _validate_target_vegetable():
    """
    TARGET_VEGETABLE が VEGETABLE_PRICES に登録されているかを
    確認する。

    Raises
    ------
    ConfigValidationError
        TARGET_VEGETABLE が VEGETABLE_PRICES のキーに
        存在しない場合
    """

    if TARGET_VEGETABLE not in VEGETABLE_PRICES:
        raise ConfigValidationError(
            f"config.py の TARGET_VEGETABLE "
            f"({TARGET_VEGETABLE!r}) が VEGETABLE_PRICES "
            f"({list(VEGETABLE_PRICES.keys())}) に登録されていません。"
            f"綴りミスがないか確認してください。"
        )


# ==========================================
# 野菜ログ読み込み・集計（YOLO個数：参考情報）
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

    Raises
    ------
    CsvValidationError
        ・vegetable.csv が存在しない場合
        ・想定する列（phase, vegetable, count）が無い場合
        ・count が整数に変換できない場合

    Notes
    -----
    同一 phase・同一野菜の行が複数回記録されている場合は
    最後に記録された値を採用する（最新の個数を正とする）。
    この個数は今回の判定には使用せず、参考情報として
    decreased_vegetables_yolo に出力するためだけに用いる。
    """

    counts = {
        "before": {},
        "after": {},
    }

    path = session_dir / VEGETABLE_LOG_FILENAME

    if not path.exists():
        raise CsvValidationError(
            f"{VEGETABLE_LOG_FILENAME} が見つかりません: {path}"
        )

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise CsvValidationError(
                f"{VEGETABLE_LOG_FILENAME} が空、またはヘッダーがありません"
            )

        required_columns = {"phase", "vegetable", "count"}
        missing_columns = required_columns - set(reader.fieldnames)

        if missing_columns:
            raise CsvValidationError(
                f"{VEGETABLE_LOG_FILENAME} に必要な列がありません: "
                f"{missing_columns}"
            )

        for row in reader:

            phase = row["phase"]
            vegetable = row["vegetable"]

            try:
                count = int(row["count"])
            except (TypeError, ValueError):
                raise CsvValidationError(
                    f"{VEGETABLE_LOG_FILENAME} の count が不正な値です: "
                    f"{row}"
                )

            if count < 0:
                raise CsvValidationError(
                    f"{VEGETABLE_LOG_FILENAME} の count が負の値です: "
                    f"{row}"
                )

            if phase not in counts:
                # before/after 以外の想定外フェーズは無視
                continue

            counts[phase][vegetable] = count

    if not counts["before"] or not counts["after"]:
        raise CsvValidationError(
            f"{VEGETABLE_LOG_FILENAME} に before/after 両方のデータが"
            f"揃っていません"
        )

    return counts


def _calc_decreased_yolo(before: dict, after: dict):
    """
    before/after の個数差分から、野菜ごとの減少数（参考情報）を算出する。

    Parameters
    ----------
    before : dict
        {"eggplant": 4, "tomato": 2}
    after : dict
        {"eggplant": 2, "tomato": 2}

    Returns
    -------
    dict
        野菜ごとの減少数 {"eggplant": 2, "tomato": 0}

    Notes
    -----
    ・個数が増えている（返品/補充など）場合や、
      在庫データに矛盾がある場合は、増加分は無視し
      0個減として扱う。
    ・この結果は判定には使用せず、参考情報としてのみ出力する。
    """

    decreased = {}

    all_vegetables = set(before.keys()) | set(after.keys())

    for vegetable in all_vegetables:

        before_count = before.get(vegetable, 0)
        after_count = after.get(vegetable, 0)

        diff = before_count - after_count

        if diff < 0:
            # 個数が増えている＝矛盾データ。無視（0個減）
            diff = 0

        decreased[vegetable] = diff

    return decreased


# ==========================================
# 重量ログ読み込み（weight.csv）
# ==========================================

def _load_weights(session_dir: Path):
    """
    weight.csv を読み込み、phase・target別の重量を集計する。

    Returns
    -------
    dict
        {
            "before": {"vegetable": 1850.0, "coinbox": 900.0},
            "after":  {"vegetable": 1600.0, "coinbox": 1510.0},
        }

    Raises
    ------
    CsvValidationError
        ・weight.csv が存在しない場合
        ・想定する列（phase, target, weight）が無い場合
        ・weight が数値に変換できない場合
        ・before/after 双方に vegetable, coinbox が揃っていない場合

    Notes
    -----
    同一 phase・同一 target の行が複数回記録されている場合は
    最後に記録された値を採用する（最新の重量を正とする）。
    """

    weights = {
        "before": {},
        "after": {},
    }

    path = session_dir / WEIGHT_LOG_FILENAME

    if not path.exists():
        raise CsvValidationError(
            f"{WEIGHT_LOG_FILENAME} が見つかりません: {path}"
        )

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise CsvValidationError(
                f"{WEIGHT_LOG_FILENAME} が空、またはヘッダーがありません"
            )

        required_columns = {"phase", "target", "weight"}
        missing_columns = required_columns - set(reader.fieldnames)

        if missing_columns:
            raise CsvValidationError(
                f"{WEIGHT_LOG_FILENAME} に必要な列がありません: "
                f"{missing_columns}"
            )

        for row in reader:

            phase = row["phase"]
            target = row["target"]

            try:
                weight = float(row["weight"])
            except (TypeError, ValueError):
                raise CsvValidationError(
                    f"{WEIGHT_LOG_FILENAME} の weight が不正な値です: "
                    f"{row}"
                )

            if weight < 0:
                raise CsvValidationError(
                    f"{WEIGHT_LOG_FILENAME} の weight が負の値です: "
                    f"{row}"
                )

            if phase not in weights:
                # before/after 以外の想定外フェーズは無視
                continue

            weights[phase][target] = weight

    required_targets = {"vegetable", "coinbox"}

    for phase in ("before", "after"):

        missing_targets = required_targets - set(weights[phase].keys())

        if missing_targets:
            raise CsvValidationError(
                f"{WEIGHT_LOG_FILENAME} の {phase} に "
                f"必要なtargetがありません: {missing_targets}"
            )

    return weights


def _calc_purchase_amount_by_weight(weights: dict):
    """
    weight.csv の vegetable 重量変化から、購入合計金額を算出する。

    今回はなす（eggplant）のみを判定対象とする。
    野菜全体の重量減少を、なす1個あたりの重量（VEGETABLE_WEIGHTS）
    で割って減少個数を推定する。

    重量センサーの誤差を考慮し、推定個数は VEGETABLE_WEIGHT_MARGIN
    を許容誤差として、最も近い整数個数に丸める。
    （例: なす1個=125g、許容誤差10gのとき、減少重量が120g～130gで
      あれば1個として扱う。範囲内かどうかに関わらず、常に
      最も近い整数個数を採用する。）

    呼び出し前に TARGET_VEGETABLE が VEGETABLE_PRICES に
    登録されていることを確認しておく必要がある
    （_validate_target_vegetable() を参照）。

    Parameters
    ----------
    weights : dict
        _load_weights() の戻り値

    Returns
    -------
    tuple(int, dict, float)
        (購入合計金額, {"eggplant": 丸め後の推定減少個数（整数）},
         丸め誤差(g))

    Notes
    -----
    ・重量が増えている（返品/補充など）場合や矛盾データの場合は、
      増加分を無視し 0g減として扱う。
    ・推定個数は「減少重量 ÷ 単位重量」を四捨五入して整数に丸める。
      VEGETABLE_WEIGHT_MARGIN は、丸めの妥当性の目安（許容誤差）
      として用いるが、範囲外であっても常に最も近い整数個数を採用する。
    """

    before_weight = weights["before"]["vegetable"]
    after_weight = weights["after"]["vegetable"]

    decreased_weight = before_weight - after_weight

    if decreased_weight < 0:
        # 重量が増えている＝矛盾データ。無視（0g減）
        decreased_weight = 0

    unit_weight = VEGETABLE_WEIGHTS

    raw_estimated_count = decreased_weight / unit_weight

    # 最も近い整数個数に丸める
    # （VEGETABLE_WEIGHT_MARGIN は許容誤差の目安として保持するが、
    #   範囲外でも常に最も近い個数を採用する）
    estimated_count = round(raw_estimated_count)

    # 丸めた個数の重量との誤差（参考情報として残す）
    rounding_error = abs(
        decreased_weight - (estimated_count * unit_weight)
    )

    price = VEGETABLE_PRICES[TARGET_VEGETABLE]

    purchase_amount = estimated_count * price

    decreased_weight_based = {
        TARGET_VEGETABLE: estimated_count,
    }

    return purchase_amount, decreased_weight_based, rounding_error


# ==========================================
# コインログ読み込み・集計
# ==========================================

def _calc_paid_amount(session_dir: Path):
    """
    coin.csv を読み込み、投入された合計金額・硬貨リストを算出する。

    Returns
    -------
    tuple(int, list[int])
        (支払合計金額, 投入された硬貨のリスト 例 [100, 100, 500, 10])

    Raises
    ------
    CsvValidationError
        ・coin.csv が存在しない場合
        ・想定する列（coin）が無い場合
        ・coin が整数に変換できない場合
        ・coin の値が COIN_WEIGHTS に存在しない（未知の硬貨種別）場合
    """

    path = session_dir / COIN_LOG_FILENAME

    if not path.exists():
        raise CsvValidationError(
            f"{COIN_LOG_FILENAME} が見つかりません: {path}"
        )

    paid_amount = 0
    coins = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise CsvValidationError(
                f"{COIN_LOG_FILENAME} が空、またはヘッダーがありません"
            )

        if "coin" not in reader.fieldnames:
            raise CsvValidationError(
                f"{COIN_LOG_FILENAME} に coin 列がありません"
            )

        for row in reader:

            try:
                coin = int(row["coin"])
            except (TypeError, ValueError):
                raise CsvValidationError(
                    f"{COIN_LOG_FILENAME} の coin が不正な値です: {row}"
                )

            if coin < 0:
                raise CsvValidationError(
                    f"{COIN_LOG_FILENAME} の coin が負の値です: {row}"
                )

            if coin not in COIN_WEIGHTS:
                raise CsvValidationError(
                    f"{COIN_LOG_FILENAME} に未知の硬貨種別があります: "
                    f"{coin}円（COIN_WEIGHTSに重量未設定）"
                )

            paid_amount += coin
            coins.append(coin)

    return paid_amount, coins


def _calc_expected_coin_weight(coins: list):
    """
    投入された硬貨のリストから、想定される硬貨総重量を算出する。

    Parameters
    ----------
    coins : list[int]
        投入された硬貨のリスト 例 [100, 100, 500, 10]

    Returns
    -------
    float
        想定される硬貨総重量（g）
    """

    return sum(COIN_WEIGHTS[coin] for coin in coins)


def _check_coin_weight_status(weights: dict, coins: list):
    """
    coin.csv から想定される硬貨重量と、weight.csv の coinbox
    重量増加分を比較し、コイン重量の整合性をチェックする。

    想定重量と実測重量増加分との差が COIN_WEIGHT_MARGIN を超える
    場合に異常とみなす。重すぎる場合・軽すぎる場合の両方を区別して
    判定する。

        差 = 実測増加重量 - 想定重量

        差 >  COIN_WEIGHT_MARGIN  → "too_heavy"
            （余分な金属片や不正な物の混入の可能性）
        差 < -COIN_WEIGHT_MARGIN  → "too_light"
            （画像認識上は投入された扱いだが、実際には軽い
              偽物・代用品である可能性、またはカメラの誤検知）
        それ以外（マージン以内）→ "ok"

    Parameters
    ----------
    weights : dict
        _load_weights() の戻り値
    coins : list[int]
        投入された硬貨のリスト

    Returns
    -------
    tuple(str, float, float)
        (coin_weight_status, 想定重量, coinbox実測増加重量)
        coin_weight_status は "ok" / "too_heavy" / "too_light" のいずれか
    """

    expected_weight = _calc_expected_coin_weight(coins)

    actual_increase = (
        weights["after"]["coinbox"] - weights["before"]["coinbox"]
    )

    if actual_increase < 0:
        # coinboxの重量が減っている＝矛盾データ。0として扱う
        actual_increase = 0

    diff = actual_increase - expected_weight

    if diff > COIN_WEIGHT_MARGIN:
        coin_weight_status = "too_heavy"
    elif diff < -COIN_WEIGHT_MARGIN:
        coin_weight_status = "too_light"
    else:
        coin_weight_status = "ok"

    return coin_weight_status, expected_weight, actual_increase


# ==========================================
# session.json 更新
# ==========================================

def _update_session_info(session_dir: Path, theft_check: dict):
    """
    判定結果を session.json に追記する。

    Parameters
    ----------
    session_dir : Path
        セッションフォルダへのパス
    theft_check : dict
        判定結果一式の辞書
    """

    path = session_dir / SESSION_INFO_FILENAME

    with open(path, "r", encoding="utf-8") as f:
        session = json.load(f)

    session["theft_check"] = theft_check

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            session,
            f,
            indent=4,
            ensure_ascii=False,
        )


def _build_error_result(error_message: str):
    """
    judgement = "error" の結果辞書を組み立てる。

    Parameters
    ----------
    error_message : str
        エラー内容（CsvValidationError / ConfigValidationError の
        メッセージ）

    Returns
    -------
    dict
        error用の結果辞書
    """

    return {
        "judgement": "error",
        "purchase_amount": None,
        "paid_amount": None,
        "shortage": None,
        "decreased_vegetables_yolo": {},
        "decreased_vegetables_weight": {},
        "vegetable_weight_rounding_error": None,
        "vegetable_weight_rounding_within_margin": None,
        "coin_weight_status": None,
        "expected_coin_weight": None,
        "actual_coin_weight_increase": None,
        "error_message": error_message,
    }


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
            "judgement": "theft" or "normal" or "error",
            "purchase_amount": int or None,
                重量ベースで算出した購入合計金額
            "paid_amount": int or None,
                coin.csvから算出した投入金額
            "shortage": int or None,
                purchase_amount - paid_amount（0未満の場合は0）
            "decreased_vegetables_yolo": dict,
                個数ベースの減少数（YOLO検知、参考情報）
            "decreased_vegetables_weight": dict,
                重量ベースで推定した減少個数（今回はeggplantのみ、
                VEGETABLE_WEIGHT_MARGINを目安に最も近い整数に丸めた値）
            "vegetable_weight_rounding_error": float or None,
                丸めた個数の重量と実測重量減少分との誤差（g）
            "vegetable_weight_rounding_within_margin": bool or None,
                上記誤差が VEGETABLE_WEIGHT_MARGIN 以内かどうか
            "coin_weight_status": str or None,
                コイン重量の整合性チェック結果
                "ok" / "too_heavy" / "too_light" のいずれか
            "expected_coin_weight": float or None,
                coin.csvから算出した想定硬貨重量
            "actual_coin_weight_increase": float or None,
                weight.csvのcoinbox実測増加重量
            "error_message": str（judgement == "error" の場合のみ）,
        }

    Notes
    -----
    まず config.py の TARGET_VEGETABLE が VEGETABLE_PRICES に
    登録されているかを確認する。登録されていない場合は、CSVを
    読みに行く前に judgement = "error" として処理を打ち切る。

    続けて vegetable.csv / coin.csv / weight.csv の値が正常で
    あることを確認した上で判定を行う。値が不正な場合も同様に、
    judgement = "error" として session.json に記録する。

    判定ルール:
    ・購入合計金額（重量ベース） > 投入金額（coin.csv） → "theft"
    ・または coin_weight_status が "too_heavy" / "too_light" → "theft"
    ・上記いずれにも該当しない → "normal"
    """

    session_dir = Path(session_dir)

    try:

        # -----------------------------
        # config.py の設定不整合チェック
        # （TARGET_VEGETABLE が VEGETABLE_PRICES に存在するか）
        # -----------------------------

        _validate_target_vegetable()

        # -----------------------------
        # YOLO個数（参考情報）の集計
        # -----------------------------

        counts = _load_vegetable_counts(session_dir)

        decreased_vegetables_yolo = _calc_decreased_yolo(
            counts["before"],
            counts["after"],
        )

        # -----------------------------
        # 重量データの読み込み
        # -----------------------------

        weights = _load_weights(session_dir)

        # -----------------------------
        # 購入合計金額（重量ベース）の算出
        # -----------------------------

        purchase_amount, decreased_vegetables_weight, rounding_error = (
            _calc_purchase_amount_by_weight(weights)
        )

        # -----------------------------
        # 投入金額の算出
        # -----------------------------

        paid_amount, coins = _calc_paid_amount(session_dir)

        # -----------------------------
        # コイン重量の整合性チェック
        # -----------------------------

        (
            coin_weight_status,
            expected_coin_weight,
            actual_coin_weight_increase,
        ) = _check_coin_weight_status(weights, coins)

    except (CsvValidationError, ConfigValidationError) as e:

        # -----------------------------
        # CSVの値、またはconfig.pyの設定が不正 → 判定不能
        # -----------------------------

        result = _build_error_result(str(e))

        _update_session_info(session_dir, result)

        return result

    # -----------------------------
    # 差分判定
    # -----------------------------

    shortage = purchase_amount - paid_amount

    if shortage <= 0:
        shortage = 0

    if shortage > 0 or coin_weight_status != "ok":
        judgement = "theft"
    else:
        judgement = "normal"

    result = {
        "judgement": judgement,
        "purchase_amount": purchase_amount,
        "paid_amount": paid_amount,
        "shortage": shortage,
        "decreased_vegetables_yolo": decreased_vegetables_yolo,
        "decreased_vegetables_weight": decreased_vegetables_weight,
        "vegetable_weight_rounding_error": round(rounding_error, 2),
        "vegetable_weight_rounding_within_margin": (
            rounding_error <= VEGETABLE_WEIGHT_MARGIN
        ),
        "coin_weight_status": coin_weight_status,
        "expected_coin_weight": round(expected_coin_weight, 2),
        "actual_coin_weight_increase": round(actual_coin_weight_increase, 2),
    }

    # -----------------------------
    # session.json への結果保存
    # -----------------------------

    _update_session_info(session_dir, result)

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

    if result["judgement"] == "error":
        print(f"Error : {result['error_message']}")
        print("-" * 50)
        print(" Judgement : ERROR (判定不能)")
        print("=" * 50)
        print()
        return

    print(f"Decreased vegetables (YOLO, 参考) : "
          f"{result['decreased_vegetables_yolo']}")
    print(f"Decreased vegetables (Weight)     : "
          f"{result['decreased_vegetables_weight']}")
    print(f"  (rounding error: "
          f"{result['vegetable_weight_rounding_error']} g, "
          f"within margin: "
          f"{result['vegetable_weight_rounding_within_margin']})")
    print(f"Purchase amount (should pay)      : "
          f"{result['purchase_amount']}")
    print(f"Paid amount                       : "
          f"{result['paid_amount']}")
    print(f"Shortage                          : "
          f"{result['shortage']}")
    print("-" * 50)
    print(f"Expected coin weight   : "
          f"{result['expected_coin_weight']} g")
    print(f"Actual coinbox increase: "
          f"{result['actual_coin_weight_increase']} g")
    print(f"Coin weight status     : "
          f"{result['coin_weight_status']}")
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
