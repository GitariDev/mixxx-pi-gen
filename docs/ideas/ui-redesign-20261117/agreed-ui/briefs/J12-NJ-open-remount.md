# Wave J12, builder N-J12 (native): OPEN mounts an ejected drive again

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` s13, 2e, 2g and **2h** (the owner's words for this wave), the J4 brief `J4-J5-NJ-eject-open.md`, and the results note on the eject rule: `docs/ideas/UI-REDESIGN-RESULTS-20261117.md` around line 695.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (68 patches; the last is `mixxx-removable-rows-fix.patch`). Another builder (J13, waveforms) works at the same time in its own worktree, on other files. Never edit an existing Mixxx patch. Make `mixxx-open-remount.patch`, placed last, with the prerequisites it needs (probably `mixxx-media-selection.patch`, `mixxx-eject-top-menu.patch`, `mixxx-eject-folders-view.patch`, `mixxx-removable-rows-fix.patch`). The orchestrator settles the final order of J12 and J13; give your lines assuming yours is last.

## Today (build L on the card)
- After a Media-page eject (clean eject: DONE), the drive stays plugged in. Its row reads SAFE TO REMOVE.
- Build B's eject rule in `mixxx-media-selection.patch` (:883, :910, :2258) retires the drive's read generation: Mixxx refuses reads from it (`m_mediaUse` false, "No SoundSourceProvider") until the drive is pulled out or Mixxx restarts. If the drive is mounted again by any other means (for example `udisksctl mount`), it still cannot be read: Folders shows file names only ("thin tags"), and tracks do not load.
- Evidence (untracked, in the main checkout): `deploy/ui-redesign-20261117/acceptance-L/card-files/logs/r1/prestart/mixxx.log:551`, `deploy/ui-redesign-20261117/acceptance-L/ACCEPTANCE.md`.

## What to build (spec 2h)
- **After the eject, the row keeps reading SAFE TO REMOVE**, as today, and keeps an **OPEN** button that can be tapped.
- **Pressing OPEN on that row mounts the drive again** (the same udisks path the system uses; never a write to the drive) and starts a new read generation for it:
  - the row goes back to **READY** (or IN USE once a track from it is on a deck, as the chip rules already say);
  - then OPEN does what it always does (s13): it reads the drive's rekordbox export, or its folders if it has none, switches to Tracks, and the button reads BROWSE;
  - the drive's tracks load to decks, and Folders shows full tags, as before the eject.
- **No re-plug and no Mixxx restart.** Pulling the drive out still removes it, as today. EJECT after the remount works again, with its clean eject.
- Find first and write in your report: what the ejected row shows today (is OPEN there, disabled, or hidden?), what OPEN does on it today, and how the read generation is tied to a mount. If an OPEN button is not on the ejected row today, report it before you add one; the owner's words say OPEN is pressed on that row.
- Keep everything else: J4, J5, J10 and J11 behaviour, the ★ start, the plug-in ping, the chip timing, and never write to a drive.

## Files you own
- the new patch;
- new tests `tests/test_open_remount.py` and `tests/native/open_remount_*`;
- in the Mixxx source: `src/library/mixpimedia*`, the media-selection files build B added, `src/sources/*` only where the read generation is checked, the Media page's native parts, and new files.

No skin files and no stylesheets unless OPEN's state on an ejected row needs one rule (say why). Do not edit the registries; give the orchestrator your registration lines. If `test_eject_folders_view.py`, `test_removable_rows_fix.py` or `test_zoom_setting.py` checks that its patch is last, give the exact change needed as a registration line.

## Checks
- **Native fixture:** a fake drive mounted, read, ejected through the Media path (reads refused, row SAFE TO REMOVE), then OPEN: the mount is restored through the same udisks interface (mocked in the fixture), reads are allowed again with a new generation, the row reads READY, OPEN's normal read runs. Then eject again: reads refused again. A pull after the remount removes the drive. A different drive is never affected. Show the fixture failing without your patch.
- All earlier eject, source-group, media, Folders-eject and removable-rows fixtures still pass.
- The Mac suite in a clean worktree: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ12-nj12-20261122 <your worktree> gate`;
  - VM b is shared with the J13 builder today. Before you start a gate, check that no other gate is running in the VM (`ssh -F ~/.config/mixpi-lima-b/ssh.config lima-b-durable 'pgrep -af "[n]inja|[c]make --build|[c]test"'`); if one is, wait for it to finish (use a Monitor with an until-loop, not sleep). Check free space before and after;
  - never use `limactl`. Keep at least 24 GB free in the VM, run `fstrim` after cleanup, and keep the Mac above 20 GiB free.
- **Never touch the Raspberry Pi or any drive.** Open no window or app on the Mac.
- Give the orchestrator the Pi check, with coordinates: Media page › GANDER1 EJECT › DONE › (row SAFE TO REMOVE) › OPEN › (row READY, Tracks opens with GANDER1's tracks) › load a track to deck 1 › Folders › GANDER1 › a folder shows full tags › EJECT again. Re-plugs are done by the owner's hand; never switch a USB port off.
