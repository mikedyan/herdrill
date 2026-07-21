"""Terminal input, session dispatch, and the curses game loop."""

from __future__ import annotations

import curses
import random
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import replace
from datetime import datetime

from . import render
from .leaderboard import (
    MAX_NAME_LENGTH,
    Record,
    add_record,
    best_score,
    clean_name,
    default_path,
    load_records,
    make_record,
    save_records,
)
from .keymap import Keymap, canonical_key
from .keymap import load as load_keymap
from .round import NAVIGATION_ACTIONS, Round
from .settings import (
    CONTROL_AUTO,
    CONTROL_HERDRILL,
    GameSettings,
    default_path as default_settings_path,
    load_settings,
    save_settings,
)
from .sound import OFF, SOUND_OPTIONS, SoundPlayer, sound_name

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
PUNCTUATION_KEYS = {
    ",": "comma",
    "+": "plus",
    "`": "backtick",
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
}
if hasattr(curses, "KEY_BTAB"):
    NAMED_KEYS[curses.KEY_BTAB] = "shift+tab"
for _function_number in range(1, 13):
    _code = getattr(curses, f"KEY_F{_function_number}", None)
    if isinstance(_code, int):
        NAMED_KEYS[_code] = f"f{_function_number}"
for _constant, _name in {
    "KEY_SLEFT": "shift+left",
    "KEY_SRIGHT": "shift+right",
    "KEY_SR": "shift+up",
    "KEY_SF": "shift+down",
}.items():
    _code = getattr(curses, _constant, None)
    if isinstance(_code, int):
        NAMED_KEYS[_code] = _name


def normalize_key(ch: int) -> str | None:
    """Turn one raw curses key code into a Herdr key name."""
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
        return None if name is None else canonical_key(f"alt+{name}")
    if ch > 0xFF:
        return None
    char = chr(ch)
    if char in SHIFTED_DIGITS:
        return f"shift+{SHIFTED_DIGITS[char]}"
    if char in PUNCTUATION_KEYS:
        return PUNCTUATION_KEYS[char]
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
    return canonical_key(f"alt+{following_name}")


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

    def __init__(
        self,
        game_round: Round,
        keymap: Keymap,
        *,
        on_target: Callable[[], None] | None = None,
    ) -> None:
        self.round = game_round
        self.keymap = keymap
        self.on_target = on_target
        self.prefix_armed = False

    def handle(self, key: str, now: float) -> bool:
        """Handle a normalized key. Return False only for an escape quit."""
        if self.prefix_armed:
            self.prefix_armed = False
            # Escape cancels/quits after a normal prefix; when Escape itself is
            # the prefix, pressing it twice provides the same escape hatch.
            if key == "esc":
                return False
            resolved = self.keymap.resolve(prefixed=True, key=key)
            self._dispatch(resolved, now)
            return True

        # Herdr permits Escape itself as the configured prefix, so test the
        # prefix before treating a bare Escape as the round's quit key.
        if key == self.keymap.prefix:
            self.prefix_armed = True
            return True

        if key == "esc":
            return False

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
            cleared = self.round.apply(action, index=index, now=now)
            if cleared and self.on_target is not None:
                self.on_target()

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


def choose_sound(
    stdscr,
    settings: GameSettings,
    player: SoundPlayer,
    settings_path: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> GameSettings:
    """Select, preview, and persist one of the target sounds."""
    selected = next(
        (
            index
            for index, option in enumerate(SOUND_OPTIONS)
            if option.id == settings.target_sound
        ),
        0,
    )
    while True:
        render.draw_settings(
            stdscr,
            SOUND_OPTIONS,
            selected,
            settings.target_sound,
            player.available,
        )
        value = read_input(stdscr)
        if value is None:
            sleep(FRAME_SECONDS)
            continue
        key = normalize_input(value)
        if key in ("q", "esc"):
            return settings
        if key in ("up", "k"):
            selected = (selected - 1) % len(SOUND_OPTIONS)
            continue
        if key in ("down", "j"):
            selected = (selected + 1) % len(SOUND_OPTIONS)
            continue
        if key == "m":
            settings = replace(settings, target_sound=OFF)
            player.close()
            save_settings(settings, settings_path)
            continue

        shortcut = "10" if key == "0" else key
        if isinstance(shortcut, str) and shortcut.isdigit():
            index = int(shortcut) - 1
            if 0 <= index < len(SOUND_OPTIONS):
                selected = index
                key = "enter"
        if key in ("enter", "space"):
            settings = replace(settings, target_sound=SOUND_OPTIONS[selected].id)
            save_settings(settings, settings_path)
            player.play(settings.target_sound, preview=True)


def _bindings(keymap: Keymap, *actions: str) -> str:
    labels: list[str] = []
    for action in actions:
        for label in keymap.bindings_for(action):
            if label not in labels:
                labels.append(label)
    return " / ".join(labels) or "unbound"


def control_rows(keymap: Keymap) -> tuple[tuple[str, str], ...]:
    """Compact effective navigation map for the controls settings screen."""
    return (
        (
            "pane move",
            _bindings(
                keymap,
                "focus_pane_left",
                "focus_pane_down",
                "focus_pane_up",
                "focus_pane_right",
            ),
        ),
        (
            "pane cycle",
            _bindings(keymap, "cycle_pane_previous", "cycle_pane_next"),
        ),
        ("tab 1..9", _bindings(keymap, "switch_tab")),
        ("tab prev/next", _bindings(keymap, "previous_tab", "next_tab")),
        ("space 1..9", _bindings(keymap, "switch_workspace")),
        (
            "space prev/next",
            _bindings(keymap, "previous_workspace", "next_workspace"),
        ),
    )


def choose_controls(
    stdscr,
    settings: GameSettings,
    keymap: Keymap,
    settings_path: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[GameSettings, Keymap]:
    """Choose automatic Herdr controls or the built-in game profile."""
    modes = (CONTROL_AUTO, CONTROL_HERDRILL)
    selected = modes.index(settings.control_mode)
    while True:
        render.draw_control_settings(
            stdscr,
            selected,
            settings.control_mode,
            keymap.source_label,
            keymap.config_path,
            control_rows(keymap),
            keymap.warnings,
        )
        value = read_input(stdscr)
        if value is None:
            sleep(FRAME_SECONDS)
            continue
        key = normalize_input(value)
        if key in ("q", "esc"):
            return settings, keymap
        if key in ("up", "k"):
            selected = (selected - 1) % len(modes)
            continue
        if key in ("down", "j"):
            selected = (selected + 1) % len(modes)
            continue
        if key == "r":
            keymap = load_keymap(mode=settings.control_mode)
            continue
        if key in ("enter", "space"):
            settings = replace(settings, control_mode=modes[selected])
            save_settings(settings, settings_path)
            keymap = load_keymap(mode=settings.control_mode)


def choose_settings(
    stdscr,
    settings: GameSettings,
    keymap: Keymap,
    player: SoundPlayer,
    settings_path: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[GameSettings, Keymap]:
    """Top-level settings menu for controls and target sound."""
    selected = 0
    while True:
        render.draw_settings_menu(
            stdscr,
            selected,
            keymap.source_label,
            sound_name(settings.target_sound),
        )
        value = read_input(stdscr)
        if value is None:
            sleep(FRAME_SECONDS)
            continue
        key = normalize_input(value)
        if key in ("q", "esc"):
            return settings, keymap
        if key in ("up", "k"):
            selected = (selected - 1) % 2
            continue
        if key in ("down", "j"):
            selected = (selected + 1) % 2
            continue
        if key not in ("enter", "space"):
            continue
        if selected == 0:
            settings, keymap = choose_controls(
                stdscr,
                settings,
                keymap,
                settings_path,
                sleep=sleep,
            )
        else:
            settings = choose_sound(
                stdscr,
                settings,
                player,
                settings_path,
                sleep=sleep,
            )


def wait_for_start(
    stdscr,
    records: list[Record],
    settings: GameSettings,
    keymap: Keymap,
    player: SoundPlayer,
    settings_path: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[GameSettings, Keymap] | None:
    """Show the opening leaderboard and settings entry point."""
    stdscr.nodelay(True)
    stdscr.keypad(True)
    while True:
        render.draw_start(
            stdscr,
            records,
            sound_name(settings.target_sound),
            keymap.source_label,
        )
        value = read_input(stdscr)
        if value is None:
            sleep(FRAME_SECONDS)
            continue
        key = normalize_input(value)
        if key in ("q", "esc"):
            return None
        if key == "s":
            settings, keymap = choose_settings(
                stdscr,
                settings,
                keymap,
                player,
                settings_path,
                sleep=sleep,
            )
            continue
        if key in ("enter", "space"):
            return settings, keymap


def edit_name(name: str, value: str | int) -> tuple[str, str | None]:
    """Apply one raw key to a name and return ``(name, action)``."""
    key = normalize_input(value)
    if key == "esc":
        return name, "cancel"
    if key == "enter":
        cleaned = clean_name(name)
        return (cleaned, "submit") if cleaned else (name, None)
    if key == "backspace":
        return name[:-1], None

    char = value if isinstance(value, str) else ""
    if (
        len(char) == 1
        and char.isprintable()
        and len(name) < MAX_NAME_LENGTH
        and not (char == " " and (not name or name.endswith(" ")))
    ):
        return name + char, None
    return name, None


def prompt_for_name(
    stdscr,
    score: int,
    best: int,
    recorded_at: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str | None:
    """Collect a required player name; escape cancels and quits."""
    stdscr.nodelay(True)
    stdscr.keypad(True)
    name = ""
    while True:
        render.draw_name_entry(stdscr, score, best, name, recorded_at)
        value = read_input(stdscr)
        if value is None:
            sleep(FRAME_SECONDS)
            continue
        name, action = edit_name(name, value)
        if action == "submit":
            return name
        if action == "cancel":
            return None


def wait_after_round(
    stdscr,
    score: int,
    records: list[Record],
    current: Record,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Show the saved leaderboard. Return True to play another round."""
    stdscr.nodelay(True)
    stdscr.keypad(True)
    render.draw_end(stdscr, score, records, current)
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
    settings_path: str | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
    wall_clock: Callable[[], datetime] = datetime.now,
    sound_player: SoundPlayer | None = None,
) -> None:
    """Run the start screen, timed rounds, and local leaderboard flow."""
    _hide_cursor()
    render.init_colors()
    path = best_path or default_path()
    sound_path = settings_path or default_settings_path()
    records = load_records(path)
    settings = load_settings(sound_path)
    game_rng = rng if rng is not None else random.Random()
    player = sound_player or SoundPlayer()

    try:
        while True:
            # Automatic mode rereads Herdr between rounds, never midway through
            # one timed run.
            keymap = load_keymap(mode=settings.control_mode)
            chosen = wait_for_start(
                stdscr,
                records,
                settings,
                keymap,
                player,
                sound_path,
                sleep=sleep,
            )
            if chosen is None:
                return
            settings, keymap = chosen

            previous_best = best_score(records)
            game_round = Round(
                started_at=clock(),
                rng=game_rng,
                best_score=previous_best,
            )
            outcome = Session(
                game_round,
                keymap,
                on_target=lambda: player.play(settings.target_sound),
            ).run(stdscr, clock=clock, sleep=sleep)
            if outcome == "quit":
                return

            recorded_moment = wall_clock()
            recorded_at = recorded_moment.strftime("%Y-%m-%d %H:%M:%S")
            name = prompt_for_name(
                stdscr,
                game_round.score,
                previous_best,
                recorded_at,
                sleep=sleep,
            )
            if name is None:
                return
            current = make_record(
                name,
                game_round.score,
                recorded_on=recorded_moment,
            )
            if current is None:  # The prompt enforces this; keep persistence defensive.
                continue
            records = add_record(records, current)
            save_records(records, path)

            if not wait_after_round(
                stdscr,
                game_round.score,
                records,
                current,
                sleep=sleep,
            ):
                return
    finally:
        player.close()


def main() -> None:
    curses.wrapper(run)
