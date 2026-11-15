# Field-grounded native UI tuner

## Editable workshop · owner revision 3

The owner approved the final pane-top Sources placement on November 11, 2026.
The exact delivered HTML is now the native implementation target recorded in
`docs/ideas/FIELD-FIXES-20261111.md` and the existing climb record. UI approval
is not native validation or release acceptance. No further visual-preference
export is required to begin the bounded local implementation slice; preserve
the approved reference rather than redesigning it.

The current standalone workshop implements the owner's November 11 layout
directions as a non-operational proposal. Open the generated HTML directly;
use **Save editable HTML copy** to retain the settings and per-screen notes
inside another standalone file. Reopening that copy restores the draft.
JSON export/import is also supported, with baseline and input validation.
It does not write back into the original file, save automatically, or install
anything on the Pi. Revision 2 JSON drafts retain their choices and notes;
the new desktop-bar preference defaults to visible and navigation starts at
the sources root. Unsupported older formats are refused.

Tracks keeps **Show / Hide** for the ordinary files/folders overlay, including
**Back** navigation. The **Sources** chooser sits at the top of that pane,
above Back, rather than beside Show / Hide on the Browse toolbar. It
selects which sources appear and stays open for multiple changes until Close.
Folders and tracks in the proposal are offline samples, not scanned files.
Actions has deck loading sketches, visible/reorderable columns and the native
Actions audit. FX keeps its ordinary native HTML dropdown, with only the empty
selection text changed to “Select effect…”, and the already-proposed MIX box.
Media combines Load/Eject and exposes clearly labelled hypothetical states;
the default reflects the current broker-OFF denial. Settings separates Advanced
and previews the native range choices through ±90%. Playback and Interface use
two columns; Interface adds **Hide / Show top bar** for the desktop strip with
Desktop, Mixxx and Speaker. Hiding it reclaims 36 px without hiding the app's
Settings tab. The setting and folder path survive HTML/JSON saving.
Deck controls appear only
on Decks. All buttons use 2 px corners. Native implementation remains pending.

Current owner-review output:
`deploy/recovery-20261111/ui-revision2/MixPi-UI-Workshop.html`.

This is a local, offline **review surface**, not a new Mixxx implementation.
It compares the November 11 owner photos, the earlier native Browse capture,
and an explicitly labelled restoration sketch. It never opens audio/devices,
records, mounts/ejects, writes Qt files or changes the Pi.

Build from the accepted overlay and locally oriented photo copies:

```sh
python3 tools/ui-tuner/build.py --photos deploy/recovery-20261111/field-stocktake/photos --output deploy/recovery-20261111/field-stocktake/ui-tuner.html
python3 -m unittest discover -s tests -p test_ui_tuner.py -v
```

To include the already captured native Pi baseline, add
`--native-evidence deploy/recovery-20261111/field-live`. This embeds eight
named screenshots and binds their hashes to the retained inventory's digest,
observation time, boot ID and binary hash. The entire profile/inventory is not
embedded. Missing or invalid requested images fail rather than substituting
the sketch. This reads local evidence only: it does not connect to the Pi or
prove the proposed repair renders correctly. Draft preference exports retain
this provenance without copying the screenshot payloads into the JSON.

The default overlay is the accepted incremental candidate under `deploy/`.
The builder checks its exact hash and reads two exact regular archive members,
never extracts the archive or executes its contents. It embeds photographs and
the historical native capture; generated HTML and personal photographs remain
under ignored `deploy/`, not committed as portable public assets.

Open the generated HTML directly. Tune track font/row height/columns, source
pane visibility/width, slider thickness/thumb, selected-row treatment and
settings grouping. Edits remain in this page until **Export preferences**;
download the JSON to retain them. Reload/reset discards unsaved edits. No
automatic localStorage, remote upload, automatic approval or deployment.

The historical reference is **not** the current live Pi. The photos are owner
field evidence, not pixel-perfect screenshots; the sketch uses example tracks
and fixed 800×480 geometry with a 36 px desktop bar. It scales uniformly rather
than rearranging controls. Colors come from the shipped native stylesheet, but
HTML/Qt font metrics and rendering differ. Initial preparation did not fetch
the running profile. Subsequent read-only inspection supplies actual native
screens and installed-file identities in
`deploy/recovery-20261111/field-live/REPORT.md`; use `--native-evidence` to
include those observations alongside the photo/reference comparison. Without
that option the page explicitly states that native evidence is absent.
Reconcile preferences with those screens before implementation. Native
acceptance remains required.

The one climb contract is in the adjacent `climb-contract-tuner` app, record
`mixpi-field-fixes-20261111`, not this preview. The final delivered HTML approval
is bound in that record; later preference changes require reconciliation rather
than silently changing the implementation target. See
`docs/ideas/FIELD-FIXES-20261111.md` for the field stocktake and release boundaries.
