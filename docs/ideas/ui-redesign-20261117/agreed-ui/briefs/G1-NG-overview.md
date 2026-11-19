# Wave G1, builder N-G1 (native): the overview strip freezes after about 6¾ hours

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read the investigation `deploy/ui-redesign-20261117/session-F/OVERVIEW-FREEZE-INVESTIGATION.md` and the fix plan `session-F/FIX-PLAN-overview-playhead.md`.

**No design of your own; where the spec is silent, build B stays.** This is a bug fix with no visible change other than the strip moving again.

Base: `feat/pi-performance-target` at the head the orchestrator names. Never edit an existing Mixxx patch. Make `mixxx-overview-playposition.patch` after the last one in `MIXXX_PATCHES` (`mixxx-shared-columns.patch`).

## The owner's request
In the build F session the owner saw the strip freeze and said: "Good catch on the strip. Please Fix".

## The cause (checked by the orchestrator)
In the pinned Mixxx (`3ebac449`), the counter `EngineBuffer::m_iSamplesSinceLastIndicatorUpdate` is a signed `int`:
- it is declared at `src/engine/enginebuffer.h:379`;
- it grows by the buffer size on every callback at `src/engine/enginebuffer.cpp:1446`;
- the threshold check that drives `playposition` and `CueControl::updateIndicators` is at `:1477-1482`.

The counter is never reset except on a seek. It overflows after 2³¹ samples (about 6 h 46 min at 44.1 kHz stereo). After that, `playposition` stops updating until the next seek, and the overview, which reads `playposition`, freezes.

## The fix
- Backport upstream commit `bef0af3172` (mixxxdj/mixxx PR #16245, merged into the 2.5 branch on 2026-06-02; it fixes issue #9751). Fetch it from GitHub; it is a public repository.
- Take it as it is, adapted only where the pinned tree differs. Say in the patch header what it is and where it came from.
- If it does not apply cleanly or does more than the investigation says, stop and tell the orchestrator. Do not design your own fix.
- Check whether `CueControl::updateIndicators` and any other control behind the same threshold also need it.

## Files you own
- the new patch, plus new tests `tests/test_overview_playposition.py` and `tests/native/overview_playposition_*`;
- in the Mixxx source, `src/engine/enginebuffer.{h,cpp}` only, unless the upstream commit touches more files.

No skin files and no stylesheets. Do not edit the registries `01-run.sh`, `tests/test_mixxx_patches.py` or `tools/performance/required-native.py`; give the orchestrator your registration lines instead.

## Checks
- **A native fixture:** drive an `EngineBuffer` with a loaded track past the old overflow point without a seek, and check that `playposition` keeps updating at the expected rate.
  - Set the counter close to `INT_MAX` through a test hook, or run enough callbacks; do not wait 6¾ hours.
  - The fixture must fail without the patch and pass with it. Show both runs.
- The Mac suite.
- The full native gate on VM `b` with your registration lines applied, 0 skips. VM workspace `uiG1-ng-20261119`, temp tree `/tmp/g1-ng-src`. Keep at least 24 GB free in the VM, and run `fstrim` after cleanup.
- Give the orchestrator a Pi check. Load a track, play, take three shots 10 s apart, and confirm the overview line moves about 19 px each time. The real overflow cannot be shown on the card in a short run, so say what the fixture proves instead.
- Never touch the Raspberry Pi; the owner is using it.
