"""Persistent game presentation and control settings."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass

from .sound import DEFAULT_SOUND, OFF, option_for

SETTINGS_PATH = "~/.herdrill/settings.json"
CONTROL_AUTO = "auto"
CONTROL_HERDRILL = "herdrill"
CONTROL_MODES = {CONTROL_AUTO, CONTROL_HERDRILL}


@dataclass(frozen=True)
class GameSettings:
    target_sound: str = DEFAULT_SOUND
    control_mode: str = CONTROL_AUTO


def default_path() -> str:
    return os.path.expanduser(SETTINGS_PATH)


def _valid_sound(value: object) -> bool:
    return isinstance(value, str) and (value == OFF or option_for(value) is not None)


def _valid_control_mode(value: object) -> bool:
    return isinstance(value, str) and value in CONTROL_MODES


def load_settings(path: str | None = None) -> GameSettings:
    try:
        with open(path or default_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        return GameSettings()
    if not isinstance(data, dict):
        return GameSettings()

    sound = data.get("target_sound")
    mode = data.get("control_mode", CONTROL_AUTO)
    return GameSettings(
        sound if _valid_sound(sound) else DEFAULT_SOUND,
        mode if _valid_control_mode(mode) else CONTROL_AUTO,
    )


def save_settings(settings: GameSettings, path: str | None = None) -> bool:
    if (
        not isinstance(settings, GameSettings)
        or not _valid_sound(settings.target_sound)
        or not _valid_control_mode(settings.control_mode)
    ):
        return False

    destination = os.path.abspath(path or default_path())
    directory = os.path.dirname(destination)
    temporary = ""
    try:
        os.makedirs(directory, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".settings-", suffix=".tmp", dir=directory
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": 2,
                    "target_sound": settings.target_sound,
                    "control_mode": settings.control_mode,
                },
                handle,
                separators=(",", ":"),
            )
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
