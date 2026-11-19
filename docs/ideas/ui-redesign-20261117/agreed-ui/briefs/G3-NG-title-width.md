# Wave G3, builder N-G3 (native): never save TITLE's stretched width

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` section 2c, plan 12.7-12.8, `briefs/F1-NF-columns.md` and `briefs/G2-NG-column-width.md`, and acceptance G's report `deploy/ui-redesign-20261117/acceptance-G/ACCEPTANCE.md`: the summary, row 5b and FAIL repro 1. The evidence is untracked, in the main checkout.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Never edit an existing Mixxx patch. Make `mixxx-shared-columns-stretch.patch` after the last one in `MIXXX_PATCHES` (`mixxx-shared-columns-width.patch`). Its prerequisite is `mixxx-shared-columns-width.patch`.

## The fault (acceptance G, FAIL 1, row 5b; a regression from wave G2)
- **The bad save:** on This Pi › Tracks, TITLE is drawn stretched to fill the row: 424 px on screen, against a saved 160. Any column change there then saves TITLE's drawn width into `[Library],SharedColumns`. One Arrange-columns hide and show of Key stores TITLE at 424; a column drag stores 364.
- **What the owner sees:** the browse tables (a folder, and Load sample › SAMPLES) also show FILENAME. With the wide TITLE they get a sideways scroll bar, and BPM and KEY go off screen. This stays after a restart.
- **Why build F hid it:** build F rewrote `SharedColumns` at every start (acceptance F note N1), which put TITLE back to 160 by accident. G2 removed that write, rightly, so the wide width now stays.

## What to build
- **Behaviour to match:** build F after a start. The saved width of the column a table stretches to fill the row (TITLE on Tracks) is its own set width, never the stretched on-screen width.
- **Then:**
  - every table that shows more columns (FILENAME in folders and Load sample) fits as on build F, with no sideways bar;
  - Tracks still draws TITLE stretched, as now.
- **First, find out how the stretch is done:** build B's fill logic, Qt's stretch mode, `mixpitablefit.h`, or something else. Write it in your report.
- **Keep G2's fixes:**
  - a re-shown column keeps its width;
  - no write at start or when a list opens.
- **Keep everything else in spec 2c:**
  - a change is saved within 1 s, and a burst gives one write;
  - the sort stays per list;
  - the narrowed fit with Sources open is never saved.
- **If the owner drags TITLE's own edge:** keep what build F stored after its next start. If that cannot be told apart cleanly, say so in your report and keep TITLE's set width.
- **The owner's current line already holds `title` 160.** Do not migrate or rewrite it.

## Files you own
- the new patch;
- `tests/test_shared_columns.py`, `tests/native/shared_columns_*` and new tests;
- in the Mixxx source, the files `mixxx-shared-columns.patch` and `mixxx-shared-columns-width.patch` touch (`src/widget/wtracktableviewheader.{h,cpp}`, `src/widget/wtracktableview.{h,cpp}`, `src/widget/wlibrarytableview.{h,cpp}`, `src/widget/mixpitablefit.h`, the shared-columns files), and new files.

No skin files and no stylesheets. Do not edit the registries; give the orchestrator your registration lines.

## Checks
- **Native fixtures:**
  - a stretched TITLE on a wide table, then an Arrange hide and show of another column: TITLE's saved width stays at its set width;
  - the same after a drag of another column's edge;
  - a second model with FILENAME plus the shared columns at 800 px fits with no horizontal scroll;
  - all of build F's and G2's fixtures still pass.
  - Show that the new fixture fails without your patch.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b` with your registration lines applied, 0 skips. VM workspace `uiG3-ng-20261119`, temp tree `/tmp/g3-ng-src`. Keep at least 24 GB free in the VM, and run `fstrim` after cleanup.
- Never touch the Raspberry Pi.
- Give the orchestrator Pi checks with coordinates: acceptance G repro 1, with the expected `title` value and the Load sample and folder layout.
