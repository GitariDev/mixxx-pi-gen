# Validation — 2026-10-03

## Automated checks

- 44 pytest tests passed; Ruff passed; TypeScript and Vite production build passed.
- MP3, FLAC, AIFF and unprotected M4A: all eight writable fields round-trip,
  Unicode is preserved, decoded PCM hashes remain identical, and embedded artwork,
  BPM/key and unrelated tags survive.
- Indexing covers stable IDs, unchanged rescans, relocation, missing drives,
  cached evidence, accepted-value conflicts and stale/rejected proposals.
- Matching rejects distinct versions/remixers and does not assign an unrelated
  compilation or reissue. Duplicate reports distinguish exact bytes and versions.
- Apply/restore tests cover stale files/libraries, per-destination status,
  interrupted writes, manual locks, recovery and protection of newer edits.
- API tests reject foreign Host/Origin and missing write tokens, preserve analysis
  fields, and keep Apply disabled without a verified adapter.
- A non-failing Starlette warning notes its upcoming test-client HTTP transport
  change; the existing httpx-based tests all pass.

## Actual collection, copied-library test

Installed rekordbox: 7.2.18; adapter: pyrekordbox 0.4.4.

A disposable encrypted database copy containing 3,434 entries passed the metadata
write/reopen/restore probe. Checks cover 47 tables, preserve unrelated content,
playlist/cue/My Tag data, and account for required local update bookkeeping.
The original live database hash still matched the initial copy after testing.

Two real import/rescan jobs completed with 3,434 entries, no duplicate database
records, 496 accessible files, and zero audio-read failures. Missing entries are
retained. File formats in this collection: 2,243 MP3, 562 FLAC, 476 WAV, 151 M4A,
one M4V and one MP4. WAV/video entries are inspection-only for metadata writes.

MusicBrainz returned three candidates for a public sample lookup. Full-library
provider enrichment was not run. AcoustID requires a user application key and
fpcalc; live AcoustID access has not been tested.

Local audio Range requests returned HTTP 206 with the requested 32 bytes;
embedded album artwork returned HTTP 200/image/jpeg. No original music files
were modified.

## Browser verification

Checked the running app in the Codex in-app browser:

- Desktop 1440px, tablet 1024px, phone 390px: no horizontal page overflow.
- 720px CSS viewport reflow (equivalent available width to a 1440px browser at
  200% zoom) passed. Actual browser zoom could not be changed by the available
  shortcut, so a literal 200% browser zoom test is not claimed.
- Search, sorting controls, mobile detail/back navigation, metadata tabs,
  keyboard arrow-tab selection, manual correction → review, duplicate warnings,
  and real import/rescan exercised.
- Long titles, Unicode artist names, actual album artwork, nested playlist paths,
  missing artwork fallback, empty and demo states inspected.
- Reduced-motion CSS disables transitions. OS-level reduced-motion emulation was
  not exercised. Visible focus and contrast tokens reviewed.

Screenshots are local and ignored: `.data/qa/desktop.png` (demo),
`.data/qa/library-desktop.png` (actual library), and `.data/qa/mobile.png`.

## Remaining release gate

**The rekordbox application's own restart/readback test has not been completed.**
SQL reopen is not equivalent to opening the copied library inside rekordbox.
Live Apply remains locked; the compatibility report explicitly records
`rekordbox_restart_verified: false` and no rekordbox-verified write formats.

A disposable rekordbox application library must verify each format and field,
playlist membership, cues, grids and native My Tags after restart and after
restoration. Preserve the user's existing library when arranging that test.

Smart My Tags, duplicate consolidation, cloud sync, Linux packaging and beatgrid
repair remain the agreed later milestones, not implied implemented features.

## Local editing and import follow-up

- Direct-save tests cover all four supported audio formats, offline save/reconnect,
  manual locks, stale editors, external conflicts, running-rekordbox queuing,
  interrupted writes, restart recovery and refusal to restore over newer changes.
- A simulated verified adapter tests offline native-only synchronization and
  destination restoration. This is an operation-layer test, not a replacement for
  the real rekordbox application compatibility gate above.
- Import tests cover files, recursive folders, copy and verified move, duplicate
  skips, collisions, changed sources, stale previews, interrupted publishing,
  retry, symlink escape rejection, restart receipts and simulated exFAT fallback.
- API tests cover the new token-protected browser, settings and edit endpoints.
- An isolated fixture app on port 5178 was exercised through the browser: direct
  and offline edits, folder selection, preview, copy into the configured collection,
  persistent Dex entry and completed receipt with a rekordbox playlist handoff.
- The real rekordbox app was running during UI testing. Song Dex correctly queued
  file tags while committing fixture corrections to the Dex. No user music was
  edited or moved during these checks.
- Actual collection remains 3,434 entries, including 2,938 offline paths at the last
  scan. Settings detects the existing Documents/GTsCollection folder.
- Before the additive schema update, the actual Dex catalog was backed up under
  `.data/backups/catalog-before-local-tools.sqlite3`.
- Follow-up layouts at 1440px, 1024px and 390px had no horizontal overflow;
  the narrow import receipt and offline metadata editor were visually inspected.
  Screenshots: `.data/qa/import-mobile.png`, `.data/qa/local-tools-desktop.png`
  and `.data/qa/local-tools-mobile.png`.
- Final availability check completed over all 3,434 paths while rekordbox was
  running: 496 available, 2,938 offline. The actual catalog still has no new
  manual edits or music imports from this testing session.

## Filtering and native My Tags follow-up

- Added native My Tag/category reads, additive catalog migration, a per-track
  My Tags tab and a saved-scan backfill. Tests cover ID/category preservation,
  tag clearing on rescan, retention during availability checks, idempotent schema
  upgrades and refusal to load a different library's snapshot.
- Six frontend logic tests cover combined tag/range/key/genre/format/playlist
  filters, any/all semantics, unknown versus confirmed untagged, numeric ordering,
  stable ties and natural key/tag sorting.
- Read the existing snapshot: 3,434 entries loaded, 20 tagged tracks, six assigned
  tag names. Live rekordbox data was not written.
- Browser check: Afro OR Bootleg, BPM 120–130, descending BPM returned three
  recordings at 125.5, 125 and 123.99 BPM; native Bootleg assignment displayed
  under Genre in the new tab. 390px view had no horizontal page overflow.
- Final checks: 48 backend tests, six frontend filter/sort tests, Ruff and the
  production TypeScript/Vite build passed. Desktop filter spacing was visually
  corrected; 1024px and 390px layouts do not overflow horizontally. Screenshots:
  `.data/qa/filters-desktop.png` and `.data/qa/filters-mobile.png`.

## File-picker visibility and ordering

The picker now exposes separate Audio files and Folders views with counts and
filename search; selections persist across both views. Verified MP3/FLAC visibility
and mixed file/folder selection in the actual collection, without starting an
import. Both views sort by Date Added descending using macOS metadata, falling
back to filesystem creation/modification dates on unindexed volumes. TypeScript
production build and Ruff passed; the phone layout has no horizontal overflow.

## Direct-write groundwork — 2026-10-10

rekordbox was open during this work, so nothing touched the live library; every
database test ran on copies of the 2026-09-28 scan snapshot, with the "rekordbox
is running" guards bypassed for those copies only.

- Playlist writes: the adapter now creates/refreshes a folder with normal and
  smart playlists. On a copy, the extended probe confirmed that existing
  playlists, memberships and all other tables were untouched, and that
  `masterPlaylists6.xml` only gained three lines.
- Smart playlist format: all 14 smart playlists that rekordbox created in this
  library re-encode byte for byte with Song Dex's own encoder. pyrekordbox 0.4.4's
  encoder is not used: it wrote `Id="-4049718608"` for a new playlist, where
  rekordbox itself stores the playlist ID as a signed 32-bit number, and it would
  store My Tag IDs unsigned where rekordbox stores them signed.
- Playlist XML: pyrekordbox's own commit rewrote the timestamps of 33 existing
  playlists and reformatted the file. Song Dex bypasses that and appends lines only.
- Rows created by the adapter for playlists and playlist entries matched
  rekordbox-created rows column for column (IDs, UUIDs, UTC timestamps, status
  flags, update counters).
- Live check (`songdex.livecheck`): exercised end to end against a library copy in
  `--db-only` mode: start, refused second start, finish without rekordbox opening
  (stays locked), finish after a simulated session (unlocks), blocked restore when
  new work appeared, cancel. Every round restored `master.db` and the playlist XML
  byte for byte. The audio-tag half is covered by unit tests on generated files.
- Write guards: the adapter refuses a library that shows Cloud Library Sync
  activity or an unexpected database version, and the probe asserts the update
  counter stays equal to the newest row stamp. Checked on a copy only.
- 60 backend tests and Ruff pass.

Not done: the live check has not been run against the real application, so
direct writes are still locked. BPM and key smart-playlist rule encodings are
unconfirmed (no such rule exists in this library yet); the live check's optional
"Dex learn" step records them. How rekordbox removes a track from the collection
(which related rows and analysis files go with it) is unobserved: none of its
three rolling backups contains a removal.

## Live rekordbox check — 2026-10-11

`python -m songdex.livecheck start` / `finish` on the real library, rekordbox
7.2.18, pyrekordbox 0.4.4. Result recorded in `.data/compatibility.json`:
`rekordbox_restart_verified: true`, `verified_formats: [".flac", ".mp3"]`.

- Written: marked metadata on one FLAC and one MP3 track (database and audio
  tags), a playlist folder with one normal and three smart playlists (artist
  equals, year range, My Tag contains).
- Confirmed by the user in rekordbox: edited fields shown, a test track played
  with waveform, grid and cues, playlist and smart-playlist counts as expected
  (4 / 2 / 193 / 23).
- Readback after rekordbox quit: metadata, playlists and their XML registration
  kept; entry count unchanged; test files untouched; rekordbox changed only
  `agentRegistry` (8 rows) and `djmdSampler` (3 rows); no column of the test
  tracks changed.
- Restore: `master.db`, `masterPlaylists6.xml`, both audio files and rekordbox's
  three rolling backups (which it rotated during the session) verified
  byte-for-byte against the originals.

Not covered: M4A and AIFF (no reachable file), BPM/key smart-playlist rules and
hand-edit bookkeeping (the optional "Dex learn" step was not done), duplicate
merges and batch sync on the real library, USB export behaviour.
