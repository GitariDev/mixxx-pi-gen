# Wave J6, builder N-J6 (native): sorting a drive's list never empties the table

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` section 2c (one column setup for every source, sort per list) and 2e.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Another builder (N-J4) is adding patches after `mixxx-quit-library-widget.patch` in parallel, in the sidebar and media files. Never edit an existing Mixxx patch. Make `mixxx-external-sort.patch`; the orchestrator will place it in `MIXXX_PATCHES` after N-J4's patches, so it must not depend on them.

## The fault (seen by the owner on the card, 2026-11-20 16:03)
On a rekordbox drive list (IXIAN › Smarties › Jazz, 36 tracks), tapping the KEY header emptied the table. The log:

```
basetrackcache.cpp 510 FAILED QUERY [ "SELECT id FROM rekordbox_library ORDER BY CASE key_id WHEN NULL THEN 0 ... END ASC, bpm DESC, lower(artist) COLLATE mixxxLexicographicalCollationFunc ASC" ] QSqlError("", "Unable to fetch row", "No query")
```

Cause (stock Mixxx 2.5.6): `ColumnCache` (`src/library/columncache.cpp` ~:259) sorts KEY by `CASE key_id ...`, but `rekordbox_library` (`src/library/rekordbox/rekordboxfeature.cpp` ~:80-100) has only `key TEXT`, no `key_id`. The query fails and the table shows nothing. Tapping another header brings the rows back.

## What to build (owner: "Let's fix that for all columns where this could happen.")
- **Audit every column's sort expression** in `ColumnCache` / `BaseTrackCache` / the table models against **every external library table** Mixxx can show: rekordbox, Serato, Traktor, iTunes, Rhythmbox, Banshee, and any other `BaseExternal*` / `BaseTrackCache` user, plus the folder browse and Load sample models. List each column whose sort SQL names a column that table lacks, or whose sort otherwise fails there.
- **Make every such sort work:**
  - KEY sorts in the same order as on This Pi (circle of fifths in the user's key notation), derived from the table's key text when there is no `key_id`. If that cannot be done safely in SQL, sort by the key text and say why.
  - Any other failing column sorts by its own shown value.
- **A failed sort must never leave an empty table.** If a sort query still fails for any reason, keep the rows in the previous order (and log it), rather than showing nothing.
- Change nothing for This Pi's own library, nothing in the column setup, and never write to a drive.

## Files you own
- the new patch;
- new tests `tests/test_external_sort.py` and `tests/native/external_sort_*`;
- in the Mixxx source: `src/library/columncache.{h,cpp}`, `src/library/basetrackcache.{h,cpp}`, `src/library/basesqltablemodel.{h,cpp}`, `src/library/rekordbox/*`, `src/library/serato/*`, `src/library/traktor/*`, `src/library/itunes/*`, `src/library/rhythmbox/*`, `src/library/banshee/*`, `src/library/baseexternal*`, and new files.

No skin files and no sidebar or media files (N-J4 owns those). Do not edit the registries; give the orchestrator your registration lines.

## Checks
- **Native fixtures:** a rekordbox-style table (and each other external table the audit flags) sorted by every shown column, ascending and descending: rows are never 0, and KEY's order matches This Pi's for the same keys. Show the KEY fixture failing without your patch.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (`test_chroot_runtime`'s 5 s timeout can trip under load; rerun it alone).
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ6-nj6-20261120 <your worktree> gate`;
  - never use `limactl`. Keep at least 24 GB free in the VM, and run `fstrim` after cleanup.
- **Never touch the Raspberry Pi.** The owner is playing on it.
- Give the orchestrator a Pi check with coordinates: IXIAN (the owner's drive, read only) › a playlist › tap each header, KEY included.
