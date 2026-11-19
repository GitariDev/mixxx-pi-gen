# Wave I3, builder S8 (skin): the Sources side menu's shadow

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 1, s5 and **2d**, plan 12.9, and the mockups `mockups/m-sources-top.png` and `m-sources-sub.png`. Read the exact shadow values in `design/all-mockups.html` and `tokens.css`. The cards next to them are `deploy/ui-redesign-20261117/acceptance-E/pairs/m-sources-top.png` and `m-sources-sub.png`, untracked in the main checkout.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. It includes wave H1, the header's empty area.

## The owner's decision (spec 2d)
Draw the Sources side menu's shadow as the mockups do: the shadow on the menu's left edge, over the Tracks table. Use the colour, width and fall-off from the mockup source. It must be painted cheaply:
- a plain gradient (for example a narrow skin widget with a `qlineargradient` background, or a border-image) on the menu's left side;
- **not** `QGraphicsDropShadowEffect` or any Qt graphics effect, which is costly on the Pi.

It shows only while the menu is open, in both its top level and inside a source. It must not take touches: taps on the table under it still reach the table, or the strip sits only over the menu's own area. It must not change the menu's width, position or contents, or the narrowed table's fit.

## Files you own
`mixpi-performance.py`, `mixpi-sources-menu.qss`, `pioneered-touch.qss` and `mixpi-performance.qss` (only the rules you need), plus `tests/test_performance_skin.py` and `tests/test_pioneered_touch.py`.

No Mixxx source and no patches.

## Checks
- Generated-XML and stylesheet tests that pin the strip, its gradient values from the mockup, its show and hide binding, and the absence of any graphics effect.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiI3-s8-20261120 <your worktree> gate`;
  - never use `limactl`.
- Never touch the Raspberry Pi.
- Give the orchestrator a Pi check:
  - ☰ (772,72) on This Pi › Tracks: say which pixels left of the menu's edge should change, and to what values;
  - then confirm a tap on a table row next to the menu still selects it.
