# Juror 2 (Mixxx / Pi 4 engineer): three-band main waveforms

Juror: Claude Fable 5.2. Date: 2026-11-22. I worked alone and did not read the other reports.

What I read: `DIRECTIONS.md`, the statute, guidelines and casebook, `waveform-three-band-sim.py`, `waveform_bands.py`, `waveform-three-band-heights.py`, `waveform-three-band-bench.cpp`, the J13 patch, the pinned Mixxx 3ebac449 sources (`allshader/waveformrendererfiltered.cpp`, `allshader/waveformrendererrgb.cpp` and `.h`, `waveformrenderersignalbase.cpp`, `waveformwidgetrenderer.h`, `waveformwidgettype.h`, `allshader/waveformrenderertextured.cpp`, `stackedsignal.frag`, `widgets/allshader/rgbwaveformwidget.cpp`), and images 01, 12, 13, 20, 21, 30, 31, plus `40-heights-on-library.txt` and `41-cpu-bench-mac.txt`. I saw 10, 11 and 14 only as panels of 20 and 21. Nothing was built or run, and nothing was measured on the Pi.

## 1. Gate check

| Gate | A Overlay | B Stack | C Split | D Lanes |
|---|---|---|---|---|
| G1 height | Pass, only with the ×2 dropped | Pass | Pass | Pass |
| G2 scope | Pass (Loop panel change is stated) | Pass | Pass | Pass |
| G3 Pi cost | Pass | Pass | Pass, at the margin | Pass |
| G4 buildable | Pass | Pass | Pass | Pass |
| G5 privacy | Pass | Pass | Pass | Pass |

Evidence:

- **G1.** `40-heights-on-library.txt`: A at ×0.80 has p99 max 0.80 and 0.00 % at the edge. A at stock height has p99 1.47 and 18.73 % at the edge for the median track, so stock type 19 fails and A depends on its patch line. B is the "today/B outline" row: p50 0.52, p99 max 0.80, 0.00 %. C and D: p99 max 0.80 and 0.76–0.80, 0.00 %. The gate cannot fail for any style drawn at ×0.80, because the data are bytes (at most 255) and 255 × 0.80 / 255 = 0.80.
- **G2.** No direction touches the overview strips. A's type change is global and `DIRECTIONS.md` says the Loop panel becomes Filtered. It does not say how tall that panel then draws (see finding 6).
- **G3.** `41-cpu-bench-mac.txt`: A ×1.32, B ×1.29, C ×2.92, D ×1.34. Fill from `40-heights-on-library.txt`: ×1.27, ×2.19, ×0.67, ×0.43. All four are plain `glDrawArrays` of client-side vertex arrays, as today; none uses a framebuffer object or fixed-function GL. C is 3 % under the limit on one Mac run with synthetic data, so I count it as a pass only if it is built as uniform-colour passes.
- **G4.** Type 19 exists (`waveformwidgettype.h`, `AllShaderFilteredWaveform`). B, C and D keep type 17 and add no type.
- **G5.** The images show "Track A" and "Track B". They also show key, BPM, elapsed time, the real overview strips and the drive label, none of which is a track name. The heights output and the scripts name no track.

### Things I found wrong or unfair

1. **`DIRECTIONS.md:35`, and `waveform-three-band-sim.py:18` and `:347`: "type 26" is really 25.** `AllShaderRGBStackedWaveform` follows `AllShaderTexturedStacked` (24) in the enum with no explicit value, so it is 25. The "// 26" is a wrong comment in upstream `waveformwidgettype.h`. It only affects a dropped option, but a config seeded with 26 would be an invalid type.
2. **`DIRECTIONS.md:28`: "the bass sits flat on the edge in 19 %".** The figure is the tallest of the three bands (`waveform-three-band-heights.py:46`, `max(l, m, h)`), not the bass. In image 30 it is mostly the white highs that sit on the edge.
3. **Slip mode is not mentioned.** Only the RGB widget has the slip split view (`widgets/allshader/rgbwaveformwidget.cpp:25-29`). There a second `WaveformRendererRGB` draws the top half only (`waveformrendererrgb.cpp:111` and the `m_isSlipRenderer` branch at the rectangle). A (type 19) loses that view. C and D do not fit a half-height slip view: C's top half would show bass only. B is mirrored, so it works unchanged. If MixPi never turns slip on, this does not matter, but it should be stated.
4. **The bench is slightly uneven (`waveform-three-band-bench.cpp:79`, `:89`, `:120`).** A, B and D build three local `Out` arrays each frame with no `reserve`, then copy them. Today and C write into the reused buffer. Mixxx reserves its vertex arrays, so A, B and D are overstated a little, and C is favoured. The ranking does not change. `columns()` (`:39-57`) also takes all four maxima for every style, which Filtered does not need.
5. **Two numbers have no evidence file.** "116.0 vs 116.0 px" (`DIRECTIONS.md:14`) and "1.18 × filtered.all" (`DIRECTIONS.md:20`) are not in the evidence folder. Image 01 does look like a match by eye.
6. **A's Loop panel height is not given.** The Loop panel is not a main waveform, so under A it would draw Filtered at 2 × total_gain (with ReplayGain). No number says whether it clips.
7. **B is drawn from six band maxima, today's renderer keeps three.** `render_stack` (`waveform-three-band-sim.py:201-203`) uses low, mid and high per channel. `waveformrendererrgb.cpp:131-146` keeps one maximum per band across both channels. The picture is fair, and the bench already counts per-channel maxima, but the patch must add them.
8. **Small simulator differences, all under one pixel.** `column_maxima` does not round the first frame to the pixel grid as `waveformrendererrgb.cpp:96` does, and Python's `round` rounds halves to even where `std::lround` rounds away from zero (`waveform-three-band-sim.py:129-130`).

Otherwise the simulator follows the code. `render_filtered` matches the Filtered renderer: `getGains(&allGain, true, …)` gives the ×2, the bands are drawn low, mid, high as opaque bars, and the axis goes last. `render_rgb` matches the colour mix and the divide by the largest part. The type 24 claims hold: 4× `QOpenGLFramebufferObject`, `glBegin` and `glMatrixMode`, and the 0.53 mix. B, C and D are drawn with the same gain, colours and column maxima, with no smoothing that would favour one of them.

Spot checks of `DIRECTIONS.md` against the evidence, all correct:

| Claim | Evidence |
|---|---|
| CPU 20.8 / 20.4 / 46.1 / 21.2 µs, ×1.32 / 1.29 / 2.92 / 1.34 | Same in `41-cpu-bench-mac.txt` |
| 12.7 k vertices vs 4.3 k; 100 KB and 249 KB vs 83 KB | 12750 vs 4254; 99.6, 249.0, 83.1 |
| A typical column 0.32 vs today 0.52, "about 40 % shorter" | p50 0.32 and 0.52: 38 % |
| A stock: 19 % and 40 % at the edge | 18.73 and 40.26 |
| Fill ×1.27 / 2.19 / 0.67 / 0.43 | Same in `40-heights-on-library.txt` |
| Pi estimate 80–130 µs, 0.5–0.8 % of a core | 15.8 µs × 5–8 = 79–126 µs; × 2 decks × 30 fps = 0.47–0.76 % |

## 2. Scores

| | K1 separation (3) | K2 mixing cues (3) | K3 size (2) | K4 fit (1) | K5 cost (1) | Weighted |
|---|---|---|---|---|---|---|
| Today | 3 | 7 | 8 | 3 | 10 | 5.9 |
| A Overlay | 7 | 6 | 3 | 9 | 7 | 6.1 |
| B Stack | 8 | 7 | 8 | 7 | 7 | 7.5 |
| C Split | 8 | 8 | 5 | 5 | 5 | 6.8 |
| D Lanes | 9 | 5 | 3 | 4 | 7 | 5.9 |

**Today**
- K1 3: one colour per column; the casebook (C-0004) records the owner's view that it "does not separate the bands".
- K2 7: the outline is big and the drop in scene 2 shows as a wall of red, but the bass entry is a hue change, not a shape.
- K3 8: "today/B outline 0.52 … 0.79 … 0.00".
- K4 3: stock #ff0000 / #00ff00 / #0000ff next to the muted tokens.
- K5 10: nothing to build.

**A Overlay**
- K1 7: three clear colours, but the highs are drawn last and hide the bass under them; in scene 1, deck 1 has a white core with the blue showing only where the bass is taller.
- K2 6: the drop in scene 2 is clear (blue jumps out past the white), but the quiet deck 2 in scene 1 is a thin strip about 20 px tall.
- K3 3: "A outer (bands x0.80) 0.32", under a third of the space, against the owner's "quite compressed … especially the bass" (C-0001).
- K4 9: it is the rekordbox three-band look in token colours.
- K5 7: about 10 lines, but config with a side effect (the Loop panel changes, and the slip view goes).

**B Stack**
- K1 8: all three bands show in every column and none can hide another; but the thicknesses are shares of the outline, so the blue gets thinner when the highs rise even if the bass has not changed.
- K2 7: the outline is today's, so drops and breakdowns read as now; in scene 2 the blue core appears at the drop; single kicks in a dense passage are no clearer than today.
- K3 8: "Identical to J15": p50 0.52, p99 0.79, none at the edge, and the bass is a thick core on both the loud and the quiet deck.
- K4 7: token colours and a familiar mirrored shape; the bass colour is deck 1's blue and the mid colour is deck 2's orange, so deck 2's row is mostly blue beside an orange "2".
- K5 7: "~120 lines + skin", ×1.29 CPU, fill ×2.19 in painter's order.

**C Split**
- K1 8: the bass has a half to itself and shows its real level; below the axis mids and highs still overlap, the smaller in front.
- K2 8: the best kick display of the four; deck 2 in scene 1 shows each kick as a blue sawtooth, and the bass entry in scene 2 is a step.
- K3 5: "C top: low 0.27", "C bottom: max(mid,high) 0.21"; each half is under a third full on a typical track.
- K4 5: muted, but lopsided and unlike any CDJ or rekordbox view.
- K5 5: "46.1 µs, ×2.92" as benched, 249 KB per frame, and it does not fit the slip half view.

**D Lanes**
- K1 9: each band on its own floor, nothing hidden.
- K2 5: 41 px lanes; on deck 2 the mid lane is a line a few pixels high, and the overall shape of the track is gone.
- K3 3: "median 0.15–0.27" of a 41 px lane, which is 6 to 11 px.
- K4 4: reads as a spectrum analyser, not a waveform.
- K5 7: about 120 lines, ×1.34, the lowest fill (×0.43).

## 3. Pairwise

- **A–B: B.** B keeps J15's height (0.52 against 0.32) and never hides a band. A's only clear win is that it needs almost no code.
- **A–C: C.** C shows the bass at its real level in every column and kicks far better. A looks more familiar, but its highs cover the bass.
- **A–D: A.** Both draw small, but A keeps one readable track shape and D breaks it into three thin strips.
- **B–C: B.** C reads kicks better, but B keeps the size the owner asked for twice, the mirrored shape, the slip view and a third of C's benched cost. This is the closest pair.
- **B–D: B.** D separates the bands more honestly, but at 41 px per lane it gives up the size and the track outline.
- **C–D: C.** C gives the bass 64 px where D gives it 41, and keeps a single shape per deck.

## 4. Against today

- A: **worse** on size, better on colour and separation; overall about the same (6.1 against 5.9), and it goes against C-0001.
- B: **better**. Same outline and height, the bands now separate, and the colours are muted.
- C: **better** for bass and kicks, worse on size and familiarity.
- D: **same** overall: better separation, worse for everything else.

## 5. Ranking, risk and build

1. **B Stack** (7.5)
2. **C Split** (6.8)
3. **A Overlay** (6.1)
4. **D Lanes** (5.9)

**Main build risk of B.** The cost is small and I expect no frame-rate problem, but it is unmeasured on the card: three times the vertices (12.7 k per deck) go through Mesa's client-array path on V3D each frame. That must be timed on the Pi before it ships. The second risk is honesty of the picture: the bands are shares of the `filtered.all` outline, not levels, and the stored values are already compressed (`pow(x, 0.632)`). The owner should know that a thinner blue core can mean "more highs", not "less bass". If kicks turn out too soft in use, C's bass-on-top idea is the fallback.

**How I would build B.**

- `src/waveform/renderers/allshader/waveformrendererrgb.h` and `.cpp`: add a `mixxx::UnicolorShader` and three `VertexData` members (as `WaveformRendererFiltered` has). In `paintGL`, branch on `m_waveformRenderer->isMixpiMainWaveform()`, which the J13 patch already provides. Every other viewer, including the Loop panel, takes the stock path.
- In the column loop, keep low, mid and high maxima per channel (six, not three) beside the two `filtered.all` maxima. Apply the EQ gains and the `sqrt(sumGained / sum)` factor exactly as lines 156–177 do, so EQ kills still shrink the outline.
- Per channel: outer = heightFactor × all; then edges at outer × (low + mid) / sum and outer × low / sum. Add one rectangle per layer: highs to the outer edge, mids, then lows. Keep the slip branch (bottom edge at `halfBreadth`).
- Draw three `glDrawArrays` calls with uniform colours from `m_rgbHighColor`, `m_rgbMidColor`, `m_rgbLowColor`, then the axis, as Filtered does at lines 179–186. Painter's order is fine on V3D (fill ×2.19 of 46 k px).
- Put the edge maths in a small header beside `mixpiwaveformgain.h` so a test can check it, as `tests/test_waveform_height.py` does for J13.
- Skin: `SignalRGBLowColor`, `SignalRGBMidColor`, `SignalRGBHighColor` on the `MixpiWaveRow` viewers only.
- Size: about 110–140 lines of patch, about 6 lines of skin, plus the test.

For the climb I would also try a bass colour that is not deck 1's blue, or accept the clash knowingly.

My top pick is **B Stack**.

Score: 8/10.
