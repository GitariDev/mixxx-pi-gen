# Wave J13, builder N-J13 (native and config): bigger main waveforms

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` sections 0, 1 and **2h** (the owner's words for this wave), and the J9 brief `J9-NS-zoom-setting.md` (the waveform zoom work, for the files around it).

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names (68 patches; the last is `mixxx-removable-rows-fix.patch`). Another builder (J12, OPEN remount) works at the same time in its own worktree, on other files. Never edit an existing Mixxx patch. If Mixxx needs a change, make `mixxx-waveform-height.patch`, placed last, with the prerequisites it needs. The orchestrator settles the final order of J12 and J13; give your lines assuming yours is last.

## The owner's words (spec 2h)
"The main waveform window on decks seems to be quite compressed you don't see the waveforms get very big especially the bass. Could you see if there is some scaling being done and if so can we increase it. Ideally very loud tracks would end up getting ever so slightly clipped."

## What the orchestrator found (check it)
- The card draws the main waveforms with `[Waveform] WaveformType 17` (all-shader RGB, `src/waveform/renderers/allshader/waveformrendererrgb.cpp`). The image's `stage3/02-desktop/files/mixxx.cfg` says 10; find out why the card has 17, and which renderer the image really uses.
- Height = `allGain × halfBreadth / 255 × filtered.all`, where `allGain = total_gain × VisualGain_0` (`waveformrenderersignalbase.cpp:171-182`, `waveformwidgetrenderer.h:115`). The RGB renderer uses `total_gain` without the ×2 compensation.
- `total_gain` (`src/engine/enginepregain.cpp`) = the pregain knob × the ReplayGain correction: the track's ReplayGain × `[ReplayGain] InitialReplayGainBoost`, or `InitialDefaultBoost` (−6 dB on the card) for a track with no ReplayGain yet.
- On the card, 87 of 405 library tracks have a ReplayGain. Quantiles (gain, dB): min 0.242 (−12.3), 10 % 0.305 (−10.3), 25 % 0.337 (−9.5), median 0.377 (−8.5), 75 % 0.432 (−7.3), 90 % 0.504 (−5.9), max 1.067 (+0.6). So a typical track is drawn at about 38 % of its stored level, and an unanalysed one at 50 %.
- The analyser stores levels with `pow(x, 2 × 0.316)` (`src/analyzer/analyzerwaveform.h:20-27`). All four `VisualGain_N` are 1 on the card and in the image.

## What to build (spec 2h)
- **Only the two decks' main waveforms on the Decks page.** The overview strips, the Loop panel's waveform (if it is a separate widget; report), and every other screen keep their look. Colours (bass, mid, high) unchanged. The pregain knob and the EQ knobs keep changing the waveform as they do today. Audio is never changed: ReplayGain still sets the sound level.
- **Goal:** a typical track fills most of the height, and only very loud tracks clip, ever so slightly, at the top and bottom edges.
- **Measure before you choose.** The orchestrator copied the card's library database and waveform analysis (the owner's private data: use it only on the Mac and VM b, never commit it, never send it anywhere, delete any VM copy when done): `deploy/ui-redesign-20261117/owner-waveform-data-20261122/wfdata/` (untracked, in the main checkout; `mixxxdb-copy.sqlite` and `analysis/`). For each analysed track, work out the height its peaks reach today (as a share of half the waveform's height, e.g. the 99th-percentile and the max of `filtered.all` × gain) and under each option:
  - **A. Leave the ReplayGain out of the main waveform's height** (use the pregain knob only), plus one visual gain if needed;
  - **B. Keep today's formula and raise `VisualGain_0`** in `mixxx.cfg`;
  - any better option you find (say why).
  Recommend the option, with numbers, where a typical track reaches most of the height and only the loudest tracks pass the edge by a few per cent. "Very loud tracks" means tracks mastered loud. Under today's ReplayGain scaling, loudly mastered tracks are pulled down the most, so check which option makes them the ones that clip. Prefer config only if it meets the goal; a Mixxx patch only if config cannot.
- **Stop and ask** (end your turn with an ASK to the orchestrator) after the measurement, with the table and your recommendation, before you build. The orchestrator answers in one line.

## Files you own
- `stage3/02-desktop/files/mixxx.cfg` (the `[Waveform]` keys only);
- the new patch, if needed, and in the Mixxx source only what it needs (the main waveform renderers and `waveformrenderersignalbase.*`, `waveformwidgetfactory.*`, new files);
- new tests `tests/test_waveform_height.py` and `tests/native/waveform_height_*`; a measurement script under `tools/performance/` or `tests/` that reads an analysis folder given as an argument (no owner data committed).

No skin files and no stylesheets. Do not edit the registries; give the orchestrator your registration lines. If `test_eject_folders_view.py`, `test_removable_rows_fix.py` or `test_zoom_setting.py` checks that its patch is last, give the exact change needed as a registration line.

## Checks
- **Fixture:** synthetic waveform data at known levels and a known ReplayGain: the main waveform's drawn height matches the chosen formula; overview and other waveforms unchanged; the pregain knob still scales it. Show it failing without your change.
- **Before and after on the owner's data:** the measurement table for today and for the build (not committed if it names the owner's tracks; put it in `deploy/ui-redesign-20261117/wave-J13/`, untracked).
- **A render** of a deck's main waveform at the card's size before and after (offscreen on VM b if the all-shader renderer can run there; otherwise say so and give a drawn simulation from the analysis data, labelled as a simulation).
- The Mac suite in a clean worktree: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ13-nj13-20261122 <your worktree> gate`;
  - VM b is shared with the J12 builder today. Before you start a gate, check that no other gate is running in the VM (`ssh -F ~/.config/mixpi-lima-b/ssh.config lima-b-durable 'pgrep -af "[n]inja|[c]make --build|[c]test"'`); if one is, wait for it to finish (use a Monitor with an until-loop, not sleep). Check free space before and after;
  - never use `limactl`. Keep at least 24 GB free in the VM, run `fstrim` after cleanup, and keep the Mac above 20 GiB free.
- **Never touch the Raspberry Pi or any drive.** Open no window or app on the Mac.
- Give the orchestrator the Pi check, with coordinates: load a loudly mastered track and a quiet one to decks 1 and 2, play, and compare the main waveforms' peaks to the edges.
