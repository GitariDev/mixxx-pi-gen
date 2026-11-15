# Mixxx Pi journal

## Master overview

- **Goal:** a compact, touchscreen-first, standalone-feeling DJ system built on a Raspberry Pi and Mixxx.
- **Current rig:** Raspberry Pi 4B; generic 7-inch 800×480 DSI touchscreen; USB mouse; Hercules DJControl Starlight as the current/temporary DJ controller; portable USB storage; external speaker; portable power under test.
- **Software:** the current build pins Mixxx 2.5.6 and Pioneered on 64-bit Raspberry Pi OS Trixie. SSH inspection on 2026-09-22 confirmed those versions, Sway 1.10.1, an 800×480 display at scale 1, and native Wayland Mixxx in an 800×444 window below the top bar, without forced fullscreen.
- **Working:** first EthioJazz gig completed. The live Pi now has larger Browse rows/menus, horizontal scrolling, an Actions button for track context menus, and a two-way USB ⇄ Pi window on the top bar: music copies in, Mixxx recordings move out. Starlight master/cue routing and the saved MIDI mapping were exercised; the user confirmed the audio/controller/touch test worked.
- **Known friction:** the live Pi now renders Mixxx on the V3D GPU (since 2026-11-08), and the Sway render-device fix is now recovered into the local image recipe; a rebuilt image remains unverified (see [`PERFORMANCE-PLAN.md`](ideas/PERFORMANCE-PLAN.md)). Audio cut-outs during USB playback remain untested. The sealed cardboard box leaves little margin: with V3D the model expects about 73 °C at two decks and the 80 °C throttle point with a copy running, until the fans in [`COOLING-PLAN.md`](ideas/COOLING-PLAN.md) are fitted (parts to order). Gig power cutouts and the USB 3 extension remain unresolved. General touchscreen long-press and live MIDI auto-discovery are still open; automatic Rekordbox discovery is installed and passed silent checks with one USB plus SD.
- **Next milestone:** the owner confirms the EOS spare now boots and generally works. Fix field recording/first-start/media issues and restore native UI quality through the new contract/UI tuners, then prepare one integrated 64 GB release with verified backup songs. EOS stays intact as the working comparison/return card; no immediate flash. Operational EJECT, recovery rehearsal and endurance remain unaccepted. See the [field stocktake](ideas/FIELD-FIXES-20261111.md) and [`SAME-CARD-UPGRADE.md`](setup/SAME-CARD-UPGRADE.md). Controller upgrade planning remains in [`CONTROLLER-UPGRADE.md`](setup/CONTROLLER-UPGRADE.md).
- **Longer-term direction:** support replaceable DJ controllers, audio interfaces, storage, displays, and auxiliary control surfaces without baking a single device into the core image.
- **DJ preparation tools:** two open issues cover Rekordbox metadata/genre enrichment and beatgrid repair; see [`DJ-LIBRARY-TOOLS.md`](ideas/DJ-LIBRARY-TOOLS.md). These are proposed Python tools with executable packaging, separate from the Pi image.
- **Backlog:** browser-based transfer and individual-playlist selection (the first copier handles a whole export), automatic MIDI mapping (stretch), and permanently installed stems tooling (long term; exact software/format unconfirmed).

## 2026-11-11

- **EOS field boot and next climb:** owner reports the card is installed and
  generally working, with ten photographs documenting unreadable effects popup,
  awkward sliders, nonworking REC, library/source/dialog style regressions,
  first-start library prompting and incomplete USB LOAD/EJECT workflow. Settings
  mostly work; live keylock/tempo switching is deferred by the owner. Prior
  software/package/image acceptance stands, but never included operational
  eject or native visual approval. EJECT denial is the intentionally OFF broker
  profile, not permission to bypass its gates. The shipped XML lacks the
  `LibraryWrapper` ancestor required by its retained dark table styles; source
  research also identifies a REC feedback-state mismatch, not proven recording
  file failure. Stocktake: `ideas/FIELD-FIXES-20261111.md`. Draft contract record
  `mixpi-field-fixes-20261111` is in the adjacent climb-contract-tuner; the new
  `tools/ui-tuner/` compares actual photos, historical native Browse and labelled
  restoration sketches. Preparation only: no live Pi/card/service changes.
- **EOS spare ready for physical boot test:** Raspberry Pi Imager 2.0.11.1 GUI
  wrote the accepted image, completed verification without skipping and safely
  ejected the 16 GB EOS card. Host inventory confirmed ejection at 08:52:04 UTC.
  No library/profile/database restoration or image customisation. Original Pi
  card and 1 TB rA9 excluded. Earlier CLI stall/direct-readback mismatch remain
  failed historical attempts; separate GUI evidence is in ignored
  `deploy/recovery-20261111/eos-test-card-20261111/GUI-ATTEMPT.md`. Pi boot,
  hardware, recovery and operational EJECT remain untested by this operation.

## 2026-11-09

- **Ownership foundation and fallback fix:** recovered the cancelled delegate's
  verified patch/evidence and independently reviewed its native producer guards.
  Fixed the review's failed-cache-acquisition provenance gap directly; the real
  constructor is now in the regression harness. Replacement media cannot be
  opened using the previous generation's lease after cache-copy failure, while
  stable-media fallback still works. Final host suite: 219 tests, 193 passed,
  26 skipped (10.904 seconds). Only the final changed ARM source was rebuilt
  (41.400 seconds); full linking and operational eject remain outstanding.
  Both user USB mounts and live trial PID 12881 were unchanged during validation.
- **Media milestone integrated after review fixes:** native per-drive selection
  now preserves physical generation through Rekordbox cached imports and
  validates resolved directory/database device and mount IDs. Fixed transient
  completion-validation recovery by invalidating the reusable root revision.
  A regression compiled from production activation, reconciliation and
  completion functions fails before the fix and passes afterward, including
  same-revision recovery and duplicate-free retry. Full host suite: 216 tests,
  190 passed, 26 skipped, in 24.910 seconds. EJECT still blocks pending real
  ownership/broker integration; no USB operations or flash occurred. Native
  compilation of the final recovery fix and full linking remain outstanding.
- **Multiple USBs required:** user connected drives during recovery and
  clarified that shared LOAD/EJECT must choose the target drive. Read-only
  mount inspection found MANTACORE and GANDER1 together. Updated the build
  contract for per-drive identity/status, duplicate labels, all partitions of
  a selected physical device and confirmation invalidation on hotplug. No
  USB copy, unmount or eject was performed.
- **Recovery validation:** all three settings-related C++ translation units
  compile on ARM; this is not a newly linked package or image. Final host
  suite: 168 tests, 142 passed, 26 skipped. Original migration archive checksums
  still match; a separate stopped-trial checkpoint verifies 291 entries and
  SQLite integrity. The isolated trial is running again with the accepted
  44100 Hz / 1024-frame stream. Settings stay disabled on its older binary.
- **Native UI recovery:** continued the existing performance checkout without
  resetting files or changing provider. Tried translucent loop controls on
  the Pi; OpenGL native windows still occlude them. Implemented the requested
  fallback with a selected-deck bottom detailed waveform and real zoom
  controls; Close restores the overview. Restored four sampler pads and
  LOAD SAMPLE → existing library → destination pad, with no automatic
  playback and playing-pad load buttons disabled. Native load/trigger/stop
  checks passed using an internal-export track. Recovered native settings
  into the package patch stack and capability-gated the skin for old binaries.
  Final image and safe USB eject remain blocking gates; no flash or shutdown.
  Evidence and separate stopped-profile checkpoints are in ignored
  `deploy/recovery-20261109/`; the verified full migration backup is untouched.
- **Space for same-card migration:** moved two movies to `rA9` with verified
  checksums before removing originals; cleared approved Xcode/npm caches and
  dependency folders in five PanelAI worktrees, preserving Git status and
  tracked changes. Mac now has about 59 GiB free. Active worktrees, Soup Engine
  outputs and Mixxx worktrees retained. Receipts: ignored
  `deploy/storage-cleanup-20261109/`. No Pi changes or music backup yet.
- **File-move preference:** user will check future ordinary copied files before
  original deletion; avoid lengthy automated verification unless agreed.

## 2026-11-09

- **Same-card climb resumed:** Mac now has 28 GiB free. User authorized a
  clean Mixxx close. Started an independently verified backup of the SD music,
  recordings, profile and copier receipts (2,649 files, about 8 GB), plus
  separate reference settings. All archive members matched the first source
  manifest and a second source pass; SQLite integrity passed. Final archives
  and verification results are in `deploy/migration-20261109/`.
- **First native compilation fix:** the isolated RAM-cache smoke test found
  an ambiguous Qt 6 `qBound` call; fixed the bound types. The test now passes
  on the Pi for cache bytes, leases, replacements, missing/oversized files,
  simultaneous readers and WavPack companions. This does not certify safe eject.
- **Build:** pushed the recovered performance work and smoke test as commits
  `c4440db` and `8725ec1`. Build `42580935705` then exposed the recovered
  read-ahead call to nonexistent `IndexRange::contains`; corrected to
  `containsIndex` in `ccbf91b`. Build `42581855459` is in progress.
  Native tab buttons now send only a press, avoiding selected-tab toggling;
  pinned skin checks pass. No production Pi package/skin deployment yet.
- **Runtime checks:** maintenance pause/restore and supervised normal/failing
  processes restored all nine timers. Temporary trial profile/skin is now
  open using the original binary, with V3D confirmed; user tab/Browse checks
  are pending. Original profile preserved; trial edits stay in `/tmp`.
- **Image preparation:** compile in a disposable root and apt-install only
  the generated package/runtime dependencies into the image; remove the
  legacy compiler/Qt5 development lists. Local commit `249da45` awaits push
  after the package build. Host suite: 148 tests, 122 passed, 26 skipped.
  Full image validation is still outstanding.

## 2026-11-08

- **Started same-card performance upgrade:** user wants to reflash the current
  card and preserve its music. Read-only SSH inventory found about 7.5 GiB
  across music, two internal exports and the Mixxx profile. Mac had only
  1.1 GiB free; user will free at least 20 GB. User is actively using Mixxx,
  so no live changes or stopped-session backup were made. Host checks again
  passed (119 passed, 27 skipped), including pinned patch application;
  compilation remains outstanding. Preservation gates and user tests are in
  [`SAME-CARD-UPGRADE.md`](setup/SAME-CARD-UPGRADE.md).

- **Recovered interrupted performance work:** both code worktrees copied into
  the main workspace without overwriting the cooling edits. GPU/maintenance/
  Beat FX fixes and experimental read-ahead/RAM-cache patches are local and
  uncommitted. No Pi changes, push or ARM build in this recovery session.
- **Checked:** 146 host tests ran: 119 passed, 27 skipped. Pinned Mixxx patch
  application passed; C++ compilation and device runtime are still unverified.
- **Touch preview:** added the interactive [Pioneer proposal](../tools/pioneer-prototype/index.html)
  with simulated decks/media/FX/settings/sources. Revised it after user feedback
  against Claude’s recovered HTML, his detailed prototype brief and actual Pi
  captures. It now preserves the stacked waveforms and Pioneered appearance at
  exactly 800×480. Settings replace the waveform region, keeping deck info and
  controls exposed. Twenty-nine interaction/geometry checks passed; captures
  are saved with the prototype. Read-ahead controls and source filtering remain
  proposed features.
- **Touch preview follow-up:** added per-deck LOOP interval panels (1/32–64
  beats, half/double, exit/reloop), Camelot(musical key) labels and a collapsible
  Browse source pane with expandable Rekordbox/USB folders. Browse defaults to
  the current Pi’s full-width table. Fifty-seven focused checks passed alongside
  the previous 29 media/settings/layout checks. These remain preview changes.
- **Eject limitation:** RAM cache fallback can still use the USB original;
  the safe-eject interlock is not implemented. See the recovery status in
  [the performance plan](ideas/PERFORMANCE-PLAN.md) before deploying.

- **Illustrated cooling build manual:** completed the 16-step guide in the
  [local model](../tools/cooling-model/index.html#build), with connector release,
  insulation, physical header pins, later mounting, power and logging steps.
  Screen pins remain unconfirmed; diagrams show an example, not an inspection.
  Documented both plastic-latch and metal-tang releases, secure insulation and
  strain relief, and the need to verify 9 V startup on the 12 V fan. No Pi
  configuration or physical hardware changed; no new thermal test was run.

- **Cooling model (read-only):** user asked where to mount two fans in the
  cardboard box and how to wire them. Photos show the Pi under the slanted
  screen face with stick-on heatsinks and masking tape, and the hub on the box
  floor. The fans are a 30 mm 5 V fan in a Pi 4 case lid and a 60 mm fan with
  an unread label. Built [`tools/cooling-model/`](../tools/cooling-model/index.html),
  a lumped heat and airflow model calibrated to the closed-box idle reading
  (66.2–67.6 °C at 13:02, `throttled=0x0`).
- **User measurements:** the box is 235 × 152 mm, 100 mm tall at the back and
  57 mm at the front. The 60 mm fan is labelled 12 V 0.22 A and is 24 mm thick.
  The 30 mm fan has a single 2-pin housing. The display uses "the main two"
  header pins, taken as 4 and 6 (**Unconfirmed**). Room 25 °C is the default.
  The masking tape is off. The user will order parts and has a soldering kit.
- **Model updated:** it now uses the measured box and fan, and the CPU loads
  measured in the GPU test (two decks: 1.4 cores with software GL, 0.5 with
  V3D). With V3D, the sealed box reaches about 73 °C at two decks and 80 °C
  with a copy. The 60 mm fan as an exhaust gives about 50 °C. Blowing in at the
  SoC heatsink on a 9 V boost cable gives about 40 °C, with the 30 mm fan as a
  backup (about 55 °C if the big fan stops). The model is about 1.6 K below the
  September 3-minute peak, and possibly about 4 K hot at idle after the GPU fix.
- **Plan and test:** placement, wiring, a parts list and a 30-minute
  before/after logging protocol are in
  [`COOLING-PLAN.md`](ideas/COOLING-PLAN.md). The 60 mm fan goes outside the
  back wall, because inside it would hit the slanted lid. The 30 mm fan uses
  pins 2 and 14 through jumpers. The logger,
  `tools/cooling-model/log-temps.sh`, was dry-run on the Pi over SSH stdin
  (nothing written there). Results go in the
  [cooling test log](setup/HARDWARE.md#cooling-test-log). Fans not fitted yet;
  waiting on parts.
- **Performance deep dive (read-only):** user asked for help with freezes when
  adding music, more RAM for Mixxx, a slimmer Pioneer view, CDJ-style media
  load/eject, a touch settings menu and upstream updates. Claude and Codex
  reviewed the image and researched upstream; live data came over SSH.
- **Main finding:** Mixxx and every Wayland client render with **llvmpipe**
  (software GL). Sway advertises vc4 `card1`, which has no render node. A
  headless Sway with `WLR_RENDER_DRM_DEVICE=/dev/dri/renderD128` gives clients
  V3D 4.2. The live-screen test is pending.
- **RAM is not the limit:** Mixxx about 500 MB, about 3 GB available, swap
  unused. 68 °C at idle.
- **Also found:** 150 of 202 library tracks live on the MANTACORE stick.
  Pioneered Beat FX master routing is broken (`effect.xml:49`). Keylock uses
  RubberBand R2 on both decks. 2.5.6 is still the latest stable Mixxx (2.6 is
  in beta), and neither skin has changed upstream.
- **Plan:** [`PERFORMANCE-PLAN.md`](ideas/PERFORMANCE-PLAN.md). The research
  pass changed nothing on the Pi.
- **Clarified problem:** the user meant lag and audio cut-outs **during
  playback** from SD or USB, not during copying. They asked for GPU tests and
  an HTML plan based on the results.
- **GPU fix installed live:** backed up `mixxx.cfg`, `soundconfig.xml` and the
  Starlight mixer state to
  `~/.local/state/mixpi-backups/gpu-test-20261108-131033/`. Added
  `/etc/X11/Xsession.d/80mixpi-gpu-render-node`
  (`WLR_RENDER_DRM_DEVICE=/dev/dri/renderD128`) and restarted LightDM. Mixxx
  now logs `V3D 4.2.14.0`. Rollback: delete the file and restart LightDM.
  It is not in the image yet.
- **Measured** (two decks from SD, Overview, Starlight muted): Mixxx CPU
  120 % → 36 % with the GPU, and 23 % with SoundTouch plus 30 fps (tested,
  then reverted). Whole Pi 34.5 % → 7.9 %. Max 67 → 61 °C.
- **No SD dropouts:** zero cache misses and no ALSA underflow, even with
  1.2 GB written during playback. Mixxx's read-ahead is only 0.37 s, so USB
  playback is the next test. Evidence: `deploy/gpu-test-20261108/`.
- **Side effects:**
  - The first run's typing hit Mixxx shortcuts: play, PFL, beat jumps and
    loop size. Nothing touched hotcues or the library.
  - About ten restarts rotated out all older Mixxx logs (2026-10-14 to 11-06).
- **Restored:** original `mixxx.cfg` and `soundconfig.xml`, Starlight
  unmuted, Mixxx running with empty decks. Removed the temporary files from
  `/tmp`.
- **Walkthrough:** artifact
  [Mix Pi Performance Plan](https://claude.ai/artifact/BxEN6L5tA7rFMSX7BTusDV).
  The OS research recommends staying on Raspberry Pi OS Trixie with Sway; the
  official `linux-image-rpi-v8-rt` kernel is available for a later trial.
- **Decisions (later the same day):**
  - **Waveforms:** keep 60 fps.
  - **Sidebar:** hide external libraries through a multi-select touch
    **Sources** menu, like the column menu. This needs a Mixxx patch.
  - **USB copier:** leave it unpaced, because it never runs during a set.
  - **Key lock engine:** only after a blind listening test on two sets of
    songs at both ends of the range.
- **Key Lock Ear Test:** rendered 20 s clips of Cranes in the Sky, Osondu,
  Watch Your Step (Picard Brothers) and SPACE INVADER at −8 % and +8 %. Used
  the Pi's own RubberBand 3.3.0 (R2 real-time, as Mixxx sets it) and
  SoundTouch 2.4.0 (quick-seek), in 1024-frame blocks. RubberBand came out
  0.5–1.3 dB quieter every time, so each SoundTouch clip was lowered to match.
  Blind page: [Key Lock Ear Test](https://claude.ai/artifact/FjGjPQxjZtVzmBuHBK6bTY).
  Tooling: `deploy/keylock-ear-test-20261108/`. Mixxx was not touched, and
  the clips were removed from the Pi's `/tmp`. Results pending.
- **Second round of decisions:**
  - **Agreed:** pause maintenance during sets; the ⚙ panel; an FX tab with
    the Beat FX bugs fixed; keep the detailed RGB waveforms; one media
    LOAD/EJECT for the whole view, because sticks connect to the Pi, not to a
    deck; Raspberry Pi OS Trixie, stripped; greetd in a later phase; and
    trying read-ahead to see how far it can go.
  - **Asked for:** decks keep playing after eject, as on a CDJ. Rekordbox is
    the default source, with a Sources menu for a limited view of one,
    several or all sources. The in-Mixxx media slot ("lights") goes in the
    plan as phase 2.
- **Audio buffer test:** a throwaway Mixxx profile in `/tmp`
  (`--settings-path`, `--developer`), so `~/.mixxx` and its logs were
  untouched. Two decks played, plus a 600 MB SD write, 75 s per size. 23 ms,
  11.6 ms and 5.8 ms all ran with **zero ALSA restarts or underruns**. Worst
  fill was 52 %, 51 % and 58 % of the buffer. Audio-thread CPU was 12.8 %,
  14.9 % and 19.1 %. The worst callback (36–47 ms) happens even at 5.8 ms
  without an underrun, which supports a start-up one-off. Evidence:
  `deploy/buffer-test-20261108/`. Logs backed up to
  `~/.local/state/mixpi-backups/buffer-test-20261108-144315/`.
- **Power finding:** the user powers the Pi from a hub port. `lsusb` shows
  only the Pi 4's internal VIA hub, with the Starlight on it directly, so
  the 7-port hub is a power source only. Recommended: the official 5.1 V
  3 A supply straight into the Pi, with the hub on its own adapter.
  `throttled=0x0` since 2026-11-06, but mostly idle.
- **In progress (not on the Pi):**
  - Codex branch 1: Mixxx patches for configurable read-ahead and a RAM
    cache for tracks from removable media, plus a Mixxx-only arm64 CI build.
  - Codex branch 2: GPU fix in the image, set-time maintenance pause, and
    the Beat FX and track-number skin fixes.
  - Claude: a clickable prototype of the Pioneer view.
  - Nothing is pushed. Pushing and the CI build wait for the user's go-ahead.

## 2026-10-10

- **Spotify controls:** user asked for pause/play, next, previous and Spotify
  volume on the Pi during a Jam, in a centred dialog over a blurred Speaker
  screen that only closes by its own Close button. librespot 0.8.0 exposes no local controls, so the receiver changes to
  pinned go-librespot 0.10.3 with a loopback-only API. **Spotify controls** in
  the Speaker footer opens it. 126 tests passed on the Pi; the exact
  service command and control CLI were checked there from `/tmp` without
  touching the live session. Pushed as `d4897a0`, then **installed on the live
  Pi** at the user's request. The first attempt restarted only the Spotify
  service, which systemd extends to the whole speaker stack and so dropped the
  combined-output routes; the installer rolled back, and the second attempt
  stopped and started Speaker mode instead and restored the saved outputs and
  levels. The phone reconnected and played through go-librespot; the dialog
  showed the live track and volume. Transport taps, the slider and a Jam still
  need the user's hands-on check. Details: [`SPEAKER-MODE.md`](setup/SPEAKER-MODE.md#october-10-spotify-controls).
- **Recordings → USB:** user asked how recording works and for a way to move
  recordings off the Pi from the USB copier. Live config confirmed Mixxx saves
  16-bit WAV plus `.cue` to `~/Music/Mixxx/Recordings`; the pinned Pioneered
  skin has no REC button, so recording starts from **Browse → Recordings** or
  Ctrl+R. The copier is now **USB ⇄ Pi** with two directions. The new one lists
  every recording, ticked, and moves the chosen ones into `Mix Pi Recordings`
  on the drive, beside any Rekordbox `PIONEER`/`Contents`.
- **Safety:** copy, flush, read back from the drive, compare SHA-256, then
  delete the Pi original. No overwrite of a different same-named file; open
  (still recording) files are refused; a repeat finishes an interrupted move.
  **Music → Pi** skips the recordings folder. Procedure:
  [`usb-media.md`](skills/usb-media.md#move-recordings-onto-a-usb-drive).
- **Validation:** 116 tests passed on the Pi (2 optional fixtures skipped),
  including 20 native GTK checks at 800×412 run in an isolated headless Sway,
  and 16 new backend cases. The Mac run skips GTK.
- **Live deployment:** installed `mixpi-media`, `mixpi_ui.py`, `mixpi-settings`
  and the Waybar label. Moved fixture recordings to loop-mounted FAT32 and
  exFAT images; hashes matched after remount and the fixture export files were
  unchanged. Repeated on the physical screen by pointer taps. Fixtures, images
  and mounts were removed; Speaker mode and its audio services were not
  touched. Backup: `~/.local/state/mixpi-backups/recordings-20261010-151217/`;
  evidence: `deploy/recordings-20261010/`.
- **Not exercised:** no removable drive was attached, so real USB detection,
  write speed and eject remain a hands-on check, as does moving a recording
  made by Mixxx itself.

## 2026-10-03

- **Manual speaker timing installed:** added **Fine adjustment** to the Speaker
  screen. Its Audio sync menu has independent 0–500 ms delays for active outputs,
  ±1/±10 ms buttons, Apply & save, and Reset. Settings persist across sessions;
  the Starlight main and headphone/sub jacks remain separate. Nonzero delays use
  the `swh-plugins` stereo delay filter; zero bypasses it.
- **Validation:** 22 routing tests, 17 native GTK interaction/layout tests, and
  11 build/navigation checks passed. A private PipeWire 1.4.2 session on ARM64
  Debian measured 1, 50 and 500 ms settings within one sample (0.021 ms) on both
  stereo channels and verified reset/reuse/cleanup. The menu fits 760×350, with
  all three output rows visible. Evidence: `deploy/speaker-sync-20261003/`.
- **Live deployment:** after explicit user approval, installed the two helpers,
  `swh-plugins`, and the floating-menu rule on the Pi. Opened Fine adjustment
  with all three active outputs at zero delay. The actual menu fits the 800×480
  screen with an empty application log. Audio service PIDs, default sink, music
  routing and saved settings remained unchanged. Backup:
  `~/.local/state/mixpi-backups/speaker-sync-20261003-164504/`.
  The user is ready to perform the listening adjustment; audible alignment
  remains unverified.

## 2026-09-28

- **Pairing dialog repaired:** user reported a blank white popup. Actual GTK colors confirmed white text on a light `messagedialog` background missed by the original CSS selector. Added that selector, explicit dialog titles and a centered floating-window rule, plus a native contrast regression test. Deployed the fix; 12 native GTK checks and 61 host checks passed. At the user's request returned from Mixxx to Speaker mode and exercised the actual Pair phone button: readable instructions, discoverable/pairable for 180 seconds, Audio Sink advertised. Phone acceptance/audio remains unverified. Backup: `~/.local/state/mixpi-backups/dialog-20260928-210057/`; evidence: `deploy/ui-20260928/dialog-fix/`.

- **UI deployed over SSH:** installed the three new launchers and shared GTK theme from `d328221`, updated only the Settings window rule, validated/reloaded Sway, and visually verified all three actual screens at 800×412 with empty logs. Speaker remained active on Starlight; all audio service PIDs were unchanged. The internal export’s 613 receipt-listed files, inventory/receipt hashes and Mixxx profile hashes were preserved; database quick check passed. Backup: `~/.local/state/mixpi-backups/ui-20260928-204507/`. Local evidence: `deploy/ui-20260928/RESULTS.md`. No rebuild or reboot was needed.

- **Utility UI redesign:** saved the existing work to GitHub `main` (`3bf0bed`) before editing. Speaker, Settings and USB → Pi now share a dark DJ-style GTK theme, grouped controls and clearer states. Open Design, AlphaTheta and W3C references and implementation notes are in [the design contract](design/DESIGN.md).
- **Validation:** 61 host tests and 11 native GTK interaction/layout checks passed; the optional upstream skin fixture was skipped. Captures in `output/ui-review/` show real GTK rendering at 800×412 using fixture data. Added a native UI CI workflow. The later SSH deployment is recorded below; audible playback/phone pairing were not re-tested.

- **Speaker chat preserved:** at the user's request, saved the full requirements, agreed scope, September 25 installation, verification, backup/evidence paths, outstanding checks and failed chat-relocation attempt in [the Speaker mode chat handoff](handoffs/2026-09-25-speaker-mode-chat.md). The original task remains under panelai; it was not moved or deleted. This follow-up changed documentation only and did not reconnect to or alter the Pi.

## 2026-09-23

- **Follow-up requirement:** user wants to filter columns in the Pioneered folder/browser view. Added under GIG-02 in `POST-GIG-PLAN.md`; exact visible-column versus per-column value-filter behavior remains to be defined before implementation.
- **Checksums recorded:** image ZIP SHA-256 `2052320ad1ce7cb62a3081209188e8739d887d99a06a20169b303d9f1965342a`; copied-export manifest SHA-256 `ca02eaafe465a9910afa1daf50dbcb31f569c770fe0068119210f156919cbbd3`. Local and Pi manifest hashes match. All 613 export files previously matched the receipt and USB source. Machine-readable record: `deploy/new-install-20260923/CHECKSUMS.json`.
- **Shutdown completed:** at the user's request, closed Mixxx normally (log confirms shutdown code 0), closed the copier, synced filesystems and issued `systemctl poweroff`. The request was accepted and SSH became unreachable. Evidence: `deploy/new-install-20260923/SHUTDOWN.json`. The Pi is shut down; remaining migration items were not applied.
- **New-card user test:** user installed the newly flashed card and reports successful tests of the UI changes and Copy to Pi.
- **SSH restored:** the initial login failed because public-key setup was unfinished. User added the dedicated Mac public key through the Pi terminal. SSH now succeeds; the new authenticated host key is saved alongside the old card's keys. Temporary public-key server stopped.
- **New-card inspection:** correct 62,226,694,144-byte boot card and `bb47200` build; Mixxx 2.5.6. Root expanded to 56.5 GiB with 45.6 GiB available. Pioneered font/row defaults, Actions button, Browse scrollbars and top-bar helper are present. One automounter, no failed services, `throttled=0x0`, temperature snapshots 66.2–68.1 °C and no matching current-boot power/USB/filesystem errors.
- **Copy verified:** internal export has 613 files including 77 audio files, totalling 2,072,726,997 bytes. All SHA-256 hashes match both its receipt and MANTACORE. Mixxx database check passed; all main-library/Rekordbox file paths exist, including 77 internal-copy records. Evidence: `deploy/new-install-20260923/RESULTS.md` and adjacent JSON files.
- **Remaining migration:** Starlight master output is configured and active at 44.1 kHz, but its saved headphone cue routing and MIDI mapping have not carried over. `/media/SD-Backup` is empty. Of 41 old audio files, 39 are absent from the new export by content hash; the original backup remains safe. Preserve the user's new library/settings and restore remaining items selectively. Inspection did not change playback, restart Mixxx or restore files.

## 2026-09-22

- **Gig feedback:** first EthioJazz set was fun. Performance date was not supplied; this is the date the feedback was logged.
- **Power:** the user reports using the powered USB hub without its separate power supply connected; adding devices caused cutouts and the Starlight did not fully power up. Wants a better supply with USB-C disconnection accessible at the case. Exact hub/power wiring still needs confirmation.
- **Audio:** Starlight audio output worked better; internal Pi audio could be much louder. Retain this as an observation, not a measured gain or routing diagnosis.
- **Cable:** USB 3 extender was unreliable; excess draw/impedance is the user's suspected explanation, not a confirmed cause.
- **Requested:** automatically discover/scan multiple removable music devices and support DJ swaps; enlarge Pioneered library/menu targets and restore horizontal scrolling specifically in its Browse page; expose context menus using only capacitive touch.
- **Also captured:** automatic MIDI detection/mapping as a stretch item, permanently available stems software as a long-term item, and a simple file-transfer web app. User confirmed the app should be planned alongside the notes, not built now.
- **Initial inspection (before changes):** Pi 4B Rev 1.1, Mixxx 2.5.6, pinned Pioneered, native Wayland, and the ft5x06 touchscreen. Both `devmon` and `udiskie` were running; saved `RescanOnStartup=0`; Rekordbox support is enabled. `/media/SD-Backup` still contains `PIONEER` and `Contents`; root has about 5.8 GiB free.
- **Found before changes:** Pioneered explicitly gave its horizontal library scrollbar zero height/width and its vertical scrollbar only 4 px. Existing menu contrast fixes are installed. Mixxx provides a built-in selected-track context-menu control suitable for a touch button.
- **Power snapshot:** `throttled=0x0`, 54.5 °C, and no matching current-boot kernel power/USB-reset messages. Neither a removable music drive nor the Starlight was attached, so the gig fault, controller audio and device swaps were not reproduced.
- **Plan:** priorities, implementation steps, acceptance checks and rollback are in [`POST-GIG-PLAN.md`](ideas/POST-GIG-PLAN.md). The initial pass was read-only; the later user request authorized implementation/testing and a new-card build.
- **Implemented:** 17 px library text, 34 px rows, 26 px Browse scrollbars, larger menus, touch Actions button and first-run defaults; USB → Pi verified whole-export/ordinary-file copying; a pinned Mixxx patch for two-second Rekordbox source discovery; one automounter in new-image startup. Commit `22aa918` was pushed to `codex/pi-touch-bluetooth-build` with explicit user approval.
- **Tests:** latest host suite ran 57 cases (56 passed, one optional upstream-skin fixture skipped in that run; the supplied pinned-skin fixture had passed earlier). Live Pi transfer fixtures passed Unicode copy, SHA-256 receipt, repeat verification, cancellation cleanup and no-overwrite publication. Transfer UI fits 800×444 and recognizes the real 613-file, 2.073 GB export without unrelated OS/trash folders.
- **Live audio:** restarted Mixxx with the Starlight attached; saved mapping opened MIDI ports. Configured ALSA master channels 1–2 and headphones 3–4 at 44.1 kHz. User confirmed the playing-controller/touch check worked, then requested playback stop; both decks stopped and Mixxx closed cleanly to save settings.
- **Power test limits:** same hub as the gig. The two-deck telemetry interval was 20:16:34–20:19:55 (21 samples), not 30 minutes. All samples had `throttled=0x0`, attached USB and an active Starlight audio stream; peak temperature was 76.4 °C while SD music was also backed up over SSH. No matching kernel undervoltage/overcurrent/USB-reset messages. Dedicated-supply, extension comparison and two-drive insertion checks remain open.
- **Restart/scroll check:** Mixxx reopened with the saved large Browse layout, Starlight MIDI connections and active four-channel audio interface; decks stayed empty/stopped. Clicking the horizontal scrollbar exposed Key/BPM/duration and other right-side columns, then returned to the starting columns.
- **USB mounting:** retired the redundant running `devmon`; `udiskie` remains active. UDisks unmount/remount from the active desktop succeeded and the transfer plan returned the same 613-file export. This was a filesystem remount, not physical unplugging or a two-USB handover. SSH-launched UDisks mount needed the desktop session for PolicyKit authorization.
- **Top-bar follow-up:** added and tested a direct **USB → Pi** button beside Settings. It fits at 800 px and reuses its existing window on repeat activation. The `bb47200` image includes it directly.
- **Build fix:** first attempt compiled/linked the media patch and generated the ARM64 Mixxx package, then failed during desktop assembly because a helper-install glob included `__pycache__`. Fixed regular-file selection and added a stage-execution regression test; pushed `bb47200` on the approved branch. Corrected build [35761701616](https://github.com/GitariDev/mixxx-pi-gen/actions/runs/35761701616) passed all stages.
- **Live media checks:** installed verified arm64 Mixxx `2.5.6+rmodified-1` with no dependency changes. Alias add/remove and idle MANTACORE unmount/remount updated the sidebar automatically within the 5–6 second checks while SD-Backup stayed selected. Temporary alias cleaned up, USB mounted, Browse restored and music stopped. Evidence is in `deploy/live-media-20260922/RESULTS.md`; two physical USBs during playback remain untested.
- **Image written and verified:** artifact `10710887081` downloaded to `deploy/touchscreen-35761701616/`; outer and both inner SHA-256 checks passed. Raw image size 6,345,981,952 bytes with valid FAT32/Linux partition bounds. After the user requested writing and completed macOS authentication, Imager 2.0.11.1 wrote the reidentified 62,226,694,144-byte external SD card (`disk8`) and passed full read-back verification. Evidence: `imager-write-complete.png` and `BUILD-VERIFICATION.json` beside the image. The card auto-ejected despite the disabled preference; reconnecting it for SSH public-key provisioning remains pending.
- **Migration prepared:** current SD music backup contains 320 files / 1,075,207,881 bytes; a separate stopped-session settings archive preserves `.mixxx`, test logs and rollback configuration. All 320 music files match the Pi by SHA-256 and size; the Rekordbox symlink is correct, and SQLite integrity check passed. Archives are local under `deploy/migration-20260922/` and excluded from Git. The replacement card is written and verified; physical swap, restore and new-card acceptance remain pending. MANTACORE and the original running Pi card were preserved.

## 2026-09-12

- **Logged:** DJ-001 for reviewed BPM/key metadata, Spotify-derived main genre, and Every Noise native My Tags; DJ-002 for local-audio beat/downbeat analysis and Rekordbox grid import.
- **Researched:** SongData.io public API access remains unconfirmed; Spotify's artist genre field is deprecated; Every Noise is based on Spotify data and needs source/coverage verification.
- **Learned:** file tags, XML grids, and native My Tags require distinct integration paths. Analysis Lock protects analysis/grid results; reviewed records and backups provide recovery for other edits.
- **Proposed:** evaluate Beat This! on representative problem tracks, prove one-track Rekordbox import behavior, then build the Python commands and package native executables.
- **Status:** requirements and acceptance criteria recorded in [`DJ-LIBRARY-TOOLS.md`](ideas/DJ-LIBRARY-TOOLS.md); no new tools implemented or music/library files changed.

## 2026-08-19

- Established this journal and the query-friendly `docs/skills/` runbook directory.
- Reviewed the image-builder repository and confirmed:
  - Mixxx is built from the `2.5` branch.
  - Sway launches Mixxx on workspace 1 and forces the main window fullscreen.
  - `wvkbd` provides the touch keyboard from the Waybar keyboard icon.
  - `udevil`/`udiskie` are included for removable media and `PrivateMounts=no` is set for udev.
  - PipeWire audio, `qpwgraph`, Nautilus, `wdisplays`, and controller udev rules are included.
  - The Pioneered and `pi_dj` small-screen skins are bundled during the build.
- Reviewed the three setup photos and recorded component identifications in [`setup/HARDWARE.md`](setup/HARDWARE.md).
- Reviewed recent Mixxx Pi task history:
  - Initial HDMI install and smoke-test runbook was created.
  - The image was verified and tested via USB boot on a Raspberry Pi 4B.
  - An early USB flash attempt disconnected partway through; stable power and direct connections remain important.
  - Fullscreen skin Settings was initially mistaken for Preferences; `Ctrl+P` is the reliable path.
  - The controller was identified as a Hercules DJControl Starlight.
  - A 5 V fan may share the Pi's 5 V/GND rails with the display, subject to power budget and correct pin selection.
- Created initial plans for playlists, incoming tracks, effects, and an auxiliary control surface.
- Research conclusion: Mixxx can support this direction well through playlists/crates, Auto DJ, keyboard mappings, MIDI/HID mappings, JavaScript mapping logic, effect chains, and command-line startup options.
- Incorporated the supplied six-page **DJ Skills & Moves List** into the notebook:
  - adopted a consistent four-hot-cue scheme suited to the Starlight's four pads per deck;
  - added runbooks for phrasing/cues, fades/EQ handoffs, loops/tempo matching, sampling, and recorded practice;
  - expanded incoming-track acceptance and playlist selection criteria;
  - preserved the learning order: selection/cues, fades, loops/tempo, then sampling.
- **Setup update:** the Preferences/settings and no-keyboard issue is resolved. A USB mouse now provides reliable navigation.
- **Controller direction:** the Hercules Starlight is the current baseline, but an upgrade/replacement is planned. The target model is not selected yet.
- Added a connection-agnostic controller upgrade brief so future controllers, audio devices, storage, displays, and auxiliary inputs remain replaceable rather than hard-coded.

## Entry template

## YYYY-MM-DD

- **Changed:**
- **Tested:**
- **Learned:**
- **Problem:**
- **Idea:**
- **Next:**

### 2026-11-08 — Taller Browse navigation on performance branch

- Created `feat/pi-performance-target` from `main`, retaining the recovered work
  and separate cooling changes in the working tree.
- Extended the HTML source pane on the right from the toolbar through the deck
  title strip (290 px tall). This geometrically overlaps Deck 2’s title; Deck 1
  remains on the left. Both overview strips and all transports remain visible.
- Replaced nested disclosure arrows with full-row navigation into Rekordbox,
  MANTACORE, playlists and folders, with Back. Preserved the fixed Show/Hide
  control, search, selection and the broad translucent loop overlay.
- Focused headless checks passed at 800/728/390 px, including collection filters,
  loading, source preferences, USB removal/reinsert and sheet/tab restoration.
- Updated the remaining native work in PERFORMANCE-PLAN.md. No native skin,
  audio settings or Pi deployment changed in this UI revision.
