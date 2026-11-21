# Wave J11, builder N-J11 (native): Removable devices keeps rows that are not drives

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` 2e and 2g, the J10 brief `J10-NJ-folders-eject.md`, and council round 6 Fable's report `deploy/ui-redesign-20261117/council/round6-fable-5.2-high.md` (untracked).

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (67 patches; the last is `mixxx-eject-folders-view.patch`). You are the only builder running. Never edit an existing Mixxx patch. Make `mixxx-removable-rows-fix.patch`, placed last, with prerequisite `mixxx-eject-folders-view.patch`.

## The fault (council round 6, Fable; confirmed on the card)
- J10's `BrowseFeature::releaseGoneFolder()` (`mixxx-eject-folders-view.patch` :92-103) removes from Folders › Removable Devices **every row whose path is not in the mount table**, on any mount change (plug-in, pull, eject).
- On the card, Removable Devices lists `/media/SD-Backup`, a plain folder on the Pi's own SD card (empty, owned by pi; not a mount). J10 drops it on any mount change. It returns only when the list is opened again. Shot: `deploy/ui-redesign-20261117/acceptance-K/shots/70-now.png` (untracked, in the main checkout) shows only IXIAN.
- Build B, and stock Mixxx, list it. Acceptance K's "stock Mixxx" note on this was wrong.

## What to build
- The pull/eject pruning drops **only a row that was a drive's mount point and is no longer mounted**, for example by remembering the mount points last seen. A plain folder such as `/media/SD-Backup` is never dropped, whether drives come or go.
- Keep everything else J10 does exactly: the shown folder is released and ☰ goes to the top level after an eject or a pull; a pulled drive leaves Removable Devices; `/` never counts as gone; nothing is read from or written to a drive.
- Also report whether a **newly plugged** drive appears in an already open Removable Devices list. Acceptance K saw it stay stale until reopened. Fix it only if it is the same small change and matches build B's behaviour when the list is opened again; otherwise report it.

## Files you own
- the new patch;
- new tests `tests/test_removable_rows_fix.py` and `tests/native/removable_rows_fix_*`, or new checks added to J10's fixture files `tests/native/eject_folders_view_*` and `tests/test_eject_folders_view.py`;
- in the Mixxx source: `src/library/browse/*` and new files.

Do not edit the registries; give the orchestrator your registration lines. If `test_eject_folders_view.py` or `test_zoom_setting.py` checks that its patch is last, give the exact change needed as a registration line.

## Checks
- **Native fixture:** a Removable Devices list with a plain folder (like `/media/SD-Backup`) and two drive mounts. Pull one drive, then eject the other through the Media path, then plug a drive in:
  - the plain folder stays listed throughout;
  - a gone drive's row goes;
  - every J10 check still passes.
- Show the new checks failing without your patch.
- The Mac suite in a clean worktree: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ11-nj11-20261121 <your worktree> gate`;
  - never use `limactl`. Keep at least 24 GB free in the VM, fstrim after cleanup, and keep the Mac above 20 GiB.
- **Never touch the Raspberry Pi or any drive.** Open no window or app on the Mac.
- Give the orchestrator a Pi check with coordinates.
