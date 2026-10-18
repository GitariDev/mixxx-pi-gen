# Song Dex

Local music-library inspection and reviewed metadata cleanup, with a PS1 /
Game Boy Advance inspired interface. This is a standalone Mac application served
in your browser. It does not participate in Pi image builds.

## Run

Python 3.10+ and Node 20.19+ are required. Run from this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/song-dex
```

Open <http://127.0.0.1:8765>. The Python service serves the built UI, fonts, API,
and local audio. It binds only to loopback. Quit rekordbox and rekordboxAgent
before importing or writing. The Settings page accepts the location of a
`master.db`; default is `~/Library/Pioneer/rekordbox/master.db`.

The already-created environment in this checkout uses Codex's bundled Python
3.12. Run `.venv/bin/song-dex` after building; no reinstall is needed.

For frontend development, run the Python service and `npm --prefix frontend run
dev` separately, then open <http://127.0.0.1:5178>.

## Workflow

1. Import/rescan to index the collection, album groupings and playlist membership.
2. Open **Scan & Review → Scan** and choose what to scan: **New tracks**, the
   **Full library**, a type (**Genre sync**, missing year or album, no artist
   tag, without My Tags, lookups that failed) or a **Custom filter** built from
   search, genres, My Tags, playlists, BPM and year. Every scan lists its tracks
   first, then runs three lookups side by side: catalog matching (AcoustID and
   MusicBrainz, keeping the recording's community genres and tags and its
   artist's genres), Discogs (the release's styles, genres, label and year, for
   every track when a token is set; a blank genre, label or year is suggested
   from it, and without Discogs a missing genre comes from the main artist) and
   My Tag and playlist suggestions. Those draw on everything found: a My Tag
   named like a Discogs style or MusicBrainz genre or tag, and the My Tags and
   playlists shared by your tracks of that genre, of the same label, or by the
   same artist. An opened row shows what each source said. A track's genre waits for its catalog match,
   and its suggestions for its genre; across tracks they overlap. Each row's
   three squares show how far its lookups are, and the list fills in as results
   arrive. Scans are resumable and rate limited per service; **Stop** ends one
   after the current lookups.
3. Each track is one row: small artwork, title, artist and the fields with
   suggestions. Open a row for an inline diff: the current value struck out, each
   suggested value added below it with its source, and **Approve**, **Edit** or
   reject on every line. Suggested My Tags and playlists are added lines too; an
   added one waits for **Write to rekordbox** with other tag choices. Tick lines
   or whole rows and **Approve selected**, or **Approve all without warnings**:
   every suggestion that is the only one for its field and fills a blank or comes
   from a high-confidence match (tags and playlists optionally). Approvals made
   while a scan runs are queued and saved by the scan between lookups. Suggestions
   that only restyle a value (capitalisation, accents, punctuation) are not shown,
   album artist is not suggested, and years are compared as years. Suggestions for
   tracks removed from rekordbox, or whose value changed since, are dropped.
   Tracks with no artist tag whose name reads "Artist - Title" get artist and
   title suggestions from that name. **Edit track** opens the full editor.
   Tagging the tracks of a new import shows the same metadata diff for each
   track, so it can be settled there without a later scan.
4. Apply reviewed changes once the installation's compatibility checks are complete.
   File, rekordbox and Dex results are recorded separately in History.
5. Review duplicate groups in **Duplicates**: merge every group without warnings
   in one step, then go through the flagged ones. Groups of three or more are
   split into versions (same version label, duration and BPM, or identical files):
   copies of one version merge into its best entry while different versions, such
   as a radio edit and an extended mix, stay in the group. The group then shows
   one choice across the versions that are left: mark it as okay to keep them
   apart, or tick entries to keep merging. **Merge all without warnings**
   includes clean version pairs inside larger groups; **Choose across versions**
   switches a group to a single choice at any time. Per group or for a selection of
   groups, choose the entry to keep (and, with more than two entries, tick the
   ones to merge), merge, or mark the group as okay. Marking as okay with some
   entries ticked merges those and leaves the others, such as remixes and other
   versions, untouched. The kept entry receives their playlist
   places and My Tags; the merged entries are listed in the rekordbox playlist
   **Song Dex / Duplicates to remove** for you to remove there. Cues, grids and
   play history are not moved, and Song Dex deletes nothing. Merges are restorable
   from History and need the same compatibility gate as other rekordbox writes.

The optional **Explore demo** is explicitly labeled and does not query providers
or modify any music files. Exit demo in Settings before importing a real library.
Use `song-dex --data-dir /path/to/another/catalog` to keep separate catalogs.

## Making My Tags and playlists

My Tags and playlists can be given to a track while tagging an import, from
any track's **My Tags** tab in the library, or from **Edit track** in Scan &
Review, which has the same tab. All offer **+ New** in each My Tag category
(suggesting names from your genres and Every Noise at Once's) and, when the
playlist search finds no match, **Make playlist** in the top level, an existing
folder or a new one. **+ New playlist** on the Song Dex page makes one directly,
in any folder or a new folder inside one, optionally with the selected track. A new one can be picked straight away; it is
made in rekordbox, with every pick waiting for it, by the next **Write to
rekordbox** (or the rescan that writes an import's choices). One with the same
name in the same place is reused rather than duplicated. **Drop** in the list of
waiting changes removes a new one before it is written. Song Dex only adds: it
makes no My Tag categories and removes nothing. The copied-library probe
(`songdex.verify`) also makes a My Tag, a folder and a playlist in it on its copy and checks that
nothing else changed.

## Genres and Discogs

The Genre field in a track's Metadata tab suggests as you type: genres already
in the collection first (with their counts), then the 6,291 genre names from
Every Noise at Once's popularity list (`backend/songdex/genres.txt`). Close
spellings match ("neo sol" finds Neo Soul); any other text can still be typed.

With a Discogs personal access token, or an application's consumer key and
secret, saved in Settings, scans look up a Discogs release carrying each
track's artist and title. Its styles feed My Tag and playlist suggestions, and a
blank genre, label or year is suggested from it. Only the artist and title are
sent. Per Discogs' API terms, responses, what was kept from them, unapproved
suggestions and My Tag or playlist reasons drawn from them are discarded after
six hours, and everything shown from Discogs links to its page as "Data provided
by Discogs".

This application uses Discogs’ API but is not affiliated with, sponsored or
endorsed by Discogs. ‘Discogs’ is a trademark of Zink Media, LLC.

## Manual editing, offline music and new imports

Open a track's **Metadata** tab, edit one or more fields, then **Save metadata**.
The correction is committed immediately to the Dex with a manual lock. MP3, FLAC,
AIFF and unprotected M4A tags are backed up, staged, verified and saved when the file
is reachable and rekordbox is stopped. Each field shows separate audio-tag and
rekordbox status. Direct database changes remain queued while the compatibility
gate is closed; a Dex save is never presented as a successful rekordbox update.
WAV and other unsupported formats still accept Dex corrections.

**Offline files** and **Available files** filter the catalog independently of
metadata conflicts. **Check availability** refreshes saved paths without opening
rekordbox's database or calling providers. Offline files retain their known metadata
and playlist membership. After reconnecting a drive, check availability, review any
external changes and click **Sync saved edits** in the track's Metadata tab.
External conflicting values require an explicit new save; rescans retain your
manual value. **Saved edits awaiting sync** finds outstanding destination writes.

**Missing files are repointed automatically.** Every rescan, and the rescan that
ends an import, looks in the main music folder for each file rekordbox cannot
find. A file with the same name and the same size is taken as the same track; so
is one with the same name and length, which covers files whose tags were edited
after rekordbox measured them. Only the entry's path is rewritten, which is all
rekordbox's own Relocate changes, so cues, grids, playlists and My Tags stay with
it. The change appears in **History** as "paths repaired" and can be restored.
Matches that are not certain (same name but different audio, or several identical
copies) are listed under **Scan & Review** and left for rekordbox's Relocate.
Files on a disconnected drive stay missing until they are found in the music
folder. When direct writes are locked, the scan reports what it found and writes
nothing.

Under **Settings**, choose an existing **Main music folder** and save it. On this
Mac, `~/Documents/GTsCollection` is detected as the default. Existing tracks are not
relocated by changing this setting.

Use **Add music** to browse Downloads, Documents or external drives. Check individual
files and/or entire folders, including subfolders. **Preview import** shows every
planned destination, duplicate skip and filename collision. Move is the default:
each original is deleted only after its destination bytes are verified. Copy keeps
originals. Folder structure is preserved; filename collisions get numbered
suffixes. Hidden files and symlinks are excluded.

A file rekordbox already lists (for example one added to rekordbox straight from
Downloads) moves too, and its rekordbox entry is pointed at the new place. Quit
rekordbox first; the import stops before moving anything if it is open. With
Copy, such files are skipped, as are files already in the music folder or the
Dex.

Imports run as background jobs. Their durable receipts are in **History**; retry
unfinished files after a disconnect or restart. Completed files are never copied
again on resume. On FAT/exFAT, a failed exclusive copy may leave an incomplete
file at its destination; retries refuse to overwrite it. Inspect/remove that
incomplete destination before retrying, with the original retained.

The completed receipt offers a **rekordbox import playlist** (`.m3u8`). Download it,
then use **File → Import → Import Playlist** in rekordbox. With Auto Analysis enabled,
rekordbox analyzes newly imported tracks through its own importer, as described in
[the rekordbox 7 manual, page 40](https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf).
Song Dex does not automate the analysis command or fabricate grids. The playlist
leaves out files rekordbox already lists, so importing it never duplicates an
entry. Rescan afterward:
matching file paths link the new rekordbox IDs to the existing Dex entries, preserving
Dex numbers and corrections. The handoff does not change the direct-write gate.

Manual tag writes have their own destination backups in History. Restoring a
backup preserves your Dex correction and marks it pending for later synchronization;
newer destination changes block restoration. The older reviewed batch Apply/restore
workflow retains its original all-destination behavior.

## Current compatibility status

**Direct writer implemented; live Apply intentionally locked pending rekordbox UI
verification.** The automated probe against a copy of the installed 7.2.18 library
passed: 3,434 entries, 47 protected tables, field writes, database reopen, and
byte-exact restoration. The original library was unchanged.

MP3, FLAC, AIFF and M4A tag round-trip tests pass and decoded audio is unchanged.
Those tests do not establish that every field is displayed correctly in rekordbox.
Actual rekordbox restart/readback has not been completed yet; see the live check below.
No settings toggle can silently bypass that requirement.

Reproduce the copied-library probe (rekordbox must be stopped):

```sh
.venv/bin/python -m songdex.verify --output .data/compatibility/new-run
```

The probe writes only its copy: track metadata, then a playlist folder with a
normal and a smart playlist, checking every other table and every existing line
of `masterPlaylists6.xml` is left alone. It does not open the copy in rekordbox.

### Unlocking direct writes: the live check

Direct writes unlock only after the real rekordbox application has opened a
library written by Song Dex. The live check does that against your own library
and then restores it byte for byte:

```sh
# 1. Quit rekordbox and rekordboxAgent, then:
.venv/bin/python -m songdex.livecheck start
# 2. Open rekordbox, follow the printed checklist, quit rekordbox completely.
.venv/bin/python -m songdex.livecheck finish
```

`start` reruns the copied-library probe, backs up `master.db`,
`masterPlaylists6.xml` and one available track per writable format, then writes
clearly marked test values (search "Song Dex check" in rekordbox) plus a
"Song Dex check" playlist folder. `finish` reads the library back, asks what you
saw, restores every backed-up byte and records the result in
`compatibility.json`. Writes unlock only if rekordbox really opened the library,
the test values and playlists survived, and you confirmed all four checklist
items. Do no other work in rekordbox during the check: restoring discards it, and
`finish` stops instead if it finds new tracks, playlists, cues or My Tags
(`--discard-session-changes` overrides). `cancel` restores without recording.

`start --db-only` skips audio-tag writes. That unlocks rekordbox-side saves
(manual edits, playlists) but leaves reviewed batch Apply locked, because no
file format was checked in rekordbox. A new rekordbox or pyrekordbox version
locks writes again until the check is repeated.

WAV and other unsupported file types remain browsable and editable in the Dex, but their audio tags cannot be written.
Analysis values (BPM/key), grids, cue points, existing artwork, comments and ratings
are preserved. Files are never renamed, moved or deleted by cleanup.

## Sources and confidence

MusicBrainz lookup is enabled without credentials. AcoustID is optional: supply an
application key in Settings and install Chromaprint's `fpcalc` in PATH. Fingerprint
lookup sends the fingerprint and duration, not audio. SongData, Spotify, Every
Noise, Beatport and similar services are not yet integrated.

Match rules compare artist/title, duration, identifiers and version qualifiers.
The identity of a named remix is preserved. A recording match never chooses a
random compilation/reissue. Release metadata remains review-only, and ambiguous
values do not erase existing tags. A manually accepted correction is locked
against provider refreshes. Confidence labels are rule outcomes, not calibrated
probability percentages. Coverage depends on the sources; unidentified music
remains in the Dex.

## Storage, recovery and security

`.data/` (ignored by Git, owner-only directory) contains the SQLite catalog,
provider cache, snapshots, operation journals, and original-file backups. Do not
share this directory: it contains collection metadata and any configured API key.
Only the latest change to rekordbox or to a file can be undone, so a backup is
deleted automatically once it can no longer be undone: after a newer write to the
same destination, a restore, or a change made outside Song Dex (checked after each
write, at the end of each job and at startup). Backups of offline files are kept.
**History → Backups** lists what remains with its date and size, shows the total
against free disk space, and deletes the ones you select; a backup needed to
recover an unfinished write cannot be deleted. A write is refused when the disk
has no room for its backup.

Applying stages and verifies the changes before replacing originals. A durable
journal handles the fact that audio files, rekordbox and the Dex are separate
stores. A crash while a destination is being replaced leaves a recovery-required
entry in History; a write that fails before reaching its destination is recorded
as failed and blocks nothing. Restore refuses to
overwrite newer library/file changes. The app never writes while rekordbox is
running or when it cannot verify process state. Another instance cannot use the
same data directory through the CLI. The local API checks Host, browser Origin,
Fetch Metadata and a per-process write token. Streaming/artwork routes only expose
indexed tracks, and external-origin browser access is refused.

Jobs can be resumed from History after interruption. Files on disconnected drives
are marked unavailable, not removed. Matching-name duplicate groups are candidates,
not proof; identical file hashes are a separate category. Cloud sync, smart native
My Tags, duplicate consolidation, Linux packaging and beatgrid repair are future
milestones.

## Verification

```sh
.venv/bin/python -m pytest
.venv/bin/ruff check backend tests
npm --prefix frontend run build
```

See `VALIDATION.md` for the current run's evidence and remaining acceptance gates.
See `DESIGN.md` for the visual system. Fonts are bundled from Fontsource, with
licenses retained under `frontend/public/licenses/`.

## Filtering and My Tags

Open **Song Dex → Filter music** to combine native My Tags (match all or any),
multiple genres, keys, formats and playlists, inclusive BPM/year ranges, search
and the existing file-availability/status filter. Option counts refer to the whole
collection. Tag status distinguishes confirmed untagged tracks from entries whose
My Tags have not yet been loaded. Unknown BPM/year values do not match bounded
ranges. Clear music filters resets these additions; Clear filters in an empty
result also clears search and availability/status.

Sort by Dex number, title, artist, album, My Tags, genre, BPM, key, year, duration
or format, ascending or descending. Numeric fields sort numerically; key/text
sorting uses natural alphanumeric ordering. Unknown values stay last in both
directions and ties retain Dex-number order.

Select a track and open **My Tags** to review its native assignments by category,
or find other tracks with a tag. **Load My Tags from last scan** backfills the
catalog from the saved consistent snapshot; subsequent native scans refresh them.
It does not read new changes from the live library. Existing artwork, cues,
playlists and native tags are not modified by this read operation.

Add My Tags and playlists from the same tab (see **Making My Tags and
playlists**); removing them, and editing categories, is done in rekordbox, after
which quit it and its companion processes and rescan here. This limitation is separate from the metadata writer's
compatibility gate. Genre remains an independently editable metadata field.
