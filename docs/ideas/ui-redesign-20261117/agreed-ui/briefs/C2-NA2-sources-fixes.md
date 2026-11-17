# Wave C2, builder N-A2 (Sources menu repairs, native)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first. It is part of this brief.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` after the wave C1 integration, which includes your `mixxx-sources-menu.patch` and `mixpi-sources-menu.qss`. **Do not edit `mixxx-sources-menu.patch`**: it is now an existing patch. Make a new patch, `mixxx-sources-menu-fixes.patch`, that applies after it (and after `mixxx-media-agreed.patch`, which is registered after yours).

## Your items (deviations you reported in C1, now to be built as drawn)

1. **Counts on rekordbox lists** (spec s5: "Inside a source … that source's rows, with counts on the right"; `mockups/m-sources-sub.png` shows MANTACORE › rekordbox with 48, 31, 26, 22). Give rekordbox playlists their track counts, in the same place and style as the other counts. Do not slow down opening a drive: count from data the feature already reads, and say what it costs.
2. **★ on every row that is on** (`mockups/m-sources-edit.png` draws ★ enabled on every row). Make ★ work on the drive row and on Samples:
   - ★ on the drive row: Tracks starts at the drive (its rekordbox export, or its folders, the same as OPEN on the Media page) when a drive is in. With no drive in, Tracks starts at This Pi.
   - ★ on Samples: Tracks starts at the Samples folder.
   - The switched-off row keeps ★ drawn disabled, as you built it. That is a listed deviation the orchestrator puts to the owner.
3. Your renders were taken before your last stylesheet change. Render again (top level, inside a drive with counts, the edit list) and put them next to the mockups.

## Files you own

New `stage3/01-install-packages/files/mixxx-sources-menu-fixes.patch`; `mixpi-sources-menu.qss`; `tests/test_sources_screen.py`, `tests/test_source_groups.py`, `tests/native/library_interface_sources_*`, `tests/native/source_groups_*`, and new tests.

Mixxx source files you may patch: `src/library/rekordbox/rekordboxfeature.{h,cpp}`, `src/library/library.{h,cpp}`, `src/widget/wlibrarysidebar.{h,cpp}`, `src/widget/touchsourcenavigation.h`, `src/widget/libraryinterface.h`, `src/library/mixpimedia.h` (only if starting at a drive needs its open path; nobody else owns it this wave), and new files. Not the media page, effects, mixer, preferences or any skin file.

## Checks

Native fixtures for each item (a rekordbox fixture with known playlist sizes; ★ on the drive row with and without a drive; ★ on Samples), the Mac suite, and the full native gate on VM `b` with your registration lines applied locally, 0 skips. Report the registration note (`MIXXX_PATCHES`, `PREREQUISITES`, any `REQUIRED_TESTS`).
