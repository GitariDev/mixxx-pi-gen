"""Check Song Dex writes inside the real rekordbox application, then put every byte back.

    python -m songdex.livecheck start    # rekordbox closed: back up, write marked test changes
    (open rekordbox, look at the printed checklist, quit rekordbox and rekordboxAgent)
    python -m songdex.livecheck finish   # read back, restore the library, record the result
    python -m songdex.livecheck cancel   # restore without recording a result

Only a finished check with every item confirmed unlocks direct writes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from pathlib import Path

from . import audio, rekordbox, verify
from .db import now
from .operations import replace_copy

MARK = "Song Dex check"
LEARN = "Dex learn"
QUESTIONS = {
    "tracks": "Did the test tracks show the edited title, artist, album, genre, label, year and mix name",
    "playback": "Did a test track load and play with its waveform, beat grid and cues intact",
    "playlists": f'Did the "{MARK}" folder contain "Check list" with the expected tracks',
    "smart": "Did each smart playlist show the expected number of tracks",
}
# New rows in these tables after the session mean real work that a restore would discard.
SESSION_TABLES = (
    "djmdContent",
    "djmdPlaylist",
    "djmdSongPlaylist",
    "djmdCue",
    "djmdSongMyTag",
)


def save(folder, state):
    temporary = folder / "state.json.new"
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    os.replace(temporary, folder / "state.json")


def load(root):
    folder = root / "compatibility" / "live"
    path = folder / "state.json"
    if not path.exists():
        raise ValueError("No live check has been started")
    return folder, json.loads(path.read_text())


def marked(metadata):
    return {
        "title": f"{metadata['title'] or 'Untitled'} [{MARK}]"[:255],
        "artist": f"{MARK} artist",
        "version": "Dex mix",
        "album": f"{MARK} album",
        "album_artist": f"{MARK} album artist",
        "year": "1987",
        "label": f"{MARK} label",
        "genre": f"{MARK} genre",
    }


def cued_ids(path):
    with rekordbox.database(path) as db:
        return {str(c.ContentID) for c in db.get_cue()}


def start(root, source, db_only=False):
    folder = root / "compatibility" / "live"
    if folder.exists():
        if (folder / "state.json").exists() and load(root)[1]["state"] == "started":
            raise ValueError("A live check is in progress; run finish or cancel first")
        # Earlier evidence is kept beside the new run.
        folder.rename(folder.with_name("live-" + now().replace(":", "")))
    if rekordbox.installed_version() != rekordbox.TARGET_VERSION:
        raise ValueError(
            f"This check is written for rekordbox {rekordbox.TARGET_VERSION}"
        )
    source = source.expanduser().resolve()
    # The copied-library probe runs first; a failure there leaves the live library untouched.
    probe = verify.verify(source, folder / "probe")
    before = rekordbox.snapshot(source, folder / "original")
    xml = source.parent / "masterPlaylists6.xml"
    # rekordbox may rotate its own rolling backups while it has the test library open.
    for backup in source.parent.glob("master.backup*.db"):
        shutil.copy2(backup, folder / "original" / backup.name)
    shutil.copytree(folder / "original", folder / "staged")
    staged = folder / "staged" / "master.db"
    rows = rekordbox.read_collection(staged)
    shared, cued = Counter(r["path"] for r in rows), cued_ids(staged)
    tracks, formats = [], set()
    (folder / "files").mkdir()
    for row in sorted(
        rows, key=lambda r: (r["source_id"] not in cued, not r["playlists"])
    ):
        path = Path(row["path"])
        extension = path.suffix.lower()
        kind = ".aiff" if extension == ".aif" else extension
        if extension not in audio.SUPPORTED or kind in formats:
            continue
        if shared[row["path"]] != 1 or not path.is_file():
            continue
        entry = {
            "source_id": row["source_id"],
            "path": str(path),
            "label": f"{row['metadata']['artist']} — {row['metadata']['title']}",
            "changes": marked(row["metadata"]),
        }
        if not db_only:
            backup = folder / "files" / f"{row['source_id']}{extension}"
            trial = backup.with_name("staged-" + backup.name)
            try:
                shutil.copy2(path, backup)
                shutil.copy2(backup, trial)
                audio.write(trial, entry["changes"])
            except Exception:
                backup.unlink(missing_ok=True)
                trial.unlink(missing_ok=True)
                continue
            entry.update(
                backup=str(backup),
                staged=str(trial),
                before_hash=audio.digest(backup),
                after_hash=audio.digest(trial),
            )
        tracks.append(entry)
        formats.add(kind)
        if db_only:
            break
    if not tracks:
        raise ValueError("No available MP3, FLAC, AIFF or M4A track to test with")
    chosen = [t["source_id"] for t in tracks]
    rekordbox.write_collection(staged, {t["source_id"]: t["changes"] for t in tracks})
    extra = [r for r in rows if r["source_id"] not in chosen][:2]
    smart = {
        "Check smart artist": (
            [{"property": "artist", "operator": 1, "left": f"{MARK} artist"}],
            len(tracks),
        ),
        "Check smart 1990s": (
            [{"property": "year", "operator": 5, "left": "1990", "right": "1999"}],
            sum(
                r["source_id"] not in chosen
                and r["metadata"]["year"].isdigit()
                and 1990 <= int(r["metadata"]["year"]) <= 1999
                for r in rows
            ),
        ),
    }
    tags = Counter(t["id"] for r in rows for t in r["my_tags"])
    if tags:
        tag, count = tags.most_common(1)[0]
        smart["Check smart tag"] = (
            [{"property": "myTag", "operator": 8, "left": tag}],
            count,
        )
    plan = {
        "folder": MARK,
        "playlists": [
            {
                "name": "Check list",
                "tracks": [*chosen, *(r["source_id"] for r in extra)],
            },
            *({"name": name, "rules": rules} for name, (rules, _) in smart.items()),
        ],
    }
    rekordbox.write_playlists(staged, plan)
    state = {
        "state": "started",
        "started_at": now(),
        "source": str(source),
        "before": {"db": before, "xml": audio.digest(xml)},
        "after": {
            "db": audio.digest(staged),
            "xml": audio.digest(staged.parent / xml.name),
        },
        "probe": probe,
        "tracks": tracks,
        "formats": sorted(formats | ({".aif"} if ".aiff" in formats else set())),
        "db_only": db_only,
        "plan": plan,
        "expected": {
            "Check list": len(plan["playlists"][0]["tracks"]),
            **{name: count for name, (_, count) in smart.items()},
        },
    }
    rekordbox.require_stopped()
    if audio.digest(source) != before:
        raise ValueError(
            "Library changed while preparing the check; nothing was written"
        )
    # Journal before the first live byte changes, so cancel/finish can always restore.
    save(folder, state)
    for entry in tracks:
        if "staged" in entry:
            replace_copy(entry["staged"], entry["path"])
    replace_copy(staged.parent / xml.name, xml)
    replace_copy(staged, source)
    if audio.digest(source) != state["after"]["db"]:
        raise ValueError("Library replacement could not be verified; run cancel")
    return state


def table_changes(wrote, got):
    """Rows rekordbox added, removed or altered after opening the written library."""
    report = {}
    for name in sorted(set(wrote) | set(got)):
        old = {str(r.get("ID", i)): r for i, r in enumerate(wrote.get(name, []))}
        new = {str(r.get("ID", i)): r for i, r in enumerate(got.get(name, []))}
        counts = {
            "added": len(new.keys() - old.keys()),
            "removed": len(old.keys() - new.keys()),
            "changed": sum(old[k] != new[k] for k in old.keys() & new.keys()),
        }
        if any(counts.values()):
            report[name] = counts
    return report


def readback(folder, state):
    """Compare what Song Dex wrote with what rekordbox left after opening and quitting."""
    staged, reopened = (
        folder / "staged" / "master.db",
        folder / "reopened" / "master.db",
    )
    wrote, got = verify.tables_snapshot(staged), verify.tables_snapshot(reopened)

    def ours(tables):
        ids = {
            str(r["ID"])
            for r in tables["djmdPlaylist"]
            if r["Name"] == MARK and r["ParentID"] == "root"
        }
        return sorted(
            (r["Name"], r["Attribute"], r["SmartList"], str(r["ID"]))
            for r in tables["djmdPlaylist"]
            if str(r["ID"]) in ids or str(r["ParentID"]) in ids
        )

    with rekordbox.database(reopened) as db:
        metadata = {
            t["source_id"]: (c := db.get_content(ID=t["source_id"]))
            and rekordbox.metadata(c)
            for t in state["tracks"]
        }
        playlists = rekordbox.playlist_state(db, MARK)
    with rekordbox.database(staged) as db:
        written = rekordbox.playlist_state(db, MARK)
    xml = (reopened.parent / "masterPlaylists6.xml").read_text(encoding="utf-8")
    session = {}
    for name in SESSION_TABLES:
        known = {str(r["ID"]) for r in wrote[name]}
        fresh = [r for r in got[name] if str(r["ID"]) not in known]
        if name == "djmdPlaylist":
            fresh = [r for r in fresh if not (r["Name"] or "").startswith(LEARN)]
        if fresh:
            session[name] = len(fresh)
    after = {str(r["ID"]): r for r in got["djmdContent"]}
    return {
        "checks": {
            "metadata_kept": all(
                metadata[t["source_id"]]
                and all(
                    str(metadata[t["source_id"]][k]) == v
                    for k, v in t["changes"].items()
                )
                for t in state["tracks"]
            ),
            "playlists_kept": playlists == written and ours(got) == ours(wrote),
            "playlists_registered": all(
                f'Id="{int(pid):X}"' in xml for *_, pid in ours(wrote)
            ),
            "entries_kept": len(got["djmdContent"]) == len(wrote["djmdContent"]),
            "files_untouched": all(
                audio.digest(t["path"]) == t["after_hash"]
                for t in state["tracks"]
                if "after_hash" in t
            ),
        },
        "changed_by_rekordbox": table_changes(wrote, got),
        # Columns rekordbox itself touched on the test tracks, e.g. after a hand edit.
        "test_track_columns_changed": {
            key: sorted(k for k, v in old.items() if v != after[key].get(k))
            for old in wrote["djmdContent"]
            if (key := str(old["ID"])) in metadata and key in after
        },
        "session_work": session,
        "learned_smart_lists": {
            r["Name"]: r["SmartList"]
            for r in got["djmdPlaylist"]
            if (r["Name"] or "").startswith(LEARN) and r["SmartList"]
        },
    }


def restore(folder, state):
    rekordbox.require_stopped()
    source = Path(state["source"])
    xml = source.parent / "masterPlaylists6.xml"
    files = [t for t in state["tracks"] if "backup" in t]
    for entry in files:
        if audio.digest(entry["backup"]) != entry["before_hash"]:
            raise ValueError("A file backup failed verification; nothing was restored")
        if audio.digest(entry["path"]) not in (
            entry["before_hash"],
            entry["after_hash"],
        ):
            raise ValueError(
                f"{Path(entry['path']).name} changed during the check; "
                f"its original is kept at {entry['backup']}"
            )
    if audio.digest(folder / "original" / "master.db") != state["before"]["db"]:
        raise ValueError("Library backup failed verification; nothing was restored")
    for entry in files:
        if audio.digest(entry["path"]) != entry["before_hash"]:
            replace_copy(entry["backup"], entry["path"])
    for backup in (folder / "original").glob("master.backup*.db"):
        if audio.digest(backup) != audio.digest(source.parent / backup.name):
            replace_copy(backup, source.parent / backup.name)
    replace_copy(folder / "original" / xml.name, xml)
    replace_copy(folder / "original" / "master.db", source)
    if audio.digest(source) != state["before"]["db"] or (
        audio.digest(xml) != state["before"]["xml"]
    ):
        raise ValueError("Restored library failed verification")


def reopen(folder, state):
    shutil.rmtree(folder / "reopened", ignore_errors=True)
    # Also refuses to continue while rekordbox runs or has an unflushed journal.
    return rekordbox.snapshot(Path(state["source"]), folder / "reopened")


def finish(root, seen=None, discard=False, ask=input):
    folder, state = load(root)
    if state["state"] != "started":
        raise ValueError("No live check is in progress")
    opened = reopen(folder, state) != state["after"]["db"]
    result = readback(folder, state)
    if result["session_work"] and not discard:
        raise ValueError(
            "rekordbox recorded new work during the check "
            f"({result['session_work']}). Restoring would discard it; rerun finish "
            "with --discard-session-changes, or redo that work afterwards."
        )
    if seen is None:
        try:
            seen = [
                key
                for key, question in QUESTIONS.items()
                if ask(f"{question}? [y/N] ").strip().lower() in ("y", "yes")
            ]
        except EOFError:
            raise ValueError(
                "Answer the prompts in a terminal, or pass --seen"
            ) from None
    restore(folder, state)
    confirmed = {key: key in seen for key in QUESTIONS}
    passed = opened and all(result["checks"].values()) and all(confirmed.values())
    report = {
        **state["probe"],
        "created_at": now(),
        "rekordbox_restart_verified": passed,
        "verified_formats": state["formats"] if passed and not state["db_only"] else [],
        "live_check": {
            "opened_by_rekordbox": opened,
            "confirmed": confirmed,
            "tracks": len(state["tracks"]),
            **result,
        },
        "note": "Live rekordbox check passed; library restored byte-for-byte."
        if passed
        else "Live rekordbox check did not pass; direct writes stay locked.",
    }
    (root / "compatibility.json").write_text(json.dumps(report, indent=2))
    state["state"] = "finished"
    save(folder, state)
    return report


def cancel(root):
    folder, state = load(root)
    if state["state"] != "started":
        raise ValueError("No live check is in progress")
    reopen(folder, state)
    restore(folder, state)
    state["state"] = "cancelled"
    save(folder, state)
    return state


def checklist(state):
    lines = [
        "",
        "Test changes are in your rekordbox library. Now:",
        "  1. Open rekordbox and search the collection for:  " + MARK,
        "     These tracks should show the edited fields (artist, album, genre, label,",
        "     year 1987, mix name 'Dex mix', title ending in '[" + MARK + "]'):",
        *(f"       - {t['label']}" for t in state["tracks"]),
        "  2. Load one of them to a deck: it should play, with waveform, grid and cues.",
        f'  3. Open the playlist folder "{MARK}" and compare track counts:',
        *(f"       - {name}: {count}" for name, count in state["expected"].items()),
        f'  4. Optional: create a smart playlist named "{LEARN}" with a BPM range and',
        "     a Key rule, and type a Comment on one test track, so Song Dex can record",
        "     how rekordbox itself stores those rules and marks a hand edit.",
        "  5. Do no other work. Quit rekordbox completely (and rekordboxAgent).",
        "  6. Run:  python -m songdex.livecheck finish",
        "",
        "Everything is restored at finish. To back out now: python -m songdex.livecheck cancel",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["start", "finish", "cancel"])
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--source", type=Path, default=rekordbox.DEFAULT_DB)
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="Do not write audio tags; unlocks rekordbox writes but no file formats",
    )
    parser.add_argument(
        "--seen",
        nargs="*",
        choices=list(QUESTIONS),
        help="Checklist items you confirmed, instead of answering prompts",
    )
    parser.add_argument("--discard-session-changes", action="store_true")
    args = parser.parse_args()
    root = (
        (
            args.data_dir
            or Path(
                os.environ.get(
                    "SONGDEX_DATA", Path(__file__).resolve().parents[2] / ".data"
                )
            )
        )
        .expanduser()
        .resolve()
    )
    try:
        if args.command == "start":
            print(checklist(start(root, args.source, args.db_only)))
        elif args.command == "finish":
            report = finish(root, args.seen, args.discard_session_changes)
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            cancel(root)
            print("Restored. No result was recorded.")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except AssertionError as exc:
        parser.exit(1, f"Copied-library probe failed, live library untouched: {exc}\n")


if __name__ == "__main__":
    main()
