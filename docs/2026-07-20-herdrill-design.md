# Herdrill — design

**Date:** 2026-07-20
**Status:** Implemented; updated with presentation and leaderboard additions

## Purpose

A terminal finger-agility drill for Herdr navigation, stripped to its core. A
**box** appears in one pane of a Herdr-shaped layout; the player's only job is to
move focus onto that pane using their real Herdr keys, as fast as possible. Land
on it, a new box appears elsewhere. A round is 60 seconds; the score is how many
boxes were cleared.

This replaces the previous Herdrill game entirely. Everything that accreted
around the original idea — a simulated fleet, permission prompts, work orders,
coaching, a tutorial, patience timers, priority scoring — is removed. What
remains is the one thing that was always the point: **jump to the thing, fast.**

## The core loop

1. A starting screen shows the local leaderboard; Enter or Space begins a round.
2. The round runs for 60 seconds and places a box in one pane of the board.
3. The player navigates focus with their Herdr keys.
4. When the focused pane is the box's pane, the box is cleared: score += 1, and a
   new box is placed.
5. At 0 seconds the player enters a name. The score and current local date and
   time are saved, then the ranked leaderboard is shown.

There is no per-box timer and no early loss. The only pressure is the wall clock.
The box never spawns on the pane the player is already focused.

## It looks like Herdr, simplified

The screen keeps the spatial skeleton that makes the skill transfer to the real
tool, and nothing else:

- **Sidebar** (left): the list of spaces, the active one marked.
- **Tab bar** (top): the tabs of the active space, the active one marked.
- **Pane area**: the active tab's split layout.

Simplifications from Herdrill: no agents, no agent states or glyphs, no
permission prompts, no activity text, no work-order status, no score-stream
overlays. A pane is an empty box. The **focused** pane has a bright, single-line
border. The **target** pane holds a compact red outline card so it is clear
without becoming a dense block. Active navigation uses a high-contrast blue
selection; target navigation uses a red marker, and neither state is dimmed.
Inactive pane borders are substantially darker than the bright blue focused
border, but pane surfaces are never blacked out. A single dark status line shows
the clock and the score.

## The keys are the player's Herdr config

Control mode defaults to **Automatic**. Herdrill checks `$HERDR_CONFIG_PATH`
and then `~/.config/herdr/config.toml`. A valid `[keys]` table is layered over
Herdr's built-in controls so omitted fields retain their real Herdr meanings.
String and array bindings, custom prefixes, direct chords, indexed `1..9`
bindings, and the legacy `[keys.indexed]` table are accepted. Herdrill only
reads this config and never changes it.

If no Herdr config or executable is present, the complete Herdrill profile is
used. The controls settings screen can force that profile even when Herdr is
installed, return to Automatic, reload the file, and inspect the effective
bindings and warnings. The setting is persisted atomically.

The actions the game consumes are:

- `switch_workspace` / `previous_workspace` / `next_workspace` — change space
- `switch_tab` / `previous_tab` / `next_tab` — address or cycle tabs
- `focus_pane_left` / `focus_pane_down` / `focus_pane_up` /
  `focus_pane_right` — move geometrically between panes
- `cycle_pane_next` / `cycle_pane_previous` — cycle through a tab's panes in
  stable tree order with wraparound

There is deliberately no workspace picker. Agent, construction, layout,
notification, custom-command, and other unsupported actions do not execute,
but their explicit chords remain reserved so a collision cannot accidentally
train a different game action. Ambiguous explicit bindings are disabled and
reported. A Herdr map without supported pane, tab, or space navigation falls
back to the complete Herdrill profile rather than generating unreachable
targets.

The Herdrill profile uses `prefix+h/j/k/l` and Tab/Shift+Tab for panes,
`prefix+alt+1..9` and `prefix+shift+h/l` for tabs, and
`prefix+shift+1..9` and `prefix+shift+k/j` for spaces. Plain prefixed numbers
remain reserved for unsupported agents. The prefix defaults to `ctrl+b`.
Terminal input normalization includes Option/Meta decoding for macOS Terminal,
modifier-order normalization, function keys, Shift+Tab, and named punctuation.

Reaching the box is defined purely by focus: when the focused pane's id equals
the target pane's id, the box is cleared. How the player got there — direct
addressing, pane movement, space/tab switching — does not matter.

## The ramp

Board size is a stepped function of boxes cleared this round:

| Boxes cleared | Spaces | Tabs / space | Panes / tab |
|---|---|---|---|
| 0–4 | 1 | 1 | 2 |
| 5–9 | 2 | up to 2 | 2–3 |
| 10–14 | 3 | up to 2 | 2–3 (deeper splits) |
| 15+ | 4 | up to 3 | nested splits |

**Within a tier** the board is fixed: the box teleports to a new pane and the
player navigates from wherever their focus currently is. This is the main skill —
routing from your current position to the target.

**Crossing a tier boundary** (clearing box 5, 10, 15) regenerates the board at
the new, larger size. On regeneration, focus resets to a known origin (the first
pane of the first space's first tab), and the new box is placed far from that
origin. The reset happens only a few times per round; it gives a clean "new
bigger board" beat and avoids the disorientation of the structure changing under
the player mid-jump.

Board generation is deterministic given a seed and a tier, through an injected
`random.Random`, so every unit is reproducible.

## Target placement

When a box is placed:

- It must land on a pane that is **not** the currently focused pane.
- Within a tier (same board), it is drawn from all panes except the current one.
- On a tier change, it is placed on a pane in a different space from the origin
  when the tier has more than one space, so the first jump of a new tier is a
  genuine cross-space move; otherwise a different pane.

A board always has at least two panes, so a valid non-current target always
exists.

## Starting screen and local leaderboard

- Launching the game shows a starting screen with the top ten local records.
  Enter/Space begins, `s` opens settings, and `esc`/`q` quits. There is no
  difficulty or level menu.
- The top-level settings menu opens Controls or Target sound. Controls selects
  Automatic or Herdrill defaults and shows the resolved map. Target sound offers
  ten distinct macOS system cues; Enter/Space saves and previews, number keys
  select directly, and `m` mutes. Both preferences are persisted atomically in
  `~/.herdrill/settings.json`.
- Clearing a target plays the selected cue asynchronously through macOS
  `afplay`; a new cue replaces any cue still playing, so game input never waits.
- `esc` quits a live round. At 0 seconds a required name prompt accepts printable
  text and backspace; Enter saves and Escape cancels/quits.
- Every saved result includes player name, score, and an ISO local date plus
  `HH:MM:SS` time. Up to 100 results are persisted atomically in
  `~/.herdrill/leaderboard.json`; malformed files and rows never prevent startup.
- The former `{\"best\": n}` format is migrated using the file modification
  date and time. Records created before time tracking display `--:--:--`.
- The results screen shows the top ten records. Any key starts a new round;
  `esc`/`q` quits.

## Architecture

A new, small package. Only the renderer and the loop import `curses`; only the
loop reads the clock. Every other module is pure and takes `now: float` /
`random.Random` as parameters, so the whole game is testable without a terminal.

| File | Responsibility |
|---|---|
| `board.py` | The board model: `Space` / `Tab` / split tree / `Pane`, focus, pane lookup; and geometry (split tree → rectangles, directional neighbour) |
| `ramp.py` | Tier table; `tier_for(cleared) -> Tier`; `build_board(tier, rng) -> Board` |
| `target.py` | Placing the box: pick a valid target pane given the board, the current focus, and whether the tier just changed |
| `keymap.py` | Parse the Herdr config and resolve keystrokes to actions |
| `round.py` | Round state: clock, score, best; applies a navigation action to move focus; detects a clear and advances |
| `render.py` | Draw the sidebar, tab bar, panes, the box, and the status line (curses) |
| `main.py` | The input loop, key normalization, start/name/results flow, the launch entry |
| `leaderboard.py` | Ranked records, name cleanup, migration, and atomic persistence |
| `settings.py` | Corrupt-tolerant sound and control-mode preference persistence |
| `sound.py` | Ten system-sound definitions and non-blocking `afplay` playback |
| `best.py` | Compatibility wrappers for the former single-best API |

The geometry (split tree → rectangles, directional neighbour lookup) lives in
`board.py` with the model, not a separate file: they change together and are
small. This is a decision, not an option.

## Testing

- `board.py`, `ramp.py`, `target.py`, `round.py`, `leaderboard.py`, `settings.py`, `sound.py`, `best.py`, `keymap.py` — unit
  tested with pytest, headlessly. Run with `python3 -B -m pytest -q -p no:cacheprovider`.
- Key properties pinned: the box never spawns on the focused pane; a tier change
  regenerates to the right size and resets focus; clearing a box advances the
  score and places a new one; the round ends at 60 seconds; leaderboard
  persistence and legacy migration are corrupt-tolerant.
- Directional pane navigation resolves against the real geometry, so it behaves
  like Herdr in nested splits.
- `render.py` is tested against a fake stdscr that polices screen bounds and
  models curses' byte-clipping, asserting the box and focus marker actually reach
  the screen — not merely that drawing does not raise.
- A headless "play" harness drives a round with scripted keys and asserts the
  score and end state, so the loop is testable without curses.
- One pty test launches the real binary, sends real navigation bytes to clear at
  least one box, and reads the score back off the screen.

## Deliverables

- A new package launched by the `herdrill` command (the shim is
  repointed at the new entry, so how the game starts is unchanged).
- The previous Herdrill game code and its tutorial/coaching/etc. are removed.

## Deferred

- Difficulty options or round lengths other than 60 seconds.
