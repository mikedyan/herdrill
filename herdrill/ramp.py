"""Difficulty ramp and deterministic board generation."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .board import Board, Leaf, Node, Pane, Space, Split, Tab


@dataclass(frozen=True)
class Tier:
    number: int
    starts_at: int
    spaces: int
    min_tabs: int
    max_tabs: int
    min_panes: int
    max_panes: int
    nested: bool = False


TIERS = (
    Tier(0, 0, spaces=1, min_tabs=1, max_tabs=1, min_panes=2, max_panes=2),
    Tier(1, 5, spaces=2, min_tabs=1, max_tabs=2, min_panes=2, max_panes=3),
    Tier(
        2,
        10,
        spaces=3,
        min_tabs=1,
        max_tabs=2,
        min_panes=2,
        max_panes=3,
        nested=True,
    ),
    Tier(
        3,
        15,
        spaces=4,
        min_tabs=1,
        max_tabs=3,
        min_panes=3,
        max_panes=4,
        nested=True,
    ),
)


def tier_for(cleared: int) -> Tier:
    """Return the highest tier whose threshold has been reached."""
    cleared = max(0, cleared)
    return next(tier for tier in reversed(TIERS) if cleared >= tier.starts_at)


def _replace_leaf(node: Node, pane_id: str, replacement: Node) -> Node:
    if isinstance(node, Leaf):
        return replacement if node.pane.id == pane_id else node
    return Split(
        node.direction,
        node.ratio,
        _replace_leaf(node.first, pane_id, replacement),
        _replace_leaf(node.second, pane_id, replacement),
    )


def _build_tree(panes: list[Pane], rng: random.Random, tier: Tier) -> Node:
    """Build a reproducible split tree, adding one pane at a time."""
    root: Node = Leaf(panes[0])
    leaf_ids = [panes[0].id]

    for pane_number, pane in enumerate(panes[1:], start=1):
        split_id = rng.choice(leaf_ids)
        leaf_ids.append(pane.id)

        if tier.number == 0:
            direction = "v"
            ratio = 0.5
        else:
            # Alternation guarantees useful two-axis geometry in larger nested
            # boards while the random phase keeps different seeds distinct.
            phase = rng.randrange(2)
            direction = "v" if (pane_number + phase) % 2 else "h"
            ratio = rng.choice((0.42, 0.5, 0.58))

        replacement = Split(
            direction=direction,
            ratio=ratio,
            first=Leaf(Pane(split_id)),
            second=Leaf(pane),
        )
        root = _replace_leaf(root, split_id, replacement)

    return root


def build_board(tier: Tier, rng: random.Random) -> Board:
    """Create a board deterministically from ``tier`` and ``rng``.

    Pane ids encode their location, which makes diagnostics and tests readable;
    navigation itself still uses the split geometry rather than parsing ids.
    """
    spaces: list[Space] = []
    for space_number in range(1, tier.spaces + 1):
        tab_count = rng.randint(tier.min_tabs, tier.max_tabs)
        tabs: list[Tab] = []
        for tab_number in range(1, tab_count + 1):
            pane_count = rng.randint(tier.min_panes, tier.max_panes)
            panes = [
                Pane(f"s{space_number}:t{tab_number}:p{pane_number}")
                for pane_number in range(1, pane_count + 1)
            ]
            root = _build_tree(panes, rng, tier)
            tabs.append(
                Tab(
                    id=f"s{space_number}:t{tab_number}",
                    name=f"tab-{tab_number}",
                    root=root,
                )
            )
        spaces.append(
            Space(
                id=f"s{space_number}",
                name=f"space-{space_number}",
                tabs=tabs,
            )
        )

    board = Board(spaces)
    board.reset_to_origin()
    return board
