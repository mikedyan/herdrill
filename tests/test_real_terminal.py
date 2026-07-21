"""Launch the real game on a pty and prove terminal bytes clear a box."""

from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _screen_from_ansi(data: bytes, width: int = 100, height: int = 30) -> list[str]:
    """Apply the small ANSI subset curses emits to an in-memory screen."""
    text = data.decode("utf-8", "replace")
    cells = [[" " for _ in range(width)] for _ in range(height)]
    row = column = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\x1b":
            if index + 1 < len(text) and text[index + 1] == "[":
                end = index + 2
                while end < len(text) and not "@" <= text[end] <= "~":
                    end += 1
                if end >= len(text):
                    break
                command = text[end]
                raw = text[index + 2 : end].lstrip("?")
                params = [int(part) if part.isdigit() else 0 for part in raw.split(";")]
                if command in ("H", "f"):
                    row = (params[0] if params and params[0] else 1) - 1
                    column = (params[1] if len(params) > 1 and params[1] else 1) - 1
                elif command == "G":
                    column = (params[0] if params and params[0] else 1) - 1
                elif command == "C":
                    column += params[0] if params and params[0] else 1
                elif command == "D":
                    column -= params[0] if params and params[0] else 1
                elif command == "A":
                    row -= params[0] if params and params[0] else 1
                elif command == "B":
                    row += params[0] if params and params[0] else 1
                elif command == "J" and params and params[0] == 2:
                    cells = [[" " for _ in range(width)] for _ in range(height)]
                elif command == "K":
                    for x in range(max(0, column), width):
                        cells[row][x] = " "
                index = end + 1
                continue
            # Charset selectors such as ESC(B have two bytes after ESC.
            index += 3 if index + 1 < len(text) and text[index + 1] in "()" else 2
            continue
        if char == "\r":
            column = 0
        elif char == "\n":
            row += 1
        elif char == "\b":
            column = max(0, column - 1)
        elif char.isprintable() and 0 <= row < height and 0 <= column < width:
            cells[row][column] = char
            column += 1
        index += 1
    return ["".join(line) for line in cells]


def test_real_binary_accepts_real_prefix_and_pane_navigation_bytes(tmp_path):
    pty = pytest.importorskip("pty")
    fcntl = pytest.importorskip("fcntl")
    termios = pytest.importorskip("termios")
    import struct

    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))

    home = tmp_path / "home"
    home.mkdir()
    settings_dir = home / ".herdrill"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text(
        '{"version":2,"target_sound":"off","control_mode":"herdrill"}\n'
    )
    env = dict(os.environ)
    env.update(
        HOME=str(home),
        TERM="xterm-256color",
        PYTHONPATH=ROOT + os.pathsep + env.get("PYTHONPATH", ""),
        LC_ALL=env.get("LC_ALL") or "en_US.UTF-8",
    )
    env.pop("LINES", None)
    env.pop("COLUMNS", None)

    try:
        process = subprocess.Popen(
            [os.path.join(ROOT, "bin", "herdrill")],
            cwd=ROOT,
            env=env,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
    except OSError as error:
        os.close(master)
        os.close(slave)
        pytest.skip(f"cannot launch pty child: {error}")
    os.close(slave)

    output = bytearray()
    started = False
    sent = False
    deadline = time.monotonic() + 5.0
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([master], [], [], 0.1)
            if readable:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)

            screen = _screen_from_ansi(bytes(output))
            if not started and b"enter / space start" in output:
                os.write(master, b" ")
                started = True

            # Tier zero is always one side-by-side split: focus starts left and
            # the only valid target is right. These are exactly the bytes a
            # terminal sends for ctrl+b followed by l.
            if started and not sent and b"score 0" in output:
                os.write(master, b"\x02l")
                sent = True
            # Curses may repaint only the changed digit, so the lightweight
            # ANSI emulator can lose unchanged status labels on some terminfo
            # implementations. The score digit itself is at fixed column 14.
            if sent and screen[-1][14] == "1":
                break
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        os.close(master)

    decoded = output.decode("utf-8", "replace")
    if "setupterm" in decoded.lower() or "unsupported locale" in decoded.lower():
        pytest.skip(decoded)
    assert started, f"game never drew its start screen: {decoded!r}"
    assert sent, f"game never drew its first frame: {decoded!r}"
    final_screen = _screen_from_ansi(bytes(output))
    assert final_screen[-1][14] == "1", (
        "real ctrl+b,l bytes did not clear the target; final status was "
        f"{final_screen[-1]!r}; terminal output was {decoded!r}"
    )
