# Wave C2, builder N-C (native controls, saving, backlight)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first. It is part of this brief.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` after the wave C1 integration. The skin builder (S2) draws the screens this wave and binds to the control names below, so keep them exactly.

## Your items

References are to `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` ("spec"); plan `docs/ideas/UI-REDESIGN-PLAN-20261117.md` R-13, R-17 and section 12.

1. **U-7, effects saved within a second of a change** (spec s8 "Saving effects"; owner: "we can save the FX loaded and chosen for a future sessions, like how we save settings - means the FX are there after a restart or shutdown").
   - Stock Mixxx writes the effects state (the loaded effects per unit and slot, and what it saves with them) only at a clean quit. Save the same state **within one second of any change**, so it survives `kill -9` and a power cut. Write atomically (temporary file, then rename), as R-13 does for `mixxx.cfg`.
   - Measure it in a native fixture: change a loaded effect, and the file on disk has it in under 1 s; a process killed after that keeps it at the next load.
   - Depth and mix still reset at start because of the Starlight's stock script. Do not change that (spec s8).
   - Ten effect changes while audio runs must not cause underruns: keep the write off the audio thread, and coalesce bursts.
2. **U-5, the Clear samples controls** (spec s6; the skin draws the popover in `mockups/m-sampler-clear.png`):
   - `[MixPi],sampler_clear_open` (0/1): the popover is open. Writing 1 clears every tick.
   - `[MixPi],sampler_clear_tick1` … `[MixPi],sampler_clear_tick8` (0/1).
   - `[MixPi],sampler_clear_count` (read-only, 0-8): the number of ticked pads that hold a sample.
   - `[MixPi],sampler_clear` (write 1): empty every ticked pad that holds a sample, clear the ticks, set `sampler_clear_open` to 0. The sampler bank is then saved by R-13's save on change. For a pad that is playing, do what build B's per-pad × CLEAR did, and say what that is in your report.
   - "The pads go empty. The files stay where they are": never delete or move a sample file.
3. **U-9, brightness, Night dim and CPU readout** (spec s12; `mockups/m-settings-interface.png`; plan 12.2 U-9):
   - `[MixPi],backlight`: a potmeter 5-100 (%), so a skin slider drives it. Saved in `mixxx.cfg` and applied at start. With no saved value, start from the panel's current level. On change, write `round(value × max_brightness / 100)` to the first `/sys/class/backlight/*/brightness` (the test card has `10-0045`, max 255). Let tests point it at a fake folder through an environment variable.
   - `[MixPi],backlight_available` (read-only): 1 when that file is writable, else 0 (the skin then shows the slider off).
   - `[MixPi],night_dim` (0/1), saved. While 1, the panel is at the night level, **10 % of max**, without changing `[MixPi],backlight`. Back to `[MixPi],backlight` when 0. The orchestrator reports 10 % to the owner, who may tune it, so keep it as one named constant.
   - `[MixPi],show_cpu` (0/1, default 1), saved. Only the skin reads it.
   - **Write access** (a new system file): a udev rule, for example `stage3/02-desktop/files/udev/99-mixpi-backlight.rules`, that gives the `video` group write access to `/sys/class/backlight/*/brightness` when the device appears (`pi` is in `video`, see `stage2/01-sys-tweaks/01-run.sh`), plus its install line in the right `stage3/02-desktop/0*-run.sh`. Nothing else in the system changes. Add a test that the rule is installed and grants only that file.
4. **Empty effect selector** (spec s8: "Select effect…" when empty, drawn dim): set a dynamic property `mixpiEmpty` (true when the slot has no effect) on the effect selector widget, and re-polish it when that changes, so a stylesheet rule can dim it. S2 writes the rule.
5. **"Every change saves within a second"** (the Settings header copy, spec s11). Builder N-B measured 1395 ms from a change to `mixxx.cfg` on disk, because the save waits for one quiet second. Make a single change reach the disk in under one second end to end, in a new patch, without more writes during a burst of changes. Measure it in a fixture.

## Files you own

New patches (for example `mixxx-effects-save.patch` and `mixxx-agreed-controls.patch`), the new udev rule and its install line in one `stage3/02-desktop/0*-run.sh`, new tests (`tests/test_effects_save.py`, `tests/test_agreed_controls.py`, `tests/native/effects_save_*`, `tests/native/agreed_controls_*`, or similar).

Mixxx source files you may patch: `src/effects/*` (the save path), `src/widget/weffectselector.{h,cpp}`, `src/coreservices.{h,cpp}`, `src/widget/mixpiperformancesettings.h`, `src/preferences/configobject.{h,cpp}`, `src/mixer/samplerbank.{h,cpp}`, `src/mixer/playermanager.{h,cpp}`, and new files. Not the library, the sidebar, `rekordboxfeature.*` or the media files (another builder), and no skin file (S2).

## Checks

- Native fixtures: effects on disk within 1 s and kept after a kill; no write storm during a burst; the four clear controls (open clears ticks, count follows ticks and loaded pads, clear empties exactly the ticked loaded pads, sample files untouched); backlight write and scaling against a fake sysfs folder; `backlight_available` 0 for a read-only file; night dim on and off; saved values read back at start; `show_cpu` default 1; `mixpiEmpty` follows the slot; a settings change on disk in under 1 s.
- Mac suite green; full native gate green on VM `b` with your registration lines applied locally, 0 skips.
- Pi checks for the orchestrator: the effects save-within-a-second test with `kill -9`, the samples full-shutdown test, brightness and Night dim on the card's panel (`/sys/class/backlight/10-0045`).
