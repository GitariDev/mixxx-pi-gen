# Wave D1: build D builders (S4, N-D1, N-D2)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of every brief here. Then read `AGREED-UI-SPEC.md` **section 2a (owner changes after build C)** and plan section 12.5. The owner's words win over everything.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at `c0bbda2`. Build C (`135a4bf`) is on the test card; its shots are in `deploy/ui-redesign-20261117/acceptance-C/conformance/k*.png` and `acceptance-C/shots/`, and its acceptance report is `acceptance-C/ACCEPTANCE.md`. Build B's code is commit `ef0874d` (build B as installed plus the post-B repairs); build B's card shots are `deploy/ui-redesign-20261117/owner-review/s*.png`.

At most three agents run at once (owner): you three. Never edit an existing Mixxx patch: new patches only, after the last one in `MIXXX_PATCHES` (`mixxx-sources-menu-fixes.patch`).

**"Build B's fonts"** (owner, 2026-11-18: "All fonts back to build B"): for every element, the font family, size and weight that build B used for it. Find them in the stylesheets and generator at `ef0874d` (`git show ef0874d:<path>`), including the Pioneered skin's own rules where MixPi set none. An element new in build C takes the build B font of the element with the same role (a button label, a screen title, a hint, a list row title, a list row subtitle, a number, a chip). Copy, colours, control sizes and layout stay as they are now (the agreed spec).

---

## S4 (skin and every stylesheet)

**Items**
1. **Fonts back to build B** in every file you own: `mixpi-performance.py`, `mixpi-performance.qss`, `pioneered-touch.py`, `pioneered-touch.qss`, `pioneered-menus.qss`, `mixpi-sources-menu.qss`, `mixpi-media-page.qss`. Make a table (element or role → build B family, size, weight → where it is set now) and put it in your report. Where text is painted in C++ and a stylesheet cannot set its font, say which element and what build B used: builder N-D1 (Sources menu, Edit sources) or N-D2 (Media page, table) matches it in C++.
2. **Loop panel while the desktop top bar shows** (spec 2a; `acceptance-C/shots/` has the 800×444 shot): the Mixxx window is 800×444 then. Make the rows shorter in that mode only, so all four rows (two rows of sizes, ½ and ×2, EXIT LOOP and RELOOP) fit in the panel. Below 48 px is allowed in that mode only (owner). At 800×480 nothing changes. Find how the skin knows the window height today (the 444 layout already exists for other pages).
3. Keep every C3 repair (`f06ad3f`, `5752aac`).

**Files you own:** the seven files above, `tests/test_performance_skin.py`, `tests/test_pioneered_touch.py`, `tests/test_touch_dialog_styles.py`, `tests/test_library_interface.py`, and a new `tests/test_fonts_build_b.py` for the font checks. Not `tests/test_sources_screen.py` (N-D1) or `tests/test_media_agreed.py` (N-D2): if a check there pins a build C font, tell that builder in your report. No Mixxx source and no native test runner.

**Checks:** tests that each element's font family, size and weight equal build B's (for the new elements, the role's build B font); the 444 loop rows fit (sizes sum to the 444 panel height) and 480 is unchanged; the Mac suite; the full native gate once at the end (the native runners read your stylesheets). VM workspace `uiD1-s4-20261118`.

---

## N-D1 (Sources native)

**Items**
1. **★ for the saved start.** The owner's saved start is `SidebarDefaultSource RekordboxFeature` (the drive group). On build C no row in Edit sources shows ★, the Sources menu's accent edge sits on This Pi, and Tracks opens on Mixxx's "Rekordbox" info page (`acceptance-C/conformance/k01-tracks.png`, `k02-sources-top.png`, `k05-edit.png`; `acceptance-C/ACCEPTANCE.md` U-4). Make every saved start value that build B could hold map to its row's ★ (the drive row for `RekordboxFeature` and any other drive feature), so Edit sources shows ★ and "TRACKS STARTS HERE" there, and Tracks starts as builder N-A2 made ★ on the drive row work (the drive when one is in, else This Pi). Keep the owner's saved value as it is: do not rewrite it unless the owner presses ★.
2. **The current-row edge** in the Sources menu follows the source whose lists the table is showing.
3. **Edit sources child rows back** (spec 2a; build B: `acceptance-B/shots/r10-edit-before.png`): This Pi's own lists (Tracks, Playlists, Crates, Auto DJ) and More's own lists come back as **indented rows under their source**, each with only an **ON/OFF** toggle (no ★, no UP or DOWN), in the agreed row style (`m-sources-edit.png` rows, `mixpi-sources-menu.qss`). They switch the same settings build B's child rows switched, and are kept over a restart. A child list that is off stays off in the menu, as in build B.
4. **Fonts:** where the Sources menu or Edit sources paints text in C++ (for example the row title's weight in the delegate), match build B's font for that role. S4 sets the stylesheet side; coordinate through your report, not by editing S4's files.

**Files you own:** a new patch `mixxx-sources-start-rows.patch`; `tests/test_sources_screen.py`, `tests/test_source_groups.py`, `tests/native/library_interface_sources_*`, `tests/native/source_groups_*`, new tests. Mixxx source: `src/widget/wlibrarysidebar.{h,cpp}`, `src/widget/touchsourcenavigation.h`, `src/library/library.{h,cpp}`, `src/widget/libraryinterface.h`, `src/library/sidebarmodel.{h,cpp}`, new files. Not the table views or the media files (N-D2).

- If a test you own pins a build C font that S4 changes back, update it to build B's font.

**Checks:** fixtures for ★ with each saved start value (including `RekordboxFeature`) with and without a drive, the current-row edge, the child rows (shown, indented, toggle kept over a restart, no ★ or UP/DOWN), and an 800×480 render of Edit sources with the child rows next to `m-sources-edit.png`. Mac suite; full native gate on VM `b` with your registration lines, 0 skips. VM workspace `uiD1-nd1-20261118`, temp tree `/tmp/d1-nd1-src`.

---

## N-D2 (table and Media page, native)

**Items**
1. **The narrowed table fits its columns.** With Sources open the table is x 0-480. On build C it keeps the column widths it had at 800 px, so a sideways scroll bar shows and KEY is cut off (`acceptance-C/conformance/k03-sources-drive.png`, `k08-tracks-picked.png`). Drawn (`m-sources-top.png`, `m-sources-sub.png`): TITLE, ARTIST, BPM and KEY all fit in 480 px with no sideways bar, the text cut with "…". When the table widens again, it gets its 800 px widths back exactly (build B's saved widths and the table-columns behaviour must not change). The same holds for Load sample's table if Sources opens over it.
2. **OPEN on the Media page switches to Tracks** (spec s13: "It then switches to Tracks."). On build C it reads the drive and the button then reads BROWSE, but the screen goes back to the tab you came from (DECKS, SAMPLER). Repro and logs: `acceptance-C/ACCEPTANCE.md` R-4. Find the cause first. If it is in the skin (for example the tab the skin restores when the Media page closes), do not change the skin: write the exact change in your report for S4 and the orchestrator. If it is native, fix it in your patch. BROWSE does the same.
3. **Fonts:** where the Media page or the table paints text in C++, match build B's font for that role (S4 does the stylesheets).

**Files you own:** a new patch `mixxx-table-fit-media-open.patch`; `tests/test_media_agreed.py`, `tests/native/media_agreed_*`, `tests/native/media_screen_runner.py`, `tests/test_table_columns.py`, `tests/native/table_columns_*`, new tests. Mixxx source: `src/widget/wtracktableview.{h,cpp}`, `src/widget/wlibrarytableview.{h,cpp}`, `src/library/mixpimedia.h`, `src/library/mixpimediapage.h`, `src/widget/mixpipage.h`, new files. Not `library.cpp` or the sidebar (N-D1): if you need them, report it.

- If a test you own pins a build C font that S4 changes back, update it to build B's font.

**Checks:** fixtures for the fit (480 px: four columns visible, no sideways bar; back to 800: the old widths exactly) and for OPEN and BROWSE switching to Tracks; Mac suite; full native gate on VM `b` with your registration lines, 0 skips. VM workspace `uiD1-nd2-20261118`, temp tree `/tmp/d1-nd2-src`.
