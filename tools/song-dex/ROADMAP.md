# Song Dex roadmap

Noted 2026-10-10. Order is the agreed working order; each item lists what exists
today and what is still missing. Nothing here is implemented unless it says so.

## 0. Pick up newly added rekordbox tracks

The Dex was last scanned on 2026-10-03 (3,434 entries); the live library held
3,471 on 2026-10-10. Tracks added to rekordbox since the scan appear after
**Import/rescan**, which needs rekordbox and rekordboxAgent to be quit so a
consistent snapshot can be taken.

Added 2026-10-13: imports move files by default, a file rekordbox already lists
moves with its entry, and every scan repoints missing entries whose file is in
the main music folder (`relocating.py`, `rekordbox.relocate`). Evidence for the
write: 30 tracks relocated by hand in rekordbox that day changed only
`FolderPath`, `rb_local_usn` and `updated_at`, and this library's analysis files
hold `?/<file name>` instead of a full path. `rekordbox.relocate` on a library
copy changed the same columns, plus `FileNameL` when the name changed and the
`agentRegistry` counter. A scan against a library copy repointed one size-matched
and one length-matched track and restored them from History.

Not yet done: a repointed track has not been opened in rekordbox, so that cues
and grids load from the new path is expected from the above, not observed. On
2026-10-13 none of the 2,502 missing entries (all on `/Volumes/Elements/Music`)
had a file of the same name in the music folder, so nothing has been written to
the real library by this feature.

Missing: brand-new files still reach rekordbox through its own importer (the
import playlist); 28 audio files in the music folder had no rekordbox entry on
2026-10-13 and nothing lists them yet.

## 1. Write to the rekordbox database (in progress)

Exists: `rekordbox.write_collection` edits title, version, year, artist, genre,
label, album and album artist through pyrekordbox, with staged copies, backups,
journals and restore. It passes on copied libraries but live use is locked by the
compatibility gate (`rekordbox_restart_verified`).

Added 2026-10-10: `rekordbox.write_playlists` (folder, normal and smart
playlists), the extended copied-library probe, cloud-sync and database-version
guards, and the live check (`python -m songdex.livecheck`, see README).

Added 2026-10-11: `Operations.library_change`, the journaled operation for
database-only changes. It stages `master.db` and `masterPlaylists6.xml`
together, shows in History and restores both. The live check was started on the
real library the same day (FLAC and MP3 test tracks).

The live check passed on 2026-10-11 (see VALIDATION.md): direct writes are
unlocked for rekordbox 7.2.18, with audio-tag writes verified for FLAC and MP3.

Missing:
- My Tag writes (assign/unassign, create tags). Not started.

## 2. Apply metadata updates

Exists: provider proposals, review, manual edits, per-destination status
(audio tags / rekordbox / Dex), queued rekordbox writes.

Added 2026-10-11: approve a suggestion or a whole track on the spot (saved in
the Dex, written where a destination is ready, queued otherwise), a background
"sync saved edits" job for everything queued, and no suggestions for values that
differ only in capitalisation, accents or punctuation (343 of 359 pending title
suggestions were of that kind).

Added 2026-10-11 (second pass): album artist no longer suggested; years compared
as years (44 of 76 year suggestions only differed from a full date in the file);
genre lookup (recording, then main artist) for tracks without a genre, which
previously ran only with AcoustID configured; artist/title suggestions read from
"Artist - Title" track names. Of 835 genre-less tracks, 608 have no artist tag.
In a 50-track trial MusicBrainz gave a genre for 17; lesser-known artists have
none there, so another source (Discogs, Last.fm or iTunes) would be needed for
the rest.

Added 2026-10-11 (third pass): genre picker with Every Noise at Once names,
Discogs genre lookup behind a personal token (search response shape checked
against the live API; not yet run with a token), merged duplicate groups shown
as one expandable line.

Missing: the batch sync writes rekordbox one track at a time (a full staged copy
of the database each); one staged write for the whole batch would be faster.

## 3. Actionable duplicates

Exists: duplicate groups (`exact` by file hash, `probable`/`related` by artist +
title with duration/BPM/version warnings).

Added 2026-10-11 (verified on a library copy only; not yet run on the real
library or opened in rekordbox): a suggested entry to keep (available file, has
cues, lossless, bitrate, playlists, My Tags), keep/merge choice per entry with a
preview of what moves, merge of playlist places and My Tags into the kept entry,
the "Song Dex / Duplicates to remove" playlist, "Not duplicates" dismissal, and
restore from History. Related-version groups start with nothing ticked.

Added 2026-10-13 (unit tests only; not yet run on the real library): marking a
group as okay with some entries ticked merges those and okays the rest, so
remixes and other versions stay separate. An okayed group with merged entries
stays under "Merged, waiting for removal", and restoring the merge reopens it.

Still missing from the list below: rating/comment/play-count merge, the holding
folder for removed files, and anything that removes entries.

Original plan:
- Choose the entry to keep per group (suggest by format/bitrate, availability,
  cues, play count, playlist membership).
- Merge into the kept entry: playlist memberships and My Tags (re-pointed in
  place so playlist order survives), rating/comment/play count. Cues and grids
  belong to a specific file's analysis and are not moved between entries.
- Removal is left to rekordbox for now: Song Dex collects the leftover entries
  in a "Song Dex / Duplicates to remove" playlist, and the user removes them
  there (select all → Remove from Collection), or uses rekordbox's own
  File → Display All Duplicated Files → Merge Duplicate Files (7.2.8+). Song Dex
  does not delete collection rows itself: there is no supported delete in the
  adapter, 16 tables plus analysis and artwork files reference a track, and how
  rekordbox cleans them up has not been observed.
- Optionally move the removed entries' files to a holding folder afterwards
  (never delete outright).
- "Not a duplicate" dismissal that survives rescans.
- Review screen with a full preview of what moves and what is removed, plus
  restore from History.

## 4. Filters to playlists

Exists: combined filters (My Tags any/all, genres, keys, formats, playlists,
BPM/year ranges, search, availability) and sorting, in the browser only.

Missing:
- Save a filter as a named Dex filter.
- Create a rekordbox **smart playlist** from a filter where rekordbox's rule
  language can express it (genre, BPM range, key, My Tag, year, rating, dates;
  one all/any operator, no nesting).
- Create or update a **normal playlist** from a filter's current results when the
  filter cannot be expressed as rekordbox rules (for example mixed all/any, or
  file availability). Updating must keep the user's manual ordering and report
  added/removed tracks before writing.
- Automatic smart playlists generated from the collection (per genre, BPM band,
  key, My Tag, recently added), kept under one "Song Dex" playlist folder so they
  never mix with hand-made playlists.

## 5. Recommended songs (key + BPM)

Missing entirely:
- For a selected track, rank other tracks by harmonic compatibility (same key,
  relative major/minor, adjacent keys on the Camelot wheel, energy-boost moves)
  and BPM proximity, including half/double time.
- Controls for BPM tolerance and which key moves count; optional same-genre /
  shared My Tag weighting.
- Show why each track was recommended (for example "8A → 9A, +2 BPM").
- Send a recommendation list to a playlist (depends on item 4).

Collection facts that matter here: every entry has a key and all but 47 have a
BPM; keys are stored as names such as `Am`, `F#m`, `Eb`, so a name → Camelot
mapping is needed.

## Direct-write findings (2026-10-10)

Sources: web research (GitHub projects and issues, pyrekordbox docs and source,
Lexicon DJ manual and forum, rekordbox 7.2.18 manual and EULA) plus read-only
inspection of this library. Reddit and the AlphaTheta community forum could not
be reached by the research tools, so nothing here rests on them.

**Can we write to `master.db` directly?** Yes. It is an established practice:
Lexicon DJ has synced by direct write since 2022 and recommends it for rekordbox
6/7, and several open-source tools do the same through pyrekordbox. Edits to
existing tracks are the lowest-risk kind. No report was found of rekordbox
refusing or reverting well-formed metadata edits with Cloud Library Sync off.
What nobody publishes is verification against the real application, which is
why the live check exists.

**What it takes**
- The SQLCipher key: unchanged across rekordbox 6 and 7 and built into
  pyrekordbox 0.4.4, which is still the latest release. Its unreleased master
  renames the API, so the pin stays.
- rekordbox **and** rekordboxAgent fully quit, and no pending `-wal` journal.
  Reported corruption ("database disk image is malformed", app not opening)
  came from writing while either was active or from a session left open.
- Cloud Library Sync off. It is off here (no row has ever been synced). With it
  on, direct writes are reported to cause duplicates and lost cues, so the
  adapter refuses libraries that show sync activity.
- Bookkeeping: bump `agentRegistry.localUpdateCount` and stamp each changed row's
  `rb_local_usn`; leave `usn` and the `rb_*status/deleted/synced` columns at
  their defaults; UTC timestamps in rekordbox's text format. pyrekordbox does
  this on commit, and the probe checks the counter stays in step.
- New playlists must also be listed in `masterPlaylists6.xml`.
- A verified backup before every write, and a write on a staged copy that
  replaces the original only after checks. Already how Song Dex works.

**Where the adapter library is wrong for this library** (measured, and worked
around in `rekordbox.py`)
- Smart playlist rules: rekordbox stores the playlist ID and My Tag IDs as signed
  32-bit numbers. pyrekordbox writes an out-of-range ID and unsigned tag IDs.
- `masterPlaylists6.xml`: any pyrekordbox commit reformats the file and rewrites
  timestamps for every playlist. Song Dex appends lines only.

**What direct edits do not reach**
- Audio file tags. rekordbox's Reload Tag replaces edited values with the file's
  tags, so an edit that is only in the database (for example an offline file)
  can be silently reverted. Song Dex writes both where the file is reachable.
- USB/SD exports. They are separate databases and stay stale until re-synced in
  rekordbox. Whether Sync Manager notices a Song Dex edit is unverified:
  rekordbox keeps a per-track `TrackInfoUpdated` counter that the adapter does
  not bump.

**Things to avoid**
- Inserting tracks: reports of pyrekordbox-inserted tracks showing as unloadable
  "Video File" entries. Song Dex keeps handing new files to rekordbox's own
  importer.
- Deleting tracks from the database (see item 3).
- Writing on a library that has used Cloud Library Sync.

**The official alternative: rekordbox XML.** Still supported in 7.2.18, but it
cannot carry My Tags, smart playlists, mix name or deletions, existing tracks
only update through a manual "Import To Collection", and it may overwrite cues
and grids from the XML. Not a fit for these features.

**Licence note.** The rekordbox EULA forbids modifying or reverse engineering
the program and circumventing its technology; XML is the only interface
AlphaTheta offers. Direct database access is unsupported by them, and a future
update could change the format, which is why writes re-lock on a new version.

**Still to be settled by the live check or a later test**
- That 7.2.18 shows and keeps Song Dex's metadata, playlists and smart playlists.
- How rekordbox stores BPM and key rules in smart playlists (none exist here).
- Which columns rekordbox changes on a hand edit (`TrackInfoUpdated` and others).
- Whether a re-sync pushes Song Dex edits to a USB device.
- What rekordbox's own duplicate merge and Remove from Collection do to related
  rows and analysis files.
