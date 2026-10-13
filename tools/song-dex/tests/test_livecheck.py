import importlib.metadata
import shutil

import pytest
from songdex import audio, livecheck, rekordbox, verify

GOOD = {
    "checks": {"metadata_kept": True, "playlists_kept": True},
    "changed_by_rekordbox": {},
    "session_work": {},
    "learned_smart_lists": {},
}


@pytest.fixture
def library(tmp_path, audio_file, monkeypatch):
    """A fake rekordbox layer around real audio files, a database file and its playlist XML."""
    source = tmp_path / "library/master.db"
    source.parent.mkdir()
    source.write_bytes(b"original database")
    xml = source.parent / "masterPlaylists6.xml"
    xml.write_bytes(b"original playlists")
    rolling = source.parent / "master.backup.db"
    rolling.write_bytes(b"rekordbox's own backup")
    files = [audio_file("flac"), audio_file("mp3")]
    rows = [
        {
            "source_id": str(index),
            "path": str(path),
            "metadata": {"title": "Original", "artist": "Artist", "year": "1994"},
            "playlists": [],
            "my_tags": [],
        }
        for index, path in enumerate([*files, tmp_path / "offline.flac"], 1)
    ]

    def snapshot(src, destination):
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, destination / "master.db")
        shutil.copy2(src.parent / xml.name, destination / xml.name)
        return audio.digest(src)

    def write_playlists(path, plan):
        path.write_bytes(path.read_bytes() + b" + playlists")
        (path.parent / xml.name).write_bytes(b"playlists registered")

    monkeypatch.setattr(
        rekordbox, "installed_version", lambda: rekordbox.TARGET_VERSION
    )
    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    monkeypatch.setattr(rekordbox, "snapshot", snapshot)
    monkeypatch.setattr(rekordbox, "read_collection", lambda path: rows)
    monkeypatch.setattr(
        rekordbox, "write_collection", lambda path, updates: path.write_bytes(b"edited")
    )
    monkeypatch.setattr(rekordbox, "write_playlists", write_playlists)
    monkeypatch.setattr(livecheck, "cued_ids", lambda path: set())
    monkeypatch.setattr(livecheck, "readback", lambda folder, state: GOOD)
    monkeypatch.setattr(
        verify,
        "verify",
        lambda source, output: {
            "rekordbox_version": rekordbox.TARGET_VERSION,
            "adapter_version": importlib.metadata.version("pyrekordbox"),
            "clone_roundtrip": True,
        },
    )
    before = {p: audio.digest(p) for p in [source, xml, rolling, *files]}
    return tmp_path / "dex", source, files, before


def unchanged(before):
    return all(audio.digest(path) == digest for path, digest in before.items())


def test_passing_check_restores_everything_and_unlocks_writes(library):
    root, source, files, before = library
    state = livecheck.start(root, source)
    assert state["formats"] == [".flac", ".mp3"]
    assert state["expected"]["Check list"] == 3
    assert source.read_bytes() == b"edited + playlists"
    assert audio.read(files[0])["artist"] == "Song Dex check artist"
    assert audio.read(files[1])["title"] == "Original [Song Dex check]"
    with pytest.raises(ValueError, match="in progress"):
        livecheck.start(root, source)
    assert rekordbox.capability(root)["enabled"] is False
    source.write_bytes(b"rekordbox opened and saved this")
    (source.parent / "master.backup.db").write_bytes(b"rotated with test changes")
    report = livecheck.finish(root, seen=list(livecheck.QUESTIONS))
    assert unchanged(before)
    assert report["rekordbox_restart_verified"] is True
    assert report["verified_formats"] == [".flac", ".mp3"]
    assert rekordbox.capability(root)["enabled"] is True


def test_unconfirmed_or_unopened_check_keeps_writes_locked(library):
    root, source, files, before = library
    livecheck.start(root, source)
    # rekordbox never opened the library: the readback proves nothing.
    report = livecheck.finish(root, seen=list(livecheck.QUESTIONS))
    assert unchanged(before)
    assert report["rekordbox_restart_verified"] is False
    livecheck.start(root, source)
    source.write_bytes(b"rekordbox opened and saved this")
    report = livecheck.finish(root, ask=lambda question: "n")
    assert unchanged(before)
    assert report["verified_formats"] == []
    assert rekordbox.capability(root)["enabled"] is False


def test_session_work_blocks_restore_until_discarded(library, monkeypatch):
    root, source, files, before = library
    livecheck.start(root, source)
    source.write_bytes(b"rekordbox opened and imported tracks")
    monkeypatch.setattr(
        livecheck,
        "readback",
        lambda folder, state: {**GOOD, "session_work": {"djmdContent": 2}},
    )
    with pytest.raises(ValueError, match="new work"):
        livecheck.finish(root, seen=[])
    assert source.read_bytes() == b"rekordbox opened and imported tracks"
    livecheck.finish(root, seen=[], discard=True)
    assert unchanged(before)


def test_cancel_restores_and_db_only_leaves_files_alone(library):
    root, source, files, before = library
    state = livecheck.start(root, source, db_only=True)
    assert len(state["tracks"]) == 1
    assert all(audio.digest(path) == before[path] for path in files)
    livecheck.cancel(root)
    assert unchanged(before)
    assert not (root / "compatibility.json").exists()
    livecheck.start(root, source, db_only=True)
    source.write_bytes(b"rekordbox opened and saved this")
    report = livecheck.finish(root, seen=list(livecheck.QUESTIONS))
    assert report["rekordbox_restart_verified"] is True
    assert report["verified_formats"] == []


def test_externally_changed_file_is_never_overwritten(library):
    root, source, files, before = library
    livecheck.start(root, source)
    audio.write(files[0], {"title": "Edited elsewhere during the check"})
    with pytest.raises(ValueError, match="changed during the check"):
        livecheck.cancel(root)
    assert audio.read(files[0])["title"] == "Edited elsewhere during the check"
    assert source.read_bytes() == b"edited + playlists"
