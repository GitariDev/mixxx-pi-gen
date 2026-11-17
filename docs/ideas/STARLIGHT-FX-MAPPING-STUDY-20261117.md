# Starlight FX mapping study (R-17b), 2026-11-17

Owner (plan question 5): "Alright but let's see if we can keep the 3 effects switcher between deck 1 deck 2 and master then have another mode. The starlight does have effects settings, maybe we just need to map them."

This is a study and a proposal. Nothing in this climb changes a controller mapping. Source: pinned Mixxx `3ebac449`, `res/controllers/Hercules DJControl Starlight.midi.xml` (cited as XML) and `Hercules-DJControl-Starlight-scripts.js` (cited as JS).

## What the Starlight's effect controls do today

| Control | Mapping | Line |
|---|---|---|
| Deck A pads 1-3, FX mode | `[EffectRack1_EffectUnit1_Effect1..3],enabled` (toggle effect 1-3 of unit 1) | XML 444-470 |
| Deck A pad 4, FX mode | `[EffectRack1_EffectUnit1],group_[Channel1]_enable` (unit 1 on deck 1) | XML 477-481 |
| Deck A Shift + pads 1-3 | `[EffectRack1_EffectUnit1_Effect1..3],effect_selector` (next effect) | XML 488-514 |
| Deck B pads 1-3, FX mode | `[EffectRack1_EffectUnit2_Effect1..3],enabled` (unit **2**) | XML 706-732 |
| Deck B pad 4, FX mode | `[EffectRack1_EffectUnit2],group_[Channel2]_enable` | XML 739-743 |
| Deck B Shift + pads 1-3 | unit 2 `effect_selector` | XML 750-776 |
| FILTER knob, each deck | `[QuickEffectRack1_[ChannelN]],super1` (the deck's quick-effect filter) | XML 874-876, 971-973 |
| Controller start | sets every unit-1 and unit-2 effect's `meta` to 0.6 and both units' `mix` to 1 | JS 94-102 |

So the "effects settings" on the Starlight are the FX pad mode (on/off per effect, Shift = next effect, pad 4 = send the unit to that deck) and the filter knobs. There is no depth or mix knob for the effect units. The controller also resets depth and mix every time Mixxx starts, whatever the screen set last time.

## What the redesign does now (no mapping change)

FX page mode **FX 1 · deck A pads** shows unit 1 with today's DECK 1 / DECK 2 / MASTER switcher, mix and three effects; mode **FX 2 · deck B pads** shows unit 2 the same way. Every Starlight effect action then shows on the screen.

## Options for a later mapping change (owner's call)

| Option | What changes | For | Against |
|---|---|---|---|
| A. Keep stock (today) | Nothing | No mapping to maintain; both units visible | Two units to think about |
| B. One unit for both decks | A MixPi copy of the mapping: deck B's FX pads 1-3 drive unit 1's effects too; deck B pad 4 sends unit 1 to deck 2 | Matches the single DECK 1 / DECK 2 / MASTER switcher the owner wants to keep; FX 2 mode no longer needed | A mapping file to keep in step with Mixxx updates; deck A and B pads then share effects |
| C. Pads follow the screen | A MixPi script mapping: the FX pads drive whichever unit the FX page shows (`[MixPi],fx_unit`) | One set of pads, two units | Most code; the pads' meaning changes with a screen state the DJ may not be looking at |
| D. Keep depth and mix | A MixPi copy that drops the start-up `meta`/`mix` reset (JS 94-102) | The screen's depth and mix (now saved within a second, R-13) survive a restart | Same maintenance cost as B |

Recommendation for the owner after testing the FX page: **B together with D**, as one MixPi mapping file installed beside the stock one and selected in Preferences › Controllers, so the stock file stays untouched and can be chosen again at any time.
