from datetime import datetime, timedelta, timezone

from conftest import ingest
from songdex.providers import Providers
from songdex.tagging import Tagging, suggestions

CHOICES = {
    "tags": [
        {"id": "11", "name": "Deep House", "category": "Genre"},
        {"id": "12", "name": "Soulful", "category": "Components"},
    ],
    "playlists": [{"id": "100", "name": "Crates / Late night"}],
}


def track(tid, genre="", label="", playlists=(), descriptors=None):
    return {
        "id": tid,
        "state": "indexed",
        "metadata": {"artist": f"Artist {tid}", "genre": genre, "label": label},
        "accepted": {},
        "my_tags": [],
        "playlists": [{"id": p, "name": p, "position": 1} for p in playlists],
        "descriptors": descriptors or {},
    }


def found(result):
    return {(s["kind"], s["id"]): s["reasons"] for s in result}


def test_styles_and_tags_from_the_sources_suggest_my_tags_and_playlists():
    new = track(
        1,
        genre="House",
        descriptors={
            "discogs": {"styles": ["Deep House"], "label": "Glasgow Underground"},
            "musicbrainz": {"tags": ["Soulful House"], "artist": "Artist 1"},
        },
    )
    library = [
        new,
        track(2, genre="Deep House", playlists=["100"]),
        track(3, genre="Deep House", playlists=["100"]),
        track(4, label="Glasgow Underground", playlists=["100"]),
    ]
    result = found(suggestions(new, library, CHOICES))
    assert result[("tag", "11")] == ["Discogs style Deep House"]
    assert result[("tag", "12")] == ["MusicBrainz tag Soulful House"]
    assert result[("playlist", "100")] == [
        "2 of your 2 Deep House tracks (Discogs style)",
        "1 of your 1 tracks on Glasgow Underground (Discogs label)",
    ]


def test_discogs_describes_the_release_and_fills_blanks(
    service, audio_file, monkeypatch
):
    t = ingest(service, audio_file(), genre="House", label="")
    service.store.set_setting("discogs_token", "token")
    provider = Providers(service.store)
    monkeypatch.setattr(
        provider,
        "get",
        lambda *args, **kwargs: {
            "results": [
                {
                    "title": "Artist - Album",
                    "uri": "/release/1",
                    "style": ["Deep House"],
                    "genre": ["Electronic"],
                    "label": ["Not On Label", "Glasgow Underground"],
                    "year": "1999",
                }
            ]
        },
    )
    provider.find_genre({**t, "metadata": {**t["metadata"], "year": ""}})
    described = service.store.track(t["id"])["descriptors"]["discogs"]
    assert (described["styles"], described["label"], described["year"]) == (
        ["Deep House"],
        "Glasgow Underground",
        "1999",
    )
    # The genre is kept; the blank label is suggested with Discogs' attribution.
    assert {
        (p["field"], p["new_value"], p["source"]) for p in service.store.proposals()
    } == {
        ("label", "Glasgow Underground", "https://www.discogs.com/release/1"),
        ("year", "1999", "https://www.discogs.com/release/1"),
    }


def test_what_came_from_discogs_goes_after_six_hours(service, audio_file):
    t = ingest(service, audio_file())
    service.store.describe(t["id"], "discogs", {"styles": ["Deep House"]})
    service.store.describe(t["id"], "musicbrainz", {"genres": ["House"]})
    Tagging(service).keep_suggestions(
        t["id"],
        [
            {"kind": "tag", "id": "11", "reasons": ["Discogs style Deep House"]},
            {"kind": "tag", "id": "12", "reasons": ["Genre House", "Discogs style X"]},
        ],
    )
    old = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    with service.store.connect() as db:
        db.execute(
            "UPDATE tracks SET descriptors=json_set(descriptors,'$.discogs.fetched_at',?)",
            (old,),
        )
        db.execute("UPDATE assignments SET created_at=?", (old,))
    service.store.proposals()
    assert set(service.store.track(t["id"])["descriptors"]) == {"musicbrainz"}
    assert [(s["target"], s["reasons"]) for s in Tagging(service).suggested()] == [
        ("12", ["Genre House"])
    ]
