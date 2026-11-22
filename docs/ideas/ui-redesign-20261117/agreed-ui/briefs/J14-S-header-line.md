# Wave J14, builder S-J14 (skin): the header's 1 px bottom line runs the full width

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` **2h** (the owner chose B), the H1 brief `H1-S7-header-strip.md`, and the round 4 council notes on listed item 4 (`deploy/ui-redesign-20261117/council/round4-opus-5.5-xhigh.md` around line 97, untracked, in the main checkout).

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (70 patches; build M). You are the only builder running.

## What to build (spec 2h, option B)
- In the Tracks table header, the part past the last section (seen when the columns do not fill the width, e.g. after TITLE is dragged narrower) gets the same **1 px `#2c333d` bottom line** the sections have, running to the scroll bar.
- Comparison the owner chose from: `deploy/ui-redesign-20261117/header-line-choice-20261122/01-header-line-A-without-B-with.png` and `02-header-line-full-screen-A-B.png` (B), drawn on `acceptance-I/shots/c1-a-title-left.png`.
- **Unchanged:** the header's height (34 px sections; no 1 px growth, the concern of wave H1), the sections' look (one 1 px line under them, not two), the empty area's `#1d222a`, every other table and header, and every other page.
- Prefer a stylesheet change in `pioneered-touch.qss` (the `#LibraryWrapper WTrackTableViewHeader` rules). Round 4's untested idea: `border-bottom: 1px solid #2c333d` on the header widget, which may double the line under the sections or change the height; check both. A native change only if the stylesheet cannot do it (stop and ASK first).

## Files you own
- `stage3/01-install-packages/files/pioneered-touch.qss` (the header rules only);
- `tests/test_performance_skin.py` (new tests only) or a new `tests/test_header_line.py`.

Do not edit the registries; give registration lines if any.

## Checks
- **An offscreen render at 800×480 on VM b** of the Tracks page with the real stylesheets, columns narrower than the table: the line runs the full width under the empty part at the same y as under the sections (1 px, `#2c333d`), the header height is unchanged against a render without your change, and there is one line, not two, under the sections. Give pixel samples (as round 4 did: x 300, 600, 700, 740, 770 at y 130-133) and the two renders side by side.
- A skin test that fails without your change.
- The Mac suite in a clean worktree: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (rerun `test_chroot_runtime` alone if its 5 s timeout trips).
- The full native gate on VM `b`, 0 skips: `~/.config/mixpi-lima-b/vm-native.sh uiJ14-sj14-20261122 <your worktree> gate`. Never use `limactl`. Keep at least 24 GB free in the VM, fstrim after cleanup, and keep the Mac above 20 GiB free.
- **Never touch the Raspberry Pi or any drive.** Open no window or app on the Mac.
- Give the orchestrator the Pi check with coordinates (drag TITLE's edge narrower, shoot the header, then drag it back to restore the owner's column widths).
