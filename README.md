# Herdrill

[![tests](https://github.com/mikedyan/herdrill/actions/workflows/tests.yml/badge.svg)](https://github.com/mikedyan/herdrill/actions/workflows/tests.yml)

> **Aim training for your terminal-multiplexing fingers.**

Herdrill is a 60-second terminal game: a target lights up in a pane, and you
get there using your real [Herdr](https://herdr.dev) bindings. Clear enough
targets and the board adds tabs, then spaces, then doubts. It is the fastest
known way to discover that `prefix+Shift+3` is not, in fact, muscle memory yet.

## Rules

1. A red target appears in a pane.
2. Move focus to that pane.
3. Repeat until the clock reaches zero.

The board gets more complicated after 5, 10, and 15 clears. Every score is
saved to a local leaderboard with a full timestamp, so there is a permanent
record either way.

## Install

Herdrill requires Python 3.11+ and has no third-party runtime dependencies.

```sh
git clone https://github.com/mikedyan/herdrill.git
cd herdrill
python3 -m pip install .
herdrill
```

To try it without installing:

```sh
./bin/herdrill
# or
python3 -m herdrill
```

## Controls

Herdrill starts in **Automatic** control mode. It checks `$HERDR_CONFIG_PATH`
and then `~/.config/herdr/config.toml`, layers your custom bindings over
Herdr's built-in controls, and uses the result in the game. It reads only the
`[keys]` table and never writes to your Herdr config.

The game understands:

- directional and cyclic pane focus
- direct and cyclic tab selection
- direct and cyclic workspace selection, called **spaces** in the game
- custom prefixes, direct chords, binding arrays, and indexed `1..9` bindings

There is deliberately no workspace picker. Agent, layout, command, and other
unsupported actions stay inert but keep their configured chords reserved, so
the game can never teach your fingers something your real setup will refuse
to honor.

If Herdr is unavailable—or its controls cannot reach every part of the
game—Herdrill falls back to its complete built-in profile and explains why in
Settings. You can also select **Herdrill defaults** manually whenever you want
a known layout instead of your everyday configuration.

### Built-in profile

| Destination | Binding |
|---|---|
| Move between panes | `prefix+h/j/k/l` |
| Previous/next pane | `prefix+Shift+Tab` / `prefix+Tab` |
| Jump to tab 1–9 | `prefix+Option+1..9` |
| Previous/next tab | `prefix+Shift+H/L` |
| Jump to space 1–9 | `prefix+Shift+1..9` |
| Previous/next space | `prefix+Shift+K/J` |

`prefix+1..9` remains reserved for agents and is intentionally inert. The game
has no agents. It has you.

On stock macOS Terminal, composed Option+digit characters are normalized to
the corresponding `alt+digit` bindings.

## Menu keys

- Enter or Space — start a round
- `s` — open settings
- `q` or Escape — quit from a menu
- Escape during a round — end it early

Settings show the resolved control source, the effective navigation bindings,
and any import warnings. They also offer ten macOS system sounds with
previews. There is a mute option.

## Local files

Everything stays on your computer:

- Settings: `~/.herdrill/settings.json`
- Leaderboard: `~/.herdrill/leaderboard.json`

Herdrill stores up to 100 results and displays the top 10. Writes are atomic,
malformed files do not prevent startup, and older single-best data is migrated
automatically. There are no accounts, no analytics, no uploads, and no battle
pass.

## Development

```sh
python3 -B -m pytest -q -p no:cacheprovider
```

The board, difficulty ramp, target placement, round state, keymap import,
leaderboard, settings, and persistence are tested headlessly. A real PTY test
also launches the executable and sends actual terminal bytes, because mocking
a keyboard is easy and trusting one is how we got here.

The implementation design lives in
[`docs/2026-07-20-herdrill-design.md`](docs/2026-07-20-herdrill-design.md).
