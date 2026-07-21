import random

from herdrill.ramp import TIERS, build_board
from herdrill.round import Round


def clear_tier_zero_target(game_round, now):
    focused = game_round.board.focused_pane_id
    target = game_round.target_pane_id
    action = "focus_pane_right" if focused.endswith("p1") and target.endswith("p2") else "focus_pane_left"
    assert game_round.apply(action, now=now)


def test_clear_advances_score_and_places_a_new_noncurrent_target():
    game_round = Round(0.0, random.Random(1))
    old_target = game_round.target_pane_id
    clear_tier_zero_target(game_round, 1.0)
    assert game_round.score == 1
    assert game_round.board.focused_pane_id == old_target
    assert game_round.target_pane_id != game_round.board.focused_pane_id


def test_fifth_clear_regenerates_board_resets_focus_and_targets_another_space():
    game_round = Round(0.0, random.Random(2))
    old_board = game_round.board
    for score in range(1, 6):
        clear_tier_zero_target(game_round, float(score))

    assert game_round.score == 5
    assert game_round.tier.number == 1
    assert game_round.board is not old_board
    assert game_round.board.active_space == 0
    assert game_round.board.focused_pane_id == game_round.board.origin_pane_id
    assert game_round.board.locate(game_round.target_pane_id)[0] != 0


def test_round_ends_at_exactly_sixty_seconds_and_rejects_late_clear():
    game_round = Round(100.0, random.Random(0))
    assert not game_round.tick(159.999)
    action = "focus_pane_right"
    assert not game_round.apply(action, now=160.0)
    assert game_round.ended
    assert game_round.score == 0
    assert game_round.remaining(999.0) == 0.0


def test_workspace_action_clears_when_it_focuses_the_target_pane():
    game_round = Round(0.0, random.Random(0))
    game_round.tier = TIERS[1]
    game_round.board = build_board(game_round.tier, random.Random(4))
    game_round.target_pane_id = game_round.board.spaces[1].tabs[0].focused_pane_id
    assert game_round.apply("switch_workspace", index=2, now=1.0)
    assert game_round.score == 1


def test_tab_action_clears_when_it_focuses_target_tab():
    game_round = Round(0.0, random.Random(0))
    game_round.tier = TIERS[1]
    for seed in range(100):
        board = build_board(game_round.tier, random.Random(seed))
        if len(board.spaces[0].tabs) > 1:
            break
    game_round.board = board
    game_round.target_pane_id = board.spaces[0].tabs[1].focused_pane_id
    assert game_round.apply("switch_tab", index=2, now=1.0)
    assert game_round.score == 1


def test_next_tab_action_wraps_and_clears_the_target_tab():
    game_round = Round(0.0, random.Random(0))
    game_round.tier = TIERS[1]
    for seed in range(100):
        board = build_board(game_round.tier, random.Random(seed))
        if len(board.spaces[0].tabs) > 1:
            break
    game_round.board = board
    game_round.target_pane_id = board.spaces[0].tabs[1].focused_pane_id
    assert game_round.apply("next_tab", now=1.0)
    assert game_round.score == 1


def test_previous_tab_action_wraps_and_clears_the_target_tab():
    game_round = Round(0.0, random.Random(0))
    game_round.tier = TIERS[1]
    for seed in range(100):
        board = build_board(game_round.tier, random.Random(seed))
        if len(board.spaces[0].tabs) > 1:
            break
    game_round.board = board
    last_tab = board.spaces[0].tabs[-1]
    game_round.target_pane_id = last_tab.focused_pane_id
    assert game_round.apply("previous_tab", now=1.0)
    assert game_round.score == 1


def test_pane_cycle_actions_wrap_and_clear_targets():
    next_round = Round(0.0, random.Random(1))
    assert next_round.apply("cycle_pane_next", now=1.0)
    assert next_round.score == 1

    previous_round = Round(0.0, random.Random(1))
    assert previous_round.apply("cycle_pane_previous", now=1.0)
    assert previous_round.score == 1


def test_ignored_actions_do_not_change_round():
    game_round = Round(0.0, random.Random(0))
    board = game_round.board
    target = game_round.target_pane_id
    assert not game_round.apply("focus_agent", index=1, now=1.0)
    assert game_round.board is board
    assert game_round.target_pane_id == target
    assert game_round.score == 0


def test_finish_updates_in_memory_best_only_when_beaten():
    game_round = Round(0.0, random.Random(0), best_score=3)
    game_round.score = 2
    assert not game_round.beat_best
    assert game_round.finish() == 3
    game_round.score = 4
    assert game_round.beat_best
    assert game_round.finish() == 4
