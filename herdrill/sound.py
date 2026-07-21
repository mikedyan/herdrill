"""macOS system-sound choices and non-blocking target playback."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Protocol

AFPLAY = "/usr/bin/afplay"
SYSTEM_SOUND_DIR = "/System/Library/Sounds"


@dataclass(frozen=True)
class SoundOption:
    id: str
    name: str
    file_name: str
    description: str

    @property
    def path(self) -> str:
        return os.path.join(SYSTEM_SOUND_DIR, self.file_name)


# Deliberately varied: short UI ticks, bells, resonant tones, electronic cues,
# playful effects, and a low percussive hit.
SOUND_OPTIONS = (
    SoundOption("tink", "Tink", "Tink.aiff", "crisp metallic tick"),
    SoundOption("ping", "Ping", "Ping.aiff", "bright bell ping"),
    SoundOption("pop", "Pop", "Pop.aiff", "soft interface pop"),
    SoundOption("glass", "Glass", "Glass.aiff", "resonant glass chime"),
    SoundOption("hero", "Hero", "Hero.aiff", "triumphant flourish"),
    SoundOption("morse", "Morse", "Morse.aiff", "electronic code pulse"),
    SoundOption("submarine", "Submarine", "Submarine.aiff", "sonar-style alert"),
    SoundOption("funk", "Funk", "Funk.aiff", "quirky synth stab"),
    SoundOption("bottle", "Bottle", "Bottle.aiff", "hollow bottle pluck"),
    SoundOption("basso", "Basso", "Basso.aiff", "deep percussive thud"),
)
DEFAULT_SOUND = SOUND_OPTIONS[0].id
OFF = "off"


def option_for(sound_id: str) -> SoundOption | None:
    return next((option for option in SOUND_OPTIONS if option.id == sound_id), None)


def sound_name(sound_id: str) -> str:
    option = option_for(sound_id)
    return option.name if option is not None else "Muted"


class Process(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class SoundPlayer:
    """Play one short cue at a time without blocking the game loop."""

    def __init__(self, *, executable: str = AFPLAY) -> None:
        self.executable = executable
        self._process: Process | None = None

    @property
    def available(self) -> bool:
        return os.path.isfile(self.executable) and any(
            os.path.isfile(option.path) for option in SOUND_OPTIONS
        )

    def play(self, sound_id: str, *, preview: bool = False) -> bool:
        option = option_for(sound_id)
        if option is None or not os.path.isfile(self.executable) or not os.path.isfile(option.path):
            return False
        self._stop_current()
        try:
            self._process = subprocess.Popen(
                [
                    self.executable,
                    "--volume",
                    "0.65",
                    "--time",
                    "1.40" if preview else "0.55",
                    option.path,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            self._process = None
            return False
        return True

    def _stop_current(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait(timeout=0.2)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def close(self) -> None:
        self._stop_current()
