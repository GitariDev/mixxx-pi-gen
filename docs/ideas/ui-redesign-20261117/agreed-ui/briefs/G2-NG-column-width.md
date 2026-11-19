# Wave G2, builder N-G2 (native): a re-shown column keeps its saved width

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` section **2c**, plan 12.7, the build F builder brief `briefs/F1-NF-columns.md`, and acceptance F's report `deploy/ui-redesign-20261117/acceptance-F/ACCEPTANCE.md`. Read the report's summary, row 5c, note N1 and FAIL repro 1. The evidence is untracked, in the main checkout.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (after `mixxx-overview-playposition.patch`). Never edit an existing Mixxx patch. Make `mixxx-shared-columns-width.patch` after the last one in `MIXXX_PATCHES` (`mixxx-overview-playposition.patch`). Its prerequisite is `mixxx-shared-columns.patch`.

## The owner's request
- The spec 2c request, verbatim: "I want to keep the column setup across the different source menus and have it be saved after edit like the settings." Their choice: columns, order and widths shared.
- On 2026-11-19 they chose "Fix both" for build G. That covers the overview fix and this one.

## The fault (acceptance F, FAIL 1, row 5c)
A column hidden and then shown again, through ✎ › Arrange columns (or the header menu), comes back at 160 px instead of its saved width:
- BPM came back at 160 px instead of 100;
- KEY at 160 px instead of 50;
- `#` at 160 px instead of 30.

The 160 px is then saved to `[Library],SharedColumns` and shared to every list at once. While the column is hidden, `SharedColumns` still holds the old width (`key hidden=1 width=50`). Qt's own hide and show keeps a section's size, so the width is lost somewhere in build B's or `mixxx-shared-columns.patch`'s show path. Find where first and write it in your report.

## What to build
- A column shown again comes back at the width it had before it was hidden. This holds when it is hidden in one list and shown in another (repro B).
- That width is what gets saved and shared.
- Nothing else changes:
  - a column never shown before keeps build B's default width;
  - the narrowed fit with Sources open is still never saved;
  - the sort stays per list;
  - a change is saved within 1 s, and a burst gives one write;
  - the first-run migration is unchanged.
- **Optional, only if it is the same code path:** acceptance F note N1. Every start rewrites `SharedColumns` once, about 6 s after launch, with no user change: TITLE's stored stretched width goes back to 160, and hidden widths go from 0 to 20. If your fix makes that start-up write a no-op without new behaviour, do it and say so. Otherwise leave it and say why.

## Files you own
- the new patch;
- `tests/test_shared_columns.py`, `tests/native/shared_columns_*` and new tests;
- in the Mixxx source, the files `mixxx-shared-columns.patch` touches: `src/widget/wtracktableviewheader.{h,cpp}`, `src/widget/wtracktableview.{h,cpp}`, `src/widget/wlibrarytableview.{h,cpp}`, `src/widget/mixpitablefit.h`, the shared-columns files the patch added, and new files.

No skin files and no stylesheets. Do not edit the registries `01-run.sh`, `tests/test_mixxx_patches.py` or `tools/performance/required-native.py`; give the orchestrator your registration lines.

## Checks
- **Native fixtures:**
  - hide and show in one list keeps the width (BPM 100, KEY 50, `#` 30);
  - hide in one model and show in another keeps the width;
  - the saved line has the old width after the show;
  - a never-shown column gets the default width;
  - all of build F's shared-columns fixtures still pass.
  - Show that the new fixture fails without your patch.
- The Mac suite.
- The full native gate on VM `b` with your registration lines applied, 0 skips. VM workspace `uiG2-ng-20261119`, temp tree `/tmp/g2-ng-src`. Keep at least 24 GB free in the VM, and run `fstrim` after cleanup.
- Never touch the Raspberry Pi; the owner is using it.
- Give the orchestrator Pi checks with coordinates: acceptance F repro A and repro B, with the expected widths.
