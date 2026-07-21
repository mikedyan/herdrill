"""Curses renderer for the herdr-shaped jump board."""

from __future__ import annotations

import curses

from .board import Rect, compute
from .round import Round

MIN_WIDTH = 48
MIN_HEIGHT = 15

PAIR_FOCUS = 1
PAIR_TARGET = 2
PAIR_ACTIVE = 3
PAIR_DIM = 4

PREFIX_CHIP = " PREFIX "
TARGET_GLYPH = "■"
FOCUS_GLYPH = "◆"


def init_colors() -> None:
    if not curses.has_colors():
        return
    try:
        curses.start_color()
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK
        curses.init_pair(PAIR_FOCUS, curses.COLOR_CYAN, background)
        curses.init_pair(PAIR_TARGET, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(PAIR_ACTIVE, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(PAIR_DIM, curses.COLOR_WHITE, background)
    except (curses.error, ValueError):
        # A game with no colour is better than a game that cannot start.
        pass


def pair(number: int) -> int:
    try:
        return curses.color_pair(number)
    except curses.error:
        return 0


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8", "replace"))


def put(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
    """Draw clipped text without splitting a multibyte border glyph."""
    height, width = stdscr.getmaxyx()
    if not 0 <= y < height or x >= width:
        return
    if x < 0:
        text = text[-x:]
        x = 0
    room = width - x - 1
    if room <= 0:
        return
    text = text[:room]
    if not text:
        return
    try:
        stdscr.addnstr(y, x, text, _byte_len(text), attr)
    except curses.error:
        pass


def sidebar_width(screen_width: int) -> int:
    return min(24, max(18, screen_width // 5))


def pane_area(screen_width: int, screen_height: int) -> Rect:
    left = sidebar_width(screen_width) + 1
    return Rect(left, 2, max(0, screen_width - left - 1), max(0, screen_height - 3))


def draw_too_small(stdscr, *, present: bool = True) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    message = f"herdr-jump needs {MIN_WIDTH}x{MIN_HEIGHT} · now {width}x{height}"
    put(stdscr, height // 2, max(0, (width - len(message)) // 2), message)
    if present:
        stdscr.refresh()


def draw(
    stdscr,
    game_round: Round,
    now: float,
    *,
    prefix_armed: bool = False,
    present: bool = True,
) -> None:
    height, width = stdscr.getmaxyx()
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        draw_too_small(stdscr, present=present)
        return

    stdscr.erase()
    _draw_sidebar(stdscr, game_round, height, width)
    _draw_tabs(stdscr, game_round, width)
    _draw_panes(stdscr, game_round, width, height)
    _draw_status(stdscr, game_round, now, width, height, prefix_armed)
    if present:
        stdscr.refresh()


def _draw_sidebar(stdscr, game_round: Round, height: int, width: int) -> None:
    board = game_round.board
    target_location = board.locate(game_round.target_pane_id)
    target_space = target_location[0] if target_location is not None else -1
    sw = sidebar_width(width)

    put(stdscr, 0, 1, "spaces", curses.A_BOLD)
    put(stdscr, 1, 0, "─" * sw, curses.A_DIM)
    for index, space in enumerate(board.spaces):
        row = index + 2
        if row >= height - 1:
            break
        active = index == board.active_space
        target = index == target_space
        marker = ("▸" if active else " ") + (TARGET_GLYPH if target else " ")
        text = f"{marker} {index + 1} {space.name}"
        attr = curses.A_BOLD if active else curses.A_DIM
        if target:
            attr |= pair(PAIR_TARGET) | curses.A_BOLD
        put(stdscr, row, 1, text[: sw - 2], attr)

    hint_row = min(height - 3, len(board.spaces) + 4)
    put(stdscr, hint_row, 1, f"tier {game_round.tier.number + 1}", curses.A_DIM)
    for row in range(height - 1):
        put(stdscr, row, sw, "│", curses.A_DIM)


def _draw_tabs(stdscr, game_round: Round, width: int) -> None:
    board = game_round.board
    space = board.current_space
    target_location = board.locate(game_round.target_pane_id)
    target_in_space = target_location is not None and target_location[0] == board.active_space
    target_tab = target_location[1] if target_in_space else -1
    x = sidebar_width(width) + 2

    for index, tab in enumerate(space.tabs):
        active = index == space.active_tab
        target = index == target_tab
        active_mark = "▸" if active else " "
        target_mark = TARGET_GLYPH if target else " "
        label = f" {active_mark}{target_mark}{index + 1}:{tab.name} "
        attr = curses.A_BOLD if active else curses.A_DIM
        if target:
            attr |= pair(PAIR_TARGET) | curses.A_BOLD
        put(stdscr, 0, x, label, attr)
        x += len(label) + 1
        if x >= width - 4:
            break

    left = sidebar_width(width) + 1
    put(stdscr, 1, left, "─" * max(0, width - left - 1), curses.A_DIM)


def _draw_panes(stdscr, game_round: Round, width: int, height: int) -> None:
    board = game_round.board
    rects = compute(board.current_tab.root, pane_area(width, height))
    for pane_id, rect in rects.items():
        _draw_pane(
            stdscr,
            rect,
            pane_id,
            focused=pane_id == board.focused_pane_id,
            target=pane_id == game_round.target_pane_id,
        )


def _draw_pane(
    stdscr,
    rect: Rect,
    pane_id: str,
    *,
    focused: bool,
    target: bool,
) -> None:
    if rect.w < 2 or rect.h < 2:
        return
    attr = (pair(PAIR_FOCUS) | curses.A_BOLD) if focused else curses.A_DIM
    title_marker = FOCUS_GLYPH if focused else "·"
    target_marker = f" {TARGET_GLYPH} BOX" if target else ""
    title = f" {title_marker} {pane_id}{target_marker} "
    inner = max(0, rect.w - 2)
    title = title[:inner]
    top_fill = max(0, inner - len(title))

    put(stdscr, rect.y, rect.x, "╭" + title + "─" * top_fill + "╮", attr)
    for row in range(rect.y + 1, rect.y + rect.h - 1):
        put(stdscr, row, rect.x, "│", attr)
        put(stdscr, row, rect.x + rect.w - 1, "│", attr)
    put(stdscr, rect.y + rect.h - 1, rect.x, "╰" + "─" * inner + "╯", attr)

    if target:
        _draw_box(stdscr, rect)


def _draw_box(stdscr, rect: Rect) -> None:
    """Paint a high-contrast, text-visible filled box in the target pane."""
    available_w = rect.w - 4
    available_h = rect.h - 2
    if available_w < 3 or available_h < 1:
        return
    box_w = min(13, available_w)
    box_h = min(5, max(1, available_h - 1))
    x = rect.x + (rect.w - box_w) // 2
    y = rect.y + (rect.h - box_h) // 2
    attr = pair(PAIR_TARGET) | curses.A_BOLD | curses.A_REVERSE

    for offset in range(box_h):
        if offset == box_h // 2 and box_w >= 5:
            label = " BOX "
            left = (box_w - len(label)) // 2
            line = TARGET_GLYPH * left + label + TARGET_GLYPH * (box_w - left - len(label))
        else:
            line = TARGET_GLYPH * box_w
        put(stdscr, y + offset, x, line, attr)


def _draw_status(
    stdscr,
    game_round: Round,
    now: float,
    width: int,
    height: int,
    prefix_armed: bool,
) -> None:
    status = (
        f" {game_round.remaining(now):04.1f}s  "
        f"score {game_round.score}  best {game_round.displayed_best} "
    )
    put(stdscr, height - 1, 0, " " * (width - 1), curses.A_REVERSE)
    put(stdscr, height - 1, 0, status, curses.A_REVERSE | curses.A_BOLD)
    if prefix_armed:
        put(stdscr, height - 1, min(len(status) + 1, width - 10), PREFIX_CHIP, pair(PAIR_ACTIVE) | curses.A_BOLD)
    hint = "esc quit"
    put(stdscr, height - 1, max(0, width - len(hint) - 2), hint, curses.A_REVERSE)


def draw_end(stdscr, score: int, best: int, *, present: bool = True) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    lines = (
        "HERDR-JUMP",
        f"{score} boxes cleared",
        f"best {best}",
        "any key · new round",
        "q / esc · quit",
    )
    start = max(1, height // 2 - len(lines) // 2)
    for offset, line in enumerate(lines):
        attr = curses.A_BOLD if offset < 3 else curses.A_DIM
        put(stdscr, start + offset, max(0, (width - len(line)) // 2), line, attr)
    if present:
        stdscr.refresh()
