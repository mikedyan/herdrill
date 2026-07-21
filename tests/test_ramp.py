import random

from herdrill_chatgpt.board import Split
from herdrill_chatgpt.ramp import TIERS, build_board, tier_for


def test_tier_thresholds_are_stepped_at_5_10_15():
    assert [tier_for(n).number for n in (0, 4, 5, 9, 10, 14, 15, 99)] == [
        0, 0, 1, 1, 2, 2, 3, 3
    ]


def test_each_tier_has_specified_space_tab_and_pane_bounds():
    for tier in TIERS:
        for seed in range(10):
            board = build_board(tier, random.Random(seed))
            assert len(board.spaces) == tier.spaces
            for space in board.spaces:
                assert tier.min_tabs <= len(space.tabs) <= tier.max_tabs
                for tab in space.tabs:
                    assert tier.min_panes <= len(tab.panes()) <= tier.max_panes


def test_generation_is_reproducible_from_seed_and_tier():
    first = build_board(TIERS[3], random.Random(42))
    second = build_board(TIERS[3], random.Random(42))
    assert first == second


def test_late_tier_tabs_are_nested_split_trees():
    board = build_board(TIERS[3], random.Random(3))
    for space in board.spaces:
        for tab in space.tabs:
            assert isinstance(tab.root, Split)
            assert isinstance(tab.root.first, Split) or isinstance(tab.root.second, Split)


def test_every_generated_board_starts_at_known_origin():
    for tier in TIERS:
        board = build_board(tier, random.Random(9))
        assert board.active_space == 0
        assert board.current_space.active_tab == 0
        assert board.focused_pane_id == "s1:t1:p1"
