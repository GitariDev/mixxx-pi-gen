# Wave H1, builder S7 (skin): theme the header's empty area

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 1 (the colour tokens) and 2c. The evidence:
- acceptance H `deploy/ui-redesign-20261117/acceptance-H/ACCEPTANCE.md`, check 4, with `shots/c4-c-title-drag-left.png` and `c4-c-zoom.png`;
- council round 3: `deploy/ui-redesign-20261117/council/round3-*.md` (listed item 9). All three seats name this as a blocker.

The evidence is untracked, in the main checkout.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Build H (56 patches) is on the test card.

## The fault
On This Pi › Tracks, dragging TITLE's edge narrower leaves a light-grey (`#efefef`) strip at the right end of the table header until the edge is dragged back. Nothing is saved, which is right (wave G3). The strip is the header's own area past the last section, and it has no stylesheet colour, so Qt's default light grey shows. Spec section 1 allows only the agreed tokens.

## What to build
- Give the header's empty area the colour the spec and mockups use for the table header. Read the header colour from `m-tracks.png`, `m-loadsample.png`, `design/all-mockups.html` and `tokens.css`, and check it against the header sections drawn on the card.
- Apply it wherever the track table header is used: Tracks, Load sample, the narrowed table with Sources open, and folders.
- Find the right selector (for example `WTrackTableViewHeader` or `QHeaderView` in the library's stylesheets). Check that no other header, such as Settings or Edit sources, changes.
- Change nothing else: no layout, no font, no section colours.

## Files you own
`pioneered-touch.qss`, plus `pioneered-menus.qss` or `mixpi-performance.qss` if the table header rules live there, and `tests/test_pioneered_touch.py` / `tests/test_performance_skin.py`.

No Mixxx source and no patches.

## Checks
- A stylesheet test that pins the rule and its colour.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips, because some native runners apply the stylesheets.
  - **VM b's Lima files were damaged by the macOS `/tmp` cleanup.** Reach it only with `ssh -F ~/.config/mixpi-lima-b/ssh.config lima-b-durable`.
  - Never run `limactl stop` or `limactl start` on `b`.
  - Run the gate with `~/.config/mixpi-lima-b/vm-native.sh WORKSPACE CHECKOUT gate`. It is the usual helper, sending every VM command over that SSH path, and it was checked on 2026-11-20. Do not use `limactl shell b`.
  - VM workspace `uiH1-s7-20261120`.
- Never touch the Raspberry Pi.
- Give the orchestrator a Pi check: drag TITLE's edge from (424,108) to (364,108) on This Pi › Tracks, and say what colour the right end of the header must then be.
