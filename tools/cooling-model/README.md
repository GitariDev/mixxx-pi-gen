# DJ box cooling model

`index.html` is a self-contained page: open it in any browser, no server or
install. It models the Pi 4 inside the cardboard DJ box as three temperatures:
chip, box air and room. An airflow solver handles vent holes, cable leaks,
stack effect and straight-line fan curves.

- **Calibration:** the one fitted number is the still-air conductance from the
  board and heatsinks to the box air. It is tuned so the sealed box at idle
  matches the reading under **Calibration** (67.5 °C on 2026-11-08). Change the
  box size or the room temperature at that reading, and the model re-calibrates.
- **Ranges:** every other assumption has a range in the **Assumptions** table.
  The "likely" figures are the 10th–90th percentiles of 32 re-runs across those
  ranges, each one re-calibrated.
- **Saved state:** inputs persist in the browser's local storage.
  **Reset assumptions** clears edited values.
- **`log-temps.sh`** logs a 30-minute test on the Pi over SSH and writes CSV to
  stdout. Drop the CSV onto the page's 30-minute chart to compare it with the
  prediction.

Plan, wiring and test protocol: [`docs/ideas/COOLING-PLAN.md`](../../docs/ideas/COOLING-PLAN.md).

The illustrated 16-step manual is inside `index.html#build`;
`build-manual.html` is a standalone copy with tabs for each assembly stage.
The pin diagram is conditional: the screen’s occupied pins still need visual
confirmation. Mounting changes can wait until the required parts arrive.
