"""Pure state machine for one timed Herdrill round."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .board import Board
from .ramp import Tier, build_board, tier_for
from .target import place_target

ROUND_SECONDS = 60.0

DIRECTION_ACTIONS = {
    "focus_pane_left": "left",
    "focus_pane_down": "down",
    "focus_pane_up": "up",
    "focus_pane_right": "right",
}
NAVIGATION_ACTIONS = {
    "switch_workspace",
    "previous_workspace",
    "next_workspace",
    "switch_tab",
    "previous_tab",
    "next_tab",
    "cycle_pane_next",
    "cycle_pane_previous",
    *DIRECTION_ACTIONS,
}


@dataclass
class Round:
    started_at: float
    rng: random.Random = field(default_factory=random.Random)
    best_score: int = 0
    duration: float = ROUND_SECONDS
    score: int = field(init=False, default=0)
    tier: Tier = field(init=False)
    board: Board = field(init=False)
    target_pane_id: str = field(init=False)
    ended: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self.best_score = max(0, int(self.best_score))
        self.tier = tier_for(0)
        self.board = build_board(self.tier, self.rng)
        self.target_pane_id = place_target(self.board, self.rng)

    def elapsed(self, now: float) -> float:
        return min(self.duration, max(0.0, now - self.started_at))

    def remaining(self, now: float) -> float:
        return max(0.0, self.duration - self.elapsed(now))

    @property
    def displayed_best(self) -> int:
        return max(self.best_score, self.score)

    @property
    def beat_best(self) -> bool:
        return self.score > self.best_score

    def tick(self, now: float) -> bool:
        """Advance the wall clock. Return whether the round is over."""
        if not self.ended and now - self.started_at >= self.duration:
            self.ended = True
        return self.ended

    def finish(self) -> int:
        """Commit the score to this round's in-memory best value."""
        self.best_score = max(self.best_score, self.score)
        return self.best_score

    def apply(
        self,
        action: str,
        *,
        index: int | None = None,
        now: float,
    ) -> bool:
        """Apply one Herdr action and return whether it cleared a box."""
        if self.tick(now) or action not in NAVIGATION_ACTIONS:
            return False

        if action == "switch_workspace" and index is not None:
            self.board.switch_workspace(index)
        elif action == "previous_workspace":
            self.board.previous_workspace()
        elif action == "next_workspace":
            self.board.next_workspace()
        elif action == "switch_tab" and index is not None:
            self.board.switch_tab(index)
        elif action == "previous_tab":
            self.board.previous_tab()
        elif action == "next_tab":
            self.board.next_tab()
        elif action == "cycle_pane_next":
            self.board.cycle_pane_next()
        elif action == "cycle_pane_previous":
            self.board.cycle_pane_previous()
        elif direction := DIRECTION_ACTIONS.get(action):
            self.board.focus_direction(direction)

        if self.board.focused_pane_id != self.target_pane_id:
            return False

        self._clear_target()
        return True

    def _clear_target(self) -> None:
        self.score += 1
        next_tier = tier_for(self.score)
        tier_changed = next_tier.number != self.tier.number

        if tier_changed:
            self.tier = next_tier
            self.board = build_board(self.tier, self.rng)
            self.board.reset_to_origin()

        self.target_pane_id = place_target(
            self.board,
            self.rng,
            tier_changed=tier_changed,
        )
