from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

from conftest import ingest
from fastapi.testclient import TestClient
from songdex import rekordbox
from songdex.api import create_app
from songdex.tagging import Tagging


def content(id, **values):
    base = dict(
        ID=id,
        Title="",
        ArtistName="",
        GenreName="",
        BPM=0,
        ReleaseYear=0,
        StockDate="",
        Rating=0,
    )
    return SimpleNamespace(**{**base, **values})


def smart(playlist_id, match, *conditions):
    return rekordbox.smart_list(playlist_id, list(conditions), match)


TRACKS = [
    content("1", Title="Warm", GenreName="Deep House", BPM=12050, ReleaseYear=1985),
    content("2", Title="Cold", GenreName="Techno", BPM=13000, StockDate="2026-10-01"),
    content("3", Title="Soft", GenreName="Soul", BPM=9000, ReleaseYear=1999),
]
PLAYLISTS = [
    SimpleNamespace(ID="10", Name="Sets", ParentID="root", Attribute=1, Seq=1),
    SimpleNamespace(ID="11", Name="Opening", ParentID="10", Attribute=0, Seq=2),
    SimpleNamespace(ID="12", Name="Closing", ParentID="10", Attribute=0, Seq=1),
    SimpleNamespace(
        ID="13",
        Name="House or soul",
        ParentID="root",
        Attribute=4,
        Seq=2,
        SmartList=smart(
            "13",
            "any",
            {"property": "genre", "operator": 8, "left": "house"},
            {"property": "genre", "operator": 1, "left": "Soul"},
        ),
    ),
    SimpleNamespace(
        ID="14",
        Name="Tagged eighties",
        ParentID="root",
        Attribute=4,
        Seq=3,
        SmartList=smart(
            "14",
            "all",
            {"property": "myTag", "operator": 8, "left": "2238842738"},
            {"property": "year", "operator": 5, "left": "1980", "right": "1989"},
        ),
    ),
    SimpleNamespace(
        ID="15",
        Name="Broken",
        ParentID="root",
        Attribute=4,
        Seq=4,
        SmartList="<NODE",
    ),
]


def fake_library(monkeypatch):
    from pyrekordbox.db6 import tables

    class DB:
        def query(self, table):
            if table == tables.DjmdSongMyTag:
                return [SimpleNamespace(ContentID="1", MyTagID="2238842738")]
            return [SimpleNamespace(ID="2238842738", Name="Warm-up")]

        def get_playlist(self):
            return PLAYLISTS

        def get_content(self):
            return TRACKS

    @contextmanager
    def database(path):
        yield DB()

    monkeypatch.setattr(rekordbox, "database", database)


def test_playlist_tree_keeps_order_and_evaluates_smart_playlists(monkeypatch):
    fake_library(monkeypatch)
    nodes = {n["id"]: n for n in rekordbox.read_playlists("master.db")["nodes"]}
    assert [n["id"] for n in rekordbox.read_playlists("x")["nodes"]][:2] == ["12", "11"]
    assert nodes["10"]["kind"] == "folder" and nodes["11"]["parent"] == "10"
    assert "tracks" not in nodes["11"]
    assert nodes["13"]["tracks"] == ["1", "3"]
    assert nodes["13"]["rules"] == ["Genre contains house", "Genre is Soul"]
    assert nodes["14"]["tracks"] == ["1"]
    assert nodes["14"]["rules"][0] == "My Tag contains Warm-up"
    assert nodes["15"]["tracks"] == [] and "cannot read" in nodes["15"]["error"]


def test_smart_rules_compare_like_rekordbox():
    def matches(rule, track, tags=()):
        return rekordbox.smart_matcher(rule, today=date(2026, 10, 19))(track, tags)

    bpm = {"property": "bpm", "operator": 1, "left": "120"}
    assert matches(bpm, TRACKS[0]) and not matches(bpm, TRACKS[1])
    blank = {"property": "genre", "operator": 1, "left": ""}
    assert matches(blank, content("9")) and not matches(blank, TRACKS[0])
    recent = {"property": "stockDate", "operator": 6, "left": "30", "unit": "day"}
    assert matches(recent, TRACKS[1]) and not matches(recent, TRACKS[0])
    untagged = {"property": "myTag", "operator": 9, "left": "5"}
    assert matches(untagged, TRACKS[0]) and not matches(untagged, TRACKS[0], {"5"})


def test_smart_playlist_tracks_are_given_by_dex_id(service, monkeypatch):
    fake_library(monkeypatch)
    service.store.set_setting("last_scan_source", "lib")
    service.store.set_setting(
        "library_playlists", rekordbox.read_playlists("master.db")
    )
    ids = {
        sid: ingest(service, "x", source="lib", source_id=sid)["id"] for sid in "123"
    }
    tree = Tagging(service).library_playlists()
    assert tree["loaded"]
    house = next(n for n in tree["nodes"] if n["id"] == "13")
    assert house["tracks"] == [ids["1"], ids["3"]]


def test_unknown_requests_say_to_restart_and_bulk_lists_route_exists(tmp_path):
    client = TestClient(create_app(tmp_path))
    state = client.get("/api/state").json()
    assert state["restart_needed"] is False
    headers = {"x-songdex-token": state["token"]}
    missing = client.post("/api/not-a-route", headers=headers)
    assert missing.status_code == 404 and "Restart Song Dex" in missing.json()["detail"]
    # The bulk My Tag request reaches its handler (an older service answered 405).
    added = client.post(
        "/api/lists/add", headers=headers, json={"ids": [1], "tags": ["5"]}
    )
    assert added.status_code == 409
    assert "no longer in rekordbox" in added.json()["detail"]
    assert client.get("/api/playlists").json() == {"nodes": [], "loaded": False}
