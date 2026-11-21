# Climb timeline

A local, standalone page for the MixPi UI redesign climb (record
`mixpi-ui-redesign-20261117`). It shows every build and council round in time
order, the seat scores against the 9/10 target, the findings and bugs with
their status, the waves (changes) that fixed them, and the owner's decisions
with their exact words.

- `climb.json` is the data and the single source of truth, hand-curated from
  `docs/ideas/UI-REDESIGN-RESULTS-20261117.md`, plan sections 11 and 12, spec
  sections 2a to 2g, the briefs, and the untracked council and acceptance
  evidence under `deploy/ui-redesign-20261117/`.
- `build.py` validates `climb.json` and writes `climb-timeline.html`.
- `timeline.source.html` is the page template (plain HTML, CSS and JS).
- `climb-timeline.html` is the built page, committed so it is ready to open.

## Open it

Open `tools/climb-timeline/climb-timeline.html` straight from disk. It needs no
server, network or CDN, and it sends nothing anywhere.

- **Timeline:** select a build or round (or use ‹ › and Esc in the panel) to
  see its scores, blockers, what changed after it, its findings, and links to
  the reports, mockup/card pairs and shots.
- **Scores:** one line per seat across the rounds, with the target line.
  Hollow marks show a seat's score without a hard cap. A table view is under
  the chart.
- **Findings:** filter by status, by the round or build that found it, by
  severity, or by text.
- **Load JSON…** shows an edited `climb.json` without rebuilding; it is
  validated first and nothing is saved. **Download JSON** saves the data shown.

Evidence links resolve from the repo root (`../../` from this folder). The
`deploy/` evidence is untracked, so it exists only in the main checkout. When
an image is missing, the page shows its path as text. If you open the page
from another checkout, set **Evidence folder** at the bottom of the page to a
relative path that reaches the main checkout's root.

## Rebuild

```sh
python3 tools/climb-timeline/build.py            # validate and write climb-timeline.html
python3 tools/climb-timeline/build.py --check    # validate only
python3 -m unittest tests.test_climb_timeline -v
```

To also check the scores against each report's `Score: N/10.` line and that
every evidence path exists, point the tests at the checkout that holds
`deploy/`:

```sh
MIXPI_EVIDENCE_ROOT=/path/to/main/checkout python3 -m unittest tests.test_climb_timeline -v
```

The test suite fails if the committed `climb-timeline.html` is out of date, so
rebuild after every edit to `climb.json` or the template.

## Add a build or a council round

`events` is in time order; the validator rejects a date that goes backwards.

1. **Build L (or the next build):** edit its `pending` entry (or add one before
   the round that scores it). Set `date`, `status: "done"`, `head`, `pigenRuns`,
   `patches`, `deb`, `duration`, `kit`, the `gate` (native passed/total/skips,
   the commit it ran at and the log under `gates/`; the Mac run) and the
   `acceptance` counts with the report path. `pass + fail + blocked` (plus
   `other`, if any) must equal `checks`. Add its pairs under `evidence.pairs`.
2. **Council round 7 (or the next round):** set `date`, `status: "done"`,
   `head`, `build`, and one `scores` entry per seat. Copy each score from the
   report's `Score: N/10.` line. When a hard cap applies, set
   `cap: {"limit": N, "reason": "…"}` and, when the report gives one, the
   `uncapped` score. A stand-in seat sets
   `standIn: {"model": "…", "replaced": "…", "reason": "…"}`; otherwise `null`.
3. **Waves:** add each wave with the event it started `after`, the build it was
   `shippedIn`, its patch file names, native test modules and commits. Use
   `status: "pending"` until its build lands, and `"reverted"` with
   `shippedIn: null` for a wave that was backed out.
4. **Findings:** add each finding with where it was `found` (`also` for other
   rounds or builds that saw it), a `severity` (`critical`, `major`, `minor`,
   `info`) and a `status`:
   - `fixed` or `pending`: name the `wave`;
   - `owner-accepted`: name the `decision`;
   - `listed`, `open` or `closed`: add a `note`.
5. **Owner decisions:** add the spec or plan section with its `date`, the event
   it comes `after`, its `source` file, and `items` with the owner's exact words
   in `quote` (or `null`). The tests check each quote appears verbatim in its
   source.
6. Run `build.py`, then the tests, and commit `climb.json` with the rebuilt
   `climb-timeline.html`.

Unknown values are `null`; say why in the nearest `note`. Paths are
repo-relative, with no URL, no `..` and no leading `/`. The validator also
rejects email addresses and home paths, so no personal details reach the page.
