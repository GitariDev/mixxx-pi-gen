# DJ library tools — metadata and beatgrid issue log

Logged: 2026-09-12. Status: researched proposal; neither tool is implemented.

These are general DJ preparation tools, initially targeting Rekordbox. They can
live alongside the Mixxx Pi notebook without becoming requirements of the Pi
image. The requested outcome is two Python tools that can also be distributed
as executable files.

| ID | Problem | Intended result | Status |
| --- | --- | --- | --- |
| DJ-001 | Unreliable BPM/key metadata and inconsistent genres | Reviewed metadata written to music files, recognized by Rekordbox, and recoverable after later changes | Open; provider access and Rekordbox compatibility need verification |
| DJ-002 | Incorrect beat positions, downbeats, and drifting grids | Analyze the actual local recording and import a corrected grid into Rekordbox | Open; benchmark and import prototype needed |

## DJ-001: Enrich and manually correct track metadata

**User requirement:** use SongData.io for BPM and key; use Spotify for the main
Genre field; use Every Noise at Once genres for Rekordbox's My Tags. Allow manual
corrections and prevent routine processing from immediately replacing them.

### Findings that affect the design

- **SongData.io API access is unconfirmed.** Its public site provides song and
  playlist BPM/key lookup, but this research did not find documented public API
  endpoints, authentication, or an audio-upload API. Keep it as the preferred
  provider, with an integration task to verify access. Do not confuse it with
  the separately named `songdata.org` service. [SongData.io](https://songdata.io/)
- **Catalog values are references, not guaranteed ground truth for a local
  file.** A remix, edit, live performance, or altered-speed copy may differ from
  the catalog recording. Match the recording before accepting its values, and
  retain source information and manual overrides.
- **Spotify genres describe artists.** The API does not establish one canonical
  primary genre for each song, and the artist `genres` field is now marked
  deprecated. Fetch artist genre candidates when available; let the user select
  the main genre and preserve that choice. Missing or empty data must not erase
  an existing genre. [Spotify Get Artist](https://developer.spotify.com/documentation/web-api/reference/get-an-artist)
- **Every Noise is a related taxonomy, not independent confirmation.** Its maps
  were built from Spotify data. Treat artist associations as genre suggestions,
  with a recorded source/snapshot date. Historical coverage is useful, but
  current coverage and a supported API are unconfirmed; the main site could not
  be fetched during this research. An accessible creator-hosted map describes a
  dated Spotify dataset. [Every Noise map and explanation](https://furia.com/everynoise_public/engenremap-ninja.html)
- **Native My Tags need their own integration.** The documented Rekordbox XML
  format includes Genre, Comments, key, and grids, but no native My Tag field.
  Rekordbox documents copying My Tags into Comments; that does not establish a
  reverse import path. A Comments fallback must be labeled as such and does not
  satisfy the native My Tags requirement. [XML specification](https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf),
  [Rekordbox manual, pp. 30–31](https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf)

### Proposed behavior

1. Read a file or folder of local tracks and show existing title, artist,
   recording identifiers, duration, BPM, key, and genres.
2. Resolve catalog candidates using identifiers such as ISRC when available,
   then title, artist, version, and duration. Distinguish original, remix,
   extended, radio, clean, and explicit versions. Ambiguous matches go to review.
3. Retrieve SongData BPM/key and Spotify artist genre candidates through verified
   provider adapters. Report missing access explicitly. Never fabricate an API
   or silently substitute a different provider.
4. Suggest Every Noise genres from a verified artist association or user-reviewed
   mapping. A genre's presence in the taxonomy alone does not prove that it fits
   a particular song. Deduplicate labels and retain their provenance.
5. Save a reviewable change plan. Manual edits take precedence over provider
   refreshes until explicitly changed. Allow individual fields to stay untouched.
6. Apply approved fields to music tags using Mutagen, preserve artwork and other
   tags, and verify the saved values. Keep an original-file backup and a per-file
   change record for restoration. Preview is the default; writes are explicit.
7. Refresh Rekordbox metadata and import any accompanying XML using a workflow
   tested against the user's exact version. Show unresolved steps separately
   from successful file writes.

For an initial MP3 implementation, candidate ID3 mappings are `TBPM` for BPM,
`TKEY` for musical key, and `TCON` for the selected Spotify-derived genre.
Store exact tempo and normalized key in the review record even when a tag
format cannot retain their full representation. FLAC, AIFF, and M4A need
separate format adapters and actual Rekordbox import tests before being listed
as supported. The first format remains to be confirmed.
[Mutagen ID3 frame documentation](https://mutagen.readthedocs.io/en/latest/api/id3_frames.html)

### Keeping corrections intact

Maintain a local JSON record for each recording, containing its identity,
provider URLs/IDs, retrieval dates, original values, proposed values, reviewed
values, manual overrides, and grid reference. Identify the audio independently
of mutable tags; a whole-file hash changes when tags are written. Record file
hashes separately for backup and conflict detection.

Rekordbox's **Reload Tag** operation imports external tag edits, while
**Analysis Lock** prevents track re-analysis and grid editing, including key
analysis. These solve different problems. After testing the import sequence,
disable unwanted automatic BPM/key analysis, import the reviewed result, verify
it, and enable Analysis Lock. Locking analysis does not make every metadata
field immutable or protect against deliberate edits and tag reloads. The JSON
record provides a way to detect and reapply changes; it is not a Rekordbox lock.
[Rekordbox manual, pp. 26 and 92](https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf)

For native My Tags, investigate a version-specific Rekordbox adapter and test it
on a disposable library first. Pyrekordbox documents separate tag definitions
and track-to-tag relationships; that is a useful research starting point, not
proof of compatibility with the installed Rekordbox version. Any eventual
database writer must handle transactions, backups, concurrent access, and
Rekordbox's bookkeeping. The initial file-tag/XML prototype should not write the
live library database. [Pyrekordbox database format](https://pyrekordbox.readthedocs.io/en/latest/formats/db6.html)

### Acceptance criteria

- [ ] Exact recording matches and ambiguous versions are distinguishable before writes.
- [ ] Manual BPM, key, and genre choices survive reruns and provider refreshes.
- [ ] Spotify-derived main genre and Every Noise genre suggestions remain separate.
- [ ] Missing providers or genre fields leave existing values intact.
- [ ] Backup/restore and interrupted-write recovery work; unrelated metadata and audio are preserved.
- [ ] Rekordbox reads the intended fields on each supported file format.
- [ ] Reviewed key/BPM/grid survive restart and attempted re-analysis with Analysis Lock enabled.
- [ ] Every Noise labels appear as actual native My Tags and remain attached after restart; Comments alone do not pass.

## DJ-002: Analyze audio and repair Rekordbox beatgrids

**User requirement:** an executable tool that sets more accurate grid points
using a better algorithm, still to be selected.

The tool must distinguish tempo, beat alignment, and the first beat of each bar.
A correct BPM can still have the wrong offset or bar numbering. An average
catalog BPM also cannot describe live tempo drift or a tempo change.

### Algorithm candidate and prototype

Start by evaluating **Beat This!**, a published beat/downbeat tracker with both
a Python interface and a command-line tool. Its `File2Beats` interface produces
beat and downbeat timestamps from an audio file. The project supports CPU
inference and publishes model weights. It is a candidate to benchmark, not a
verified improvement on this library. [Official implementation](https://github.com/CPJKU/beat_this)

1. Decode the entire local recording on a consistent timebase, accounting for
   decoder/encoder delay. Analyze beats and downbeats, including quiet intros,
   breakdowns, and outros.
2. Compare inferred tempo with reviewed catalog BPM as a sanity check. Surface
   half/double-time and conflicting evidence for review instead of forcing the
   audio onto the catalog value.
3. Fit a stable grid for constant-tempo material. Fit a limited set of tempo
   segments when the audio actually changes tempo; avoid exporting model timing
   jitter as hundreds of unnecessary tempo changes.
4. Validate downbeat/bar alignment separately. Start with a documented 4/4 scope;
   flag unsupported meters and ambiguous sections for manual review. Allow
   manual BPM, beat-one, offset, and tempo-segment corrections.
5. Produce a timing report and an audible click-track preview. Include beginning,
   middle, end, and transition checkpoints so long-term drift is visible.
6. Write reviewed results to a separate Rekordbox XML file, preserving the
   exported collection's track references, playlists, cues, and loops. Existing
   cue times stay intact; questionable alignment can be flagged for review.
7. Import into a test library, compare the resulting grid against the audio, and
   use Analysis Lock after verification. Record which import behaviors were
   actually tested for new tracks and tracks already in the collection.

Rekordbox documents XML tempo markers using `Inizio` (seconds), `Bpm`, `Metro`,
and `Battito` (beat number within the bar). This is the initial interchange
route; writing a BPM tag alone is not a beatgrid export. No binary analysis-file
editing is required for the first prototype.
[Rekordbox developer documentation](https://rekordbox.com/en/support/developer/),
[XML specification](https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf)

### Acceptance criteria

- [ ] Benchmark at least 30 representative tracks against existing Rekordbox grids and manually checked reference beats.
- [ ] Include steady electronic tracks, syncopation, sparse intros, live drums, tempo changes, and different edits of the same song.
- [ ] Report beat timing error, downbeat correctness, half/double-time errors, drift, and manual correction time separately.
- [ ] Proposed initial target: reviewed checkpoints within 20 ms on steady-tempo test material, with correct bar alignment. This is a project target, not a published guarantee.
- [ ] Compare automatic outputs before manual correction; use held-out tracks and retain failure cases when choosing the algorithm.
- [ ] Fewer corrections are needed than with the Rekordbox baseline; uncertain tracks enter review rather than receiving a success label.
- [ ] Imported XML preserves cues, loops, and playlists and works for both new and existing collection entries.
- [ ] Grid results survive restart and attempted re-analysis with Analysis Lock enabled.
- [ ] Batch processing can resume without redoing reviewed work or replacing manually corrected grids.

## Shared build plan

| Step | Deliverable | Completion evidence |
| --- | --- | --- |
| 1. Resolve dependencies | Confirm Rekordbox version, audio formats, SongData access, Spotify genre response, and Every Noise source | Small documented sample from each provider; no assumed endpoints |
| 2. Prove import behavior | One copied track with edited tags, XML grid, and preserved cues | Verified values and grid in the user's Rekordbox version after restart |
| 3. Build metadata CLI | Preview/apply/restore, manual overrides, recording matching, provider adapters | DJ-001 criteria except native My Tags passed |
| 4. Benchmark grid engine | Beat This! analysis, comparison report, manual correction input, XML export | DJ-002 timing and import criteria passed |
| 5. Complete native My Tags | Version-tested tag assignment adapter | Actual My Tag filtering works and existing assignments survive |
| 6. Package executables | Documented Python entry points and native distributions | Clean-machine tests, including audio decoding and model loading |

The existing [`songdata_to_crate.py`](../../tools/songdata_to_crate.py) converts
SongData playlist PDF exports to JSON/PDF. Its JSON can seed a manually reviewed
offline prototype while API access is unresolved. It does not identify local
recordings reliably by itself, write audio metadata, or generate beatgrids.

Proposed command names, **not currently available**:

```text
dj-metadata scan /path/to/music --plan review.json
dj-metadata apply review.json --backup-dir /path/to/backups
dj-metadata restore /path/to/backups/run-manifest.json
dj-grid analyze /path/to/music --output grids.json
dj-grid export grids.json --collection collection.xml --output corrected.xml
```

Use a shared Python core with separate command entry points. Keep per-file
errors visible, support resuming batches, and pin tested dependency/model
versions. Start the beat analysis on the preparation computer; Pi performance
is a later measurement, not an assumption.

PyInstaller is a candidate for native executable distribution. Each operating
system needs its own build and test. A self-contained beat-analysis executable
must account for its audio decoder and model weights; test a folder bundle
before attempting a single-file package. [PyInstaller packaging documentation](https://pyinstaller.org/en/stable/operating-mode.html)

## Information to collect before implementation

- Installed Rekordbox version and target operating system(s).
- Audio formats and approximate collection size.
- Any SongData.io API documentation/access already available to the user.
- A small set of problem tracks and their current exported Rekordbox grids.
- Spotify developer access and whether artist genres are returned for the actual app.
- A usable Every Noise source and a plan for artists missing from its coverage.

No music files or Rekordbox databases were changed during this research.
