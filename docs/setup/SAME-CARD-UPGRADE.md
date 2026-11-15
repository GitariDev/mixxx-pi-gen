# Performance target: same-card upgrade

Started 2026-11-08. Target: [performance plan](../ideas/PERFORMANCE-PLAN.md).
The user wants to reuse the card currently booting the Pi and preserve its
music. This supersedes the older instruction to use a new card in the
[touchscreen build guide](TOUCHSCREEN-BUILD.md).

## Current checkpoint

**November 11 — owner confirms EOS boot; field fixes before 64 GB release:**
the spare is installed and generally working. Native UI quality is rejected;
recording, first-start internal-library selection and actual USB LOAD/EJECT
workflow remain incomplete. Settings mostly work. The next route is one
functional climb plus a photo-grounded UI tuner, followed by one integrated
release to the 64 GB card with verified backed-up songs. Keep EOS working and
do not overwrite either card during preparation. A fresh coherent backup,
song/recording manifest and capacity check, current target identity and
target-specific erase/write confirmation are required before that flash.
See [field stocktake and release boundaries](../ideas/FIELD-FIXES-20261111.md).
The draft contract is not implementation/deployment approval. Broker OFF denial
must not be bypassed to make EJECT appear to work.

**November 11 — EOS spare flashed, verified and safely ejected:** the user
authorized the 16 GB EOS_DIGITAL spare instead of overwriting the original Pi
card, explicitly omitting the library. Raspberry Pi Imager 2.0.11.1 GUI wrote
the accepted custom image, completed verification without skipping, and reported
automatic safe ejection. Host inventory at 08:52:04 UTC confirmed the target
was no longer enumerated. No library/profile/database was restored and no image
customisation was applied. The earlier CLI stall and direct-write readback
mismatch remain failed historical attempts, not successful verification.
Evidence: `deploy/recovery-20261111/eos-test-card-20261111/GUI-ATTEMPT.md` and
`GUI-RESULT.json` in that directory.

At the flash handoff the next step was a physical spare-card boot: keep the original
working card intact as the return path, insert EOS, and check display/Mixxx
startup before audio/controller/touch and USB testing. The owner has since
confirmed boot/general operation as recorded above. No Pi boot, shutdown,
SSH or hardware test was performed by the flash task itself. This spare-card trial
does not establish recovery readiness for overwriting the original card or
production/operational EJECT acceptance.

**November 11 — Step 4/4 recovery availability exhausted:** the accepted new
image remains hash-matched, but the historically booted September recovery
image is unavailable in the checked project locations and authenticated GitHub
resources. Run `35761701616` has zero artifacts, the recorded artifact returns
404, and no matching September release asset exists. This is scoped
unavailability, not proof that no private copy exists anywhere. No recovery
image was downloaded or substituted; newer unbooted images and data archives
are not known-good rollback. The investigation's 1.5 GiB acquisition ceiling
also excluded the original 1,751,738,350-byte inner ZIP; that task limit is not
a fundamental storage requirement and can be reassessed against measured
capacity if exact bytes become available. Availability is the actual blocker.
The fresh check reconfirmed the accepted gzip, all 200 sources, source/public
archives and DEB/overlay identities. No Pi/VM/device operation or live backup
occurred. Evidence:
`deploy/recovery-20261111/recovery-availability-20261110T225034Z/REPORT.txt`.

The next safe route needs either an exact retained September archive location
or an independently boot-tested recovery device while the current boot card
remains untouched. Existing backups are preserved but are not the final stopped
backup: later cues/settings/recordings/music must be captured before card reuse.
Restore the coherent selected user profile and media separately from system
authority; never blindly restore old sudo/polkit/services/review gates. Recovery
rehearsal and Pi boot/audio/touch/controller/USB/endurance checks remain
unperformed; the separately authorized EOS spare write is complete as recorded
above, not a write to the original Pi card. No additional software
rebuild or generic runtime rerun is justified by the missing recovery bytes.

**November 10 — accepted-artifact image ingestion reviewed:** the exact repaired
DEB and separate overlay can now enter a fresh image build without recompiling
Mixxx or regenerating Pioneered. Independent delta review closed all four
ingestion findings: desktop stage order, renamed policy detection, root-local
hardening checks and nested SKIP rejection. Evidence:
`deploy/recovery-20261110/ingestion-acceptance-20261110/independent-review/REVIEW.txt`.
The 184-input snapshot is bound by SHA-256
`225dfeccc67f21e60298c795f5b7603da60119b4d68dbfd1c7e6ed04cb96de65`.
This is assembly-readiness acceptance, not an actual image. Next is a fresh
Linux ARM64 builder with measured capacity, controlled profile explicitly OFF
and no `eject-reviewed` gate. Recovery, activation and physical acceptance remain
separate; no spent retained-VM launch seal may be reused.

The user requested local image assembly rather than another machine. The earlier
65.922 GiB conservative capacity estimate is superseded as an admission blocker:
a new isolated 24 GiB ARM builder passed qualification and attempted the recipe
with measured capacity gates. Minimum sampled host/guest free space was
31.44/12.28 GiB; capacity was not the failure. Assembly refused an unexpectedly
world-writable `/run` tmpfs, and a harness invocation without `-e` continued after
that refusal. No image was produced. Parent fixes explicitly mount `/run` as
0755 and enable `set -e` even when invoking `bash build.sh`. Independent offline
delta review accepted both fixes. The reviewer's first Linux transfer changed
file modes and incorrectly continued after binding failure; that run is not
accepted exact qualification. Parent recheck preserved modes, verified all four
guest files before and after execution, and passed all four Linux tests with no
skips. All 200 frozen/current inputs and 667 scoped preservation records matched.
That same boot completed a second fresh-work assembly attempt. Normal package
installation, `dpkg --audit`, `apt-get check` and the installed binary hash passed,
then fail-fast correctly stopped at a new metadata conflict: the accepted DEB
records `0775` on three private Mixxx directories, rejected by the unchanged
writable-parent checks. No image was exported. A narrow importer change now
prevalidates and hardens only those three directories to `0755`. Its 45 focused
tests (one skip) and 363 host-suite tests (58 skips) pass without failures.
Independent Sol 6.1 review accepted the exact two-file offline delta, including
12 fresh adverse-case groups. The subsequent fresh Linux build passed exact-DEB
extraction, normal installation, stages 0–3 and final integration with profile
OFF. The 200-input source binding for that run is
`b4be0938b1bfc77a27d4402a4563acd16e20582ee37bfbf8a2428f9119ac424b`.
Neither package bytes nor the global security checks are relaxed. Minimum
measured host/guest free space for the preceding attempt was 26.18/8.18 GiB.
The builder and both older VMs are stopped. Failed-work evidence remains preserved.
Evidence:
`deploy/recovery-20261110/image-build-local-20261110T194254Z/HANDOFF.txt` and
`deploy/recovery-20261110/image-run-permissions-fix-20261110/` and
`deploy/recovery-20261110/image-linux-recheck-20261110T203134Z/RESULT.json`,
`deploy/recovery-20261110/image-build-local-20261110T203410Z/HANDOFF.txt` and
`deploy/recovery-20261110/image-directory-hardening-20261110T205621Z/` and its
`independent-review/REVIEW.txt`.

**November 11 — Step 3/4 image export repair reviewed:** the latest fresh
build reached final integration successfully, but final validation remounted
virtual filesystems after stage cleanup. Export sizing then counted
`/proc/kcore`, requesting a bogus 5.4 PB image; the capacity gate stopped before
image creation. Actual unmounted sizing is approximately 5.08 GB. A checked
unmount now precedes export, and the shared unmount helper explicitly returns
the first failure even in a conditional caller. A behavioral regression fails
before the fix and passes afterward; all 367 host tests complete without failure
(59 skips). Independent Sol 6.1/high review accepted the exact three-file delta,
with 11 fresh adverse holdout groups / 17 fixtures and five frozen regressions.
The 200-source binding is
`ee89c47bdf9541e27446a91b2004ce052311b41c54f554fb69f55ad9d6d4b2b2`.
The next fresh build passed all eight Linux lifecycle regressions with zero
skips and completed normal-apt image assembly and export. The 1,419,935,592-byte
compressed image has SHA-256
`80b1b13eb2c1686e9b2fd2ca1a3fb2a4d17b107dee4d7d1fe8e65b969aac1061`;
its 5,079,302,144-byte raw stream hashes to
`d76cc0eb77292ae3383acd93808ebdddcc0501566394744f9b682abab973e6f5`.
Builder checks passed exact payloads/modes, normal package audits, repository
signatures, partition/PARTUUID/kernel/initramfs consistency, authority inventory,
profile OFF/no review gates, and Mac gzip CRC/streamed raw hash. These new image
results passed independent Sol 6.1/high review: exact gzip CRC/identities,
200-source binding, manifests/archive equality and 389-file final closure all
passed. Step 3's bounded software/assembly/static/export gates are accepted;
no image rebuild or six-session runtime repeat is required. Step 4 recovery,
fresh final preservation, Pi boot and physical acceptance remain NOT READY.
The dedicated builder was expanded through supported tooling to 30 GiB; minimum
host/guest free space in the preceding failed attempt was 22.25/4.78 GiB. All three VMs
finish stopped; failed roots and historical evidence remain retained. The
successful attempt fit the existing 30 GiB root without another expansion;
minimum host/guest free space was 14.53/3.50 GiB. All 200 source bindings and
1,334 scoped preservation records match. Final image inspection observes the
root account locked by stage2, superseding the earlier intermediate-stage
default-root-password warning. The pi test credential remains guest-private;
SSH is disabled. Stock NOPASSWD sudo and UDisks2 authority remain, and profile
OFF does not remove them or establish production credential hardening. Evidence:
`deploy/recovery-20261110/image-build-local-20261110T211642Z/HANDOFF.txt` and
`deploy/recovery-20261111/image-export-unmount-fix/independent-review/REVIEW.txt` and
`deploy/recovery-20261111/image-build-local-20261110T220134Z/HANDOFF.txt` and
`deploy/recovery-20261111/image-acceptance/independent-review/REPORT.txt`.

**November 10 — Step 3/4 isolated software accepted; image pending:** the broker, offline checker and GUI
implementation have passed their bounded independent reviews, including the
completion-notification, context-independent Browse refresh and probe-free repaint
fixes. Final eighth-patch SHA-256:
`25464d7f4a7d7cc83018d99d4afc1770ab34fc2a98e9c8a940184a01f7e619b1`.
Evidence: `deploy/recovery-20261109/gui-lazy-probes/receipt.json`.
Independent review accepted the coherent full ARM build, delivered artifacts and
strict bounded provenance for attempt3 plus resume4: 794 top-level and 73 nested
outputs. No further rebuild is required for that acceptance. The accepted DEB
SHA-256 is `5f4a214eacf521e1594e96ad7766a7cbc194d26c41911e389b4b01d271f6d8ec`;
it excludes the separately delivered Pioneered/tools overlay. Evidence and hashes:
`deploy/recovery-20261110/full-native-build/attempt3/resume4/HANDOFF.md` and
`DELIVERY.md` in that directory. Earlier failed artifacts remain uncertified.
The user-approved isolated ARM VM exposed a real startup stack overflow in both
normal and safe modes. Seven owner-publication calls now use `setAndConfirm()`.
The repair and its new incremental full candidate have passed independent bounded
review: one object rebuilt, normal archive/relink, 866 object/PCH outputs and 402
MOC outputs unchanged. New DEB SHA-256:
`40fb4a74485a67c3ea0b33a3a01f661d4d2d6b19dc929d9441e7a50a878749c1`.
Fresh staging, packaging, prospective provenance and exact strip equivalence pass;
no further rebuild is required for this acceptance. Independent review now also
accepts this exact candidate's scoped isolated package and software runtime gates.
Evidence: `deploy/recovery-20261110/settings-incremental-candidate/HANDOFF.md` and
`DELIVERY.md` in that directory. Authenticated recipe-matched Trixie plus Raspberry
Pi repositories resolved the unchanged dependencies; normal installation,
`dpkg --audit` and `apt-get check` passed. Six full-app sessions exited 0, covering
normal/safe startup, synthetic null-audio playback, settings persistence/restart,
cache final-use release, permission-denial fallback and recovery. This supersedes
the earlier Debian main-only compatibility failure for this repository snapshot,
not for an eventual image or future repositories.
LOAD coverage is ancestry-denial/refresh/cancel; EJECT coverage is service/profile
denial only. Successful provider selection, mounting and operational eject remain
unverified. IPC listeners and locks release, but a stale private socket pathname
remains after shutdown; restart reclamation succeeds. Path existence alone must
not be used as readiness evidence. Software rendering/null audio do not establish
Pi performance or physical audio quality. Runtime evidence and scoped corrections:
`deploy/recovery-20261110/runtime-repaired-20261110T1542Z/HANDOFF.md` and
`deploy/recovery-20261110/runtime-acceptance-20261110/REVIEWED-RESULT.json`.
The user has authorized ejecting the currently attached USB drives, noting nothing
critical on GANDER1. No ejection has occurred in this qualification work; permission
does not establish implementation safety or authorize formatting/deletion.
Independent recovery remains unapproved; live install/restart, controlled-profile
activation and card writes remain separately gated. Different HOME/XDG settings alone
do not isolate global cache/IPC endpoints; see `CONTROLLED-MEDIA.md`.
The dependency-check VM restart unintentionally reformatted its disposable data
disk through a missed format-enabled label check. Its prior Docker state is no
longer visible; post-incident snapshots are preserved, not a claim of recovery.
Subsequent independent review accepted detached-data-disk preparation, offline
system/user service masks and actual combined isolation diagnostics. The same
accepted boot completed the package/runtime tests and was then stopped. Both VMs
are stopped, all 200 protected records remain unchanged, and runtime services are
remasked. The disposable working root intentionally retains packages, runtime
storage and drop-ins; it was not restored to its pretest bytes. Any future boot
needs a fresh reviewed procedure, never a spent launch seal.
The user also approved verified task-local tooling acquisition and autonomous
routine software/dependency updates needed to complete automated qualification;
this does not waive review, preservation or remaining physical-acceptance gates.
The incident data disk and snapshots remain protected; this is not Pi/deployment/flash approval. This incident did not
touch the Pi, USB drives or accepted local artifacts. Details:
`deploy/recovery-20261110/vm-preservation-20261110T0812Z/HANDOFF.md`.
The earlier dated milestones below are retained as history.

**Offline qualification update (November 9):** Step 1 ownership is done; Step 2/4
broker/profile qualification now includes a read-only staged-rootfs checker and
fixture coverage. The four broker fixes passed independent review per handoff;
the new checker/recovery draft awaits independent review. No current local rootfs
or top-level image archive is available, so installed-image qualification remains
UNVERIFIED. Step 3 full rebuild/link/runtime/image and Step 4 preservation/flash
are not performed. `CONTROLLED-MEDIA.md` proposes image-plus-verified-data recovery
or a separately prepared Linux/ext4 reader route for user approval. Neither is
an established recovery path; no erase/reflash, privilege change or review-gate
provisioning is authorized by that draft. Existing preservation gates below remain
unchanged. Evidence: `deploy/recovery-20261109/offline-qualification/`.

**Recovery update, November 9 (supersedes the session/build state below):**
Work continues on the existing dirty `feat/pi-performance-target` checkout.
No card write, shutdown, package installation or replacement of the verified
migration backup has occurred. The new UI runs only in the isolated profile
`/home/pi/mixpi-performance-ui-trial-20261109/profile`, with the extracted
`96ea682` binary and resources; the installed profile remains untouched.

- **Location handoff prerequisite (November 9):** the eighth patch additionally
  guards PlayerManager location resolution, TrackDAO lookup/import entry points,
  TrackLoader queue admission and spawned cover guessing. Operation-scoped
  leases are revalidated across queue handoffs; cached Tracks do not permanently
  hold media busy. Focused extracted-production tests and affected ARM object
  evidence are recorded in `deploy/recovery-20261109/location-handoff/`.
  This does not enable EJECT or replace the later full-link/runtime gate.
  See `tools/performance/README.md` for concrete remaining caller gaps; external
  copy admission and the authenticated topology-owning broker remain required.
- **Native ownership foundation integrated:** pending cache-reader loads,
  decoders/fallback, analyzer queues, Rekordbox, browsing, cover art, metadata,
  recording flush and track export now retain native ownership guards.
  Independent review found a failed-cache-copy provenance gap; the constructor
  now revalidates before initializing an original-file decoder. The extracted
  constructor regression fails before the fix and passes afterward, including
  unchanged-media fallback. Final host suite: 219 tests, 193 passed, 26 skipped
  in 10.904 seconds. The final changed ARM source compiled in 41.400 seconds
  after an initial const-member compile error was corrected without changing
  the header. Evidence: `deploy/recovery-20261109/ownership-integration/`.
  This is not a fully linked binary or runtime eject acceptance. Scanner/task
  and scheduler backlogs, remaining external producers and the mount-lifecycle
  broker are still required; production EJECT remains blocked.
- **Integrated media-selection milestone:** the eighth image patch adds
  separate multi-drive LOAD and EJECT choosers. Physical generation follows
  Rekordbox discovery/import/cache reuse, and opened directory/database
  descriptors must match device and mount ID. Independent review's two P1
  identity findings are fixed. Its P2 completion-recovery finding is also
  fixed: a failed observation invalidates the root revision before refresh,
  preventing stale playlist activation and duplicate retry children.
  The extracted-production regression fails before the fix and passes after.
  Current host suite: 216 tests, 190 passed, 26 skipped, in 24.910 seconds;
  evidence is `deploy/recovery-20261109/media-integration/host-tests.log`.
  The delegate compiled three ARM objects before the final P2 fix; that last
  fix still needs ARM compilation. No linked candidate or live UI acceptance
  exists for this milestone. EJECT deliberately remains BLOCKED until actual
  ownership and broker-controlled unmounts are implemented and verified.
- Native translucent-loop probing failed: the embedded OpenGL windows still
  cover the loop controls. The default fallback now replaces the selected
  deck's bottom overview with a zoomable detailed waveform while loops are
  open. Both decks' panels render; zoom changes the time scale and Close
  restores the normal overview and main waveforms.
- SAMPLER now has four pads, loaded titles, trigger/Stop and LOAD SAMPLE.
  The existing library provides destination buttons without auto-playing.
  An internal-export track loaded, triggered and stopped in the native trial;
  its destination was disabled while playing. Missing USB files produce the
  native missing-file dialog, not a fabricated successful load.
- The native settings implementation is recovered into the image patch stack.
  Audio-buffer changes require stopped players/recording and confirmation;
  cache/read-ahead are next-launch choices. All three changed C++ translation
  units compiled successfully on the Pi, including the settings header. A
  linked package and runtime audio acceptance are still required. Older
  binaries disable these settings.
- `deploy/recovery-20261109/` contains native screenshots, test/build logs and
  independently verified stopped-trial profile checkpoints. The original
  `deploy/migration-20261109/VERIFIED.json` remains unchanged. New checkpoints
  supplement that backup; they do not replace the final music/recording scan.
- **Not flash-ready:** the final image has not been rebuilt with these edits.
  Mount-wide media-use accounting, guarded USB eject and backed-up USB tests
  are still missing. No safe-to-remove indication is exposed. The existing
  recordings-folder file-use scan is not a mount-wide eject interlock.
- Full-target audit: native source visibility/navigation exists, but source
  defaults/reordering, all source-pane geometry and physical touch acceptance
  are not signed off. Shared media status/hold-to-eject remains unimplemented.
  Keep LightDM/Xorg/Nautilus until their replacement paths are verified;
  desktop removal is not a substitute for the remaining safety work.
- Multi-USB requirement confirmed: LOAD and EJECT must both select a specific
  drive, with per-drive safety state and identity revalidation. MANTACORE
  (58.6 GiB, exFAT) and GANDER1 (3.7 GiB, FAT) were observed mounted together
  during recovery. Neither was ejected, written to or included in the earlier
  SD backup. Physical removal tests still require a backed-up test drive.
- Final recovery checks: 168 host tests (142 passed, 26 explicit skips),
  including the pinned seven-patch application/reversal check. Both original
  migration archive checksums still match. Latest stopped-trial checkpoint
  `checkpoint-1794226430320311131` independently verifies all 291 entries
  and SQLite integrity. The trial was relaunched afterward, so another final
  stopped-profile refresh remains necessary before flashing.

The earlier build history follows. Its successful intermediate images do not
include this recovery's sampler, waveform fallback or settings patch.

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
