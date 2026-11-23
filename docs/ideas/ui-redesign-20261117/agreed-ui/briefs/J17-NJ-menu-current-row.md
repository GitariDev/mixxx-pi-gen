# Wave J17, builder N-J17 (native): the menu's edge stays on the list in view

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` **2a** and **2e** with `mockups/m-sources-sub.png` (the current-row edge marks the list the table shows), the J16 brief `J16-NJ-menu-place.md` and its patch `mixxx-menu-place-fix.patch`, and council round 9 Opus `deploy/ui-redesign-20261117/council/round9-opus-5.5-xhigh.md` (Deviations, Blockers; untracked, in the main checkout).

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (72 patches; build P). You are the only builder running. Never edit an existing Mixxx patch. Make `mixxx-menu-current-row.patch`, placed last, with prerequisite `mixxx-menu-place-fix.patch`.

## The fault (confirmed on the card by the orchestrator, build P, 2026-11-23; shots `deploy/ui-redesign-20261117/acceptance-P/shots/o9-*.png`, samples at x 483)
1. GANDER1 BROWSE, ☰: inside, edge on TRACKS (`o9-1`).
2. Tap A - MAIN PLAYLIST: the table shows its one track, ☰ closes (`o9-2`).
3. ☰: edge on A - MAIN PLAYLIST (483,226) (`o9-3`). Correct.
4. Tap the empty part of the open menu (640,420): **no row has the edge** (`o9-4`). This press clears the current row (upstream `focusInEvent` → `clearCurrentIndex()`, kept by `mixxx-source-tap.patch`); true since the menu was built.
5. ✕ then ☰: **the edge is on TRACKS** while the table still shows A - MAIN PLAYLIST (`o9-5`). J16's `edgeShownDriveTracks` picks TRACKS whenever the current row is gone, without checking which list the table shows.

## What to build
- **In touch mode, a focus-in (a drag or a tap on an empty part of the menu) keeps the current row.** Skip the upstream `clearCurrentIndex()` there only when the touch menu is active; desktop behaviour unchanged.
- **J16's show-time restore edges the row whose list the table shows**: the shown drive's playlist (or folder row) if a playlist or folder list is in view, matched the way `RekordboxFeature::selectShownDriveTracks` matches the drive; TRACKS only when the drive's Tracks list is in view. If no row of the current level shows the list in view, leave the current row as it is (J16's other rules unchanged).
- Keep everything else exactly: J4, J5, J16's first-OPEN fix, the ★ start, BACK, the crumb, row taps, scrolling the menu by drag, and the source groups.

## Files you own
- the new patch; in the Mixxx source `src/widget/wlibrarysidebar.{h,cpp}` and, only if needed, `src/library/rekordbox/rekordboxfeature.{h,cpp}` (a read-only accessor for the shown list), and new files;
- new tests `tests/test_menu_current_row.py` and `tests/native/menu_current_row_*`; J16's tests only where they assert TRACKS for a case this brief changes (say which).

Do not edit the registries; give registration lines (and any "is last" assert changes).

## Checks
- **Native fixtures, each failing without your patch:** (a) a playlist picked, then a focus-in, `clearCurrentIndex()` and a model reset, each → ☰ → current = that playlist; (b) a press and a drag on an empty part of the open menu keep the current row; (c) TRACKS in view → focus-in → ☰ → TRACKS (J16 unchanged); (d) J4 and the first-OPEN case unchanged.
- All earlier source-menu, eject, media and J16 fixtures still pass.
- The Mac suite in a clean worktree: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (timing errors in `test_chroot_runtime` / `test_shutdown_order` under load: rerun alone).
- The full native gate on VM `b`, 0 skips, with your registration lines applied: `~/.config/mixpi-lima-b/vm-native.sh uiJ17-nj17-20261123 <your worktree> gate`. Check first that nothing heavy runs in the VM. Never use `limactl`. Keep 24 GB free in the VM, fstrim after cleanup, the Mac above 20 GiB.
- **Never touch the Raspberry Pi or any drive.** Open no window or app on the Mac.
- Give the orchestrator the Pi check: the five steps above (expect the edge on A - MAIN PLAYLIST at steps 4 and 5), and acceptance P's checks 1-5.
