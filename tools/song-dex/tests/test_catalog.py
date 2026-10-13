from conftest import ingest
from songdex.db import Store, dump
from songdex.demo import seed
from songdex.providers import Providers


def test_scan_idempotent_and_moves_keep_id(service, audio_file):
    p = audio_file()
    first = ingest(service, p)
    second = ingest(service, p)
    assert first["id"] == second["id"] and len(service.store.tracks()) == 1
    moved = p.with_name("moved.flac")
    p.rename(moved)
    third = ingest(service, moved)
    assert third["id"] == first["id"] and third["path"] == str(moved)
    moved.unlink()
    ingest(service, moved)
    assert service.store.track(first["id"])["state"] == "unavailable"


def test_external_changes_conflict_with_accepted(service, audio_file):
    p = audio_file()
    t = ingest(service, p)
    with service.store.connect() as db:
        db.execute(
            "UPDATE tracks SET accepted=? WHERE id=?",
            (dump({"title": "Reviewed"}), t["id"]),
        )
    ingest(service, p)
    assert service.store.track(t["id"])["state"] == "conflict"


def test_rejected_proposals_stay_rejected_and_overrides_win(service, audio_file):
    t = ingest(service, audio_file())
    service.store.propose(t, "genre", "House", "high", "Evidence", "test")
    with service.store.connect() as db:
        db.execute("UPDATE proposals SET status='rejected'")
    service.store.propose(t, "genre", "House", "high", "Evidence", "test")
    assert not service.store.proposals()
    t["overrides"] = {"genre": "Soul"}
    service.store.propose(t, "genre", "Disco", "high", "Evidence", "test")
    assert not service.store.proposals()


def test_duplicate_versions_warn_and_exact_files_group(store, service):
    seed(store)
    groups = service.duplicates()
    assert any(g["kind"] == "exact" and len(g["tracks"]) == 2 for g in groups)
    related = next(g for g in groups if g["kind"] == "related")
    assert "Different version labels" in related["warnings"]
    assert "Duration differs significantly" in related["warnings"]


def test_restart_marks_jobs_interrupted(store):
    with store.connect() as db:
        db.execute(
            "INSERT INTO jobs VALUES ('one','enrich','running','{}',3,10,'','today')"
        )
    restarted = Store(store.root)
    with restarted.connect() as db:
        row = db.execute("SELECT * FROM jobs").fetchone()
        assert row["state"] == "interrupted" and row["progress"] == 3


def test_provider_version_conflict_has_no_proposals(service, audio_file, monkeypatch):
    t = ingest(service, audio_file(), title="Original (Extended Mix)", duration=2)
    provider = Providers(service.store)
    monkeypatch.setattr(
        provider,
        "get",
        lambda *args: {
            "recordings": [
                {
                    "id": "x",
                    "title": "Original",
                    "length": 2000,
                    "artist-credit": [{"name": "Artist"}],
                }
            ]
        },
    )
    evidence = provider.enrich(t)
    assert evidence[0]["version_conflict"]
    assert not service.store.proposals()


def test_ambiguous_album_not_overwritten(service, audio_file, monkeypatch):
    t = ingest(service, audio_file())
    provider = Providers(service.store)
    monkeypatch.setattr(
        provider,
        "get",
        lambda *args: {
            "recordings": [
                {
                    "id": "x",
                    "title": "Original",
                    "length": 2000,
                    "artist-credit": [{"name": "Artist"}],
                    "releases": [
                        {"id": "a", "title": "Compilation"},
                        {"id": "b", "title": "Reissue"},
                    ],
                }
            ]
        },
    )
    provider.enrich(t)
    assert not service.store.proposals()


def test_distinct_remixers_are_not_same_version():
    from songdex.providers import version_signature

    assert version_signature("Track (Alice Remix)") != version_signature(
        "Track (Bob Remix)"
    )


def test_unchanged_rescan_keeps_evidence(service, audio_file):
    p = audio_file()
    t = ingest(service, p)
    with service.store.connect() as db:
        db.execute(
            "UPDATE tracks SET evidence=? WHERE id=?",
            (dump([{"provider": "test"}]), t["id"]),
        )
    ingest(service, p)
    assert service.store.track(t["id"])["evidence"] == [{"provider": "test"}]


def test_stale_proposal_can_be_recomputed(service, audio_file):
    t = ingest(service, audio_file())
    service.store.propose(t, "genre", "House", "high", "Evidence", "test")
    with service.store.connect() as db:
        db.execute("UPDATE proposals SET status='stale'")
    service.store.propose(t, "genre", "House", "review", "Changed evidence", "test")
    assert service.store.proposals()[0]["confidence"] == "review"


def test_native_metadata_matches_but_file_tag_differs(service, audio_file):
    track = ingest(service, audio_file(), title="Reviewed title")
    service.store.propose(track, "title", "Reviewed title", "high", "Match", "test")
    assert service.store.proposals()[0]["new_value"] == "Reviewed title"


def test_disconnected_drive_keeps_known_metadata_and_evidence(service, audio_file):
    path = audio_file()
    track = ingest(service, path)
    with service.store.connect() as db:
        db.execute(
            "UPDATE tracks SET evidence=? WHERE id=?",
            (dump([{"provider": "test"}]), track["id"]),
        )
    path.rename(path.with_name("disconnected.flac"))
    ingest(service, path)
    saved = service.store.track(track["id"])
    assert not saved["available"]
    assert saved["file_hash"] == track["file_hash"]
    assert saved["evidence"] == [{"provider": "test"}]
    assert saved["file_metadata"] == track["file_metadata"]
