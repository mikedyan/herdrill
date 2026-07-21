import random

from herdrill import main
from herdrill.keymap import Keymap
from herdrill.main import (
    Session,
    _read_utf8,
    edit_name,
    normalize_input,
    normalize_key,
    play_script,
)
from herdrill.ramp import TIERS, build_board
from herdrill.round import Round
from herdrill.settings import CONTROL_HERDRILL, GameSettings, load_settings


def test_normalizes_controls_shifted_digits_and_option_digits():
    assert normalize_key(2) == "ctrl+b"
    assert normalize_input("!") == "shift+1"
    assert normalize_input("™") == "alt+2"
    assert normalize_input(0xB1) == "alt+1"
    assert normalize_input("H") == "shift+h"
    assert normalize_input("L") == "shift+l"
    assert normalize_input(",") == "comma"
    assert normalize_input("+") == "plus"
    assert normalize_input(27) == "esc"


class ByteScreen:
    def __init__(self, values):
        self.values = list(values)

    def getch(self):
        return self.values.pop(0) if self.values else -1


def test_narrow_curses_reassembles_option_codepoint_from_utf8_bytes():
    assert _read_utf8(ByteScreen([0xE2, 0x84, 0xA2])) == "™"


def test_name_editor_accepts_text_edits_and_requires_a_name_to_submit():
    name, action = edit_name("", "M")
    assert (name, action) == ("M", None)
    name, action = edit_name(name, " ")
    assert (name, action) == ("M ", None)
    name, action = edit_name(name, 127)
    assert (name, action) == ("M", None)
    assert edit_name("", 10) == ("", None)
    assert edit_name("Mike", 10) == ("Mike", "submit")
    assert edit_name("Mike", 27) == ("Mike", "cancel")


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


def test_escape_prefix_arms_once_and_double_escape_quits():
    session = Session(
        Round(0.0, random.Random(1)),
        Keymap.from_bindings({"focus_pane_right": "prefix+l"}, prefix="esc"),
    )
    assert session.handle("esc", 1.0)
    assert session.prefix_armed
    assert session.handle("l", 1.0)
    assert session.round.score == 1

    session = Session(Round(0.0, random.Random(1)), Keymap(prefix="esc"))
    assert session.handle("esc", 1.0)
    assert not session.handle("esc", 1.0)


def test_headless_play_harness_clears_from_scripted_real_key_names():
    session = Session(
        Round(0.0, random.Random(1)),
        Keymap.from_bindings({"focus_pane_right": "prefix+l"}),
    )
    score = play_script(session, [(1.0, "ctrl+b"), (1.0, "l")])
    assert score == 1


def test_shift_number_switches_spaces_while_plain_number_is_agent_only():
    game_round = Round(0.0, random.Random(0))
    game_round.score = 5
    game_round.tier = TIERS[1]
    game_round.board = build_board(game_round.tier, random.Random(4))
    game_round.target_pane_id = game_round.board.spaces[1].tabs[0].focused_pane_id
    session = Session(
        game_round,
        Keymap.from_bindings(
            {
                "switch_workspace": "prefix+shift+1..9",
                "focus_agent": "prefix+1..9",
            }
        ),
    )

    assert session.handle("ctrl+b", 1.0)
    assert session.handle("2", 1.0)
    assert game_round.board.active_space == 0
    assert game_round.score == 5

    assert session.handle("ctrl+b", 1.0)
    assert session.handle("shift+2", 1.0)
    assert game_round.board.active_space == 1
    assert game_round.score == 6


def test_target_clear_invokes_the_sound_callback_once():
    hits = []
    session = Session(
        Round(0.0, random.Random(1)),
        Keymap.from_bindings({"focus_pane_right": "prefix+l"}),
        on_target=lambda: hits.append("hit"),
    )
    assert session.handle("ctrl+b", 1.0)
    assert session.handle("l", 1.0)
    assert hits == ["hit"]


def test_sound_settings_can_be_selected_and_previewed(monkeypatch, tmp_path):
    values = iter(["j", "\n", "\x1b"])
    previews = []

    class Player:
        available = True

        def play(self, sound_id, *, preview=False):
            previews.append((sound_id, preview))
            return True

        def close(self):
            pass

    monkeypatch.setattr(main, "read_input", lambda _screen: next(values))
    monkeypatch.setattr(main.render, "draw_settings", lambda *args, **kwargs: None)
    path = str(tmp_path / "settings.json")
    chosen = main.choose_sound(
        object(),
        GameSettings(control_mode=CONTROL_HERDRILL),
        Player(),
        path,
        sleep=lambda _: None,
    )

    assert chosen == GameSettings("ping", CONTROL_HERDRILL)
    assert previews == [("ping", True)]
    assert load_settings(path) == chosen


def test_control_mode_can_be_reset_to_herdrill_defaults(monkeypatch, tmp_path):
    values = iter(["j", "\n", "\x1b"])
    monkeypatch.setattr(main, "read_input", lambda _screen: next(values))
    monkeypatch.setattr(main.render, "draw_control_settings", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main,
        "load_keymap",
        lambda *, mode: Keymap.from_bindings({}, source=f"mode:{mode}"),
    )
    path = str(tmp_path / "settings.json")
    settings, keymap = main.choose_controls(
        object(),
        GameSettings(),
        Keymap.from_bindings({}),
        path,
        sleep=lambda _: None,
    )

    assert settings.control_mode == CONTROL_HERDRILL
    assert keymap.source == f"mode:{CONTROL_HERDRILL}"
    assert load_settings(path) == settings


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
