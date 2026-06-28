"""
CSVログ保存モジュール
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from config import (
    DATETIME_FORMAT,
    COIN_LOG_FILENAME,
    VEGETABLE_LOG_FILENAME,
    WEIGHT_LOG_FILENAME,
    SESSION_INFO_FILENAME,
    VIDEO_FILENAME,
)


def _now():
    """
    現在時刻を取得
    """
    return datetime.now().strftime(DATETIME_FORMAT)


# ==========================================
# セッション作成
# ==========================================

def create_session(session_dir: Path):
    """
    セッションフォルダ・CSV作成
    """

    session_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    _create_csv(
        session_dir / COIN_LOG_FILENAME,
        ["datetime", "coin"],
    )

    _create_csv(
        session_dir / VEGETABLE_LOG_FILENAME,
        ["datetime", "phase", "vegetable", "count"],
    )

    _create_csv(
        session_dir / WEIGHT_LOG_FILENAME,
        ["datetime", "phase", "target", "weight"],
    )


def _create_csv(path: Path, header: list):
    """
    CSV作成
    """

    if path.exists():
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)


# ==========================================
# session.json
# ==========================================

def create_session_info(session_dir: Path):
    """
    セッション開始情報作成
    """

    session = {
        "session_id": session_dir.name,
        "status": "running",
        "video": VIDEO_FILENAME,
        "start_time": _now(),
        "end_time": None,
    }

    with open(
        session_dir / SESSION_INFO_FILENAME,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            session,
            f,
            indent=4,
            ensure_ascii=False,
        )


def finish_session_info(session_dir: Path):
    """
    セッション終了情報更新
    """

    path = session_dir / SESSION_INFO_FILENAME

    with open(path, "r", encoding="utf-8") as f:
        session = json.load(f)

    session["status"] = "finished"
    session["end_time"] = _now()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            session,
            f,
            indent=4,
            ensure_ascii=False,
        )


# ==========================================
# コインログ
# ==========================================

def log_coin(session_dir: Path, coin: int):
    """
    コインログ保存
    """

    with open(
        session_dir / COIN_LOG_FILENAME,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            _now(),
            coin,
        ])


# ==========================================
# 野菜ログ
# ==========================================

def log_vegetable(
    session_dir: Path,
    phase: str,
    vegetable: str,
    count: int,
):
    """
    野菜ログ保存
    """

    with open(
        session_dir / VEGETABLE_LOG_FILENAME,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            _now(),
            phase,
            vegetable,
            count,
        ])


# ==========================================
# 重量ログ
# ==========================================

def log_weight(
    session_dir: Path,
    phase: str,
    target: str,
    weight: float,
):
    """
    重量ログ保存
    """

    with open(
        session_dir / WEIGHT_LOG_FILENAME,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            _now(),
            phase,
            target,
            weight,
        ])