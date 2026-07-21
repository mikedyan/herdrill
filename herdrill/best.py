"""Compatibility helpers over the local leaderboard.

New code should use :mod:`herdrill.leaderboard` directly.
"""

from __future__ import annotations

from .leaderboard import (
    add_record,
    best_score,
    default_path,
    load_records,
    make_record,
    save_records,
)

BEST_PATH = "~/.herdrill/leaderboard.json"


def load_best(path: str | None = None) -> int:
    return best_score(load_records(path))


def save_best(score: int, path: str | None = None) -> bool:
    record = make_record("PLAYER", score)
    if record is None:
        return False
    records = load_records(path)
    if score <= best_score(records):
        return True
    return save_records(add_record(records, record), path)
