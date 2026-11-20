# Wave J3, builder S10 (skin): the USB chip's colours as the mockups draw them

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 0 and 1, especially lines 21-22 ("colours and states") and the control-roles table around line 54 (a current Navigate control gets an accent marker, not a tint). Read s13 Media and 2a-2d too. Then:
- council round 4, Opus deviation 1: `deploy/ui-redesign-20261117/council/round4-opus-5.5-xhigh.md`, section "Deviations from the spec that are not in the lists";
- the pair `deploy/ui-redesign-20261117/acceptance-I/pairs/m-media.png`;
- the shots `acceptance-I/shots/c4-c-media-inuse.png`, `a02-menu.png` and `c3-r-loaded.png`.

These are untracked, in the main checkout.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names.

## The faults (Opus, round 4)
1. **The chip while the Media page is open.**
   - **Mockup:** `m-media.png` draws the chip `is-live`, the chip's plain fill `#1d222a` with a 1 px accent border (`design/all-mockups.html:685-688`, `design/layout.css:17-20`).
   - **Card:** the lit "Choose" look, a 26 % tint `#3f4c37` with a 2 px accent border (`mixpi-performance.qss:107-112`, added in `5752aac` after build C). That commit's comment says "as the gear is on Settings", but the mockups draw the gear `is-on` and the chip `is-live`, which are different.
   - **Make the open-page chip `is-live` as drawn.** The chip must still show that the Media page is open: that was the point of `5752aac`'s repair, "the tab stayed lit and the chip did not". `is-live` (the accent border) is how the mockup shows it.
2. **The state word on every screen.**
   - **Mockups:** READY is `--mx-play` `#5fae6e` and IN USE is `--mx-info` `#5aa4c4` (`all-mockups.html:693-694`; sampled `#5eac6d` and `#59a2c2`).
   - **Card:** the lighter `#7cc58a` and `#86c0d8` (`mixpi-performance.qss:118-119`). Use the mockup values.
   - **Check the other states** (EJECTING, SAFE TO REMOVE, NO USB, the scan %) against the mockups and `tokens.css`, and change only those that differ. List them all.

Keep build B's fonts and the chip's size and layout.

## Files you own
`mixpi-performance.qss` (the chip rules only) and `tests/test_performance_skin.py` (the chip tests).

Do not touch `mixpi-sources-menu.qss`, `pioneered-menus.qss` or `pioneered-touch.qss`: builder S9 is changing the Sources menu's case in parallel. No Mixxx source.

## Checks
- Stylesheet tests that pin each rule and colour.
- An offscreen render on VM b of the chip in each state (rest, Media page open, READY, IN USE) with the real stylesheets, sampled against the mockup pixels.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ3-s10-20261120 <worktree> gate`;
  - never use `limactl`.
- Never touch the Raspberry Pi.
- Give the orchestrator a Pi check: the chip at (527,24) at rest, with the Media page open, and READY and IN USE. Give the expected pixels.
