# Wave C1, builder N-A (Sources, native)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first. It is part of this brief.

**No design of your own; where the spec is silent, build B stays.**

## Your item: U-4 native, the Sources side menu and the full-screen edit list

Spec: `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` section 1 (all rules) and **s5**. Mockups: `mockups/m-sources-top.png`, `m-sources-sub.png`, `m-sources-edit.png`. Exact sizes, icons (inline SVG) and copy: `design/all-mockups.html`. Plan: `docs/ideas/UI-REDESIGN-PLAN-20261117.md` R-9, R-10 and section 12.1 (R-9 and R-11 overrides). Build B as the owner saw it: `deploy/ui-redesign-20261117/owner-review/s00-sources.png`.

Build B shows Sources full screen: a 264 px rail of source tiles on the left, and a panel with Back and a crumb. The agreed design replaces that with one side menu on the right.

**The side menu** (`m-sources-top.png`, `m-sources-sub.png`):
- A panel 320 px wide at the right of the screen (x 480-800), from under the Tracks header (y ≈ 100) to the bottom (y 480). It is over deck 2's half of the strip and the load row while it is open. The table sits to its left, with its own scroll bar.
- **Top level:** a header with [‹ BACK] [EDIT]. Each has an icon beside its label: a ‹ chevron, and a pencil-on-list icon (not the ✎ actions pencil). Then the source rows: icon, title, small subtitle, and › when the row can be entered. The current source has the current-row style (spec section 1: `--mx-surface-2`, 4 px accent edge on the left, semibold).
- **Inside a source** (for example MANTACORE › rekordbox): a header with [‹ BACK] and the place name. Then that source's rows, with counts on the right and › where a row can be entered; the current row has the accent edge.
- Rows as drawn (52 px in the mockup), source icons in the source colour as drawn.
- **Scroll bar** at the menu's right edge when its list is longer than the panel: 24 px natively (spec section 1, rubric 8), and drag scrolling still works.
- EDIT opens the edit list.

**The full-screen edit list** (`m-sources-edit.png`): full width under the top bar.
- Header: the title "EDIT SOURCES", the hint "Switch sources on or off, set the order, ★ where Tracks starts.", then **DONE** (Confirm: solid muted accent, dark text) and the close ✕ (spec section 1 close control) at the right.
- Each row: ★ (start here; lit on the start row, whose subtitle reads "TRACKS STARTS HERE"), icon, title and subtitle, an ON/OFF toggle drawn as in the mockup, ▲ UP and ▼ DOWN.
- The row that is switched off is dimmed. UP is disabled on the first row and DOWN on the last (drawn dashed and dim in the mockup).
- R-10 behaviour stays: changes kept over a restart.

**Load sample's SOURCES…** (spec s7) opens Sources too. In build B a pick there returns to Load sample. Keep that behaviour with the side menu.

**Styles:** put every rule for the side menu and the edit list in a **new file** `stage3/01-install-packages/files/mixpi-sources-menu.qss`, using the tokens in `design/tokens.css` and the section 1 rules (3 px radius, roles, lit tints at 26%, close ✕ red with no outline at rest, 24 px scroll bar, fonts). It will load after `pioneered-menus.qss` (registration note: add it to the stylesheet tuple in `pioneered-touch.py`). Do not edit `pioneered-menus.qss`; its old `#MixpiSource*` section is removed in wave C2. Make your rules complete, so nothing from the old section leaks through.

**The skin side is wave C2, not yours.** The skin (`mixpi-performance.py`) places the native sidebar today (`browse_page()`: `SidebarWrapper` fills screen 1). You choose how the panel gets its place over the strip and load row: for example a native overlay under the skin root, as the Media page does (`src/widget/mixpipage.h`, which builder N-B owns this wave: use it, do not change it), or a skin placement. Then write a **skin handover note** in your report: exactly what the skin must do in C2 (where `SidebarWrapper` goes, its size, which controls it binds, what to remove from the old Sources screen, how the table narrows to x 0-480 while the menu is open). You may try your skin change locally to test it, but do not commit `mixpi-performance.py`.

## Files you own

New `stage3/01-install-packages/files/mixxx-sources-menu.patch`, new `stage3/01-install-packages/files/mixpi-sources-menu.qss`; `tests/test_sources_screen.py`, `tests/test_source_groups.py`, `tests/native/library_interface_sources_*`, `tests/native/source_groups_*`, and new tests you add.

Mixxx source files you may patch: `src/widget/wlibrarysidebar.{h,cpp}`, `src/widget/touchsourcenavigation.h`, `src/library/library.{h,cpp}`, `src/widget/libraryinterface.h`, and new files you add. Not `mixpipage.h`, `mixpimedia*.h` (N-B) or any skin file (S1).

## Checks

- Native fixtures: top-level rows and header (BACK, EDIT, icons), inside-a-source header (BACK, place name) and counts, current-row edge, › only on rows that can be entered, scroll bar shown when the list is longer than the panel, drag scrolling, EDIT opens the edit list, DONE and ✕ close it, UP disabled on the first row, DOWN on the last, the off row dimmed, ★ start row, changes kept (R-10), a pick from Load sample returns to Load sample.
- Offscreen renders at 800×480 with the real stylesheets of: the top level, inside a source with a long list (scroll bar showing), and the edit list. Put each next to its mockup in your report.
- Mac suite green; full native gate green on VM `b` with your registration lines applied locally, 0 skips.

## Assumptions to report, not to invent

- What BACK does at the top level. The mockup draws it enabled. Build B disables Back at the top. If you make it close the menu, say so.
- What DONE and ✕ each do in the edit list, given that build B saves each change at once.
