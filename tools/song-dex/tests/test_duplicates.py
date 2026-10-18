import shutil
from contextlib import contextmanager

import pytest
from songdex import audio, rekordbox
from songdex.duplicates import FOLDER, REMOVAL, Duplicates
from songdex.operations import Operations

REMOVAL_LIST = {"name": f"{FOLDER} / {REMOVAL}", "id": "9", "position": 1}


def row(source_id, path, playlists=(), tags=(), cues=0, title="Same Song", **more):
    return {
        "source_id": source_id,
        "path": str(path),
        "metadata": {
            "title": title,
            "artist": "Artist",
            "format": path.suffix[1:],
            **more,
        },
        "playlists": [{"name": n, "id": n, "position": 1} for n in playlists],
        "my_tags": [{"id": t, "name": t, "category": ""} for t in tags],
        "stats": {"cues": cues, "plays": 0, "rating": 0},
    }


def fake_rekordbox(service, tmp_path, monkeypatch, before, after):
    """`before` behind a fake rekordbox layer; after a merge it reads as `after(plans)`."""
    source = tmp_path / "library/master.db"
    source.parent.mkdir()
    source.write_bytes(b"original")
    xml = source.parent / "masterPlaylists6.xml"
    xml.write_bytes(b"playlists")
    plans = []

    def snapshot(src, destination):
        destination.mkdir(parents=True)
        shutil.copy2(src, destination / "master.db")
        shutil.copy2(xml, destination / xml.name)
        return audio.digest(src)

    def merge_entries(path, plan, own_folder):
        plans.append(plan)
        path.write_bytes(b"merged")
        return {"playlists": 2, "my_tags": 2}

    def read_collection(path):
        return after(plans) if path.read_bytes() == b"merged" else before

    @contextmanager
    def database(path):
        yield None

    monkeypatch.setattr(rekordbox, "require_stopped", lambda: None)
    monkeypatch.setattr(
        rekordbox, "capability", lambda root: {"enabled": True, "report": {}}
    )
    monkeypatch.setattr(rekordbox, "snapshot", snapshot)
    monkeypatch.setattr(rekordbox, "merge_entries", merge_entries)
    monkeypatch.setattr(rekordbox, "read_collection", read_collection)
    monkeypatch.setattr(rekordbox, "database", database)
    monkeypatch.setattr(rekordbox, "playlist_state", lambda db, folder: {})
    monkeypatch.setattr(
        rekordbox,
        "write_playlists",
        lambda path, plan: (path.parent / xml.name).write_bytes(b"registered"),
    )
    service.store.set_setting("rekordbox_db", str(source))
    service.store.set_setting("last_scan_source", str(source))
    service.store.set_setting("library_hash", audio.digest(source))
    for entry in before:
        service.ingest(str(source), entry)
    ids = {t["source_id"]: t["id"] for t in service.store.tracks()}
    return Duplicates(Operations(service)), source, xml, ids, plans


@pytest.fixture
def library(service, tmp_path, monkeypatch):
    """Three entries for one song and one unrelated track."""
    before = [
        row("1", tmp_path / "a.mp3", ["Warm up"], ["Vocal"]),
        row("2", tmp_path / "b.flac", ["Peak"], cues=3),
        row("3", tmp_path / "c.mp3", ["Warm up", "Closing"], ["Bootleg"]),
        row("4", tmp_path / "d.flac", title="Another Song"),
    ]
    after = [
        row("1", tmp_path / "a.mp3", [REMOVAL_LIST["name"]]),
        row("2", tmp_path / "b.flac", ["Peak", "Warm up", "Closing"], ["Vocal"], 3),
        row("3", tmp_path / "c.mp3", ["Warm up", REMOVAL_LIST["name"]]),
        before[3],
    ]
    return fake_rekordbox(service, tmp_path, monkeypatch, before, lambda plans: after)


def test_group_suggests_the_entry_with_cues_and_better_audio(library):
    duplicates, _, _, ids, _ = library
    (group,) = duplicates.groups()
    assert set(group["tracks"]) == {ids["1"], ids["2"], ids["3"]}
    assert group["keep"] == ids["2"]
    assert group["merged"] is False


def test_merge_moves_memberships_and_restores_from_history(library):
    duplicates, source, xml, ids, plans = library
    result = duplicates.merge([{"keep": ids["2"], "remove": [ids["1"], ids["3"]]}])
    assert result["manifest"]["library_status"] == "complete"
    assert plans == [[{"keep": "2", "remove": ["1", "3"]}]]
    assert source.read_bytes() == b"merged" and xml.read_bytes() == b"registered"
    tracks = {t["source_id"]: t for t in duplicates.store.tracks()}
    assert [p["name"] for p in tracks["2"]["playlists"]] == [
        "Peak",
        "Warm up",
        "Closing",
    ]
    (group,) = duplicates.groups()
    assert group["merged"] is True
    assert set(group["awaiting_removal"]) == {ids["1"], ids["3"]}
    # Entries waiting for removal cannot be merged a second time.
    with pytest.raises(ValueError, match="changed"):
        duplicates.merge([{"keep": ids["2"], "remove": [ids["1"]]}])
    duplicates.operations.restore(result["id"])
    assert source.read_bytes() == b"original" and xml.read_bytes() == b"playlists"
    tracks = {t["source_id"]: t for t in duplicates.store.tracks()}
    assert [p["name"] for p in tracks["2"]["playlists"]] == ["Peak"]
    assert duplicates.groups()[0]["merged"] is False


def test_merge_refuses_stale_or_unrelated_selections(library, monkeypatch):
    duplicates, source, _, ids, plans = library
    for merges in (
        [{"keep": ids["2"], "remove": [ids["4"]]}],
        [{"keep": ids["2"], "remove": [ids["2"]]}],
        [
            {"keep": ids["2"], "remove": [ids["1"]]},
            {"keep": ids["1"], "remove": [ids["3"]]},
        ],
    ):
        with pytest.raises(ValueError, match="changed"):
            duplicates.merge(merges)
    source.write_bytes(b"edited in rekordbox since the scan")
    with pytest.raises(ValueError, match="Rescan"):
        duplicates.merge([{"keep": ids["2"], "remove": [ids["1"]]}])
    source.write_bytes(b"original")
    monkeypatch.setattr(
        rekordbox, "capability", lambda root: {"enabled": False, "reason": "locked"}
    )
    with pytest.raises(ValueError, match="locked"):
        duplicates.merge([{"keep": ids["2"], "remove": [ids["1"]]}])
    assert plans == [] and source.read_bytes() == b"original"


def test_failed_write_is_recoverable_and_leaves_the_library(library, monkeypatch):
    duplicates, source, xml, ids, _ = library

    def fail(path, plan):
        raise ValueError("rekordbox verification failed")

    monkeypatch.setattr(rekordbox, "write_playlists", fail)
    result = duplicates.merge([{"keep": ids["2"], "remove": [ids["1"]]}])
    assert result["manifest"]["error"] == "rekordbox verification failed"
    assert source.read_bytes() == b"original" and xml.read_bytes() == b"playlists"
    with pytest.raises(ValueError, match="interrupted operation"):
        duplicates.merge([{"keep": ids["2"], "remove": [ids["1"]]}])
    duplicates.operations.restore(result["id"])
    assert source.read_bytes() == b"original"


def partly_merged(monkeypatch, tmp_path, source):
    """rekordbox after entry 1 alone merged into entry 2; entry 3 is another version."""
    before = rekordbox.read_collection(source)
    after = [
        row("1", tmp_path / "a.mp3", [REMOVAL_LIST["name"]]),
        row("2", tmp_path / "b.flac", ["Peak", "Warm up"], ["Vocal"], 3),
        *before[2:],
    ]
    monkeypatch.setattr(
        rekordbox,
        "read_collection",
        lambda path: after if path.read_bytes() == b"merged" else before,
    )


def test_okay_merges_ticked_entries_and_leaves_the_rest(library, monkeypatch, tmp_path):
    duplicates, source, _, ids, plans = library
    partly_merged(monkeypatch, tmp_path, source)
    result = duplicates.merge([{"keep": ids["2"], "remove": [ids["1"]], "okay": True}])
    assert plans == [[{"keep": "2", "remove": ["1"]}]]
    tracks = {t["source_id"]: t for t in duplicates.store.tracks()}
    assert [p["name"] for p in tracks["3"]["playlists"]] == ["Warm up", "Closing"]
    (group,) = duplicates.groups()
    assert group["merged"] is True and group["awaiting_removal"] == [ids["1"]]
    assert duplicates.store.setting("duplicates_dismissed") == [[ids["2"], ids["3"]]]
    with pytest.raises(ValueError, match="changed"):
        duplicates.merge([{"keep": ids["2"], "remove": [ids["3"]]}])
    # Undoing the merge brings the whole group back for review.
    duplicates.operations.restore(result["id"])
    (group,) = duplicates.groups()
    assert group["merged"] is False and group["awaiting_removal"] == []


def test_okay_after_a_merge_keeps_the_merged_entry_listed(
    library, monkeypatch, tmp_path
):
    duplicates, source, _, ids, _ = library
    partly_merged(monkeypatch, tmp_path, source)
    duplicates.merge([{"keep": ids["2"], "remove": [ids["1"]]}])
    assert duplicates.groups()[0]["merged"] is False
    duplicates.dismiss([[ids["1"], ids["2"], ids["3"]]])
    (group,) = duplicates.groups()
    assert group["merged"] is True and group["awaiting_removal"] == [ids["1"]]
    assert duplicates.store.setting("duplicates_dismissed") == [[ids["2"], ids["3"]]]


def test_failed_merge_does_not_mark_the_rest_as_okay(library, monkeypatch):
    duplicates, _, _, ids, _ = library

    def fail(path, plan):
        raise ValueError("rekordbox verification failed")

    monkeypatch.setattr(rekordbox, "write_playlists", fail)
    duplicates.merge([{"keep": ids["2"], "remove": [ids["1"]], "okay": True}])
    assert duplicates.store.setting("duplicates_dismissed", []) == []


def test_dismissed_group_stays_hidden_until_it_grows(library, service, tmp_path):
    duplicates, source, _, ids, _ = library
    with pytest.raises(ValueError, match="changed"):
        duplicates.dismiss([[ids["1"], ids["2"]]])
    duplicates.dismiss([[ids["1"], ids["2"], ids["3"]]])
    assert duplicates.groups() == []
    service.ingest(str(source), row("5", tmp_path / "e.mp3"))
    assert len(duplicates.groups()[0]["tracks"]) == 4
    duplicates.reset_dismissed()
    assert len(duplicates.groups()) == 1


def six(tmp_path):
    """One song six times: the Original from three albums, two Extended, one Radio Edit."""
    entry = lambda n, title, album, duration, **more: row(  # noqa: E731
        n,
        tmp_path / f"{n}.mp3",
        title=title,
        album=album,
        duration=duration,
        bpm=124,
        **more,
    )
    return [
        entry("1", "Same Song", "Single", 330),
        entry("2", "Same Song (Extended Mix)", "Single", 412),
        entry("3", "Same Song (Radio Edit)", "Single", 215),
        entry("4", "Same Song (Original Mix)", "Club Hits 2019", 331, cues=4),
        entry("5", "Same Song [Extended Mix]", "Extended Club", 412.5, cues=1),
        entry("6", "Same Song", "Best Of", 330.5),
    ]


@pytest.fixture
def versioned(service, tmp_path, monkeypatch):
    """The six entries; a merge lists the removed ones for removal."""
    before = six(tmp_path)

    def after(plans):
        removed = {i for plan in plans for merge in plan for i in merge["remove"]}
        return [
            {**r, "playlists": [REMOVAL_LIST]} if r["source_id"] in removed else r
            for r in before
        ]

    return fake_rekordbox(service, tmp_path, monkeypatch, before, after)


def test_large_group_is_ordered_and_labelled_by_version(versioned):
    duplicates, _, _, ids, _ = versioned
    (group,) = duplicates.groups()
    by = lambda *n: [ids[i] for i in n]  # noqa: E731
    assert group["tracks"] == by("1", "4", "6", "2", "5", "3")
    assert group["versions"] == [
        {
            "label": "Original",
            "tracks": by("1", "4", "6"),
            "keep": ids["4"],
            "warnings": [],
            "same_file": False,
        },
        {
            "label": "Extended Mix",
            "tracks": by("2", "5"),
            "keep": ids["5"],
            "warnings": [],
            "same_file": False,
        },
        {
            "label": "Radio Edit",
            "tracks": by("3"),
            "keep": ids["3"],
            "warnings": [],
            "same_file": False,
        },
    ]
    assert "Different version labels" in group["warnings"]


def test_small_or_single_version_groups_get_no_versions(service, tmp_path):
    for r in six(tmp_path)[:2]:
        service.ingest("test", r)
    # Three copies of one version need no second check either.
    for n in ("7", "8", "9"):
        service.ingest("test", row(n, tmp_path / f"{n}.mp3", title="Other"))
    groups = Duplicates(Operations(service)).groups()
    assert sorted(len(g["tracks"]) for g in groups) == [2, 3]
    assert all("versions" not in g for g in groups)


def test_versions_sharing_a_label_are_told_apart_by_duration(service, tmp_path):
    for n, duration in (("1", 332), ("2", 332.5), ("3", 250)):
        service.ingest("test", row(n, tmp_path / f"{n}.mp3", duration=duration))
    (group,) = Duplicates(Operations(service)).groups()
    assert [v["label"] for v in group["versions"]] == [
        "Original · 5:32",
        "Original · 4:10",
    ]
    assert "Duration differs significantly" in group["warnings"]


def test_titles_that_differ_beyond_a_version_warn_inside_the_version(service, tmp_path):
    for n, title in (("1", "Same Song"), ("2", "Same Song (feat. Singer)")):
        service.ingest("test", row(n, tmp_path / f"{n}.mp3", title=title, duration=300))
    service.ingest("test", row("3", tmp_path / "3.mp3", title="Same Song (Dub Remix)"))
    (group,) = Duplicates(Operations(service)).groups()
    assert [(v["label"], v["warnings"]) for v in group["versions"]] == [
        ("Original", ["Titles differ beyond punctuation"]),
        ("Dub Remix", []),
    ]


def test_okay_merges_per_version_close_the_group(versioned):
    duplicates, _, _, ids, plans = versioned
    result = duplicates.merge(
        [
            {"keep": ids["4"], "remove": [ids["1"], ids["6"]], "okay": True},
            {"keep": ids["5"], "remove": [ids["2"]], "okay": True},
        ]
    )
    assert result["manifest"]["library_status"] == "complete"
    assert plans == [
        [{"keep": "4", "remove": ["1", "6"]}, {"keep": "5", "remove": ["2"]}]
    ]
    (group,) = duplicates.groups()
    assert group["merged"] is True and "versions" not in group
    assert set(group["awaiting_removal"]) == {ids["1"], ids["6"], ids["2"]}
    assert duplicates.store.setting("duplicates_dismissed") == [
        sorted([ids["4"], ids["5"], ids["3"]])
    ]


def test_merging_one_version_leaves_the_rest_open(versioned):
    duplicates, _, _, ids, _ = versioned
    duplicates.merge([{"keep": ids["4"], "remove": [ids["1"], ids["6"]]}])
    (group,) = duplicates.groups()
    assert group["merged"] is False
    assert [v["label"] for v in group["versions"]] == [
        "Extended Mix",
        "Radio Edit",
        "Original",
    ]
    assert group["tracks"][-2:] == [ids["1"], ids["6"]]
    assert duplicates.store.setting("duplicates_dismissed", []) == []


def test_after_merging_copies_the_versions_left_are_one_choice(versioned):
    duplicates, _, _, ids, _ = versioned
    duplicates.merge(
        [
            {"keep": ids["4"], "remove": [ids["1"], ids["6"]]},
            {"keep": ids["5"], "remove": [ids["2"]]},
        ]
    )
    (group,) = duplicates.groups()
    # One entry per version is left, so the group is a single choice across them.
    assert group["merged"] is False and "versions" not in group
    open_ids = [i for i in group["tracks"] if i not in group["awaiting_removal"]]
    assert sorted(open_ids) == sorted([ids["4"], ids["5"], ids["3"]])
    assert "Different version labels" in group["warnings"]
    # Squashing on: the radio edit merges too, and the rest is marked okay.
    duplicates.merge([{"keep": ids["4"], "remove": [ids["3"]], "okay": True}])
    (group,) = duplicates.groups()
    assert group["merged"] is True
    assert set(group["awaiting_removal"]) == {ids["1"], ids["6"], ids["2"], ids["3"]}


def test_versions_left_after_merging_copies_can_be_marked_okay(versioned):
    duplicates, _, _, ids, _ = versioned
    duplicates.merge(
        [
            {"keep": ids["4"], "remove": [ids["1"], ids["6"]]},
            {"keep": ids["5"], "remove": [ids["2"]]},
        ]
    )
    (group,) = duplicates.groups()
    duplicates.dismiss([group["tracks"]])
    (group,) = duplicates.groups()
    assert group["merged"] is True
