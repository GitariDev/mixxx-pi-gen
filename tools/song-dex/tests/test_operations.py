import shutil
from pathlib import Path

import pytest
from conftest import ingest
from songdex import audio, rekordbox
from songdex.operations import Operations


@pytest.fixture
def prepared(service, audio_file, tmp_path, monkeypatch):
    source = tmp_path / "library/master.db"
    source.parent.mkdir()
    source.write_bytes(b"original database fixture")
    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    monkeypatch.setattr(
        rekordbox,
        "capability",
        lambda root: {"enabled": True, "report": {"verified_formats": [".flac"]}},
    )

    def snapshot(src, dst):
        dst.mkdir(parents=True)
        shutil.copy2(src, dst / "master.db")
        return audio.digest(src)

    def write(path, changes):
        path.write_bytes(b"updated database fixture")

    monkeypatch.setattr(rekordbox, "snapshot", snapshot)
    monkeypatch.setattr(rekordbox, "write_collection", write)
    service.store.set_setting("rekordbox_db", str(source))
    service.store.set_setting("library_hash", audio.digest(source))
    t = ingest(service, audio_file(), source=str(source))
    service.store.propose(
        t, "title", "Reviewed title", "high", "User correction", "manual"
    )
    return Operations(service), source, t, [service.store.proposals()[0]["id"]]


def test_apply_restore_roundtrip(prepared):
    op, source, t, ids = prepared
    before = audio.digest(t["path"])
    result = op.apply(ids)
    assert result["manifest"]["dex_status"] == "complete"
    assert result["manifest"]["library_status"] == "complete"
    assert audio.read(t["path"])["title"] == "Reviewed title"
    assert op.store.track(t["id"])["overrides"]["title"] == "Reviewed title"
    op.restore(result["id"])
    assert audio.digest(t["path"]) == before
    assert source.read_bytes() == b"original database fixture"
    assert not op.store.track(t["id"])["accepted"]


def test_stale_file_cannot_be_written(prepared):
    op, source, t, ids = prepared
    audio.write(t["path"], {"title": "External edit"})
    with pytest.raises(ValueError, match="changed after review"):
        op.apply(ids)
    assert source.read_bytes() == b"original database fixture"


def test_stale_library_cannot_be_written(prepared):
    op, source, t, ids = prepared
    source.write_bytes(b"external library edit")
    with pytest.raises(ValueError, match="rekordbox changed"):
        op.apply(ids)


def test_interrupted_write_is_recoverable(prepared, monkeypatch):
    import songdex.operations as mod

    op, source, t, ids = prepared
    original = mod.replace_copy

    def fail_db(src, dest):
        if Path(dest) == source:
            raise OSError("simulated drive failure")
        original(src, dest)

    monkeypatch.setattr(mod, "replace_copy", fail_db)
    result = op.apply(ids)
    assert result["manifest"]["error"] == "simulated drive failure"
    assert audio.read(t["path"])["title"] == "Reviewed title"
    assert not op.store.track(t["id"])["accepted"]
    with pytest.raises(ValueError):
        op.apply(ids)
    monkeypatch.setattr(mod, "replace_copy", original)
    op.restore(result["id"])
    assert audio.read(t["path"])["title"] == "Original"


def test_restore_refuses_to_erase_newer_edits(prepared):
    op, source, t, ids = prepared
    result = op.apply(ids)
    source.write_bytes(b"newer library changes")
    with pytest.raises(ValueError, match="protect newer edits"):
        op.restore(result["id"])
    assert source.read_bytes() == b"newer library changes"
