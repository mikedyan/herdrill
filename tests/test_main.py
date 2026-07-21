import random

from herdrill_chatgpt.keymap import Keymap
from herdrill_chatgpt.main import (
    Session,
    _read_utf8,
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
