from types import SimpleNamespace

from conftest import ingest
from songdex import rekordbox
from songdex.db import Store


def test_tag_membership_preserves_category_and_stable_identity():
    from pyrekordbox.db6 import tables

    tags = [
        SimpleNamespace(ID="1", Name="Energy", ParentID="0"),
        SimpleNamespace(ID="2", Name="Warm", ParentID="1"),
        SimpleNamespace(ID="3", Name="Mood", ParentID="0"),
        SimpleNamespace(ID="4", Name="Warm", ParentID="3"),
    ]
    links = [
        SimpleNamespace(MyTagID="2", ContentID="99"),
        SimpleNamespace(MyTagID="4", ContentID="99"),
        SimpleNamespace(MyTagID="missing", ContentID="99"),
    ]

    class DB:
        def query(self, table):
            return tags if table == tables.DjmdMyTag else links

    assert rekordbox.tag_membership(DB()) == {
        "99": [
            {"id": "2", "name": "Warm", "category": "Energy"},
            {"id": "4", "name": "Warm", "category": "Mood"},
        ]
    }


def test_scan_and_availability_preserve_native_tags(service, audio_file):
    path = audio_file()
    t = ingest(service, path)
    assert t["my_tags_loaded"] == 0
    row = {
        "source_id": "1",
        "path": str(path),
        "metadata": t["metadata"],
        "playlists": [],
        "my_tags": [{"id": "a", "name": "Warm", "category": "Energy"}],
    }
    service.ingest("test", row)
    assert service.store.track(t["id"])["my_tags"][0]["name"] == "Warm"
    assert service.store.track(t["id"])["my_tags_loaded"] == 1
    ingest(service, path)
    assert service.store.track(t["id"])["my_tags"][0]["name"] == "Warm"
    service.ingest("test", {**row, "my_tags": []})
    assert service.store.track(t["id"])["my_tags"] == []


def test_schema_upgrade_is_idempotent(store):
    Store(store.root)
    with store.connect() as db:
        names = [r["name"] for r in db.execute("PRAGMA table_info(tracks)")]
    assert names.count("my_tags") == 1 and names.count("my_tags_loaded") == 1


def test_load_saved_tags_is_scoped_to_the_scanned_library(
    service, tmp_path, monkeypatch
):
    import pytest
    from songdex import audio
    from songdex.db import dump, now

    source = str(tmp_path / "library/master.db")
    track = ingest(service, tmp_path / "offline.mp3", source=source)
    copy = service.store.root / "snapshots/scan1/master.db"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(b"saved native scan")
    with service.store.connect() as db:
        db.execute(
            "INSERT INTO jobs(id,kind,state,payload,created_at) VALUES (?,?,?,?,?)",
            ("scan1", "scan", "complete", dump({}), now()),
        )
    service.store.set_setting("rekordbox_db", source)
    service.store.set_setting("library_hash", audio.digest(copy))
    service.store.set_setting("last_scan_source", source)

    def read_tags(path):
        assert path == copy
        return {"1": [{"id": "tag", "name": "Warm", "category": "Energy"}]}

    monkeypatch.setattr(rekordbox, "read_my_tags", read_tags)
    service.load_my_tags()
    assert service.store.track(track["id"])["my_tags"][0]["name"] == "Warm"
    service.store.set_setting("rekordbox_db", str(tmp_path / "different/master.db"))
    with pytest.raises(ValueError, match="different library"):
        service.load_my_tags()
