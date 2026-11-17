# Wave C2, builder S2 (skin)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first. It is part of this brief.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` after the wave C1 integration (S1 skin, N-A Sources menu, N-B Media page, registration). The card preview of the C1 skin on build B's native is in `deploy/ui-redesign-20261117/waveC/c1-preview/p*.png`.

## Your items

References are to `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` ("spec") and `mockups/`.

1. **Fixes from the C1 card preview** (each is a deviation from a mockup):
   - **Deck row** (spec s6 "Deck row, on every screen"; `m-loop.png`, `m-fx.png`, `m-sampler.png`). On the card, with tracks loaded, the row shows only the deck badge, centred in its half, with the title (FX, Sampler) or nothing at all (tool panel open, `c1-preview/p08-loop-loaded.png`), and never the artist. Drawn: badge at the left, then the title, then the artist dimmer and right after it, and SYNC/MASTER pills at the right end. The artist is shortened with "…" first, then the title. Make it render that way in the real skin, on Decks, with the tool panel open, on FX and on Sampler. A throwaway program is not enough: the tracks' artist must show on the card.
   - **Settings rail** (`m-settings-media.png`): labels left-aligned as drawn, not centred.
   - **Settings › Media, Eject** (`m-settings-media.png`): drawn as the ON/OFF toggle (label plus knob), "Safe eject on this card". It stays an **indicator that cannot be pressed**: the eject gate must not open by a setting or a skin change (rubric criterion 4).
   - **FX effect selector** (`m-fx.png`): the ▾ sits inside the field, as drawn, not in a separate dark box. "SELECT EFFECT…" is dim when no effect is loaded: builder N-C adds a native dynamic property `mixpiEmpty` (true when the slot has no effect) on the effect selector; you add the rule that dims its text.
   - The open effect list uses the token colours, like every other list (S1 left build B's brighter colours because `tests/native/effect_selector_test.cpp` checks them: you own that test now, so update its expected colours).
   - Menu and dialog ticks follow spec section 1 (the tick on the accent, as in `m-sampler-clear.png`), including the Arrange columns dialog. You own `tests/native/library_interface_test.cpp`, which checks build B's white-on-blue tick: update it.
   - `tests/test_sample_browser.py` checks the literal `('SAMPLES', 1), ('THIS PI', 2), ('RECORDINGS', 4)` in the generator: drop that check, and remove the comment S1 kept for it.
2. **U-4 skin side, the Sources side menu** (spec s5; `m-sources-top.png`, `m-sources-sub.png`, `m-sources-edit.png`). Follow builder N-A's handover note, quoted at the end of this brief. Header while Sources is open: search, ✎, then ☰ turned into the red ✕ in the same spot. The table narrows to x 0-480 and keeps its scroll bar. The menu sits at x 480-800, y 100-480 over deck 2's half of the strip and the load row. Remove the old Sources screen's title, hint, EDIT LIST button and full-screen body.
3. **U-5 skin, Sampler** (spec s6; `m-sampler.png`, `m-sampler-clear.png`):
   - Header: **+ LOAD SAMPLE** (Confirm), **CLEAR SAMPLES…** (Danger), then the hint "Starlight SAMPLER mode: deck A pads 1-4 · deck B pads 5-8".
   - Pads A1-A4 (deck 1 badge) and B1-B4 (deck 2 badge). A loaded pad shows its number, label, duration and name, and two buttons: **▶ TRIGGER** (Sound, lit while it plays) and **■ STOP** (Caution). The per-pad × CLEAR goes (CLEAR SAMPLES… replaces it). Empty pad: "+ Empty · tap to load".
   - **CLEAR SAMPLES…** opens the popover drawn in `m-sampler-clear.png`: title "CLEAR SAMPLES" with the close ✕ at the right; one row per loaded pad with tick, badge, pad label, name and duration (ticked rows: tick plus `--mx-surface-2`, no left edge); the note "The pads go empty. The files stay where they are."; **CANCEL** (Navigate) and **CLEAR (n)** (Danger), n = ticked pads. The rest of the screen is dimmed behind it, as drawn. Bind to the controls builder N-C makes:
     - `[MixPi],sampler_clear_open` (0/1): the popover is open. Writing 1 clears every tick.
     - `[MixPi],sampler_clear_tick1` … `tick8` (0/1).
     - `[MixPi],sampler_clear_count` (read-only, 0-8): ticked pads that are loaded.
     - `[MixPi],sampler_clear` (write 1): clears the ticked pads, clears the ticks, and sets `sampler_clear_open` to 0.
     - CLEAR (n) is not enabled at n = 0.
4. **U-8 Settings row** (spec s11; `m-settings-media.png`): "Plugging in a drive", subtext "What happens when a drive goes in", choices **ASK** / **AUTO LOAD** bound to `[MixPi],drive_insert` (0 = ASK, 1 = AUTO LOAD; builder N-B made it in C1), then the note line "ASK shows a small strip with LOAD and DISMISS. AUTO LOAD opens the drive at once." drawn as in the mockup.
5. **U-9 Settings › Interface rows** (spec s12; `m-settings-interface.png`): Desktop bar (the button "SHOW TOP BAR"; keep build B's other states), Deck time (ELAPSED / REMAINING), **Brightness** (sub "Screen backlight"; a slider bound to `[MixPi],backlight`, a potmeter 5-100, enabled by `[MixPi],backlight_available`, with the "80%" style readout), **Night dim** (sub "Drops the screen to a low level for dark rooms"; OFF / ON bound to `[MixPi],night_dim`), **CPU readout** (sub "The CPU % at the top right"; SHOW / HIDE bound to `[MixPi],show_cpu`). The top bar's CPU box shows only while `[MixPi],show_cpu` is 1. N-C makes these controls this wave.
6. **Dead styles:** remove the old Sources (`#MixpiSource*`) and Media (`#MixpiPage…`, `#MixpiMedia*`, `#MixpiEject*`, `#MixpiBottomStrip`) sections from `pioneered-menus.qss`, now replaced by `mixpi-sources-menu.qss` and `mixpi-media-page.qss`. Update the tests that read those sections.

## Files you own

GEN `mixpi-performance.py`, QSS-P `mixpi-performance.qss`, PT-PY `pioneered-touch.py` (not its stylesheet tuple, which is a registry), QSS-T `pioneered-touch.qss`, QSS-M `pioneered-menus.qss`; `tests/test_performance_skin.py`, `tests/test_pioneered_touch.py`, `tests/test_touch_dialog_styles.py`, `tests/test_library_interface.py`, `tests/test_sample_browser.py`, `tests/native/effect_selector_test.cpp`, `tests/native/library_interface_test.cpp`, `tests/native/library_interface_runner.py`. No Mixxx source. Not `mixpi-sources-menu.qss` (N-A) or `mixpi-media-page.qss` (N-B).

## Checks

Generated-XML and QSS tests for each item, the 48 px minimum, page sizes summing to 800×480, the Mac suite, and the full native gate once at the end. Give the hit map of every control you add or move, including the popover's rows, CANCEL, CLEAR (n) and ✕, and the new Settings rows.

## Builder N-A's skin handover note (wave C1, verbatim)

- Put `SidebarWrapper` (`LibrarySidebar` with `TouchNavigation`, inside `#LibraryWrapper`) as a 320×380 overlay at x 480–800, y 100–480, shown while `[MixPi],screen` is 1. It must cover deck 2's half of the strip and the load row, so it has to sit above those containers. The existing `right-overlay` layout can carry it: the base is everything below the Tracks header, the second child is the wrapper (`320f`).
- Waveforms are native GL windows, so a widget cannot cover them. While screen is 1, hide deck 2's waveform and keep deck 1's.
- While `[Library],sidebar_sources_editing` is 1 (the full-screen edit list is open), hide the whole waveform row. Keep screen at 1 and keep `SidebarWrapper` shown during editing: hiding it ends editing.
- Narrow the table to x 0–480 while screen is 1, for example with a 320 px spacer shown only then, so its scroll bar sits at x ≈ 456–480.
- Keep the header showing search, ✎ and the ☰ that turns into a red ✕ (that styling is S1's). Change `TRACKS_MODE`/`LOAD_MODE` and the table's "screen ≠ 1" condition so the header, crumb and table stay visible on screen 1.
- Remove: the `MixpiSourcesHead` title and hints, the `LibrarySourcesButton` EDIT LIST/DONE button (the native EDIT replaces it), and the full-screen `MixpiSourcesBody`.
- Keep `MixpiSampleCloses`, so the ✕ returns to Load sample.
- The skin needs no Back or EDIT controls. The menu writes `[MixPi],screen` 0 and `[Sidebar],sidebar_visible` 0 when it closes.
