import json
import shutil
from pathlib import Path

import pytest
from songdex import audio, rekordbox
from songdex.importing import Importing
from songdex.operations import Operations
from songdex.tagging import Tagging, names_genre, suggestions
from test_editing_importing import job

CHOICES = {
    "tags": [
        {"id": "10", "name": "Afro", "category": "Genre"},
        {"id": "11", "name": "Deep House", "category": "Genre"},
        {"id": "12", "name": "90s", "category": "Genre"},
        {"id": "13", "name": "Raggae/Dub", "category": "Genre"},
        {"id": "20", "name": "Vocal", "category": "Components"},
        {"id": "30", "name": "Peak Time", "category": "Situation"},
    ],
    "playlists": [
        {"id": "100", "name": "Crates / Neo Afro"},
        {"id": "101", "name": "Warm up"},
    ],
}


def track(tid, artist="", genre="", year="", tags=(), playlists=(), state="indexed"):
    return {
        "id": tid,
        "state": state,
        "metadata": {"artist": artist, "genre": genre, "year": year},
        "accepted": {},
        "my_tags": [{"id": t} for t in tags],
        "playlists": [{"id": p, "name": p, "position": 1} for p in playlists],
    }


def found(result):
    return {(s["kind"], s["id"]): s["reasons"] for s in result}


def test_tag_names_match_genre_words_not_fragments():
    assert names_genre("Afro", "Afro House")
    assert names_genre("Afro", "Afrobeats")
    assert names_genre("Raggae/Dub", "Dub")
    assert names_genre("Deep House", "deep house")
    assert not names_genre("Alt", "Altitude")
    assert not names_genre("Techno", "Afro House")


def test_suggestions_come_from_artist_genre_year_and_duplicates():
    new = track(1, artist="Burna Boy feat. Wizkid", genre="Afrobeats", year="1998")
    library = [
        new,
        track(2, artist="Burna Boy", tags=["30"], playlists=["100"]),
        track(3, artist="Burna Boy", tags=["30"]),
        track(4, artist="Burna Boy"),
        track(5, artist="Someone", genre="Afrobeats", playlists=["101"]),
        track(6, artist="Someone else", genre="Afrobeats", playlists=["101"]),
        track(7, artist="Gone", playlists=["100"], state="removed"),
    ]
    twin = track(8, artist="Burna Boy", tags=["20"], playlists=["100"])
    result = found(suggestions(new, library, CHOICES, [twin]))
    assert result[("tag", "30")] == ["2 of your 3 other tracks by Burna Boy"]
    assert result[("tag", "10")] == ["Genre Afrobeats"]
    assert result[("tag", "12")] == ["Released in 1998"]
    assert result[("tag", "20")] == ["On NO. 0008, a possible duplicate"]
    assert result[("playlist", "101")] == ["2 of your 2 Afrobeats tracks"]
    # One of three tracks by the artist is a one-off; the duplicate still counts.
    assert result[("playlist", "100")] == ["On NO. 0008, a possible duplicate"]


def test_suggestions_skip_what_the_track_has_and_unknown_targets():
    new = track(1, artist="A", genre="Deep House", tags=["11"])
    library = [new, track(2, artist="A", tags=["99"], playlists=["101"])]
    result = found(suggestions(new, library, CHOICES))
    assert ("tag", "11") not in result and ("tag", "99") not in result
    assert ("playlist", "101") in result
    # Choices made for other tracks in the session count as theirs.
    pending = {2: {"tag": {"20"}}}
    assert ("tag", "20") in found(suggestions(new, library, CHOICES, pending=pending))


def row(source_id, path, tags=(), playlists=()):
    return {
        "source_id": source_id,
        "path": str(path),
        "size": Path(path).stat().st_size if Path(path).exists() else 0,
        "metadata": {"title": Path(path).stem, "artist": "Artist"},
        "playlists": [{"name": p, "id": p, "position": 1} for p in playlists],
        "my_tags": [{"id": t, "name": t, "category": ""} for t in tags],
        "stats": {},
    }


@pytest.fixture
def library(service, tmp_path, monkeypatch):
    """A rekordbox library whose master.db is a JSON list of collection rows."""
    music = tmp_path / "Collection"
    music.mkdir()
    source = tmp_path / "library/master.db"
    source.parent.mkdir()
    xml = source.parent / "masterPlaylists6.xml"
    xml.write_bytes(b"playlists")
    plans = []

    def write(rows):
        source.write_text(json.dumps(rows))

    def snapshot(src, destination):
        destination.mkdir(parents=True)
        shutil.copy2(src, destination / "master.db")
        shutil.copy2(xml, destination / xml.name)
        return audio.digest(src)

    def assign(path, plan):
        plans.append(plan)
        rows = json.loads(path.read_text())
        for r in rows:
            wanted = plan.get(r["source_id"], {})
            r["my_tags"] += [
                {"id": t, "name": t, "category": ""} for t in wanted.get("tags", [])
            ]
            r["playlists"] += [
                {"name": p, "id": p, "position": 9} for p in wanted.get("playlists", [])
            ]
        path.write_text(json.dumps(rows))
        return {"my_tags": 1, "playlists": 1}

    def relocate(path, moves):
        rows = json.loads(path.read_text())
        for r in rows:
            r["path"] = moves.get(r["source_id"], r["path"])
        path.write_text(json.dumps(rows))
        return {"moves": len(moves)}

    monkeypatch.setattr(rekordbox, "relocate", relocate)
    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    monkeypatch.setattr(
        rekordbox, "capability", lambda root: {"enabled": True, "report": {}}
    )
    monkeypatch.setattr(rekordbox, "snapshot", snapshot)
    monkeypatch.setattr(rekordbox, "assign", assign)
    monkeypatch.setattr(rekordbox, "read_choices", lambda path, folder: CHOICES)
    monkeypatch.setattr(
        rekordbox, "read_collection", lambda path: json.loads(path.read_text())
    )
    service.store.set_setting("rekordbox_db", str(source))
    service.store.set_setting("music_folder", str(music))
    write([])
    service.scan("first", {})
    return music, write, plans


def imported(service, paths):
    importer = Importing(service)
    preview = importer.preview([str(p) for p in paths], "move")
    importer.run(job(service, preview["id"]), {"import_id": preview["id"]})
    return preview["id"]


def test_new_files_wait_for_rekordbox_then_the_scan_writes_their_choices(
    service, library, audio_file
):
    music, write, plans = library
    folder = music / "2026-10-18"
    folder.mkdir()
    new = Path(shutil.move(audio_file(), folder / "new.flac"))
    sid = imported(service, [folder])
    # Already in the music folder: indexed in place, not moved.
    assert new.is_file()
    tagging = Tagging(service)
    (tid,) = tagging.open(sid)
    session = tagging.session(sid)
    (item,) = session["tracks"]
    assert (item["id"], item["in_rekordbox"]) == (tid, False)
    assert session["choices"]["loaded"] is True
    tagging.choose(sid, tid, ["10", "20"], ["101"], 0)
    tagging.choose(sid, tid, ["10"], ["101"], 0)  # Vocal unticked again
    assert tagging.session(sid)["tracks"][0]["pending"] == {
        "tags": ["10"],
        "playlists": ["101"],
    }
    with pytest.raises(ValueError, match="not in rekordbox"):
        tagging.write()
    # rekordbox imports the playlist; the next scan finds the file and writes.
    write([row("55", new)])
    note = service.scan("second", {})
    assert note == "Added 1 My Tags and 1 playlist places to 1 tracks in rekordbox."
    assert plans == [{"55": {"tags": ["10"], "playlists": ["101"]}}]
    t = service.store.track(tid)
    assert (t["source_id"], [g["id"] for g in t["my_tags"]]) == ("55", ["10"])
    assert tagging.assignments("pending") == []
    assert tagging.session(sid)["tracks"][0]["saved"]["tags"] == ["10"]
    # Nothing left, so later scans write nothing.
    assert service.scan("third", {}) is None and len(plans) == 1


def test_tracks_in_rekordbox_are_written_together_and_restorable(
    service, library, audio_file, tmp_path
):
    music, write, plans = library
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    old = Path(shutil.move(audio_file(), downloads / "listed.flac"))
    write([row("7", old, tags=["30"])])
    service.scan("listed", {})
    sid = imported(service, [old])
    tagging = Tagging(service)
    (tid,) = tagging.open(sid)
    assert tagging.session(sid)["tracks"][0]["in_rekordbox"] is True
    # A tag the entry already has is not written again.
    tagging.choose(sid, tid, ["30", "11"], [], 0)
    result = tagging.write()
    assert result["message"] == (
        "Added 1 My Tags and 0 playlist places to 1 tracks in rekordbox."
    )
    assert plans[-1] == {"7": {"tags": ["11"], "playlists": []}}
    assert {g["id"] for g in service.store.track(tid)["my_tags"]} == {"30", "11"}
    Operations(service).restore(result["id"])
    assert [g["id"] for g in service.store.track(tid)["my_tags"]] == ["30"]


def test_choices_are_checked_against_the_library(service, library, audio_file):
    music, write, plans = library
    new = Path(shutil.move(audio_file(), music / "new.flac"))
    sid = imported(service, [new])
    tagging = Tagging(service)
    (tid,) = tagging.open(sid)
    with pytest.raises(ValueError, match="no longer in rekordbox"):
        tagging.choose(sid, tid, ["999"], [], 0)
    with pytest.raises(ValueError, match="not part of this tagging session"):
        tagging.choose(sid, tid + 1, [], [], 0)
    tagging.finish(sid)
    assert tagging.summaries() == []


def test_import_job_checks_tracks_before_tagging(
    service, library, audio_file, monkeypatch
):
    music, write, plans = library
    new = Path(shutil.move(audio_file(), music / "new.flac"))
    importer = Importing(service)
    preview = importer.preview([str(new)], "move")
    looked_up = []
    monkeypatch.setattr(
        service.providers, "enrich", lambda t, *_: looked_up.append(t["id"]) or []
    )
    jid = service.start("import_music", {"import_id": preview["id"]})
    service.lock.acquire()
    service.lock.release()
    with service.store.connect() as db:
        state, message = db.execute(
            "SELECT state,message FROM jobs WHERE id=?", (jid,)
        ).fetchone()
    assert state == "complete" and message.endswith("Ready to tag.")
    (summary,) = Tagging(service).summaries()
    assert (summary["id"], summary["state"], summary["total"]) == (
        preview["id"],
        "ready",
        1,
    )
    assert looked_up == Tagging(service).row(preview["id"])["checked"]


def test_interrupted_checks_resume_where_they_stopped(
    service, library, audio_file, monkeypatch
):
    music, write, plans = library
    first = Path(shutil.move(audio_file(), music / "first.flac"))
    second = Path(shutil.move(audio_file("mp3"), music / "second.mp3"))
    sid = imported(service, [first, second])
    tagging = Tagging(service)
    ids = tagging.open(sid)
    # The import job stopped after checking the first track.
    with service.store.connect() as db:
        db.execute("UPDATE tag_sessions SET checked=? WHERE id=?", (f"[{ids[0]}]", sid))
    looked_up = []
    monkeypatch.setattr(
        service.providers, "enrich", lambda t, *_: looked_up.append(t["id"]) or []
    )
    service.start("tag_check", {"session_id": sid})
    service.lock.acquire()
    service.lock.release()
    assert looked_up == [ids[1]]
    assert tagging.row(sid)["state"] == "ready"
