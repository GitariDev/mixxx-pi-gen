# Wave J10, builder N-J10 (native): an eject also clears a drive's Folders view

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` 2e and **2g**, and the J4 brief `J4-J5-NJ-eject-open.md`. J4's patch is `mixxx-eject-top-menu.patch`.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (66 patches; the last is `mixxx-zoom-setting.patch`). You are the only builder running. Never edit an existing Mixxx patch. Make `mixxx-eject-folders-view.patch`, placed last, with the prerequisites it needs (probably `mixxx-eject-top-menu.patch`).

## The fault (seen on the card, 2026-11-21 19:3x, build J)
- **Steps:**
  1. Sources › Folders › Removable devices › GANDER1 › Contents › "21 Savage Metro Boomin Drake" › SAVAGE MODE II. The table shows the folder's file ("43 - Mr. Right Now…").
  2. Close the menu, then open the Media page and eject GANDER1 (clean eject: DONE).
  3. Close the page.
- **Result:**
  - the table still shows GANDER1's file row;
  - ☰ opens at "Folders" (its own level), not at the top level.
- **Shots** (untracked, in the main checkout): `deploy/ui-redesign-20261117/acceptance-J/shots/201-folders-gander1-before-eject.png`, `202-folders-table-after-eject.png`, `203-menu-after-folders-eject.png`.
- **Likely cause (check it):** J4 releases the table and resets the menu only for rekordbox lists (`RekordboxFeature::releaseRemovedDrives` and the sidebar's handling). The Browse feature (`src/library/browse/*`, `BrowseTableModel`, `BrowseFeature`) keeps the folder path and its rows when the mount goes away.

## What to build (spec 2e, as 2g applies it)
- When a drive is ejected (from the Media page, or pulled out) and the table shows a folder on that drive through Folders:
  - the table stops showing its rows (what Mixxx draws with no list selected, as J4 does);
  - the Sources menu's place goes to the top level, with no edge on a row not in view, exactly as J4.
- The same for Quick links or `/` paths that lie on that drive's mount.
- When a different drive is ejected, or the folder is not on the ejected drive, nothing changes.
- Keep J4's rekordbox behaviour, J5, the clean eject, the ★ start, and never write to a drive.
- Also check whether Folders › Removable devices itself still lists the ejected drive after the eject. If it does, it should drop it like the Media page does. Report what you find; fix it only if it is in the same small change.

## Files you own
- the new patch;
- new tests `tests/test_eject_folders_view.py` and `tests/native/eject_folders_view_*`;
- in the Mixxx source: `src/library/browse/*`, `src/widget/wlibrarysidebar.{h,cpp}`, `src/library/library.{h,cpp}`, `src/library/mixpimedia.h` (only to hand the eject to Browse), and new files.

No skin files and no stylesheets. Do not edit the registries; give the orchestrator your registration lines.

## Checks
- **Native fixture:** a folder on a fake mount shown in the Browse table, then the mount removed through the same path an eject takes: 0 rows from it, and the menu's place is the top level. The same for a pull with no Media page. A different mount's removal leaves the table alone. Show the fixture failing without your patch.
- All earlier eject, source-group and media fixtures still pass.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`, in a clean worktree, so untracked `.claude/` folders don't reach the VM.
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ10-nj10-20261121 <your worktree> gate`;
  - never use `limactl`. Keep at least 24 GB free in the VM, run `fstrim` after cleanup, and keep the Mac above 20 GiB free.
- **Never touch the Raspberry Pi or any drive.** Open no window or app on the Mac.
- Give the orchestrator the Pi check from the steps above, with coordinates. Re-plugs are done by the owner's hand; never switch a USB port off.
