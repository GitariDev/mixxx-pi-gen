# Pioneered touch proposal

Open `index.html` directly in a browser. It is self-contained, makes no network
requests, and is a silent, simulated UI proposal. It does not control Mixxx or
change the Pi. `prototype.source.html` is its editable source; the entry point
inlines the PNGs from `assets/` and `reference/`. After editing the source, run
`python3 tools/pioneer-prototype/build.py` from the repository root. This also
produces `loop-preview.html` and `browse-preview.html`, which open the relevant
controls for review.

This revision replaces the rejected side-by-side card design. Its references are:

- Claude's original HTML, retained verbatim in `reference/claude-original.html`.
- The user's annotated screenshot and decisions in the original conversation,
  especially the prototype brief at timeline position 378.
- Actual Pi captures, `reference/pi-perform.png` and `reference/pi-browse.png`.
- The Pioneered `skin.xml`, `waveform.xml`, `deck.xml`, `style.qss` and the image's
  Waybar configuration. Open Sans is the skin font; the preview falls back to
  DejaVu Sans or Arial if it is absent on the viewing computer.

## Screen geometry

The UI always lays out at 800×480 and scales uniformly for a smaller display.
It never rearranges into a mobile dashboard.

| Row | Perform / FX / settings | Browse / sources |
| --- | ---: | ---: |
| Waybar | 36 px | 36 px |
| Tabs, media, record, CPU, settings | 50 px | 50 px |
| Main content | 208 px | 262 px |
| Deck information | 82 px | 28 px |
| Overview waveforms | 52 px | 52 px |
| Deck controls | 52 px | 52 px |
| Total | 480 px | 480 px |

Settings replace the waveform area. They do not cover deck information,
overviews or transport controls. All overview rows have fixed heights and clip
within their own bounds. The active tabs retain the yellow-green outline;
blue title strips, white tempo boxes, deck labels and the black waveform area
follow the real skin. Detailed and overview textures are extracted from the Pi
capture, with neutral grid/text pixels removed before adding separate playheads
and cues. These are reference textures, not audio analysis of demo tracks.

## Interactive scope

- Three tabs; selecting the active tab preserves its state.
- Two loaded decks, cue/play, key lock, quantize and sync simulation.
- A LOOP button on each deck opens 1/32–64 beat intervals in the waveform area.
  The translucent panel overlays the waveform area, leaving deck information,
  overview strips and transport exposed. Waveforms keep scrolling behind it.
  Background controls are temporarily inert to prevent accidental taps; closing
  restores them. On Perform, the deck labels stay exposed.
  Choosing an interval engages that loop, snapped to a beat when Q is enabled.
  Half/double length, Exit and Reloop work independently for each deck. Playback
  wraps at the loop end; cue exits the loop and a replacement track clears it.
  Loop ranges appear on both waveform views, and bottom buttons show active size.
- Keys show Camelot(musical key), for example `8A(Am)` and `12A(C♯m)`, in the
  detailed waveform labels, deck information and Browse key column.
- Shared media LOAD/EJECT; media chip to remove/reinsert the simulated stick.
- Eject by a one-second hold or tap and confirmation. Releasing a longer-than-
  tap hold early cancels it. Loading and USB-dependent decks block eject.
- Browse selection/search, separate deck loading, a playing-deck load lock,
  source checkboxes, one/several/all-source views and a default source. Browse
  opens with the full-width track table, as on the current Pi. One Show/Hide
  button stays at the far right of the full-width toolbar in both states. The
  source pane slides in from the right and spans 290 px, from the search toolbar
  through the deck title strip (y=86–376 at native size). It stops above both
  overview waveforms. The right-hand overlap covers part of Deck 2’s title;
  Deck 1 is on the left. The track list and search use the remaining width.
  The same Show/Hide button stays at x=710 in both states.
  Tap Rekordbox → MANTACORE → Playlists or Folders, then a collection to filter
  the track table. Back returns one level; no small disclosure-arrow targets
  are needed. Source visibility/default preferences remain under Choose sources
  at the root. Search, selection and the current collection survive panel and
  tab changes. The named collections are illustrative, using the demo tracks.
- Three effects, exclusive 1/2/Master routing, preserved depth on enable.
- Settings for engine, waveform frame rate, tempo range, quantize, split cue
  and buffer. Buffer changes require confirmation. Read-ahead and cache choices
  are represented as startup settings.
- Record timer, reset and a comparison with the actual Pi screenshot.

The key-lock choice stays at RubberBand pending the user's listening comparison.
The waveform setting starts at 60 fps. Audio, effects, CPU lamps, library data
and eject are illustrative. Reduced motion stops waveform scrolling.

The recovered cache patch can fall back to the USB original, and a real eject
interlock is still unimplemented. The preview deliberately blocks an uncached
loaded deck. Nothing here verifies audio quality, lower buffers, safe physical
USB removal, or native Qt rendering of a new skin.

## Validation on November 8, 2026

Headless Chromium checked the actual file at 800, 728 and 390 px viewport widths.
The 800 px layout measured exactly 800×480 with a 36 px bar and 444 px app. No
horizontal page overflow or out-of-stage buttons/selects occurred in Perform,
Browse, FX, settings or sources. Twenty-nine interaction/geometry checks passed,
including active-tab stability, playing-deck load rejection, loading/cached/
uncached eject cases, short-hold cancellation, source scope/default selection,
buffer cancellation, and FX depth retention. No JavaScript errors were reported.
Screenshots are in `qa/`; `review.html` is a state-comparison gallery of those
captures. These checks validate the HTML, not the native Pi implementation.

The loop/key/folder revision passed 57 focused checks: both deck loops, fractional
and long intervals, wraparound, half/double limits, exit/reloop/cue, clearing loops
on track replacement, Camelot formatting, source pane and nested folder state,
selection retention and bounds at 800, 728 and 390 px. The earlier 29 checks for
media, FX, buffer confirmation and layout also pass with the collapsible pane.
The full interactive `index.html` is now shown directly in the conversation.

The taller right-panel revision passed focused interaction and geometry checks
at 800, 728 and 390 px: unchanged toggle bounds; folder/Back navigation; playlist
filtering; search and selection retention; valid deck loads; source preferences;
USB removal/reinsert; panel restoration after tabs/settings; and the unchanged
712 px translucent loop overlay. No JavaScript errors occurred. Updated Browse
captures include `qa/browse-sources.png` and `qa/browse-playlists.png`.
