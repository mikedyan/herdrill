"""Pure board model and split-tree geometry for Herdrill."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


@dataclass(frozen=True)
class Pane:
    id: str


@dataclass(frozen=True)
class Leaf:
    pane: Pane


@dataclass(frozen=True)
class Split:
    """A binary split. ``v`` is side-by-side and ``h`` is stacked."""

    direction: Literal["v", "h"]
    ratio: float
    first: Node
    second: Node


Node = Leaf | Split


def iter_panes(node: Node) -> Iterator[Pane]:
    """Yield panes in stable top/left-first tree order."""
    if isinstance(node, Leaf):
        yield node.pane
        return
    yield from iter_panes(node.first)
    yield from iter_panes(node.second)


@dataclass
class Tab:
    id: str
    name: str
    root: Node
    focused_pane_id: str = ""

    def __post_init__(self) -> None:
        panes = list(iter_panes(self.root))
        if not panes:
            raise ValueError("a tab must contain at least one pane")
        ids = {pane.id for pane in panes}
        if not self.focused_pane_id:
            self.focused_pane_id = panes[0].id
        elif self.focused_pane_id not in ids:
            raise ValueError("focused pane must belong to its tab")

    def panes(self) -> list[Pane]:
        return list(iter_panes(self.root))


@dataclass
class Space:
    id: str
    name: str
    tabs: list[Tab]
    active_tab: int = 0

    def __post_init__(self) -> None:
        if not self.tabs:
            raise ValueError("a space must contain at least one tab")
        if not 0 <= self.active_tab < len(self.tabs):
            raise ValueError("active tab is out of range")


@dataclass
class Board:
    spaces: list[Space]
    active_space: int = 0

    def __post_init__(self) -> None:
        if not self.spaces:
            raise ValueError("a board must contain at least one space")
        if not 0 <= self.active_space < len(self.spaces):
            raise ValueError("active space is out of range")
        ids = [pane.id for pane in self.iter_panes()]
        if len(ids) != len(set(ids)):
            raise ValueError("pane ids must be unique")

    @property
    def current_space(self) -> Space:
        return self.spaces[self.active_space]

    @property
    def current_tab(self) -> Tab:
        space = self.current_space
        return space.tabs[space.active_tab]

    @property
    def focused_pane_id(self) -> str:
        return self.current_tab.focused_pane_id

    @property
    def origin_pane_id(self) -> str:
        return self.spaces[0].tabs[0].panes()[0].id

    def iter_panes(self) -> Iterator[Pane]:
        for space in self.spaces:
            for tab in space.tabs:
                yield from iter_panes(tab.root)

    def pane_ids(self) -> list[str]:
        return [pane.id for pane in self.iter_panes()]

    def locate(self, pane_id: str) -> tuple[int, int, int] | None:
        """Return ``(space, tab, pane)`` indexes for a pane id."""
        for space_index, space in enumerate(self.spaces):
            for tab_index, tab in enumerate(space.tabs):
                for pane_index, pane in enumerate(iter_panes(tab.root)):
                    if pane.id == pane_id:
                        return space_index, tab_index, pane_index
        return None

    def reset_to_origin(self) -> None:
        self.active_space = 0
        self.spaces[0].active_tab = 0
        self.spaces[0].tabs[0].focused_pane_id = self.origin_pane_id

    def switch_workspace(self, index: int) -> bool:
        """Switch to a one-based space index, as Herdr's binding does."""
        wanted = index - 1
        if not 0 <= wanted < len(self.spaces):
            return False
        changed = wanted != self.active_space
        self.active_space = wanted
        return changed

    def previous_workspace(self) -> bool:
        if len(self.spaces) < 2:
            return False
        self.active_space = (self.active_space - 1) % len(self.spaces)
        return True

    def next_workspace(self) -> bool:
        if len(self.spaces) < 2:
            return False
        self.active_space = (self.active_space + 1) % len(self.spaces)
        return True

    def switch_tab(self, index: int) -> bool:
        """Switch to a one-based tab index in the active space."""
        wanted = index - 1
        space = self.current_space
        if not 0 <= wanted < len(space.tabs):
            return False
        changed = wanted != space.active_tab
        space.active_tab = wanted
        return changed

    def previous_tab(self) -> bool:
        space = self.current_space
        if len(space.tabs) < 2:
            return False
        space.active_tab = (space.active_tab - 1) % len(space.tabs)
        return True

    def next_tab(self) -> bool:
        space = self.current_space
        if len(space.tabs) < 2:
            return False
        space.active_tab = (space.active_tab + 1) % len(space.tabs)
        return True

    def cycle_pane_next(self) -> bool:
        return self._cycle_pane(1)

    def cycle_pane_previous(self) -> bool:
        return self._cycle_pane(-1)

    def _cycle_pane(self, step: int) -> bool:
        tab = self.current_tab
        panes = tab.panes()
        if len(panes) < 2:
            return False
        current = next(
            index for index, pane in enumerate(panes) if pane.id == tab.focused_pane_id
        )
        tab.focused_pane_id = panes[(current + step) % len(panes)].id
        return True

    def focus_direction(self, direction: Direction) -> bool:
        tab = self.current_tab
        rects = compute(tab.root, NAVIGATION_RECT)
        target = directional_neighbor(rects, tab.focused_pane_id, direction)
        if target is None:
            return False
        tab.focused_pane_id = target
        return True


# A fixed canvas keeps navigation pure and independent of the terminal. Split
# topology and shared edges determine reachability; this canvas merely gives
# those edges stable integer coordinates.
NAVIGATION_RECT = Rect(0, 0, 1200, 800)


def _cut(total: int, ratio: float) -> int:
    if total <= 1:
        return 0
    return min(max(1, int(total * ratio)), total - 1)


def compute(node: Node, rect: Rect) -> dict[str, Rect]:
    """Map each pane below ``node`` to its rectangle inside ``rect``."""
    if isinstance(node, Leaf):
        return {node.pane.id: rect}

    if node.direction == "v":
        first_size = _cut(rect.w, node.ratio)
        first = Rect(rect.x, rect.y, first_size, rect.h)
        second = Rect(rect.x + first_size, rect.y, rect.w - first_size, rect.h)
    else:
        first_size = _cut(rect.h, node.ratio)
        first = Rect(rect.x, rect.y, rect.w, first_size)
        second = Rect(rect.x, rect.y + first_size, rect.w, rect.h - first_size)

    result = compute(node.first, first)
    result.update(compute(node.second, second))
    return result


Direction = Literal["left", "down", "up", "right"]
_MOVES: dict[Direction, tuple[str, int]] = {
    "left": ("x", -1),
    "right": ("x", 1),
    "up": ("y", -1),
    "down": ("y", 1),
}


def _span(rect: Rect, axis: str) -> tuple[int, int]:
    return (rect.x, rect.right) if axis == "x" else (rect.y, rect.bottom)


def _overlap(first: tuple[int, int], second: tuple[int, int]) -> int:
    return max(0, min(first[1], second[1]) - max(first[0], second[0]))


def directional_neighbor(
    rects: dict[str, Rect], pane_id: str, direction: Direction
) -> str | None:
    """Find the nearest pane sharing an edge in ``direction``.

    Diagonal panes do not qualify. Equal-distance candidates prefer the one
    with the largest shared edge and then its stable pane id.
    """
    origin = rects.get(pane_id)
    move = _MOVES.get(direction)
    if origin is None or move is None:
        return None

    axis, step = move
    cross_axis = "y" if axis == "x" else "x"
    origin_axis = _span(origin, axis)
    origin_cross = _span(origin, cross_axis)
    best: tuple[int, int, str] | None = None

    for other_id, other in rects.items():
        if other_id == pane_id:
            continue
        low, high = _span(other, axis)
        distance = low - origin_axis[1] if step > 0 else origin_axis[0] - high
        if distance < 0:
            continue
        shared = _overlap(origin_cross, _span(other, cross_axis))
        if shared <= 0:
            continue
        candidate = (distance, -shared, other_id)
        if best is None or candidate < best:
            best = candidate

    return best[2] if best is not None else None
