import json
import shutil
import unicodedata
from pathlib import Path

import pytest
from songdex import audio, rekordbox
from songdex.importing import Importing
from songdex.operations import Operations
from songdex.relocating import plan
from test_editing_importing import job


def row(source_id, path, size=0, duration=0):
    return {
        "source_id": source_id,
        "path": str(path),
        "size": size,
        "metadata": {
            "title": Path(path).stem,
            "artist": "Artist",
            "duration": duration,
        },
        "playlists": [],
        "my_tags": [],
        "stats": {"cues": 2, "plays": 0, "rating": 0},
    }


@pytest.fixture
def folders(tmp_path):
    music, downloads = tmp_path / "Collection", tmp_path / "Downloads"
    music.mkdir()
    downloads.mkdir()
    return music, downloads


@pytest.fixture
def library(service, folders, tmp_path, monkeypatch):
    """A rekordbox library whose master.db is a JSON list of collection rows."""
    music, _ = folders
    source = tmp_path / "library/master.db"
    source.parent.mkdir()
    xml = source.parent / "masterPlaylists6.xml"
    xml.write_bytes(b"playlists")

    def write(rows):
        source.write_text(json.dumps(rows))

    def snapshot(src, destination):
        destination.mkdir(parents=True)
        shutil.copy2(src, destination / "master.db")
        shutil.copy2(xml, destination / xml.name)
        return audio.digest(src)

    def relocate(path, moves):
        rows = json.loads(path.read_text())
        for r in rows:
            r["path"] = moves.get(r["source_id"], r["path"])
        path.write_text(json.dumps(rows))
        return {"moves": len(moves)}

    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    monkeypatch.setattr(
        rekordbox, "capability", lambda root: {"enabled": True, "report": {}}
    )
    monkeypatch.setattr(rekordbox, "snapshot", snapshot)
    monkeypatch.setattr(rekordbox, "relocate", relocate)
    monkeypatch.setattr(
        rekordbox, "read_collection", lambda path: json.loads(path.read_text())
    )
    service.store.set_setting("rekordbox_db", str(source))
    service.store.set_setting("music_folder", str(music))
    return source, write


def test_plan_matches_by_name_with_size_or_length(folders, audio_file):
    music, downloads = folders
    same = shutil.copy2(audio_file(), music / "same.flac")
    retagged = shutil.copy2(same, music / "retagged.flac")
    audio.write(retagged, {"title": "A much longer title than rekordbox measured"})
    (music / "other.flac").write_bytes(b"a different recording")
    size, length = Path(same).stat().st_size, audio.read(same)["duration"]
    moves, review = plan(
        [
            row("1", downloads / "same.flac", size),
            row("2", downloads / "retagged.flac", size, int(length)),
            row("3", downloads / "other.flac", size, int(length)),
            row("4", "/Volumes/Elements/Music/elsewhere.flac", size),
        ],
        music,
    )
    assert moves == {"1": str(same), "2": str(retagged)}
    assert [(r["source_id"], r["candidates"]) for r in review] == [
        ("3", [str(music / "other.flac")])
    ]


def test_plan_never_shares_a_file_between_entries(folders, audio_file):
    music, downloads = folders
    used = Path(shutil.copy2(audio_file(), music / "song.flac"))
    size = used.stat().st_size
    # The file already belongs to entry 1, so the missing duplicate entry stays missing.
    assert (
        plan([row("1", used, size), row("2", downloads / "song.flac", size)], music)[0]
        == {}
    )


def test_plan_follows_neighbours_and_composed_names(folders, audio_file):
    music, downloads = folders
    (music / "A").mkdir()
    (music / "B").mkdir()
    name = unicodedata.normalize("NFD", "Omertà.flac")
    track = Path(shutil.copy2(audio_file(), music / "A" / name))
    for folder in ("A", "B"):
        shutil.copy2(track, music / folder / "twin.flac")
    size = track.stat().st_size
    rows = [
        row("1", downloads / unicodedata.normalize("NFC", name), size),
        row("2", downloads / "twin.flac", size),
    ]
    moves, review = plan(rows, music)
    assert moves == {"1": str(track), "2": str(music / "A/twin.flac")}
    # Without a neighbour to follow, identical copies are left for the user.
    moves, review = plan(rows[1:], music)
    assert moves == {} and len(review[0]["candidates"]) == 2


def test_scan_repoints_moved_files_and_restores(service, library, folders, audio_file):
    source, write = library
    music, downloads = folders
    track = Path(shutil.copy2(audio_file(), music / "moved.flac"))
    old = downloads / "moved.flac"
    write([row("7", old, track.stat().st_size)])
    note = service.scan("job", {})
    assert note == "Repointed 1 missing files found in the music folder."
    assert json.loads(source.read_text())[0]["path"] == str(track)
    (entry,) = service.store.tracks()
    assert entry["path"] == str(track) and entry["available"]
    assert service.store.setting("library_hash") == audio.digest(source)
    with service.store.connect() as db:
        (op,) = db.execute("SELECT * FROM operations").fetchall()
        history = db.execute(
            "SELECT kind,detail FROM history WHERE track_id IS NOT NULL"
        ).fetchall()
    assert op["state"] == "complete"
    assert [tuple(h) for h in history] == [("path repaired", f"{old} → {track}")]
    # A second scan has nothing left to do.
    assert service.scan("again", {}) is None
    Operations(service).restore(op["id"])
    assert json.loads(source.read_text())[0]["path"] == str(old)
    assert not service.store.tracks()[0]["available"]


def test_scan_reports_files_it_could_not_repoint(
    service, library, folders, audio_file, monkeypatch
):
    source, write = library
    music, downloads = folders
    track = Path(shutil.copy2(audio_file(), music / "moved.flac"))
    write([row("7", downloads / "moved.flac", track.stat().st_size)])
    before = source.read_bytes()
    monkeypatch.setattr(
        rekordbox,
        "capability",
        lambda root: {"enabled": False, "reason": "Direct writes are locked."},
    )
    note = service.scan("job", {})
    assert note.startswith("Found 1 missing files") and "locked" in note
    assert source.read_bytes() == before
    assert not service.store.tracks()[0]["available"]


def test_import_moves_a_file_rekordbox_lists_and_repoints_it(
    service, library, folders, audio_file
):
    source, write = library
    music, downloads = folders
    old = Path(shutil.move(audio_file(), downloads / "track.flac"))
    (music / "track.flac").write_text("Another song with this name")
    write([row("7", old, old.stat().st_size)])
    service.scan("first", {})
    importer = Importing(service)
    assert importer.preview([str(old)], "copy")["entries"][0]["status"] == "skipped"
    preview = importer.preview([str(old)], "move")
    (entry,) = preview["entries"]
    assert entry["status"] == "ready" and entry["repoint"] == str(old)
    dest = music / "track (1).flac"
    assert entry["destination"] == str(dest)
    note = importer.run(job(service, preview["id"]), {"import_id": preview["id"]})
    assert note == "Repointed 1 missing files found in the music folder."
    assert not old.exists() and dest.is_file()
    assert json.loads(source.read_text())[0]["path"] == str(dest)
    # Still one Dex entry, and it is the rekordbox one.
    (track,) = service.store.tracks()
    assert (track["source_id"], track["path"], track["available"]) == (
        "7",
        str(dest),
        1,
    )
    assert service.store.setting("moved_files") == {}
    # rekordbox already lists the file, so it stays out of the import playlist.
    playlist = service.store.root / "imports" / (preview["id"] + ".m3u8")
    assert playlist.read_text() == "#EXTM3U\n\n"


def test_import_of_a_listed_file_waits_for_rekordbox_to_close(
    service, library, folders, audio_file, monkeypatch
):
    source, write = library
    music, downloads = folders
    old = Path(shutil.move(audio_file(), downloads / "track.flac"))
    write([row("7", old, old.stat().st_size)])
    service.scan("first", {})
    importer = Importing(service)
    preview = importer.preview([str(old)], "move")

    def running():
        raise ValueError("Quit rekordbox")

    monkeypatch.setattr(rekordbox, "require_stopped", running)
    with pytest.raises(ValueError, match="Quit rekordbox"):
        importer.run(job(service, preview["id"]), {"import_id": preview["id"]})
    assert old.exists() and not (music / "track.flac").exists()
