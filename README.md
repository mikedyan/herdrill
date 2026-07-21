# Herdrill

An independent implementation of the approved **Herdrill** design: a
60-second terminal finger-agility drill for your real Herdr navigation keys.
The source design is snapshotted at
[`docs/2026-07-20-herdrill-design.md`](docs/2026-07-20-herdrill-design.md).

A box appears in a pane. Move focus to it, clear it, and repeat. The board grows
at 5, 10, and 15 clears. A starting screen shows the local leaderboard before
each session; the drill itself remains focused entirely on spatial routing
under a wall clock.

## Install and run

Requires Python 3.11+ and has no third-party runtime dependencies.

From a source checkout:

```sh
cd herdrill
python3 -m pip install .
herdrill
```

Without installing, run `./bin/herdrill` or `python3 -m herdrill` from the
checkout.

## Herdr controls

Controls default to **Automatic**. Herdrill checks `$HERDR_CONFIG_PATH` and
then `~/.config/herdr/config.toml`; a valid config is layered over Herdr's
built-in bindings, including its configured prefix and string or array
bindings. If neither a config nor the `herdr` executable is present, Herdrill
uses its own built-in profile. Herdrill only reads Herdr's `[keys]` table and
never edits it.

Herdrill models directional and cyclic pane focus, direct and cyclic tab
selection, and direct and cyclic workspace selection (called spaces in the
game). It deliberately does not implement the Herdr workspace picker. Agent,
layout, command, and other unsupported actions stay inert while reserving
their configured chords, so the game does not train a conflicting action.
A control set without supported pane, tab, or space navigation safely falls
back to the complete Herdrill profile and reports why in settings.

The built-in profile is:

- `prefix+h/j/k/l` and `prefix+Tab` / `prefix+Shift+Tab` for panes
- `prefix+Option+1..9` and `prefix+Shift+H/L` for tabs
- `prefix+Shift+1..9` and `prefix+Shift+K/J` for spaces
- `prefix+1..9` remains reserved for agents and is inert

On stock macOS Terminal, composed Option+digit characters are normalized to
the corresponding `alt+digit` bindings. The focused pane uses a bright blue
border against much darker inactive borders, keeping the current position
clear without blacking out other panes.

Press Enter or Space on the starting screen to begin, `s` to open settings,
or `q`/`esc` to quit. Controls can be switched between **Automatic** and
**Herdrill defaults**, and the effective bindings and import warnings are
shown in the controls screen. The sound screen offers ten macOS system sounds
with in-menu preview and a mute option. Settings are saved atomically in
`~/.herdrill/settings.json`.

`esc` quits a live round. After 60 seconds, enter a player name and press Enter
to save the score. The results screen shows the ranked score, player name, and
record date and time; any key returns to the starting screen.

Up to 100 local results are stored atomically in
`~/.herdrill/leaderboard.json`, and
the top 10 appear on the starting and results screens. Existing single-best
files are migrated into the leaderboard automatically.

## Development

```sh
python3 -B -m pytest -q -p no:cacheprovider
```

The board, ramp, target placement, round, keymap, leaderboard, settings, and
persistence are headlessly tested. Only `render.py` and `main.py` import
curses; only `main.py` reads the clock.
