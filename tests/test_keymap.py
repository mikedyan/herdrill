import textwrap

from herdrill_chatgpt.keymap import DEFAULT_BINDINGS, Keymap, load


def test_navigation_defaults_are_available():
    keymap = Keymap.from_bindings(DEFAULT_BINDINGS)
    assert keymap.resolve(True, "1") == ("switch_tab", 1)
    assert keymap.resolve(True, "h") == ("focus_pane_left", None)
    assert keymap.resolve(True, "j") == ("focus_pane_down", None)
    assert keymap.resolve(True, "k") == ("focus_pane_up", None)
    assert keymap.resolve(True, "l") == ("focus_pane_right", None)


def test_real_owner_style_bindings_coexist():
    keymap = Keymap.from_bindings(
        {
            "switch_workspace": "prefix+1..9",
            "switch_tab": "prefix+alt+1..9",
            "focus_agent": "prefix+shift+1..9",
        }
    )
    assert keymap.resolve(True, "3") == ("switch_workspace", 3)
    assert keymap.resolve(True, "alt+3") == ("switch_tab", 3)
    assert keymap.resolve(True, "shift+3") == ("focus_agent", 3)


def test_user_binding_displaces_a_colliding_default(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[keys]\nprevious_workspace = "prefix+k"\n')
    keymap = load(str(config))
    assert keymap.resolve(True, "k") == ("previous_workspace", None)
    assert keymap.binding_for("focus_pane_up") is None


def test_malformed_config_falls_back_without_raising(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("this [ is not toml")
    assert load(str(path)).resolve(True, "l") == ("focus_pane_right", None)


def test_prefix_and_unprefixed_binding_are_read(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(textwrap.dedent("""
        [keys]
        prefix = "ctrl+a"
        next_workspace = "n"
    """))
    keymap = load(str(path))
    assert keymap.prefix == "ctrl+a"
    assert keymap.resolve(False, "n") == ("next_workspace", None)
