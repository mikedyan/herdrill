"""Target-box placement rules."""

from __future__ import annotations

import random

from .board import Board


def place_target(
    board: Board,
    rng: random.Random,
    *,
    tier_changed: bool = False,
) -> str:
    """Choose a target pane that is not the currently focused pane.

    The first target after a larger board appears is forced into another space,
    making the tier transition a genuine workspace-navigation drill.
    """
    focused = board.focused_pane_id
    candidates = [pane_id for pane_id in board.pane_ids() if pane_id != focused]

    if tier_changed and len(board.spaces) > 1:
        origin_space = board.locate(focused)[0]
        distant = [
            pane_id
            for pane_id in candidates
            if board.locate(pane_id)[0] != origin_space
        ]
        if distant:
            candidates = distant

    if not candidates:
        raise ValueError("a target requires at least two board panes")
    return rng.choice(candidates)
