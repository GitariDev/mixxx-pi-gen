import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from conftest import ingest
from fastapi.testclient import TestClient
from songdex import audio, rekordbox
from songdex.api import create_app
from songdex.backups import Backups
from songdex.db import Store, dump, now
from songdex.editing import Editing, revision
from songdex.importing import Importing
from songdex.service import Service


@pytest.fixture
def editing(service, monkeypatch):
    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    return Editing(service)


def job(service, iid):
    jid = str(uuid4())
    with service.store.connect() as db:
        db.execute(
            "INSERT INTO jobs(id,kind,state,payload,created_at) VALUES (?,?,?,?,?)",
            (jid, "import_music", "running", dump({"import_id": iid}), now()),
        )
    return jid


@pytest.fixture
def importer(service, tmp_path):
    destination = tmp_path / "Collection"
    destination.mkdir()
    service.store.set_setting("music_folder", str(destination))
    return Importing(service)


@pytest.mark.parametrize("ext", ["flac", "mp3", "aiff", "m4a"])
def test_direct_save_and_restore_file(editing, service, audio_file, ext):
    path = audio_file(ext)
    original = path.read_bytes()
    t = ingest(service, path)
    result = editing.save(
        t["id"], {"title": "New title", "genre": "House"}, revision(t)
    )
    assert result["saved"]
    assert audio.read(path)["title"] == "New title"
    t = service.store.track(t["id"])
    assert t["accepted"]["title"] == t["overrides"]["title"] == "New title"
    assert {s["file_status"] for s in editing.statuses(t["id"])} == {"saved"}
    assert {s["library_status"] for s in editing.statuses(t["id"])} == {"pending"}
    with service.store.connect() as db:
        wid = db.execute("SELECT id FROM local_writes").fetchone()[0]
    editing.restore(wid)
    assert path.read_bytes() == original
    assert service.store.track(t["id"])["accepted"]["title"] == "New title"
    assert {s["file_status"] for s in editing.statuses(t["id"])} == {"pending"}


def test_offline_save_reconnect_and_manual_locks(editing, service, audio_file):
    path = audio_file()
    t = ingest(service, path)
    parked = path.with_suffix(".offline")
    path.rename(parked)
    t = ingest(service, path)
    result = editing.save(t["id"], {"artist": "My artist"}, revision(t))
    assert "offline" in result["message"].lower()
    ingest(service, path)
    assert service.store.track(t["id"])["state"] == "unavailable"
    assert service.store.track(t["id"])["overrides"]["artist"] == "My artist"
    parked.rename(path)
    ingest(service, path)
    editing.sync(t["id"])
    assert audio.read(path)["artist"] == "My artist"
    ingest(service, path)
    assert service.store.track(t["id"])["state"] == "indexed"
    assert len(service.store.tracks()) == 1


def test_external_conflict_cannot_be_silently_synced(editing, service, audio_file):
    path = audio_file()
    t = ingest(service, path)
    editing.save(t["id"], {"title": "Mine"}, revision(t))
    audio.write(path, {"title": "Someone else"})
    ingest(service, path, title="External")
    t = service.store.track(t["id"])
    assert t["state"] == "conflict"
    assert "conflicting" in editing.sync(t["id"])["message"]
    assert audio.read(path)["title"] == "Someone else"
    # Saving again after explicitly reviewing the current entry resolves the conflict.
    editing.save(t["id"], {"title": "Mine"}, revision(t))
    assert audio.read(path)["title"] == "Mine"


def test_stale_editor_and_analysis_fields_rejected(editing, service, audio_file):
    t = ingest(service, audio_file())
    editing.save(t["id"], {"title": "First"}, revision(t))
    with pytest.raises(ValueError, match="changed while"):
        editing.save(t["id"], {"title": "Second"}, revision(t))
    with pytest.raises(ValueError, match="editable"):
        editing.save(t["id"], {"bpm": "150"}, revision(t))


def test_running_rekordbox_queues_without_losing_correction(
    editing, service, audio_file, monkeypatch
):
    path = audio_file()
    t = ingest(service, path)
    monkeypatch.setattr(
        rekordbox,
        "require_stopped",
        lambda: (_ for _ in ()).throw(ValueError("Close rekordbox first")),
    )
    assert (
        "Close rekordbox"
        in editing.save(t["id"], {"title": "Saved locally"}, revision(t))["message"]
    )
    assert audio.read(path)["title"] == "Original"
    assert service.store.track(t["id"])["accepted"]["title"] == "Saved locally"


def test_interrupted_file_write_recovers_after_restart(
    editing, service, audio_file, monkeypatch
):
    from songdex import editing as module

    path = audio_file()
    t = ingest(service, path)
    before = path.read_bytes()
    replace = module.replace_copy

    def crash(source, target):
        replace(source, target)
        raise RuntimeError("power interrupted")

    monkeypatch.setattr(module, "replace_copy", crash)
    result = editing.save(t["id"], {"title": "After"}, revision(t))
    assert "power interrupted" in result["message"]
    assert audio.read(path)["title"] == "After"
    monkeypatch.setattr(module, "replace_copy", replace)
    new = Editing(Service(Store(service.store.root)))
    with new.store.connect() as db:
        wid = db.execute("SELECT id FROM local_writes").fetchone()[0]
    new.restore(wid)
    assert path.read_bytes() == before


def test_import_copy_collision_duplicate_and_rekordbox_reconciliation(
    importer, service, audio_file, tmp_path
):
    path = audio_file()
    destination = Path(service.store.setting("music_folder"))
    (destination / path.name).write_text("Do not overwrite")
    plan = importer.preview([str(path)], "copy")
    entry = plan["entries"][0]
    assert Path(entry["destination"]).name == "track (1).flac"
    importer.run(job(service, plan["id"]), {"import_id": plan["id"]})
    assert path.exists()
    assert (destination / path.name).read_text() == "Do not overwrite"
    assert Path(entry["destination"]).read_bytes() == path.read_bytes()
    local = service.store.tracks()[0]
    assert local["source"] == "local"
    assert importer.preview([str(path)], "copy")["entries"][0]["status"] == "skipped"
    ingest(
        service, Path(entry["destination"]), source="/library/master.db", source_id="42"
    )
    assert len(service.store.tracks()) == 1
    assert service.store.tracks()[0]["id"] == local["id"]
    assert service.store.tracks()[0]["source_id"] == "42"


def test_import_folder_move_and_same_selection_duplicates(
    importer, service, audio_file, tmp_path
):
    source = tmp_path / "Downloads"
    source.mkdir()
    path = audio_file()
    shutil.move(path, source / path.name)
    path = source / path.name
    (source / "notes.txt").write_text("ignored")
    plan = importer.preview([str(source), str(path)], "move")
    assert len(plan["entries"]) == 1
    importer.run(job(service, plan["id"]), {"import_id": plan["id"]})
    assert not path.exists()
    assert Path(plan["entries"][0]["destination"]).is_file()
    assert (source / "notes.txt").exists()


def test_import_changed_source_retained_then_retry(importer, service, audio_file):
    path = audio_file()
    plan = importer.preview([str(path)], "move")
    original = path.read_bytes()
    path.write_bytes(b"changed")
    jid = job(service, plan["id"])
    with pytest.raises(ValueError, match="need attention"):
        importer.run(jid, {"import_id": plan["id"]})
    assert path.exists()
    assert not service.store.tracks()
    path.write_bytes(original)
    importer.run(jid, {"import_id": plan["id"]})
    assert len(service.store.tracks()) == 1
    assert importer.get(plan["id"])["state"] == "complete"


def test_import_publish_interruption_resumes_without_overwrite(
    importer, service, audio_file, monkeypatch
):
    import os

    path = audio_file()
    plan = importer.preview([str(path)], "copy")
    link = os.link

    def crash(a, b):
        link(a, b)
        raise RuntimeError("power interrupted")

    monkeypatch.setattr(os, "link", crash)
    with pytest.raises(ValueError):
        importer.run(job(service, plan["id"]), {"import_id": plan["id"]})
    assert importer.get(plan["id"])["entries"][0]["status"] == "publishing"
    monkeypatch.setattr(os, "link", link)
    importer.run(job(service, plan["id"]), {"import_id": plan["id"]})
    assert len(service.store.tracks()) == 1
    assert Path(plan["entries"][0]["destination"]).read_bytes() == path.read_bytes()


def test_import_rejects_parent_of_destination_and_symlink_escape(
    importer, service, audio_file, tmp_path
):
    with pytest.raises(ValueError, match="outside"):
        importer.preview([str(tmp_path)], "copy")
    source = tmp_path / "Downloads"
    source.mkdir()
    shutil.copy2(audio_file(), source / "track.flac")
    outside = tmp_path / "outside"
    outside.mkdir()
    root = Path(service.store.setting("music_folder"))
    (root / "Downloads").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="outside"):
        importer.preview([str(source)], "copy")


def test_import_does_not_overwrite_new_collision(importer, service, audio_file):
    path = audio_file()
    plan = importer.preview([str(path)], "move")
    dest = Path(plan["entries"][0]["destination"])
    dest.write_bytes(b"new file")
    with pytest.raises(ValueError):
        importer.run(job(service, plan["id"]), {"import_id": plan["id"]})
    assert dest.read_bytes() == b"new file" and path.exists()


def test_new_api_security_settings_and_offline_edit(tmp_path, monkeypatch):
    app = create_app(tmp_path / "state")
    client = TestClient(app)
    t = ingest(app.state.service, tmp_path / "missing.flac")
    state = client.get("/api/state").json()
    headers = {"x-songdex-token": state["token"]}
    assert (
        client.post("/api/files/browse", json={"path": str(tmp_path)}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/files/browse", headers=headers, json={"path": str(tmp_path)}
        ).status_code
        == 200
    )
    response = client.post(
        f"/api/tracks/{t['id']}/edit",
        headers=headers,
        json={
            "changes": {"title": "Offline edit"},
            "revision": state["tracks"][0]["revision"],
        },
    )
    assert response.status_code == 200 and response.json()["saved"]
    assert (
        client.get("/api/state").json()["tracks"][0]["accepted"]["title"]
        == "Offline edit"
    )
    assert (
        client.post(
            "/api/settings",
            headers=headers,
            json={"rekordbox_db": "/test/master.db", "music_folder": str(tmp_path)},
        ).status_code
        == 200
    )
    assert client.get("/api/state").json()["settings"]["music_folder"] == str(tmp_path)


def test_offline_native_write_and_restore_with_verified_adapter(
    editing, service, tmp_path, monkeypatch
):
    source = tmp_path / "library/master.db"
    source.parent.mkdir()
    source.write_bytes(b"original library")
    monkeypatch.setattr(rekordbox, "capability", lambda root: {"enabled": True})

    def snapshot(src, dest):
        dest.mkdir(parents=True)
        shutil.copy2(src, dest / "master.db")

    monkeypatch.setattr(rekordbox, "snapshot", snapshot)
    monkeypatch.setattr(
        rekordbox,
        "write_collection",
        lambda path, changes: path.write_bytes(b"new library"),
    )
    service.store.set_setting("rekordbox_db", str(source))
    service.store.set_setting("library_hash", audio.digest(source))
    t = ingest(service, tmp_path / "offline.flac", source=str(source))
    result = editing.save(t["id"], {"title": "Offline correction"}, revision(t))
    assert result["statuses"][0]["library_status"] == "saved"
    assert result["statuses"][0]["file_status"] == "pending"
    assert source.read_bytes() == b"new library"
    with service.store.connect() as db:
        wid = db.execute("SELECT id FROM local_writes WHERE kind='library'").fetchone()[
            0
        ]
    editing.restore(wid)
    assert source.read_bytes() == b"original library"
    assert service.store.track(t["id"])["metadata"]["title"] == "Original"
    assert service.store.track(t["id"])["accepted"]["title"] == "Offline correction"


def test_file_restore_refuses_newer_tags(editing, service, audio_file):
    path = audio_file()
    t = ingest(service, path)
    editing.save(t["id"], {"title": "Saved"}, revision(t))
    with service.store.connect() as db:
        wid = db.execute("SELECT id FROM local_writes").fetchone()[0]
    audio.write(path, {"title": "Newer edit"})
    with pytest.raises(ValueError, match="newer changes"):
        editing.restore(wid)
    assert audio.read(path)["title"] == "Newer edit"


def test_write_that_fails_while_preparing_does_not_block_later_writes(
    editing, service, audio_file, monkeypatch
):
    path = audio_file()
    t = ingest(service, path)

    def crash(target, changes):
        raise RuntimeError("stopped while preparing")

    monkeypatch.setattr(audio, "write", crash)
    editing.save(t["id"], {"title": "Saved"}, revision(t))
    monkeypatch.undo()
    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    with service.store.connect() as db:
        wid, state = db.execute("SELECT id,state FROM local_writes").fetchone()
    # Nothing reached the file, so there is nothing to recover and nothing waits on it.
    assert state == "failed" and audio.read(path)["title"] == "Original"
    with pytest.raises(ValueError, match="No restorable write"):
        editing.restore(wid)
    editing.sync(t["id"])
    assert audio.read(path)["title"] == "Saved"
    # The same holds when the process was killed while preparing.
    with service.store.connect() as db:
        db.execute("UPDATE local_writes SET state='preparing' WHERE id=?", (wid,))
    Store(service.store.root)
    with service.store.connect() as db:
        row = db.execute("SELECT state FROM local_writes WHERE id=?", (wid,)).fetchone()
    assert row[0] == "failed"


def test_older_interrupted_write_without_a_destination_change_can_be_cleared(
    editing, service, audio_file
):
    path = audio_file()
    t = ingest(service, path)
    editing.journal(
        "w",
        t["id"],
        "file",
        "recovery_required",
        {"path": str(path), "backup": "", "before": "", "changes": {"title": "X"}},
    )
    audio.write(path, {"title": "Newer edit"})
    assert "message" in editing.restore("w")
    assert audio.read(path)["title"] == "Newer edit"
    with service.store.connect() as db:
        assert db.execute("SELECT state FROM local_writes").fetchone()[0] == "restored"


def test_finished_write_keeps_only_its_backup(editing, service, audio_file):
    path = audio_file()
    t = ingest(service, path)
    editing.save(t["id"], {"title": "Saved"}, revision(t))
    (folder,) = (service.store.root / "backups").iterdir()
    assert [p.name for p in folder.iterdir()] == ["original.flac"]


def test_low_disk_space_stops_writes_before_they_start(
    editing, service, audio_file, monkeypatch, tmp_path
):
    path = audio_file()
    t = ingest(service, path)
    before = path.read_bytes()
    usage = shutil.disk_usage(path)
    monkeypatch.setattr(
        shutil, "disk_usage", lambda folder: usage._replace(free=audio.MB)
    )
    result = editing.save(t["id"], {"title": "Saved"}, revision(t))
    assert "Not enough free disk space" in result["message"]
    assert path.read_bytes() == before
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM local_writes").fetchone()[0] == 0
    # A batch stops outright, so the job reports the shortage instead of noting it per track.
    library = tmp_path / "master.db"
    library.write_bytes(b"library")
    service.store.set_setting("rekordbox_db", str(library))
    job_id = job(service, "unused")
    with pytest.raises(ValueError, match="free disk space"):
        editing.sync_pending(job_id)


def test_job_that_dies_with_an_unwritable_catalog_is_recorded_later(
    service, monkeypatch
):
    job_id, progress = job(service, "unused"), service.progress
    with service.store.connect() as db:
        db.execute("UPDATE jobs SET kind='sync_edits' WHERE id=?", (job_id,))

    def unwritable(*args, **fields):
        raise OSError("No space left on device")

    monkeypatch.setattr(service, "progress", unwritable)
    service.lock.acquire()
    service.run(job_id)
    monkeypatch.setattr(service, "progress", progress)
    service.settle()
    with service.store.connect() as db:
        state, message = db.execute("SELECT state,message FROM jobs").fetchone()
    assert (state, message) == ("failed", "No space left on device")
    assert service.unrecorded is None and not service.lock.locked()


def test_backups_are_listed_with_sizes_and_deleted_on_request(
    editing, service, audio_file
):
    path = audio_file()
    t = ingest(service, path)
    editing.save(t["id"], {"title": "Saved"}, revision(t))
    stray = service.store.root / "backups" / "notes.txt"
    stray.write_text("kept by hand")
    backups = Backups(service)
    listing = backups.list()
    other, write = listing["items"]
    assert other["id"] == "notes.txt" and listing["free"] > 0
    assert listing["total"] == sum(i["size"] for i in listing["items"])
    assert write["size"] > 0 and "title → Saved" in write["detail"]
    assert write["undoable"] and not other["undoable"]
    with pytest.raises(ValueError, match="refresh"):
        backups.delete(["../songdex.sqlite3"])
    with service.store.connect() as db:
        db.execute("UPDATE local_writes SET state='recovery_required'")
    with pytest.raises(ValueError, match="unfinished write"):
        backups.delete([write["id"]])
    with service.store.connect() as db:
        db.execute("UPDATE local_writes SET state='complete'")
    assert backups.delete([write["id"], "notes.txt"])["freed"] == (
        write["size"] + other["size"]
    )
    assert backups.list()["items"] == []
    with pytest.raises(ValueError, match="was deleted"):
        editing.restore(write["id"][len("manual-") :])
    assert audio.read(path)["title"] == "Saved"


def test_backups_that_can_no_longer_be_undone_are_removed(editing, service, audio_file):
    path = audio_file()
    t = ingest(service, path)
    backups, folder = Backups(service), service.store.root / "backups"
    for title in ("First", "Second"):
        editing.save(t["id"], {"title": title}, revision(service.store.track(t["id"])))
    # The second write spent the first one's backup; its own can still be undone.
    (second,) = backups.list()["items"]
    assert second["undoable"] and "title → Second" in second["detail"]
    with service.store.connect() as db:
        deleted = [
            "backup_deleted" in r[0]
            for r in db.execute("SELECT manifest FROM local_writes ORDER BY created_at")
        ]
    assert deleted == [True, False]
    # A file that is offline may match again once its drive is back, so it is kept.
    away = path.rename(path.with_suffix(".away"))
    assert backups.prune() == 0 and not backups.list()["items"][0]["undoable"]
    away.rename(path)
    # Restoring a write spends its backup, and so does a change made elsewhere.
    (folder / "notes.txt").write_text("kept by hand")
    editing.restore(second["id"][len("manual-") :])
    assert [p.name for p in folder.iterdir()] == ["notes.txt"]
    editing.save(t["id"], {"title": "Third"}, revision(service.store.track(t["id"])))
    assert len(list(folder.iterdir())) == 2
    audio.write(path, {"title": "Edited elsewhere"})
    assert backups.prune() == 1
    assert [p.name for p in folder.iterdir()] == ["notes.txt"]


def test_import_stale_preview_rechecks_duplicate(importer, service, audio_file):
    path = audio_file()
    first = importer.preview([str(path)], "copy")
    second = importer.preview([str(path)], "copy")
    importer.run(job(service, first["id"]), {"import_id": first["id"]})
    importer.run(job(service, second["id"]), {"import_id": second["id"]})
    assert len(service.store.tracks()) == 1
    assert importer.get(second["id"])["entries"][0]["status"] == "skipped"


def test_import_exfat_fallback(importer, service, audio_file, monkeypatch):
    import errno
    import os

    path = audio_file()
    plan = importer.preview([str(path)], "copy")

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "No hard links")

    monkeypatch.setattr(os, "link", unsupported)
    importer.run(job(service, plan["id"]), {"import_id": plan["id"]})
    assert Path(plan["entries"][0]["destination"]).read_bytes() == path.read_bytes()


def test_restart_preserves_local_edits_and_import_receipt(service):
    with service.store.connect() as db:
        db.execute("INSERT INTO imports VALUES ('one','running','{}','today')")
        db.execute(
            "INSERT INTO local_writes VALUES ('write',NULL,'file','writing','{}','today')"
        )
    restarted = Store(service.store.root)
    with restarted.connect() as db:
        assert db.execute("SELECT state FROM imports").fetchone()[0] == "interrupted"
        assert (
            db.execute("SELECT state FROM local_writes").fetchone()[0]
            == "recovery_required"
        )
