# Performance target: same-card upgrade

Started 2026-11-08. Target: [performance plan](../ideas/PERFORMANCE-PLAN.md).
The user wants to reuse the card currently booting the Pi and preserve its
music. This supersedes the older instruction to use a new card in the
[touchscreen build guide](TOUCHSCREEN-BUILD.md).

## Current checkpoint

**November 9 update:** Mac capacity rechecked at 28 GiB free. User authorized
closing Mixxx; it exited cleanly. The new stopped-session backup is **verified**
under ignored `deploy/migration-20261109/`. `VERIFIED.json` records a successful
source/archive/source comparison and SQLite integrity `ok`; `SHA256SUMS`
records the final archives. Both the originals and the Mac copy remain intact.
The source manifest contains 2,649 regular files, 7,987,551,978 payload bytes.
The library also contains 150 references to the separate MANTACORE USB stick;
this SD backup preserves those references, not files on the absent stick.

The recovered performance code is pushed on `feat/pi-performance-target`.
The first standalone Pi compile caught an ambiguous Qt 6 integer overload in
the RAM cache; it is fixed, and its real C++ smoke test passes. The corrected
ARM build `42580935705` exposed another recovered error: `IndexRange` uses
`containsIndex`, not `contains`. Fixed in `ccbf91b`; replacement build
`42581855459` passed at `ccbf91b`. The downloaded arm64 package checksum,
Mixxx source revision and all four patch hashes match. Its extracted binary
on the Pi resolves all shared libraries; an apt simulation resolves its
dependencies without upgrades or removals. The user subsequently accepted
its short runtime/audio smoke test, as recorded below. The package is staged at `/home/pi/mixpi-package-trial-20261109/`
and has not replaced the installed binary.
Host checks with the pinned skin fixture and image-stage isolation tests:
148 tests, 122 passed, 26 skipped. Image isolation commit
`249da45` was pushed after that package build succeeded. Its full image build
`42590130970` passed; it predates runtime cleanup and native Sources/navigation
and is not the final flash candidate. Sources package `42592257666` at
`3d50f7b` passed compilation. The next package adds native folder navigation
and Back, a right-hand pane beside the track table, and real Qt navigation
smoke checks. Host validation: 152 tests, 126 passed, 26 skipped. Navigation
package `42594754742` at `96ea682` has now passed ARM compilation and the CI
Qt smoke check. The downloaded package and six patch hashes match; the Pi
copy and matching skin verify, and all runtime libraries resolve. The candidate
is extracted at `/home/pi/mixpi-candidate-96ea682/` without starting it.
Full image `42594756523` is building from that same recipe. Live touch checks
remain pending. No further Pi session restart or card write has taken place.

The maintenance helper passed live pause/restore and systemd normal/failing
process checks, restoring every timer's initial state. Its temporary state
was cleaned up. No production service was installed.

**Touch acceptance:** on November 9 the user confirmed Overview/Browse/Sampler
stay selected when tapped again, and Browse → select track → Actions works.

**Current Pi session:** the extracted performance binary now runs from
`/home/pi/mixpi-package-trial-20261109/extracted/usr/bin/mixxx` with explicit
`--settings-path /home/pi/mixpi-package-trial-20261109/profile` and
`--resource-path /home/pi/mixpi-package-trial-20261109/extracted/usr/share/mixxx`.
The prior trial exited cleanly. Its copied profile retains the accepted patched
Pioneered skin. Two internal-export MP3s loaded at startup; both emitted RAM
cache-ready messages and their decoder paths point into `/dev/shm/`.
Both waveforms rendered; V3D 4.2.14.0 and the existing 44100 Hz / 1024-frame
(23.22 ms) audio stream initialized. Temperature was 49.6°C, throttled=0x0.
Recoverable MP3-header messages appeared. The user subsequently passed the
master/headphone/controller/loops/FX smoke test and reported noticeably better
performance. Post-test temperature was 48.2°C with throttled=0x0, no swap use
and about 2963 MiB available memory. The captured log had no matches for
underflow/overflow/xrun/critical/fatal; this is a short smoke test, not endurance
acceptance or proof of safe eject.
No production package was installed. New cues/playlists in this session remain
in its temporary profile. Preserve the original profile and return to the normal
launcher after cleanly closing this trial. The user deferred the 30-minute two-deck session to the new image; do not
physically eject USB during this trial.

### Historical inventory (superseded by the checkpoint above)

The following inventory was recorded before the verified backup:

**2026-11-09 storage update:** the Mac now has about 59 GiB free. Two large
movies were copied to `rA9`, independently checksummed, and their originals
removed. Xcode DerivedData, npm's download cache and approved dependency
folders in five inactive PanelAI worktrees were cleared. Source changes were
preserved. Receipts are in ignored `deploy/storage-cleanup-20261109/`.
The storage blocker is resolved; the Pi's stopped-session backup is still
pending. For future ordinary file moves, the user prefers to check the copied
files themselves before original removal instead of a full automated checksum
pass. Agree the Pi backup verification procedure at its own checkpoint.

- Pi reachable as `pi@mixxxpi.local` using the existing dedicated SSH key.
- Root is `/dev/mmcblk0p2`, 57 GiB, with about 40 GiB available.
- Read-only inventory: `~/Music` 176 MiB, `~/.mixxx` 80 MiB,
  `/media/SD-Backup` effectively empty, and two internal exports under
  `/media/pi/` of 5.3 GiB and 2.0 GiB. These are ordinary directories on
  the boot card, not independently mounted USB drives.
- Mac had 1.1 GiB available and no external volume mounted. User will free
  at least 20 GB. Recheck capacity before copying and downloading images;
  this is a data-backup budget, not room for a full 62 GB card image.
- User is using Mixxx. Do not stop it or change the live system during this
  session. Final backup must wait until the user finishes and Mixxx exits.
- Host suite: 146 tests, 119 passed, 27 skipped. Pinned-source patch
  application passed. ARM compilation and runtime remain unverified.
- No new backup, build, deployment or flash has happened at this checkpoint.

## Preservation gate

1. Recheck Mac free space and inspect all music/library locations on the Pi,
   including recording destinations, copy receipts and any additional local
   music directories. The inventory above is a starting point, not proof of
   complete coverage. Distinguish USB-dependent library entries from SD files.
2. When the user finishes, quit Mixxx cleanly and confirm it has exited.
   Preserve the full `.mixxx` profile (database, cues, playlists, analysis,
   mappings, audio settings), `~/Music`, `/media/SD-Backup`, and both complete
   `/media/pi/MixPi-*` exports. Preserve symlinks and original absolute paths.
   Capture relevant user settings and system configuration separately for
   reference, including Wi-Fi recovery and audio routing; keep private data
   in ignored `deploy/`, never in Git.
3. Stream archives to a new dated Mac backup directory. Generate a source
   manifest of file paths, sizes, hashes and symlink targets. Independently
   read back archive members and compare them to that manifest. Check the
   backed-up SQLite database's integrity. Do not accept an archive's own
   checksum alone as evidence that all source files were preserved.
4. Keep archives, manifests and verification results off the Pi. If the user
   resumes Mixxx before flashing, repeat the final settings backup and check
   for changed music/recordings. Do not erase the card with a stale snapshot.
5. Have both the new verified image and a known-good recovery image available.
   Data archives restore user content but are not a full bootable rollback.
   If full-card rollback is wanted, allocate additional space for it.

## Build and implementation order

1. Compile the recovered ARM package; resolve compiler errors before building
   the image. Preserve exact source revision, patch list and checksums.
2. Finish the native touch layout and source navigation from the accepted
   prototype. HTML interactions alone are not implementation evidence.
3. Finish media-use accounting and safe eject. Cache fallback, pending loads,
   analyzers and decoder lifetime must block eject when necessary. Do not
   expose a safe-to-remove indication based only on the RAM cache patch.
4. Complete image packaging/strip-down and run regression checks. Keep the
   agreed 60 fps waveforms and existing keylock engine pending listening tests.
5. Build and verify the image, then perform the preservation gate above before
   the same-card flash. Small staged package trials may precede the final image
   once the Pi is available and its profile is backed up.

## User test checkpoints

| Checkpoint | User action | Evidence to collect |
| --- | --- | --- |
| Backup window | Finish the session and leave Mixxx stopped | Verified archives, database integrity, complete file manifest |
| Card handoff | Shut down after backup, move the existing card to the Mac reader | Reidentify capacity and physical device; never reuse an old disk number |
| First boot | Return the verified flashed card to the Pi; connect network | Boot, expanded root, SSH host fingerprint verified locally, V3D renderer |
| Restore | Leave Mixxx stopped during restoration | Identical music hashes/paths, library integrity, playlists/cues/mapping present |
| Touch/audio smoke test | Exercise tabs, Browse, loops, FX, settings; listen to master and headphone cue | Touch reachability, correct routing, single Mixxx process, Speaker handoff |
| USB safety | Use a backed-up test USB through insertion, load, cache failure and guarded eject | Eject refusal during dependencies; uninterrupted playback where supported |
| Endurance | Play two decks/controller for 30 minutes, including SD and USB sources | Audible dropouts, logs, temperature, throttle flags and buffer behavior |

Restore the saved profile into the fresh installation while Mixxx is stopped,
after moving its newly generated profile aside. Do not blindly overwrite the
new desktop/system configuration with the old reference copy. Verify the
restored files before launch, then verify saved routing and library behavior
with the user. Retain the Mac backup after the upgrade passes.

## Next image cleanup (November 9)

Removed Firefox, Syncthing and qpwgraph from the requested runtime packages.
Portal backends are explicitly installed and selected by `sway-portals.conf`:
GTK supplies general desktop portals; wlr supplies screenshot/screencast. The
old backend masks are no longer created. Config-file modes are preserved
instead of recursively forcing 755, and only executable helpers receive 755.
The kernel stage removes `preempt=full`, preserves unrelated boot arguments,
and writes one performance-governor option on repeat runs. These edits are
for the next image and have not been applied to the running Pi.

LightDM/Xorg and Nautilus remain until their replacement paths are tested.
Image run `42590130970` builds `249da45`, preceding this cleanup.
