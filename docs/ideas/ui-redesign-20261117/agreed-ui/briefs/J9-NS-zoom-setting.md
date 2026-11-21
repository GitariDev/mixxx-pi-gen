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
