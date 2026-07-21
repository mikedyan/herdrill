"""Corrupt-tolerant, atomic local best-score persistence."""

from __future__ import annotations

import json
import os
import tempfile

BEST_PATH = "~/.herdr-jump/best.json"


def default_path() -> str:
    return os.path.expanduser(BEST_PATH)


def load_best(path: str | None = None) -> int:
    """Read a non-negative integer best, or zero for any bad input."""
    try:
        with open(path or default_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        return 0

    value = data.get("best") if isinstance(data, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def save_best(score: int, path: str | None = None) -> bool:
    """Atomically save ``score``. Return False if the filesystem rejects it."""
    if isinstance(score, bool) or not isinstance(score, int) or score < 0:
        return False

    destination = os.path.abspath(path or default_path())
    directory = os.path.dirname(destination)
    temporary = ""
    try:
        os.makedirs(directory, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".best-", suffix=".tmp", dir=directory
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"best": score}, handle, separators=(",", ":"))
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
