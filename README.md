# Herdrill-ChatGPT

An independent implementation of the approved **herdr-jump** design: a
60-second terminal finger-agility drill for your real herdr navigation keys.
The source design is snapshotted at
[`docs/2026-07-20-herdr-jump-design.md`](docs/2026-07-20-herdr-jump-design.md).

A box appears in a pane. Move focus to it, clear it, and repeat. The board grows
at 5, 10, and 15 clears. There are no menus, agents, prompts, work orders, or
coaching—just spatial routing under a wall clock.

## Run

```sh
cd /Users/mike/code/herdrill-chatgpt
./herdrill-chatgpt
```

Or:

```sh
python3 -m herdrill_chatgpt
```

Requires Python 3.11+ and no third-party runtime packages.

The game reads `~/.config/herdr/config.toml`, including the configured prefix
and workspace/tab/pane bindings. Missing or malformed config falls back to
herdr defaults. On stock macOS Terminal, composed Option+digit characters are
normalized to the corresponding `alt+digit` bindings.

`esc` quits a live round. After 60 seconds, any key starts another round;
`q`/`esc` quits. The local best is stored atomically in
`~/.herdr-jump/best.json`.

## Development

```sh
python3 -B -m pytest -q -p no:cacheprovider
```

The board, ramp, target placement, round, keymap, and persistence are pure and
headlessly tested. Only `render.py` and `main.py` import curses; only `main.py`
reads the clock.
