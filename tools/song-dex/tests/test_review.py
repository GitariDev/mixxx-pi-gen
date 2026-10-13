import pytest
from conftest import ingest
from songdex import audio, rekordbox
from songdex.db import Store
from songdex.editing import Editing, revision


@pytest.fixture
def editing(service, monkeypatch):
    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    return Editing(service)


def test_restyled_spellings_are_not_suggested(service, audio_file):
    t = ingest(service, audio_file())
    for value in ("ORIGINAL", " original", "Original!", "Órigínal", "‘Original’"):
        service.store.propose(t, "title", value, "high", "Evidence", "provider")
    assert not service.store.proposals()
    service.store.propose(t, "title", "Original (Remix)", "high", "Evidence", "x")
    # The user's own restyling is always a real change.
    service.store.propose(t, "artist", "ARTIST", "high", "Manual", "manual")
    assert {p["field"] for p in service.store.proposals()} == {"title", "artist"}


def test_restyled_suggestions_already_stored_are_retired(service, audio_file):
    t = ingest(service, audio_file(), title="Original", genre="House")
    with service.store.connect() as db:
        for field, old, value in (
            ("title", "Original", "ORIGINAL"),
            ("genre", "House", "Disco"),
        ):
            db.execute(
                "INSERT INTO proposals(track_id,field,old_value,new_value,confidence,reason,source,signature,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (t["id"], field, old, value, "high", "", "provider", "", ""),
            )
    assert [p["field"] for p in Store(service.store.root).proposals()] == ["genre"]


def test_approve_saves_now_and_queues_what_cannot_be_written(
    editing, service, audio_file
):
    path = audio_file()
    t = ingest(service, path)
    service.store.propose(t, "genre", "House", "high", "Evidence", "provider")
    service.store.propose(t, "year", "1999", "review", "Evidence", "provider")
    ids = [p["id"] for p in service.store.proposals()]
    result = editing.approve(ids[:1])
    assert result["approved"] == 1 and "Saved in Song Dex" in result["message"]
    assert audio.read(path)["genre"] == "House"
    assert service.store.track(t["id"])["accepted"] == {"genre": "House"}
    # rekordbox stays queued until direct writes are verified.
    assert editing.pending() == [t["id"]]
    assert [p["id"] for p in service.store.proposals()] == ids[1:]
    with pytest.raises(ValueError, match="stale"):
        editing.approve(ids[:1])


def test_sync_job_retries_every_waiting_edit(editing, service, audio_file):
    path = audio_file()
    parked = path.with_suffix(".offline")
    path.rename(parked)
    t = ingest(service, path)
    service.store.propose(t, "genre", "House", "high", "Evidence", "provider")
    editing.approve([service.store.proposals()[0]["id"]])
    parked.rename(path)
    ingest(service, path)
    with service.store.connect() as db:
        db.execute(
            "INSERT INTO jobs(id,kind,state,payload,created_at) VALUES ('j','sync_edits','running','{}','')"
        )
    # The file is written; the rekordbox side is still locked, so one track remains.
    assert editing.sync_pending("j") == 1
    assert audio.read(path)["genre"] == "House"


def test_live_check_holds_writes_back(editing, service, audio_file):
    path = audio_file()
    t = ingest(service, path)
    live = service.store.root / "compatibility" / "live"
    live.mkdir(parents=True)
    (live / "state.json").write_text('{"state": "started"}')
    service.store.propose(t, "genre", "House", "high", "Evidence", "provider")
    result = editing.approve([service.store.proposals()[0]["id"]])
    assert "live rekordbox check" in result["message"]
    assert audio.read(path).get("genre", "") != "House"
    assert service.store.track(t["id"])["accepted"] == {"genre": "House"}


def test_full_file_dates_compare_and_survive_as_years(service, audio_file):
    from mutagen.flac import FLAC

    path = audio_file()
    tags = FLAC(path)
    tags["date"] = ["2019-11-08"]
    tags.save()
    assert audio.read(path)["year"] == "2019"
    t = ingest(service, path, year="2019")
    service.store.propose(t, "year", "2019", "review", "Evidence", "provider")
    assert not service.store.proposals()
    # Writing the same year keeps the file's fuller date; a new year replaces it.
    audio.write(path, {"year": "2019"})
    assert FLAC(path)["date"] == ["2019-11-08"]
    audio.write(path, {"year": "2020"})
    assert FLAC(path)["date"] == ["2020"]


def test_album_artist_is_not_suggested_but_can_be_edited(service, audio_file):
    t = ingest(service, audio_file())
    service.store.propose(t, "album_artist", "Various", "review", "Evidence", "x")
    assert not service.store.proposals()
    service.store.propose(t, "album_artist", "Various", "high", "Manual", "manual")
    assert len(service.store.proposals()) == 1


def test_track_names_are_split_only_when_the_shape_is_clear():
    from songdex.providers import split_name

    assert split_name("Burna Boy - Ye") == {"artist": "Burna Boy", "title": "Ye"}
    assert split_name("Yves Tumor - Heaven - 02 Medicine Burn") == {
        "artist": "Yves Tumor",
        "title": "Medicine Burn",
        "album": "Heaven",
    }
    assert split_name("BAE BAE - Playing Games (BAE BAE Edit)")["artist"] == "BAE BAE"
    for unclear in ("Dance now cry later - The Kount Remix", "NOISE", "A - B - C - D"):
        assert split_name(unclear) is None


def test_untagged_track_gets_name_and_artist_genre_suggestions(
    service, audio_file, monkeypatch
):
    from songdex.providers import Providers

    ingest(service, audio_file(), source_id="9", title="Hip-Hop song", genre="Hip-Hop")
    path = audio_file("mp3")
    t = ingest(service, path, source_id="2", title="Skepta - Greaze Mode", artist="")
    provider = Providers(service.store)

    def get(url, params):
        if url.endswith("/recording"):
            return {"recordings": []}
        if url.endswith("/artist"):
            return {"artists": [{"id": "a1", "name": "Skepta", "score": 100}]}
        return {
            "genres": [
                {"name": "grime", "count": 9},
                {"name": "hip hop", "count": 6},
                {"name": "pop", "count": 1},
            ]
        }

    monkeypatch.setattr(provider, "get", get)
    provider.enrich(t)
    found = {p["field"]: p["new_value"] for p in service.store.proposals()}
    # The genre is spelled the way the collection already spells it.
    assert found == {"artist": "Skepta", "title": "Greaze Mode", "genre": "Hip-Hop"}
    # Two artists with the same name: nobody's genre is borrowed.
    with service.store.connect() as db:
        db.execute("DELETE FROM proposals")
    monkeypatch.setattr(
        provider,
        "get",
        lambda url, params: {
            "recordings": [],
            "artists": [{"id": "a", "name": "Skepta"}, {"id": "b", "name": "SKEPTA"}],
        },
    )
    provider.enrich(t)
    assert "genre" not in {p["field"] for p in service.store.proposals()}


def test_discogs_genre_needs_a_token_and_expires_after_six_hours(
    service, audio_file, monkeypatch
):
    from songdex.providers import Providers

    t = ingest(service, audio_file(), title="Greaze Mode", artist="Skepta ft. Nafe")
    provider = Providers(service.store)
    calls = []

    def get(url, params, headers=None, keep=None):
        calls.append((url, headers, keep))
        if "discogs" not in url:
            return {"recordings": [], "artists": []}
        return {
            "results": [
                {"title": "Someone Else - Greaze", "style": ["House"], "uri": "/x"},
                {
                    "title": "Skepta - Ignorance Is Bliss",
                    "style": ["Grime"],
                    "genre": ["Hip Hop"],
                    "uri": "/release/1-Skepta",
                },
            ]
        }

    monkeypatch.setattr(provider, "get", get)
    provider.enrich(t)
    assert not service.store.proposals() and "discogs" not in str(calls)
    service.store.set_setting("discogs_token", "secret")
    provider.enrich(t)
    (proposal,) = service.store.proposals()
    assert proposal["new_value"] == "Grime"
    assert proposal["source"] == "https://www.discogs.com/release/1-Skepta"
    url, headers, keep = next(c for c in calls if "discogs" in c[0])
    assert headers == {"Authorization": "Discogs token=secret"}
    assert keep.total_seconds() == 6 * 3600
    with service.store.connect() as db:
        db.execute("UPDATE proposals SET created_at='2020-01-01T00:00:00+00:00'")
    assert not service.store.proposals()
    # An application's key and secret work in place of a token; half a pair does not.
    from songdex.providers import discogs_auth

    service.store.set_setting("discogs_token", "")
    service.store.set_setting("discogs_key", "app")
    assert discogs_auth(service.store) == ""
    service.store.set_setting("discogs_secret", "hidden")
    assert discogs_auth(service.store) == "Discogs key=app, secret=hidden"


def test_suggestions_for_removed_or_changed_tracks_leave_review(
    editing, service, audio_file
):
    gone = ingest(service, audio_file("flac"), source_id="1")
    changed = ingest(service, audio_file("mp3"), source_id="2", label="Old label")
    kept = ingest(service, audio_file("m4a"), source_id="3")
    for t in (gone, changed, kept):
        service.store.propose(t, "label", "Roulé", "review", "Evidence", "provider")
    ids = {p["track_id"]: p["id"] for p in service.store.proposals()}
    assert len(ids) == 3
    with service.store.connect() as db:
        db.execute("UPDATE tracks SET state='removed' WHERE id=?", (gone["id"],))
        db.execute(
            "UPDATE tracks SET metadata=json_set(metadata,'$.label','Edited in rekordbox') WHERE id=?",
            (changed["id"],),
        )
    assert [p["track_id"] for p in service.store.proposals()] == [kept["id"]]
    # A selection made before they were retired still goes through for the rest.
    result = editing.approve(list(ids.values()))
    assert result["approved"] == 1 and "2 skipped" in result["message"]
    assert service.store.track(kept["id"])["accepted"] == {"label": "Roulé"}
    assert service.store.track(changed["id"])["accepted"] == {}


def test_saved_edit_on_a_removed_track_is_not_synced_or_counted(
    editing, service, audio_file
):
    path = audio_file()
    t = ingest(service, path)
    # Saved while its drive was away, so the edit is left waiting.
    away = path.rename(path.with_suffix(".away"))
    editing.save(t["id"], {"genre": "House"}, revision(t))
    away.rename(path)
    assert editing.pending() == [t["id"]]
    with service.store.connect() as db:
        db.execute("UPDATE tracks SET state='removed' WHERE id=?", (t["id"],))
    assert editing.pending() == []
    assert "no longer in rekordbox" in editing.sync(t["id"])["message"]
    assert audio.read(path).get("genre", "") != "House"
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM local_writes").fetchone()[0] == 0


def test_background_approval_skips_what_changed_meanwhile(editing, service, audio_file):
    path = audio_file()
    t = ingest(service, path)
    service.store.propose(t, "genre", "House", "review", "Evidence", "provider")
    service.store.propose(t, "label", "Roulé", "review", "Evidence", "provider")
    genre, label = sorted(service.store.proposals(), key=lambda p: p["field"])
    with service.store.connect() as db:
        db.execute("UPDATE proposals SET status='rejected' WHERE id=?", (label["id"],))
        db.execute(
            "INSERT INTO jobs(id,kind,state,payload,created_at) VALUES ('j','approve','running','{}','')"
        )
    assert editing.approve_job("j", [genre["id"], label["id"]]) == 0
    assert audio.read(path)["genre"] == "House"
    assert service.store.track(t["id"])["accepted"] == {"genre": "House"}
    assert not service.store.proposals()
