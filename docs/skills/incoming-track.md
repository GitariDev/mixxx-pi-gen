# Incoming track and playlist setup

**Aliases:** incoming track, new song, ingest, import music, prepare track,
playlist setup

## Definition of done

The file is safely stored, visible in Mixxx, analyzed, tagged, assigned to at
least one crate, placed in an ordered playlist when appropriate, auditioned,
and backed up outside the Pi.

## Workflow

1. **Land the file.** Copy it from USB or network storage into a durable music folder. Do not make a removable USB path the only copy.
2. **Use a predictable path.** Suggested structure: `Music/Incoming/YYYY-MM-DD/` while sorting, then `Music/Library/<Genre or Event>/` when accepted.
3. **Add or rescan in Mixxx.** If the folder is outside the configured library directories, add it in Preferences → Library. Rescan after copying.
4. **Analyze before performance.** Run BPM, beatgrid, waveform, ReplayGain, and key analysis. Do this in batches while on reliable power, not moments before a set.
5. **Verify manually.** Preview the start, first downbeat, loud section, transition points, and end. Correct obviously wrong BPM halves/doubles and beatgrid placement.
6. **Normalize metadata.** At minimum confirm artist, title, genre, year, and a useful comment. Optional comment grammar: `energy:3 | intro:16 | clean | vocal | exit:breakdown`.
7. **Set performance markers.** Use the rig's standard four-cue system: Hot Cue 1 = first clean downbeat/mix-in; 2 = main vocal or musical entry; 3 = drop/chorus/peak; 4 = clean outro or emergency exit. See [`phrasing-hot-cues.md`](phrasing-hot-cues.md).
8. **Classify with crates.** Add reusable labels such as genre, energy, context, language, clean/explicit, and must-play. Crates are unordered and work like tags.
9. **Place in a playlist.** Use a playlist only when order matters: a planned set, warm-up arc, event segment, or transition rehearsal.
10. **Audition on the actual rig.** Load both decks, test cue/master routing, and check the file for decoding glitches or unexpectedly low/high gain.
11. **Back up.** Keep the source track, metadata/library backup, and any exported playlist on another device.

## Playlist compatibility check

Before adding a track to a planned set, assess more than personal preference:

- compatible genre, rhythm, and drum pattern;
- manageable BPM difference while learning;
- whether it raises, maintains, or lowers energy;
- identifiable intro, first vocal, breakdown, drop, and outro;
- clean instrumental space for entering and exiting;
- compatible key when melodies or vocals will overlap;
- a clear role: opener, builder, peak, reset, bridge, or closer.

For initial practice, choose 6-10 tracks with a coherent sound and restrained BPM range.

## Fast triage for a track arriving during a set

- Copy or locate it, preview it, and confirm the file plays.
- Analyze BPM/waveform; do not trust an unanalyzed grid for Sync or quantized loops.
- Add it to the `INBOX - LIVE` crate and the current playlist.
- Add a minimal comment and energy value.
- Do the full metadata, cue, and backup pass after the set.

## Suggested acceptance flags

- `READY`: analyzed, checked, classified, and backed up.
- `GRID`: beatgrid needs repair.
- `TAG`: metadata cleanup needed.
- `QUALITY`: questionable source/encoding; do not perform with it yet.
- `REQUEST`: audience request; review after the event.
