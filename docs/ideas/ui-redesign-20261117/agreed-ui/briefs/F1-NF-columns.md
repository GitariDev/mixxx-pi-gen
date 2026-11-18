# Wave F1, builder N-F (native): one shared column setup, saved on change

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 2a, 2b and **2c**, and plan 12.7 and R-13 (save on change).

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Build E (52 patches) is on the test card. Never edit an existing Mixxx patch: make `mixxx-shared-columns.patch` after the last one in `MIXXX_PATCHES` (`mixxx-sampler-clear-playing.patch`).

## The owner's request (verbatim)
"I want to keep the column setup across the different source menus and have it be saved after edit like the settings." Their choice: **columns, order and widths shared; sorting stays per list.**

## What to build
1. **One column setup for every track table:** This Pi › Tracks, playlists, crates, Auto DJ, History, folders, each drive's rekordbox lists, and the Samples table in Load sample.
   - Which columns show, their order and their widths are the same everywhere.
   - A column that a table does not have (for example `#` outside a playlist, or PREVIEW) is skipped there and keeps its place for tables that have it.
   - Sorting stays per list, as today.
   - Today Mixxx keeps the header state per table model (find where: `WTrackTableViewHeader` save and restore, and the model's setting keys) and writes it when a view goes away.
2. **Saved within one second of each change** (show or hide a column through Arrange columns or the header menu, move one, resize one), like the settings. It must survive `kill -9` and a power cut: use the config and its save-on-change path (R-13, `mixxx-save-on-change.patch` and `mixxx-save-within-second.patch`), or another atomic write. A burst of changes during a drag gives one write.
3. **The first time it runs,** the shared setup starts from This Pi › Tracks' current setup. The owner's existing per-source setups are not lost: leave the old keys in place, unused.
4. **The narrowed table** with Sources open (`mixxx-table-fit-media-open.patch`, builder N-D2) keeps fitting its columns. Fitted widths are never saved, so the shared full widths come back when the table widens.
   - Acceptance E saw once: after ✕ in Edit sources, the Tracks table kept its narrowed columns until a restart. Make sure every way of closing Sources or Edit sources restores the full widths.
   - Add a fixture for this.

## Files you own
The new patch; `tests/test_table_columns.py`, `tests/native/table_columns_*`, new tests (`tests/test_shared_columns.py`, `tests/native/shared_columns_*`). Mixxx source: `src/widget/wtracktableviewheader.{h,cpp}`, `src/widget/wtracktableview.{h,cpp}`, `src/widget/wlibrarytableview.{h,cpp}`, the track models' header-state code (`src/library/basetracktablemodel.*`, `src/library/trackmodel.h`, and the like), `src/widget/mixpitablefit.h`, and new files. No skin files or stylesheets.

## Checks
Native fixtures:
- one setup across at least three different models, including a playlist with `#` and a browse or rekordbox model;
- skipped columns keep their place;
- the sort stays per list;
- a change is on disk within 1 s, and a burst gives one write;
- the setup is kept after a kill;
- the first-run migration from This Pi's setup;
- the narrowed fit never saved, and full widths back after every close path.

Also run the Mac suite, and the full native gate on VM `b` with your registration lines applied, 0 skips. VM workspace `uiF1-nf-20261118`, temp tree `/tmp/f1-nf-src`. Give the orchestrator Pi checks with coordinates (see `ACCEPTANCE-C-tester.md`'s hit map).
