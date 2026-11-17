# Build C: rules for every builder (part of your brief)

You are a builder (Claude Opus 5.5, medium effort) in the MixPi build C climb. The orchestrator (Claude Opus 5.5 xhigh) integrates your work, runs every Pi check and owns the shared registries. Up to two other builders work at the same time, in their own worktrees, on other files.

## The UI rule (the owner's main point)

The owner, 2026-11-17 19:13: "Please don't deviate from UI we set and have the reviewers know what the app is supposed to look like so they judge against that not what they think is best."

- **No design of your own; where the spec is silent, build B stays.**
- Build exactly what `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` and its mockups (`agreed-ui/mockups/*.png`, 800×480) show. Read **spec section 0 and section 1 (the rules for every screen)** before anything else, then the spec sections and mockups named in your brief.
- Mixxx skins and native widgets are Qt, not HTML. Match structure, order, labels (exact copy), roles, colours and states. Pixels may differ only where Qt forces it.
- The values come from `agreed-ui/design/tokens.css` (colours, radius, lit alpha), `primitives.css` (buttons, segments, close, chips, sliders, tick rows, scroll bars) and `layout.css`. `design/all-mockups.html` holds the 12 screens as HTML, so you can read exact sizes, icons (inline SVG paths) and copy there.
- The touch minimum of 48 px stays (the mockups draw some buttons 44 px; making them 48 px is not a deviation). Text no smaller than 13 px.
- **If something cannot be built as drawn, do not choose another design.** Stop that part, and in your report say what, why, and the nearest faithful option. The orchestrator asks the owner.
- Where the spec is silent on behaviour and you must pick something to make it work, pick the build B behaviour, or the least visible option, and list it under "Assumptions" in your report.

## Where you work

- You are in your own git worktree of `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`, based on `feat/pi-performance-target`. Work and commit only there. Small, focused commits. Every commit message ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Never push, merge or rebase. Never switch the main checkout's branch.
- Edit only the files your brief says you own, plus the new files it names. If you need a change to any other file, do not make it: put it in your report as a request.

## Read first

1. `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` (the binding spec), then the mockups for your items. View each mockup PNG.
2. `docs/ideas/UI-REDESIGN-PLAN-20261117.md` section 12 (precedence and U-1 to U-10), then the R-items your brief names.
3. Build B, as the owner reviewed it: `deploy/ui-redesign-20261117/owner-review/s*.png` (s00 Sources, s04 Decks, s05 Loop, s08 FX 1, s10 Sampler, s11 Load sample, s12-s15 Settings, s16 Media). The spec says what changes from these.
4. `docs/ideas/UI-REVIEW-1-20261117.md` sections 1 and 5-8: the owner's words, verbatim.

## Hard constraints

- Never touch the Raspberry Pi, the EOS card, MANTACORE or any USB drive. The orchestrator runs every Pi check.
- Never touch the Lima VMs `colima-mixpi-ui` or `colima-synthetic`. On Lima VM `b`, use only your own new `/srv/<workspace>` folder (the helper below makes it). Never delete or change other `/srv` folders. Keep at least 24 GB free there.
- **Never edit an existing Mixxx patch file.** New Mixxx changes go in new patch files under `stage3/01-install-packages/files/`, made to apply after every patch now in `MIXXX_PATCHES` (`bash stage3/01-install-packages/01-run.sh --mixxx-print-patches`; the list ends with `mixxx-media-lists.patch`).
- No new dependency (package, library, font) without a stated reason in your report.
- **Shared registries** are owned by the orchestrator: `MIXXX_PATCHES` in `stage3/01-install-packages/01-run.sh`, `PREREQUISITES` in `tests/test_mixxx_patches.py`, `REQUIRED_TESTS` in `tools/performance/required-native.py`, and the stylesheet list in `pioneered-touch.py` (the tuple `("pioneered-menus.qss", "pioneered-touch.qss")`). You may edit them locally to run your tests, but do not commit those edits. Put the exact lines in your report as a **registration note**.
- Owner-visible words are plain English, and are the exact copy from the mockups.
- Never type passwords.

## Making a Mixxx patch

1. Make a patched tree: `git clone -q /tmp/mixpi-actions-routing-objects-20261115 /tmp/<your-name>-src && cd /tmp/<your-name>-src && git checkout -q 3ebac449e7e5fe2a0186596657696e87ce8b0e56`, then `git apply` every patch in the list above, in order (from `<worktree>/stage3/01-install-packages/files/<name>`), then `git add -A && git commit -qm base`.
2. Make your change there, then `git diff > <worktree>/stage3/01-install-packages/files/<new>.patch`. Check that it applies on a fresh copy after the others.
3. `tests/test_mixxx_patches.py` shows the `PREREQUISITES` format. Follow it in your registration note.

## Tests

- **Mac suite** (must stay green): `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`. Platform skips are expected on the Mac. For one module, add `-p test_x.py`. Baseline at `ef0874d`: 710 tests OK (141 skips).
- **Native Qt tests** run on VM `b` through the helper. It copies your worktree's tracked and new files to a fresh folder and runs there:
  `/private/tmp/claude-501/-Users-gitaritirima-Documents-Workspace-Personal-Projects-mixxx-pi-gen/01eef82b-7712-44de-b076-2782a69dc643/scratchpad/vm-native.sh <your-workspace> <absolute worktree path> <test_x.py | gate> [tail-lines]`
  - `gate` runs `tools/performance/required-native.py`, the full native gate. On the Linux VM a skip is a failure. It takes 5-10 minutes. Baseline: 190 tests, 0 skips.
  - Follow the existing native test pattern (for example `tests/test_media_screen.py` with `tests/native/media_screen_*`). A new native module goes in your registration note for `REQUIRED_TESTS`.
- **Visual check for native pages:** render each native page you change offscreen at 800×480, with the real stylesheets applied, to a PNG (for example with `QWidget::grab()` in a native fixture run on VM `b`; copy the PNG back with `limactl shell b -- cat <path> > <local>` using `LIMA_HOME=/tmp/mq1110-1943`). Put each render next to its mockup, fix what differs, and list the renders in your report.
- Before you finish: your new tests pass, the Mac suite passes, and the full native gate passes on VM `b` with your registration lines applied locally. Report the exact pass count and 0 skips.

## Final report (short)

- Commits: sha and subject, in order.
- Files changed, per item.
- Registration note (exact lines).
- Tests: exact commands, pass counts, skips.
- Conformance: for each spec line in your items, "done" or "deviation: what and why". Renders, if any, with paths.
- Assumptions (where the spec was silent).
- Pi checks the orchestrator should run for your items, with coordinates on the 800×480 screen.
- Anything not finished, and any request for a file you do not own.
