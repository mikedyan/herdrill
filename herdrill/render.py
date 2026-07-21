"""Curses renderer for the Herdr-shaped jump board."""

from __future__ import annotations

import curses

from .board import Rect, compute
from .leaderboard import Record, top_records
from .round import Round
from .sound import SoundOption

MIN_WIDTH = 48
MIN_HEIGHT = 15

PAIR_FOCUS = 1
PAIR_TARGET = 2
PAIR_ACTIVE = 3
PAIR_DIM = 4
PAIR_BRIGHT = 5
PAIR_RAIL = 6
PAIR_TARGET_RAIL = 7
PAIR_TARGET_ACTIVE = 8
PAIR_BORDER_DIM = 9

PREFIX_CHIP = " PREFIX "
TARGET_GLYPH = "◆"
_COLOR_ENABLED = False


def init_colors() -> None:
    """Install a muted Herdr-like palette, with an eight-colour fallback."""
    global _COLOR_ENABLED
    _COLOR_ENABLED = False
    if not curses.has_colors():
        return
    try:
        curses.start_color()
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK

        if getattr(curses, "COLORS", 0) >= 256:
            dark, rail = 234, 233
            blue, red, red_on_blue = 75, 211, 124
            muted, border_dim, bright = 146, 60, 255
        else:
            dark, rail = curses.COLOR_BLACK, curses.COLOR_BLACK
            blue, red, red_on_blue = (
                curses.COLOR_CYAN,
                curses.COLOR_RED,
                curses.COLOR_RED,
            )
            muted, border_dim, bright = (
                curses.COLOR_WHITE,
                curses.COLOR_BLUE,
                curses.COLOR_WHITE,
            )

        curses.init_pair(PAIR_FOCUS, blue, background)
        curses.init_pair(PAIR_TARGET, red, background)
        curses.init_pair(PAIR_ACTIVE, dark, blue)
        curses.init_pair(PAIR_DIM, muted, background)
        curses.init_pair(PAIR_BRIGHT, bright, background)
        curses.init_pair(PAIR_RAIL, muted, rail)
        curses.init_pair(PAIR_TARGET_RAIL, red, rail)
        curses.init_pair(PAIR_TARGET_ACTIVE, red_on_blue, blue)
        curses.init_pair(PAIR_BORDER_DIM, border_dim, background)
        _COLOR_ENABLED = True
    except (curses.error, ValueError):
        # A game with no colour is better than a game that cannot start.
        pass


def pair(number: int) -> int:
    try:
        return curses.color_pair(number)
    except curses.error:
        return 0


def _active_attr() -> int:
    attr = pair(PAIR_ACTIVE) | curses.A_BOLD
    return attr if _COLOR_ENABLED else attr | curses.A_REVERSE


def _target_attr(*, on_rail: bool = False, on_active: bool = False) -> int:
    number = (
        PAIR_TARGET_ACTIVE
        if on_active
        else PAIR_TARGET_RAIL
        if on_rail
        else PAIR_TARGET
    )
    attr = pair(number) | curses.A_BOLD
    return attr if _COLOR_ENABLED else attr | curses.A_UNDERLINE


def _inactive_attr(*, on_rail: bool = False) -> int:
    number = PAIR_RAIL if on_rail else PAIR_DIM
    return pair(number) | curses.A_DIM


def _bright_attr() -> int:
    return pair(PAIR_BRIGHT) | curses.A_BOLD


def _navigation_attr(*, active: bool, target: bool, on_rail: bool = False) -> int:
    """Choose one state; highlighted elements must never inherit A_DIM."""
    if active:
        return _active_attr()
    if target:
        return _target_attr(on_rail=on_rail)
    return _inactive_attr(on_rail=on_rail)


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8", "replace"))


def put(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
    """Draw clipped text without splitting a multibyte glyph."""
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


_ACS_FALLBACKS = {
    "ACS_HLINE": "─",
    "ACS_VLINE": "│",
    "ACS_ULCORNER": "┌",
    "ACS_URCORNER": "┐",
    "ACS_LLCORNER": "└",
    "ACS_LRCORNER": "┘",
}


def _acs(name: str):
    """Use terminfo's native line glyph, falling back to Unicode in tests."""
    return getattr(curses, name, _ACS_FALLBACKS[name])


def _put_line_cell(stdscr, y: int, x: int, name: str, attr: int) -> None:
    height, width = stdscr.getmaxyx()
    if not 0 <= y < height or not 0 <= x < width - 1:
        return
    try:
        stdscr.addch(y, x, _acs(name), attr)
    except (AttributeError, curses.error, TypeError):
        put(stdscr, y, x, _ACS_FALLBACKS[name], attr)


def _draw_hline(stdscr, y: int, x: int, length: int, attr: int) -> None:
    height, width = stdscr.getmaxyx()
    if not 0 <= y < height or length <= 0:
        return
    if x < 0:
        length += x
        x = 0
    length = min(length, width - x - 1)
    if length <= 0:
        return
    try:
        stdscr.hline(y, x, _acs("ACS_HLINE"), length, attr)
    except (AttributeError, curses.error, TypeError):
        put(stdscr, y, x, _ACS_FALLBACKS["ACS_HLINE"] * length, attr)


def _draw_vline(stdscr, y: int, x: int, length: int, attr: int) -> None:
    height, width = stdscr.getmaxyx()
    if not 0 <= x < width - 1 or length <= 0:
        return
    if y < 0:
        length += y
        y = 0
    length = min(length, height - y)
    if length <= 0:
        return
    try:
        stdscr.vline(y, x, _acs("ACS_VLINE"), length, attr)
    except (AttributeError, curses.error, TypeError):
        for row in range(y, y + length):
            put(stdscr, row, x, _ACS_FALLBACKS["ACS_VLINE"], attr)


def _draw_border(stdscr, rect: Rect, attr: int) -> None:
    """Draw a terminal-native continuous plain border around ``rect``."""
    if rect.w < 2 or rect.h < 2:
        return
    right = rect.x + rect.w - 1
    bottom = rect.y + rect.h - 1
    _put_line_cell(stdscr, rect.y, rect.x, "ACS_ULCORNER", attr)
    _put_line_cell(stdscr, rect.y, right, "ACS_URCORNER", attr)
    _put_line_cell(stdscr, bottom, rect.x, "ACS_LLCORNER", attr)
    _put_line_cell(stdscr, bottom, right, "ACS_LRCORNER", attr)
    _draw_hline(stdscr, rect.y, rect.x + 1, rect.w - 2, attr)
    _draw_hline(stdscr, bottom, rect.x + 1, rect.w - 2, attr)
    _draw_vline(stdscr, rect.y + 1, rect.x, rect.h - 2, attr)
    _draw_vline(stdscr, rect.y + 1, right, rect.h - 2, attr)


def sidebar_width(screen_width: int) -> int:
    return min(24, max(18, screen_width // 5))


def pane_area(screen_width: int, screen_height: int) -> Rect:
    left = sidebar_width(screen_width) + 1
    return Rect(left, 2, max(0, screen_width - left - 1), max(0, screen_height - 3))


def draw_too_small(stdscr, *, present: bool = True) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    message = f"Herdrill needs {MIN_WIDTH}x{MIN_HEIGHT} · now {width}x{height}"
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

    put(stdscr, 0, 1, "spaces", _bright_attr())
    legend = f"{TARGET_GLYPH} target"
    put(stdscr, 0, max(8, sw - len(legend) - 1), legend, _target_attr())
    _draw_hline(stdscr, 1, 0, sw, pair(PAIR_BORDER_DIM))
    row_width = max(0, sw - 2)
    for index, space in enumerate(board.spaces):
        row = index + 2
        if row >= height - 1:
            break
        active = index == board.active_space
        target = index == target_space
        marker = TARGET_GLYPH if target else ("▸" if active else " ")
        text = f"{marker} {index + 1} {space.name}"
        attr = _navigation_attr(active=active, target=target)
        if active:
            put(stdscr, row, 1, " " * row_width, attr)
        put(stdscr, row, 1, text[:row_width], attr)
        if target:
            put(stdscr, row, 1, TARGET_GLYPH, _target_attr(on_active=active))

    hint_row = min(height - 3, len(board.spaces) + 4)
    put(stdscr, hint_row, 1, f"tier {game_round.tier.number + 1}", _inactive_attr())
    _draw_vline(stdscr, 0, sw, height - 1, pair(PAIR_BORDER_DIM))


def _draw_tabs(stdscr, game_round: Round, width: int) -> None:
    board = game_round.board
    space = board.current_space
    target_location = board.locate(game_round.target_pane_id)
    target_in_space = target_location is not None and target_location[0] == board.active_space
    target_tab = target_location[1] if target_in_space else -1
    left = sidebar_width(width) + 1
    put(stdscr, 0, left, " " * max(0, width - left - 1), pair(PAIR_RAIL))
    x = left + 1

    for index, _tab in enumerate(space.tabs):
        active = index == space.active_tab
        target = index == target_tab
        marker = f"{TARGET_GLYPH} " if target else ""
        label = f" {marker}{index + 1} "
        attr = _navigation_attr(active=active, target=target, on_rail=True)
        put(stdscr, 0, x, label, attr)
        if target:
            put(stdscr, 0, x + 1, TARGET_GLYPH, _target_attr(on_active=active))
        x += len(label) + 1
        if x >= width - 4:
            break

    _draw_hline(stdscr, 1, left, max(0, width - left - 1), pair(PAIR_BORDER_DIM))


def _draw_panes(stdscr, game_round: Round, width: int, height: int) -> None:
    board = game_round.board
    rects = compute(board.current_tab.root, pane_area(width, height))
    for pane_id, rect in rects.items():
        _draw_pane(
            stdscr,
            rect,
            focused=pane_id == board.focused_pane_id,
            target=pane_id == game_round.target_pane_id,
        )


def _draw_pane(
    stdscr,
    rect: Rect,
    *,
    focused: bool,
    target: bool,
) -> None:
    """Draw an otherwise empty pane; focus is carried entirely by its border."""
    if rect.w < 2 or rect.h < 2:
        return
    # Herdr uses Ratatui's plain line set with colour—but no bold/dim font
    # modifier—on structural borders. Do the same through ncurses' ACS layer.
    attr = pair(PAIR_FOCUS) if focused else pair(PAIR_BORDER_DIM)
    _draw_border(stdscr, rect, attr)

    if target:
        _draw_box(stdscr, rect)


def _draw_box(stdscr, rect: Rect) -> None:
    """Draw a light target card that remains recognizable in small panes."""
    available_w = rect.w - 4
    available_h = rect.h - 2
    marker_attr = _target_attr()
    border_attr = pair(PAIR_TARGET)

    if available_w < 9 or available_h < 3:
        put(
            stdscr,
            rect.y + rect.h // 2,
            rect.x + rect.w // 2,
            TARGET_GLYPH,
            marker_attr,
        )
        return

    if available_w < 11 or available_h < 4:
        box_w, box_h = 9, 3
        x = rect.x + (rect.w - box_w) // 2
        y = rect.y + (rect.h - box_h) // 2
        _draw_border(stdscr, Rect(x, y, box_w, box_h), border_attr)
        put(stdscr, y + 1, x + 4, TARGET_GLYPH, marker_attr)
        return

    box_w, box_h = 11, 4
    x = rect.x + (rect.w - box_w) // 2
    y = rect.y + (rect.h - box_h) // 2
    _draw_border(stdscr, Rect(x, y, box_w, box_h), border_attr)
    put(stdscr, y + 1, x + 5, TARGET_GLYPH, marker_attr)
    put(stdscr, y + 2, x + (box_w - len("TARGET")) // 2, "TARGET", _bright_attr())


def _draw_status(
    stdscr,
    game_round: Round,
    now: float,
    width: int,
    height: int,
    prefix_armed: bool,
) -> None:
    timer = f" {game_round.remaining(now):04.1f}s "
    score = f" score {game_round.score} "
    best = f" best {game_round.displayed_best} "
    put(stdscr, height - 1, 0, timer, pair(PAIR_FOCUS) | curses.A_BOLD)
    put(stdscr, height - 1, len(timer), score, _bright_attr())
    put(stdscr, height - 1, len(timer) + len(score), best, _inactive_attr())
    status_width = len(timer) + len(score) + len(best)
    if prefix_armed:
        put(stdscr, height - 1, min(status_width + 1, width - 10), PREFIX_CHIP, _active_attr())
    hint = "esc quit"
    put(stdscr, height - 1, max(0, width - len(hint) - 2), hint, _inactive_attr())


def _centered_x(width: int, text: str) -> int:
    return max(0, (width - len(text)) // 2)


def _leaderboard_rect(width: int, height: int, y: int) -> Rect:
    panel_width = min(60, max(42, width - 6))
    panel_height = min(13, max(4, height - y - 3))
    return Rect(max(0, (width - panel_width) // 2), y, panel_width, panel_height)


def _draw_leaderboard(
    stdscr,
    records: list[Record],
    rect: Rect,
    *,
    highlighted: Record | None = None,
) -> None:
    _draw_border(stdscr, rect, pair(PAIR_BORDER_DIM))
    put(stdscr, rect.y, rect.x + 2, " Herdrill leaderboard ", _bright_attr())
    if rect.h < 4:
        return

    inner_width = rect.w - 2
    name_width = min(16, max(5, inner_width - 32))
    header = f"  #  {'name':<{name_width}} {'score':>5}  recorded at"
    put(stdscr, rect.y + 1, rect.x + 1, header[:inner_width], _inactive_attr())

    visible = top_records(records)[: max(0, rect.h - 3)]
    if not visible:
        message = "no scores yet"
        put(
            stdscr,
            rect.y + 2,
            rect.x + max(1, (rect.w - len(message)) // 2),
            message,
            _inactive_attr(),
        )
        return

    for rank, record in enumerate(visible, 1):
        line = (
            f" {rank:>2}  {record.name[:name_width]:<{name_width}} "
            f"{record.score:>5}  {record.timestamp}"
        )
        attr = _target_attr() if record == highlighted else _bright_attr()
        put(stdscr, rect.y + rank + 1, rect.x + 1, line[:inner_width], attr)


def _draw_screen_title(stdscr, y: int, width: int, title: str) -> None:
    x = _centered_x(width, title)
    put(stdscr, y, x, title, pair(PAIR_FOCUS) | curses.A_BOLD)
    if x >= 2:
        put(stdscr, y, x - 2, TARGET_GLYPH, _target_attr())


def draw_start(
    stdscr,
    records: list[Record],
    sound_label: str = "Tink",
    controls_label: str = "Herdrill defaults",
    *,
    present: bool = True,
) -> None:
    height, width = stdscr.getmaxyx()
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        draw_too_small(stdscr, present=present)
        return

    stdscr.erase()
    _draw_screen_title(stdscr, 1, width, "HERDRILL")
    subtitle = "60 seconds · navigate to every target"
    put(stdscr, 2, _centered_x(width, subtitle), subtitle, _inactive_attr())
    panel = _leaderboard_rect(width, height, 4)
    _draw_leaderboard(stdscr, records, panel)
    start = "enter / space start · s settings"
    quit_hint = f"q / esc quit · sound {sound_label} · controls {controls_label}"
    put(stdscr, panel.bottom, _centered_x(width, start), start, _bright_attr())
    put(stdscr, panel.bottom + 1, _centered_x(width, quit_hint), quit_hint, _inactive_attr())
    if present:
        stdscr.refresh()


def draw_settings_menu(
    stdscr,
    selected: int,
    controls_label: str,
    sound_label: str,
    *,
    present: bool = True,
) -> None:
    height, width = stdscr.getmaxyx()
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        draw_too_small(stdscr, present=present)
        return

    stdscr.erase()
    _draw_screen_title(stdscr, 1, width, "SETTINGS")
    subtitle = "controls and target feedback"
    put(stdscr, 2, _centered_x(width, subtitle), subtitle, _inactive_attr())

    panel_width = min(70, width - 6)
    panel = Rect((width - panel_width) // 2, 5, panel_width, 4)
    _draw_border(stdscr, panel, pair(PAIR_BORDER_DIM))
    rows = (("Controls", controls_label), ("Target sound", sound_label))
    for offset, (name, value) in enumerate(rows, 1):
        active = selected == offset - 1
        attr = _active_attr() if active else _bright_attr()
        if active:
            put(stdscr, panel.y + offset, panel.x + 1, " " * (panel.w - 2), attr)
        marker = TARGET_GLYPH if active else " "
        text = f" {marker} {name:<14} {value}"
        put(stdscr, panel.y + offset, panel.x + 1, text[: panel.w - 2], attr)
        if active:
            put(
                stdscr,
                panel.y + offset,
                panel.x + 2,
                TARGET_GLYPH,
                _target_attr(on_active=True),
            )

    hint = "↑/↓ or j/k choose · enter open · q / esc back"
    put(stdscr, panel.bottom + 2, _centered_x(width, hint), hint, _inactive_attr())
    if present:
        stdscr.refresh()


def draw_control_settings(
    stdscr,
    selected: int,
    active_mode: str,
    source_label: str,
    config_path: str | None,
    rows: tuple[tuple[str, str], ...],
    warnings: tuple[str, ...],
    *,
    present: bool = True,
) -> None:
    height, width = stdscr.getmaxyx()
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        draw_too_small(stdscr, present=present)
        return

    stdscr.erase()
    _draw_screen_title(stdscr, 1, width, "CONTROLS")
    subtitle = "use Herdr automatically or the built-in Herdrill layout"
    put(stdscr, 2, _centered_x(width, subtitle), subtitle, _inactive_attr())

    panel_width = min(82, width - 4)
    panel_height = min(height - 7, 12)
    panel = Rect((width - panel_width) // 2, 4, panel_width, panel_height)
    _draw_border(stdscr, panel, pair(PAIR_BORDER_DIM))
    options = (
        ("auto", "Automatic — use Herdr when available"),
        ("herdrill", "Herdrill defaults"),
    )
    row_width = panel.w - 2
    row = panel.y + 1
    for index, (mode, label) in enumerate(options):
        highlighted = selected == index
        attr = _active_attr() if highlighted else _bright_attr()
        if highlighted:
            put(stdscr, row, panel.x + 1, " " * row_width, attr)
        active = TARGET_GLYPH if mode == active_mode else " "
        text = f" {active} {label}"
        put(stdscr, row, panel.x + 1, text[:row_width], attr)
        if mode == active_mode:
            put(
                stdscr,
                row,
                panel.x + 2,
                TARGET_GLYPH,
                _target_attr(on_active=highlighted),
            )
        row += 1

    source = f"resolved: {source_label}"
    put(stdscr, row, panel.x + 2, source[: panel.w - 4], _target_attr())
    row += 1
    if config_path and row < panel.bottom:
        path_line = f"config: {config_path}"
        put(stdscr, row, panel.x + 2, path_line[: panel.w - 4], _inactive_attr())
        row += 1

    for name, value in rows:
        if row >= panel.bottom:
            break
        text = f"{name:<16} {value}"
        put(stdscr, row, panel.x + 2, text[: panel.w - 4], _bright_attr())
        row += 1

    footer = panel.bottom + 1
    if warnings and footer <= height - 2:
        more = f" (+{len(warnings) - 1} more)" if len(warnings) > 1 else ""
        warning = f"warning: {warnings[0]}{more}"
        put(stdscr, footer, _centered_x(width, warning), warning, _target_attr())
        footer += 1
    if footer <= height - 2:
        hint = "↑/↓ choose · enter apply · r reload · q / esc back"
        put(stdscr, footer, _centered_x(width, hint), hint, _inactive_attr())
    if present:
        stdscr.refresh()


def draw_settings(
    stdscr,
    options: tuple[SoundOption, ...],
    selected: int,
    active_sound: str,
    sound_available: bool,
    *,
    present: bool = True,
) -> None:
    height, width = stdscr.getmaxyx()
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        draw_too_small(stdscr, present=present)
        return

    stdscr.erase()
    _draw_screen_title(stdscr, 1, width, "SETTINGS")
    subtitle = "choose the sound played when a target is cleared"
    put(stdscr, 2, _centered_x(width, subtitle), subtitle, _inactive_attr())

    panel_width = min(70, width - 4)
    panel_height = min(len(options) + 2, max(4, height - 8))
    panel = Rect((width - panel_width) // 2, 4, panel_width, panel_height)
    capacity = max(1, panel.h - 2)
    offset = min(max(0, selected - capacity + 1), max(0, len(options) - capacity))
    end = min(len(options), offset + capacity)
    _draw_border(stdscr, panel, pair(PAIR_BORDER_DIM))
    title = f" target sounds {offset + 1}-{end}/{len(options)} "
    put(stdscr, panel.y, panel.x + 2, title, _bright_attr())

    row_width = panel.w - 2
    for row, index in enumerate(range(offset, end), panel.y + 1):
        option = options[index]
        active = option.id == active_sound
        marker = TARGET_GLYPH if active else " "
        shortcut = "0" if index == 9 else str(index + 1)
        text = f" {marker} {shortcut}  {option.name:<10} {option.description}"
        is_selected = index == selected
        attr = _active_attr() if is_selected else _bright_attr() if active else _inactive_attr()
        if is_selected:
            put(stdscr, row, panel.x + 1, " " * row_width, attr)
        put(stdscr, row, panel.x + 1, text[:row_width], attr)
        if active:
            put(
                stdscr,
                row,
                panel.x + 2,
                TARGET_GLYPH,
                _target_attr(on_active=is_selected),
            )

    active_label = next(
        (option.name for option in options if option.id == active_sound),
        "Muted",
    )
    status = f"active: {active_label}"
    if not sound_available:
        status += " · playback unavailable"
    footer = min(height - 3, panel.bottom + 1)
    put(stdscr, footer, _centered_x(width, status), status, _target_attr())
    if width >= 70:
        hint = "↑/↓ or j/k choose · enter/space select + preview · m mute"
        back = "1-9/0 quick select · q / esc back"
    else:
        hint = "↑/↓ choose · enter preview · m mute"
        back = "1-9/0 select · esc back"
    put(stdscr, footer + 1, _centered_x(width, hint), hint, _bright_attr())
    put(stdscr, footer + 2, _centered_x(width, back), back, _inactive_attr())
    if present:
        stdscr.refresh()


def draw_name_entry(
    stdscr,
    score: int,
    best: int,
    name: str,
    recorded_at: str,
    *,
    present: bool = True,
) -> None:
    height, width = stdscr.getmaxyx()
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        draw_too_small(stdscr, present=present)
        return

    stdscr.erase()
    _draw_screen_title(stdscr, 1, width, "ROUND COMPLETE")
    result = f"{score} targets cleared"
    put(stdscr, 3, _centered_x(width, result), result, _bright_attr())
    if score > best:
        badge = "NEW BEST"
        put(stdscr, 4, _centered_x(width, badge), badge, _target_attr())
    else:
        best_line = f"best {best}"
        put(stdscr, 4, _centered_x(width, best_line), best_line, _inactive_attr())

    box_width = min(42, width - 6)
    box = Rect((width - box_width) // 2, 6, box_width, 3)
    _draw_border(stdscr, box, pair(PAIR_TARGET))
    put(stdscr, box.y, box.x + 2, " enter name ", _target_attr())
    prompt = f"> {name}"
    put(stdscr, box.y + 1, box.x + 2, prompt[: box.w - 5], _bright_attr())
    cursor_x = min(box.x + 2 + len(prompt), box.right - 2)
    put(stdscr, box.y + 1, cursor_x, "▏", _target_attr())

    date_line = f"recorded {recorded_at}"
    put(stdscr, 10, _centered_x(width, date_line), date_line, _inactive_attr())
    hint = "enter save · backspace edit · esc quit"
    put(stdscr, height - 2, _centered_x(width, hint), hint, _inactive_attr())
    if present:
        stdscr.refresh()


def draw_end(
    stdscr,
    score: int,
    records: list[Record],
    current: Record,
    *,
    present: bool = True,
) -> None:
    height, width = stdscr.getmaxyx()
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        draw_too_small(stdscr, present=present)
        return

    stdscr.erase()
    _draw_screen_title(stdscr, 1, width, "SCORE SAVED")
    summary = f"{current.name} · {score} targets · {current.timestamp}"
    put(stdscr, 2, _centered_x(width, summary), summary, _bright_attr())
    panel = _leaderboard_rect(width, height, 4)
    _draw_leaderboard(stdscr, records, panel, highlighted=current)
    again = "press any key to return to start"
    quit_hint = "q / esc quit"
    put(stdscr, panel.bottom, _centered_x(width, again), again, _bright_attr())
    put(stdscr, panel.bottom + 1, _centered_x(width, quit_hint), quit_hint, _inactive_attr())
    if present:
        stdscr.refresh()
