# Herdrill

[![tests](https://github.com/mikedyan/herdrill/actions/workflows/tests.yml/badge.svg)](https://github.com/mikedyan/herdrill/actions/workflows/tests.yml)

> **Aim training for your terminal-multiplexing fingers.**

Targets appear. Panes multiply. The clock is rude. Navigate with your real
[Herdr](https://herdr.dev) controls and discover whether those shortcuts are
muscle memory—or merely optimistic documentation.

Herdrill is a 60-second terminal game about getting to the right pane as fast
as possible. Clear enough targets and the board adds tabs, spaces, and
increasingly unreasonable demands on your spatial memory. It is less painful
than learning in production and more socially acceptable than blaming your keyboard.

## The highly sophisticated rules

1. A red target appears in a pane.
2. Move focus to that pane.
3. Feel briefly unstoppable.
4. Repeat until the clock reaches zero.

The board becomes more complicated after 5, 10, and 15 clears. Your score is
saved to a local leaderboard, complete with the date and exact time of your
triumph—or cautionary tale.

## Install before your confidence returns

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

## It borrows your controls, politely

Herdrill starts in **Automatic** control mode. It checks `$HERDR_CONFIG_PATH`
and then `~/.config/herdr/config.toml`, layers your custom bindings over
Herdr's built-in controls, and uses the result in the game. It reads only the
`[keys]` table and never edits your Herdr config. No shortcuts are harmed in
the making of this drill.

The game understands:

- directional and cyclic pane focus
- direct and cyclic tab selection
- direct and cyclic workspace selection, called **spaces** in the game
- custom prefixes, direct chords, binding arrays, and indexed `1..9` bindings

There is deliberately no workspace picker. Agent, layout, command, and other
unsupported actions remain inert while reserving their configured chords. That
prevents Herdrill from teaching a key to do something your real setup says it
does not.

If Herdr is unavailable—or its controls cannot reach every part of the
game—Herdrill falls back to its complete built-in profile and explains why in
Settings. You can also select **Herdrill defaults** manually whenever you want
a known layout instead of your everyday configuration.

### Built-in controls

| Destination | Binding |
|---|---|
| Move between panes | `prefix+h/j/k/l` |
| Previous/next pane | `prefix+Shift+Tab` / `prefix+Tab` |
| Jump to tab 1–9 | `prefix+Option+1..9` |
| Previous/next tab | `prefix+Shift+H/L` |
| Jump to space 1–9 | `prefix+Shift+1..9` |
| Previous/next space | `prefix+Shift+K/J` |

`prefix+1..9` remains reserved for agents and is intentionally inert. The game
has no agents; it already has you.

On stock macOS Terminal, composed Option+digit characters are normalized to
the corresponding `alt+digit` bindings.

## Buttons worth knowing

- Enter or Space — start a round
- `s` — open settings
- `q` or Escape — quit from a menu
- Escape during a round — abandon the evidence

Settings show the resolved control source, effective navigation bindings, and
any import warnings. They also offer ten macOS system sounds with previews,
because clearing a target should sound at least slightly important. Muting is
available for people with dignity.

## Scores, shame, and local files

Everything stays on your computer:

- Settings: `~/.herdrill/settings.json`
- Leaderboard: `~/.herdrill/leaderboard.json`

Herdrill stores up to 100 results and displays the top 10. Writes are atomic,
malformed files do not prevent startup, and older single-best data is migrated
automatically. There are no accounts, analytics, uploads, seasons, battle
passes, or suspiciously valuable terminal cosmetics.

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
