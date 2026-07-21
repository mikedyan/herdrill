from herdrill_chatgpt.keycheck import describe


def test_describes_ghostty_legacy_alt_digit():
    assert describe(b"\x1b2") == "alt+2"


def test_describes_ghostty_kitty_keyboard_alt_digit():
    assert describe(b"\x1b[50;3u") == "alt+2"


def test_describes_ghostty_kitty_keyboard_ctrl_b():
    assert describe(b"\x1b[98;5u") == "ctrl+b"


def test_describes_macos_composed_option_digit():
    assert describe("™".encode()) == "alt+2"


def test_describes_prefix_control_byte():
    assert describe(b"\x02") == "ctrl+b"
