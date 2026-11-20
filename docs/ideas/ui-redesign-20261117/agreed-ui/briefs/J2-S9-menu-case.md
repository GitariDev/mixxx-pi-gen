# Wave J2, builder S9 (skin): the Sources menu rows in the mockups' case

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 0 and 1, especially **line 15 (mockup labels are exact copy)** and the Fonts row with section 2a. Read s5 Sources and 2d too. Then:
- council round 4, Sol's D1/B2: `deploy/ui-redesign-20261117/council/round4-gpt-6.1-sol-xhigh.md`;
- acceptance I N4 and the pairs `deploy/ui-redesign-20261117/acceptance-I/pairs/m-sources-top.png` and `m-sources-sub.png`.

These are untracked, in the main checkout.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Build I is on the card, and build J's native fix is on the branch.

## The fault
Every row in the Sources side menu is drawn in upper case on the card ("TRACKS", "A - MAIN PLAYLIST", "DRAKE SHIT"). The mockups draw the rows in the source's own case: "Tracks", "Playlists", "Afro house", and the This Pi and drive rows in `m-sources-top.png`.

Sol traced the cause. The Pioneered stylesheet's `#LibraryWrapper WLibrarySidebar { text-transform: uppercase; }` (generated `style.qss` around line 292) is inherited by the Sources menu's row delegate (`mixxx-sources-menu.patch`, the delegate around line 1085). Check how Qt and Mixxx actually apply it, whether through `text-transform` or a font capitalization, before you change anything.

**The owner's 2a decision keeps build B's font family, size and weight.** Case is not part of it, and the mockups' copy binds the case.

## What to build
- The Sources side menu draws each row's text in its own case, as the mockups do, at both the top level and inside a source.
  - Use the narrowest selector that reaches the menu: the scoped menu selector in `mixpi-sources-menu.qss`, or a rule after the Pioneered one.
  - Keep build B's family, size and weight.
- **Check the case of every text in the menu against the mockups:** the row titles, subtitles, the place label ("MANTACORE › rekordbox"), BACK, EDIT, and the Edit sources rows.
  - Where a mockup draws upper case (for example BACK), keep it.
  - Change only what differs from the mockups. List each text with its mockup case and its card case before and after.
- Do not change other sidebars or other screens unless the mockups draw them differently from the card. If they do, list them and stop for the orchestrator.

## Files you own
`mixpi-sources-menu.qss`, `pioneered-menus.qss`, `pioneered-touch.qss` (only if the rule must live there), and `tests/test_pioneered_touch.py` / `tests/test_performance_skin.py` / `tests/test_source_groups.py` (stylesheet parts only).

No Mixxx source and no patches. If case can only be fixed natively (for example the delegate forces capitalization), stop and report.

## Checks
- A stylesheet test that pins the rule.
- An offscreen render on VM b of the Sources menu rows with the real stylesheets, as builder S7 did, showing "Tracks" in mixed case.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ2-s9-20261120 <worktree> gate`;
  - never use `limactl`.
- Never touch the Raspberry Pi.
- Give the orchestrator a Pi check with coordinates.
