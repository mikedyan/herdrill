# herdr-jump — design

**Date:** 2026-07-20
**Status:** Design approved, pending implementation plan

## Purpose

A terminal finger-agility drill for herdr navigation, stripped to its core. A
**box** appears in one pane of a herdr-shaped layout; the player's only job is to
move focus onto that pane using their real herdr keys, as fast as possible. Land
on it, a new box appears elsewhere. A round is 60 seconds; the score is how many
boxes were cleared.

This replaces the previous herdrill game entirely. Everything that accreted
around the original idea — a simulated fleet, permission prompts, work orders,
coaching, a tutorial, patience timers, priority scoring — is removed. What
remains is the one thing that was always the point: **jump to the thing, fast.**

## The core loop

1. A round begins immediately (no menu) and runs for 60 seconds.
2. A box is placed in one pane of the current board.
3. The player navigates focus with their herdr keys.
4. When the focused pane is the box's pane, the box is cleared: score += 1, and a
   new box is placed.
5. At 0 seconds the round ends and shows the final count and the best count.

There is no per-box timer and no early loss. The only pressure is the wall clock.
The box never spawns on the pane the player is already focused.

## It looks like herdr, simplified

The screen keeps the spatial skeleton that makes the skill transfer to the real
tool, and nothing else:

- **Sidebar** (left): the list of spaces, the active one marked.
- **Tab bar** (top): the tabs of the active space, the active one marked.
- **Pane area**: the active tab's split layout.

Simplifications from herdrill: no agents, no agent states or glyphs, no
permission prompts, no activity text, no work-order status, no score-stream
overlays. A pane is an empty box. The **focused** pane has a bright border. The
**target** pane holds the box — a distinct, high-contrast fill so it is
unmistakable. A single status line shows the clock and the score.

## The keys are the player's herdr config

Navigation bindings are read from `~/.config/herdr/config.toml`, exactly as the
current game does. Two pieces of the old code are carried into the new package
verbatim because they are correct and hard-won, and nothing else:

- `keymap.py` — parsing the config into a binding table and resolving keystrokes
  to actions.
- the input normalization from the old `main.py` — turning raw terminal bytes
  into key names, including the Option/Meta decoding that makes `alt+digit` work
  on stock macOS Terminal (`get_wch`/high-bit/ESC-prefix handling). This layer
  is the reason a real terminal's keys reach the game at all.

The only actions the game consumes:

- `switch_workspace` / `previous_workspace` / `next_workspace` — change space
- `switch_tab` — change tab
- `focus_pane_left` / `focus_pane_down` / `focus_pane_up` / `focus_pane_right` —
  move between panes
- `focus_agent` is **not** used (there are no agents). `goto`, `open_notification_target`,
  and every construction/other binding are ignored.

The prefix (default `ctrl+b`) is honored: a bound action is `prefix` then the
key, exactly as in herdr. A missing or malformed config falls back to herdr
defaults and never raises. Rebinding herdr rebinds the game.

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

## No menu, immediate start, best-score persistence

- Launching the game starts a round immediately. There is no difficulty or level
  menu.
- `esc` quits at any time. At the end-of-round screen, any key starts a new
  round; `esc`/`q` quits.
- The **best** count is persisted to a single small file
  (`~/.herdr-jump/best.json`), read at start and shown on the end screen. A
  missing or corrupt file reads as no best and never raises. Written atomically
  when a round beats the stored best.

## Architecture

A new, small package. Only the renderer and the loop import `curses`; only the
loop reads the clock. Every other module is pure and takes `now: float` /
`random.Random` as parameters, so the whole game is testable without a terminal.

| File | Responsibility |
|---|---|
| `board.py` | The board model: `Space` / `Tab` / split tree / `Pane`, focus, pane lookup; and geometry (split tree → rectangles, directional neighbour) |
| `ramp.py` | Tier table; `tier_for(cleared) -> Tier`; `build_board(tier, rng) -> Board` |
| `target.py` | Placing the box: pick a valid target pane given the board, the current focus, and whether the tier just changed |
| `keymap.py` | Reused from herdrill: parse the herdr config, resolve keystrokes to actions |
| `round.py` | Round state: clock, score, best; applies a navigation action to move focus; detects a clear and advances |
| `render.py` | Draw the sidebar, tab bar, panes, the box, and the status line (curses) |
| `main.py` | The input loop, key normalization, best-score I/O, the launch entry |
| `best.py` | Best-score load/save, atomic and corrupt-tolerant |

The geometry (split tree → rectangles, directional neighbour lookup) lives in
`board.py` with the model, not a separate file: they change together and are
small. This is a decision, not an option.

## Testing

- `board.py`, `ramp.py`, `target.py`, `round.py`, `best.py`, `keymap.py` — unit
  tested with pytest, headlessly. Run with `python3 -B -m pytest -q -p no:cacheprovider`.
- Key properties pinned: the box never spawns on the focused pane; a tier change
  regenerates to the right size and resets focus; clearing a box advances the
  score and places a new one; the round ends at 60 seconds; best-score is
  corrupt-tolerant.
- Directional pane navigation resolves against the real geometry, so it behaves
  like herdr in nested splits.
- `render.py` is tested against a fake stdscr that polices screen bounds and
  models curses' byte-clipping, asserting the box and focus marker actually reach
  the screen — not merely that drawing does not raise.
- A headless "play" harness drives a round with scripted keys and asserts the
  score and end state, so the loop is testable without curses.
- One pty test launches the real binary, sends real navigation bytes to clear at
  least one box, and reads the score back off the screen.

## Deliverables

- A new package launched by the existing `herdrill` command (the shim is
  repointed at the new entry, so how the game starts is unchanged).
- The previous herdrill game code and its tutorial/coaching/etc. are removed.

## Deferred

- Difficulty options or round lengths other than 60 seconds.
- Any sound.
- Leaderboards beyond a single local best.
