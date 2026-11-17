# Wave C1, builder S1 (skin)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first. It is part of this brief.

**No design of your own; where the spec is silent, build B stays.**

## Your items

All references are to `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` ("spec") and its `mockups/`.

1. **U-1, the rules for every screen** (spec section 1, all of it, and "Roles and colours"), for every skin screen and for the general dialog and menu rules:
   - Every control gets its one role (Navigate, Choose, Confirm, Sound, Caution, Danger) with the token colours in `design/tokens.css` and nothing brighter.
   - 3 px radius on buttons, segments, fields and panels; 2 px on slider thumbs; pills (radius 999) on chips that cannot be pressed: SYNC and MASTER chips, drive-state chips, the USB chip's scan %.
   - Lit or chosen state: a see-through tint of the role colour at 26% (`--mx-lit-alpha`) over what is behind it, a 2 px border in the role colour (Qt: a 2 px border is fine), and the light role text colour. Never a flat solid fill.
   - The close control: 48×48 native, `--mx-surface-2` background, red ✕ in #ec7f74 drawn as two strokes, **no outline at rest**, pressed `--mx-danger-surface` with a `--mx-danger` border. **At the right end of its header** on every skin screen that has one: the tool panel (replaces "× CLOSE"), Settings (today on the left), Load sample, Choose pad (today CANCEL), and the ✕ that ☰ becomes while Sources is open.
   - Ticked rows: tick plus `--mx-surface-2`, no left edge. Current menu row (no tick): `--mx-surface-2`, a 4 px accent edge on the left, semibold.
   - Fonts: labels and buttons Ubuntu Condensed uppercase; body and list text Open Sans; numbers Ubuntu Mono. Use only fonts already on the image; if one is missing, say so and do not add it.
   - Scroll bars: every skin list longer than its space shows a 24 px bar at its right edge.
   - Files: `mixpi-performance.py` (GEN), `mixpi-performance.qss` (QSS-P), `pioneered-touch.py` (PT-PY), `pioneered-touch.qss` (QSS-T), and the **general** sections of `pioneered-menus.qss` (QSS-M: menus, the column arrangement dialog, other dialogs). **Do not edit the Sources section (`#MixpiSource*`) or the Media page section (`#MixpiPage`, `#MixpiMedia*`, `#MixpiEject*`, `#MixpiBottomStrip`) of QSS-M.** Two native builders replace those this wave in new files, and wave C2 deletes the old sections.
2. **U-2, the tool panel** (spec s2, `mockups/m-loop.png`): header deck badge, "DECK 1", LOOP / JUMP / CUES segments, close ✕ at the right end; loop sizes 1/32 … 64 in two rows of six (chosen size lit, Choose role); the ½ and ×2 row, each neutral with a green border (`color-mix(accent 60%, surface-2)`); EXIT LOOP (Danger) and RELOOP (Sound, info blue) on their own row. JUMP and CUES: no layout change, only the section 1 rules.
3. **U-3, Tracks** (spec s3, `mockups/m-tracks.png`): header left to right: search (fills the space), ✎ actions, ☰ Sources at the right end. Bottom row for each deck: LOAD n · track name · CUE · ▶, with ▶ back, right of CUE, on both decks.
   - The ☰ and its ✕ state are shared with the Sources screen (screen 1). Put ☰/✕ at the right end of the header there too. **Do not rework the rest of the Sources screen** (its body, title, hint and the EDIT LIST button). Builder N-A replaces the native Sources this wave, and wave C2 does the skin side of it.
4. **U-6 skin, Load sample** (spec s7, `mockups/m-loadsample.png`): header "LOAD SAMPLE", the hint "Pick a sound, then a pad", search, close ✕ at the right; source buttons SAMPLES and SOURCES… only, then the hint "Or a list picked in Sources."; table Filename, BPM, Key, Duration; footer hint "Tap a sound, then load it to a pad." and LOAD TO PAD… (Confirm) at the right. If removing This Pi, USB and Recordings needs a native change, do not make it: report it.
5. **U-7 skin, FX** (spec s8, `mockups/m-fx.png`): the effect ON/OFF becomes a **button** (Sound, lit and reading ON when on, reading OFF at rest), not a switch. Slider fills (`--mx-slider-fill` #5d7238) run the **full height** of the track up to the handle, for Mix and every effect slider. Mode segments, Route segments, "EFFECT n" with "deck A FX pad n", and the selector ("SELECT EFFECT…" when empty) as drawn.
6. **Deck row, on every screen** (spec s6 "Deck row"; `m-loop.png`, `m-sampler.png`, `m-fx.png`): title and artist side by side, the artist dimmer and after the title. When SYNC or MASTER chips show, the artist is shortened with "…" first, then the title.
7. **Settings header** (spec s11 and s12 headers, `m-settings-media.png`): "SETTINGS", the hint "Every change saves within a second.", close ✕ at the right. **Not the rows**: the new Media and Interface rows are wave C2.

Not yours this wave: the Sources screen body and EDIT LIST (N-A, then C2), the Sampler pads and Clear samples popover (C2), the Settings rows for drive insert, brightness, Night dim and CPU readout (C2), the Media page (N-B).

## Files you own

GEN, QSS-P, PT-PY, QSS-T, QSS-M (general sections only), `tests/test_performance_skin.py`, `tests/test_pioneered_touch.py`, `tests/test_touch_dialog_styles.py`, `tests/test_library_interface.py`, and new skin icon files written by GEN. No Mixxx source files.

The stylesheet list in PT-PY (`("pioneered-menus.qss", "pioneered-touch.qss")`) is a registry: do not commit changes to that line.

## Checks

- Generated-XML and QSS tests for each item: order and labels of the header controls, the roles' colours and radius, close ✕ at the right end of each header, ½ and ×2 borders, EXIT LOOP and RELOOP row, ▶ beside CUE on both decks, the two Load sample source buttons, the ON/OFF button, full-height fills, deck-row title and artist, the 48 px minimum, and that each page's fixed sizes still sum to 800×480.
- Mac suite green. You patch no Mixxx source, so the native gate only needs to stay green: run it once at the end.
- Give the hit map for every control you moved (800×480 coordinates), so the orchestrator can preview your skin on the card and compare each screen with its mockup.
