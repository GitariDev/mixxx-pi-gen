import shutil
import threading

import pytest
from conftest import ingest
from songdex import rekordbox, scanning
from songdex.editing import Editing
from songdex.scanning import Scanning, scope
from songdex.tagging import Tagging

CHOICES = {
    "tags": [{"id": "10", "name": "Afro", "category": "Genre"}],
    "playlists": [{"id": "100", "name": "Warm up"}],
}


@pytest.fixture
def library(service, audio_file, tmp_path, monkeypatch):
    """Three tracks; the second has no genre, the third was looked up already."""
    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    service.store.set_setting("library_choices", CHOICES)
    tracks = []
    for n, genre in enumerate(("House", "", "Disco")):
        path = tmp_path / f"track{n}.flac"
        shutil.copy(audio_file(), path)
        tracks.append(
            ingest(service, path, source_id=str(n), title=f"Song {n}", genre=genre)
        )
    with service.store.connect() as db:
        db.execute(
            'UPDATE tracks SET evidence=\'[{"provider": "MusicBrainz"}]\' WHERE id=?',
            (tracks[2]["id"],),
        )
    return [t["id"] for t in tracks]


def run(service, ids):
    jid = service.start("enrich", {"ids": ids, "label": "Test"})
    service.lock.acquire()
    service.lock.release()
    with service.store.connect() as db:
        return jid, dict(db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())


def test_scope_picks_new_all_by_type_and_custom(service, library):
    tracks = service.store.tracks()
    assert scope(tracks, "new") == (library[:2], "New tracks")
    assert scope(tracks, "all") == (library, "Full library")
    assert scope(tracks, "type", "genre") == ([library[1]], "Genre sync")
    assert scope(tracks, "custom", ids=[library[2], 999]) == (
        [library[2]],
        "Custom filter",
    )
    with pytest.raises(ValueError, match="No tracks match"):
        scope(tracks, "type", "artist")
    with pytest.raises(ValueError, match="Choose what"):
        scope(tracks, "type", "nonsense")


def test_scan_runs_each_lookup_and_lists_every_track(service, library, monkeypatch):
    order = []

    def enrich(track, genre=True):
        assert genre is False  # The genre has its own worker.
        order.append(("catalog", track["id"]))
        if track["id"] == library[0]:
            service.store.propose(track, "year", "1999", "high", "Match", "mb")
        return [{"provider": "MusicBrainz"}]

    def find_genre(track):
        order.append(("genre", track["id"]))
        service.store.propose(track, "genre", "Afro House", "review", "Style", "dg")

    monkeypatch.setattr(service.providers, "enrich", enrich)
    monkeypatch.setattr(service.providers, "find_genre", find_genre)
    jid, job = run(service, library)
    assert (job["state"], job["progress"], job["total"]) == ("complete", 3, 3)
    latest = Scanning(service).latest()
    assert latest["job_id"] == jid and latest["label"] == "Test"
    assert [i[0] for i in latest["items"]] == library
    states = {i[0]: tuple(i[1:]) for i in latest["items"]}
    # Only the track without a genre gets a genre lookup.
    assert states[library[1]] == ("done", "done", "done")
    assert states[library[0]] == ("done", "skipped", "done")
    # A track's genre waits for its catalog match.
    assert order.index(("catalog", library[1])) < order.index(("genre", library[1]))
    assert {(p["track_id"], p["field"]) for p in service.store.proposals()} == {
        (library[0], "year"),
        (library[1], "genre"),
    }
    # The suggested genre suggests the Afro tag.
    suggested = Tagging(service).suggested()
    assert {(s["track_id"], s["kind"], s["target"]) for s in suggested} >= {
        (library[1], "tag", "10")
    }


def test_turned_down_suggestions_stay_down_and_approved_ones_wait(service, library):
    tagging = Tagging(service)
    tid = library[1]
    found = [
        {"kind": "tag", "id": "10", "reasons": ["Genre Afro House"]},
        {"kind": "playlist", "id": "100", "reasons": ["2 of your tracks"]},
    ]
    tagging.keep_suggestions(tid, found)
    assert (
        tagging.decide([{"track_id": tid, "kind": "tag", "target": "10"}], False) == 1
    )
    assert (
        tagging.decide([{"track_id": tid, "kind": "playlist", "target": "100"}], True)
        == 1
    )
    tagging.keep_suggestions(tid, found)
    assert tagging.suggested() == []
    assert [(a["kind"], a["target"]) for a in tagging.assignments("pending")] == [
        ("playlist", "100")
    ]
    with pytest.raises(ValueError, match="no longer in rekordbox"):
        tagging.keep_suggestions(tid, [{"kind": "tag", "id": "99", "reasons": []}])
        tagging.decide([{"track_id": tid, "kind": "tag", "target": "99"}], True)


def test_approvals_during_a_scan_are_queued_then_saved(service, library, monkeypatch):
    started, release = threading.Event(), threading.Event()
    service.store.propose(
        service.store.track(library[1]), "genre", "Soul", "high", "Match", "mb"
    )
    (proposal,) = service.store.proposals()

    def enrich(track, genre=True):
        started.set()
        release.wait(5)
        return []

    monkeypatch.setattr(service.providers, "enrich", enrich)
    monkeypatch.setattr(service.providers, "find_genre", lambda track: None)
    service.start("enrich", {"ids": library[:1], "label": "Test"})
    assert started.wait(5)
    result = Editing(service).approve([proposal["id"]])
    assert (
        result["queued"] == [proposal["id"]]
        and "saved as the scan" in result["message"]
    )
    assert Editing(service).queued() == [proposal["id"]]
    release.set()
    service.lock.acquire()
    service.lock.release()
    assert Editing(service).queued() == []
    assert service.store.track(library[1])["accepted"] == {"genre": "Soul"}
    assert service.store.proposals() == []


def test_approval_queued_after_the_scan_let_go_is_still_saved(service, library):
    service.store.propose(
        service.store.track(library[1]), "genre", "Soul", "high", "Match", "mb"
    )
    (proposal,) = service.store.proposals()
    # Nothing holds the lock, so queueing saves it straight away.
    Editing(service).queue([proposal["id"]])
    assert service.store.track(library[1])["accepted"] == {"genre": "Soul"}


def test_a_stopped_scan_resumes_where_it_stopped(service, library, monkeypatch):
    seen, started, release = [], threading.Event(), threading.Event()

    def enrich(track, genre=True):
        seen.append(track["id"])
        if len(seen) == 1:
            started.set()
            release.wait(5)
        return []

    monkeypatch.setattr(service.providers, "enrich", enrich)
    monkeypatch.setattr(service.providers, "find_genre", lambda track: None)
    jid = service.start("enrich", {"ids": library, "label": "Test"})
    assert started.wait(5)
    scanning.stop(service.store)
    release.set()
    service.lock.acquire()
    service.lock.release()
    with service.store.connect() as db:
        assert db.execute("SELECT state FROM jobs WHERE id=?", (jid,)).fetchone()[
            0
        ] == ("interrupted")
    assert seen == library[:1]
    service.start("enrich", None, jid)
    service.lock.acquire()
    service.lock.release()
    assert seen == library
    states = Scanning(service).latest()["items"]
    assert all(s in ("done", "skipped") for item in states for s in item[1:])
