# Mixxx Pi journal

## Master overview

- **Goal:** a compact, touchscreen-first, standalone-feeling DJ system built on a Raspberry Pi and Mixxx.
- **Current rig:** Raspberry Pi 4B; generic 7-inch 800×480 DSI touchscreen; USB mouse; Hercules DJControl Starlight as the current/temporary DJ controller; portable USB storage; external speaker; portable power under test.
- **Software:** the current build pins Mixxx 2.5.6 and Pioneered on 64-bit Raspberry Pi OS Trixie. SSH inspection on 2026-09-22 confirmed those versions, Sway 1.10.1, an 800×480 display at scale 1, and native Wayland Mixxx in an 800×444 window below the top bar, without forced fullscreen.
- **Working:** first EthioJazz gig completed. The live Pi now has larger Browse rows/menus, horizontal scrolling, an Actions button for track context menus, and a USB → Pi copier accessible directly from the top bar. Starlight master/cue routing and the saved MIDI mapping were exercised; the user confirmed the audio/controller/touch test worked.
- **Known friction:** gig power cutouts and the USB 3 extension remain unresolved. General touchscreen long-press and live MIDI auto-discovery are still open; automatic Rekordbox discovery is installed and passed silent checks with one USB plus SD.
- **Next milestone:** finish selective migration on the verified new card: restore Starlight MIDI mapping/headphone cue routing and the older music while preserving the user's new library. Removable-device handovers and a sustained power test remain outstanding; see [`POST-GIG-PLAN.md`](ideas/POST-GIG-PLAN.md). Controller upgrade planning remains in [`CONTROLLER-UPGRADE.md`](setup/CONTROLLER-UPGRADE.md).
- **Longer-term direction:** support replaceable DJ controllers, audio interfaces, storage, displays, and auxiliary control surfaces without baking a single device into the core image.
- **DJ preparation tools:** two open issues cover Rekordbox metadata/genre enrichment and beatgrid repair; see [`DJ-LIBRARY-TOOLS.md`](ideas/DJ-LIBRARY-TOOLS.md). These are proposed Python tools with executable packaging, separate from the Pi image.
- **Backlog:** browser-based transfer and individual-playlist selection (the first copier handles a whole export), automatic MIDI mapping (stretch), and permanently installed stems tooling (long term; exact software/format unconfirmed).

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
