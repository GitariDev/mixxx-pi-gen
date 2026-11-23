# Handoff to the main climb: three-band main waveforms (owner pick)

Branch `rnd/waveform-three-band-20261122`, on `fd1e940` (kMainWaveformGain 0.90). Not pushed, not merged; the main climb's orchestrator integrates it.

This version answers two adversarial reviews of `589144d` (Sol 5/10, Fable 7/10; `deploy/rnd-waveform-three-band-20261122/review/` in the main checkout) and carries the owner's three answers to the review questions (2026-11-23, below). **Nothing here has run on the card.** The full Mixxx build has not been compiled with this patch yet; see "What is proven".

## What the owner chose (`OWNER-DECISIONS.md`)
- **A Overlay** in **Pioneered's own colours** (low #004ee4, mid #c95a00, high #f6e9d3): Mixxx's all-shader Filtered waveform (type 19), bass, mids and highs drawn over each other.
- **A setting** in **Settings › Advanced**, row **"Waveform colours"**, choices **RGB** and **3-BAND**, under Read ahead.
- **Three-band by default** after the next build; RGB is one tap away.
- **The Loop panel's waveform follows the setting** (Mixxx's waveform type covers every scrolling waveform). The overview strips stay as they are.
- **The Loop panel's 3-BAND waveform is as tall as RGB there** ("Same height as RGB"): total_gain, not Mixxx's doubled Filtered height.
- **A start that cannot draw 3-BAND shows the choice disabled** ("Show it unavailable").
- **A third waveform type picked in Mixxx's Preferences keeps lighting RGB** ("Keep lighting RGB").
- J13/J15 height kept: the main rows draw at pregain × 0.90, no ReplayGain.

## What changed
| File | Change |
|---|---|
| `stage3/01-install-packages/files/mixxx-waveform-three-band.patch` (**last** in `MIXXX_PATCHES`) | See "How it works". Touches `coreservices.cpp`, `mixxxmainwindow.{h,cpp}`, `util/mixpiwaveformcolours.h` (new), `waveform/mixpiwaveformgain.h`, `waveform/renderers/allshader/waveformrendererfiltered.cpp`, `waveform/waveformwidgetfactory.{h,cpp}`, `widget/wwaveformviewer.cpp`. |
| `stage3/01-install-packages/01-run.sh` | the patch, after `mixxx-menu-current-row.patch` |
| `stage3/01-install-packages/files/mixpi-performance.py` | the Advanced row; the 3-BAND button's `enabled` is bound to `[MixPi],waveform_three_band_available` (as the Audio buffer buttons are to `buffer_available`); `three_band_colours()` sets the three colours on the waveform template, and a `SignalColor` when the base skin has none (Mixxx drops the band colours without one) |
| `stage3/02-desktop/files/bin/mixpi-touch-defaults` | **unchanged from before the R&D** (the default moved into Mixxx) |
| `tests/test_waveform_three_band.py`, `tests/native/waveform_three_band_{runner.py,test.cpp}` | patch, skin and native checks |
| `tests/test_mixxx_patches.py`, `tests/test_menu_current_row.py` | registry line; prerequisites (height-gain and zoom-setting patches); only this patch may follow menu-current-row |
| `tools/performance/required-native.py` | `test_waveform_three_band` in the required gate |
| `tools/performance/waveform-three-band-heights.py` | the "A Loop panel" row is at total_gain; the old 2 × total_gain row stays as "A-stock Loop" |

**After the owner's answers:**
| Answer | Change |
|---|---|
| Same height as RGB | `mixpi::filteredHeightCompensation(rgbStacked)` no longer looks at the main-row flag: the all-shader Filtered renderer never asks for the doubled height, on a main row or in the Loop panel. The Stacked type and every other renderer are stock. Native: the Loop panel's Filtered height on the example is 0.38 (was 0.76). |
| Show it unavailable | New read-only control `[MixPi],waveform_three_band_available` (1 or 0) in `mixpiwaveformcolours.h`, from a third call the main window hands over (`findHandleIndexFromType(19) >= 0`). Only the 3-BAND button binds `enabled` to it; the page's existing `#MixpiButton:disabled` rule draws it, no new QSS. |
| Keep lighting RGB | no code change |

## How it works
- **The setting.** `[MixPi],waveform_colours` is 0 (RGB, type 17) or 1 (3-BAND, type 19). The main window owns it: made in `MixxxMainWindow::initialize` after the waveform factory has its config, deleted in the destructor before the factory. Outside that time the control does not exist.
- **Threads.** A write from any thread (a controller script, a MIDI mapping) is queued to the GUI thread and applied there, in the order written. It never touches a widget on the caller's thread. A write still queued at quit is dropped.
- **The row is honest.** The control shows the type the factory runs (`WaveformWidgetFactory::mixpiAppliedType`): 1 when every scrolling waveform runs type 19, otherwise 0. It follows every change of the type (`mixpiWidgetTypeChanged`: the skin has loaded, Mixxx's own Preferences, this setting). A request is confirmed only if the waveforms run the asked type afterwards. If a waveform fell back to the empty one, the type from before is asked for again. The factory is the only writer of `[Waveform],WaveformType`.
- **The default, once.** `CoreServices` calls `MixpiWaveformColours::defaultOnce` when `mixxx.cfg` has been read, before the factory reads the type: without `[MixPi],ThreeBandDefault` the type becomes 19. The key is recorded once the factory has taken type 19, and saved by the save on change (under 1 s) or at exit. After that a choice of RGB is kept. Mixxx's own parser reads the file, so repeated or indented keys, repeated sections and malformed lines behave as Mixxx reads them and never stop the start.
- **Unavailable.** `[MixPi],waveform_three_band_available` is read-only (a write is ignored with Mixxx's read-only warning): 1 when the factory has a handle for type 19, otherwise 0. It is made with the setting, before the skin binds, written at every sync, and ends with the setting. At 0 the 3-BAND button is disabled (dim text, dashed border, as a disabled Audio buffer choice) and cannot be tapped; RGB is always enabled. A handle whose widget fails to start still counts as available; the honest row covers that case.
- **Height.** Only the all-shader Filtered renderer does not ask `getGain` for Mixxx's doubled height (`mixpi::filteredHeightCompensation`), on a main row and in the Loop panel, so 3-BAND is as tall as RGB in both: pregain × 0.90 on a main row, total_gain in the Loop panel. `WaveformWidgetRenderer::getGain` is stock; the software, textured and Stacked renderers are as in Mixxx.
- **Passthrough.** Each switch used to leave one more passthrough connection on the viewer (stock Mixxx). The connection now ends with its waveform widget.

## Install, start and rollback
- **Binary and skin ship together.** The default is in the binary; the row is in the generated skin.
  - New binary, old skin: the card opens in 3-BAND at the right height, with no row to go back (RGB only through Mixxx's Preferences).
  - Old binary, new skin: the row is there but does nothing (no such control), and nothing changes. The 3-BAND button is disabled: the skin makes the missing availability control itself, at 0.
  - The seeder has no part, so there is no order to keep with it and an old binary never gets the default.
- **Order on an existing card:** stop Mixxx (it saves `mixxx.cfg` on a clean quit), back up `~/.mixxx/mixxx.cfg`, install the Mixxx DEB and regenerate the Pioneered skin with this branch's `mixpi-performance.py`, then start Mixxx.
- **Any start route applies the default:** the launcher, `systemctl --user restart mixpi-mixxx.service`, a reboot.
- **Rollback:** stop Mixxx, restore the backed-up `mixxx.cfg`, install the previous DEB and skin. Without the backup, set `WaveformType 17` under `[Waveform]` by hand: an older binary draws a saved type 19 at stock double height on the main rows and has no row. `ThreeBandDefault 1` in a kept config means a later update will not switch to 3-BAND again; delete the line to get the default once more.
- **Other gates:** any screenshot baseline or review-page image that shows the main waveforms changes with the default.

## What is proven, and what is not
- **Mac suite:** all pass apart from skips.
- **Native test (`test_waveform_three_band`, 6 modes):** run on the Mac with a Qt 6 SDK, patched and baseline, after the owner's answers too. Not yet run on VM b (the leader's gate).
  - Real code: `mixpiwaveformcolours.h`, Mixxx's config parser and save on change, the control framework, `WaveformWidgetRenderer::getGain` from the real header, and the Filtered renderer's own argument to `getGains`, cut out of the stack's source at build time.
  - The baseline (the stack without the patch) fails for the real reason: stock Filtered asks `true`, stock `getGain` doubles, the main row draws 1.80 and the Loop panel 0.76 (patched: 0.90 and 0.38).
  - The availability control follows the factory double's handle for type 19 (1 with it, 0 without, again at a sync), ignores a write, and ends with the setting.
  - Worker-thread writes reach the apply callback on the GUI thread only; rapid opposing writes run in order and end in the last value.
- **Doubles, so not proven natively:** the waveform factory is a recording double. `mixpiAppliedType`, `mixpiSwitchTo`, the main window's wiring (the availability call included) and the Filtered renderer's call site are checked as text. The skin's `enabled` binding is checked in the generated XML; the disabled look itself is not rendered in a test. The renderer's constructor is a test double; `m_gain` is set as `onPreRender` sets it.
- **Not compiled anywhere yet:** `mixxxmainwindow.cpp`, `waveformwidgetfactory.cpp`, `wwaveformviewer.cpp` and `waveformrendererfiltered.cpp` with this patch. The first full build is the proof.
- **Not proven at all until the card:** the live switch of four GL widgets on Wayland and V3D, first paint, audio continuity, frame rate.

## Numbers, and what they are
- **Main rows, 3-BAND, modelled on the card's library** (`tools/performance/waveform-three-band-heights.py`; pregain 1, VisualGain 1, flat EQ): tallest band median 0.36 of the half height, 99th percentile 0.83, at most 0.90, no column at the edge (RGB outline: 0.58 / 0.89 / 0.90). A pregain above 1, an EQ boost or a VisualGain above 1 draws past 0.90 in both styles.
- **Stock Filtered without the height rule** (2 × 0.90) would put 25.6 % of a typical track's columns on the edge.
- **The Loop panel's waveform** now draws 3-BAND at total_gain, as RGB does: on the example a loud track is 0.38 in both styles (stock Filtered would be 0.76). Measured on the card's library copy (on the Mac, `deploy/rnd-waveform-three-band-20261122/44-heights-on-library-2cef7c8.txt`, "A Loop panel" row): median 0.15, 99th percentile 0.34, largest track-level 99th percentile 0.60, no column at the edge (stock 2 × total_gain: 0.31 / 0.69 / 1.19). A boosted quiet master with a pregain above 1 can still reach the edge, in both styles.
- **CPU:** "+29 % on the waveform loop, about 1 % of a core" comes from a synthetic bench on the Mac that repeats the renderer's per-frame loops on random bytes and **draws nothing**. Filtered sends three vertex arrays and four draw calls per waveform against RGB's one. The card's frame rate is unmeasured.
- J13's height script assumes 3 visual frames per column; the card shows 4 at that zoom (small effect on its statistics).

## Card checklist (none done: the card is the main climb's)
Before: back up `~/.mixxx/mixxx.cfg` and the Mixxx logs (each start keeps only 10).
1. **Default applied.** After the install and a start by `systemctl --user restart mixpi-mixxx.service`: `grep -A3 -E '^\[(Waveform|MixPi)\]' ~/.mixxx/mixxx.cfg` shows `WaveformType 19` and `ThreeBandDefault 1`. The same on a clean first start with no `mixxx.cfg`.
2. **Decks page.** Both main waveforms in blue / orange / cream. The overview strips unchanged.
3. **Measured height, not by eye.** A screenshot of a loud track in 3-BAND: the tallest band at 0.90 of the half height on both main rows. The same measurement after switching to RGB and back (the main-row flag survives re-creation). Repeat with two tracks of different ReplayGain at the same pregain: same height.
4. **The row.** Settings › Advanced has four rows (Waveform FPS, Read ahead, Waveform colours, Mixxx preferences), 3-BAND lit. Layout checked at 800×480 and 800×444.
   - **3-BAND is enabled on the Pi.** The 3-BAND button has the normal look (solid border, not dim text on a dashed border) and takes a tap, whichever choice is lit. If a controller or the developer tools are at hand: `[MixPi],waveform_three_band_available` reads 1. A disabled 3-BAND on the Pi means the factory has no handle for type 19: stop and report.
5. **First paint after switching from Settings.** With both decks playing: choose RGB, go back to Decks: both rows painted at once, no blank or black row. Choose 3-BAND, back to Decks: the same. Time from tap to first painted frame.
6. **What is kept through a switch.** Tracks, play position, zoom per deck, hot cue marks with labels and colours, beat grid, loop range (with a loop active through the switch), the play marker and the end-of-track flash, on both rows.
7. **The Loop panel reopened.** The gear closes the Loop panel, so after each switch reopen it on each deck: its waveform paints on first show, in the chosen style, with marks and loop range.
8. **Twenty switches, both decks playing.** No audio dropout, no change in the xrun count, no GL error or warning in the Mixxx log, memory steady, no crash. Then toggle passthrough once: the label shows once.
9. **Audio continuity.** Record the master through one switch each way: no gap or click.
10. **Frame rate at 30 fps.** Both decks playing in 3-BAND: sustained frame rate and dropped frames, against RGB. Note the first-show latency.
11. **RGB kept.** Choose RGB, restart twice (once by the launcher, once by the service): RGB still lit, `WaveformType 17`, the decks in RGB.
12. **Mixxx Preferences agrees.** Choose 3-BAND, open Preferences › Waveforms: "Filtered (all-shaders)". Choose RGB there, apply, close: the row lights RGB without a restart.
13. **Loop panel height equal to RGB's.** Measured from screenshots, not by eye: with the Loop panel open on a loud track, the tallest band in 3-BAND is as tall as the RGB outline in the same columns after switching (reopen the panel after each switch, check 7). Repeat on a quiet track. Neither style is doubled, and the two change together with the pregain knob.
14. **Controller write** (if a controller is at hand): a script line `engine.setValue('[MixPi]', 'waveform_colours', 0)` while both decks play switches cleanly.

## Known limits
- **GL failure after creation.** The row is honest about a type with no handle and a widget that fails to start. A GL window that fails later, at first exposure, is not seen by the factory; checks 5 and 7 are the guard.
- **Order across threads.** Writes from one thread keep their order. A write made on the GUI thread is applied at once, ahead of writes still queued from another thread.
- **A start that cannot draw type 19** (no shader support; not the Pi): the row shows RGB with 3-BAND disabled, the default is not used up and is tried again at each start, so until then a non-shader type picked in Preferences is replaced by Mixxx's own choice at start.
- **The control's lifetime.** A script that writes `[MixPi],waveform_colours` before the main window exists or after it has gone gets Mixxx's unknown-control warning.
- **Preferences left open.** Mixxx's Preferences reads the type when it opens; a change from Advanced while it is open shows there after reopening (stock dialog).
- **Slip mode's split view** exists only for the RGB type (stock); MixPi's skin has no slip control, a controller's slip button would show no split in 3-BAND.
- **End-to-end gate.** There is no automated test of the real application with GL widgets and a loaded track; the checklist stands in for it.

## Review findings
| Finding | Outcome |
|---|---|
| Sol 1, Fable M1 (thread, lifetime) | fixed: GUI-thread apply, owned by the main window, native thread mode |
| Sol 2, Fable m6 (seeder parsing, launch stops) | fixed: the default is in Mixxx, read by its parser; the seeder is untouched |
| Sol 3, Fable m2, m3 (honest row) | fixed: applied type from the factory, confirm only on success, restore after a fallback. 3-BAND is disabled when it cannot be drawn (owner: "Show it unavailable") |
| Sol 4, Fable m1, H1 (rollout) | fixed: any start route; install and rollback above |
| Sol 5, Fable M2 (tests) | fixed for threads, default and height (real `getGain`, real baseline); the real GL switch stays a card check |
| Sol 6 (Preferences and Advanced disagree) | fixed for RGB and 3-BAND; other types still light RGB (owner: "Keep lighting RGB") |
| Sol 7 (height rule scope) | fixed: Filtered renderer only (main rows and the Loop panel) |
| Sol 8 (passthrough connections) | fixed in the patch |
| Sol 9, Fable M3, H2, H3 (checklist, claims) | fixed: this document |
| Fable m4 (Loop panel height) | fixed: the RGB height (owner: "Same height as RGB") |
| Fable m5 (`SignalColor`) | fixed |

## The owner's answers (2026-11-23, `OWNER-DECISIONS.md`)
No question is open.
1. **The Loop panel's waveform height in 3-BAND: "Same height as RGB".** Done: total_gain, no doubling; card check 13.
2. **A third waveform type picked in Mixxx's Preferences: "Keep lighting RGB".** No change: the row lights RGB for any type other than 19.
3. **A start that cannot draw 3-BAND: "Show it unavailable".** Done: the 3-BAND button is disabled from `[MixPi],waveform_three_band_available`; card check 4 confirms it is enabled on the Pi.
