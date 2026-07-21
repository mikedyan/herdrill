import json

from herdrill.settings import (
    CONTROL_AUTO,
    CONTROL_HERDRILL,
    SETTINGS_PATH,
    GameSettings,
    load_settings,
    save_settings,
)


def test_canonical_settings_path_uses_the_herdrill_name():
    assert SETTINGS_PATH == "~/.herdrill/settings.json"


def test_settings_default_and_corrupt_file_fall_back_safely(tmp_path):
    path = tmp_path / "settings.json"
    assert load_settings(str(path)) == GameSettings("tink", CONTROL_AUTO)
    path.write_text("not json")
    assert load_settings(str(path)) == GameSettings("tink", CONTROL_AUTO)
    path.write_text('{"target_sound":"unknown","control_mode":"bad"}')
    assert load_settings(str(path)) == GameSettings("tink", CONTROL_AUTO)


def test_version_one_sound_setting_migrates_to_automatic_controls(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"version":1,"target_sound":"glass"}')
    assert load_settings(str(path)) == GameSettings("glass", CONTROL_AUTO)


def test_sound_and_control_mode_round_trip_atomically(tmp_path):
    path = tmp_path / "nested" / "settings.json"
    settings = GameSettings("submarine", CONTROL_HERDRILL)
    assert save_settings(settings, str(path))
    assert load_settings(str(path)) == settings
    payload = json.loads(path.read_text())
    assert payload == {
        "version": 2,
        "target_sound": "submarine",
        "control_mode": CONTROL_HERDRILL,
    }
    assert not list(path.parent.glob("*.tmp"))

    automatic = GameSettings("off", CONTROL_AUTO)
    assert save_settings(automatic, str(path))
    assert load_settings(str(path)) == automatic


def test_invalid_settings_are_not_written(tmp_path):
    path = tmp_path / "settings.json"
    assert not save_settings(GameSettings("unknown"), str(path))
    assert not save_settings(GameSettings("tink", "unknown"), str(path))
    assert not path.exists()
