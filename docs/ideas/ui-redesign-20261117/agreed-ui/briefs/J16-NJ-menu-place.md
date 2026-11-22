# Wave J16, builder N-J16 (native): ☰ after OPEN always opens inside the drive with the edge on TRACKS

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` 2b, **2e** ("☰ after OPEN opens inside the drive, with the current-row edge on Tracks, as `m-sources-sub.png` draws it"), the J4/J5 brief `J4-J5-NJ-eject-open.md`, the council report `deploy/ui-redesign-20261117/council/round8-opus-5.5-xhigh.md` (Deviations) and the investigation `deploy/ui-redesign-20261117/investigation-R8-edge/REPORT.md` (both untracked, in the main checkout).

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (71 patches; build O). You are the only builder running. Never edit an existing Mixxx patch. Make `mixxx-menu-place-fix.patch`, placed last, with the prerequisites it needs (at least `mixxx-media-open-inside.patch`, `mixxx-sources-open-edge.patch`).

## The faults (spec 2e)
1. **Reproduced on the card (2 of 2):** after a Mixxx start, the first OPEN (or BROWSE, or a load from it) before ☰ has ever been shown makes ☰ open at the **top level** (edge on the drive's tile), not inside the drive. Cause: `openShownSource()` / `followShownSource()` return early while `m_sourceScreen` is false (`wlibrarysidebar.cpp:630`, `:655`), and the hidden sidebar only gets its width, and `m_sourceScreen`, when ☰ is first shown. Introduced by J5's guard.
2. **Seen once in acceptance M (`acceptance-M/shots/38-menu.png`):** ☰ opened inside "GANDER1 › rekordbox" with **no row edged**. Likely a cleared current row (focus-in `clearCurrentIndex()` at `:1429`, or a sidebar model reset → `rebuildSourceRail` → `openGroupedTile(id, false)`), with nothing putting it back.

## What to build
- An OPEN (or BROWSE) that happens while the sidebar has not yet been shown is remembered and applied when the menu first becomes the source screen: ☰ opens inside that drive, crumb "DRIVE › rekordbox" (or the folder case as J5 does), edge on TRACKS.
- Whenever ☰ is shown while the menu is inside a drive and the current row is not a visible row of that level, the current row is set to the shown drive's TRACKS row (the row J5 edges), so the edge is never missing.
- Keep everything else exactly: J4 (after an eject, top level, no edge on a row not in view), J5, J10, J11, J12, the ★ start, BACK, the crumb, taps on rows, and the source-group behaviour. Do not change what the table shows.

## Files you own
- the new patch; in the Mixxx source `src/widget/wlibrarysidebar.{h,cpp}` and, only if needed, the sidebar model or `src/library/rekordbox/rekordboxfeature.cpp` around `selectShownDriveTracks`, and new files;
- new tests `tests/test_menu_place_fix.py` and `tests/native/menu_place_fix_*`.

No skin files and no stylesheets. Do not edit the registries; give registration lines (and any "is last" assert changes).

## Checks
- **Native fixtures, each failing without your patch:** (a) a sidebar never shown (width 0) → OPEN path → show and resize → inside, crumb, current = TRACKS; (b) inside with the edge → `clearCurrentIndex()`, a focus-in, and a model reset, each → show ☰ → current = TRACKS; (c) J4: after an eject the menu opens at the top level with no edge on a row not in view (unchanged).
- All earlier source-menu, eject, media, Folders-eject, removable-rows and open-remount fixtures still pass.
- The Mac suite in a clean worktree: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (rerun `test_chroot_runtime` alone if its timeout trips).
- The full native gate on VM `b`, 0 skips, with your registration lines applied: `~/.config/mixpi-lima-b/vm-native.sh uiJ16-nj16-20261123 <your worktree> gate`. Check first that nothing heavy runs in the VM (`ssh -F ~/.config/mixpi-lima-b/ssh.config lima-b-durable 'pgrep -af "[b]uild.sh|[n]inja|[c]make --build|[c]test"'`). Never use `limactl`. Keep 24 GB free in the VM, fstrim after cleanup, the Mac above 20 GiB.
- **Never touch the Raspberry Pi or any drive.** Open no window or app on the Mac.
- Give the orchestrator the Pi check with coordinates: restart Mixxx, OPEN GANDER1 with no ☰ before it, then ☰ (inside, edge on TRACKS); then LOAD 1, play, pause, unload, ☰ again (edge on TRACKS); then J4 (eject → ☰ top level).
