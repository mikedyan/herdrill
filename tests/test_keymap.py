import textwrap

from herdrill.keymap import (
    DEFAULT_BINDINGS,
    HERDR_DEFAULT_BINDINGS,
    Keymap,
    canonical_key,
    default_config_path,
    load,
)
from herdrill.settings import CONTROL_HERDRILL


def test_herdrill_navigation_defaults_are_available():
    keymap = Keymap.from_bindings(DEFAULT_BINDINGS)
    assert keymap.resolve(True, "1") == ("focus_agent", 1)
    assert keymap.resolve(True, "shift+1") == ("switch_workspace", 1)
    assert keymap.resolve(True, "alt+1") == ("switch_tab", 1)
    assert keymap.resolve(True, "shift+h") == ("previous_tab", None)
    assert keymap.resolve(True, "shift+l") == ("next_tab", None)
    assert keymap.resolve(True, "h") == ("focus_pane_left", None)
    assert keymap.resolve(True, "j") == ("focus_pane_down", None)
    assert keymap.resolve(True, "k") == ("focus_pane_up", None)
    assert keymap.resolve(True, "l") == ("focus_pane_right", None)
    assert keymap.resolve(True, "tab") == ("cycle_pane_next", None)
    assert keymap.resolve(True, "shift+tab") == ("cycle_pane_previous", None)


def test_real_owner_style_bindings_coexist():
    keymap = Keymap.from_bindings(
        {
            "switch_workspace": "prefix+shift+1..9",
            "switch_tab": "prefix+alt+1..9",
            "focus_agent": "prefix+1..9",
            "previous_tab": "prefix+shift+h",
            "next_tab": "prefix+shift+l",
        }
    )
    assert keymap.resolve(True, "3") == ("focus_agent", 3)
    assert keymap.resolve(True, "shift+3") == ("switch_workspace", 3)
    assert keymap.resolve(True, "alt+3") == ("switch_tab", 3)
    assert keymap.resolve(True, "shift+h") == ("previous_tab", None)
    assert keymap.resolve(True, "shift+l") == ("next_tab", None)


def test_complete_herdr_config_is_layered_over_herdr_defaults(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(textwrap.dedent("""
        [keys]
        switch_workspace = "prefix+shift+1..9"
        previous_tab = "prefix+shift+h"
        next_tab = "prefix+shift+l"
    """))
    keymap = load(str(config), herdr_installed=False)
    assert keymap.source == "herdr_config"
    assert keymap.resolve(True, "shift+h") == ("previous_tab", None)
    assert keymap.resolve(True, "shift+l") == ("next_tab", None)
    assert keymap.resolve(True, "1") == ("switch_tab", 1)
    assert keymap.binding_for("previous_tab") == "ctrl+b shift+h"


def test_incomplete_herdr_config_uses_safe_full_fallback(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[keys]\nnext_tab = "prefix+x"\n')
    keymap = load(str(config), herdr_installed=False)
    assert keymap.source == "herdrill_fallback"
    assert keymap.resolve(True, "shift+l") == ("next_tab", None)
    assert any("space navigation" in warning for warning in keymap.warnings)


def test_user_binding_displaces_a_colliding_default(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[keys]\nprevious_workspace = "prefix+k"\n')
    keymap = load(str(config), herdr_installed=False)
    assert keymap.resolve(True, "k") == ("previous_workspace", None)
    assert keymap.binding_for("focus_pane_up") is None


def test_unsupported_action_reserves_its_explicit_chord(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(textwrap.dedent("""
        [keys]
        switch_workspace = "prefix+shift+1..9"
        close_pane = "prefix+h"
    """))
    keymap = load(str(config), herdr_installed=False)
    assert keymap.resolve(True, "h") == ("close_pane", None)
    assert keymap.binding_for("focus_pane_left") is None


def test_arrays_and_empty_action_overrides_are_supported(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(textwrap.dedent("""
        [keys]
        switch_workspace = "prefix+shift+1..9"
        next_tab = ["prefix+n", "ctrl+alt+]"]
        previous_tab = ""
    """))
    keymap = load(str(config), herdr_installed=False)
    assert keymap.resolve(True, "n") == ("next_tab", None)
    assert keymap.resolve(False, "alt+ctrl+]") == ("next_tab", None)
    assert keymap.binding_for("previous_tab") is None


def test_ambiguous_explicit_chord_is_disabled_and_reported(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(textwrap.dedent("""
        [keys]
        switch_workspace = "prefix+shift+1..9"
        next_tab = "prefix+n"
        close_pane = "prefix+n"
    """))
    keymap = load(str(config), herdr_installed=False)
    assert keymap.resolve(True, "n") is None
    assert any("ambiguous" in warning for warning in keymap.warnings)


def test_individual_indexed_bindings_keep_their_digit(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(textwrap.dedent("""
        [keys]
        switch_workspace = ["prefix+2", "prefix+4"]
    """))
    keymap = load(str(config), herdr_installed=False)
    assert keymap.resolve(True, "2") == ("switch_workspace", 2)
    assert keymap.resolve(True, "4") == ("switch_workspace", 4)
    assert keymap.bindings_for("switch_workspace") == ("ctrl+b 2", "ctrl+b 4")


def test_legacy_indexed_modifiers_are_loaded(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(textwrap.dedent("""
        [keys]
        previous_workspace = "prefix+k"
        [keys.indexed]
        tabs = "alt"
        workspaces = "ctrl+alt"
    """))
    keymap = load(str(config), herdr_installed=False)
    assert keymap.resolve(False, "alt+2") == ("switch_tab", 2)
    assert keymap.resolve(False, "ctrl+alt+2") == ("switch_workspace", 2)


def test_malformed_config_falls_back_without_raising(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("this [ is not toml")
    keymap = load(str(path), herdr_installed=False)
    assert keymap.source == "herdrill_fallback"
    assert keymap.resolve(True, "l") == ("focus_pane_right", None)
    assert keymap.warnings


def test_missing_herdr_uses_herdrill_defaults(tmp_path):
    keymap = load(str(tmp_path / "missing.toml"), herdr_installed=False)
    assert keymap.source == "herdrill_defaults"
    assert keymap.resolve(True, "alt+1") == ("switch_tab", 1)


def test_installed_herdr_without_config_falls_back_when_spaces_are_unreachable(tmp_path):
    keymap = load(str(tmp_path / "missing.toml"), herdr_installed=True)
    assert keymap.source == "herdrill_fallback"
    assert any("space navigation" in warning for warning in keymap.warnings)


def test_forced_herdrill_mode_ignores_a_real_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[keys]\nprefix = "ctrl+a"\nnext_workspace = "n"\n')
    keymap = load(str(config), mode=CONTROL_HERDRILL, herdr_installed=True)
    assert keymap.source == "herdrill_defaults"
    assert keymap.prefix == "ctrl+b"
    assert keymap.resolve(False, "n") is None


def test_prefix_unprefixed_binding_and_modifier_order_are_normalized(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(textwrap.dedent("""
        [keys]
        prefix = "ctrl+a"
        next_workspace = "n"
        next_tab = "alt+ctrl+]"
    """))
    keymap = load(str(path), herdr_installed=False)
    assert keymap.prefix == "ctrl+a"
    assert keymap.resolve(False, "n") == ("next_workspace", None)
    assert keymap.resolve(False, "ctrl+alt+]") == ("next_tab", None)
    assert canonical_key("option+control+]") == "ctrl+alt+]"


def test_prefix_displaces_a_conflicting_direct_action(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(textwrap.dedent("""
        [keys]
        prefix = "ctrl+a"
        next_workspace = "ctrl+a"
        switch_workspace = "prefix+shift+1..9"
    """))
    keymap = load(str(path), herdr_installed=False)
    assert keymap.resolve(False, "ctrl+a") is None
    assert any("is the prefix" in warning for warning in keymap.warnings)


def test_environment_config_path_matches_herdr(monkeypatch, tmp_path):
    path = tmp_path / "custom.toml"
    monkeypatch.setenv("HERDR_CONFIG_PATH", str(path))
    assert default_config_path() == str(path)


def test_official_herdr_profile_keeps_workspace_picker_reserved_only():
    keymap = Keymap.from_bindings(HERDR_DEFAULT_BINDINGS)
    assert keymap.resolve(True, "w") == ("workspace_picker", None)
    assert keymap.binding_for("switch_workspace") is None
