# Wave C3, builder S3 (skin repairs after build C)

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first. It is part of this brief.

**No design of your own; where the spec is silent, build B stays.**

Base: `feat/pi-performance-target` at the head the orchestrator names. Build C (`135a4bf`) is on the test card. These repairs are skin only, so the orchestrator delivers them in place (no new build). Card shots of build C: `deploy/ui-redesign-20261117/acceptance-C/conformance/k*.png`.

## Items (each a deviation from a mockup, seen on the card)

1. **Clear samples popover** (spec s6; `mockups/m-sampler-clear.png`; card shots `k12-clear.png`, `k13-clear-ticked.png`, `k14-clear-tickbox.png`):
   - With two pads loaded, the sheet is x 160-640, y 124-356 and its list shows one row at a time, with a scroll bar that has arrow buttons. Drawn: the sheet is x 160-640, y 82-398, and the list shows every loaded pad's row with no scrolling (three rows drawn). Make the list show all loaded rows up to the space the drawn sheet gives; a scroll bar only when rows do not fit, and then the plain 24 px bar of spec section 1 (no arrow buttons).
   - Tapping a row's name or duration does not tick it; only the tick box does (`k13` vs `k14`). Drawn and specified: the row is the tick row (spec section 1 "Ticked rows"). Make the whole row toggle its tick.
2. **Media page open** (spec s13; `mockups/m-media.png`; card shot `k20-media.png`): while the Media page is open (`[MixPi],screen` 2), the tab that was open (FX in the shot) stays lit and the USB chip is not lit. Drawn: no tab lit and the chip lit, the same way the gear is lit and no tab is lit while Settings is open (`k19-settings-interface.png`).

## Files you own

`mixpi-performance.py`, `mixpi-performance.qss`, `pioneered-touch.qss` (only if needed), `tests/test_performance_skin.py`. No Mixxx source, no native test.

## Checks

Generated-XML tests for each item (the popover's list height for 1, 2, 4 and 8 loaded pads; the row-wide tick; no arrow buttons; chip lit and tabs unlit on screen 2), the Mac suite. Give the popover's new hit map (✕, each row, CANCEL, CLEAR (n)) for two loaded pads.
