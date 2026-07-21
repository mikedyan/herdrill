"""Read the player's real herdr keymap so the drill trains their actual keys."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field

CONFIG_PATH = os.path.expanduser("~/.config/herdr/config.toml")

DEFAULT_PREFIX = "ctrl+b"

# Only the actions herdrill simulates. Values are herdr's shipped defaults.
#
# herdr's `workspace_picker` (prefix+w) is deliberately absent. Every action
# listed here must have a `Game._do_<action>` handler behind it: a bound key
# that dispatches to nothing trains a keystroke the drill does not respond to,
# which is worse than not offering the key. herdrill has no separate
# space-picking overlay to model it with -- the goto navigator already reaches
# every pane in every space -- so the binding is not shipped rather than
# shipped dead. Adding it back means adding the overlay first.
DEFAULT_BINDINGS: dict[str, str] = {
    "goto": "prefix+g",
    "help": "prefix+?",
    "open_notification_target": "prefix+o",
    "new_tab": "prefix+c",
    "new_workspace": "prefix+shift+n",
    "new_worktree": "prefix+shift+g",
    "switch_tab": "prefix+1..9",
    "focus_agent": "",
    "switch_workspace": "",
    "previous_workspace": "",
    "next_workspace": "",
    "focus_pane_left": "prefix+h",
    "focus_pane_down": "prefix+j",
    "focus_pane_up": "prefix+k",
    "focus_pane_right": "prefix+l",
    "cycle_pane_next": "prefix+tab",
    "cycle_pane_previous": "prefix+shift+tab",
    "split_vertical": "prefix+v",
    "split_horizontal": "prefix+minus",
    "close_pane": "prefix+x",
    "zoom": "prefix+z",
}

PREFIX_MARKER = "prefix+"
INDEXED_SUFFIX = "1..9"
INDEXES = range(1, 10)


@dataclass
class Keymap:
    """Keystrokes resolved to actions.

    `bindings` maps (was the prefix held first?, normalized key) to
    (action, index), where index is the 1-9 digit of an indexed binding such as
    `switch_tab` and None for every other binding.
    """

    prefix: str = DEFAULT_PREFIX
    bindings: dict[tuple[bool, str], tuple[str, int | None]] = field(
        default_factory=dict
    )

    @classmethod
    def from_bindings(
        cls,
        config: dict[str, str],
        prefix: str = DEFAULT_PREFIX,
        overrides: dict[str, str] | None = None,
    ) -> Keymap:
        """Build a keymap from `config`, then let `overrides` displace it.

        The two passes are the whole point. herdr since v0.7.1 resolves a
        collision in the user's favour: a key the user bound explicitly stops
        doing whatever default also claimed it. A single pass would instead
        hand the key to whichever action happens to sit later in
        `DEFAULT_BINDINGS`, which is an ordering accident, and the drill would
        train keys the player's real herdr does not have.
        """
        keymap = cls(prefix=prefix)
        for action, spec in config.items():
            keymap._add(action, spec)
        for action, spec in (overrides or {}).items():
            keymap._add(action, spec)
        return keymap

    def _add(self, action: str, spec: str) -> None:
        """Record one herdr binding spec, e.g. `prefix+shift+1..9`."""
        if not spec:
            return
        prefixed = spec.startswith(PREFIX_MARKER)
        rest = spec.removeprefix(PREFIX_MARKER) if prefixed else spec
        if rest.endswith(INDEXED_SUFFIX):
            # Whatever precedes the range is the modifier stem: "", "shift+"...
            stem = rest.removesuffix(INDEXED_SUFFIX)
            for index in INDEXES:
                self.bindings[(prefixed, f"{stem}{index}")] = (action, index)
        else:
            self.bindings[(prefixed, rest)] = (action, None)

    def resolve(self, prefixed: bool, key: str) -> tuple[str, int | None] | None:
        """Return (action, index) for a keystroke, or None if it is unbound."""
        return self.bindings.get((prefixed, key))

    def binding_for(self, action: str) -> str | None:
        """Human-readable binding for an action, for on-screen hints."""
        for (prefixed, key), (name, index) in sorted(self.bindings.items()):
            if name != action:
                continue
            stem = key.removesuffix(str(index))
            shown = key if index is None else f"{stem}{INDEXED_SUFFIX}"
            return f"{self.prefix} {shown}" if prefixed else shown
        return None


def load(path: str | None = None) -> Keymap:
    """Load the player's herdr config, falling back to shipped defaults.

    A missing, unreadable, corrupt or oddly shaped config yields the defaults;
    a broken herdr config must never stop the drill from starting.
    """
    bindings = dict(DEFAULT_BINDINGS)
    try:
        with open(path or CONFIG_PATH, "rb") as handle:
            data = tomllib.load(handle)
    # ValueError covers tomllib.TOMLDecodeError *and* the UnicodeDecodeError
    # tomllib raises when the file is not valid UTF-8; both subclass ValueError.
    except (OSError, ValueError):
        return Keymap.from_bindings(bindings)

    keys = data.get("keys")
    if not isinstance(keys, dict):
        return Keymap.from_bindings(bindings)

    prefix = keys.get("prefix")
    # Split, rather than overlaying into one dict: an action-keyed overlay
    # loses the distinction between "this is the shipped default" and "the
    # player typed this", and that distinction is what decides a collision.
    # The default for a *rebound* action is dropped entirely -- rebinding
    # `goto` to prefix+q must not leave prefix+q and prefix+g both opening it.
    overrides = {
        action: spec
        for action in bindings
        if isinstance(spec := keys.get(action), str)
    }
    defaults = {
        action: spec for action, spec in bindings.items() if action not in overrides
    }
    return Keymap.from_bindings(
        defaults,
        prefix if isinstance(prefix, str) else DEFAULT_PREFIX,
        overrides=overrides,
    )
