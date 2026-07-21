"""Tiny raw-terminal diagnostic for terminal-specific Alt encodings."""

from __future__ import annotations

import os
import select
import sys
import termios
import time
import tty

from .main import _csi_modified_key, normalize_char, normalize_key


def describe(data: bytes) -> str | None:
    """Best-effort name for one burst of raw terminal bytes."""
    if len(data) == 1:
        return normalize_key(data[0])
    if data.startswith(b"\x1b["):
        try:
            return _csi_modified_key(data[2:].decode("ascii"))
        except UnicodeDecodeError:
            return None
    if data.startswith(b"\x1b"):
        try:
            following = data[1:].decode("utf-8")
        except UnicodeDecodeError:
            return None
        if len(following) != 1:
            return None
        name = normalize_char(following)
        return None if name is None else f"alt+{name}"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return normalize_char(text) if len(text) == 1 else None


def main() -> None:
    if not sys.stdin.isatty():
        raise SystemExit("keycheck must run in a terminal")

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    print("Herdrill key check")
    print(f"terminal: {os.environ.get('TERM_PROGRAM', '?')}  TERM={os.environ.get('TERM', '?')}")
    print("Press Option+2 by itself, then Ctrl+B followed by Option+2.")
    print("Press Ctrl+C when done.\n")
    sys.stdout.flush()

    try:
        tty.setraw(fd)
        while True:
            ready, _, _ = select.select([fd], [], [], None)
            if not ready:
                continue
            burst = bytearray(os.read(fd, 64))
            # Terminal escape sequences can span writes; group bytes until the
            # input has been quiet for 50 ms.
            quiet_at = time.monotonic() + 0.05
            while time.monotonic() < quiet_at:
                ready, _, _ = select.select([fd], [], [], max(0.0, quiet_at - time.monotonic()))
                if not ready:
                    break
                burst.extend(os.read(fd, 64))
                quiet_at = time.monotonic() + 0.05

            if burst == b"\x03":
                break
            raw = bytes(burst)
            hexadecimal = " ".join(f"{byte:02x}" for byte in raw)
            name = describe(raw)
            suffix = f"  =>  {name}" if name is not None else ""
            os.write(sys.stdout.fileno(), f"bytes: {hexadecimal}{suffix}\r\n".encode())
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        print("\nDone.")
