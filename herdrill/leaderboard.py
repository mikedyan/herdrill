"""Corrupt-tolerant, atomic local leaderboard persistence."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Iterable

LEADERBOARD_PATH = "~/.herdrill/leaderboard.json"
MAX_NAME_LENGTH = 16
MAX_STORED_RECORDS = 100
DISPLAY_RECORDS = 10
UNKNOWN_TIME = "--:--:--"


@dataclass(frozen=True)
class Record:
    name: str
    score: int
    date: str
    time: str = UNKNOWN_TIME

    @property
    def timestamp(self) -> str:
        return f"{self.date} {self.time}"


def default_path() -> str:
    return os.path.expanduser(LEADERBOARD_PATH)


def clean_name(value: str) -> str:
    """Return a compact printable player name suitable for the TUI."""
    if not isinstance(value, str):
        return ""
    printable = "".join(char for char in value if char.isprintable())
    return " ".join(printable.split())[:MAX_NAME_LENGTH]


def _valid_score(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _valid_time(value: object) -> bool:
    if value == UNKNOWN_TIME:
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%H:%M:%S")
    except ValueError:
        return False
    return True


def _record(value: object) -> Record | None:
    if not isinstance(value, dict):
        return None
    name = clean_name(value.get("name", ""))
    score = value.get("score")
    recorded_on = value.get("date")
    recorded_time = value.get("time", UNKNOWN_TIME)
    if (
        not name
        or not _valid_score(score)
        or not _valid_date(recorded_on)
        or not _valid_time(recorded_time)
    ):
        return None
    return Record(name, score, recorded_on, recorded_time)


def ranked(records: Iterable[Record], limit: int | None = None) -> list[Record]:
    """Sort by score while preserving insertion order for tied scores."""
    result = sorted(records, key=lambda record: -record.score)
    return result if limit is None else result[: max(0, limit)]


def top_records(records: Iterable[Record]) -> list[Record]:
    return ranked(records, DISPLAY_RECORDS)


def best_score(records: Iterable[Record]) -> int:
    return max((record.score for record in records), default=0)


def make_record(
    name: str,
    score: int,
    *,
    recorded_on: date | str | None = None,
    recorded_time: str | None = None,
) -> Record | None:
    cleaned = clean_name(name)
    if not cleaned or not _valid_score(score):
        return None

    if recorded_on is None:
        moment = datetime.now()
        date_value = moment.date().isoformat()
        time_value = moment.strftime("%H:%M:%S")
    elif isinstance(recorded_on, datetime):
        date_value = recorded_on.date().isoformat()
        time_value = recorded_on.strftime("%H:%M:%S")
    elif isinstance(recorded_on, date):
        date_value = recorded_on.isoformat()
        time_value = recorded_time or UNKNOWN_TIME
    else:
        date_value = recorded_on
        time_value = recorded_time or UNKNOWN_TIME

    if not _valid_date(date_value) or not _valid_time(time_value):
        return None
    return Record(cleaned, score, date_value, time_value)


def add_record(records: Iterable[Record], record: Record) -> list[Record]:
    """Add one result and retain a bounded, ranked local history."""
    return ranked([*records, record], MAX_STORED_RECORDS)


def _legacy_record(data: object, path: str) -> Record | None:
    """Turn the former {\"best\": n} file into a dated leaderboard row."""
    if not isinstance(data, dict) or not _valid_score(data.get("best")):
        return None
    try:
        timestamp = os.path.getmtime(path)
        moment = datetime.fromtimestamp(timestamp)
    except (OSError, OverflowError, ValueError):
        moment = datetime.now()
    return Record(
        "Previous best",
        data["best"],
        moment.date().isoformat(),
        moment.strftime("%H:%M:%S"),
    )


def load_records(path: str | None = None) -> list[Record]:
    """Read valid records, ignoring malformed files and individual rows."""
    source = path or default_path()
    try:
        with open(source, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        return []

    legacy = _legacy_record(data, source)
    if legacy is not None:
        return [legacy]
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        return []
    records = [record for value in data["records"] if (record := _record(value))]
    return ranked(records, MAX_STORED_RECORDS)


def save_records(records: Iterable[Record], path: str | None = None) -> bool:
    """Atomically save a bounded leaderboard. Return False on I/O failure."""
    valid = [
        record
        for record in records
        if isinstance(record, Record) and _record(asdict(record)) is not None
    ]
    payload = {
        "version": 2,
        "records": [asdict(record) for record in ranked(valid, MAX_STORED_RECORDS)],
    }
    destination = os.path.abspath(path or default_path())
    directory = os.path.dirname(destination)
    temporary = ""
    try:
        os.makedirs(directory, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".leaderboard-", suffix=".tmp", dir=directory
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        return True
    except OSError:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        return False
