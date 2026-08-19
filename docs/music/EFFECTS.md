# Effects notebook

Mixxx provides effect units that can route to decks and other buses; each unit
can chain up to three effects. The small rig should favor a few repeatable,
auditioned moves over dense chains that hide mistakes or increase CPU load.

## Starter recipes to test

| Name | Chain/action | Use | Guardrail |
| --- | --- | --- | --- |
| Clean transition | Filter/QuickEffect only | Remove bass/space during a blend | Return to neutral before the next mix |
| Echo exit | Echo, modest wet mix | Exit a vocal or hard cut | Trigger on phrase, then lower outgoing fader |
| Short loop build | 4- or 8-beat loop, shorten carefully | Build tension before incoming drop | Confirm beatgrid and quantize first |
| Reverb tail | Short reverb send | Soften an abrupt ending | Avoid washing out bass-heavy overlaps |
| Texture moment | Flanger/phaser at low mix | Brief color during a breakdown | Use sparingly; audition in headphones |
| Transition sweep | Riser sample during final phrase | Land a fade or drop at the sweep endpoint | Treat as sampling; keep below the main track |

## Experiment record

```text
Date:
Recipe:
Track pair:
Effect order and values:
Where triggered (bars/cue):
CPU/audio result on Pi:
Keep/change/remove:
```

## Rules for this Pi

- Preview a new chain in headphones and test it under two-deck load.
- Save only recipes that can be repeated with the available controls.
- Record controller assignments alongside the recipe.
- Keep an instant dry/reset control available.
- Treat current `mixxx.cfg` in this repository as a reference only: its installation is commented out, so runtime settings on the Pi may differ.
