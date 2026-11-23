# Handoff to the main climb: three-band main waveforms (owner pick)

Branch `rnd/waveform-three-band-20261122`, on `fd1e940` (kMainWaveformGain 0.90). Not pushed, not merged; the main climb's orchestrator integrates it.

## What the owner chose (`OWNER-DECISIONS.md`)
- **A Overlay** in **Pioneered's own colours** (low #004ee4, mid #c95a00, high #f6e9d3): Mixxx's all-shader Filtered waveform (type 19), bass, mids and highs drawn over each other.
- **A setting** in **Settings › Advanced**, row **"Waveform colours"**, choices **RGB** and **3-BAND**, under Read ahead.
- **Three-band by default** after the next build; RGB is one tap away.
- **The Loop panel's waveform follows the setting** (Mixxx's waveform type covers every scrolling waveform). The overview strips stay as they are.
- J13/J15 height kept: pregain × 0.90, no ReplayGain.

## What changed
| File | Change |
|---|---|
| `stage3/01-install-packages/files/mixxx-waveform-three-band.patch` (new, **last** in `MIXXX_PATCHES`) | `util/mixpiwaveformcolours.h`: `[MixPi],waveform_colours` (0 RGB, 1 3-BAND) switches every scrolling waveform live through `WaveformWidgetFactory::setWidgetTypeFromHandle` and saves `[Waveform],WaveformType` 17 / 19; refuses other values; confirms only after the factory switched. `waveform/mixpiwaveformgain.h` + `waveformwidgetrenderer.h`: the main waveforms skip `getGain(true)`'s ×2 (`mixpi::heightCompensation`), so 3-BAND's loudest band stops at 0.90 like the RGB outline. `coreservices.{h,cpp}`: owns it next to the Zoom setting. |
| `stage3/01-install-packages/01-run.sh` | the patch, after `mixxx-menu-current-row.patch` |
| `stage3/01-install-packages/files/mixpi-performance.py` | the Advanced row; `three_band_colours()` sets the three colours on the waveform template (main rows and the Loop panel's) |
| `stage3/02-desktop/files/bin/mixpi-touch-defaults` | `three_band_once()`: sets `[Waveform] WaveformType 19` once, records `[MixPi] ThreeBandDefault 1`; afterwards the owner's choice is kept |
| `tests/test_waveform_three_band.py`, `tests/native/waveform_three_band_{runner.py,test.cpp}` (new) | patch, skin, default and native checks; the native checks fail without the patch |
| `tests/test_mixxx_patches.py` | registry line; `PREREQUISITES`: height-gain and zoom-setting patches |
| `tools/performance/required-native.py` | `test_waveform_three_band` in the required gate |
| `tests/test_menu_current_row.py`, `tests/test_pioneered_touch.py` | only the three-band patch may follow menu-current-row; new configs also get the three-band default lines |

## Height at 0.90 (on the card's library, `tools/performance/waveform-three-band-heights.py`)
3-BAND's tallest band: median 0.36 of the half height, 99th percentile 0.83, at most 0.90, no column at the edge (RGB outline: 0.58 / 0.89 / 0.90). Without the patch's height rule, stock Filtered at 2 × 0.90 would put 25.6 % of a typical track's columns on the edge. The Loop panel's waveform keeps Mixxx's 2 × total_gain (median 0.31, at most 1.19 on a boosted quiet master).

## Checks to ask for on the card (none done: the card is the main climb's)
1. Decks page after the update: both main waveforms in blue / orange / cream (3-BAND), loud tracks short of the edge.
2. Settings › Advanced: four rows (Waveform FPS, Read ahead, Waveform colours, Mixxx preferences), 3-BAND lit; RGB switches both decks and the Loop panel live, with tracks, zoom and play position kept; 3-BAND switches back; the choice survives a restart.
3. Frame rate with 3-BAND on both decks playing at 30 fps (CPU estimate +29 % on the waveform loop, about 1 % of a core; not measured).
4. The overview strips unchanged.

## Not done / notes
- A type chosen later in Mixxx's own Preferences dialog is not reflected by the row (the row reads the saved type at start).
- Slip mode's split view exists only for the RGB type; MixPi does not use slip.
- J13's height script assumes 3 visual frames per column; the card shows 4 at that zoom (small effect on its statistics).
