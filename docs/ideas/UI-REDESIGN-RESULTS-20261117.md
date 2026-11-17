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
