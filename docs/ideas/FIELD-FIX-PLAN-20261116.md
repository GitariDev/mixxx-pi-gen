# Field fix plan — 64 GB test card batch, 2026-11-16

Source of truth: `docs/ideas/FIELD-REVIEW-20261116.md` (owner comments and SSH walkthrough).
This plan covers each owner comment and each confirmed finding. It ends with one package build, one image build and one test-card flash.

Reference names used below:

- **GEN** = `stage3/01-install-packages/files/mixpi-performance.py` (skin generator).
- **PIN** = pinned Mixxx 2.5.6 source, commit `3ebac449…` (bare repo `/tmp/mixpi-actions-routing-objects-20261115`).
- **PT** = patched tree `/tmp/mixpi-actions-routing-source-20261115` (PIN plus the patch stack).
- **TOOLS** = `deploy/recovery-20261116/pi-review/tools` (`pi.sh`, `ui.sh`, `shot.sh`, `vtouch.py`).
- Shot numbers refer to `deploy/recovery-20261116/pi-review/shots/`.

## 1. Constraints

- The EOS card and the MANTACORE USB are read-only. Do not write to them. Do not use `TOOLS/pi.sh` on EOS.
- Do not touch the Lima VMs `colima-mixpi-ui` and `colima-synthetic`. The builder VM is Lima `b` with `LIMA_HOME=/tmp/mq1110-1943`.
- Controlled media and Mixxx eject stay OFF.
- Push only `feat/pi-performance-target`.
- Add no dependency without a stated reason. This plan adds none. F-14 can remove one.
- Pi work uses the test card only, with `ssh -4`. Back up `~/.mixxx/logs` before tests that restart Mixxx; Mixxx keeps 10 logs.
- GTK tests run on the Pi only. On macOS, platform skips are expected. On the Linux gate, a skip is a failure.
- New Mixxx changes go into new patches at the end of `MIXXX_PATCHES` (`stage3/01-install-packages/01-run.sh:4-25`). Do not edit earlier patches; later patches depend on their context.

## 2. Coverage map

| Review entry | Source | Item |
|---|---|---|
| Owner 1: recording works | owner | No change. Regression check in F-15. |
| Owner 2: Actions and Browse formatting, browse settings | owner | F-7, F-8, F-9 |
| Owner 3: LOAD and CUE on Tracks | owner | F-3 |
| Owner 4: waveform and beat grid versus EOS | owner | F-4 |
| Owner 5: Advanced Back; Preferences from Advanced | owner | F-1, F-2 |
| Owner 6: samples copied | owner | Done. Sampler check in F-15. |
| B1 Advanced Back dead | found + owner | F-1 |
| B2 no Preferences entry | found + owner | F-2 |
| B3 sources touch-drag | found | F-6 |
| B4 time readouts clipped | found | F-5 |
| Table width, BPM lock square, selection style | found | F-7 |
| Browse columns, preview icons, no persisted state, folder icons, SD-BACKUP | found | F-8 |
| Arrange columns dialog | found | F-9 |
| Load/Eject wording | found | F-10 |
| SETTINGS and DECKS both highlighted | found | F-11 |
| No headphone/cue output | found | F-12 |
| Appliance quieting candidates | found | F-13 |
| `xdg-desktop-portal-wlr`, `waybar` failures | found | F-14 |
| Starlight MIDI "not open for output", deprecated-key warnings | found | Not in this batch. Check LED feedback in the F-12 hardware session. The deprecated keys come from the upstream skin manifest and do no harm. |
| Loop panel, FX, sampler load flow | found, working | No change. Regression check in F-15. |

## 3. Work order

1. **Stage 0, no code, current test card:** F-4 measurement, F-12 step 1, F-13 measurement, F-14 journal read, F-8 SD-BACKUP check. One SSH session.
2. **Stage 1, skin generator only:** F-1, F-3, F-5, F-11, F-4 decision, QSS parts of F-7 and F-9. Verify each on the current test card: regenerate the skin with `/opt/mixpi-skin-tools/mixpi-performance.py`, restart Mixxx, run the Pi check.
3. **Stage 2, Mixxx patches:** F-2, F-6, F-7 (width), F-8, F-9 (dialog), F-10. Verify with native Qt fixtures on VM `b`. No package build yet.
4. **Stage 3, image and system config:** F-12, F-13, F-14.
5. **Stage 4:** F-15, one package build, one image build, one flash, full Pi acceptance run.

Item numbers give priority: bugs and owner requests first.

---

## F-1 Advanced Back does nothing — owner-requested, found (B1)

- **Problem:** Back leaves the Advanced page open (shots 17–22).
- **Root cause (read in source, not yet reproduced):**
  - `[MixPi],settings_advanced` is a plain `ControlObject` (`mixxx-performance-settings.patch:181`, `:206-210`).
  - A `WPushButton` toggles only when its control is a `ControlPushButton`. Otherwise the left mode stays PUSH (PIN `src/widget/wpushbutton.cpp:144-151`).
  - In PUSH mode each press sends 1.0 (PIN `wpushbutton.cpp:410-414`). "Advanced…" sends 1 and works. Back also sends 1, so nothing changes. The release value 0 is not sent, because the connection uses `EmitOnDownPress` (GEN `:65`).
  - The native test writes the control directly, so it passes (`tests/native/performance_settings_test.cpp:138-142`). No test presses the button.
  - The review's z-order and re-entry suspects are not necessary to explain the bug.
- **Change:** GEN `:272` and `:280`. Build both buttons with the existing `preset()` helper (GEN `:228-233`): `preset('Advanced…', key, 1)` and `preset('Back', key, 0)`. These are explicit set-value push buttons, as the FPS buttons and the loop Close button (GEN `:158-161`) already are.
- **Acceptance:**
  - Unit (`tests/test_performance_skin.py`, extend `test_settings_effective_columns_and_advanced`): both buttons have `LeftClickIsPushButton`; Back writes through `<Not/>`; Advanced writes through `<IsEqual>1</IsEqual>`.
  - Unit guard, new: each generated two-state `PushButton` without `LeftClickIsPushButton` must target a key in an allowlist of real Mixxx toggle controls (`keylock`, `quantize`, `sync_enabled`, `play`, `headSplit`, effect `enabled`). This prevents the same defect on a new button.
  - Pi: `TOOLS/ui.sh f1.png 'tap 591 25' 'tap 598 279' 'tap 400 275'`. The shot shows PLAYBACK and INTERFACE. Repeat three times, with taps at x = 60, 400 and 740.
- **Risk:** Low. **Size:** S. **Layer:** skin generator only.

## F-2 Open Mixxx Preferences from Advanced — owner-requested, found (B2)

- **Problem:** The touch UI has no path to Mixxx Preferences. The only path is the desktop Settings app, which sends Ctrl+P with `wtype` (`stage3/02-desktop/files/bin/mixpi-audio-preferences`).
- **Root cause:** No skin control opens the dialog in 2.5.6.
- **Change:**
  - New patch `mixxx-preferences-entry.patch`: add control `[MixPi],show_preferences` in `MixpiPerformanceSettings`. On a request above 0, call the public slot `MixxxMainWindow::slotOptionsPreferences` (PIN `src/mixxxmainwindow.h:58-63`) with a queued `QMetaObject::invokeMethod` on the parent window. Queued, so the dialog does not open inside the touch press handler.
  - GEN: on the Advanced page, put `Back` and a push button `Mixxx preferences…` in one 48 px row.
- **Acceptance:**
  - Native (`tests/native/performance_settings_test.cpp`): a test window counts slot calls. Request 1 gives one call after the event loop runs. Request 0 gives none.
  - Unit: the button is on the Advanced page, is a push button, and uses `EmitOnDownPress`.
  - Pi, while a track plays: Settings → Advanced… → Mixxx preferences…. The shot shows the dialog fully inside 800×480 with its Close/OK buttons visible. Close it. The shot shows the decks. `throttled=0x0`; the log has no new underrun.
- **Risk:** Medium. The dialog must fit `floating_maximum_size 780 x 420` (`stage3/02-desktop/files/i3.conf`). The dialog is not a touch design; this item gives access only. Changing sound hardware while playing stops audio; that is upstream behaviour.
- **Size:** M. **Layer:** Mixxx patch (package build) plus skin generator.

## F-3 LOAD and CUE in the bottom bar on Tracks — owner-requested

- **Problem:** On Tracks, each deck shows CUE and PLAY (shot 01). The owner wants LOAD and CUE. LOAD loads the highlighted track into that deck.
- **Root cause:** The bottom row is the same on all tabs. Only the first four buttons are tab-scoped (GEN `:463-474`).
- **Change (GEN `:463-474`):**
  - Add `LOAD` per deck on `[ChannelN],LoadSelectedTrack`, sent on press and release, as the sampler pads do (GEN `:318-320`). Bind `visible` to `[Tab],library`. Bind `enabled` to `[ChannelN],play` through `<Not/>`.
  - Bind `visible` of ▶ to `[Tab],library` through `<Not/>`.
  - Order on Tracks: LOAD, CUE. FX and Sampler keep CUE and ▶. Decks is unchanged.
  - Do not use `LoadSelectedTrackAndPlay` (the test at `tests/test_performance_skin.py:348` already forbids it for pads; extend it to decks).
- **Notes:** The load uses the selection of the current table (PT `src/widget/wtracktableview.cpp:1396`), so it works in Tracks, playlists, Computer and rekordbox views. A fresh profile rejects a load into a playing deck (`LoadWhenDeckPlaying 0`, `testcard-mixxx.cfg:68`; PT `src/mixer/playermanager.cpp:713-719`). The disabled state shows this to the user.
- **Acceptance:**
  - Unit: per deck, LOAD has the key, the two bindings and press-and-release emit; ▶ has the inverse `visible` binding; CUE is unchanged; each button is at least 48 px high.
  - Pi: Tracks → tap a row → tap LOAD for a stopped deck (cells at x = 100/300/500/700, y = 454). The title strip shows the new track. With deck 1 playing, LOAD 1 is grey and a tap does not change the title. Repeat once in Computer → Music.
- **Risk:** Low. Tracks has no touch PLAY after this change; play comes from the Decks tab or the controller. This is the owner's request.
- **Size:** S. **Layer:** skin generator only.

## F-4 Waveform and beat grid versus EOS — owner-requested

- **Problem:** The owner sees a different deck view on the test card and reads it as less visible.
- **What is known:**
  - Renderer, waveform settings and `<Visual>` definitions are identical (review).
  - Generator delta in the deck view: `MixpiWaveInfo` is 136 px, was 100 px (GEN `:444`; EOS `skin.xml:2095`, `:2229`). The key label is 132 px, was 92 px (GEN `:442`). The waveform is 664 px wide, was 700 px.
  - Row height is not a regression. The Nov 9 EOS capture has the 36 px top bar; the test card shots do not (see F-14). Rows are about 122 px against 104 px.
  - **Beat spacing is zoom state, not skin (computed, to confirm in step 1).** Pixels per second = 441 ÷ zoom at rate 1.0 (PIN `src/waveform/renderers/waveformwidgetrenderer.cpp:135-154`, `src/analyzer/analyzerwaveform.cpp:59`). At 102 BPM, zoom 3 gives 86.5 px per beat (EOS capture: 86). Zoom 5 gives 51.9 (test card: 52). `DefaultZoom` is 3 on both. Mixxx applies it at start (PIN `src/waveform/waveformwidgetfactory.cpp:540`). Two taps on the loop panel "−" (GEN `:365`) give zoom 5, and zoom sync moves both decks.
- **Controlled A/B (test card only):**
  1. Back up the logs. Save `/usr/share/mixxx/skins/Pioneered/skin.xml` and its sha256 to `~/ab-20261116/current/`. Record `[Waveform]` from `mixxx.cfg` and the FPS setting.
  2. Run A = current `skin.xml`. Run B = EOS `skin.xml` (sha `180733c8…`, `deploy/recovery-20261110/full-native-build/native-skin/skin.xml`). Swap only `skin.xml`, with Mixxx stopped. Judge only the Decks page in run B.
  3. Each run: start Mixxx (zoom returns to 3). Use the same top-bar state. Load "Frontin' The Best" (102 BPM) on deck 1 and "Kanye West-Addiction…" (125.5 BPM) on deck 2. Do not touch zoom or tempo. Tap CUE on both, stay paused, take a grim shot. Then play both decks for 60 s and sample.
  4. Measure from the PNG: px per beat (mean over at least 8 grid lines; expected 86.5 and 70.3), waveform width and height, grid-line width, and the contrast ratio of the grid line against the background and against the waveform.
  5. Measure load: Mixxx process CPU (`top -b -d 5 -n 12 -p <pid>`), the CPU readout in the top bar, the frame rate shown in Preferences → Waveforms, `vcgencmd measure_temp`, `vcgencmd get_throttled`, and underrun lines in the log.
  6. Order the runs A, B, A, B, A, B to cancel thermal drift. Use medians.
  7. Restore: stop Mixxx, copy the saved `skin.xml` back, confirm the sha256, start Mixxx, take shots of Decks and Tracks.
  8. Store shots and numbers in `deploy/recovery-20261116/waveform-ab/` (gitignored).
- **Revert criteria ("if performant").** Restore the EOS deck layout only if all are true:
  1. Median Mixxx CPU in B is at most A + 3 points of one core, and the CPU readout is at most A + 2 points.
  2. Frame rate in B is at least A − 2 FPS and at least 90 % of the configured FPS.
  3. `get_throttled` stays `0x0` and the log has no new underrun in B.
  4. The shots confirm that B has the wider waveform and the same px per beat as A at zoom 3.
- **Change if the criteria pass:** GEN `:442-444`: `MixpiWaveInfo` back to `100f`, `MixpiWaveKey` back to `92f,36f`. Keep `PairedNotation`; the Nov 9 capture shows "6A (Gm)" inside 100 px. Add `Elide` if the longest key clips.
- **If the criteria fail:** keep 136 px and record the numbers in the review file.
- **If step 1 shows a px-per-beat difference at zoom 3:** stop. The zoom explanation is wrong; open a new finding before any change.
- **Acceptance:**
  - Unit: assert the chosen sizes in the generated XML. The existing test `test_build_on_pinned_pioneered_preserves_visual_and_overview` must pass unchanged.
  - Pi: after a fresh start, a paused shot shows 86 ± 2 px per beat at 102 BPM and the chosen waveform width.
- **Risk:** Low. The run-B skin refers to controls that no longer exist (`media_eject`); Mixxx creates empty ones.
- **Size:** M (mostly measurement). **Layer:** skin generator only.

## F-5 Deck time readouts are clipped — found (B4)

- **Problem:** `-3:14` and `-2:45` run under the BPM box on Decks and Sampler (shots 00, 24).
- **Root cause:** `MixpiTime` is 112 px, was 130 px; the key cell is 140 px, was 75 px (GEN `:139-144`). A fresh profile shows elapsed and remaining time (`PositionDisplay 2`, `testcard-mixxx.cfg:70`), about 16 characters at 21 px (`mixpi-performance.qss:19`). The Nov 9 EOS capture shows one time only; the EOS setting is not confirmed. The image no longer installs its `mixxx.cfg` (`stage3/02-desktop/03-run.sh:3`).
- **Change (GEN `:139-144`, `mixpi-performance.qss:19-21`):** Make the widest mode fit, because a tap on the readout cycles the three modes (PIN `src/widget/wnumberpos.cpp:36-47`). Start from Time `176me`, BPM `76me`, Rate `52me`, Key `96me` (sum 400) and a 19 px time font. Tune on the Pi.
- **Owner decision (section 4.1):** elapsed only by default, tap toggles to remaining. This replaces the three-mode fit above: size the cell for one time, seed `PositionDisplay 0`, and restrict the tap cycle to two modes.
- **Acceptance:**
  - Unit: the four minimum widths sum to at most 400; Time is at least 170.
  - Pi: load a track longer than 10 minutes, set the elapsed-and-remaining mode, take shots on Decks and Sampler. Both times, the BPM, the rate and the key are complete. Check key `11B (G♭)` or the longest key in the library.
- **Risk:** Low. Font metrics can be checked only on the Pi.
- **Size:** S. **Layer:** skin generator only.

## F-6 Sources list: a touch-drag must scroll — found (B3)

- **Problem:** A drag on the Sources list opens a source and does not scroll. The highlight stays on the old source (shot 05).
- **Root cause (read in source):**
  - The sidebar is a `QTreeView` with no touch scroller (PT `src/widget/wlibrarysidebar.cpp:16-33`). The patch stack has no `QScroller`.
  - `pressed` activates a source on finger-down (`mixxx-sidebar-sources.patch:115-117`). `clicked` enters it (PT `src/widget/touchsourcenavigation.h:20-21`). A drag is a press without a click, so the page changes and the selection does not.
- **Change (new patch `mixxx-touch-scroll.patch`, in `enableTouchNavigation()`, PT `wlibrarysidebar.cpp:35-57`):**
  - Set `ScrollPerPixel` and grab a `QScroller` touch gesture on the viewport. `QScroller` is in QtWidgets; no new dependency.
  - In touch mode, a pointer press must not emit `pressed`. Activation comes from `clicked` only (the model already activates on `clicked`). Keep the keyboard and controller paths that emit `pressed` (PT `wlibrarysidebar.cpp:308`, `:342`).
- **Also check, not in the review:** the track table has no scroller either (PIN `src/widget/wlibrarytableview.cpp:31-46`). Run the same drag on the track table. If it selects rows and does not scroll, add the table to this patch and disable row drag-and-drop in the touch skin.
- **Acceptance:**
  - Native (`tests/native/library_interface_sources_test.cpp`): a synthetic touch drag over three rows changes the scroll value and causes no activation. A tap causes one activation, and the selected row equals the active source.
  - Pi: `TOOLS/ui.sh f6.png 'drag 640 400 640 250'`. The list moved and the Tracks table is still shown. Then tap PLAYLISTS: the Playlists page shows and PLAYLISTS is highlighted.
- **Risk:** Medium. Scroller and tap can conflict; the fixture must cover a slow drag, a fast flick and a tap. USB hot-plug resets the tree during a drag; the existing navigation tests must still pass.
- **Size:** M. **Layer:** Mixxx patch (package build).

## F-7 Tracks table formatting — owner-requested, found

- **Problem:** The table uses about 550 of 770 px, with a blank light header block (shot 01). The BPM column shows a black square. The selected row is a light bar with a separate cell outline.
- **Root cause:**
  - Width: the touch defaults set order and visibility only (`mixxx-library-interface.patch:495-509`). No column stretches.
  - Square: the BPM delegate draws a checkbox named `LibraryBPMButton` (PIN `src/library/tabledelegates/bpmdelegate.cpp:33-34`, `checkboxdelegate.cpp:9-20`). The skin has no rule for it.
  - Selection: the upstream skin uses `selection-background-color: #e5e6ea` (EOS `style.qss:276-291`). The focus outline comes from the `focusBorderColor` property (PT `src/widget/wtracktableview.h:76`).
- **Change:**
  - New patch `mixxx-table-columns.patch` (shared with F-8): the first visible text column (Title; Filename in Browse) uses stretch mode. Keep `stretchLastSection` on as a fallback when that column is hidden.
  - `pioneered-touch.qss`: a zero-size indicator for `#LibraryWrapper #LibraryBPMButton`; a dark selection (`#27577d` with white text, as `mixpi-performance.qss:6`); `qproperty-focusBorderColor` equal to the selection colour.
- **Acceptance:**
  - Native (`tests/native/library_interface_test.cpp`): at a 770 px viewport, the visible section widths sum to the viewport width, with and without Title.
  - Unit (`tests/test_pioneered_touch.py`): the managed style block has the three rules.
  - Pi: a Tracks shot shows no light block right of KEY and no black squares; the selected row is one bar. Tap a BPM cell three times; `bpm_lock` for that track does not change (`sqlite3 -readonly`).
- **Risk:** Low. Stretch mode removes manual resize of that one column.
- **Size:** M. **Layer:** Mixxx patch (width) plus skin QSS.

## F-8 Computer/Browse columns and persistence — owner-requested, found

- **Problem:** Browse opens with the wide upstream columns and needs a sideways scroll (shots 09–12, 29). The Preview column has no use, because the preview deck is hidden. No browse header state is stored.
- **Root cause:**
  - Defaults (confirmed in source): the touch defaults run only when `fieldIndex("title")` is 0 or more (PT `src/widget/wtracktableviewheader.cpp:294-300`). Browse uses `ProxyTrackModel`, which does not override `fieldIndex`; the base returns −1 (PIN `src/library/trackmodel.h:238-241`).
  - Persistence (**not confirmed**): the namespace exists (`mixxx.db.model.browse`, PT `src/library/browse/browsetablemodel.cpp:48-49`), the proxy forwards the setting (PIN `src/library/proxytrackmodel.cpp:216-228`), and a save runs on each model switch (PT `src/widget/wtracktableview.cpp:223-227`). A row should exist. Suspects: Browse header items have no column-name role, so the saved state has empty names and restore cannot map them (PT `wtracktableviewheader.cpp:47-55`); or the database copy was read before a save.
- **Change (in `mixxx-table-columns.patch`):**
  1. First, reproduce in a native fixture: Browse model through the proxy, change the header, switch model, read the settings row.
  2. When `fieldIndex` returns −1, find columns with `columnIndexFromSortColumnId`. Browse default: Filename (stretch), BPM, Key, Duration. Preview is hidden.
  3. Give Browse columns stable names for the saved state (set the name role in the model, or use the logical index when the name is empty). Save on each Arrange change and on each model switch.
- **Check only:** the review calls `SD-BACKUP` stale because `/media/pi` has only MANTACORE. The source keeps copies under `/media/SD-Backup` by design (PT `src/library/rekordbox/rekordboxfeature.cpp:216-227`, `removablemounts.h:52-60`). Run `ls /media` on the test card. If the directory exists, there is no bug.
- **Not in this batch:** folder icons in the Computer tree. This needs a model change for a small gain.
- **Acceptance:**
  - Native: default Browse columns are the four above and fill 770 px. After Arrange (add Artist), a model switch and a switch back, the order is the same. The row `mixxx.db.model.browse.header_state_pb` exists.
  - Pi: Computer → Music shows four columns and no horizontal scrollbar. Add Artist, restart Mixxx, open Music again: Artist is still shown.
- **Risk:** Medium. The persistence cause is open until step 1.
- **Size:** M. **Layer:** Mixxx patch (package build).

## F-9 Actions menu and Arrange columns dialog — owner-requested ("clunky"), found

- **Problem:** The Arrange columns dialog is a light dialog with 17 px rows (shot 04). The Actions menu opens over the selected row with small rows (shot 03).
- **Root cause:** The dialog is a plain `QDialog` with a `QListWidget`, 360×360, default row height, drag-to-reorder (`mixxx-library-interface.patch:529-590`). The skin styles `QMenu` only (`pioneered-menus.qss`). The dialog already has the object name `MixpiColumnArrangement` (`:530`). The menu opens at the row position (`:728`).
- **Change:**
  - `pioneered-menus.qss`: rules for `#MixpiColumnArrangement` (dark background, 17 px text, list rows at least 48 px, 28 px check indicator, buttons at least 48 px). Menu rows at least 48 px.
  - New patch `mixxx-touch-dialogs.patch`: dialog size 520×400 (inside the 780×420 float limit). Replace drag-to-reorder with touch scroll; Up and Down stay. When the Actions control opens the menu, anchor it under the Actions button. A right-click keeps the row position.
- **Acceptance:**
  - Native (`library_interface_test.cpp`): dialog size is at most 780×420; each row and each button is at least 48 px high; the list background is dark in a grabbed image.
  - Unit: the style block has the dialog rules.
  - Pi: shots of the menu and the dialog. Tap "Album": the column shows. Drag the list: it scrolls. Close.
- **Risk:** Low.
- **Size:** M. **Layer:** Mixxx patch plus skin QSS.

## F-10 Load/Eject dialog wording — found

- **Problem:** The dialog shows internal terms (shot 25).
- **Root cause:** Strings at `mixxx-media-activity.patch:53`, `mixxx-transfer-display.patch:18` and the device line near `mixxx-media-continuation.patch:533-536`.
- **Change (new patch `mixxx-dialog-wording.patch`, strings only):**

  | Now | New |
  |---|---|
  | No tracked use; not eject clearance | Mixxx is not using this drive. This does not mean it is safe to remove. |
  | Unresolved media use | Mixxx may still use this drive. |
  | No retained transfer result | No copy has run yet. |
  | Transfer interrupted; progress unavailable | The last copy was interrupted. |
  | Transfer result unavailable | The last copy result is not available. |
  | `/media/pi/MANTACORE · 8:0` | `/media/pi/MANTACORE` (keep the device number in the log) |
  | Eject… disabled, no reason shown | Status line: "Eject is off on this system." |

- **Do not change:** logic, the eject gate, or controlled media (stays OFF).
- **Acceptance:**
  - Native: update `tests/test_media_transfer_display.py` and `tests/test_media_activity.py` to the new strings. Add an assertion that no dialog label contains "clearance", "retained" or a `major:minor` number.
  - Pi: tap LOAD / EJECT (402, 25), select the drive, take a shot. Eject stays disabled.
- **Risk:** Low. The safety meaning of the first line must stay.
- **Size:** S. **Layer:** Mixxx patch (package build).

## F-11 Two tabs highlighted at once — found

- **Problem:** With Settings open, SETTINGS and DECKS are both active (shot 15).
- **Root cause:** Settings is a view inside the Decks page. Its button sets `loop_deck` to 3 and forces `[Tab],overview` to 1 (GEN `:416-419`). Both style rules apply (`mixpi-performance.qss:6`, `:12`).
- **Change (GEN `:407-411`):** Replace the DECKS button with a stacked pair of the same size. The normal tab is visible when `loop_deck` is not 3. A twin with no display connection is visible when `loop_deck` is 3. Both send the same writes, so a tap on DECKS still closes Settings.
- **Acceptance:**
  - Unit: for each `loop_deck` value, one DECKS button is visible; the twin has no value-to-widget connection. Update the tests that count `MixpiTab` buttons (`tests/test_performance_skin.py:129`, `:243`, `:293`).
  - Pi: tap SETTINGS: only SETTINGS is highlighted. Tap DECKS: only DECKS is highlighted and the waveforms show.
- **Risk:** Low. **Size:** S. **Layer:** skin generator only.

## F-12 Headphone/cue output — found (deferred audio handoff)

- **Problem:** The test card routes only Master to the Starlight (`hw:3,0`, 4 channels). Pre-listening is not possible.
- **Root cause:** The image seeds no `soundconfig.xml`. On first start Mixxx sets the main output only. The docs record EOS as Master 1–2 and Headphones 3–4 at 44.1 kHz (`docs/setup/HARDWARE.md:41`, `docs/ideas/POST-GIG-PLAN.md:15`). An earlier decision says: do not overwrite saved routing (`docs/ideas/FIELD-FIXES-20261111.md:1142-1148`).
- **Change:**
  1. **Compare, read-only.** With the EOS card booted by the owner, copy `~/.mixxx/soundconfig.xml` and the `[Soundcard]` lines of `mixxx.cfg` with `scp` to `deploy/recovery-20261116/eos-audio/`. Read only; no write, no restart. Copy the same files from the test card. Diff them. Record how EOS names the device (name or `hw:` index).
  2. **Owner decision.** Option A, recommended: `mixpi-touch-defaults` writes a `soundconfig.xml` only when none exists and a Starlight is present: Master on channels 1–2, Headphones on channels 3–4, values from the EOS file. Option B: no seed; the owner sets it once through F-2.
  3. Keep the rule: never change an existing `soundconfig.xml`.
- **Acceptance:**
  - Unit (seeder): no file plus Starlight gives a file with two outputs; an existing file is not changed; no Starlight gives no file.
  - Pi, with the owner, Starlight and headphones: the log shows both outputs open. PFL on deck 2 is audible in the headphones only. SPLIT CUE works. Master is unchanged. Check controller LEDs in the same session.
- **Risk:** Medium. An ALSA card index can change between boots; step 1 must show how EOS stores the device. The listening check needs a person.
- **Size:** M. **Layer:** image/system config (profile seeder).

## F-13 Appliance quieting — found

- **Problem:** Processes with no use in DJ mode run all the time: ModemManager, obexd, mpris-proxy, blueman-applet and tray, an open blueman-manager window, nm-applet, swaync, udiskie, a `foot` terminal.
- **Root cause:** Session autostart in `stage3/02-desktop/files/i3.conf:233-236`, package defaults (`stage3/01-install-packages/00-packages`), and bluez user units.
- **Change:**
  1. **Measure first** (Stage 0): RSS and CPU per candidate, 5 minutes idle and 5 minutes with two decks playing.
  2. **Tier 1, apply:** mask `ModemManager.service`; there is no modem. Find what opens the `foot` and blueman-manager windows (sway tree and journal). Remove the cause if it is in the image.
  3. **Tier 2, owner decision:** start nm-applet, blueman-applet and swaync with the top bar only (their icons are visible only there). Mask the obex user unit. Remove mpris-proxy only if the Speaker tests pass without it.
  4. **Keep:** udiskie. It is the only automounter while controlled media is OFF (`i3.conf:232-233`). Keep lxpolkit.
- **Acceptance:**
  - Unit: stage-file assertions for each change (pattern of `tests/test_touchscreen_build.py` and `tests/test_image_runtime.py`).
  - Pi after flash: `systemctl is-enabled ModemManager` gives `masked`. The process list agrees with the decision. SSH over Wi-Fi works. A USB drive mounts under `/media/pi`. Speaker mode starts and the Speaker tests pass. Bluetooth settings open from the Settings app.
- **Risk:** Medium for Tier 2 (Wi-Fi, Bluetooth and Speaker flows). Low for Tier 1. The gain is small; do not block the batch on Tier 2.
- **Size:** M. **Layer:** image/system config.

## F-14 Failing units: xdg-desktop-portal-wlr and waybar — found

- **Problem:** `xdg-desktop-portal-wlr.service` fails at each boot. `waybar.service` failed twice. Settings still offers "Show top bar".
- **Root cause (not confirmed; read the journal in Stage 0):**
  - The session starts waybar at boot (`i3.conf:227`), but no test-card shot shows a top bar. The failure is the likely reason.
  - Likely race: sway runs the environment import (`i3.conf:221`) and the service starts (`:224`, `:227`) as separate `exec` lines, with no order. A unit that starts before `WAYLAND_DISPLAY` is in the systemd user environment fails.
  - The portal config sends Screenshot and ScreenCast to wlr (`stage3/02-desktop/files/xdg-desktop-portal-sway.conf`). No MixPi part uses these portals; screenshots use grim.
- **Change:**
  1. Read `journalctl --user -b -u waybar -u xdg-desktop-portal-wlr` on the test card. Confirm or replace the cause.
  2. Session start: one `exec` that imports the environment and then starts `sway-session.service` and `waybar.service`, in that order.
  3. Portal: remove `xdg-desktop-portal-wlr` from `00-packages:33` and the two wlr lines from the portal config, if the journal and a repository search show no user. This removes a dependency. If a user exists, order the unit after `sway-session.target`.
  4. Owner decision: top bar visible or hidden after boot. The current design starts it visible.
- **Acceptance:**
  - Unit: `tests/test_desktop_bar.py` plus stage-file assertions for the single start line and the package list.
  - Pi after flash, five cold boots: `systemctl --user --failed` is empty; waybar has the decided state; the shot agrees with it. "Show top bar" and "Hide top bar" each change the shot by the 36 px bar.
- **Risk:** Low to medium. Session start order affects each boot; test five cold boots.
- **Size:** S to M. **Layer:** image/system config.

## F-15 One build, one flash, full acceptance

1. Mac: `python3 -m unittest discover -s tests`. Platform skips are expected.
2. VM `b`: `MIXXX_TEST_SOURCE=<source with the pinned commit> python3 -B tools/performance/required-native.py`. Add each new fixture to `REQUIRED_TESTS` (`tools/performance/required-native.py:15-33`). No skips.
3. Patch order: add the new patches at the end of `MIXXX_PATCHES`. `tests/test_mixxx_patches.py` passes with a local source and with a fresh clone.
4. Build the package once on VM `b`. Verify the `.deb` and its `candidate.json` with `tools/performance/mixxx-candidate.py verify`.
5. Build the image once. Flash the 64 GB test card only.
6. Run the Pi checks of F-1 to F-14 with TOOLS. Store shots in `deploy/recovery-<date>/field-fix-acceptance/`.
7. Regression checks: record 30 s and confirm the WAV and CUE files; load both sampler pads and trigger them; open the loop panel, set a 4-beat loop, exit; set one effect; check `get_throttled` and the CPU readout with two decks playing.
8. Push `feat/pi-performance-target`. Record results in a new review file.

- **Risk:** One build means a failed patch blocks the whole batch. Stage 1 and Stage 2 checks must pass before the build.
- **Size:** L. **Layer:** package build and image.

## 4. Owner decisions (2026-11-16)

1. **F-5:** show elapsed time only. A tap switches to remaining time, and the next tap switches back. Seed `[Controls] PositionDisplay 0` for new profiles only. Limit the tap cycle to elapsed ↔ remaining (the pinned `WNumberPos` cycles three modes); the "both" mode must not appear. The width and font goals still apply to the wider of the two modes.
2. **F-12:** no routing seed. Audio routing stays as Mixxx sets it. The owner changes it in Preferences (F-2) as equipment changes.
3. **F-13:** Tier 1 only. Tier 2 is deferred.
4. **F-14:** top bar hidden after boot. The owner shows it from Settings.

## 5. Council scoring rubric

Score the batch plan from 1 to 10. Use these seven criteria. Each criterion is pass, partial or fail.

| # | Criterion | Pass means |
|---|---|---|
| 1 | Coverage | Each owner comment and each confirmed finding maps to an item or to a stated "no change" with a reason. Each item is marked owner-requested or found. |
| 2 | Root cause | Each cause cites file and line, or is marked "not confirmed" with a first step that confirms it. No guess is written as fact. |
| 3 | Verifiable | Each item has an automated check (unit, native Qt fixture or generated-XML assertion) and a Pi check with TOOLS. A person other than the author can run them. |
| 4 | Safe | All constraints in section 1 hold. Saved user data and saved routing are not overwritten. Eject stays off. |
| 5 | Order | Bugs and owner requests come first. All patch work lands before one package build, one image build and one flash. |
| 6 | Size and layer | Each item is small, independent, and has an honest size and layer. No item hides a second build. |
| 7 | Waveform item | The A/B is controlled (same track, position, zoom), swaps and restores `skin.xml`, lists the measurements, and has numeric revert criteria. |

Scale:

- **10:** all seven pass, and a reviewer finds no factual error in a cited line.
- **9:** all seven pass. At most two minor defects: an unclear step, a missing coordinate, or a size that is one step off. No defect can cause a second rebuild or a wrong fix.
- **7–8:** one criterion is partial. Example: one item has no automated check, or one cause is stated as fact without evidence.
- **5–6:** two or three criteria are partial, or one fails.
- **4 or less:** a constraint is broken, an owner comment is missing, or the plan needs more than one rebuild.

Hard limits: a broken constraint caps the score at 4. A missing owner comment caps it at 6. A root cause that a reviewer disproves in source caps it at 7 until corrected.
