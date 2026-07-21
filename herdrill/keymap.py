"""Resolve Herdr navigation controls for the drill."""

from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass, field
from typing import TypeAlias

from .settings import CONTROL_AUTO, CONTROL_HERDRILL

CONFIG_PATH = "~/.config/herdr/config.toml"
DEFAULT_PREFIX = "ctrl+b"
PREFIX_MARKER = "prefix+"
INDEXED_SUFFIX = "1..9"
INDEXES = range(1, 10)
INDEXED_ACTIONS = {"switch_tab", "switch_workspace", "focus_agent"}

BindingSpec: TypeAlias = str | list[str] | tuple[str, ...]

# Herdr's built-in controls are the base for a real Herdr config: fields that
# are absent from config.toml still have these meanings in Herdr. Unsupported
# actions are included so their chords remain reserved instead of accidentally
# training a navigation action after a collision.
HERDR_DEFAULT_BINDINGS: dict[str, BindingSpec] = {
    "help": "prefix+?",
    "settings": "prefix+s",
    "new_workspace": "prefix+shift+n",
    "new_worktree": "prefix+shift+g",
    "open_worktree": "",
    "remove_worktree": "",
    "rename_workspace": "prefix+shift+w",
    "close_workspace": "prefix+shift+d",
    "workspace_picker": "prefix+w",  # Reserved; Herdrill has no picker.
    "goto": "prefix+g",
    "detach": "prefix+q",
    "reload_config": "prefix+shift+r",
    "open_notification_target": "prefix+o",
    "previous_workspace": "",
    "next_workspace": "",
    "previous_agent": "",
    "next_agent": "",
    "focus_agent": "",
    "new_tab": "prefix+c",
    "rename_tab": "prefix+shift+t",
    "previous_tab": "prefix+p",
    "next_tab": "prefix+n",
    "switch_tab": "prefix+1..9",
    "switch_workspace": "",
    "close_tab": "prefix+shift+x",
    "rename_pane": "prefix+shift+p",
    "edit_scrollback": "prefix+e",
    "copy_mode": "prefix+[",
    "focus_pane_left": "prefix+h",
    "focus_pane_down": "prefix+j",
    "focus_pane_up": "prefix+k",
    "focus_pane_right": "prefix+l",
    "swap_pane_left": "prefix+shift+h",
    "swap_pane_down": "prefix+shift+j",
    "swap_pane_up": "prefix+shift+k",
    "swap_pane_right": "prefix+shift+l",
    "cycle_pane_next": "prefix+tab",
    "cycle_pane_previous": "prefix+shift+tab",
    "last_pane": "",
    "split_vertical": "prefix+v",
    "split_horizontal": "prefix+minus",
    "close_pane": "prefix+x",
    "zoom": "prefix+z",
    "resize_mode": "prefix+r",
    "toggle_sidebar": "prefix+b",
}

# The published Herdrill fallback is the owner's layout. Agent chords are
# deliberately present but inert, preserving their meaning without assigning
# them to a game action.
HERDRILL_BINDINGS: dict[str, BindingSpec] = {
    "switch_workspace": "prefix+shift+1..9",
    "previous_workspace": "prefix+shift+k",
    "next_workspace": "prefix+shift+j",
    "switch_tab": "prefix+alt+1..9",
    "previous_tab": "prefix+shift+h",
    "next_tab": "prefix+shift+l",
    "focus_agent": "prefix+1..9",
    "previous_agent": "prefix+alt+k",
    "next_agent": "prefix+alt+j",
    "focus_pane_left": "prefix+h",
    "focus_pane_down": "prefix+j",
    "focus_pane_up": "prefix+k",
    "focus_pane_right": "prefix+l",
    "cycle_pane_next": "prefix+tab",
    "cycle_pane_previous": "prefix+shift+tab",
}

# Backwards-compatible public name used by tests and callers that construct the
# game's built-in keymap directly.
DEFAULT_BINDINGS = HERDRILL_BINDINGS

PANE_ACTIONS = {
    "focus_pane_left",
    "focus_pane_down",
    "focus_pane_up",
    "focus_pane_right",
    "cycle_pane_next",
    "cycle_pane_previous",
}
TAB_ACTIONS = {"switch_tab", "previous_tab", "next_tab"}
WORKSPACE_ACTIONS = {
    "switch_workspace",
    "previous_workspace",
    "next_workspace",
}

# These bindings only have meaning inside Herdr's navigate overlay. Herdrill
# intentionally has no workspace picker, so treating them as global controls
# would be inaccurate.
MODE_ONLY_FIELDS = {
    "navigate_workspace_up",
    "navigate_workspace_down",
    "navigate_pane_left",
    "navigate_pane_down",
    "navigate_pane_up",
    "navigate_pane_right",
}
NON_ACTION_FIELDS = {"prefix", "indexed", "command"}

_MODIFIER_ORDER = ("ctrl", "alt", "shift", "cmd", "super")
_MODIFIER_ALIASES = {
    "control": "ctrl",
    "option": "alt",
    "command": "cmd",
}
_KEY_ALIASES = {
    "-": "minus",
    ",": "comma",
    "+": "plus",
    "`": "backtick",
    "ampersand": "shift+7",
    " ": "space",
    "return": "enter",
    "escape": "esc",
}


def canonical_key(value: str) -> str:
    """Canonicalize modifier order and common Herdr key aliases."""
    raw = value.strip().lower()
    if not raw:
        return ""
    raw = _KEY_ALIASES.get(raw, raw)
    parts = raw.split("+")
    if len(parts) == 1:
        return _KEY_ALIASES.get(parts[0], parts[0])

    key = _KEY_ALIASES.get(parts[-1], parts[-1])
    modifiers: set[str] = set()
    extras: list[str] = []
    for part in parts[:-1]:
        modifier = _MODIFIER_ALIASES.get(part, part)
        if modifier in _MODIFIER_ORDER:
            modifiers.add(modifier)
        elif modifier:
            extras.append(modifier)
    ordered = [name for name in _MODIFIER_ORDER if name in modifiers]
    return "+".join([*ordered, *extras, key])


def default_config_path() -> str:
    configured = os.environ.get("HERDR_CONFIG_PATH")
    return os.path.abspath(os.path.expanduser(configured or CONFIG_PATH))


@dataclass
class Keymap:
    """Keystrokes resolved to actions, with control-source diagnostics."""

    prefix: str = DEFAULT_PREFIX
    bindings: dict[tuple[bool, str], tuple[str, int | None]] = field(
        default_factory=dict
    )
    source: str = "custom"
    config_path: str | None = None
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_bindings(
        cls,
        config: dict[str, BindingSpec],
        prefix: str = DEFAULT_PREFIX,
        overrides: dict[str, BindingSpec] | None = None,
        *,
        source: str = "custom",
        config_path: str | None = None,
        warnings: tuple[str, ...] = (),
    ) -> Keymap:
        """Build a map, then let explicit overrides displace defaults."""
        keymap = cls(
            prefix=canonical_key(prefix) or DEFAULT_PREFIX,
            source=source,
            config_path=config_path,
            warnings=warnings,
        )
        for action, spec in config.items():
            keymap._add(action, spec)
        for action, spec in (overrides or {}).items():
            keymap.remove_action(action)
            keymap._add(action, spec)
        return keymap

    @property
    def source_label(self) -> str:
        return {
            "herdr_config": "Herdr config",
            "herdr_defaults": "Herdr defaults",
            "herdrill_defaults": "Herdrill defaults",
            "herdrill_fallback": "Herdrill defaults (fallback)",
        }.get(self.source, "Custom controls")

    def _add(self, action: str, spec: BindingSpec) -> None:
        values = [spec] if isinstance(spec, str) else list(spec)
        for value in values:
            if not isinstance(value, str):
                continue
            for chord, index in _expand_spec(value, action):
                self.bindings[chord] = (action, index)

    def remove_action(self, action: str) -> None:
        self.bindings = {
            chord: resolved
            for chord, resolved in self.bindings.items()
            if resolved[0] != action
        }

    def resolve(self, prefixed: bool, key: str) -> tuple[str, int | None] | None:
        """Return ``(action, index)`` for a keystroke, if it is bound."""
        return self.bindings.get((prefixed, canonical_key(key)))

    def has_any(self, actions: set[str]) -> bool:
        return any(action in actions for action, _index in self.bindings.values())

    def bindings_for(self, action: str) -> tuple[str, ...]:
        """Return compact, human-readable bindings for an action."""
        labels: list[str] = []
        for (prefixed, key), (name, index) in sorted(self.bindings.items()):
            if name != action:
                continue
            stem = key.removesuffix(str(index)) if index is not None else key
            complete_range = index is not None and all(
                self.bindings.get((prefixed, f"{stem}{candidate}"))
                == (action, candidate)
                for candidate in INDEXES
            )
            shown = f"{stem}{INDEXED_SUFFIX}" if complete_range else key
            label = f"{self.prefix} {shown}" if prefixed else shown
            if label not in labels:
                labels.append(label)
        return tuple(labels)

    def binding_for(self, action: str) -> str | None:
        labels = self.bindings_for(action)
        return labels[0] if labels else None


def _expand_spec(
    spec: str,
    action: str | None = None,
) -> list[tuple[tuple[bool, str], int | None]]:
    raw = spec.strip().lower()
    if not raw:
        return []
    prefixed = raw.startswith(PREFIX_MARKER)
    rest = raw.removeprefix(PREFIX_MARKER) if prefixed else raw
    if rest.endswith(INDEXED_SUFFIX):
        stem = rest.removesuffix(INDEXED_SUFFIX)
        return [
            ((prefixed, canonical_key(f"{stem}{index}")), index)
            for index in INDEXES
        ]
    key = canonical_key(rest)
    if not key:
        return []
    if action in INDEXED_ACTIONS:
        final = key.rsplit("+", 1)[-1]
        if final not in "123456789":
            return []
        return [((prefixed, key), int(final))]
    return [((prefixed, key), None)]


def _spec_values(value: object) -> tuple[list[str], bool]:
    if isinstance(value, str):
        return [value], True
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value, True
    return [], False


def _apply_user_keys(
    keymap: Keymap,
    keys: dict[str, object],
    warnings: list[str],
) -> None:
    """Apply explicit fields, disabling ambiguous explicit chords."""
    claims: dict[tuple[bool, str], list[tuple[str, int | None]]] = {}

    for action, value in keys.items():
        if action in NON_ACTION_FIELDS or action in MODE_ONLY_FIELDS:
            continue
        values, valid = _spec_values(value)
        keymap.remove_action(action)
        if not valid:
            warnings.append(f"keys.{action} has an unsupported value and was disabled")
            continue
        for spec in values:
            expanded = _expand_spec(spec, action)
            if spec.strip() and not expanded:
                warnings.append(f"keys.{action} contains an invalid binding: {spec!r}")
            for chord, index in expanded:
                if "cmd+" in chord[1] or "super+" in chord[1]:
                    warning = (
                        f"keys.{action} uses {chord[1]}, which many terminals "
                        "cannot deliver"
                    )
                    if warning not in warnings:
                        warnings.append(warning)
                claims.setdefault(chord, []).append((action, index))

    indexed = keys.get("indexed")
    if isinstance(indexed, dict):
        legacy = {
            "tabs": "switch_tab",
            "workspaces": "switch_workspace",
            "agents": "focus_agent",
        }
        for field_name, action in legacy.items():
            modifier = indexed.get(field_name)
            if not isinstance(modifier, str) or not modifier.strip():
                continue
            # Explicit modern fields take precedence over legacy additions.
            if action in keys:
                continue
            keymap.remove_action(action)
            for chord, index in _expand_spec(
                f"{modifier.strip()}+{INDEXED_SUFFIX}", action
            ):
                claims.setdefault(chord, []).append((action, index))

    commands = keys.get("command")
    if isinstance(commands, list):
        for command_index, command in enumerate(commands):
            if not isinstance(command, dict):
                continue
            values, valid = _spec_values(command.get("key"))
            if not valid:
                continue
            action = f"custom_command_{command_index}"
            for spec in values:
                for chord, index in _expand_spec(spec):
                    claims.setdefault(chord, []).append((action, index))

    for chord, resolutions in claims.items():
        unique_actions = {action for action, _index in resolutions}
        if len(unique_actions) > 1:
            keymap.bindings.pop(chord, None)
            shown = _show_chord(keymap.prefix, chord)
            names = ", ".join(sorted(unique_actions))
            warnings.append(f"{shown} is ambiguous ({names}) and was disabled")
            continue
        keymap.bindings[chord] = resolutions[-1]


def _show_chord(prefix: str, chord: tuple[bool, str]) -> str:
    prefixed, key = chord
    return f"{prefix} {key}" if prefixed else key


def _missing_navigation(keymap: Keymap) -> list[str]:
    missing: list[str] = []
    pane_actions = {
        action
        for action, _index in keymap.bindings.values()
        if action in PANE_ACTIONS
    }
    has_pane_cycle = bool(
        pane_actions & {"cycle_pane_next", "cycle_pane_previous"}
    )
    has_all_directions = {
        "focus_pane_left",
        "focus_pane_down",
        "focus_pane_up",
        "focus_pane_right",
    }.issubset(pane_actions)
    if not has_pane_cycle and not has_all_directions:
        missing.append("pane")
    if not keymap.has_any(TAB_ACTIONS):
        missing.append("tab")
    if not keymap.has_any(WORKSPACE_ACTIONS):
        missing.append("space")
    return missing


def _fallback(warnings: list[str], config_path: str | None = None) -> Keymap:
    return Keymap.from_bindings(
        HERDRILL_BINDINGS,
        source="herdrill_fallback",
        config_path=config_path,
        warnings=tuple(warnings),
    )


def load(
    path: str | None = None,
    *,
    mode: str = CONTROL_AUTO,
    herdr_installed: bool | None = None,
) -> Keymap:
    """Resolve automatic Herdr controls or the built-in Herdrill profile."""
    if mode == CONTROL_HERDRILL:
        return Keymap.from_bindings(HERDRILL_BINDINGS, source="herdrill_defaults")

    config_path = os.path.abspath(os.path.expanduser(path)) if path else default_config_path()
    installed = shutil.which("herdr") is not None if herdr_installed is None else herdr_installed
    warnings: list[str] = []

    try:
        with open(config_path, "rb") as handle:
            data = tomllib.load(handle)
        config_found = True
    except FileNotFoundError:
        data = None
        config_found = False
    except (OSError, ValueError) as error:
        data = None
        config_found = os.path.exists(config_path)
        warnings.append(f"Could not read Herdr config: {error}")

    if data is None and not config_found and not installed:
        return Keymap.from_bindings(HERDRILL_BINDINGS, source="herdrill_defaults")

    source = "herdr_config" if isinstance(data, dict) else "herdr_defaults"
    if isinstance(data, dict) and not installed:
        warnings.append("Herdr executable was not found; using the saved config")
    keymap = Keymap.from_bindings(
        HERDR_DEFAULT_BINDINGS,
        source=source,
        config_path=config_path if config_found else None,
    )

    if isinstance(data, dict):
        keys = data.get("keys", {})
        if isinstance(keys, dict):
            prefix = keys.get("prefix", DEFAULT_PREFIX)
            if isinstance(prefix, str) and canonical_key(prefix):
                keymap.prefix = canonical_key(prefix)
            elif "prefix" in keys:
                warnings.append("keys.prefix is invalid; using ctrl+b")
            if "cmd+" in keymap.prefix or "super+" in keymap.prefix:
                warnings.append(
                    f"keys.prefix uses {keymap.prefix}, which many terminals cannot deliver"
                )
            _apply_user_keys(keymap, keys, warnings)
            direct_prefix = (False, keymap.prefix)
            if direct_prefix in keymap.bindings:
                action, _index = keymap.bindings.pop(direct_prefix)
                warnings.append(
                    f"{keymap.prefix} is the prefix and cannot also trigger {action}; "
                    "the direct action was disabled"
                )
        elif "keys" in data:
            warnings.append("[keys] is not a table; using Herdr defaults")

    missing = _missing_navigation(keymap)
    if missing:
        joined = ", ".join(missing)
        warnings.insert(
            0,
            f"Herdr controls have no supported {joined} navigation; "
            "using Herdrill defaults",
        )
        return _fallback(warnings, config_path if config_found else None)

    keymap.warnings = tuple(warnings)
    return keymap
