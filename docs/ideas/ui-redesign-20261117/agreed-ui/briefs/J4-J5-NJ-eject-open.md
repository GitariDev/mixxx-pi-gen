# Waves J4 and J5, builder N-J4 (native): the menu and table after an eject, and ☰ after OPEN

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 1, s5, 2b and **2e** (the owner's decisions of 2026-11-20, which win over 2b), the mockup `mockups/m-sources-sub.png`, and acceptance I `deploy/ui-redesign-20261117/acceptance-I/ACCEPTANCE.md`: row 3f, repro 1, and the X1 repro's note on the stale table. The shots are in `acceptance-I/shots/` (`c4o-d-open.png`, `c4o-e-menu.png`, `c4o-f-mainpl.png`, `c3o-l-menu.png`, `c5-r-menu.png`). The evidence is untracked, in the main checkout.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Build I (59 patches) is on the card; build J's crash fix `mixxx-quit-library-widget.patch` is the last patch in `MIXXX_PATCHES`. Never edit an existing Mixxx patch. Add new patches after it, with the prerequisites they need: `mixxx-eject-top-menu.patch` (J4) and `mixxx-media-open-inside.patch` (J5). One patch for both is fine if they cannot be separated cleanly; say why.

## J4: after an eject (owner: "Let just land on the top menu instead")
- **Today:** after a drive is ejected, the Tracks table keeps showing that drive's rows until another list is picked, and ☰ opens with its edge on This Pi (`c5-r-menu.png`).
- **Build:** when the drive whose list is in the Tracks table is ejected (from the Media page, or pulled out):
  - the table stops showing its rows: no rows from a drive that is gone, ever;
  - the Sources menu's place goes to the **top level**, so the next ☰ opens there;
  - nothing is selected in the menu (no current-row edge on a row that is not in view), unless build B's top-level rules already mark a row.
- **What the empty table looks like:** whatever Mixxx draws with no list selected (build B). Do not add a message or another view.
- When a different drive is ejected, or the list in view is This Pi's, nothing changes.
- The saved ★ start is not changed. If the ★ start is the ejected drive, the next start falls back as today.
- Keep the clean eject: the drive's views are released (`refreshMediaLifecycle`), and nothing is written to the drive.

## J5: ☰ after OPEN opens inside the drive (owner: "Open the drive.")
- **Today:** after OPEN on the Media page, ☰ opens at the top level with the edge on the drive row (`c4o-e-menu.png`); one more tap goes inside (`c4o-f-mainpl.png`).
- **Build:** after any path that opens a drive's Tracks (OPEN and BROWSE on the Media page, and the plug-in ping's LOAD), the next ☰ opens **inside "DRIVE › rekordbox"** with the current-row edge on **Tracks**, as `m-sources-sub.png` draws it. This must hold even when the menu was last left elsewhere, and after an eject and re-plug (acceptance I repro 1).
- Find the cause first and write it in your report. Wave E1 (`mixxx-sources-open-edge.patch`) set the menu's current source and edge to the drive; the place stayed at the top level.
- Keep: BACK from inside goes to the top level with the edge on the drive; the ★ start; the narrowed fit; the shadow strip; the ping timing (15 s from the plug-in, unchanged by the owner's decision).

## Files you own
- the new patch or patches;
- `tests/test_source_groups.py`, `tests/native/source_groups_*`, `tests/test_media_agreed.py`, `tests/native/media_*`, and new tests;
- in the Mixxx source: `src/widget/wlibrarysidebar.{h,cpp}`, `src/widget/touchsourcenavigation.h`, `src/library/library.{h,cpp}`, `src/widget/libraryinterface.h`, `src/library/mixpimedia.h`, `src/library/mixpimediapage.h`, `src/library/mixpiopentracks.h`, `src/library/rekordbox/*` (only to release a view), and new files.

No skin files and no stylesheets. Do not edit the registries; give the orchestrator your registration lines.

## Checks
- **Native fixtures:**
  - J4: a drive's list in the table, then the drive ejected: the table has 0 rows from it, and the menu's place is the top level. The same with the drive pulled (unmounted without the page). Ejecting another drive leaves the table alone.
  - J5: OPEN, BROWSE and ping LOAD, each from a menu left inside This Pi and from one left inside the same drive before an eject and re-plug: the menu's place is "DRIVE › rekordbox" with the edge on Tracks.
  - Show each new fixture failing without your patch.
  - All earlier source-group and media fixtures still pass.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`. (`test_chroot_runtime`'s 5 s timeout can trip under full-suite load; rerun it alone.)
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ4-nj4-20261120 <your worktree> gate`;
  - never use `limactl`. VM b's Lima files were lost to the macOS `/tmp` cleanup; that helper reaches it over SSH.
  - Keep at least 24 GB free in the VM, and run `fstrim` after cleanup.
- **Never touch the Raspberry Pi.** The owner is playing on it.
- Give the orchestrator Pi checks with coordinates. **Re-plugs are done by the owner's hand: never switch a USB port off,** and do not write any check that does.
