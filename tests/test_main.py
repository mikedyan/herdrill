import curses
import random

from herdrill_chatgpt.keymap import Keymap
from herdrill_chatgpt.main import (
    Session,
    _csi_modified_key,
    _read_utf8,
    _resolve,
    normalize_input,
    normalize_key,
    play_script,
)
from herdrill_chatgpt.round import Round


def test_normalizes_controls_shifted_digits_and_option_digits():
    assert normalize_key(2) == "ctrl+b"
    assert normalize_input("!") == "shift+1"
    assert normalize_input("™") == "alt+2"
    assert normalize_input(0xB1) == "alt+1"
    assert normalize_input("L") == "shift+l"


class ByteScreen:
    def __init__(self, values):
        self.values = list(values)

    def getch(self):
        return self.values.pop(0) if self.values else -1


def test_narrow_curses_reassembles_option_codepoint_from_utf8_bytes():
    assert _read_utf8(ByteScreen([0xE2, 0x84, 0xA2])) == "™"


class EscapeScreen:
    def __init__(self, values):
        self.values = list(values)
        self.waiting = False
        self.waits = []
        self.nodelay_values = []

    def get_wch(self):
        if not self.values:
            raise curses.error()
        value = self.values[0]
        if value is None:
            self.values.pop(0)
            raise curses.error()
        return self.values.pop(0)

    def timeout(self, milliseconds):
        self.waits.append(milliseconds)
        self.waiting = True

    def nodelay(self, value):
        self.nodelay_values.append(value)


def test_delayed_esc_prefixed_alt_digit_is_not_mistaken_for_quit():
    screen = EscapeScreen([None, "2"])
    assert _resolve(screen, "\x1b") == "alt+2"
    assert screen.waits, "the reader never waited for iTerm's second write"
    assert screen.nodelay_values == [True]


def test_csi_u_alt_digit_from_ghostty_is_normalized():
    screen = EscapeScreen(["[", "5", "0", ";", "3", "u"])
    assert _resolve(screen, "\x1b") == "alt+2"
    assert _csi_modified_key("50;3u") == "alt+2"


def test_csi_u_ctrl_b_prefix_from_ghostty_is_normalized():
    screen = EscapeScreen(["[", "9", "8", ";", "5", "u"])
    assert _resolve(screen, "\x1b") == "ctrl+b"
    assert _csi_modified_key("98;5u") == "ctrl+b"
    # Kitty may include alternate key codes, event type, and associated text.
    assert _csi_modified_key("98:66:98;5:1;2u") == "ctrl+b"


def test_xterm_modify_other_keys_alt_digit_is_normalized():
    assert _csi_modified_key("27;3;50~") == "alt+2"


def test_prefix_is_a_one_key_latch_even_when_chord_is_unbound():
    session = Session(
        Round(0.0, random.Random(1)),
        Keymap.from_bindings({"focus_pane_right": "prefix+l"}),
    )
    assert session.handle("ctrl+b", 1.0)
    assert session.prefix_armed
    assert session.handle("x", 1.0)
    assert not session.prefix_armed
    assert session.round.score == 0


def test_headless_play_harness_clears_from_scripted_real_key_names():
    session = Session(
        Round(0.0, random.Random(1)),
        Keymap.from_bindings({"focus_pane_right": "prefix+l"}),
    )
    score = play_script(session, [(1.0, "ctrl+b"), (1.0, "l")])
    assert score == 1


def test_unprefixed_user_navigation_binding_works():
    session = Session(
        Round(0.0, random.Random(1)),
        Keymap.from_bindings({"focus_pane_right": "l"}),
    )
    assert session.handle("l", 1.0)
    assert session.round.score == 1


def test_escape_quits_without_mutating_round():
    session = Session(Round(0.0, random.Random(1)), Keymap.from_bindings({}))
    assert not session.handle("esc", 1.0)
    assert session.round.score == 0
