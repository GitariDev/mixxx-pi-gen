# Wave J1, builder N-J1 (native): no use of a deleted library widget at quit

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read the investigation `deploy/ui-redesign-20261117/acceptance-I/INVESTIGATION-X1-X2.md` (X2) and acceptance I's X2 section. Both are untracked, in the main checkout. The investigation's fixture sources are in the session scratchpad under `fixture/`, at `/private/tmp/claude-501/-Users-gitaritirima-Documents-Workspace-Personal-Projects-mixxx-pi-gen/01eef82b-7712-44de-b076-2782a69dc643/scratchpad/fixture/`, and on VM b in `/tmp/x2fix`.

**No design of your own.** This is a crash fix with no visible change.

Base: `feat/pi-performance-target` at the head the orchestrator names. Build I (59 patches) is on the card. Never edit an existing Mixxx patch. Make `mixxx-quit-library-widget.patch` after the last one in `MIXXX_PATCHES` (`mixxx-sources-menu-shadow.patch`), with the prerequisites it needs.

## The fault (acceptance I, X2; new in build I)
`mixxx-media-chip-ping.patch` made every deck or pad track change call `MixpiMedia::refresh()` (`src/library/mixpimedia.h:89-96`). At Ctrl+Q, Mixxx deletes the skin's widgets before the players. So a player unloading its track during quit calls `refresh()`, and `refresh()` reaches the screen through `Library::m_pLibraryWidget` (`library.h:254`), a plain pointer to the already deleted `WLibrary` (`mixpimedia.h:798` → `:333` → `mixpipage.h:21`). This is a use-after-free, and it was seen once on the card as a SIGSEGV on quit.

## The fix
- **The investigation's smallest fix:** make `Library::m_pLibraryWidget` a `QPointer<WLibrary>`, so the lookup returns null after the layout is deleted. The existing callers already handle null.
- **Check every other raw pointer** that `refresh()` or the strip reaches during quit, and guard it the same way if it can dangle.
- Change no behaviour while Mixxx runs.

## Files you own
- the new patch;
- new tests `tests/test_quit_library_widget.py` and `tests/native/quit_library_widget_*`;
- in the Mixxx source, `src/library/library.{h,cpp}`, plus `src/library/mixpimedia.h` and `mixpimediapage.h` only for guards.

No skin files. Do not edit the registries; give the orchestrator your registration lines.

## Checks
- **A native fixture** with Mixxx's quit order: the skin widgets deleted, then players unloading tracks with a drive loaded.
  - It crashes or reports a use-after-free without the patch (run it 20 times, or under ASan if available) and is clean 20 of 20 with it.
  - Base it on the investigation's fixture.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ1-nj1-20261120 <worktree> gate`;
  - never use `limactl`.
- Never touch the Raspberry Pi.
- Give the orchestrator a Pi check: load a GANDER1 track on a deck and a sample on a pad, do several ejects and re-plugs, then Ctrl+Q three times (start in between). Each quit ends "shutdown complete with code 0".
