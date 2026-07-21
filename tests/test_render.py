import random

from herdrill_chatgpt import render
from herdrill_chatgpt.round import Round


class FakeScreen:
    def __init__(self, width=100, height=30):
        self.width = width
        self.height = height
        self.erase()
        self.refreshed = 0

    def getmaxyx(self):
        return self.height, self.width

    def erase(self):
        self.cells = [[" " for _ in range(self.width)] for _ in range(self.height)]

    def addnstr(self, y, x, text, byte_count, attr=0):
        assert 0 <= y < self.height
        assert 0 <= x < self.width
        assert byte_count == len(text.encode("utf-8", "replace"))
        assert x + len(text) <= self.width
        for offset, char in enumerate(text):
            self.cells[y][x + offset] = char

    def refresh(self):
        self.refreshed += 1

    def text(self):
        return "\n".join("".join(row) for row in self.cells)


def test_frame_shows_focus_target_clock_score_and_best():
    screen = FakeScreen()
    game_round = Round(0.0, random.Random(1), best_score=7)
    render.draw(screen, game_round, 2.5, prefix_armed=True)
    text = screen.text()
    assert "╔" in text and "╗" in text
    assert "┏━━━━━━━┓" in text
    assert "┃███████┃" in text
    assert "■ target" in text
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
    assert any("┏━━━━━━━┓" in row for row in rows)
    assert any("┃███████┃" in row for row in rows)
    assert any("╔" in row and "╗" in row for row in rows)
    assert "s1:t1:p1" not in screen.text(), "internal pane ids leaked into the UI"
    assert "BOX" not in screen.text(), "the target should look like a box, not be labelled"


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


def test_end_screen_has_restart_and_quit_instructions():
    screen = FakeScreen()
    render.draw_end(screen, 14, 22)
    text = screen.text()
    assert "14 boxes cleared" in text
    assert "best 22" in text
    assert "any key" in text
    assert "q / esc" in text
