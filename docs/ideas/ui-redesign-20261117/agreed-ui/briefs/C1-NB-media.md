# Wave C1, builder N-B (Media page, native)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first. It is part of this brief.

**No design of your own; where the spec is silent, build B stays.**

## Your items

Spec: `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` section 1 (all rules), **s13** and **s11**. Mockups: `mockups/m-media.png`, `m-settings-media.png`. Exact sizes, icons (inline SVG) and copy: `design/all-mockups.html`. Plan: `docs/ideas/UI-REDESIGN-PLAN-20261117.md` R-2, R-4, R-5, R-6, section 10.1 (Q1, Q2, Q3) and section 12.1 (R-4 override). Build B as the owner saw it: `deploy/ui-redesign-20261117/owner-review/s16-media.png` (shown unstyled there; the styling bug is fixed at `fb1a119`).

### U-10, the Media page (s13, `m-media.png`)

- **Header:** the title "USB & MEDIA"; next to it the filter segments **ALL** (default), **READY** and **IN USE** (Choose role); the close ✕ at the right end (spec section 1 close control: 48×48, `--mx-surface-2`, red ✕ #ec7f74 as two strokes, no outline at rest). Build B has the close on the left: it moves to the right, in `mixpipage.h` (you own it).
- **One row per drive:** the USB icon, the name, the size, a state chip (a pill, not pressable: READY, IN USE or EJECTING, coloured as drawn); **OPEN** with the browse (list) icon, Navigate (neutral); **EJECT** with the eject (⏏) icon, Caution (dark amber, amber border and text).
- **Scrolling:** the list scrolls when several drives are in, with a 24 px bar at its right edge, and by drag.
- **Removed:** no deck or song lines, no explanatory paragraph, **no COPY TO PI**. The "playing from Pi memory" column goes too.
- **Footer:** one short line, "**N tracks** playing from Pi memory" (N tracks in bold), shown only when any tracks are.
- **What OPEN does:** it reads the drive, the same as LOAD on the plug-in strip (its rekordbox export, or its folders if it has none), then switches to Tracks. After that the button reads **BROWSE**. If switching to Tracks needs `library.cpp` or a skin change, do not make it: report the request (N-A owns `library.cpp`, S1 the skin).
- **Filters:** ALL shows every drive, READY the drives that are ready, IN USE the drives in use.
- The eject sheet (R-6), the insert ping with LOAD and DISMISS (Q1) and the green Safe to remove strip (Q2) are not drawn in the spec. Their behaviour and words stay as in build B. Apply the section 1 rules to them: EJECT is Caution, LOAD is Confirm, CANCEL and DISMISS are Navigate, 3 px radius, muted tokens.

### U-8 native, plugging in a drive (s11, `m-settings-media.png`)

- A new control **`[MixPi],drive_insert`**: 0 = ASK (default), 1 = AUTO LOAD. Saved in `mixxx.cfg` within a second of a change and read at start, like the other MixPi settings.
- ASK is today's bottom ping with LOAD and DISMISS. AUTO LOAD opens the drive at once, as LOAD does, with no ping.
- The Settings row that writes it is drawn by the skin in wave C2 (row "Plugging in a drive", ASK / AUTO LOAD, with the subtext from the mockup). Do not edit the skin.

### Styles

Put every rule for the Media page, the eject sheet and the bottom strips in a **new file** `stage3/01-install-packages/files/mixpi-media-page.qss`, using `design/tokens.css` and the section 1 rules. It will load after `pioneered-menus.qss` (registration note: add it to the stylesheet tuple in `pioneered-touch.py`). Do not edit `pioneered-menus.qss`: its old Media section is removed in wave C2. Make your rules complete, so nothing from the old section leaks through.

## Files you own

New `stage3/01-install-packages/files/mixxx-media-agreed.patch`, new `stage3/01-install-packages/files/mixpi-media-page.qss`; `tests/test_media_screen.py`, `tests/test_media_handover.py`, `tests/test_media_transfer_display.py`, `tests/native/media_screen_*`, `tests/native/media_handover_*`, and new tests you add.

Mixxx source files you may patch: `src/widget/mixpipage.h`, `src/library/mixpimediapage.h`, `src/library/mixpimedia.h`, and new files you add. Not `library.cpp`, the sidebar or any skin file.

Keep every safety rule of R-5 and R-6: the eject gate and the controlled-media profile behave as today, eject is engine A only, and nothing writes to a drive.

## Checks

- Native fixtures: header order (title, ALL, READY, IN USE, ✕ at the right), filter results, one row per drive with OPEN and EJECT and the state chip, no COPY TO PI, no deck or song lines, the footer shown only with tracks on the Pi and its count, scrolling with several drives, OPEN then BROWSE, `[MixPi],drive_insert` saved and read back, ASK shows the ping, AUTO LOAD loads with no ping.
- Offscreen renders at 800×480 with the real stylesheets: three drives (one IN USE, two READY, so the list scrolls) with the footer "2 tracks playing from Pi memory"; the READY filter; no drive; the insert ping. Put each next to `m-media.png` in your report.
- Mac suite green; full native gate green on VM `b` with your registration lines applied locally, 0 skips.

## Assumptions to report, not to invent

- What the page shows with no drive. The spec removes the explanatory paragraph and does not draw an empty state; keep build B's short "No USB drive" line and drop the paragraphs, unless the code says otherwise.
- Where EJECTING and SAFE TO REMOVE drives show under the READY and IN USE filters.
