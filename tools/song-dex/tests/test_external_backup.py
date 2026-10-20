import json
import os
import sqlite3

import pytest
from conftest import ingest
from songdex import external, rekordbox
from songdex.external import ExternalBackup


@pytest.fixture
def library(service, tmp_path, monkeypatch):
    """A rekordbox folder, two music files (one offline) and a connected drive."""
    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    monkeypatch.setattr(external, "VOLUMES", tmp_path / "Volumes")
    monkeypatch.setattr(external, "external", lambda path: path.is_dir())
    folder = tmp_path / "Pioneer/rekordbox"
    (folder / "share/PIONEER/USBANLZ").mkdir(parents=True)
    (folder / "master.db").write_bytes(b"collection")
    (folder / "masterPlaylists6.xml").write_text("<playlists/>")
    (folder / "share/PIONEER/USBANLZ/ANLZ0000.DAT").write_bytes(b"waveform")
    service.store.set_setting("rekordbox_db", str(folder / "master.db"))
    music = tmp_path / "Music"
    music.mkdir()
    (music / "one.mp3").write_bytes(b"x" * 1000)
    ingest(service, music / "one.mp3", source=str(folder / "master.db"))
    ingest(service, music / "gone.mp3", source=str(folder / "master.db"), source_id="2")
    drive = tmp_path / "Volumes/Backup Drive"
    drive.mkdir(parents=True)
    return folder, music, drive


def run(service, drive, scope, catalog=True):
    backup = ExternalBackup(service)
    backup.drive(str(drive))
    folder = drive / external.FOLDER / f"run-{len(list(drive.rglob('backup.json')))}"
    payload = {"drive": str(drive), "scope": scope, "catalog": catalog}
    return backup.run("job", {**payload, "folder": str(folder)}), folder


def test_drives_and_sizes_are_listed(service, library):
    folder, music, drive = library
    overview = ExternalBackup(service).overview()
    assert [d["name"] for d in overview["drives"]] == ["Backup Drive"]
    assert overview["sizes"]["database"] == len(b"collection") + len("<playlists/>")
    assert overview["sizes"]["rekordbox"] == overview["sizes"]["database"] + 8
    assert overview["sizes"]["music"] == 1000
    assert (overview["music_files"], overview["music_missing"]) == (1, 1)
    with pytest.raises(ValueError, match="not connected"):
        ExternalBackup(service).start(str(drive.parent / "Other"), "database", True)
    with pytest.raises(ValueError, match="what to back up"):
        ExternalBackup(service).start(str(drive), "everything", True)


def test_database_only(service, library):
    folder, music, drive = library
    (state, message), out = run(service, drive, "database", catalog=False)
    assert state == "complete" and "rekordbox database" in message
    assert (out / "rekordbox/master.db").read_bytes() == b"collection"
    assert (out / "rekordbox/masterPlaylists6.xml").is_file()
    assert not (out / "rekordbox/share").exists() and not (out / "songdex").exists()
    assert not (drive / external.FOLDER / "Music").exists()
    assert "README.txt" in os.listdir(out)


def test_whole_library_mirrors_music_and_copies_only_changes(service, library):
    folder, music, drive = library
    (state, message), out = run(service, drive, "library")
    assert state == "complete" and "1 music files were offline" in message
    assert (out / "rekordbox/share/PIONEER/USBANLZ/ANLZ0000.DAT").is_file()
    with sqlite3.connect(out / "songdex/songdex.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM tracks").fetchone()[0] == 2
    copy = drive / external.FOLDER / "Music" / (music / "one.mp3").relative_to("/")
    assert copy.read_bytes() == b"x" * 1000
    manifest = json.loads((out / "backup.json").read_text())
    assert manifest["tracks"] == [{"path": str(music / "one.mp3"), "backup": str(copy)}]
    assert service.store.setting("external_backups")[0]["drive"] == str(drive)
    assert ExternalBackup(service).drives()[0]["last"]["scope"] == "library"

    (state, message), _ = run(service, drive, "library")
    assert "1 music files already up to date" in message
    (music / "one.mp3").write_bytes(b"y" * 1000)
    os.utime(music / "one.mp3", (1, 1))
    run(service, drive, "library")
    assert copy.read_bytes() == b"y" * 1000


def test_backup_refuses_a_drive_without_room(service, library, monkeypatch):
    folder, music, drive = library
    monkeypatch.setattr(external, "MARGIN", 10**18)
    with pytest.raises(ValueError, match="needs"):
        run(service, drive, "library")
    assert not (drive / external.FOLDER / "Music").exists()


def test_api_lists_drives_and_checks_the_choice(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from songdex.api import create_app

    monkeypatch.setattr(external, "VOLUMES", tmp_path / "Volumes")
    client = TestClient(create_app(tmp_path / "dex"))
    headers = {"x-songdex-token": client.get("/api/state").json()["token"]}
    assert client.get("/api/backups/external").json()["drives"] == []
    response = client.post(
        "/api/backups/external",
        headers=headers,
        json={"drive": "/Volumes/Nope", "scope": "database"},
    )
    assert response.status_code == 409 and "not connected" in response.json()["detail"]
