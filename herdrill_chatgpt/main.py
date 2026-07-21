"""Terminal input, session dispatch, and the curses game loop."""

from __future__ import annotations

import curses
import random
import time
from collections.abc import Callable, Iterable, Iterator

from . import render
from .best import default_path, load_best, save_best
from .keymap import Keymap
from .keymap import load as load_keymap
from .round import NAVIGATION_ACTIONS, Round

ESC = 27
FRAME_SECONDS = 1 / 30

# macOS Terminal.app's Option+digit codepoints on a US keyboard when Option is
# not configured as Meta. This is the owner's real switch-tab input path.
OPTION_DIGITS = {
    "¡": "1",
    "™": "2",
    "£": "3",
    "¢": "4",
    "∞": "5",
    "§": "6",
    "¶": "7",
    "•": "8",
    "ª": "9",
}
SHIFTED_DIGITS = {
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
}
NAMED_KEYS = {
    8: "backspace",
    9: "tab",
    10: "enter",
    13: "enter",
    ESC: "esc",
    32: "space",
    45: "minus",
    127: "backspace",
    curses.KEY_UP: "up",
    curses.KEY_DOWN: "down",
    curses.KEY_LEFT: "left",
    curses.KEY_RIGHT: "right",
    curses.KEY_BACKSPACE: "backspace",
    curses.KEY_ENTER: "enter",
    curses.KEY_F1: "f1",
}


def normalize_key(ch: int) -> str | None:
    """Turn one raw curses key code into a herdr key name."""
    if ch < 0:
        return None
    if ch in NAMED_KEYS:
        return NAMED_KEYS[ch]
    if 1 <= ch <= 26:
        return f"ctrl+{chr(ch + 96)}"
    if 0x80 <= ch <= 0xFF:
        base = ch & 0x7F
        if not 0x20 <= base < 0x7F:
            return None
        name = normalize_key(base)
        return None if name is None else f"alt+{name}"
    if ch > 0xFF:
        return None
    char = chr(ch)
    if char in SHIFTED_DIGITS:
        return f"shift+{SHIFTED_DIGITS[char]}"
    if char.isupper():
        return f"shift+{char.lower()}"
    if not char.isprintable():
        return None
    return char


def normalize_char(char: str) -> str | None:
    digit = OPTION_DIGITS.get(char)
    if digit is not None:
        return f"alt+{digit}"
    return normalize_key(ord(char))


def normalize_input(value: str | int) -> str | None:
    if isinstance(value, int):
        return normalize_key(value)
    return normalize_char(value)


def read_input(stdscr) -> str | int | None:
    """Read one complete codepoint, including on narrow macOS curses."""
    get_wch = getattr(stdscr, "get_wch", None)
    if get_wch is None:
        return _read_utf8(stdscr)
    try:
        value = get_wch()
    except curses.error:
        return None
    if isinstance(value, int) and value < 0:
        return None
    return value


def _utf8_length(lead: int) -> int:
    if 0xC2 <= lead <= 0xDF:
        return 2
    if 0xE0 <= lead <= 0xEF:
        return 3
    if 0xF0 <= lead <= 0xF4:
        return 4
    return 0


def _read_utf8(stdscr) -> str | int | None:
    lead = stdscr.getch()
    if lead < 0:
        return None
    if lead > 0xFF:
        return lead
    if lead < 0x80:
        return chr(lead)

    length = _utf8_length(lead)
    if length == 0:
        return lead

    tail: list[int] = []
    for _ in range(length - 1):
        following = stdscr.getch()
        if following < 0 or not 0x80 <= following <= 0xBF:
            if following >= 0:
                _unget(following)
            for byte in reversed(tail):
                _unget(byte)
            return lead
        tail.append(following)

    try:
        return bytes([lead, *tail]).decode("utf-8")
    except UnicodeDecodeError:
        return lead


def _unget(ch: int) -> None:
    try:
        curses.ungetch(ch)
    except (curses.error, OverflowError, ValueError):
        pass


def _unget_input(value: str | int) -> None:
    if isinstance(value, int):
        _unget(value)
        return
    unget_wch = getattr(curses, "unget_wch", None)
    if unget_wch is not None:
        try:
            unget_wch(value)
            return
        except (curses.error, OverflowError, ValueError):
            return
    if ord(value) < 0x80:
        _unget(ord(value))


def _resolve(stdscr, value: str | int) -> str | None:
    """Distinguish bare escape from the ESC prefix used by Alt chords."""
    name = normalize_input(value)
    if name != "esc":
        return name
    following = read_input(stdscr)
    if following is None:
        return "esc"
    following_name = normalize_input(following)
    if following_name is None or following_name == "esc":
        _unget_input(following)
        return "esc"
    return f"alt+{following_name}"


def drain_keys(stdscr) -> Iterator[str]:
    while True:
        value = read_input(stdscr)
        if value is None:
            return
        key = _resolve(stdscr, value)
        if key is not None:
            yield key


class Session:
    """Headless-friendly input dispatcher for a single round."""

    def __init__(self, game_round: Round, keymap: Keymap) -> None:
        self.round = game_round
        self.keymap = keymap
        self.prefix_armed = False

    def handle(self, key: str, now: float) -> bool:
        """Handle a normalized key. Return False only for an escape quit."""
        if key == "esc":
            return False

        if key == self.keymap.prefix:
            self.prefix_armed = True
            return True

        if self.prefix_armed:
            self.prefix_armed = False
            resolved = self.keymap.resolve(prefixed=True, key=key)
            self._dispatch(resolved, now)
            return True

        # Keymap supports non-prefixed user bindings too. Plain unbound input is
        # intentionally inert: there are no agents or text fields in this game.
        resolved = self.keymap.resolve(prefixed=False, key=key)
        self._dispatch(resolved, now)
        return True

    def _dispatch(
        self,
        resolved: tuple[str, int | None] | None,
        now: float,
    ) -> None:
        if resolved is None:
            return
        action, index = resolved
        if action in NAVIGATION_ACTIONS:
            self.round.apply(action, index=index, now=now)

    def run(
        self,
        stdscr,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> str:
        stdscr.nodelay(True)
        stdscr.keypad(True)

        while True:
            now = clock()
            for key in drain_keys(stdscr):
                if not self.handle(key, now):
                    return "quit"

            self.round.tick(now)
            render.draw(
                stdscr,
                self.round,
                now,
                prefix_armed=self.prefix_armed,
            )
            if self.round.ended:
                return "ended"
            sleep(FRAME_SECONDS)


def play_script(session: Session, script: Iterable[tuple[float, str]]) -> int:
    """Drive normalized keys at synthetic times without curses or sleeping."""
    for now, key in script:
        if not session.handle(key, now):
            break
        session.round.tick(now)
        if session.round.ended:
            break
    return session.round.score


def wait_after_round(
    stdscr,
    score: int,
    best: int,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Return True to restart; q/esc return False."""
    stdscr.nodelay(True)
    stdscr.keypad(True)
    render.draw_end(stdscr, score, best)
    while True:
        keys = list(drain_keys(stdscr))
        if keys:
            return keys[0] not in ("q", "esc")
        sleep(FRAME_SECONDS)


def _hide_cursor() -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass


def run(
    stdscr,
    *,
    best_path: str | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> None:
    """Start immediately and keep offering rounds until the player quits."""
    _hide_cursor()
    render.init_colors()
    keymap = load_keymap()
    path = best_path or default_path()
    best = load_best(path)
    game_rng = rng if rng is not None else random.Random()

    while True:
        game_round = Round(started_at=clock(), rng=game_rng, best_score=best)
        outcome = Session(game_round, keymap).run(stdscr, clock=clock, sleep=sleep)
        if outcome == "quit":
            return

        improved = game_round.beat_best
        best = game_round.finish()
        if improved:
            save_best(best, path)

        if not wait_after_round(stdscr, game_round.score, best, sleep=sleep):
            return


def main() -> None:
    curses.wrapper(run)
