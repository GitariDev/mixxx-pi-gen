# Wave J9, builder N-J9 (skin and native): the Zoom row in Settings › Interface

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 0, 1, s2, s12, 2a and **2f** (the owner's words for this wave), the mockups `m-settings-interface.png` and `m-loop.png`, and the card's Interface page as built: `deploy/ui-redesign-20261117/acceptance-I/shots/c7-f-interface.png` (untracked, in the main checkout).

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at `a856b48` (65 patches; the last is `mixxx-rekordbox-utf16-text.patch`). You are the only builder running. Never edit an existing Mixxx patch. If Mixxx needs a change, make `mixxx-zoom-setting.patch`, placed last in `MIXXX_PATCHES`, with the prerequisites it needs.

## What to build (spec 2f)
- **Settings › Interface gets a new last row, after CPU readout: "Zoom", then a + button, then a − button,** in that order. No subtext and no level readout. The buttons are 48 px tall, styled like the page's other neutral buttons (build B's font, role colours from `design/tokens.css`).
- **One tap changes the zoom of both decks' main waveforms on the Decks page** (the two big waveforms just below the top bar) by one step, the same step as the Loop panel's − and +. + zooms in; − zooms out. They stop at the same ends as the Loop panel's buttons.
- **Saved like every setting:** within a second of a change, kept over `kill -9`, a power cut and a restart. After a restart, both decks start at the saved zoom.
- **Keep:** the Loop panel's − and + (on the focused deck's waveform) work as today. If they change a deck's zoom, say in your report how that interacts with the saved setting (for example whether the setting stores the last zoom from either place). Choose the least surprising option, list it under "Assumptions", and change nothing on the Loop panel.
- **Find first and write in your report:** how Mixxx 2.5.6 holds the zoom today (`[ChannelN],waveform_zoom`, `[Waveform] DefaultZoom` and `ZoomSynchronization` in `stage3/02-desktop/files/mixxx.cfg`), what the Loop panel's buttons drive (`mixpi-performance.py` ~:1255), and whether the stock config can do this with no Mixxx patch. Prefer the smallest change; a Mixxx patch only if the skin and config cannot do it.
- **Fit:** the page is 800×480. If a sixth row does not fit without scrolling or squeezing the other rows below 48 px, stop that part and report the nearest faithful option; do not choose another layout.

## Files you own
- `stage3/01-install-packages/files/mixpi-performance.py` (the Interface rows only, plus a zoom helper if needed);
- `stage3/02-desktop/files/mixxx.cfg` (the `[Waveform]` zoom keys only), if needed;
- the new patch, if needed, and in the Mixxx source only what it needs (for example `src/util/mixpidisplaycontrols.h`, `src/coreservices.{h,cpp}`, the waveform widget's zoom code), plus new files;
- `tests/test_performance_skin.py` (new tests only), new `tests/test_zoom_setting.py` and `tests/native/zoom_setting_*`.

No other skin pages and no stylesheets except where the new buttons need a rule you cannot avoid (say why). Do not edit the registries; give the orchestrator your registration lines (and the stylesheet note if any).

## Checks
- **Skin tests:** the row's order, copy ("Zoom", "+", "−"), sizes and roles; the Loop panel's − and + unchanged byte for byte.
- **Native fixture (if you make a patch) or a config/skin fixture:** + and − change both decks' zoom by one step, stop at the ends, save within 1 s, and come back after a restart. Show it failing without your change.
- A render of the Interface page at 800×480 (offscreen Qt on VM b, or the skin tools you have) next to `c7-f-interface.png`: the first five rows are unchanged.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (`test_chroot_runtime`'s 5 s timeout can trip under load; rerun it alone). Run it in a clean worktree: untracked `.claude/` folders must not reach the VM.
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ9-nj9-20261121 <your worktree> gate`;
  - never use `limactl`. Keep at least 24 GB free in the VM, and run `fstrim` after cleanup.
- **Never touch the Raspberry Pi or any drive.**
- Give the orchestrator a Pi check with coordinates: Settings (gear) › INTERFACE › Zoom + and −, then the Decks page, then a clean restart.

## Amendment 1 (2026-11-21, after the owner saw the render): read spec 2f again, all of it
The owner accepted the row and the 65 px rows, and asked for four more things, all in this wave:
1. **Top bar shown (800×444):** the Interface rows get shorter (about 57 px) so all six fit; buttons stay 48 px. Only in that mode; the other Settings pages are unchanged.
2. **A % readout** right of the buttons, like Brightness's: `Zoom [+] [−] 100%`. % = 3 ÷ zoom × 100, rounded (300, 150, 100, 75, 60, 50, 43, 38, 33, 30). It always shows the saved setting.
3. **Starlight:** SHIFT held + the headphone volume knob sets the saved zoom from the knob's position (fully left 30%, fully right 300%, the ten steps). While SHIFT is held the knob must not change the headphone volume, and releasing SHIFT must not make the volume jump (use soft takeover or the mapping's own pattern). Find the stock mapping (`res/controllers/Hercules DJControl Starlight.midi.xml` and `Hercules-DJControl-Starlight-scripts.js` in the pinned Mixxx source), see what SHIFT + that knob does today, and report it. Change the mapping with a new patch (or the same J9 patch if cleaner; say which). It must not change any other control on the Starlight.
4. **The indicator:** on the Decks page, a small pill "ZOOM 150%" over the left (already played) part of the main waveforms, centred on the line between Deck 1's and Deck 2's waveforms, never over the playhead. It shows while the saved zoom changes (Starlight, or the Zoom row when the Decks page is in view) and hides 1 s after the last change. Neutral surface (`--mx-surface-2`, `--mx-line-strong` border), build B's font, text 13 px or more, no animation beyond show and hide. The Loop panel's − and + do not show it.

Also, keep the files you own, plus: the Starlight mapping files in the Mixxx source (only through a new patch), and the Decks page's waveform area in `mixpi-performance.py` for the pill. Add fixtures for 1-4 (each failing without the change), renders at 800×480 and 800×444 of the Interface page and of the Decks page with the pill showing, and run the Mac suite and the full native gate again (`uiJ9b-nj9-20261121`). Give updated registration lines and the Pi checks (the owner's hands are needed for the Starlight check; say so).
