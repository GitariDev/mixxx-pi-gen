# MixPi UI redesign: build plan, 2026-11-17

Author: Claude Fable 5.2 (high), design sub-agent. Branch `feat/pi-performance-target`, head `6e06c13` (the code review was done at `08d1a6a`; `6e06c13` adds only the spec and the prototype).
Status: plan for owner review. Nothing here is built. No file other than this one was changed.

Source of truth: `docs/ideas/UI-REDESIGN-REQUEST-20261117.md`. **The owner's words win** over the spec, over the prototype and over this plan.

What was read:

| Input | State |
|---|---|
| Owner request and the six photos (rotated with `sips -r 270`) | Read. |
| `ui-redesign-20261117/REDESIGN-SPEC.md` | Read and checked against code. Corrections are in section 2. |
| Prototype `prototype/mixpi-ui.html` and `prototype/mixpi-ui.js` | Read in full. The script arrived on disk after the code review; this plan was then revised against it. Where the plan departs from the prototype, section 4.2 lists it with a reason. The prototype's "Your calls" panel is empty by design: it waits for this plan's questions (`window.MIXPI_CALLS`). Section 10 gives each question the prototype screen (`go`) and highlight (`hl`) to point at. |
| XDJ-AZ manual | Read (downloaded, text extracted). Cited as **MAN p.N** (printed page number). |
| grasp.study lesson | Read without a login. It says: insert the drive and the port ring lights up; press SOURCE and select the drive; browse; load; the track is then "in memory". To remove: hold **USB Stop** until the light stops blinking. |
| Code, tests, evidence | Read as cited below. |

Reference names:

- **GEN** = `stage3/01-install-packages/files/mixpi-performance.py`. **QSS-P** = `mixpi-performance.qss`. **PT-PY** = `pioneered-touch.py`. **QSS-T** = `pioneered-touch.qss`. **QSS-M** = `pioneered-menus.qss`.
- **PATCH/name:line** = a line in `stage3/01-install-packages/files/mixxx-name.patch`.
- **PIN** = pinned Mixxx 2.5.6, `3ebac449…` (bare repo `/tmp/mixpi-actions-routing-objects-20261115`).
- **PT** = patched tree `/tmp/mixpi-actions-routing-source-20261115`. It holds only the patched files and is older than `dialog-wording` and `council-fixes`; where those patches matter, the patch file is cited.
- **TOOLS** = `deploy/recovery-20261116-fixes/tools` (`pi.sh`, `ui.sh`, `shot.sh`, `vtouch.py`, `pxdiff.py`).
- **EV** = `deploy/recovery-20261116-fixes`.
- **PROTO** = `docs/ideas/ui-redesign-20261117/prototype/mixpi-ui.js`.

## 1. Constraints

- The EOS card and the MANTACORE USB are read-only for us. Never write, move or delete anything on `/media/pi/MANTACORE`. Do not use `TOOLS/pi.sh` on EOS.
- USB drives stay mounted read-write (owner decision). Tests never write to MANTACORE. **Every eject, handover and USB-storm test uses a spare stick, never MANTACORE** (an unmount of a read-write volume can update its flags, and MANTACORE has a loose connection).
- Never touch the Lima VMs `colima-mixpi-ui` and `colima-synthetic`. The builder VM is Lima `b` (`LIMA_HOME=/tmp/mq1110-1943`). Each job uses a new `/srv/<name>-<date>` workspace. Keep at least 24 GB free.
- **Controlled media and eject stay OFF until the owner approves the new media design.** This plan builds the new design behind a gate (R-6). Every image and every package from this plan ships with the gate closed.
- Push only `feat/pi-performance-target`. No merge, no rebase. No new dependency without a stated reason. This plan adds none.
- Do not edit existing Mixxx patches. New Mixxx changes go into new patches at the end of `MIXXX_PATCHES` (`stage3/01-install-packages/01-run.sh:4-34`). Each new patch gets `PREREQUISITES` in `tests/test_mixxx_patches.py:68-92`. Each new native test module goes into `REQUIRED_TESTS` (`tools/performance/required-native.py:15-35`).
- Gates:
  - Mac: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`. Platform skips are expected.
  - VM `b`: `QT_QPA_PLATFORM=offscreen python3 -B tools/performance/required-native.py`, 0 skips. Last gate: 128/128 at `053c618`; 135/135 with the held options.
- Existing `deploy/recovery-*`, `deploy/migration-*` and `deploy/test-image-*` folders are read-only evidence. New evidence goes into new `deploy/` folders.
- Test card: the 64 GB card in the Pi 4. Prefer an in-place update from a file-level image diff (method: `deploy/test-image-20261116b/DEPLOY-FILES.txt`). A flash is done by the owner by hand.
- Quit Mixxx with Ctrl+Q before a restart, until R-14 is on the card (a service stop does not save settings: `EV/field-fix-acceptance-b2/ACCEPTANCE.md`, finding 1).
- Back up `~/.mixxx` logs before restart-heavy tests (Mixxx keeps 10).
- Keep the owner's Wi-Fi, BT keyboard, audio routing and Sources settings. Never write `soundconfig.xml`.
- The fan is unplugged. Log `vcgencmd measure_temp` and `get_throttled` in every Pi session. Pause playback above 80 °C.
- GTK tests run on the Pi only.

## 2. Facts checked in code, and corrections to the spec

| # | Spec, prototype or brief statement | What the code says | Effect on the plan |
|---|---|---|---|
| 1 | Sampler pads: deck A = samplers 1-4, deck B = 5-8; the script raises `num_samplers` to 8 | True. PIN `res/controllers/Hercules DJControl Starlight.midi.xml:522-559` and `:784-821` (`cue_gotoandplay`), LEDs `:1499-1573` (`play_indicator`); script `:76-78`. The skin asks for 4 (GEN `:400-402`) and draws 4 (GEN `:333`, `:353`). `slotChangeNumSamplers` only grows (PIN `src/mixer/playermanager.cpp:265-278`), so with a Starlight there are already 8 samplers and 4 are invisible. | R-7. |
| 2 | "Handover can build on the RAM cache"; PROTO eject step "Copy N items in use to the Pi" | Half true. The reader copies the whole file to `/dev/shm/mixpi-track-cache` **at load time**, before it opens it (PATCH/removable-ram-cache `:36`, `:465-580`), for decks and samplers alike. The copy is deleted when its last user lets go (`:309-314`) and stale copies are deleted at start (`:414-416`). **But the open audio source also keeps a use lease on the drive** (PATCH/media-selection `:2146`, `:2286`; PT `src/sources/audiosourcetrackproxy.h:23`). The lease holds an `O_PATH` descriptor on the mount (PT `src/library/media/mediause.h:15-16`; released at PT `mediauseregistry.h:40-49`). So a loaded deck blocks a drain and an unmount today, even when it plays from RAM. A copy made at eject time would need the deck to reload, which stops its sound. | R-5 is a real code change. The eject step becomes "keep", not "copy". |
| 3 | "Eject… is off (controlled media OFF)" | Not exactly. **Eject… is enabled whenever a drive is selected** (PATCH/media-continuation `:477`). It opens a second dialog that can do nothing (R-4). The owner's photo `IMG_0316` shows that dead end. | R-4 answers C-4. |
| 4 | Eject "powers the port down" | No code does this. The broker only unmounts (`mixpi-mount-broker.py:240-244`). | Cut. Section 8. |
| 5 | Media card "SCAN"; Settings "on insert: SCAN" | A USB drive is not a Mixxx music directory. The scan in `IMG_0310` is of `/home/pi/Music`. Scanning a drive would add its tracks to the Pi library, where they go missing after an eject. | Cut. Section 8. |
| 6 | One `<Library>` widget per skin? | Yes. `Library::bindLibraryWidget` keeps one pointer (PT `src/library/library.cpp:409-411`, `:474`). `LibraryControl::bindLibraryWidget` disconnects the old widget and takes the new one (PIN `src/library/librarycontrol.cpp:564-570`). `[SamplerN],LoadSelectedTrack` reads that one widget's table (PIN `librarycontrol.cpp:603-608`). PT-PY `:172` refuses a skin with more than one. The sidebar and the search box are bound once too (PT `library.cpp:342-351`). | R-8 picks the implementation. |
| 7 | FX cards "name their Starlight FX pad" | Only right for deck A. Deck A pads drive effect unit 1 (PIN midi.xml `:444-481`). **Deck B pads drive effect unit 2** (`:706-743`). The FX page shows unit 1 only (GEN `:205`). | R-17. |
| 8 | Scan bar "1,240 of 3,050" | The scanner has no total. The bar is indeterminate (PATCH/quiet-scan `:101-104`). | R-12 defines an honest %. |
| 9 | "These are the XDJ-AZ pad modes" | Hot Cue, Beat Loop, Slip Loop, Beat Jump; 8 hot cues A-H (MAN p.94-95). **The XDJ-AZ has no sampler pad mode.** | The sampler is MixPi's own, shaped by the Starlight. |
| 10 | Brief: the scan bar "must not cover the transport row" | Owner: "With the hide it is okay that it covers". Both hold if the bar sits above the transport row, as PROTO draws it. | R-12. |
| 11 | PROTO Sources tiles: MANTACORE, This Pi, Recordings, History, Folders, Samples | Mixxx's top level is one row per feature: Tracks, Auto DJ, Playlists, Crates, Computer, Recordings, History, Rekordbox and so on (PT `library.cpp:101-200`). Drives are children of Rekordbox or of Computer. The prototype's tiles are a new grouping. | R-9, question 4. |

What "access" means in Mixxx terms today:

| Level | What happens | Who starts it today |
|---|---|---|
| 0 Mount | The volume appears at `/media/pi/<label>`, read-write. | udiskie, on insert (`stage3/02-desktop/files/i3.conf:231`). With the controlled profile: the broker, on request (`mixpi-mount-broker.py:286-314`). |
| 1 Detect | Mixxx re-reads the mount table every 2 s and checks each mount for a rekordbox export (PATCH/media-hotplug `:187-188`; PT `src/library/rekordbox/rekordboxfeature.cpp:175-225`). File-exists checks only. | Automatic. |
| 2 Open as a source | Mixxx reads the rekordbox database, or lists folders, and shows the drive in Tracks (PT `library.cpp:654-700`). | The owner: **Load** in the dialog, or a tap on the drive in Sources. |
| 3 Use a track | Copy to RAM, decode, analyse. | A load to a deck or pad. |
| 4 Library scan | Not done for USB drives. | — |
| 5 Write to the drive | Mixxx writes nothing (tag export is off; DJ-003 is backlog). | — |

So the Pioneer model fits what the code already does: insert is automatic (levels 0-1), **access is level 2 and is the owner's tap** (MAN p.53 "Selecting a source"), and eject is the deliberate, safe action (MAN p.51).

## 3. Coverage map

| Request entry | Kind | Item |
|---|---|---|
| `IMG_0316` Eject and media: Pioneer way, choose access, choose eject, keep last track for handover, clean after | owner | R-3 (model), R-4, R-5, R-6 |
| `IMG_0315` Redesign Load/Eject; load is automatic, eject is the safe action | owner | R-4 |
| `IMG_0314` Full-length sample menu that may cover the tracks; one Load button, then Choose pad | owner | R-8 |
| `IMG_0313` Sample selection nearly impossible; 8 slightly larger pads; Load opens a browse menu; separate from the browse list but similar | owner | R-7, R-8 |
| `IMG_0311` Revisit Sources; easier to navigate; big menus cover the whole screen | owner | R-1, R-9, R-10 |
| `IMG_0311` Actions = pen icon; Show = hamburger that turns into an X | owner | R-11 |
| `IMG_0310` Scan bar: file name only, Hide and Cancel, save the hidden setting, USB icon with % | owner | R-12 |
| Overall: modern and clean, keep the layout's spirit, touch-first, works with the Starlight, inspiration from the XDJ-AZ | owner | R-1, R-16, R-17, R-18, sections 7 and 8 |
| Save on settings change | owner | R-13 |
| Process: prototype, plan, questions with screenshots, 3 builders, council to 9 | owner | sections 5, 10, 11 |
| C-1 round-1 repairs, unbuilt (`053c618`) | carried | R-19 |
| C-2 `a8a86fa` clean quit | carried | R-14 |
| C-2 `72e98c4` udiskie `--no-notify` | carried | R-15 |
| C-3 save on change; reboot must stop Mixxx first | carried | R-13, R-14 |
| C-4 F-10 on the Pi with a drive; "Prepare selected disk" | carried | R-4 (answer), R-19 (Pi check) |
| C-4 tracked results file | carried | R-20 |
| C-4 one-time sway crash after a USB storm | carried | R-20 |
| C-5 routing mono 1/2 versus 1-2/3-4 | owner check | R-21, question 8 |
| C-5 MANTACORE loose connection | owner check | R-21, question 9 |
| C-5 DJ-003 in the backlog | owner check | R-21, question 10. No change. |
| C-5 USB stays read-write | owner decision | Section 1. No change: udiskie and the broker both mount read-write (`mixpi-mount-broker.py:229-231`). |
| Starlight drivability | brief | Section 7, R-16, R-17 |
| XDJ-AZ additions in the spec | brief | Section 8 |

## 4. Design decisions settled in this plan

### 4.1 The screen model

1. **One screen control.** A skin-only control `[MixPi],screen` says which full-screen view is open: 0 none, 1 Sources, 2 Media, 3 Load sample, 4 Choose pad, 5 Settings. The two bottom rows (overviews and transport) show only when it is 0. Every tab and every ✕ writes 0. This is PROTO's `RD.ovl`.
2. **Two kinds of full-screen view.** Views with fixed content are skin pages (Sources, Load sample, Choose pad, Settings). The Media screen has dynamic content (drives, users, steps), so it is a native page: a child widget of the main window under the top bar, not a dialog. The session caps dialogs at 780×420 (`FIELD-FIX-PLAN-20261116.md` F-2), and a child widget needs no window manager.
3. **No widget ever sits over a live waveform.** When a full-screen view opens, the skin has already switched the waveform rows off (the GEN `:476-478` pattern). This keeps the rule in GEN `:534-535` ("focus avoids native GL stacking").
4. **Full-screen views have no touch CUE or PLAY.** The Starlight keeps play, cue, sync and PFL. One tap on ✕ brings the rows back. The owner allowed this: "we can cover the whole screen because its deeper context".
5. **Every touch target is at least 48 px in both directions.** A unit test enforces it. PROTO has a few 40-44 px buttons; they become 48.
6. **The handover copy lives in RAM** unless the owner picks the SD card (question 3). RAM is what exists, it is cleaned without new code, and it does not write to the SD card while audio plays.

### 4.2 Departures from the prototype

The orchestrator should change the prototype to match, or bring a row to the owner if they disagree.

| Prototype (PROTO) | Plan | Reason |
|---|---|---|
| Pad strip: STOP and ⋯, 40 px high; pad about 98 px | Pad 200×104: tap area 56 px, strip 48 px with **Stop** and **Clear**. No ⋯ menu. | 48 px rule. The owner asked for one load button; an empty pad still opens Load sample for itself, as PROTO does. |
| Pad progress fill | Lit while playing only. | A skin button has no progress fill; it needs a native widget. Later. |
| Eject step 2 "Copy N items in use to the Pi"; step 4 "power down the port" | Step 2 "Keep N items playing from their Pi copies"; step 4 "Unmount and check". | Section 2, rows 2 and 4. |
| Media card buttons EJECT, BROWSE, COPY TO PI, SCAN | EJECT, BROWSE, COPY TO PI. No SCAN. | Section 2, row 5. COPY TO PI starts the existing `mixpi-media` tool, as PROTO's own note says. |
| Settings › Media "on insert: READY / ASK / SCAN" | READY / ASK only, and only if question 1 keeps both. | Same. |
| USB chip: drive name, state text with deck numbers, a progress ring | Drive name (one unconfirmed step, R-4), fixed state words, and a % number. No ring. | A skin button shows fixed texts per state and a number. A ring needs a native widget. |
| Scan strip "1,240 of 3,050" | "42%" of folders. | Section 2, row 8. |
| Tracks rows: deck badges on loaded tracks, coloured key chips | Mixxx's table as it is today (F-7, F-8 columns). | Both need new table delegates. Not asked for; later. |
| Tracks bottom: a two-line LOAD button with the deck's title inside | A 104 px LOAD button with the deck title in a label beside it, inside the same 230 px cell. | A skin button cannot carry live text, and a label on top of a button would take its taps. |
| Load sample rows: two lines and a 48 px preview button; a "Selected" footer text | Mixxx's table rows (48 px). No preview. The footer has the LOAD TO PAD… button only; the selected row is highlighted. | R-8: one library widget. Preview plays to the headphone output only, and routing is an open owner check (R-21). |
| Choose pad title "Load "<track>" to which pad?" | "Load to which pad?" | Live text. |
| Sources edit: Up, Down and a switch per row | Same, with 48×48 buttons, plus **Start here** for the start source. | The start source exists today (PATCH/library-interface `:165`) and the owner uses it (`EV/field-fix-acceptance/ACCEPTANCE.md`, finding 11). |
| Deck chips: ON PI, USB, SYNC, MASTER | The same, plus **PFL**. | The Starlight toggles PFL (section 7). |
| FX: one unit | A unit switch, FX 1 / FX 2 (question 5). | Section 2, row 7. |

## 5. Work order, waves and builds

### 5.1 Build honesty

One "build" is one pi-gen run on VM `b`. Build 2 took 12 min 14 s for packages and image together, with a warm ccache (`deploy/test-image-20261116b/BUILD.md`). The check phase, the native gate (about 3.5 min), the compress-and-copy and the file-level diff add about 13 min. The in-place update on the card and the Pi acceptance run take much longer than the build; I give no number for them because none was recorded as a total.

| Build | Carries | When |
|---|---|---|
| **A** | C-1 (`053c618`, already committed), R-14, R-15, R-13, R-12, R-9/R-10 native part, all wave-1 skin work | After wave 1 passes both gates |
| **B** | R-2, R-4, R-5, R-6 (gate closed), R-8 native part, R-9 grouping if chosen, all wave-2 skin work | After wave 2 passes both gates |
| **C** | Repairs from the Pi run and the council | Reserve |

**Planned: 2 builds. Honest ceiling: 3.** Flashes: 0 (in-place updates from a file-level diff). The field-fix climb needed 2 builds and prepared a third; this plan assumes the same.

What can be checked without any build, on the card as it is today (build 2), by copying the new GEN and QSS files to the card and running `/opt/mixpi-skin-tools/pioneered-touch.py` and then `/opt/mixpi-skin-tools/mixpi-performance.py`:

| No build (skin generator and QSS) | Needs a package build (Mixxx patch) | System files (in-place copy, no package) |
|---|---|---|
| R-1 shell and screen control; R-7 8 pads; R-8 skin part (full-screen Load sample, Choose pad); R-9 skin part (full-screen Sources as one list); R-11 icons; R-16 deck page and tool panel; R-17 FX units; R-18 Settings | R-2, R-4, R-5, R-6, R-8 native part, R-9 rail, crumb and grouping, R-10, R-12, R-13, R-14 patch | R-14 unit and helper, R-15, R-6 gate file (owner-approved check only) |

A skin with new controls is safe on the old program: Mixxx creates empty controls for unknown keys (`FIELD-FIX-PLAN-20261116.md` F-4, risk note). The USB chip then shows no state and still opens the old dialog. Before a skin-only preview, save `skin.xml`, `style.qss` and the seven tool files with their sha256, and restore them afterwards. The official update copies the built `style.qss`; a re-run of the generators on the card is not byte-equal (`DEPLOY-FILES.txt`, warning in section A).

### 5.2 Waves and file ownership

Rule: no two builders in a wave touch the same repo file, and no two native builders in a wave patch the same Mixxx source file. Three files are shared registries: `01-run.sh` (`MIXXX_PATCHES`), `tests/test_mixxx_patches.py` (`PREREQUISITES`), `tools/performance/required-native.py` (`REQUIRED_TESTS`). **Builders do not commit changes to them.** Each builder hands over a registration note (patch name, prerequisites, test modules). The orchestrator makes one registration commit per wave.

**Wave 0 — orchestrator, no builder, no build.**
- Record the owner's answers (section 10) in this file.
- If approved: cherry-pick `a8a86fa` and `72e98c4` from `prep/owner-options-20261117` (each applies alone).
- Create the tracked results files (R-20).
- Stage-0 reads on the test card, one SSH session: the shutdown-order journal (R-14 step 2), the sway-crash logs (R-20), a `grim` shot of every current page for the before/after set.

**Wave 1 — three builders.**

| Builder | Items | Repo files owned | Mixxx source files patched |
|---|---|---|---|
| **S** (skin) | R-1, R-7, R-8 skin part, R-9 skin part, R-11 | GEN, QSS-P, PT-PY, QSS-T, `tests/test_performance_skin.py`, `tests/test_pioneered_touch.py` | none |
| **N1** (saving) | R-13, R-14 system part | new `mixxx-save-on-change.patch`; new `tests/test_save_on_change.py`, `tests/native/save_on_change_*`; new `stage3/02-desktop/files/systemd/mixpi-mixxx-stop.service`, new `stage3/02-desktop/files/sbin/mixpi-stop-mixxx`, `stage3/02-desktop/02-run.sh` (install lines), new `tests/test_shutdown_order.py` | `src/preferences/configobject.{h,cpp}`, `src/coreservices.cpp`, `src/mixer/playermanager.cpp`, `src/mixer/samplerbank.{h,cpp}` |
| **N2** (library) | R-9 native part, R-10, R-12 | new `mixxx-sources-screen.patch`, new `mixxx-scan-progress.patch`; QSS-M; new `tests/test_sources_screen.py`, `tests/test_scan_progress.py`; extends `tests/native/library_interface_sources_test.cpp`, `tests/native/library_scanner_strip_test.cpp`, `tests/test_quiet_scan.py`, `tests/test_touch_dialog_styles.py` | `src/library/library.cpp`, `src/widget/libraryinterface.h`, `src/widget/wlibrarysidebar.{h,cpp}`, `src/library/scanner/libraryscannerdlg.{h,cpp}`, `src/library/scanner/libraryscanner.{h,cpp}` |

Then: registration commit, both gates, a skin preview on the card, **build A**, in-place update, Pi checks of wave 1 and of C-1.

**Wave 2 — three builders.**

| Builder | Items | Repo files owned | Mixxx source files patched |
|---|---|---|---|
| **S** | R-4 skin part (USB chip), R-16, R-17, R-18, ON PI chips, scan % | GEN, QSS-P, QSS-T, `tests/test_performance_skin.py`, `tests/test_pioneered_touch.py` | none |
| **N3** (media) | R-2, R-4, R-5, R-6 | new `mixxx-media-screen.patch`, then new `mixxx-media-handover.patch` (same builder, in this order); QSS-M; `stage3/02-desktop/06-run.sh`, `tools/performance/accepted-artifact.py`, `tests/test_controlled_media_profile.py`, `tests/test_accepted_artifact.py`; new `tests/test_media_screen.py`, `tests/test_media_handover.py`, `tests/native/media_screen_*`, `tests/native/media_handover_*`; updates `tests/native/media_ownership_test.cpp.in` | new `src/widget/mixpipage.h`, new `src/library/mixpimediapage.h`; `src/library/mixpimedia.h`, `src/sources/soundsourceproxy.cpp`, `src/sources/audiosourcetrackproxy.h`, `src/sources/removabletrackcache.h` |
| **N4** (browse) | R-8 native part; R-9 grouping if question 4 says so | new `mixxx-sample-browser.patch`, then new `mixxx-source-groups.patch`; new `tests/test_sample_browser.py`, `tests/test_source_groups.py`, `tests/native/sample_browser_*`, `tests/native/source_groups_*` | `src/library/library.{h,cpp}`, `src/widget/wtracktableview.cpp`, `src/widget/wlibrarysidebar.{h,cpp}`, `src/library/browse/browsefeature.{h,cpp}` |

N4 builds on N2's wave-1 changes to `library.cpp` and the sidebar; that is across waves, so there is no conflict. N3 must not touch `library.cpp`: the media object already gets its callbacks there (PT `library.cpp:215-226`).

Then: registration commit, both gates, **build B**, in-place update, full Pi acceptance (R-22), council.

**Wave 3 — repairs.** One builder per failing area, same ownership rules, then **build C** if needed.

Order of the items below: the sweeping ones first (R-1 shell and screen model, R-2 page host, R-3 to R-6 media), then the views (R-7 to R-12), then saving and shutdown (R-13 to R-15), then polish (R-16 to R-18), then the carried items and acceptance (R-19 to R-22).

### 5.3 Planned hit map

Coordinates are for the 800×480 screen with the desktop bar hidden (the default). They come from the planned sizes, which follow PROTO. **Each Pi check starts with `TOOLS/shot.sh` and confirms its coordinates on that shot before the first tap.** The skin builder also adds a unit test that the fixed sizes of each page sum to 800×480.

| Area | Targets (x, y) |
|---|---|
| Top bar, y 24 | DECKS 42 · TRACKS 129 · FX 209 · SAMPLER 294 · USB chip 527 · REC 649 · gear 717 |
| Decks transport, y 452 | Deck 1: KEY 27, Q 79, SYNC 137, LOOP 201, CUE 273, ▶ 356. Deck 2: add 400. |
| Tool panel (y 48-304) | Tabs at y 76: LOOP 182, JUMP 288, CUES 394; CLEAR 627; CLOSE 737. Cue tiles: x 106/302/498/694, y 141 (1-4) and 217 (5-8). Jump: x 177/290/403/516/629/742, y 134 (back) and 196 (forward). |
| Tracks | ☰ (24,72) · ✎ (776,72) · rows at y 152/200/248/296/344 · bottom y 452: LOAD 1 at 57, CUE 1 at 318, LOAD 2 at 457, CUE 2 at 718 |
| Sources | ✕ (24,72) · EDIT LIST (730,72) · rail tiles x 132, y 128/192/256/320/384/448 · Back (316,120) · rows x 530, y 172/228/284/340/396/452 |
| Media | ✕ (24,72) · EJECT (114,208) · BROWSE (290,208) · COPY TO PI (430,208) · sheet: CANCEL (400,308), EJECT (570,308) |
| Sampler | LOAD SAMPLE (101,72) · pads x 100/300/500/700 · row 1: tap y 124, strip y 176 · row 2: tap y 228, strip y 280 · Stop at x−50, Clear at x+50 |
| Load sample | ✕ (24,72) · source buttons at y 124 · rows at y 208/256/304/352/400 · LOAD TO PAD… (667,448) |
| Choose pad | Tiles x 144/315/485/656, y 176 (pads 1-4) and 280 (pads 5-8) · CANCEL (682,92) |
| Settings | ✕ (24,72) · rail x 100, y 124/180/236/292 |
| Scan bar (y 376-424) | HIDE (650,400) · CANCEL (750,400) |

---

## 6. Items

## R-1 Shell: top bar and the screen control — owner-requested

- **Problem:** Big menus share the screen with the decks. In `IMG_0313` the list has about 166 px left between the toolbar, the LOAD TO row, the titles, the overviews and the transport. Tabs show "active" with a 2 px border only.
- **Root cause (read in code):**
  - The overview and transport rows are outside the page stack and are always shown (GEN `:488-511`). Only single buttons are tab-scoped (GEN `:505-506`).
  - Sources is a 290 px pane over the right side of the table (GEN `:316-320`, `:343`). Sample loading is a row inside the Tracks page (GEN `:331-343`). Settings is a view inside the Decks page (GEN `:298-299`, `:444-447`).
  - Tab style: QSS-P `:12`.
- **Change (GEN, QSS-P):**
  1. Top bar 48 px, in PROTO's order: DECKS 84, TRACKS 90, FX 70, SAMPLER 100, spacer, USB chip 150 (replaces the `LOAD / EJECT` button at GEN `:440-443`; its state wiring comes in R-4), ● REC 76, gear 48, CPU 56. Active tab: filled, with a 3 px underline. While Sources is open TRACKS stays lit; while Load sample is open SAMPLER stays lit; the gear is lit while Settings is open.
  2. Add the manifest attribute `[MixPi],screen` = 0 next to the other view states (GEN `:405-409`). Not saved.
  3. Wrap the two bottom rows in one group whose `visible` is bound to `[MixPi],screen` through `<IsEqual>0</IsEqual>`.
  4. Every tab writes `screen` 0 (extend `tab()`, GEN `:423-427`). Every opener writes its number with the existing set-value pattern (`preset()`, GEN `:234-239`). The gear writes 5 and still sets `loop_deck` 3. LOAD SAMPLE writes 3 and still sets `sample_load` 1. Existing native code keeps working because it writes `sample_load` and `loop_deck` only (PT `library.cpp:695-697`); the new patches write `screen` as well where they close a view.
  5. Palette and type from spec section 10 and PROTO's CSS: deck 1 blue, deck 2 amber, active lime, danger red, safe green; radius 6; no text under 13 px. Fonts are the ones the image has (Ubuntu, Open Sans).
- **Layer:** skin generator and QSS.
- **Automated checks (`tests/test_performance_skin.py`):**
  - The top bar's fixed widths sum to at most 800 and every item is 48 px high.
  - For each value 0-5 of `screen`, the bottom-row group has the expected `visible` transform; each opener and each tab writes the expected value. This replaces the per-button asserts at `:344`, `:463-467`, `:524`.
  - Guard: every generated `PushButton` is at least 48×48. Display-only chips have no write connection and are exempt.
  - The existing F-11 twin-tab assert and the "two-state buttons target real toggles" guard still pass.
- **Pi check (skin only, current card):** `TOOLS/ui.sh r1-decks.png 'tap 42 24'`, then TRACKS (129,24), FX (209,24), SAMPLER (294,24): one filled tab each time, bottom rows present. Gear (717,24): Settings covers y 48-480, no transport row. DECKS (42,24): waveforms and transport are back. Repeat with the desktop bar shown (800×444).
- **Risk:** Medium. This touches every page; the unit guard and a shot of every page per `screen` value catch layout loss.
- **Size:** L.

## R-2 Native page host — found (needed by R-4)

- **Problem:** The media screens are two `QDialog`s. A dialog cannot cover the screen.
- **Root cause (read in code):** Both are window-modal dialogs at 740×380 (PATCH/media-continuation `:377`; PATCH/media-selection `:4042-4065`). The session caps floating windows at 780×420.
- **Change (in `mixxx-media-screen.patch`, new header `src/widget/mixpipage.h`):** A `MixpiPage` widget: child of the main window, geometry x 0, y 48, full width, down to the bottom; a 48 px header with ✕ at the left (48×48), a title and a hint line; a content area. On show it writes `[MixPi],screen` to its number; on close it writes 0. It follows window resizes with an event filter, as the scan strip does (PATCH/quiet-scan `:134-140`). It does not take keyboard focus from Mixxx. Style rules live in QSS-M under `#MixpiPage`.
- **Layer:** new Mixxx patch, plus QSS.
- **Automated checks (native `media_screen` fixture, in `REQUIRED_TESTS`):** in an 800×480 host the page rect is (0,48,800,432); in 800×444 it is (0,48,800,396); show writes the control, close writes 0; ✕ is at least 48×48; the grabbed image has a dark background.
- **Pi check:** with R-4: `TOOLS/ui.sh r2.png 'tap 527 24'`. The page covers y 48-480 and no waveform shows through. ✕ (24,72) returns to the tab that was open.
- **Risk:** Medium. A child widget over the skin must never meet a live GL widget; decision 3 in section 4.1 and the fixture's control check cover it.
- **Size:** S.

## R-3 Media model: access, handover, eject — owner-requested

This item is the design. R-4, R-5 and R-6 build it.

**Owner:** "work like a pioneer dj where you choose when the program can access the files and choose when to eject and keep the last playing/loaded song in storage for handover (gets cleaned out after transition out)". "load is usually automatic actually - eject is what is done safely".

**References:** MAN p.51: hold USB STOP until the indicator stops blinking; "If the tracks loaded to the deck from the removed USB device have been cached, the track aren't unloaded and playback continues with the restriction." MAN p.53: SOURCE shows the connected devices; you select one. MAN p.58 and p.132: Load Lock stops a load to a playing deck. The grasp lesson says the same.

**The model:**

| Moment | What the owner sees | What the system does | Existing code it uses |
|---|---|---|---|
| Insert | USB chip: `MANTACORE · READY` | Mount read-write. Mixxx detects the drive (level 1 in section 2). Nothing is read from its database; nothing is scanned. | udiskie; hotplug poll; `mixpi-media-inventory.py` |
| Open (the owner's choice) | Chip: `IN USE`. Tracks shows the drive. | Level 2: read the rekordbox export or list folders. | `Library::openRemovableSourceAsync` (PATCH/media-continuation `:21`) |
| Load a track or sample | Deck or pad plays. | The file is copied to RAM first; the deck plays the copy. | RAM cache (PATCH/removable-ram-cache) |
| Eject (deliberate) | A sheet lists what uses the drive. Then steps: stop reading → keep playing copies → close files → unmount and check → **Safe to remove**. | Refuse new loads from the drive; close the library views; keep decks and pads that play from a copy; unmount; verify. | Use registry and drain (PT `mediauseregistry.h:164-175`); R-5; R-6 |
| After eject | Decks that held a copy keep playing, with an **ON PI** chip. | The copy lives while that deck or pad holds it. | Lease lifetime (PATCH/removable-ram-cache `:309-314`) |
| Transition out | The chip goes away when the deck loads the next track. | The copy is deleted at once. Copies left by a crash are deleted at the next start. | Same; `:414-416` |

**Honest limits, stated to the owner on the screens:**

- A copy needs RAM. The limit is `CACHE MB` in Settings, 1024 by default (PATCH/performance-settings `:177`; PATCH/removable-ram-cache `:371-375`), and the cache always leaves 512 MiB or one eighth of RAM free (`:365`). A file that does not fit, or `CACHE MB OFF`, means that deck plays straight from the drive.
- A deck that plays straight from the drive cannot be handed over. Eject is refused while such a deck plays, and the sheet names the deck (the Load Lock idea, MAN p.132). A stopped deck of that kind is unloaded.
- Pad samples from the drive are kept the same way, until the pad is cleared or Mixxx quits. After a restart without the drive those pads are empty. Samples to keep belong on the Pi (`~/Music/Samples`).
- "Access" before Open is not zero: Mixxx checks every 2 s that the mount is there and whether it has a rekordbox export. A hard block (no mount until Open) needs the controlled profile; it is option C in question 1.

**The gate:** R-6. Everything above except the Eject button works with the gate closed. With the gate closed the Media screen says "Eject is off until the owner approves it." and the button is disabled.

## R-4 USB chip and Media screen replace LOAD / EJECT — owner-requested; answers C-4

- **Problem:** `IMG_0315`: a dialog with a text list, small buttons and the line "This does not mean it is safe to remove". "Load" is a step the owner does not expect. `IMG_0316`: a second dialog, "EJECT — one physical USB disk", with "Eject is not available on this system", an empty box and a "Prepare selected disk" button.
- **Root cause (read in code):**
  - `LOAD / EJECT` (GEN `:440-443`) raises `[MixPi],media_load`, which opens `MixpiMediaDialog` (PATCH/media-selection `:1036-1037`; PATCH/media-continuation `:377`).
  - "Load" is shown only for a mounted, selected drive (PATCH/media-continuation `:472`) and calls the open-source path. It is the only "access" step in the dialog.
  - **"Eject…" is enabled for any selected drive** (`:477`). It closes the dialog and opens `MixpiControlledDialog` (`:574`).
  - **What "Prepare selected disk" does with controlled media OFF: nothing.** `MixpiControlledMedia::openProduction()` needs `/etc/mixpi/controlled-media` and `/etc/mixpi/eject-reviewed`, both root-owned with the content `v1`, and the broker socket (PATCH/media-selection `:3762-3790`). With the profile OFF none exist, so no socket is opened and the state stays `Unavailable` (`:4028`) with the message "Eject is not available on this system. Keep the drive connected." (PATCH/dialog-wording `:10`). No `list` request is sent, so the disk list stays empty. The button is created (`:4077`) and shown, but it is enabled only in the `Inventory` state with a selected row (`:4116`), which never happens. Even a forced click returns at once (`begin()`, `:3856`). Nothing is sent to any service and nothing touches the drive. The defect is a dead button in a dead-end dialog.
  - A second fact: `MIXPI_CONTROLLED_MEDIA=1` alone would not enable eject either. Nothing in the repo writes `/etc/mixpi/eject-reviewed` (`stage3/02-desktop/06-run.sh:9-29` writes only `controlled-media`), and the broker unit needs both (`stage3/02-desktop/files/systemd/mixpi-mount-broker.service:4-5`).
- **Change:**
  1. **USB chip (GEN, wave 2).** A 150×48 button in the top bar. It writes `[MixPi],media_load` as today. Its look and its second line follow a new control `[MixPi],media_state`: 0 "NO USB", 1 "READY", 2 "IN USE", 3 "EJECTING…", 4 "SAFE TO REMOVE". A `Number` widget inside it shows `[MixPi],scan_percent` while `[MixPi],scan_active` is 1 (R-12). The drive name is a skin `Label` named `MixpiUsbName`; the media code sets its text after each skin load and each change. **Not confirmed:** that a text set from native code survives on a skin `Label`. First step: a fixture that parses the generated chip, sets the text and re-reads it after a control change. If it fails, the chip shows the state words only and the name stays on the Media screen.
  2. **Media screen (new patch `mixxx-media-screen.patch`; new `src/library/mixpimediapage.h`; changes in `mixpimedia.h`).** `media_load` opens a `MixpiPage` (R-2), number 2, titled "USB & media", in place of both dialogs. Layout as PROTO `rdMedia()`:
     - Left, 520 px: one card per drive. Name; one line "58.6 GB · exFAT · rekordbox export found · read-write"; a state pill; one line per user ("Deck 1 is playing …", "Pad 3 holds …"); three buttons of 56 px height: **EJECT** (176 px, the main action), **BROWSE** (level 2: opens the drive, closes the page and shows it in Sources), **COPY TO PI** (starts the existing `mixpi-media` tool). A drive with more than one volume gets one BROWSE row per volume. No Load, no Refresh.
     - Right, 280 px: "Kept on the Pi for handover": one row per deck or pad with an ON PI copy; then "Cleaned out": the last three copies removed in this session.
     - No drive: one card "No USB drive. Plug in a drive. Nothing is read until you open it."
     - **Not confirmed:** how `mixpi-media` presents itself over Mixxx. First step: start it over SSH with Mixxx in front and take a shot. If it does not come to the front cleanly, the button is left out of build B and noted.
  3. **State without polling a script.** The inventory script runs only when the mount table changes (the mounts are already read every 2 s) and when the page opens, not on a timer. `media_state` comes from the inventory plus the use registry (PT `mixpimedia.h:214-238` already computes the same text).
  4. **Eject sheet.** A tap on EJECT opens a sheet in the page, as PROTO `rdEjectSheet()`: "Eject MANTACORE?", then one line per user in plain words ("Deck 1 · Frontin' — keeps playing from the Pi", "Pad 3 · SNARE9 — kept on the Pi", "Deck 2 · stopped — will be unloaded", "Deck 2 · plays from the drive — stop it first"), then **CANCEL** and **EJECT** (56 px). After EJECT: the four steps of R-3 with a spinner on the current one, Cancel until the unmount starts, and the end state **Safe to remove** in green with **DONE**.
  5. With the gate closed (R-6) the EJECT button is disabled and the line under it says "Eject is off until the owner approves it."
  6. If question 1 picks "Ask": on insert a sheet "MANTACORE plugged in — NOT NOW / USE THIS DRIVE" (PROTO `insertsheet`), shown only when no full-screen view is open and no deck plays; otherwise the chip alone shows the drive.
  7. The two old dialog classes stay in the source (we do not edit old patches) but nothing opens them. With engine B in R-6 the page drives the same broker protocol through `MixpiControlledMedia`.
- **Layer:** new Mixxx patch; skin generator for the chip.
- **Automated checks:**
  - Native (`media_screen` fixture): with a fake inventory of 0, 1 and 2 drives the page shows the empty card, 1 card, 2 cards; `media_state` is 0/1/2 as the fake registry changes; BROWSE calls the open callback once with that drive's volume; with the gate closed EJECT is disabled and the gate line is shown; with the gate open and a fake engine the sheet lists the fake users and the steps reach "Safe to remove"; the handover list follows the fake on-Pi flags; no label contains "physical", "generation", "broker", "token" or a `major:minor` number; every button is at least 48 px high; nothing in the page can reach `MixpiControlledDialog` when the profile files are absent.
  - Unit: the chip has the state and scan connections, is 150×48 and writes `media_load`; the old `LOAD / EJECT` text is gone.
- **Pi check (build B, spare stick, gate closed):**
  1. No drive: the chip says NO USB. `TOOLS/ui.sh r4-none.png 'tap 527 24'`: the empty card.
  2. Insert the spare stick. Within 5 s the chip shows its name and READY. No dialog, no pop-up (with R-15), no scan.
  3. `tap 527 24`, then BROWSE (290,208): Sources shows the drive; pick a playlist; the chip says IN USE.
  4. Open Media again: EJECT (114,208) is grey and the gate line is shown; a tap changes 0 px (`TOOLS/pxdiff.py`).
  5. `journalctl` shows no mount or unmount caused by these taps.
- **Risk:** Medium. The inventory and identity checks stay as they are; the page is a new face on them.
- **Size:** L.

## R-5 Handover: keep the loaded or playing track and the pad samples — owner-requested

- **Problem:** The owner wants the last loaded or playing track kept for handover after an eject, and cleaned up after the transition.
- **Root cause (read in code):** Section 2, row 2. The copy exists, and its cleanup exists. What blocks handover is the drive lease that every open audio source keeps, copy or not (PATCH/media-selection `:2146`, `:2286`). The drain reports busy while any lease is counted (PT `mediauseregistry.h:68-78`), and the lease's `O_PATH` descriptor pins the mount.
- **Change (new patch `mixxx-media-handover.patch`, after `mixxx-media-screen.patch`):**
  1. In `SoundSourceProxy::openAudioSource` (PT `src/sources/soundsourceproxy.cpp:979`): when the source was opened from a RAM copy, hand the audio source the copy's lease but **not** the drive lease. The drive lease then ends when the open finishes. When the decoder fell back to the original file (`:970-972`), keep the drive lease as today.
  2. `RemovableTrackCache`: a read-only query "is this original path served from a copy right now" (the entry map already has it, PATCH/removable-ram-cache `:488-496`).
  3. New controls `[Channel1..2],mixpi_on_pi` and `[Sampler1..8],mixpi_on_pi`: 1 when the player's track is served from a copy **and** its drive is no longer mounted. The media object sets them on eject and clears them on the player's next load or unload. The skin shows an **ON PI** chip from them (R-16, R-7).
  4. The eject sheet uses the same query to sort players into "keeps playing", "will be unloaded" and "stop it first" (R-3).
  5. The cache already removes copies when the last user lets go and at start; no new cleaner.
- **Checks to run before coding (not confirmed items):**
  - That the cache's inotify watches on the original (PATCH/removable-ram-cache `:223-248`) do not block an unmount. The cache comment says they "never hold original media files open". Confirm on VM `b` with a loop-mounted FAT image: load, drop the lease, `umount` must succeed.
  - Which existing fixtures pin "a loaded cached deck counts as drive use". `tests/native/media_ownership_test.cpp.in:254-284` models the proxy with a cache; update the expectations there and give the reason in the commit.
- **Layer:** new Mixxx patch.
- **Automated checks (native `media_handover` fixture, in `REQUIRED_TESTS`):**
  - Open through a RAM copy: after the open, the registry shows 0 users for that drive and a drain is idle; reads still return the same samples.
  - Open with the fallback to the original: the registry shows 1 user and a drain is busy.
  - Remove the original (rename the temp directory): the copy keeps decoding; the query says "served from a copy".
  - Drop the audio source: the copy file is gone from the cache directory.
  - Start-up with a stale `track-*` file: it is deleted (existing behaviour, asserted again).
  - `test_ram_cache_identity` and the media ownership tests pass.
- **Pi check (gate opened by hand after owner approval only; spare stick):**
  1. Load a track from the stick to deck 1 and play. Load a sample from the stick to pad 3.
  2. `ls -la /dev/shm/mixpi-track-cache`: two `track-*` files.
  3. Eject (R-6). Deck 1 keeps playing with no dropout; the log has no new underrun; the ON PI chip shows on deck 1 and pad 3; the mount is gone from `findmnt`. Pull the stick. Trigger pad 3: it plays.
  4. Load a Pi track to deck 1: the chip goes away and the cache directory has one file left. Clear pad 3: the directory is empty; Media › Cleaned out lists both.
  5. Load a file larger than the cache limit, play it, tap EJECT: the sheet says "stop it first" for deck 1 and EJECT stays off until the deck stops.
- **Risk:** High. This changes a safety rule in the reviewed media code: "loaded means in use". The patch is small, but the reasoning must hold: with a copy, the decoder never reads the original again. The fallback path keeps the old rule.
- **Size:** M.

## R-6 Eject engine and the approval gate — owner-requested; gated

- **Problem:** There is no working eject in Mixxx today (R-4), and the constraint says eject stays OFF until the owner approves the design.
- **Root cause (read in code):** The only eject path is the root broker. It needs the controlled profile, which changes the system: it masks `udisks2`, removes user `pi` from `sudo` and `disk`, turns off user namespaces and limits sudo to `shutdown` (`06-run.sh:9-29`; `mixpi-mount-broker.py:401-416`). The broker never adopts a mount it did not make (`mixpi-mount-broker.py:2`, `:273-274`), so it cannot eject a drive that udiskie mounted. The drain can be started only by a root peer (PATCH/media-selection `:3596`).
- **The honest options (question 2):**

  | | Engine A: system eject | Engine B: controlled profile | C: no eject in Mixxx |
  |---|---|---|---|
  | How | Mixxx drains its own use in-process, then asks udisks2 to unmount each volume (`udisksctl unmount -b … --no-user-interaction`), then checks the mount table. | The existing broker: mount on request, drain, cutoff, unmount, proof. The Media screen drives it. | The chip and the Media screen show state only. Remove the drive after a shutdown. |
  | System change | None. udiskie stays the automounter. | The profile above. `pi` loses general `sudo`: our in-place updates and the `TOOLS` recovery steps that use `sudo -n` stop working on that card. | None. |
  | Safety | The kernel refuses an unmount while a file is open, and an unmount flushes. Mixxx closes its own users first. Other programs are not checked. | Strongest: identity pinned, no other mounter, proof of unmount. | No risk from Mixxx; no safe removal while running. |
  | "Choose when Mixxx may access" | By the Browse tap (level 2). The drive is mounted from insert. | Can be strict: nothing is mounted until Browse. | By the Browse tap. |
  | New code | In-process drain (small) and a `QProcess` call with a timeout. | The page-to-broker mapping only. | None. |

  **Recommendation: A.** It gives the Pioneer behaviour with no system lock-down, and it keeps the test card serviceable. B stays in the tree for a future appliance profile.
- **Change (engine in `mixxx-media-handover.patch`; gate in system files):**
  1. **Gate.** A control `[MixPi],media_eject_available`. It is 1 only when a root-owned, not group- or world-writable file `/etc/mixpi/media-eject` holds `v1` (engine A), or when the controlled-profile files exist (engine B). The check copies the existing one (PATCH/media-selection `:3762-3775`). A setting or a skin change cannot open it.
  2. **The image never writes the gate file by default.** `06-run.sh` writes it only for `MIXPI_MEDIA_EJECT=1`. `tools/performance/accepted-artifact.py` treats the new file like the controlled-profile files (`:180`, `:308-310`): artifact mode requires it absent. The image check phase prints "media eject OFF".
  3. **Engine A sequence:** begin a drain for the drive (new loads are refused: PT `cachingreaderworker.cpp:188-192`); release the library views (`refreshMediaLifecycle`, PT `library.cpp:219-225`); unload stopped players that are not on a copy; wait until the drain is idle, 10 s at most, with Cancel; unmount each volume; confirm in `/proc/self/mountinfo` that every mount of that disk is gone; mark the drive retired; set `media_state` 4. Any failure cancels the drain, leaves the drive mounted, and says "Not ejected. The drive is still in use." No power-off: the drive can be opened again without a replug, and the Pioneer model does not power the port down either.
  4. **Engine B sequence:** `eject` → poll → on `ready` send `commit` at once (the sheet's EJECT tap was the confirmation) → poll until `unmounted` with `safe` true (`mixpi-mount-broker.py:320-398`).
- **Layer:** new Mixxx patch plus system config.
- **Automated checks:**
  - Unit (`tests/test_controlled_media_profile.py`, `tests/test_accepted_artifact.py`): a default build writes no `/etc/mixpi/media-eject`; artifact mode fails if it exists; `MIXPI_MEDIA_EJECT=1` writes it root-owned, mode 644.
  - Native (`media_handover` fixture): gate file absent → control 0 and no engine call; present but writable by others → 0; present and valid → 1. With a fake unmount command: the success path reaches state 4 only after the fake mount table is empty; a failing unmount cancels the drain and the state returns to 2; Cancel before the unmount cancels the drain; a drain busy for 10 s gives the "still in use" message and no unmount call.
- **Pi check:** only after the owner approves in writing. Create the gate file by hand on the test card (`sudo install -m 644 -o root -g root`), restart Mixxx cleanly. Spare stick only. Eject with nothing loaded: "Safe to remove" within 5 s; `findmnt` shows no mount; `dmesg` shows no I/O error; re-insert: the chip says READY and the journal has no "not properly unmounted" line. Then the R-5 checks. Afterwards remove the gate file unless the owner says keep it.
- **Risk:** High, which is why it is gated. Engine A's weak point is another program holding a file on the drive; then the unmount fails, the screen says so, and nothing is lost.
- **Size:** M (A), or S (B, code only; the profile work is outside this plan).

## R-7 Sampler: eight pads that match the Starlight — owner-requested

- **Problem:** The screen shows four pads. The Starlight has eight sampler pads. The owner asks for "eight just slightly larger".
- **Root cause (read in code):** GEN `:400-402` sets `num_samplers` to 4; the page draws `range(1, 5)` (GEN `:353`). Section 2, row 1.
- **Change (GEN, QSS-P), following PROTO `rdSampler()`:**
  - Manifest: `num_samplers` 8.
  - Header 48 px: **LOAD SAMPLE** (190×48), a "Bank saved" note bound to `[MixPi],saved` (R-13; hidden until that control exists), and the hint "Starlight SAMPLER mode: deck A pads 1-4 · deck B pads 5-8".
  - 8 pads in 2 rows of 4, each 200×104 (y 96-304). Row 1 = pads 1-4, tagged "A1…A4" in the deck 1 colour. Row 2 = pads 5-8, tagged "B1…B4" in the deck 2 colour.
  - A loaded pad: a 56 px tap area (name; lit from `[SamplerN],play`) that sends `cue_gotoandplay` on press and release as today (GEN `:359-361`); a 48 px strip with **■ Stop** (`[SamplerN],stop`) and **✕ Clear** (`[SamplerN],eject`, enabled only while the pad is stopped); an ON PI tag (R-5).
  - An empty pad: "Empty · tap to load". A tap opens Load sample (R-8) with that pad as the target.
  - Below the pads, unchanged in order: deck info 72 px, overviews 48, transport 56. The DJ keeps time and BPM in view while playing samples.
- **Layer:** skin generator and QSS.
- **Automated checks (`tests/test_performance_skin.py`):** `num_samplers` is 8 (update `:462`); eight pads with keys `[Sampler1]`…`[Sampler8]` in reading order; each has trigger, stop and clear; clear's `enabled` is bound to `play` through `<Not/>`; the empty-pad button is visible through `track_loaded` and `<Not/>` and writes `screen` 3 and the target pad; every tap target is at least 48 px; the page's fixed heights sum to 432.
- **Pi check (skin only, current card; then build A):** SAMPLER (294,24). With the Starlight in sampler mode, press deck A pad 2 and deck B pad 3: on-screen pads 2 and 7 light while they play. Tap pad 2's Stop (250,176): it stops. Tap its Clear (350,176): the pad is empty. Two decks playing plus four pads: `get_throttled` 0x0; log the CPU readout and the underrun count against the build-2 numbers (3-4 %, 0 underruns).
- **Risk:** Low to medium. Eight sampler engines exist already whenever the Starlight is connected; without it the skin now creates them, so measure the idle cost once.
- **Size:** M.

## R-8 Load sample: a separate full screen, one Load button, then Choose pad — owner-requested

- **Problem:** `IMG_0313`, `IMG_0314`: loading a sample happens inside Tracks, under a LOAD TO row with four pad buttons, beside the Sources pane; almost no list is left.
- **Root cause (read in code):** `[MixPi],sample_load` only adds a row to the Tracks page (GEN `:331-343`). The table shares the page with everything else (R-1).
- **Can there be a second library widget?** No (section 2, row 6). The two honest ways:

  | | A: a skin page that reuses the one library widget | B: a native screen with its own list and model |
  |---|---|---|
  | What it can show | Everything the library can: the Samples folder, Tracks, a drive, Recordings. The owner said "select from library". | Only what we write a model for (folders of audio files). No playlists and no rekordbox drives without re-doing the Sources code. |
  | Separate from Tracks? | Its own screen and its own remembered place, through a small native patch. One table underneath. | Fully separate. |
  | Size and risk | Skin M + native M. Uses tested table code (touch scroll, columns, search). | Native L. New list, new touch scroll, new styling, new load path. |

  **Chosen: A.** It meets "a separate component from the browse list but similar" for the owner's eyes and hands, and it keeps "select from library" true.
- **Change:**
  1. **Skin (GEN, wave 1), following PROTO `rdSampleBrowser()`.** `screen` 3 = Load sample: a second layout of the browse page around the same `<Library>` element. Header 48 px: ✕, the title "LOAD SAMPLE", a hint ("Pick a sound, then a pad" or "For pad 5"), the search box. A 56 px row of source buttons (48 px high): **SAMPLES**, **THIS PI**, **USB** (shown only while a drive is open), **RECORDINGS**. The table from y 152 to 416 (header 32, rows 48, 24 px scroll bar). A 64 px footer with one button, **LOAD TO PAD…** (250×56). No Sources pane, no Actions, no deck rows: the list covers the song tracks, as the owner allowed.
  2. **Choose pad (GEN), following PROTO `rdChoosePad()`.** `screen` 4: a sheet over the list with the 8 pads as 96 px tiles, 4×2, in the R-7 order and tags, each showing what it holds (`TrackProperty` on the sampler group, as GEN `:355-357`). A tile sends `[SamplerN],LoadSelectedTrack` on press and release (as GEN `:334-335`), then writes `screen` 0 and `[Tab],sampler` 1. A tile is off while its pad plays (the rule at GEN `:336`). **CANCEL** returns to the list.
  3. **A preset pad.** When Load sample was opened from an empty pad, the footer button reads "LOAD TO PAD 5" and loads at once, without the sheet. In the skin this is a stack of nine buttons, one visible per value of `[MixPi],sample_pad` (0 = chooser).
  4. **Native (new patch `mixxx-sample-browser.patch`, wave 2).** When `sample_load` goes to 1: remember the current source, search text and scroll position of Tracks, then show the sample browser's own last place (first time: the `Samples` folder under the Pi's music directory). When it goes to 0: restore Tracks. The source buttons write `[MixPi],sample_source`: 1 Samples folder, 2 the Tracks collection, 3 the open drive, 4 Recordings. The Actions menu on Tracks gains "Load to a sampler pad…" (PROTO `actionsmenu`), which opens Choose pad for the selected row.
- **Layer:** skin generator, then a new Mixxx patch.
- **Automated checks:**
  - Unit: on `screen` 3 the browse page shows exactly one `<Library>`, no `SidebarWrapper`, one footer stack; the old `MixpiSamplerDestinations` row is gone; Choose pad has eight tiles with the keys, the `enabled` bindings and the two writes; the footer stack has nine buttons and one is visible per `sample_pad` value; no `LoadSelectedTrackAndPlay` anywhere (existing guard).
  - Native (`sample_browser` fixture): Tracks on playlist P with search "abc"; enter sample mode → the model is the Samples folder and the search is empty; pick `sample_source` 2 → the track collection; leave → P and "abc" are back; enter again → the collection, as left; a drive that vanished falls back to Samples; the new Actions entry writes `screen` 4.
- **Pi check:**
  - Wave 1 (skin only, current card): SAMPLER → LOAD SAMPLE (101,72): the list fills y 152-416. Tap row 2 (300,256), LOAD TO PAD… (667,448), pad 5's tile (144,280): the Sampler tab shows the name on pad 5. A playing pad's tile is grey and a tap changes nothing. A drag on the list scrolls; the scroll bar scrolls. Tap an empty pad 8 (700,228): the footer reads LOAD TO PAD 8; tap it: pad 8 is loaded.
  - Build B: Tracks on a playlist with a search; LOAD SAMPLE; ✕ (24,72); Tracks shows the same playlist and search. Tracks → ✎ → "Load to a sampler pad…": Choose pad opens.
- **Risk:** Medium. One table serves two screens; the save-and-restore fixture is the guard. Until build B the two screens share their place (known; stated in the wave-1 result).
- **Size:** M (skin) + M (native).

## R-9 Sources: full-screen navigation — owner-requested

- **Problem:** `IMG_0311`, `IMG_0313`: Sources is a narrow pane with 3.75 visible rows (`EV/field-fix-acceptance-b2/ACCEPTANCE.md`, F-6 row and finding 5), beside a table nobody reads while choosing a source. Picking Rekordbox or Computer fills the list area with help text.
- **Root cause (read in code):** The pane is fixed at 290 px inside the browse page (GEN `:316-320`), in a right-overlay layout over the table (GEN `:343`). Navigation is already one level at a time with Back (PT `src/widget/touchsourcenavigation.h:44-71`).
- **Change, in three steps:**
  1. **Skin (GEN, PT-PY, QSS-T, wave 1), following PROTO `rdSources()`.** `screen` 1 = Sources, opened by ☰ on Tracks. Its own 48 px header: ✕ in the spot where ☰ was, the title, a hint, and **EDIT LIST** (pen icon plus text, 128×48) at the right. The sidebar widget takes the whole area below (y 96-480, 800 wide). Rows 56 px (QSS-T `:17-20`), 24 px scroll bar.
  2. **Native rail, crumb and auto-close (new patch `mixxx-sources-screen.patch`, wave 1; `wlibrarysidebar.{h,cpp}`).** In touch mode the sidebar reserves a left margin of 264 px and a top margin of 48 px inside itself (`setViewportMargins`). The left margin holds the **rail**: one 64 px tile per visible top-level source (icon, name, a fixed sub-line per source kind), in the owner's saved order. The top margin holds **Back** (96×48) and a **crumb** ("Rekordbox › MANTACORE › Friday"). A tap on a tile shows that source's top level on the right (the existing `home()` then `enter()`). A tap on a row with children drills in. A tap on a row without children (a playlist, a crate, a folder of tracks) opens it in Tracks and closes Sources: it writes the sidebar-visible control and `screen` 0. The rail hides what Sources edit hides.
  3. **Grouping the prototype's way (new patch `mixxx-source-groups.patch`, wave 2; only if question 4 says A).** The rail's tiles become: one tile per connected drive (first, in plug-in order), **This Pi** (Tracks, Playlists, Crates, Auto DJ), **Recordings**, **History**, **Folders** (Computer), **Samples**. A tile is a view onto existing features: it shows a subset of top-level rows, or one feature's children, or one drive's node under Rekordbox or Computer. Edit list then orders and hides tiles; the owner's present per-source choices are mapped once (a tile whose sources are all hidden starts hidden). Sources the grouping does not name (iTunes, Serato, Traktor, Analyse) appear under a **More** tile, shown only if the owner has any of them on.
- **Layer:** skin generator and QSS; new Mixxx patches.
- **Automated checks:**
  - Unit: on `screen` 1 the sidebar group is 800 wide with no fixed 290; the table is not shown; EDIT LIST writes `[Library],show_sidebar_sources_menu`.
  - Native (extend the `library_interface_sources` fixture): at 800×384 the rail is 264 px, tiles 64 px, rows at least 56 px; the rail lists the visible sources in saved order and skips hidden ones; tap a tile → the right part shows that source's children and the crumb shows its name; tap a leaf → one activation and the close control written once; a drag over three rows scrolls and activates nothing (C-1 behaviour kept); a model reset during a drill returns to the top without a crash (the existing hot-plug tests pass).
  - Native (`source_groups` fixture, step 3): with a fake drive the first tile is the drive and its rows are that drive's node; without it the first tile is This Pi; This Pi shows exactly the four features, minus hidden ones; unplug while the drive tile is selected → This Pi is selected and nothing dangles; the one-time mapping keeps a hidden source hidden.
- **Pi check:**
  - Wave 1 (skin only): TRACKS, ☰ (24,72): the list covers y 96-480 with at least 6 full rows. Tap a source, Back, ✕ (24,72): Tracks is unchanged.
  - Build A: rail tiles at x 132; tap "Playlists" (132,192 if second): the right part lists playlists and the crumb says Playlists; tap one (530,172): Tracks shows it and Sources is closed. `drag 530 420 530 200` scrolls and opens nothing.
  - Build B (step 3): with the spare stick in, the first tile carries its name; tap it, then "Playlists", then a playlist: Tracks shows it with the drive name in the crumb. Pull the stick (after R-6's checks, or with nothing loaded): the tile goes within 5 s.
- **Risk:** Medium for steps 1-2: margins inside a `QTreeView` are standard Qt, and the rail must follow model resets. Medium to high for step 3: it adds a second way to hide rows, and drives come and go; the fixture covers an unplug.
- **Size:** M (skin) + M (rail) + M to L (grouping).

## R-10 Sources edit: show, hide and order as its own step — owner-requested

- **Problem:** `IMG_0311`: a menu in two columns over the page, with check boxes on the left and a small order list on the right.
- **Root cause (read in code):** `Library::showSidebarSourcesMenu` builds a `QMenu` (PATCH/sidebar-sources `:203`; PATCH/library-interface `:112`) with one check-box row per source (`:371` onwards), a separate order list (`:420`), Up/Down, a "Default source" submenu (`:165`) and Close. It is taller than the screen. **Not confirmed in Qt source:** that Qt wraps an over-tall menu into columns; the photo shows two columns. First step: build the menu with 12 sources in a 444 px high fixture and read its size and column count.
- **Change (in `mixxx-sources-screen.patch`; `library.cpp`, `libraryinterface.h`, `wlibrarysidebar.cpp`), following PROTO's edit mode:** EDIT LIST switches the right part of Sources to the edit list and reads **DONE**; the rail stays. **One list** does both jobs: each 56 px row has the source name, **Up** and **Down** (48×48 each) and an on/off switch (at least 64×48); the start source carries a ★. Below the list: **Start here** (sets the start source to the selected row). The last visible source cannot be switched off (existing `protectLastVisible`). Order and visibility use the existing settings and functions; only the face changes. No drag-to-reorder. No `QMenu`.
- **Layer:** new Mixxx patch, QSS-M.
- **Automated checks (native, in the `library_interface_sources` fixture; unit for QSS-M):** rows at least 56 px, buttons at least 48 px, one list only; a switch writes the same config key as before; Up/Down change the saved order; the last visible row's switch is disabled; Start here writes the default source; DONE restores the navigation view; a grabbed image is dark; the style block has the edit-list rules.
- **Pi check (build A):** ☰ (24,72), EDIT LIST (730,72). Switch "Recordings" off; move "History" up twice; DONE. The rail shows the new order without Recordings. Quit Mixxx, start: both are kept. Switch Recordings back on (the owner's settings are restored at the end of the run).
- **Risk:** Low. Same data, new widget.
- **Size:** M.

## R-11 Pen icon for Actions; hamburger that turns into an X — owner-requested

- **Problem:** The buttons say "Actions" and "Show"/"Hide" and take 96 and 90 px.
- **Root cause (read in code):** PT-PY `:25-36` (Actions text); GEN `:311-315` (sizes; "Show"/"Hide" state text).
- **Change (GEN, PT-PY, QSS-T):** Both become 48×48 icon buttons with no text. Actions: a pen, at the right end of the Tracks toolbar. Sources: three bars at the left end; when Sources is open, an ✕ is in the same spot (the Sources header's close button). The icons are small SVG files that GEN writes into the skin, as it writes the slider handle (GEN `:523-529`). Toolbar order, as PROTO: ☰, the crumb of the current list (220 px), the search box, ✎. The buttons keep their object names, so the native menu still anchors under the Actions button (PATCH/touch-dialogs `:29-33`). **Not confirmed:** how the pinned `WPushButton` scales an SVG state image at 48×48 on the Pi. First step: a unit assert on the generated state elements and one shot on the card. The crumb of the current list is native text; until `mixxx-sources-screen.patch` supplies it (same mechanism as the R-4 name label), the space is empty.
- **Layer:** skin generator and QSS.
- **Automated checks:** each button is 48×48, has no state text, and each state names an existing SVG; the SVGs parse; the Sources button keeps its original key; `tests/test_pioneered_touch.py` still finds the managed button block.
- **Pi check (skin only, current card):** TRACKS. Shot: three bars at (24,72) and a pen at (776,72). Tap the bars: Sources opens and an ✕ is at (24,72). Tap it: closed, bars. Tap the pen: the Actions menu opens under it.
- **Risk:** Low.
- **Size:** S.

## R-12 Scan bar: file name, Hide and Cancel, a saved Hide, and a % on the USB chip — owner-requested

- **Problem:** `IMG_0310`: the bar covers the transport row, shows a long path cut in the middle, the text looks overdrawn, and there is only Cancel.
- **Root cause (read in code):**
  - Position: the strip is placed at the host's bottom edge, 44 px high (PATCH/quiet-scan `:171-176`, `:251`). That is the transport row.
  - Text: "Scanning: " plus the full path (`:193`), elided in the middle (`:35`).
  - Buttons: Cancel only, 96×36 (`:109-117`).
  - Progress: indeterminate, "the scan does not know its total" (`:101-104`).
  - Overdrawn text: **not confirmed.** The label paints without its own background (`:24-36`). First step: in the strip fixture, send two different paths and compare the grabbed label with a fresh render of the second.
- **Change (new patch `mixxx-scan-progress.patch`; `libraryscannerdlg.{h,cpp}`, `libraryscanner.{h,cpp}`), following PROTO `rdScanStrip()`:**
  1. Height 48 px. Position: directly above the transport row (host bottom − 56 − 48), over the overview row. It is not shown while a full-screen view is open (`[MixPi],screen` not 0); the chip then carries the progress.
  2. Content: a USB icon, "SCANNING", the file or folder name only (elided at the right), the %, a progress bar. The label fills its background before it draws.
  3. Buttons: **HIDE** and **CANCEL**, each 96×48.
  4. **HIDE** hides the bar and saves `[MixPi],ScanBarHidden 1` in `mixxx.cfg` (kept by R-13). Later scans do not show the bar. Settings › Media › Scan progress (BAR / ICON ONLY) turns it back on (R-18).
  5. **Percent.** The scanner counts the folders under the music directories once, on its own thread, before it queues work; it already reports them one by one (PIN `src/library/scanner/libraryscanner.cpp:557`, `:566`). Percent = folders done ÷ folders counted, capped at 99 until the scan-finished signal. New controls: `[MixPi],scan_active` and `[MixPi],scan_percent`. The bar and the USB chip show the same number. The owner asked for the USB icon; the chip carries it even though this scan is of the Pi's music folder.
  6. The 2 s delay before the bar appears stays (`:187`), so short scans show nothing.
- **Layer:** new Mixxx patch; chip in the skin.
- **Automated checks:**
  - Native (extend the `library_scanner_strip` fixture; add its module to `REQUIRED_TESTS` — `test_quiet_scan` is not in the list today): in an 800×480 host with `screen` 0 the strip rect is (0,376,800,48); with `screen` 1 it is hidden and `scan_active` is still 1; the label for `/home/pi/Music/Backup/x/Beautiful.mp3` is "Beautiful.mp3"; HIDE and CANCEL are 96×48; HIDE writes the key and hides the strip; with the key set a scan never shows the strip; percent goes 0 → 99 → inactive on a fake tree of 10 folders and never goes down; two paths in a row leave no pixels of the first.
  - Unit: the chip has the two scan connections.
- **Pi check (build A):** Settings › Advanced › Mixxx preferences… › Library › Rescan. After 2 s: the bar is at y 376-424; CUE and ▶ at y 452 are fully visible, and a tap on ▶ (356,452) starts deck 1. Tap HIDE (650,400): the bar goes; the chip shows a rising %. Start a second scan: no bar, the chip shows %. Restart Mixxx, scan again: still no bar. Settings › Media › Scan progress: BAR; scan: the bar is back. CANCEL (750,400) stops the scan within 2 s.
- **Risk:** Low. The pre-count is one directory walk on the scanner thread; time it on the card's 2,401-file music folder and record it.
- **Size:** M.

## R-13 Save on change: `mixxx.cfg` and the sampler bank — owner-requested (C-3)

- **Problem:** A power pull or an unclean stop loses settings and pads. "We control the codebase, why can't we just save on settings change?"
- **Root cause (read in code):**
  - A setting change only updates memory: `ConfigObject::set` (PIN `src/preferences/configobject.cpp:161-164`). No signal, no dirty flag.
  - The file is written at three points only: once after start-up (PIN `src/coreservices.cpp:376`), at quit (`:793`), and from the Library preferences page (PIN `src/preferences/dialog/dlgpreflibrary.cpp:598`).
  - Controls marked "persist" copy their value into the config only when they are destroyed, at quit (PIN `src/control/control.cpp:89-99`).
  - The write is not atomic: it writes a temp file, **removes the old file, then renames** (PIN `configobject.cpp:293-302`), with no sync. A power cut in that window leaves no `mixxx.cfg`.
  - The sampler bank is written only in `~PlayerManager` (PIN `src/mixer/playermanager.cpp:146`), by truncating `samplers.xml` and writing in place (PIN `src/mixer/samplerbank.cpp:98-131`).
- **Change (new patch `mixxx-save-on-change.patch`):**
  1. `ConfigObject`: a change counter raised in `set` and `remove`. `save()` writes through `QSaveFile` (a temp file in the same directory, then one atomic rename; the old file is never removed first) and syncs the file. **Not confirmed:** whether `QSaveFile::commit()` syncs to disk in the Pi's Qt version. First step: read the Qt source for that version; if it does not, call `fsync` on the file before commit and on the directory after.
  2. An autosave object in `CoreServices`, on the GUI thread: a 1 s timer. When the counter has changed and 1 s has passed since the last change, it copies the current values of all persist controls into the config and saves on a worker thread. At most one write every 5 s under constant change. No write when nothing changed.
  3. Sampler bank: each sampler's "track loaded" and "track unloaded" signals start a 1 s single-shot; then `samplers.xml` is written through `QSaveFile`. No save before `loadSamplers()` (PIN `playermanager.cpp:395-396`) has finished at start-up, or an early save would wipe the bank.
  4. A control `[MixPi],saved` pulses for 2 s after each successful write; Settings and the Sampler header show "Saved" from it.
- **Layer:** new Mixxx patch.
- **Automated checks (native `save_on_change` fixture, in `REQUIRED_TESTS`):**
  - Set a key: the file is unchanged at 0.5 s and holds the value by 2.5 s. Fifty sets in 1 s give one write.
  - Kill the process with SIGKILL 3 s after a change: the file parses and holds the value.
  - Make the directory read-only: the save fails, the old file is byte-identical, a warning is logged.
  - At no time during a save is the config path missing (watch the directory).
  - A persist control changed at run time is in the file after the autosave.
  - Load a location to sampler 1: `samplers.xml` holds it within 3 s. With a bank on disk and a slow load at start-up, no write happens before the load ends and the bank is intact.
  - No write in 10 s of idle.
- **Pi check (build A):** Settings: change the key lock engine; wait 3 s; `TOOLS/pi.sh 'pkill -KILL -x mixxx'`; `grep` the key in `~/.mixxx/mixxx.cfg`: the new value. Start Mixxx: the setting shows. Load a sample to pad 6; wait 3 s; kill again; `samplers.xml` names it; start: pad 6 is loaded. Tap the deck time to "remaining", kill, start: still remaining. Two decks playing during ten setting changes: 0 new underruns, `get_throttled` 0x0. Optional, by the owner: one real power pull 5 s after a change.
- **Risk:** Medium. An SD write while audio plays: it is a few kB on a worker thread, rate-capped; the Pi check measures underruns. The owner's settings file is rewritten more often, but atomically.
- **Size:** M.

## R-14 Clean quit, and reboot or power-off stops Mixxx first — carried (C-2 `a8a86fa`, C-3)

- **Problem:** `systemctl --user stop`, a reboot and a power-off end Mixxx without saving (`EV/field-fix-acceptance-b2/ACCEPTANCE.md`, finding 1). Build 1's pads were lost this way.
- **Root cause:**
  - Read in code: the pinned Mixxx has no SIGTERM handler; the unit has no stop settings (`stage3/02-desktop/files/systemd/user/mixpi-mixxx.service:1-12`). `a8a86fa` fixes both: `mixxx-clean-quit.patch` routes SIGTERM and SIGHUP to the File › Exit path without the prompt, and the unit sends SIGTERM with a 20 s limit. Native gate 135/135 with it (`EV/owner-options/README.txt`).
  - Shutdown order: **confirmed on VM `b`, not on the Pi.** The session scope is ordered after `user@1000.service`, so at shutdown the session (sway, under LightDM) stops before the user manager stops `mixpi-mixxx.service`; Mixxx then loses its Wayland connection and Qt exits without the quit path (`EV/owner-options/README.txt`, `session-ordering-vm-b.txt`). The power button runs a plain `shutdown -h now` (`stage3/02-desktop/files/waybar/config:61`).
- **Change:**
  1. Cherry-pick `a8a86fa` as it is (wave 0, after question 7).
  2. **Confirm the order on the card first** (wave 0): with build 2, `sudo reboot`, then `journalctl -b -1 -o short-monotonic -u lightdm -u user@1000` and the tail of the last Mixxx log. Expected: lightdm stops before Mixxx gets a signal, and the log has no "shutdown complete".
  3. New system unit `mixpi-mixxx-stop.service` (wave 1, N1): `After=lightdm.service user@1000.service`, `RemainAfterExit=yes`, `ExecStart=/bin/true`, `ExecStop=/usr/local/sbin/mixpi-stop-mixxx`, `TimeoutStopSec=25`, enabled in the image. systemd stops units in the reverse of their start order, so this unit's stop step runs before LightDM and the user manager go down, on every path (power button, `sudo reboot`, `systemctl poweroff`). The helper runs `systemctl --user stop mixpi-mixxx.service` as `pi` with `XDG_RUNTIME_DIR` set, and returns when the unit is inactive. It does nothing if Mixxx is not running.
  4. With R-13 a hard power pull loses at most the last second; with this item a normal reboot loses nothing.
- **Layer:** Mixxx patch (existing, held) plus system config.
- **Automated checks:** `tests/test_clean_quit.py` and the native `test_clean_quit` from `a8a86fa`; new `tests/test_shutdown_order.py`: the unit file has the two `After=` names, the stop command and the timeout; `02-run.sh` installs and enables it; the helper is root-owned 755 and stops only the one fixed unit.
- **Pi check (build A):** Load pad 7, change a setting, then at once `sudo reboot` (no wait for the autosave). After boot: the previous Mixxx log ends with "shutdown complete with code 0"; `journalctl -b -1` shows `mixpi-mixxx-stop` stopping before lightdm; the setting and pad 7 are back. Repeat with the power button's Restart, and with Shut down plus a manual power-on: three runs, all clean. `systemctl --user stop mixpi-mixxx`: the same log line, in about 1 s.
- **Risk:** Medium. A stuck Mixxx delays a shutdown by up to 20 s, then systemd kills it. Boot is not affected.
- **Size:** S (cherry-pick) + S (unit).

## R-15 No udiskie pop-ups — carried (C-2 `72e98c4`)

- **Problem:** udiskie pop-ups cover SETTINGS and REC for minutes in a USB storm, and a tap went to a pop-up (`EV/field-fix-acceptance/ACCEPTANCE.md:48`). About 60 queued notifications preceded the sway crash (`:47`).
- **Root cause (read in code):** `stage3/02-desktop/files/i3.conf:231` starts `udiskie --tray` with notifications on.
- **Change:** Cherry-pick `72e98c4` (`--no-notify`). The USB chip (R-4) now shows what the pop-ups showed. Owner decision: question 6.
- **Layer:** system config.
- **Automated checks:** `tests/test_appliance_quieting.py` from the commit.
- **Pi check (build A, spare stick):** insert and remove the stick five times: no pop-up in any shot; the volume still mounts under `/media/pi`; the tray menu still lists it (top bar shown).
- **Risk:** Low. **Size:** S.

## R-16 Deck page: colours, info row, and the tool panel (Loop · Jump · Cues) — owner-requested (overall direction), found

- **Problem:** The owner wants a modern, clean look with ideas from the XDJ-AZ, usable by touch and with the Starlight. The Starlight has 4 hot cue pads and 4 loop sizes; rekordbox tracks carry up to 8 hot cues (MAN p.95).
- **Root cause (read in code):** The panel has loops only (GEN `:162-192`). Deck identity is a "DECK 1" label and a blue title strip for both decks (QSS-P `:15`). Nothing on screen shows sync leader or PFL, which the Starlight sets (PIN midi.xml `:205`, `:269`, `:77`, `:153`).
- **Change (GEN, QSS-P, wave 2), following PROTO `rdWaves()`, `rdDeck()`, `rdTransport()`, `rdTool()`:**
  1. Rows: waveforms 2×128 with a 92 px left column (deck badge in the deck colour, key, MT and Q state pills); deck info 72 px; overview 48; transport 56 (KEY 48, Q 48, SYNC 60, LOOP 60, CUE 76, ▶ the rest, about 83).
  2. Info row 1: badge, title, artist (dim), and display chips: **ON PI** (R-5), **USB** (the track is on a drive and not yet handed over), **SYNC**, **MASTER** (`sync_leader`), **PFL** (`pfl`). Row 2: time with a small "ELAPSED · TAP" or "REMAINING · TAP" caption (tap toggles, as today), BPM, tempo range and %, key.
  3. Tool panel, opened by LOOP as today, covering the waveform rows; that deck's waveform moves to the overview row with − and + (unchanged). Header: deck badge, three tabs **LOOP · JUMP · CUES**, **CLEAR** (on Cues), **CLOSE**; all 48 px high. **Loop**: today's 12 sizes plus ½, ×2, EXIT, RELOOP (same controls). **Jump**: `beatjump_1/2/4/8/16/32_backward` and `_forward`, two labelled rows of six. **Cues**: hot cues 1-8 as 4×2 tiles of 70 px, lit from `hotcue_N_enabled`; a tap sends `hotcue_N_activate`; with CLEAR on, a tap sends `hotcue_N_clear`. The tab is skin-only state (`[MixPi],tool_tab`).
  4. The LOOP button also lights while a loop is on (`loop_enabled`), so a Starlight loop pad shows on screen.
  5. On Tracks the bottom row is LOAD (104 px, off while that deck plays, as F-3) with the deck's title beside it, and CUE; per deck.
  6. Waveform and overview colours do not change: GEN keeps the pinned `<Visual>` and `<Overview>` definitions, and a test pins that (`test_build_on_pinned_pioneered_preserves_visual_and_overview`). PROTO draws coloured waveforms; that part is not taken.
- **Layer:** skin generator and QSS.
- **Automated checks:** the four row heights sum to 432; per deck the transport widths sum to at most 400; each Jump and Cue button has the right key and is at least 48 px high; CLEAR changes only which connection is live; the chips have no write connection; the pinned waveform test passes; the F-5 time-cell assert passes; the F-3 LOAD asserts pass.
- **Pi check (skin only on the current card, then build B):** load the 102 BPM and 125.5 BPM tracks. LOOP 1 (201,452): the panel shows three tabs. JUMP (288,76), "4 ▶" (403,196): the position moves by 4 beats (overview shot before and after). CUES (394,76), tile 5 (106,217): tick 5 appears on the overview; CLEAR (627,76), tile 5: gone. Starlight: hot cue pad 2 on deck A lights cue 2 on screen; loop pad 3 lights LOOP and the "4" button; Shift+Sync on deck B shows MASTER on deck 2; PFL on deck A shows PFL. Fresh start, paused shot: 86 ± 2 px per beat at 102 BPM (F-4 holds).
- **Risk:** Medium. The left column shrinks from 100 to 92 px and the waveform widens by 8 px; re-check CPU and frame rate against the F-4 numbers.
- **Size:** L.

## R-17 FX page: show the unit that deck B's pads drive — found

- **Problem:** In FX mode the Starlight's deck B pads switch effects the screen does not show.
- **Root cause (read in code):** Section 2, row 7. GEN `:205` draws effect unit 1 only; deck B pads drive unit 2 and route it to deck 2 (PIN midi.xml `:706-743`).
- **Change (GEN, QSS-P; question 5):** PROTO's FX page, plus a two-button switch at the left of the header: **FX 1 · deck A pads** and **FX 2 · deck B pads**. Each unit has its own route chips (DECK 1, DECK 2, MASTER), MIX slider and three effect cards; the cards carry "Starlight FX pad 1-3" for that unit's deck and the unit's own-deck route chip carries "PAD 4". The switch is skin-only state. Slider handles 28×48.
- **Layer:** skin generator and QSS.
- **Automated checks:** two unit groups with keys `EffectUnit1` and `EffectUnit2`; exactly one visible per switch value; the route buttons keep the "others off first" order (GEN `:211-218`); the effect-selector placeholder test passes.
- **Pi check:** FX (209,24). Starlight in FX mode: deck A pad 1 lights card 1 of FX 1. Switch to FX 2: deck B pad 2 lights card 2 and deck B pad 4 lights DECK 2. A touch on FX 2's card 3 ON does not change FX 1.
- **Risk:** Low. **Size:** M.

## R-18 Settings: full screen with a rail — owner-requested (big menus cover the screen)

- **Problem:** Settings is a panel inside the Decks page with an Advanced sub-page; there is no place for the new media and scan settings.
- **Root cause (read in code):** GEN `:249-300`.
- **Change (GEN, QSS-P, wave 2), following PROTO `rdSettings()`:** `screen` 5. Header 48 px: ✕, the title, "Every change saves as you make it.", and a "Saved" note from `[MixPi],saved` (R-13). Left rail 200 px with four 56 px entries. Right pane: rows with a label, a sub-line and 48 px choices.
  - **Playback:** key lock engine; audio buffer; tempo range (6, 8, 10, 16, 24 %; other values stay in Mixxx preferences); quantize per deck; split cue, with a line that shows headphone mix on cue or master.
  - **Interface:** desktop bar hidden / shown; deck time elapsed / remaining.
  - **Media:** when a USB is plugged in (per question 1); scan progress BAR / ICON ONLY (R-12); handover copies (per question 3, with the `CACHE MB` choices and the line "also the room for handover copies"); Copy to Pi (starts `mixpi-media`, as in R-4); a read-only line "Eject: off / on" from the gate (R-6).
  - **Advanced:** waveform FPS; read ahead; Mixxx preferences… (F-2).
  - All F-1 and F-2 behaviour stays.
- **Layer:** skin generator and QSS.
- **Automated checks:** the rail has four set-value buttons; each pane is visible for one value; the F-1 guard (no two-state toggle on a plain control) passes; the Preferences button is on Advanced and is a push button; every choice is at least 48 px high.
- **Pi check:** gear (717,24): the screen covers y 48-480. Tap each rail entry (100, 124/180/236/292): one pane each. Change the buffer: "Saved" shows within 2 s (build A or later). Advanced › Mixxx preferences…: the dialog opens inside the screen (F-2). DECKS closes Settings.
- **Risk:** Low. **Size:** M.

## R-19 C-1: the round-1 repairs, built and checked — carried

- **State:** committed in `053c618`, never built. Native gate 128/128 (`EV/build3-fixes/`).
- **Change:** none. Build A carries them.
- **Pi check (build A):**
  - **F-10 with a drive (also C-4):** spare stick in. Build A still has the old dialog (the skin-only chip opens it). Select the drive: the status line reads "Load opens this drive in the library. Eject is not available on this system. Keep the drive connected." Tap Eject…: the second dialog shows the same sentence, an empty list, and "Prepare selected disk" grey; a tap on it changes 0 px. Record this as the proof for R-4's answer. Build B removes both dialogs; check that no tap path reaches them.
  - **F-6:** in Sources, press a row, drag 15 px away and back, release: nothing opens.
  - **F-5:** with a saved `PositionDisplay 2`, start: one time shows (elapsed); a tap gives remaining.
  - **F-9:** in Arrange columns, tap a label: the row toggles; a checked box shows a tick.
- **Size:** S (checks only).

## R-20 C-4 leftovers: tracked results files and the sway crash — carried

- **Tracked results files.** Problem: F-15 step 8 was not done; evidence under `deploy/` is not tracked. Change (wave 0, orchestrator): `docs/ideas/FIELD-FIX-RESULTS-20261116.md` with the build-1 and build-2 results, the council round-1 scores, and each open finding mapped to an item here or to "backlog". And `docs/ideas/UI-REDESIGN-RESULTS-20261117.md`, updated at each gate with pass or fail per item and the evidence folder names. Check: both files are in `git ls-files` before the council starts.
- **Sway crash.** Problem: sway exited once (lightdm: "session exited 1"), 2 s after a tab tap, just after a USB storm with about 60 queued udiskie notifications; no segfault in dmesg and no sway message (`EV/field-fix-acceptance/ACCEPTANCE.md:47`, `findings/sway-crash-*`). Root cause: **not confirmed.** First step: reproduce without MANTACORE. With the spare stick in a hub port, toggle that port's `authorized` file 60 times at 2 s intervals while tapping tabs every 5 s; run three times on build 2 (notifications on). For these runs only, start sway with `-d` and keep its log.
  - If it crashes: the log names the cause; open a finding with it; repeat on build A.
  - If it does not crash in three runs: record "not reproduced".
  - Either way run the same three storms on build A (R-15, no notifications). Pass: no crash, Mixxx alive, no pop-up, the chip follows the stick.
- **Layer:** docs; test procedure. No new dependency (no coredump package).
- **Risk:** the cause may stay unknown; the plan then closes the trigger (the notification storm) and says so plainly.
- **Size:** S.

## R-21 C-5: owner checks — carried

| Check | Plan |
|---|---|
| Routing: the card's saved routing is mono, Master on channel 1 and Headphones on channel 2; EOS used Master 1-2 and Headphones 3-4 | No code. The owner decided "no routing seed" on 2026-11-16. Question 8 asks which one is intended; the owner sets it in Preferences. Acceptance compares routing by meaning, not by sha (`EV/field-fix-acceptance-b2/ACCEPTANCE.md`, finding 2). |
| MANTACORE has a loose USB connection | No code. Question 9. During tests its hub port is disabled when it flaps (procedure in `EV/field-fix-acceptance-b2/findings/usb-flap-*`). No eject or storm test uses it. |
| DJ-003: write cues, loops and history back to rekordbox | Stays in the backlog (`docs/ideas/DJ-LIBRARY-TOOLS.md`). This redesign adds no write to any drive. Question 10. |
| USB drives stay read-write | Kept. Nothing in this plan remounts read-only. |

## R-22 Acceptance: builds, in-place updates, the full run

1. Per wave: the Mac suite; the native gate on VM `b` in a new `/srv/uiredesign-<date>` workspace, 0 skips; `tests/test_mixxx_patches.py` with the local source and with a fresh clone.
2. Build on VM `b` with `MIXPI_CONTROLLED_MEDIA=0` and no `MIXPI_MEDIA_EJECT`. Verify the `.deb` with `tools/performance/mixxx-candidate.py verify`. The check phase must print "controlled media OFF" and "media eject OFF".
3. File-level diff against the previous image; write `DEPLOY-FILES.txt` in a new `deploy/test-image-<date>` folder.
4. On the card: back up the logs, `mixxx.cfg`, `soundconfig.xml`, `samplers.xml` and the skin; quit Mixxx (Ctrl+Q for the update to build A; any stop after it); install; verify the sha256 of each file; start.
5. Run every Pi check in this plan with TOOLS; store shots and logs in a new `deploy/ui-redesign-<date>/` folder; log temperature and throttling.
6. Regression set from the field-fix run: record 30 s and check the WAV and CUE; F-1, F-2, F-3, F-4, F-5, F-7, F-8, F-9, F-11, F-14; two decks plus FX with the CPU readout and the underrun count.
7. Owner settings after the run: Wi-Fi, keyboard, routing (by meaning), Sources choices, time mode: unchanged.
8. Update the tracked results file; push `feat/pi-performance-target`.

- **Size:** L.

## 7. Starlight drivability

Every state the Starlight can change must show on the screen. Everything the Starlight cannot do must work by touch.

| Starlight action | Mixxx control (PIN midi.xml) | On-screen mirror | Today | Plan |
|---|---|---|---|---|
| Play | `play` (`:41`, `:117`) | ▶ lit | Yes | Keep |
| Cue | `cue_default` (`:53-56`, `:129-132`) | CUE; position | Yes | Keep |
| Sync | `sync_enabled` (`:65`, `:141`) | SYNC lit; SYNC chip | Button only | R-16 |
| Shift+Sync | `sync_leader` (`:205`, `:269`) | MASTER chip | No | R-16 |
| PFL | `pfl` (`:77`, `:153`) | PFL chip | No | R-16 |
| Shift+PFL on A / on B | script: `headMix` toggle / `headSplit` (`:216-284`; script `:221-258`) | Split cue in Settings, with a cue/master line | Split cue only | R-18 |
| Shift+Cue, Shift+Play | `start`, `play_stutter` | Position on the overview | Yes | Keep |
| Hot cue pads 1-4; Shift = clear | `hotcue_N_activate`, `_clear` (`:310-391`, `:572-653`) | Cues tab 1-8 and overview ticks | Ticks only | R-16 |
| Loop pads 1/2/4/8 beats | `beatloop_N_toggle` (`:400-436`, `:662-698`) | Loop tab buttons lit; LOOP lit | Panel buttons, only when open | R-16 |
| FX pads, deck A | unit 1 effects 1-3; unit 1 → deck 1 (`:444-481`) | FX 1 cards and route | Yes | R-17 |
| FX pads, deck B | unit 2 effects 1-3; unit 2 → deck 2 (`:706-743`) | FX 2 cards and route | **No** | R-17 |
| Shift+FX pad | `effect_selector` (next effect) | The card's effect name | Unit 1 only | R-17 |
| Sampler pads A 1-4, B 1-4 | `[Sampler1-8],cue_gotoandplay`; LED `play_indicator` | Pads 1-8 lit | 1-4 only | R-7 |
| Tempo fader | `rate` | Tempo % | Yes | Keep |
| Jog (touch = scratch, Shift = seek) | script | Waveform and time | Yes | Keep |
| Vinyl button | script-internal state, no control | None possible without a mapping change | No | Not mirrored; stated here |
| Volume, bass, filter, crossfader | mixer controls | None | No | The hardware is the truth; no screen copy |

Touch-only, because the Starlight has no control for it (its mapping has no `[Library]` control and no `LoadSelectedTrack`): browsing, search, Sources, loading to decks and pads, the Media screen and eject, key lock, quantize, loop sizes other than 1/2/4/8, halve, double, exit, reloop, beat jump, hot cues 5-8, effect depth and mix, the effect list, record, Settings. All of these are targets of at least 48 px (unit guard in R-1).

## 8. The XDJ-AZ-inspired additions: keep, cut or change

| Addition | Verdict | Reason |
|---|---|---|
| USB status chip in the top bar | **Keep, change** | It is the owner's "USB icon". No port power-down (no such code; the XDJ does not do it either). The drive name depends on one unconfirmed step; the ring is dropped for a % number (R-4, R-12). |
| Full-screen Media screen with drive cards | **Keep, change** | MAN p.35 SOURCE screen. Buttons: EJECT, BROWSE, COPY TO PI. SCAN is cut: a scan would add drive tracks to the Pi library, where they go missing after eject. |
| "Kept on the Pi for handover" and "Cleaned out" lists | **Keep** | They show the owner's "gets cleaned out after transition out" happening. |
| ON PI chip | **Keep, change** | MAN p.39 shows where a track is saved. Shown only after the drive is gone; before that the chip says USB. |
| Deck tool panel: Loop | **Keep** | Exists and works. |
| Deck tool panel: Jump | **Keep** | MAN p.85; the Starlight has no beat jump; the controls exist in Mixxx. |
| Deck tool panel: Cues 1-8 | **Keep** | MAN p.95: 8 hot cues; the Starlight reaches 4. |
| Slip loop, key shift, gate cue, beat loop 2 | **Cut** | Not requested; each adds a mode to learn on a small screen. |
| Deck colours (deck 1 blue, deck 2 amber) | **Keep, change** | Colour the badges, strips, pad tags and chips. Waveform colours stay as pinned (a test protects them). |
| Sources: left rail of tiles, right pane, crumb, Back | **Keep** | MAN p.37: categories beside the list, with a "next level up" display. Grouping is question 4. |
| Per-pad "⋯" menu | **Change** | Stop and Clear buttons at 48 px. An empty pad opens Load sample for itself. |
| Pad play progress | **Cut for now** | Needs a native widget. Lit-while-playing is kept. |
| Per-row preview button in Load sample | **Cut for now** | Mixxx's preview deck plays to the headphone output only, and the card's routing is an open owner check (question 8). MAN p.58 Touch Preview is the model for later. |
| Loaded-deck badges and coloured key chips in the track list | **Cut for now** | New table delegates; not requested. |
| Two-line LOAD button on Tracks | **Change** | The title sits beside the button (section 4.2). |
| Scan bar "N of M" | **Change** | Percent of folders, honest and never going down (R-12). |
| "Saved" note | **Keep** | Cheap, and it shows the owner that save-on-change works. |
| On insert "READY / ASK / SCAN" | **Change** | SCAN is not an option. READY or ASK is question 1. |
| Handover store "RAM / SD CARD" | **Change** | Question 3. If the answer is RAM, the row shows the cache size choices only. |
| Load Lock (no load to a playing deck) | **Keep** | Already our rule (F-3); MAN p.58, p.132. The same idea guards Eject (R-3). |

## 9. Sizes at a glance

| Item | Layer | Size | Build |
|---|---|---|---|
| R-1 Shell and screen control | skin | L | none to check; A |
| R-2 Page host | patch | S | B |
| R-3 Media model | design | — | — |
| R-4 USB chip and Media screen | patch + skin | L | B |
| R-5 Handover | patch | M | B |
| R-6 Eject engine and gate | patch + system | M | B, gate closed |
| R-7 Eight pads | skin | M | none to check; A |
| R-8 Load sample and Choose pad | skin + patch | M + M | skin: none; native: B |
| R-9 Sources full screen | skin + patch | M + M (+ M to L for grouping) | skin: none; rail: A; grouping: B |
| R-10 Sources edit | patch | M | A |
| R-11 Icons | skin | S | none to check; A |
| R-12 Scan bar | patch | M | A |
| R-13 Save on change | patch | M | A |
| R-14 Clean quit and shutdown order | patch (held) + system | S + S | A |
| R-15 No pop-ups | system | S | A |
| R-16 Deck page and tool panel | skin | L | none to check; B |
| R-17 FX units | skin | M | none to check; B |
| R-18 Settings | skin | M | none to check; B |
| R-19 C-1 checks | — | S | A |
| R-20 Results files, sway crash | docs, procedure | S | — |
| R-21 Owner checks | — | — | — |
| R-22 Acceptance | build | L | A, B, (C) |

New patches, in `MIXXX_PATCHES` order after `mixxx-council-fixes.patch`:

| Patch | Prerequisites |
|---|---|
| `mixxx-clean-quit.patch` (held, `a8a86fa`) | none (it applies to pristine upstream; see its commit) |
| `mixxx-save-on-change.patch` | `mixxx-media-selection.patch` (it patches `samplerbank.cpp` and `playermanager.cpp`), `mixxx-performance-settings.patch` and `mixxx-initial-library.patch` (`coreservices.cpp`) |
| `mixxx-sources-screen.patch` | `mixxx-council-fixes.patch` |
| `mixxx-scan-progress.patch` | `mixxx-quiet-scan.patch`, `mixxx-media-selection.patch` (`libraryscanner.cpp`) |
| `mixxx-media-screen.patch` | `mixxx-council-fixes.patch` |
| `mixxx-media-handover.patch` | `mixxx-media-screen.patch`, `mixxx-removable-ram-cache.patch` |
| `mixxx-sample-browser.patch` | `mixxx-sources-screen.patch` |
| `mixxx-source-groups.patch` (only if question 4 says A) | `mixxx-sample-browser.patch` |

## 10. Owner decisions needed

Each question names the screen, and the prototype jump (`go`) and highlight (`hl`) for the orchestrator's annotated screenshots and for `window.MIXPI_CALLS`.

1. **What should happen when a USB drive is plugged in?**
   Options: **A** Ready: the chip shows the drive; Mixxx reads it only after you tap Browse or pick it in Sources. **B** Ask: a sheet "Not now / Use this drive" on each insert. **C** Strict: the drive is not even mounted until you open it (needs the locked-down profile of question 2B).
   Recommendation: **A**. It is the Pioneer SOURCE flow, with no extra tap and no pop-up.
   Area: USB chip and Media screen. Prototype: `go: media`, `hl: usbchip, mediacard`; for B, `hl: insertsheet`.

2. **May we turn Eject on, and with which engine?** This is the approval gate. Until you answer, Eject stays off.
   Options: **A** System eject: Mixxx lets go of the drive, the system unmounts it, the screen says "Safe to remove". No system lock-down. **B** Controlled profile: the strict broker; it removes the `pi` user's general sudo and replaces the automounter, which breaks our in-place updates on that card. **C** Keep Eject off; the screens show state only.
   Recommendation: **A**, tested on a spare stick first, never on MANTACORE.
   Area: Media screen, EJECT button and sheet. Prototype: `go: eject`, `hl: ejectbtn, ejectsheet`; current UI `hlcu: cu-ejdialog, cu-prepare`.

3. **Where should the handover copy of a loaded or playing track live?**
   Options: **A** In memory (up to the `CACHE MB` limit, 1024 by default): nothing is written to the SD card; the copy is removed when the deck loads the next track, and at every start. **B** On the SD card: no size limit, but it writes while audio plays and wears the card.
   Recommendation: **A**. A track too big to copy plays from the drive, and Eject then waits until that deck stops.
   Area: deck info row (ON PI chip), Media screen right column, Settings › Media. Prototype: `go: handover`, `hl: onpi, handover`.

4. **Should Sources be grouped the prototype's way?**
   Options: **A** Grouped tiles: each drive, This Pi (Tracks, Playlists, Crates), Recordings, History, Folders, Samples. A larger change, built in the second wave on top of B. **B** One tile per Mixxx source as today's list has them (Tracks, Playlists, Crates, Computer, Rekordbox and so on), full screen with the rail, crumb and Back.
   Recommendation: **A**. It is what makes Sources easier to navigate, and drives-first matches the Pioneer SOURCE screen. You get B first in build A either way.
   Area: Sources. Prototype: `go: sources`, `hl: sourcesrail, sourcespane`.

5. **The Starlight's deck B effect pads drive effect unit 2, which the screen does not show. How should we fix that?**
   Options: **A** The FX tab gets a switch: "FX 1 · deck A pads" and "FX 2 · deck B pads". **B** Remap the Starlight so both decks' pads drive unit 1 (a custom controller mapping to maintain). **C** Leave it.
   Recommendation: **A**. The screen then mirrors the hardware and the mapping stays stock.
   Area: FX tab. Prototype: `go: fx`.

6. **Turn off the udiskie pop-ups (`72e98c4`)?**
   Options: Yes / No. Recommendation: **Yes**. The USB chip now shows the same facts, and the pop-ups covered SETTINGS and REC.
   Area: top right of the screen. Prototype: `go: decks`, `hl: usbchip`; current UI `hlcu: cu-top`.

7. **Take the clean-quit change (`a8a86fa`) and let a reboot or power-off wait for Mixxx to save (about 1 s normally, 20 s at most)?**
   Options: Yes / No. Recommendation: **Yes**. Together with save-on-change, a normal reboot loses nothing and a power pull loses at most a second.
   Area: power button; Settings "Saved" note. Prototype: `go: settings`, `hl: saved`.

8. **Audio routing: the test card is saved as mono, Master on channel 1 and Headphones on channel 2; EOS used Master 1-2 and Headphones 3-4. Which do you want on the test card?**
   Options: keep mono 1/2 / set stereo 1-2 and 3-4 yourself in Preferences. Recommendation: **stereo 1-2 and 3-4**, if the card should behave like EOS. We change nothing either way. Sample preview in Load sample waits for this answer.
   Area: Settings › Advanced › Mixxx preferences… › Sound Hardware. Prototype: `go: settings` (Advanced).

9. **Can you give us a spare USB stick (FAT32 or exFAT, with a rekordbox export, a few tracks and a few samples) for the eject, handover and USB-storm tests, and check MANTACORE's loose connector?**
   Options: Yes / No. Recommendation: **Yes**. Without a spare stick the Eject and handover checks cannot run, because we will not test them on MANTACORE.
   Area: USB port. Prototype: `go: media`.

10. **DJ-003 (write Pi cues, loops and history back to rekordbox) stays in the backlog, and this redesign writes nothing to any USB drive. OK?**
    Options: Yes / pull it into this redesign. Recommendation: **Yes**, keep it out. Eject and handover should be proven before any write path is added.
    Area: none.

### 10.1 Owner answers, 2026-11-17, and what they change

Recorded by the orchestrator (Claude Opus 5.5 xhigh). The owner's words are verbatim. Where an answer changes an item, the change below overrides the item text above.

| Q | Owner (verbatim) | Decision and changed items |
|---|---|---|
| 1 | "It should have a small ping that ask's to load with a load and dismiss button, it shouldn't be very intrusive and can cover the bottom actions." | **Insert ping.** On insert, a small strip at the bottom (over the transport row, which the owner allows) says "MANTACORE plugged in" with **LOAD** and **DISMISS** (each at least 96×48). LOAD = Open (level 2, R-3); DISMISS closes the ping and leaves the drive closed; it can still be opened from the USB chip or Sources. No sheet, no scrim, no pop-up. It closes by itself after 15 s as DISMISS. Changes R-3 (Insert row), R-4 (chip and ping), R-18 (no on-insert setting: the ping is the behaviour). The ping belongs to the media page code (R-4, N3). |
| 2 | "Yes, maybe a bottom indicator that flashes up when it's safe to remove." | **Eject approved, engine A (system eject).** The gate (R-6) may be opened on the test card once R-5 and R-6 pass their native fixtures. Add a **Safe to remove** bottom indicator: when the unmount is confirmed, a green strip at the bottom flashes up ("MANTACORE · Safe to remove"), whatever screen is open, and stays until the drive is pulled out or 30 s pass. Changes R-4, R-6. The controlled profile (engine B) stays off. |
| 3 | "Yes but only if it doesn't impact performance more than 10% of the current average load if not then we can go with a seamless a when eject is pressed and then pass or wait till it's done." | **RAM copy, with a performance gate.** Measure on the test card: average `[MixPi],audio_load_percent` and underruns with two decks playing tracks from a USB drive, CACHE MB 1024 against OFF, same tracks, 5 min each. Pass: the RAM-copy run's average load is at most 1.10 × the OFF run's. If it fails, switch R-5 to **copy on eject**: Eject copies each in-use file to RAM (or the SD card if it does not fit), swaps the reader to the copy at the next chunk boundary without a gap, then unmounts; the sheet shows the copy step and waits until it is done. Changes R-5 (new acceptance step), R-3. |
| 4 | "Alright well see how it works" | **Grouped Sources (A)** in wave 2 (`mixxx-source-groups.patch`, N4). The one-tile-per-source rail ships first in build A. |
| 5 | "Alright but let's see if we can keep the 3 effects switcher between deck 1 deck 2 and master then have another mode. The starlight does have effects settings, maybe we just need to map them." | **FX page keeps today's three-way route switcher** (DECK 1 / DECK 2 / MASTER) for effect unit 1 as the main mode, and adds a **second mode** for effect unit 2 (the unit deck B's pads drive), with the same switcher. Plus a **mapping study** (R-17b): list the Starlight's FX controls in the pinned mapping and propose how they could drive what the screen shows. No mapping file is changed in this climb; the proposal goes to the owner with the result. Changes R-17. |
| 6 | "Absolutely yes" | Cherry-pick `72e98c4` (R-15). |
| 7 | "yes" | Cherry-pick `a8a86fa`; build R-14's stop unit. |
| 8 | "Sure you can go ahead and do that." | **Set the test card's routing to stereo: Master on outputs 1-2, Headphones on 3-4**, through Mixxx Preferences › Sound Hardware on the card (wave 0), after a backup of `soundconfig.xml`. This is the one allowed change to the owner's routing. Changes R-21. |
| 9 | "It should be okay, I can switch but everything is a usb 2.0 anyway, i'd rather really see performance with a proper flash." Clarified: **9a B** (tests may use MANTACORE itself) and **9b B** ("yes": a faster USB flash drive, not an SD reflash). | **MANTACORE may be ejected** in the eject and handover tests: clean unmounts only, through R-6. We still never write, move or delete anything on it. **The USB-storm test (R-20) never cuts the connection of a mounted MANTACORE**: each cycle ejects it cleanly first, then toggles the port, then waits for the mount and the chip; if its loose-connection loop starts, disable its hub port (field-fix ACCEPTANCE finding 1). The build-2 notification storm is not reproduced on MANTACORE; R-15 removes the notifications anyway. **Flashes stay 0.** Performance checks (R-5 gate, holdout CPU) run on MANTACORE (USB 2.0) now, and are re-run on a faster flash drive when the owner plugs one in; results name the drive. |
| 10 | "Agreed." | DJ-003 stays in the backlog. Nothing writes to any USB drive. |

## 11. Council scoring rubric

Seats: Claude Opus 5.5 (xhigh), Claude Fable 5.2 (high), GPT-6.1 Sol (xhigh). If a provider cannot run, fill its seat as the owner's standing rule says and name the stand-in in every report. Target: all three at 9 or more.

Score the plan, and later the built result, from 1 to 10. Each criterion is pass, partial or fail.

| # | Criterion | Pass means |
|---|---|---|
| 1 | Coverage | Each owner comment in the request (six photos, overall direction, saving) and each carried item C-1 to C-5 maps to an item or to a stated "no change" with a reason. Each item is marked owner-requested, carried or found. |
| 2 | Root cause | Each cause cites file and line, or is marked "not confirmed" with the first step that confirms it. No guess is written as fact. Spec and prototype statements that the code contradicts are corrected. |
| 3 | Verifiable | Each item has an automated check (unit, generated-XML assertion, or a native Qt fixture named for `REQUIRED_TESTS`) and a Pi check with TOOLS and coordinates. A person other than the author can run them. |
| 4 | Safe | Every constraint in section 1 holds. Eject and controlled media are off in every image; the gate cannot open by a setting or a skin change. MANTACORE is never a test target. Saved user data and routing are not overwritten. |
| 5 | Order | Sweeping changes first (shell, page framework, media model), details after. Each wave ends with both gates before a build. No item depends on a later one. |
| 6 | Size, layer and build honesty | Each item has an honest size and layer. The build count is stated with a ceiling. Skin-only checks are separated from package-build checks. The ownership map has no repo file, and no Mixxx source file, owned by two builders in a wave. |
| 7 | Design fidelity | The result matches the owner's comments first and the approved prototype second. Each departure from the prototype is listed with a reason (sections 2, 4.2 and 8). The owner's answers to section 10 are applied. |
| 8 | Touch and Starlight usability | Every touch target is at least 48 px (enforced by a test). Lists scroll by drag and by a 24 px bar. Every state the Starlight can change shows on screen; every function the Starlight lacks works by touch (section 7). Full-screen views close with one tap. |

Scale:

- **10:** all eight pass, and a reviewer finds no factual error in a cited line.
- **9:** all eight pass. At most two minor defects: an unclear step, a missing coordinate, or a size one step off. No defect can cause an extra build or a wrong fix.
- **7-8:** one criterion is partial. Example: one item has no automated check, or one cause is stated as fact without evidence.
- **5-6:** two or three criteria are partial, or one fails.
- **4 or less:** a constraint is broken, an owner comment is missing, or the plan needs more builds than its stated ceiling.

Hard limits: a broken constraint caps the score at 4. A missing owner comment caps it at 6. A root cause that a reviewer disproves in source caps it at 7 until corrected.

## 12. Owner UI review, 2026-11-17: binding for build C

Recorded by the orchestrator (Claude Opus 5.5 xhigh).

**Background.** After build B, the owner reviewed every screen in the private review page "MixPi UI review" over five rounds and agreed every item. Their words are verbatim in `docs/ideas/UI-REVIEW-1-20261117.md`. The agreed design is written down, with 800×480 mockups and the design CSS, in **`docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md`**.

**Owner, 2026-11-17 19:13:** "Okay let's do the thread migrate where we update the climb tuner plan with all these agreed items and climb to the new pi build. Same orchecstration, builders and reviewers as we have done in the recent past. Please don't deviate from UI we set and have the reviewers know what the app is supposed to look like so they judge against that not what they think is best."

### 12.1 Precedence

- Where the spec differs from an item above, from 4.2, from the prototype or from build B, **the spec wins**.
- Where the spec says nothing, build B stays as it is.
- Nobody adds a design of their own: no builder, reviewer or orchestrator.
- Known overrides:
  - **R-9:** Sources is no longer full-screen navigation. It is a **side menu on the right**, under ☰. **Edit sources** (the owner's name for the list where sources are switched on or off, ordered and starred; owner note on s5, 19:10: "Say edit sources when putting it in the plan.") stays full screen (spec s5).
  - **R-11:** while Sources is open, ☰ becomes the standard **red ✕ close, with no outline**, in the same spot. It is not a lit button.
  - **R-17:** effect ON/OFF is a **button**, not a switch. Slider fills run full height. Effects are **saved within a second of a change**.
  - **10.1 Q1 and R-18:** Settings › Media gains **"Plugging in a drive: ASK / AUTO LOAD"**, default ASK. ASK is the Q1 ping, and AUTO LOAD opens the drive with no ping. This replaces Q1's "no on-insert setting".
  - **R-4:** the Media page follows spec s13:
    - ALL, READY and IN USE filters;
    - one row per drive with OPEN (browse icon) and EJECT (eject icon, Caution);
    - a scroll bar;
    - no COPY TO PI, and no deck or song lines;
    - the footer line "N tracks playing from Pi memory".
  - **R-16:**
    - Tool panel: EXIT LOOP (Danger) and RELOOP (Sound) on their own row, with ½ and ×2 given green borders.
    - Deck row: title and artist side by side; the artist is shortened first when the SYNC or MASTER chips show.
  - **R-7:**
    - CLEAR SAMPLES… opens a popover with ticks, and CLEAR (n) is Danger.
    - Each pad has its own ▶ TRIGGER and ■ STOP.
  - **R-8:** Load sample offers SAMPLES and SOURCES… only.

### 12.2 New items, U-1 to U-10

| Item | What (spec section) | Builds on | Layer |
|---|---|---|---|
| U-1 | The rules for every screen (spec 1): tokens, roles, 3 px radius, pill chips, see-through lit states, close on the right as the red ✕ with no outline at rest, ticked rows with no left edge, scroll bars | R-1, R-16, all QSS | skin |
| U-2 | Tool panel loop rows (s2) | R-16 | skin (generator) |
| U-3 | Tracks header order and ▶ beside CUE on both decks (s3) | R-11, R-1 | skin |
| U-4 | Sources: side menu on the right, ☰ becomes ✕, Back and Edit icons, top-level and inside-a-source headers, scroll bar, full-screen **Edit sources** with DONE and ✕ (s5) | R-9, R-10, R-11 | skin and native (the Sources rail patch) |
| U-5 | Sampler: CLEAR SAMPLES… popover, TRIGGER and STOP split, empty-pad text, deck-row title and artist (s6). Acceptance adds a full shutdown test for the samples | R-7, R-16, R-13 | skin and native |
| U-6 | Load sample: SAMPLES and SOURCES… only (s7) | R-8 | skin and native |
| U-7 | FX: ON/OFF button, full-height slider fill, effects saved within a second of a change (s8) | R-17, R-13 | skin and native (save) |
| U-8 | Settings › Media: Plugging in a drive, ASK or AUTO LOAD (s11) | R-18, R-4 | skin and native |
| U-9 | Settings › Interface: Brightness, Night dim and CPU readout (s12). Brightness and Night dim need write access to `/sys/class/backlight/*/brightness` for the session user, through a udev rule or a small root helper (a new system file), which is a system change. Night dim's low level is an implementation value: report it to the owner, who may tune it. | R-18, R-1 | skin, native and system |
| U-10 | Media page (s13) | R-4 | native (the media page) and skin |

**Carried into build C:**
- every round-1 council repair at `fb1a119`;
- build B's 5 failed and 6 blocked acceptance checks, with the drive checks run on the owner's spare stick;
- the Q3 10% performance gate (fallback approved: ship the RAM copy, and add copy-on-eject only if a later test fails);
- the interactive Starlight session, where the owner presses and the orchestrator screenshots, and the owner comments before anything changes.

### 12.3 Rubric amendment (section 11)

- **Criterion 7, Design fidelity, now reads:**
  - The built result matches `agreed-ui/AGREED-UI-SPEC.md` and its mockups, and the owner's verbatim words. On the card, each spec screen is checked against its mockup, with a screenshot.
  - **A deviation from the spec is a defect.** A reviewer's own preference is not a finding and does not change the score.
  - Real usability or safety concerns with the agreed design go under "Owner questions (no score effect)".
- **New hard limit:** an unlisted deviation from the agreed UI caps the score at 6, the same as a missing owner comment.
- **Briefing reviewers:** every reviewer gets the spec, the 12 mockups and this section before scoring.

### 12.4 Budget

- **Build C:** the owner's message of 19:13 is their yes to build C as the 4th pi-gen run, past the old ceiling of 3.
- **Any later build** needs the owner's yes again.
- **Council rounds:** 1 of 5 used.
- **Flashes:** stay at 0. Delivery is an in-place update.

### 12.5 Owner decisions after build C (2026-11-18)

The owner saw build C on the test card (acceptance C: 43 of 45 PASS, the Q3 gate PASS at 1.01×). Their answers, in chat:

- **Fonts:** "I want you to fold in reverting the font as you continue." Then: "All fonts back to build B". The spec's font rule (section 1) now says build B's fonts; the mockups no longer bind the font.
- **Build D:** "Yes, run build D". This is the **5th pi-gen run**. It carries the three deviations that need app code (★ for the saved start, the narrowed table's columns, OPEN switching to Tracks), the two below, the font revert, and the skin repairs made after build C. Any later build needs the owner's yes again.
- **Edit sources child rows:** "Bring the rows back". They are indented rows with only an ON/OFF toggle, in the agreed row style (spec 2a).
- **Loop panel with the top bar shown (800×444):** "Shorter rows then". The rows may go below 48 px in that mode only (spec 2a).
- **Starlight session:** later.
- **Agents:** "Let's change to only having 3 agents running at a time max." This counts builders, testers, operators and council seats together. A 3-seat council round runs only when nothing else does.
- **Reviewers:** score against the spec as amended in its section 2a. A build D screen whose font differs from the mockup is **not** a finding when it matches build B's font.

### 12.6 Owner decisions after council round 2 (2026-11-18)

Council round 2 (at `d75c1fe`, build D on the card) scored Claude Opus 5.5 xhigh 6, Claude Fable 5.2 high 6 and GPT-6.1 Sol xhigh 6. All three were real seats, with no stand-ins.

The owner's answers (spec 2b):
- **Items accepted as they are:** "1 is not necessary" (Edit sources drag on row text), "3 is not necessary" (the narrowed Samples table's last header) and "4 is not necessary" (Clear samples drag).
- **Build E:** "do 2" (the accent edge after OPEN and BROWSE). This is the **6th pi-gen run**. It also carries the owner's "Stop it, then clear" for a ticked pad that is playing, and the skin repairs (REC dot, EXIT LOOP and RELOOP at rest, the table's row colours).
- **Owner session:** after build E is on the card.
- **Reviewers in round 3:** the three accepted items are **not** findings, and they do not make criterion 8 partial; the owner accepted them.

### 12.7 Owner decisions after build E (2026-11-18)

- **RELOOP:** "that is correct". Build B's behaviour stays (no pressed look while a press starts the loop). Not a finding.
- **Shared column setup:** "I want to keep the column setup across the different source menus and have it be saved after edit like the settings". The owner chose "Columns, order and widths" (sorting stays per list) and "Build F now, then council". **Build F is the 7th pi-gen run**, approved for this. Spec 2c.
- **FX pads:** the owner described deck A pads → FX 1 and deck B pads → FX 2, independent of the screen, with a per-unit route override. That is already how the stock Starlight mapping and the FX page work; there is no change. It is checked in the Starlight session.


### 12.8 Owner decisions in the build F session (2026-11-19)

- **The overview strip freeze:** "Good catch on the strip. Please Fix". The cause is a stock Mixxx 2.5.6 bug, upstream issue #9751: EngineBuffer's `playposition` throttle counter overflows about 6 h 46 min after a load without a seek. Build G backports upstream `bef0af3172` as `mixxx-overview-playposition.patch`.
- **Build G (the 8th pi-gen run):** the owner chose "Fix both": the overview fix, and acceptance F's FAIL. A column shown again through Arrange columns must come back at its saved width, not 160 px (`mixxx-shared-columns-width.patch`).
- **MANTACORE's port:** "You can remove the Mantacore port rule and put it on again." Its hub port is no longer disabled after a boot. MANTACORE stays read-only: nothing is ever written, moved or deleted there.
- **Kept as stock and not findings:**
  - a short Sync tap syncs once, and a hold latches (`LONGPRESSLATCHING`);
  - Shift+Sync gives the leader only to a playing deck;
  - PFL does not take a deck off master.
- **Build H (the 9th pi-gen run):** "Yes, build H first". After acceptance G, build H fixes acceptance G's regression: TITLE's stretched width was saved (`mixxx-shared-columns-stretch.patch`). Council round 3 scores build H.

### 12.9 Owner decisions after council round 3 (2026-11-20)

- **Scores:** Fable 8, Sol 8 and Opus 6. The Opus seat was capped by the narrowed-header cuts; it would score 8 without the cap.
- **Accepted:** the cut header letters in every narrowed table, and the disabled ★ on an off row (spec 2d).
- **Build I (the 10th pi-gen run):** the owner chose to build three items as drawn: the menu shadow, the Tracks row inside a drive, and the chip and ping timing. The header strip fix also goes in.
- **The owner is away overnight and asked for no more questions.** The orchestrator carries build I through to acceptance and council round 4 on its own judgement, within the spec. Anything that cannot be built as drawn is recorded for the owner, not asked.


### 12.10 Owner decisions after council round 4 and during build J (2026-11-20/21)

- **Kept as on the card (spec 2e):** the Sources menu's capitals, build I's USB chip, and the ping's 15 s. J2 and J3 were reverted. Round 4's two caps are owner-accepted items.
- **Build J (spec 2e, 2f):**
  - the quit crash (J1);
  - after an eject, the table drops the drive's rows and ☰ opens at the top level (J4);
  - ☰ after OPEN opens inside the drive (J5);
  - the KEY-sort fix (J6);
  - the drive-rows cache fix (J7);
  - the rekordbox text fix (J8);
  - the Zoom row with its % readout, and shorter rows with the top bar (J9).
- **Dropped by the owner:** the Starlight quick zoom (the headphone knob is hardware) and the zoom indicator.
- **USB ports are never switched off** by tests or tools; re-plugs are done by the owner's hand.

### 12.11 Owner decisions after council round 5 and in build K (2026-11-21)

- **Sideways scroll with many columns is accepted** (spec 2g). Owner: "Sideways scroll is fine."
- **Build K (the 12th pi-gen run):** the owner said "sure thing. Go ahead!" for J10, the Folders eject case of spec 2e. After the DNS failure the owner chose "Resume from stage 3", and gave "Go ahead" for the card update.
- **Port toggles in acceptance K only:** the owner said "Just try turning the port off and on again to simulate it." The orchestrator switched GANDER1's port (1-1-port1) off and on twice, IXIAN untouched, and all ports were back on. The default "never switch a USB port off" still holds for later tests.

### 12.12 Owner decisions after council round 6 (2026-11-21, night)

- **Build L (the 13th pi-gen run), the card update and acceptance L tonight.** The owner, going to bed: "do that last round fix have everything ready for the morning. Do all the proof and give me a visual timeline in the pr so I can go through all these rounds changes in the morning."
- **The timeline:** the orchestrator chose the "climb tuner local app style" option. It is a standalone `tools/climb-timeline/` page built from one JSON file, in its own thread. No PR was opened.
- **No port toggles and no physical re-plugs tonight.** GANDER1 is mounted and unmounted in software (`udisksctl`), and IXIAN is never ejected.

### 12.13 Owner notes for the next build (2026-11-22, morning)

Recorded only; no work has started. The owner: "You can add these to the note's for the next build. Don't do any work yet."

- **Reading a drive again after an eject.** Today a drive that is ejected and then mounted again without a physical re-plug stays unreadable until Mixxx restarts (build B's eject rule in `mixxx-media-selection.patch`). The owner: "No, we should be able to reload it if it is still connected." Next build: a drive that is still connected after an eject can be mounted again and read without a re-plug or a restart. This also covers the "thin tags" in Folders and the "SAFE TO REMOVE" that stays after a software remount.
- **The 1 px line under the empty part of the table header** (carried minor item). The owner: "Show me so I can choose to keep or remove it." Next step: show the owner a before-and-after (a card screenshot with the line and a render without it), then keep or remove it as the owner chooses.
- **GANDER1's file system** (marked "not properly unmounted" before acceptance L). The owner: "I'll give it a look, but it should be okay." No repair from the Pi.
- **Debian package updates on the card** (the card still has build I's packages; 18 security updates were out on 2026-11-22). The owner: "Absolutely do that. Thanks!" Apply them on the card when the work starts, and put the same package state in the next image.
