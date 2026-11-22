# Wave J15, builder N-J15 (native): the main waveforms at 0.80

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` **2h** (with the owner's notes after build M), plan 12.16, and the J13 brief `J13-NJ-waveform-height.md` with its patch `mixxx-waveform-height.patch`, tests `tests/test_waveform_height.py`, `tests/native/waveform_height_*` and script `tools/performance/waveform-height.py`.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (70 patches; the last is `mixxx-waveform-height.patch`; J14's stylesheet line is in). You are the only builder running. Never edit an existing Mixxx patch. Make `mixxx-waveform-height-gain.patch`, placed last, with prerequisite `mixxx-waveform-height.patch`.

## What to build (owner: "Let's set the gain to around .80")
- The decks' main waveforms (the `MixpiWaveRow` ones J13 picks out) draw at **0.80 ×** J13's height: `pregain × VisualGain_0 × 0.80`. One named constant, e.g. `kMainWaveformGain = 0.80`, in J13's `mixpiwaveformgain.h`.
- Unchanged: the Loop panel's waveform and the overview strips (still `total_gain`), the colours, the pregain knob's effect, the sound.
- J13's tests may assert the old formula: update them through your own new tests or by adjusting J13's test files where they check the formula (you own `tests/test_waveform_height.py` and `tests/native/waveform_height_*` for this; keep every other J13 check).
- **Re-run the measurement** on the owner's data (`deploy/ui-redesign-20261117/owner-waveform-data-20261122/wfdata/`, untracked, private: Mac only, never commit or send) with the script, at 0.80, and also at 0.90 for comparison. Report for each: a typical track's median / 90th / 99th percentile height, and the loudest-mastered quarter's and the quietest quarter's 99th percentile and share of columns at the edge. Put the tables in `deploy/ui-redesign-20261117/wave-J15/` (untracked), and redraw J13's simulation for 0.80 there (labelled as a simulation).

## Files you own
- the new patch, and in the Mixxx source only `src/waveform/mixpiwaveformgain.h` (and new files);
- `tests/test_waveform_height.py`, `tests/native/waveform_height_*`, new `tests/test_waveform_height_gain.py` if cleaner, and `tools/performance/waveform-height.py` (a gain argument, if needed).

Do not edit the registries; give registration lines (if `test_waveform_height.py` checks that its patch is last, give the change).

## Checks
- Fixture: the main waveform's height is `pregain × VisualGain_0 × 0.80 × level`; the Loop panel's still `total_gain`; failing without your patch.
- The Mac suite in a clean worktree: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (rerun `test_chroot_runtime` alone if its 5 s timeout trips).
- The full native gate on VM `b`, 0 skips: `~/.config/mixpi-lima-b/vm-native.sh uiJ15-nj15-20261122 <your worktree> gate`. **A pi-gen build (build N) may be running in VM b:** before you start the gate, check (`ssh -F ~/.config/mixpi-lima-b/ssh.config lima-b-durable 'pgrep -af "[b]uild.sh|[n]inja|[c]make --build|[c]test"'`) and wait with a Monitor until-loop until nothing runs. Never use `limactl`. Keep at least 24 GB free in the VM, fstrim after cleanup, and the Mac above 20 GiB.
- **Never touch the Raspberry Pi or any drive.** Open no window or app on the Mac.
- Give the orchestrator the Pi check (the loud and quiet tracks of acceptance M on decks 1 and 2).
