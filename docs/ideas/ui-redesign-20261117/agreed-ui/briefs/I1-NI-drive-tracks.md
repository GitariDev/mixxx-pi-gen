# Wave I1, builder N-I1 (native): a "Tracks" row inside a rekordbox drive

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 1, s5 and **2d**, plan 12.9, and the mockup `mockups/m-sources-sub.png`. The card next to it is `deploy/ui-redesign-20261117/acceptance-E/pairs/m-sources-sub.png`. The evidence is untracked, in the main checkout.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Build H (56 patches) is on the test card. Never edit an existing Mixxx patch. Make `mixxx-drive-tracks-row.patch` after the last one in `MIXXX_PATCHES` (`mixxx-shared-columns-stretch.patch`), with the prerequisites it needs.

## The owner's decision (spec 2d)
Build it as the mockup draws it. Inside "DRIVE › rekordbox" in the Sources side menu, the **first row is "Tracks"**. It has the music-note icon This Pi's Tracks row uses and no ›. Picking it shows **every track in the drive's rekordbox export** in the Tracks table, like any other list. The drive's real playlists and folders follow as now. The mockup's playlist names and counts are example data; do not change them or their order.

Today Mixxx's rekordbox reader lists playlists and folders only: `RekordboxFeature`, `src/library/rekordbox/rekordboxfeature.{h,cpp}` in the pinned 2.5.6, which reads the export's database through kaitai. Find how it builds its tree and its playlist track models. Then add an all-tracks node that reads every track entry in the export, the same way a playlist's tracks are read. The table gets the shared columns (spec 2c), its own sort, and loading to decks and pads, like any rekordbox list.

Keep everything else:
- the ★ start and the menu's current-row edge (it must work on the new row too);
- the narrowed fit;
- OPEN and BROWSE;
- eject: a drive with this row in view must still eject cleanly, with the views released (`refreshMediaLifecycle`);
- read-only drives: **never write to the drive**.

## Files you own
- the new patch;
- `tests/test_source_groups.py`, `tests/native/source_groups_*`, and new tests;
- in the Mixxx source, `src/library/rekordbox/*`, plus `src/widget/wlibrarysidebar.{h,cpp}` and `src/widget/touchsourcenavigation.h` only if the row needs them.

No skin files and no stylesheets. Do not edit the registries; give the orchestrator your registration lines. Another builder (N-I2) works on the USB chip and ping in `src/library/mixpimedia.h` and the media files, so do not touch those.

## Checks
- **Native fixtures:**
  - a fake rekordbox export with N tracks across playlists, including tracks in no playlist: the Tracks row is first and lists all N;
  - loading a track from it works;
  - the edge sits on the row when it is in view;
  - an eject with the row in view works.
  - Show the fixture failing without your patch.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiI1-ni1-20261120 <your worktree> gate`;
  - never use `limactl`;
  - VM b's Lima files were lost to the macOS `/tmp` cleanup, so that helper reaches it over SSH.
  - Temp tree `/tmp/i1-ni1-src`.
- Never touch the Raspberry Pi.
- Give the orchestrator Pi checks with coordinates. Use GANDER1 (the owner's spare stick, read only, with a rekordbox export of a few playlists): TRACKS › ☰ › GANDER1 › rekordbox › Tracks.
- **If the export format makes an all-tracks list impossible or unsafe,** stop and report why. Do not invent another layout.
