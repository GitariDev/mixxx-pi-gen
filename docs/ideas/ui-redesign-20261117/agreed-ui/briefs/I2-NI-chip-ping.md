# Wave I2, builder N-I2 (native): USB chip IN USE timing and the ping on the Media page

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 1, s13 (Media page), the "Plugging in a drive" row in Settings, and **2d**, plan 12.9 and R-3 to R-6 (media model, chip, handover, eject). Look at the mockups `m-media.png`, `m-tracks.png` and `m-sources-sub.png`, where the chip reads READY.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Build H (56 patches) is on the test card. Never edit an existing Mixxx patch. Make `mixxx-media-chip-ping.patch` after the last one in `MIXXX_PATCHES` (the orchestrator orders it after N-I1's patch). Give it the prerequisites it needs.

## The owner's decision (spec 2d)
1. **IN USE timing.**
   - A drive reads **IN USE** (`[MixPi],media_state` 2, on the top-bar chip and on its Media page row and filter) only once a track or sample from it is **loaded on a deck or a sampler pad**. This is the eject rule's "loaded means in use".
   - OPEN or BROWSE alone, or browsing its lists, leaves it at **READY**.
   - When the last loaded item from it is ejected or replaced, it goes back to READY.
   - Today it reads IN USE as soon as the drive is opened (plan line 264, `Library::openRemovableSourceAsync`). The owner has now chosen the later trigger.
   - EJECTING, SAFE TO REMOVE and the scan % stay as they are.
2. **The plug-in ping while the Media page is open.**
   - With "Plugging in a drive" set to ASK, plugging a drive in shows the bottom ping (LOAD and DISMISS) even while the Media page is open, as it does on every other screen. Today it is suppressed there.
   - With AUTO LOAD, nothing changes.
   - The ping must sit where it sits on other screens and stay usable over the Media page. Check that the page's own row also appears.

Find the code first and write the cause in your report. The chip state and inventory are in `src/library/mixpimedia.h` and the media patches (`mixxx-media-*.patch`). The handover and loaded-track tracking are in the patch that implements "loaded means in use".

## Files you own
- the new patch;
- `tests/test_media_agreed.py`, `tests/native/media_*`, and new tests;
- in the Mixxx source, `src/library/mixpimedia.h`, the media page and ping widgets the media patches add, `src/library/library.{h,cpp}` only for the open path, and the player-manager hook if loaded-from-drive tracking needs it.

No skin files and no stylesheets. Do not touch `src/library/rekordbox/*`, which belongs to N-I1. Do not edit the registries; give the orchestrator your registration lines.

## Checks
- **Native fixtures:**
  - open a fake drive: READY;
  - load a track from it to a deck: IN USE;
  - eject that deck's track (or load one from This Pi over it): READY;
  - load a sample from the drive to a pad: IN USE;
  - clear the pad: READY;
  - two drives tracked independently;
  - the ping shows with the Media page open (ASK), and not with AUTO LOAD.
  - Show the fixture failing without your patch.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiI2-ni2-20261120 <your worktree> gate`;
  - never use `limactl`.
  - Temp tree `/tmp/i2-ni2-src`.
- Never touch the Raspberry Pi.
- Give the orchestrator Pi checks with coordinates, using GANDER1 (read only; clean ejects and re-plugs by port toggle are allowed).
