# UI redesign climb results, 2026-11-17 (tracked record)

Plan: `docs/ideas/UI-REDESIGN-PLAN-20261117.md` (owner answers in 10.1). Tuner record: `mixpi-ui-redesign-20261117`. Prototype: `docs/ideas/ui-redesign-20261117/prototype/` (published privately). Updated at each gate. Evidence folders under `deploy/` stay untracked.

## Gates

| When | Commit | Mac suite | Native gate (VM b) | Notes |
|---|---|---|---|---|
| Wave 0 baseline | `cdc5c1b` | exit 0 | 135/135, 0 skips | Held options `a8a86fa`, `72e98c4` cherry-picked as `6bda16f`, `cdc5c1b` |
| Wave 1 integrated | `9d9bf30` | 642 run, OK (133 platform skips) | 153/153, 0 skips | N1 save-on-change + stop unit, N2 Sources rail/edit + scan bar, S shell/pads/Load sample/Sources/icons |
| Wave 1 skin fix | `ec580e1` | builder: 619 OK | not needed (skin only) | Sampler layout, Choose pad stacking, Sources search, header Back removed, EDIT LIST → DONE |
| Wave 2 skin + R-14 fix | `2c21ede` | builders green | not needed (skin and system files) | S: deck page, tool panel, FX 1/FX 2, full-screen Settings, chip states, Load sample hand-off, full-height views; N1: logind delay inhibitor |
| Wave 2 media (N3) | `7f6b677` | 679 run, OK (135 platform skips) | 164/164, 0 skips | Media page, chip state, insert ping, Safe strip, handover, gated engine-A eject |
| Wave 2 browse (N4) | `c4a00bd` | 689 run, OK (137 platform skips) | 174/174, 0 skips | Load sample keeps its own place, grouped Sources |
| Wave 2 final skin | `67341f2` | skin + sample-browser modules OK | not needed (skin only) | USB source button; Choose pad from Tracks returns to Tracks |
| Post-B and council R1 repairs | `fb1a119` | 710 run, OK (141 platform skips) | 190/190, 0 skips | 42 patches. Skin: EDIT LIST command no longer drives the label, waveforms hidden for every screen ≠ 0, chip writes screen 2 first, USB/SYNC chips, ±N% caption. Native: Media page under the skin root (styled) and opened after the screen write; tempo range saved to `[Controls],RateRangePercent`; late top-bar confirm re-checked; media lists keep their widgets and scroll, drag-scroll with 24 px bars, bounded handover and eject-user lists, `mixpi_from_usb`; scan strip moves to the deck-info row while a tool panel is open; `sidebar_sources_editing` set with setAndConfirm (read-only control) |
| Build C baseline | `ef0874d` | 710 run, OK (141 platform skips) | 190/190, 0 skips | Handoff state of thread 2 |
| Wave C1 integrated | `dda4966` | 732 run; 1 error in `test_chroot_runtime` (5 s timeout while the native gate ran), then 3 of 3 OK alone | 206/206, 0 skips | S1 skin (U-1, U-2, U-3, U-6, U-7 skin, Settings header), N-A Sources side menu and edit list, N-B Media page and `drive_insert` |
| Wave C2 integrated | `85dc076` | 761 run, OK (146 platform skips) | 227/227, 0 skips (at `123b5e6`; `85dc076` adds only a generator change and its unit test) | 48 patches. S2 skin, N-C controls and saving, N-A2 Sources repairs; the backlight udev rule |
| Wave D1 integrated | `335a75b` | 786 run, OK (150 platform skips) | 236/236, 0 skips | 50 patches. S4 fonts back to build B and shorter loop rows at 800×444; N-D1 ★ for the saved start, current-row edge, Edit sources child rows; N-D2 narrowed table fits, OPEN and BROWSE switch to Tracks; C3 skin repairs |

## Wave 0 on the test card (build 2)

- Settings and logs backed up: `deploy/ui-redesign-20261117/stage0/backup/`.
- Before shots of every page: `deploy/ui-redesign-20261117/stage0/before-*.png`.
- Routing set to stereo at the owner's request (Q8): Master 1-2, Headphones 3-4 on the Starlight's USB audio (4 channels FL FR RL RR). Backup on the card: `~/.mixxx/soundconfig.xml.before-stereo-20261117`. After a reboot Mixxx kept it (`stage0/reboot-1.txt`).
- The card's journal is volatile, so the shutdown order of the previous boot cannot be read; R-14's Pi check uses Mixxx's own "shutdown complete" line.

## Wave 1 skin preview on build 2

`deploy/ui-redesign-20261117/wave1-preview/`: top bar, ☰/✕, ✎ Actions, 8 pads with Stop/Clear, full-screen Sources, Load sample render on today's Mixxx. Four skin defects found and fixed in `ec580e1` (see above); re-check after build A.

## Builds

| Build | Commit | State |
|---|---|---|
| A | `9d9bf30` (+ skin tools from `ec580e1`) | pi-gen exit 0 on VM b in 11 min 15 s; 33 patches; check phase all pass; installed in place on the test card 08:30 (`deploy/test-image-20261117a/`, `deploy/ui-redesign-20261117/buildA-update/`): every expected sha256, `dpkg -V` clean, controlled media OFF, media eject OFF |
| B, run 1 | `67341f2` | **aborted**: pi-gen exit 0 and the check phase passed, but the file listing failed with I/O errors when the Mac's disk filled (VM b's disk file in /tmp grew to 27 GB). The image was discarded; the owner approved deleting two old images to free space. Counted as a pi-gen run. |
| B, run 2 | `67341f2` | pi-gen exit 0 in 9 min 29 s; 37 patches; check phase all pass; Mac free space logged (lowest 20 GiB); VM trimmed after; installed in place 10:30 (`deploy/test-image-20261117b/`, `acceptance-B/`) |

**Build count against the plan's ceiling (one build = one pi-gen run):** A, B run 1 (aborted), B run 2 = **3 runs**. A build C for the post-B repairs would be the **4th run**, past the contract's ceiling of 3, so it needs the owner's explicit yes (asked 2026-11-17).

## Build A on the test card (`deploy/ui-redesign-20261117/buildA-checks/`, `wave2-preview/`)

| Item | Result |
|---|---|
| R-13 settings | PASS: keylock change written within ~1 s, kept after `kill -9`, no temp file left (`r13-keylock-kill.txt`) |
| R-13 sampler bank | PASS: pad 6 in `samplers.xml` within 3 s, kept after `kill -9` (`r13-pad6-kill.txt`) |
| R-14 service stop | PASS: `systemctl --user stop` → "shutdown complete with code 0" in 0.6 s |
| R-14 reboot | FAIL on build A (log ended 33 s early, no shutdown line): the stop unit and the LightDM session scope stop in parallel, so sway died first (`r14-diagnose.txt`). Fixed by `2c21ede` (logind delay inhibitor, `InhibitDelayMaxSec=20`), applied in place: reboot → "shutdown complete with code 0" 0.7 s after the request, the change made just before the reboot kept, inhibitor re-armed at boot (`r14b-after.txt`) — PASS |
| R-15 | udiskie runs with `--no-notify` after reboot. Pop-up check with a drive: pending (MANTACORE port disabled, see below) |
| R-9 rail | PASS: tiles with sub-lines, Back, crumb (Computer › Quick Links › Music), drill-down |
| R-9 from Load sample | FAIL then fixed in skin `2f46f22`: a leaf pick in Sources opened from Load sample now returns to Load sample |
| R-10 edit list | renders with Up/Down, switches, ★, Start here (`wave2-preview/x04-edit.png`); persistence check pending |
| R-7, R-8 | 8 pads with Stop/Clear; Choose pad sheet opens and loads; the empty-pad → Load sample → LOAD TO PAD n path did not load once (re-check in acceptance) |
| Wave-2 skin preview (R-16, R-17, R-18, chip) | Deck page, tool panel LOOP/JUMP/CUES, FX 1/FX 2 with route switchers, Settings full screen, chip "NO USB". Defects fixed in `228215c`: full-height views, tabs from Settings, cut text |

**MANTACORE:** after each reboot its hub port (1-1 port 2) flaps (234 USB disconnects in 4 h, never attached as a disk: no `/dev/sd*` mount in the journal, no exFAT lines). The port is disabled after each boot (`echo 1 > /sys/bus/usb/devices/1-1:1.0/1-1-port2/disable`). Eject, handover and the R-5 load measurement need a working drive.

## Build B acceptance on the test card (`deploy/ui-redesign-20261117/acceptance-B/ACCEPTANCE.md`)

Build B (`67341f2`) was installed in place at 10:30-10:33 by following `deploy/test-image-20261117b/UPDATE.md`:
- Every step passed: 61 files OK, 37 patches, `dpkg -V` clean, and the skin tree equals the expected tree.
- The eject gate was opened (owner Q2). `/etc/mixpi` had to be created. Settings › Media shows Eject ON.

The checks ran 10:33-11:18, with 2 reboots and 64.7-70.1 °C, `throttled=0x0` throughout. Result: **51 PASS, 5 FAIL, 6 BLOCKED (drive)**.

- **PASS:**
  - R-1, R-7, R-8: the empty-pad 7 path now loads.
  - R-9 (grouped tiles, and back to Load sample).
  - R-10: kept after a restart, then restored exactly.
  - R-11.
  - R-12: bar, Hide → chip %, kept after a restart, SHOW, Cancel in 0.07 s.
  - R-13: settings, pad and deck time all kept after kill -9; ten changes while playing gave 0 underruns.
  - R-14: `systemctl reboot` and the power-menu Restart both log "shutdown complete with code 0" in under 2 s.
  - R-16: F-4 at 86-87 px per beat; CPU readout 4 %, 0 underruns.
  - R-17, R-18.
  - R-19 (F-5, F-6, F-9, F-10 with no drive).
  - Holdout: REC 33.8 s gives WAV + CUE; F-1, F-2, F-3, F-7, F-8, F-11; pads, loop and FX.
- **FAIL:**
  1. R-2: opened from DECKS, the Media page has the waveform area (x 92-800, y 48-408) drawn black over it.
  2. R-4: the Media page is unstyled (Qt default light grey, system font), although `style.qss` has its rules.
  3. R-13: Tempo range is never saved, not even on a clean quit (`RateRangePercent` stays 8).
  4. R-10: the edit-list button never reads DONE.
  5. F-14: the first Show top bar after a start once raised "Top bar was not confirmed" (1 of 3 tries).
- **BLOCKED (drive):** MANTACORE flapped again when its port was enabled (16 disconnects in 17 s; the port is disabled again). Blocked: R-4 insert ping, LOAD/DISMISS and chip states; R-5 handover and the Q3 RAM-copy gate; R-6 eject and the Safe strip; the R-9 drive tile; the R-15 pop-up check; the R-20 storm.
- **Owner state restored:** RB Fast, pads 1-2 only, Sources and scan bar as found, time remaining, stereo routing, top bar hidden, Mixxx on DECKS. The eject gate stays.

## Council round 1 (at `24d2b3a`, build B on the card)

| Seat | Score | Main blockers |
|---|---|---|
| Claude Opus 5.5 xhigh | 6 | repairs unbuilt; tempo range; F-14 cause; Q3 gate before C; evidence on the card only; build count; two unlisted deck-row departures |
| Claude Fable 5.2 high | 6 | tempo + F-14 open; repairs unbuilt; media never on hardware (≤ 8 without a drive or a written deferral); scan strip over the focused waveform |
| GPT-6.1 Sol xhigh | 6 | repairs on C; six drive checks + Q3 gate; Media list refresh/scroll/overflow; screenshots and hands-on Starlight |

Reports: `deploy/ui-redesign-20261117/council/round1-*.md`. Every code finding is repaired at `fb1a119`. Build B's screenshots are now on the Mac (`acceptance-B/shots/`), and the Starlight steps are marked NOT RUN. Still needed: build C (a 4th pi-gen run, owner's yes asked), a working USB drive (owner asked), and a short hands-on Starlight session (owner asked).

## Owner UI review and the build C go (2026-11-17)

- **The review:** the owner reviewed every screen over five rounds in a private review page and agreed every item. The owner's notes are in `docs/ideas/UI-REVIEW-1-20261117.md`.
- **The binding spec:** `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md`, with 12 mockups and the design CSS. Commit `2b1365d`.
- **The plan:** section 12 adds U-1 to U-10, the precedence rules, a rubric amendment (reviewers judge conformance, not taste) and the budget.
- **The tuner:** record `mixpi-ui-redesign-20261117` revision 7 adds U-1 to U-10 and the spec as a source. The harness approved it on the owner's chat instruction of 19:13, which produced **revision 8**.
- **Build C:** approved as the 4th pi-gen run. Any later build needs the owner's yes. Council rounds: 1 of 5 used.
- **Next:** the climb continues in a new orchestrator thread, by the owner's "thread migrate" request.

## Build C climb (orchestrator thread 2, from 2026-11-17 22:20)

**Handoff:** tuner record `mixpi-ui-redesign-20261117` revision 8 (approved). Branch head `ef0874d`. Card: build B, Mixxx on DECKS, 66.2 °C, `throttled=0x0`, MANTACORE port disabled, eject gate open. Deck 1 SYNC turned off (it was on from testing). Mac free space 18 GiB: below the 20 GB needed for a build, so space must be freed before build C.

**Baseline at `ef0874d`:** Mac suite 710 run, OK (141 platform skips).

### Wave plan for U-1 to U-10 (plan 12.2)

Builder rules for build C: `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` (spec first, mockups, "No design of your own; where the spec is silent, build B stays").

Shared registries stay with the orchestrator: `MIXXX_PATCHES`, `PREREQUISITES`, `REQUIRED_TESTS`, and now the stylesheet list in `pioneered-touch.py`. `pioneered-menus.qss` is read by many tests, so it is not split. Instead each native builder writes its page's rules in a new stylesheet file that loads after it, and the old Sources and Media sections are removed in wave C2.

**Wave C1: three builders.**

| Builder | Items | Repo files owned | Mixxx source files patched |
|---|---|---|---|
| **S1** (skin) | U-1 (skin and general dialog rules), U-2, U-3, U-6 skin, U-7 skin (ON/OFF button, full-height fills), deck-row title and artist (s6) | GEN `mixpi-performance.py`, QSS-P, PT-PY, QSS-T, QSS-M (general sections only, not Sources or Media), `tests/test_performance_skin.py`, `tests/test_pioneered_touch.py`, `tests/test_touch_dialog_styles.py`, `tests/test_library_interface.py` | none |
| **N-A** (Sources) | U-4 native: the side menu on the right, its headers, rows and scroll bar; the full-screen edit list | new `mixxx-sources-menu.patch`, new `mixpi-sources-menu.qss`; `tests/test_sources_screen.py`, `tests/test_source_groups.py`, `tests/native/library_interface_sources_*`, `tests/native/source_groups_*`; new tests | `src/widget/wlibrarysidebar.{h,cpp}`, `src/widget/touchsourcenavigation.h`, `src/library/library.{h,cpp}`, `src/widget/libraryinterface.h` |
| **N-B** (Media) | U-10 Media page; U-8 native (`[MixPi],drive_insert`, ASK or AUTO LOAD) | new `mixxx-media-agreed.patch`, new `mixpi-media-page.qss`; `tests/test_media_screen.py`, `tests/test_media_handover.py`, `tests/test_media_transfer_display.py`, `tests/native/media_screen_*`, `tests/native/media_handover_*`; new tests | `src/widget/mixpipage.h`, `src/library/mixpimediapage.h`, `src/library/mixpimedia.h` |

Then: registration commit, both gates, skin preview on the card (build B's native), and a first conformance look.

**Wave C2: up to three builders.**

| Builder | Items | Repo files owned | Mixxx source files patched |
|---|---|---|---|
| **S2** (skin) | U-4 skin side (from N-A's handover note), U-5 skin (pads with ▶ TRIGGER and ■ STOP, header, empty pads, the Clear samples popover), U-8 and U-9 Settings rows, CPU readout show or hide, fixes from the C1 preview, removal of the dead Sources and Media sections from QSS-M | GEN, QSS-P, PT-PY, QSS-T, QSS-M and the skin tests | none |
| **N-C** (controls) | U-7 effects saved within a second of a change; U-5 Clear samples controls; U-9 brightness, Night dim and CPU readout controls, and the backlight write access (new system file) | new patches (`mixxx-effects-save.patch`, `mixxx-agreed-controls.patch`), a new udev rule under `stage3/02-desktop/files/`, its install line, new tests | `src/effects/*` (the save path), `src/coreservices.cpp`, `src/widget/mixpiperformancesettings.h`, new files |
| repair | only if C1 integration or the preview finds a native defect, on that builder's files | | |

Control names fixed now, so the skin and native builders can work in parallel:
- U-8: `[MixPi],drive_insert` 0 = ASK (default), 1 = AUTO LOAD; saved.
- U-9: `[MixPi],backlight` 5-100 (%), `[MixPi],backlight_available`, `[MixPi],night_dim` 0 or 1, `[MixPi],show_cpu` 0 or 1 (default 1); all saved.
- U-5: `[MixPi],sampler_clear_open`, `[MixPi],sampler_clear_tick1`…`8`, `[MixPi],sampler_clear_count`, `[MixPi],sampler_clear`.

Then: registration commit, both gates, skin preview, native renders next to the mockups, Mac free space at least 20 GB, then **build C** (the 4th pi-gen run, approved), in-place update, acceptance C, conformance pass, council round 2.

### Wave C1 result (2026-11-17, 22:40-23:35)

- **Builders** (Claude Opus 5.5 medium, own worktrees): S1 skin `7680c14`, `99aee21`; N-A Sources `1f7e2b9`, `5b1a61f`; N-B Media `489f581`, `457c1f0`; registration by the orchestrator.
- **Native renders next to the mockups:** the side menu and the edit list (N-A) and the Media page (N-B) match `m-sources-top`, `m-sources-edit` and `m-media` in structure, order, copy, roles and colours.
- **Skin preview on the card** (build B's native, `waveC/c1-preview/`): the tool panel, Tracks, FX, Load sample and the Settings header match their mockups. Deviations found, all for wave C2:
  - the deck row shows the badge centred, with the title only (FX, Sampler) or nothing (tool panel open), and never the artist;
  - the Settings rail labels are centred (drawn left-aligned);
  - Settings › Media Eject shows a plain ON label (drawn as a toggle);
  - the FX selector's ▾ sits in a separate box, and "SELECT EFFECT…" is not dim (needs a native property);
  - the open effect list and the Arrange dialog tick keep build B's colours (tests lock them).
- **Deviations the builders reported, for wave C2:** no counts on rekordbox lists; ★ disabled on the drive and Samples rows (Mixxx could only start Tracks at a top-level source).
- **Owner questions (no change without the owner):**
  1. The edit list shows the six top rows as drawn, so This Pi's own lists (Playlists, Crates, Auto DJ) and More's (iTunes, Serato) can no longer be switched on or off on screen. Build B could.
  2. ★ on a switched-off row is drawn disabled.
  3. With the desktop top bar shown (800×444) the tool panel's EXIT LOOP / RELOOP row is cut off.
  4. Under the READY and IN USE filters, a drive that is ejecting or safe to remove still shows (so it does not vanish mid-eject).
- **Card note:** the deck time showed REMAINING while `mixxx.cfg` held `PositionDisplay 0`, so the restart came up ELAPSED. One tap saved `PositionDisplay 1` within 5 s, so the save path works. The earlier state was live only.

### Wave C2 result (2026-11-17 23:40 to 2026-11-18 00:40)

- **Builders** (Claude Opus 5.5 medium, own worktrees):
  - S2 skin: `c2fbebc`, `c6a9ac6`, `2fb8864`, `85dc076`.
  - N-C controls: `b633757`, `76a849d`, `ae8fea5`.
  - N-A2 Sources repairs: `5f98518`, `2c0e550`, `2d64c6a`, `1efd4cd`.
  - Registration by the orchestrator: `2ae88f3`, `c845cbc`. Runner cleanup: `123b5e6`.
- **New patches (48 in all):** `mixxx-effects-save.patch`, `mixxx-save-within-second.patch`, `mixxx-agreed-controls.patch`, `mixxx-sources-menu-fixes.patch`. **New system file:** `stage3/02-desktop/files/udev/99-mixpi-backlight.rules` (the video group may write the backlight level), installed by `03-run.sh`.
- **Measured on VM b (N-C fixtures):**
  - A settings change reaches `mixxx.cfg` in 555-686 ms. It was 1395 ms; the save now waits for 500 ms of quiet instead of 1000.
  - An effect change reaches `effects.xml` in 441-597 ms, and is kept after `SIGKILL`.
  - A burst of 50 settings changes gives 1 write, and 10 effect changes give 1 write.
- **Night dim level: 10 % of max** (26 of 255 on the test card), one constant `kNightDimPercent`. Reported to the owner, who may tune it.
- **Card preview of the skin on build B's native** (`waveC/c2-preview/`):
  - Matches its mockup: the deck row (badge, title, dimmer artist, then the SYNC and MASTER pills), the Sources header (search, ✎, red ✕) with the table narrowed and the panel over deck 2's half, the Sampler header and pads, Settings › Media (ASK / AUTO LOAD and the note line), Settings › Interface (rows as drawn) and FX (▾ inside the field).
  - The pad top rows were centred at first; S2 fixed them in `85dc076`, and the fix was checked on the card.
  - Parts that need build C's native to show: the side menu's content, Clear samples, Brightness, CPU show and hide, and the dim "SELECT EFFECT…".
- **Rekordbox lists** now have counts, and inside a drive the place reads "MANTACORE › rekordbox". ★ works on the drive row and on Samples.
- **Listed deviations, with reasons:**
  - The Clear samples list scrolls by its 24 px bar only, with no drag scrolling. A skin scroll area has none.
  - ★ is drawn disabled on a switched-off row.
  - The side menu has no drop shadow; Qt graphics effects are costly on the Pi.
- **More owner questions (no change without the owner):**
  5. CLEAR (n) with a ticked pad that is playing: Mixxx refuses to empty a playing pad (build B's × CLEAR was off while a pad played), so that pad keeps playing and stays loaded while the others clear.
  6. With ★ on the drive row and a drive plugged in, Tracks opens the drive at start (read only). Build B never opened a drive by itself.
- **Gates:** Mac suite 761 run, OK (146 platform skips) at `85dc076`; native gate 227/227, 0 skips at `123b5e6`.

## Build C (2026-11-18)

- **Build:** operator Claude Opus 5.5 medium, one pi-gen run on VM b from `135a4bf`. Exit 0 in 14 m 40 s (0 ccache hits). 48 patches. `.deb` `5d7aa7aa…`. `finish-image.sh check` and candidate verify pass. Mac free space 21 GiB at the start, lowest 7 GiB, 22 GiB at the end. Kit: `deploy/test-image-20261118c/`.
- **In-place update** (orchestrator, 00:57, `deploy/ui-redesign-20261117/buildC-update/`):
  - Steps 0-9 all passed: 67 files, 48 patches, 9 skin tools, `dpkg -V` clean, the skin tree as expected (48 files), the backlight rule installed (the panel is `root:video` with group write), the eject gate unchanged, controlled media OFF.
  - Mixxx rewrote `soundconfig.xml` at start in a different line order. The routing is unchanged (Master 1-2, Headphones 3-4).
- **The owner's spare stick GANDER1** (3.8 GB FAT, rekordbox export, 196 tracks, USB 2.0, hub port 1) was plugged in about 00:50. Every drive check ran on it, and nothing was written to it.
- **Conformance pass** (orchestrator, `acceptance-C/conformance/k*.png`): every spec screen was shot on the card next to its mockup.
  - Matches: Tracks, the Sources menu (top level and inside a drive, "GANDER1 › rekordbox" with counts), Edit sources (layout), the tool panel, Sampler, FX ("SELECT EFFECT…" dim), Load sample, Settings › Media and › Interface, and the Media page (one drive).
  - Deviations, skin (fixed in place after build C by builder S3, `f06ad3f`, `5752aac`):
    - the Clear samples list showed one row at a time with an arrowed scroll bar, and only the tick box toggled;
    - with the Media page open, the tab stayed lit and the chip did not.
  - Deviations, native (build D):
    - no ★ in Edit sources for the owner's saved start `RekordboxFeature`; the menu's accent edge sat on This Pi and Tracks opened on the Rekordbox info page;
    - the narrowed table keeps full-width columns (sideways bar, KEY cut).
- **Acceptance C** (tester Claude Opus 5.5 medium, `deploy/ui-redesign-20261117/acceptance-C/ACCEPTANCE.md`): **45 checks, 43 PASS, 2 FAIL, 0 BLOCKED.**
  - **FAIL R-4:** OPEN on the Media page reads the drive and then reads BROWSE, but goes back to the tab you came from instead of Tracks.
  - **FAIL U-4:** the ★ defect above.
  - **PASS:**
    - all five of build B's FAILs (Media page not overdrawn and styled, tempo range saved in 0.58 s and kept after kill -9, Edit sources DONE and kept, SHOW TOP BAR 3 of 3);
    - all six of build B's BLOCKED drive checks, now on GANDER1 (chip states, OPEN, eject with the Safe strip, a five-cycle eject storm, no udiskie pop-up, ASK and AUTO LOAD, filters, eject while a deck plays from the drive with the footer "1 track playing from Pi memory");
    - samples kept over a reboot, with "shutdown complete with code 0"; CLEAR (2) leaves the sample files byte-identical;
    - effects saved in about 0.5 s and kept after kill -9;
    - every settings change on disk within 1 s (0.52-0.68 s);
    - the holdout (REC gives WAV + CUE, F-1 to F-11, F-4 at 86-87 px per beat); 65.7-70.1 °C, `throttled=0x0`.
  - **Q3 gate: PASS.** CPU readout average 3.40 % with RAM cache 1024 against 3.37 % with it OFF, a ratio of 1.010 (gate ≤ 1.10). 0 underflow lines in either 5-minute run. So the RAM copy ships, as approved.
  - **Notes:**
    - Mixxx's underrun counter read 1 in the session after the reboot; the moment is unknown (pad loads, the first two-deck run and REC were in it). A fresh session read 0 before and after two decks plus Reverb with 10 effect changes.
    - EJECTING is never seen, because the unmount takes under 0.4 s.
    - No plug-in ping shows while the Media page is open.
    - Clearing a pad that is playing does nothing and says nothing.
    - GANDER1 was already marked "not properly unmounted" before testing; no fsck was run, since the stick must not be written.
- **Owner state restored by the tester:** `mixxx.cfg`, `samplers.xml` and `effects.xml` copied back; two tracks loaded and paused; SYNC off; time REMAINING; panel 255; Night dim OFF; CPU SHOW; top bar hidden; GANDER1 READY; MANTACORE's port disabled. One difference: deck 1 shows 127.00 at ±0 instead of 118.00 at −7.1 %.

## Owner decisions after build C (2026-11-18), and build D

Plan 12.5 and spec 2a record them:
- all fonts back to build B;
- **build D approved (the 5th pi-gen run)**;
- the Edit sources child rows come back;
- shorter loop rows while the desktop top bar shows;
- the Starlight session later;
- **at most 3 agents running at a time**, all kinds counted.

### Wave D1 (2026-11-18 morning)

- **Builders** (Claude Opus 5.5 medium, own worktrees, three at once, the owner's cap):
  - S4: `8bf674c`, `4872049`.
  - N-D1: `ef11be3`.
  - N-D2: `9a0da7d`, `0060f82`, `4af56f5`.
  - Registration by the orchestrator: `335a75b`.
- **OPEN's cause** (N-D2): opening the drive wrote `[Tab],library` while the skin's page stack was hidden behind the Media page. A hidden `WWidgetStack` ignores its triggers, so closing the page brought back the old tab. The fix closes the page first, then switches to Tracks.
- **Skin preview on build C's native** (`waveD/d1-preview/`), all as intended:
  - fonts back to build B's (deck time, BPM and key in Open Sans; the Settings rail in Ubuntu Condensed 18 bold);
  - the loop panel at 800×444 with all four rows (39 px each);
  - the Clear samples list showing both rows, ticked by a tap on the name;
  - the USB chip lit, with no tab lit, on the Media page.
- **N-D1 render:** Edit sources with the owner's start shows ★ and "TRACKS STARTS HERE" on the drive row, and This Pi's child rows indented with ON/OFF only.
- **Next:** build D (the 5th pi-gen run, approved), in-place update, targeted acceptance D, conformance pass, then council round 2.

## Build D (2026-11-18)

- **Build:** operator Claude Opus 5.5 medium, one pi-gen run (the 5th, owner-approved) from `ce2186c`.
  - Exit 0 in 9 m 26 s (759 of 790 ccache hits). 50 patches. `.deb` `b44299e4…`.
  - Every check passes. Image C → D changed exactly the expected files.
  - Mac free space: 33 GiB at the start, after the owner chose to clear `~/Library/Caches`; 18 GiB at the lowest.
  - Kit: `deploy/test-image-20261118d/`.
- **In-place update** (orchestrator, `buildD-update/`): steps 0-9 all pass. The backlight rule and the eject gate are unchanged.
- **Conformance pass** (orchestrator, `acceptance-D/conformance/d*.png`), every spec screen against its mockup, in build B's fonts:
  - Tracks opens GANDER1 at start, with the edge on GANDER1;
  - the narrowed table fits four columns and gets its widths back when the menu closes;
  - Edit sources shows ★ and "TRACKS STARTS HERE" on GANDER1, and This Pi's child rows indented with ON/OFF;
  - OPEN switches to Tracks;
  - the popover and the lit chip work.
- **Acceptance D** (tester Claude Opus 5.5 medium, `acceptance-D/ACCEPTANCE.md`): **31 checks, 28 PASS, 3 FAIL, 0 BLOCKED.**
  - **FAIL:** after OPEN or BROWSE on the Media page, the Sources menu reopens inside This Pi with its edge there, not on the drive (native).
  - **FAIL:** Load sample → SOURCES…: the narrowed Samples table's last header is cut to "DURATIO" by its scroll bar (native).
  - **FAIL:** the empty FX selector reads "SELECT EFFECT." because build B's font no longer fits the field (skin).
  - **PASS:** ★ and the saved start with and without the drive; the child rows kept over restarts; the table fit and the full widths kept; OPEN and BROWSE from DECKS, SAMPLER and FX; fonts equal to build B's with nothing clipped elsewhere; all four loop rows at 800×444 (35 px), working; the skin repairs; saves within 1 s (0.40-0.67 s); effects kept after kill -9; samples kept; two eject-and-replug cycles; REC; F-4 at 86-87 px per beat.
  - **CPU:** two decks plus Reverb for 2 minutes averaged 4.33 % (build C's matching run read about 4.0-4.1 %), with 0 underruns and 67-69 °C, `throttled=0x0`.
- **Owner state restored** (sha256 match): the saved start `RekordboxFeature`, Playlists OFF, two tracks loaded and paused, panel 255, top bar hidden, GANDER1 READY.
- **In-place repair after acceptance D** (builder S5, `2eedc8f`, `buildD-inplace-1/`): the FX selector's padding and ▾ zone now give the text 147 px, so "SELECT EFFECT…" shows in full in build B's font (the text is 144 px; the area was 133 px). Installed as one skin tool, with the skin regenerated from the upstream originals: `style.qss` `49df2a8f…`, `skin.xml` unchanged. Checked on the card (`e01-fx.png`).
- **Conformance pairs for the council:** `acceptance-D/pairs/*.png`, each mockup on the left with build D on the card on the right.

## Council round 2 (at `d75c1fe`, build D on the card)

| Seat | Score | Main blockers |
|---|---|---|
| Claude Opus 5.5 xhigh | 6 | Unlisted: Edit sources has no drag on row text; the REC dot is white (the mockups draw it red). Listed: the edge after OPEN, "DURATIO", Clear samples drag |
| Claude Fable 5.2 high | 6 | Unlisted: Edit sources drag; EXIT LOOP and RELOOP drawn lit while a loop is on. Listed: the edge after OPEN, "DURATIO"; the owner session not yet run |
| GPT-6.1 Sol xhigh | 6 | Unlisted: the table's alternate rows are `#32323c` (the mockups use `#161a20`); Edit sources drag. Listed: the edge after OPEN, "DURATIO" |

Reports: `deploy/ui-redesign-20261117/council/round2-*.md`. All three are real seats, with no stand-ins. Each seat confirmed that round 1's findings are repaired or overridden by the agreed spec, and that the other screens match their mockups.

**Owner decisions (plan 12.6, spec 2b):**
- Edit sources drag, the "DURATIO" header and Clear samples drag are accepted as they are.
- Build E (the 6th pi-gen run) carries the edge after OPEN and BROWSE, and "Stop it, then clear" for a ticked pad that is playing.
- The skin repairs go in too.
- The owner session runs after build E.

### Wave E1 (2026-11-18 afternoon)

- **Builders** (Claude Opus 5.5 medium):
  - N-E `83174c8`, `54a8256`:
    - The Sources menu follows a drive opened with OPEN or BROWSE. The cause: `featureSelect` moved the sidebar's current row, but the menu's own source, BACK floor and place stayed on the last source picked in the menu.
    - A ticked playing pad is stopped, then emptied.
  - S6 `b9ab450`, `8d7ecdd`, `ee024dd`: the library tables take the mockups' row colours (`#000`, alternate rows `#161a20`, text `#e4e7ec`, selected `#263b51`); EXIT LOOP and RELOOP stay at rest while a loop is on; the REC dot is red `#d0574d`.
  - Registration by the orchestrator: `db4beb9` (52 patches).
- **Gates at `ee024dd`:** Mac suite OK (150 platform skips); native gate 242/242, 0 skips.
- **In place on build D** (`buildD-inplace-2/`): the three skin tools from `ee024dd` installed, and the skin regenerated from the originals. Checked on the card: the red REC dot, EXIT LOOP and RELOOP at rest with a 4-beat loop on, and the darker alternate rows.
- **Card note:** the owner was playing on the card during the in-place installs ("I was using the deck"). The deck-time change seen then (REMAINING to ELAPSED) was the owner's own, not a bug, and the owner's setting is kept. The owner: "Don't let me interrupt. I'll stop you if i need too."

## Build E (2026-11-18)

- **Build:** operator Claude Opus 5.5 medium, one pi-gen run (the 6th, owner-approved) from `c87fff8`.
  - Exit 0 in 10 m 36 s (769 of 790 ccache hits). 52 patches. `.deb` `5583ca72…`.
  - Every check passes. Image D → E changed exactly the expected files.
  - Mac free space: 31 GiB at the start, 15 GiB at the lowest, 30 GiB at the end.
  - Kit: `deploy/test-image-20261118e/`.
- **In-place update** (orchestrator, `buildE-update/`): steps 0-9 all pass. The three skin tools were already at `c87fff8`'s bytes from the in-place install. The skin tree is as expected. The eject gate and the backlight rule are unchanged.
