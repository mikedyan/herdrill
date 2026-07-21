import random

from herdrill.ramp import TIERS, build_board
from herdrill.target import place_target


def test_target_never_spawns_on_current_focus():
    for tier in TIERS:
        board = build_board(tier, random.Random(1))
        for seed in range(30):
            assert place_target(board, random.Random(seed)) != board.focused_pane_id


def test_tier_change_target_is_in_a_different_space_from_origin():
    for tier in TIERS[1:]:
        board = build_board(tier, random.Random(4))
        target = place_target(board, random.Random(7), tier_changed=True)
        assert board.locate(target)[0] != board.locate(board.focused_pane_id)[0]


def test_same_tier_can_draw_from_all_noncurrent_panes():
    board = build_board(TIERS[1], random.Random(2))
    choices = {place_target(board, random.Random(seed)) for seed in range(200)}
    assert board.focused_pane_id not in choices
    assert choices == set(board.pane_ids()) - {board.focused_pane_id}
