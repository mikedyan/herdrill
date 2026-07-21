import curses
import random

from herdrill import render
from herdrill.leaderboard import Record
from herdrill.round import Round


class FakeScreen:
    def __init__(self, width=100, height=30):
        self.width = width
        self.height = height
        self.line_calls = 0
        self.erase()
        self.refreshed = 0

    def getmaxyx(self):
        return self.height, self.width

    def erase(self):
        self.cells = [[" " for _ in range(self.width)] for _ in range(self.height)]
        self.attrs = [[0 for _ in range(self.width)] for _ in range(self.height)]

    def addnstr(self, y, x, text, byte_count, attr=0):
        assert 0 <= y < self.height
        assert 0 <= x < self.width
        assert byte_count == len(text.encode("utf-8", "replace"))
        assert x + len(text) <= self.width
        for offset, char in enumerate(text):
            self.cells[y][x + offset] = char
            self.attrs[y][x + offset] = attr

    def addch(self, y, x, char, attr=0):
        assert isinstance(char, str) and len(char) == 1
        assert 0 <= y < self.height
        assert 0 <= x < self.width
        self.cells[y][x] = char
        self.attrs[y][x] = attr

    def hline(self, y, x, char, count, attr=0):
        self.line_calls += 1
        for offset in range(count):
            self.addch(y, x + offset, char, attr)

    def vline(self, y, x, char, count, attr=0):
        self.line_calls += 1
        for offset in range(count):
            self.addch(y + offset, x, char, attr)

    def refresh(self):
        self.refreshed += 1

    def text(self):
        return "\n".join("".join(row) for row in self.cells)


def test_frame_shows_focus_target_clock_score_and_best():
    screen = FakeScreen()
    game_round = Round(0.0, random.Random(1), best_score=7)
    render.draw(screen, game_round, 2.5, prefix_armed=True)
    text = screen.text()
    assert "┌" in text and "┐" in text
    assert "┌─────────┐" in text
    assert "│    ◆    │" in text
    assert "TARGET" in text
    assert screen.line_calls > 0, "borders should use the terminal line API"
    assert "◆ target" in text
    assert "57.5s" in text
    assert "score 0" in text
    assert "best 7" in text
    assert "PREFIX" in text
    assert screen.refreshed == 1


def test_target_box_and_focus_marker_reach_actual_fake_screen_cells():
    screen = FakeScreen(60, 18)
    game_round = Round(0.0, random.Random(5))
    render.draw(screen, game_round, 0.0)
    rows = screen.text().splitlines()
    assert any("┌─────────┐" in row for row in rows)
    assert any("│    ◆    │" in row for row in rows)
    assert any("TARGET" in row for row in rows)
    assert "█" not in screen.text(), "the target should not be a dense block"
    assert "s1:t1:p1" not in screen.text(), "internal pane ids leaked into the UI"


def test_highlighted_navigation_never_inherits_dim(monkeypatch):
    monkeypatch.setattr(render, "pair", lambda number: number)
    monkeypatch.setattr(render, "_COLOR_ENABLED", True)

    active = render._navigation_attr(active=True, target=True)
    target = render._navigation_attr(active=False, target=True)
    inactive = render._navigation_attr(active=False, target=False)

    assert active & curses.A_BOLD
    assert target & curses.A_BOLD
    assert not active & curses.A_DIM
    assert not target & curses.A_DIM
    assert inactive & curses.A_DIM


def test_focus_uses_a_distinct_border_without_blacking_out_other_panes(monkeypatch):
    monkeypatch.setattr(render, "pair", lambda number: number)
    screen = FakeScreen()
    game_round = Round(0.0, random.Random(1))
    render.draw(screen, game_round, 1.0, prefix_armed=True)

    # Tier zero is a left/right split with focus on the left and target right.
    assert screen.attrs[2][21] == render.PAIR_FOCUS
    assert screen.attrs[2][60] == render.PAIR_BORDER_DIM
    assert screen.attrs[4][23] == 0
    assert screen.attrs[4][62] == 0


def test_renderer_never_writes_out_of_bounds_across_supported_sizes():
    for width, height in ((48, 15), (60, 18), (100, 30), (180, 50)):
        for seed in range(5):
            screen = FakeScreen(width, height)
            game_round = Round(0.0, random.Random(seed))
            render.draw(screen, game_round, 1.0)
            assert screen.refreshed == 1


def test_small_terminal_gets_a_legible_message():
    screen = FakeScreen(30, 8)
    game_round = Round(0.0, random.Random(0))
    render.draw(screen, game_round, 0.0)
    assert "needs" in screen.text()


def test_start_screen_shows_instructions_and_timestamped_leaderboard():
    screen = FakeScreen()
    records = [Record("Mike", 22, "2026-07-21", "14:35:09")]
    render.draw_start(screen, records)
    text = screen.text()
    assert "HERDRILL" in text
    assert "Herdrill leaderboard" in text
    assert "Mike" in text
    assert "2026-07-21 14:35:09" in text
    assert "enter / space start" in text
    assert "s settings" in text
    assert "sound Tink" in text
    assert "controls Herdrill defaults" in text


def test_name_entry_screen_shows_score_timestamp_and_editable_name():
    screen = FakeScreen()
    render.draw_name_entry(screen, 14, 10, "Mike", "2026-07-21 14:35:09")
    text = screen.text()
    assert "ROUND COMPLETE" in text
    assert "14 targets cleared" in text
    assert "NEW BEST" in text
    assert "enter name" in text
    assert "> Mike" in text
    assert "2026-07-21 14:35:09" in text


def test_end_screen_shows_saved_record_leaderboard_and_restart_instructions():
    screen = FakeScreen()
    current = Record("Mike", 14, "2026-07-21", "14:35:09")
    render.draw_end(screen, 14, [current], current)
    text = screen.text()
    assert "SCORE SAVED" in text
    assert "Mike" in text
    assert "14" in text
    assert "2026-07-21 14:35:09" in text
    assert "return to start" in text
    assert "q / esc" in text


def test_settings_menu_shows_controls_and_sound_source():
    screen = FakeScreen()
    render.draw_settings_menu(screen, 0, "Herdr config", "Glass")
    text = screen.text()
    assert "SETTINGS" in text
    assert "Controls" in text
    assert "Herdr config" in text
    assert "Target sound" in text
    assert "Glass" in text


def test_control_settings_show_modes_effective_bindings_and_warning():
    screen = FakeScreen()
    render.draw_control_settings(
        screen,
        0,
        "auto",
        "Herdr config",
        "/tmp/config.toml",
        (("pane move", "ctrl+b h / ctrl+b j"), ("space 1..9", "ctrl+b shift+1..9")),
        ("example warning",),
    )
    text = screen.text()
    assert "CONTROLS" in text
    assert "Automatic" in text
    assert "Herdrill defaults" in text
    assert "resolved: Herdr config" in text
    assert "/tmp/config.toml" in text
    assert "space 1..9" in text
    assert "example warning" in text


def test_settings_screen_lists_ten_varied_previewable_sounds():
    from herdrill.sound import SOUND_OPTIONS

    screen = FakeScreen()
    render.draw_settings(screen, SOUND_OPTIONS, 0, "tink", True)
    text = screen.text()
    assert "SETTINGS" in text
    assert "Tink" in text
    assert "Ping" in text
    assert "Basso" in text
    assert "select + preview" in text
    assert "m mute" in text
