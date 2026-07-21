from herdrill_chatgpt.board import (
    Board,
    Leaf,
    Pane,
    Rect,
    Space,
    Split,
    Tab,
    compute,
    directional_neighbor,
)


def simple_board():
    root = Split(
        "v",
        0.5,
        Leaf(Pane("left")),
        Split("h", 0.5, Leaf(Pane("top")), Leaf(Pane("bottom"))),
    )
    return Board([Space("s1", "space", [Tab("t1", "tab", root)])])


def test_compute_tiles_nested_split_without_losing_cells():
    rects = compute(simple_board().current_tab.root, Rect(10, 5, 100, 40))
    assert rects["left"] == Rect(10, 5, 50, 40)
    assert rects["top"] == Rect(60, 5, 50, 20)
    assert rects["bottom"] == Rect(60, 25, 50, 20)


def test_directional_navigation_uses_real_geometry():
    board = simple_board()
    assert board.focused_pane_id == "left"
    assert board.focus_direction("right")
    # Both right-hand panes share the same edge; the stable id tie-break wins.
    assert board.focused_pane_id == "bottom"
    assert board.focus_direction("up")
    assert board.focused_pane_id == "top"
    assert board.focus_direction("left")
    assert board.focused_pane_id == "left"
    assert not board.focus_direction("left")


def test_diagonal_candidate_is_not_a_neighbor():
    rects = {
        "origin": Rect(0, 0, 10, 10),
        "corner": Rect(10, 10, 10, 10),
    }
    for direction in ("left", "right", "up", "down"):
        assert directional_neighbor(rects, "origin", direction) is None


def test_space_and_tab_switching_are_one_based_and_preserve_tab_focus():
    make_tab = lambda name: Tab(name, name, Split("v", 0.5, Leaf(Pane(name + "a")), Leaf(Pane(name + "b"))))
    board = Board(
        [
            Space("s1", "one", [make_tab("t1"), make_tab("t2")]),
            Space("s2", "two", [make_tab("t3")]),
        ]
    )
    assert board.switch_tab(2)
    board.current_tab.focused_pane_id = "t2b"
    assert board.switch_workspace(2)
    assert board.focused_pane_id == "t3a"
    assert board.previous_workspace()
    assert board.current_tab.id == "t2"
    assert board.focused_pane_id == "t2b"
    assert not board.switch_workspace(9)


def test_locate_and_reset_to_origin():
    board = simple_board()
    board.current_tab.focused_pane_id = "bottom"
    assert board.locate("bottom") == (0, 0, 2)
    assert board.locate("missing") is None
    board.reset_to_origin()
    assert board.focused_pane_id == "left"
