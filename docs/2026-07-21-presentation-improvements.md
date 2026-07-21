# Presentation improvements

**Date:** 2026-07-21
**Status:** Active

The goal is to make the drill feel like a native, simplified Herdr screen while
keeping the target immediately recognizable.

## Implemented

- Replace the dense filled target with a compact outlined target card.
- Use a small diamond fallback when a pane cannot fit the full card.
- Give active navigation a periwinkle-blue selection with dark text.
- Show target locations with a red diamond rather than a yellow row fill.
- Make active, target, and inactive styles mutually exclusive; highlighted text
  never inherits the dim attribute.
- Replace heavy double focus borders with crisp blue single-line borders.
- Render structural lines through ncurses' terminfo-backed ACS line API instead
  of sending Unicode border strings. This uses the terminal's native continuous
  line-drawing set and matches Herdr's plain square-corner geometry.
- Add a dark tab rail with compact numbered tabs.
- Replace the white reverse-video footer with a dark, restrained status line.
- Use a muted charcoal, lavender, blue, and red terminal palette, with a safe
  eight-colour fallback.
- Make the focused pane border bright blue and move inactive structural borders
  to a much darker blue-gray.
- Keep pane surfaces visible in prefix mode; rely on the brighter focused border
  and substantially darker inactive borders for location awareness.
- Add a starting-screen settings menu with automatic Herdr control import,
  a resettable built-in control profile, effective-binding diagnostics, ten
  previewable target sounds, and a persisted mute option.

## Next passes

- Review a fresh screenshot in the owner's real terminal and tune indexed
  colours for that profile.
- Rebalance the pane area and any unused space at common window sizes.
- Refine sidebar spacing, hierarchy, and target/active markers.
- Tune typography density and end-of-round presentation.
- Verify tiny nested panes remain clear in every difficulty tier.
