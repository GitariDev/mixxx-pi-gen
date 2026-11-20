# Wave J7, builder N-J7 (native): a drive's lists show that drive's tracks

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` 2d and 2e.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Two builders work in parallel: N-J4 (sidebar and media files, patches after `mixxx-quit-library-widget.patch`) and N-J6 (`mixxx-external-sort.patch`, in `columncache`, `basetrackcache` and the external library sort code). Never edit an existing Mixxx patch. Make `mixxx-drive-track-cache.patch`; the orchestrator places it after theirs, so it must not depend on them. If your fix must touch `basetrackcache.{h,cpp}`, keep the change small and say so, because N-J6 may touch the same file.

## Evidence (the owner, 2026-11-20, untracked in `deploy/ui-redesign-20261117/owner-ixian-20261120/`)
- `mixxx.log` (the card's log), `shots/owner-now*.png` (the card), `shots/rbxport-sunny-day-vibes.png` (the owner's rekordbox-export tool showing the same playlist), and copies of the drive's `export.pdb` and `exportLibrary.db` (read only; the owner's private data, never send it anywhere).
- **Sequence:** GANDER1 (98 tracks) was the only drive. 15:57 GANDER1 ejected: the log shows "Dropping Rekordbox table" for the three tables and their re-creation. 16:02 the owner plugged IXIAN (555 tracks) and opened it.
- **Fault 1, wrong songs:** IXIAN's playlists (Jazz, Volk MUSIK, Bootlegsss, Sunny Day Vibes) show GANDER1's Drake tracks with GANDER1 paths. The log shows TagLib and "File not found" for `/media/pi/GANDER1/Contents/...` while GANDER1 is gone.
- **Likely cause (check it):** stock `RekordboxFeature::onRekordboxDevicesFound()` (`src/library/rekordbox/rekordboxfeature.cpp` ~:1550) drops and re-creates `rekordbox_library` when no drive is left. Its `id INTEGER PRIMARY KEY AUTOINCREMENT` restarts at 1, so IXIAN reuses GANDER1's ids. `m_trackSource` (the `BaseTrackCache` made once at ~:1345) still holds GANDER1's rows for those ids, so the table draws them. MixPi's hot-plug and eject make this path common; stock Mixxx users rarely hit it. Check every path that clears or re-fills these tables (eject, pull, re-plug, a second drive, the "Tracks" row from `mixxx-drive-tracks-row.patch`) and the same pattern in the other external features MixPi uses.
- **Fault 2, count:** on the card "Sunny Day Vibes(Neo/RnB/Afro/Rap)" reads 42 tracks; the owner's tool shows 55 for the same playlist. Find out why from `export.pdb`: parse it (Mixxx's kaitai reader through a native fixture on VM b is the safest way) and list the playlist's entries. Then say whether Mixxx drops entries (for example a missing track row, a missing file, a duplicate, a type it skips) or the export itself holds 42. Fix it only if Mixxx is dropping entries the export has; otherwise report what the export holds.

## What to build
- After any eject, pull or re-plug, every list of the drive in view shows exactly that drive's tracks: never rows from a drive that is gone, and loading a row loads that drive's file.
- The smallest safe fix, for example resetting the track cache whenever the tables are cleared, or never reusing ids. Find the right one and say why.
- Fault 2 as above.
- Keep the clean eject (`refreshMediaLifecycle`), the ★ start, the Tracks row, the shared columns, and never write to a drive.

## Files you own
- the new patch;
- new tests `tests/test_drive_track_cache.py` and `tests/native/drive_track_cache_*`;
- in the Mixxx source: `src/library/rekordbox/*`, the other external features' sources if they share the fault, `src/library/basetrackcache.{h,cpp}` only if needed (see above), and new files.

No skin files and no sidebar or media files. Do not edit the registries; give the orchestrator your registration lines.

## Checks
- **Native fixtures:** drive A's export parsed and its rows viewed; A removed with no drive left (tables dropped); drive B's export parsed: B's playlists show only B's tracks and paths. Also with a second drive present, and with the Tracks row. Show the fixture failing without your patch.
- Fault 2: the fixture's list of the Sunny Day Vibes entries from the copied `export.pdb`, with its count.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (`test_chroot_runtime`'s 5 s timeout can trip under load; rerun it alone).
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ7-nj7-20261120 <your worktree> gate`;
  - never use `limactl`. Keep at least 24 GB free in the VM, and run `fstrim` after cleanup. Delete the copied export from the VM when done.
- **Never touch the Raspberry Pi or any drive.** The owner is playing on it.
- Give the orchestrator a Pi check with coordinates. Re-plugs are done by the owner's hand; never switch a USB port off.
