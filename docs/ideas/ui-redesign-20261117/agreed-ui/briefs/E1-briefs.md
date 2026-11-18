# Wave E1: build E builders (S6, N-E)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of both briefs. Then read `AGREED-UI-SPEC.md` sections 0, 1, **2a and 2b** and plan 12.5-12.6. The owner's words win over everything.

**No design of your own; where the spec is silent, build B stays.** Fonts are build B's (spec 2a).

Base: `feat/pi-performance-target` at `819056f`. Build D (`ce2186c`, 50 patches) is on the test card, plus the in-place stylesheet repair `2eedc8f`. Card shots: `deploy/ui-redesign-20261117/acceptance-D/conformance/d*.png`, `acceptance-D/shots/`, and the mockup-against-card pairs in `acceptance-D/pairs/`. Council round 2 reports: `deploy/ui-redesign-20261117/council/round2-*.md`.

At most three agents run at once (owner). Never edit an existing Mixxx patch; new patches go after the last one in `MIXXX_PATCHES` (`mixxx-table-fit-media-open.patch`).

---

## S6 (skin): three repairs from council round 2 (spec 2b)

1. **REC dot red.** Every mockup draws the REC button's dot red (see `m-loop.png`, `m-tracks.png`: the "● REC" at x ≈ 640, y ≈ 24). On build D it is white (`d06-tracks-loaded.png`). Draw it in the mockups' red (the Danger token's colour as drawn; read `design/all-mockups.html` for the exact value). Keep build B's REC states (waiting, recording) as they are now.
2. **EXIT LOOP and RELOOP at rest while a loop is on.** `m-loop.png` draws a loop on (size 4 lit) with EXIT LOOP and RELOOP at rest: Danger and Sound at rest, not lit. On build D they are lit while a loop is on (`d07-loop.png`; `mixpi-performance.py`, the `display=…loop_enabled` binding near the EXIT LOOP and RELOOP buttons, cited by the Fable seat). Make them at rest in every state, with the pressed look while pressed. Do not change what they do.
3. **The table's row colours.** The Tracks and Load sample mockups (`m-tracks.png`, `m-loadsample.png`) draw the table with the agreed surfaces. Their alternate rows are `#161a20`, as the Sol seat measured on the PNGs. Build D draws `#32323c` stripes (`d06-tracks-loaded.png`, `d10-loadsample.png`) from Pioneered's inherited `QTableView` rule (`alternate-background-color: #32323c`). Make the library tables (Tracks, Load sample, and the table in Sources) use the mockups' row, alternate-row, text and selected-row colours. Read the colours from `design/all-mockups.html` and `tokens.css`, and check them against the mockup PNGs.

**Files you own:** `mixpi-performance.py`, `mixpi-performance.qss`, `pioneered-touch.qss`, `pioneered-menus.qss` (only if a table rule lives there), `tests/test_performance_skin.py`, `tests/test_pioneered_touch.py`, `tests/test_fonts_build_b.py`. No Mixxx source.

**Checks:** generated-XML and stylesheet tests for each repair; the Mac suite; the full native gate once at the end (some native runners apply the stylesheets). VM workspace `uiE1-s6-20261118`. Give the orchestrator what to look at on the card for each repair.

---

## N-E (native): two items for build E (spec 2b)

1. **The accent edge after OPEN or BROWSE** (acceptance D FAIL 1: `acceptance-D/ACCEPTANCE.md` repro 1, shot `acceptance-D/shots/f1-step4-top.png`). After a drive is opened from the Media page with OPEN or BROWSE, Tracks shows the drive's tracks, but the Sources menu reopens inside This Pi with its edge on This Pi. Make the menu's current source, place and edge follow the drive that was opened. The top level then shows the edge on the drive row, and the place matches what Tracks shows. Do not change the saved ★ start. N-D1's `shownSourceTile()` and `currentChanged` logic is in `mixxx-sources-start-rows.patch`; N-D2's `mixpiClosePageToTracks()` is in `mixxx-table-fit-media-open.patch`. Find the cause first and write it in your report.
2. **Clearing a playing pad: "Stop it, then clear"** (owner). Today `[MixPi],sampler_clear` skips a ticked pad that is playing, because Mixxx refuses to eject a playing pad. Make it stop each ticked pad that is playing, then empty it, so every ticked pad goes empty. Keep everything else: unticked pads are untouched, ticks clear, the popover closes, the sampler bank is saved, and no sample file is touched. The controls are in `mixxx-agreed-controls.patch` (`src/mixer/mixpisamplerclear.h`).

**Files you own:** new patches `mixxx-sources-open-edge.patch` and `mixxx-sampler-clear-playing.patch`; `tests/test_source_groups.py`, `tests/native/source_groups_*`, `tests/test_agreed_controls.py`, `tests/native/agreed_controls_*`, `tests/test_media_agreed.py`, `tests/native/media_*`, and new tests. Mixxx source: `src/widget/wlibrarysidebar.{h,cpp}`, `src/widget/touchsourcenavigation.h`, `src/library/library.{h,cpp}`, `src/widget/libraryinterface.h`, `src/library/mixpimedia.h`, `src/library/mixpiopentracks.h`, `src/mixer/mixpisamplerclear.h`, new files. No skin files and no stylesheets (S6).

**Checks:** native fixtures for each (OPEN and BROWSE from a non-drive source, then the menu's edge and place on the drive; a ticked playing pad stopped and emptied, a ticked stopped pad emptied, an unticked playing pad untouched, sample files byte-identical); the Mac suite; the full native gate on VM `b` with your registration lines, 0 skips. VM workspace `uiE1-ne-20261118`, temp tree `/tmp/e1-ne-src`.
