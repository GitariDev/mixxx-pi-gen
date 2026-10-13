"""Explicitly labeled illustrative data; never connects to a music library."""

from .db import dump, now

ROWS = [
    (
        "Music Sounds Better With You",
        "Stardust",
        "Music Sounds Better With You",
        "French house",
        124,
        "F minor",
        403,
        "Original",
        "Late-night / Warm up",
    ),
    (
        "Music Sounds Better With You (Radio Edit)",
        "Stardust",
        "Music Sounds Better With You",
        "French house",
        124,
        "F minor",
        260,
        "Radio Edit",
        "Favorites",
    ),
    (
        "One More Time",
        "Daft Punk",
        "Discovery",
        "House",
        123,
        "D major",
        320,
        "",
        "Late-night / Warm up",
    ),
    (
        "Digital Love",
        "Daft Punk",
        "Discovery",
        "House",
        125,
        "A major",
        301,
        "",
        "Favorites",
    ),
    (
        "Lady (Hear Me Tonight)",
        "Modjo",
        "Modjo",
        "French house",
        126,
        "B-flat minor",
        307,
        "",
        "Late-night / Warm up",
    ),
    (
        "Lady (Hear Me Tonight)",
        "Modjo",
        "Modjo",
        "French house",
        126,
        "B-flat minor",
        307,
        "",
        "USB preparation",
    ),
    (
        "Inspector Norse",
        "Todd Terje",
        "It’s the Arps",
        "Disco",
        120,
        "F-sharp minor",
        400,
        "",
        "Late-night / Peak",
    ),
    ("Tadow", "Masego & FKJ", "Tadow", "Soul", 122, "F minor", 302, "", "Warm up"),
    (
        "La Ritournelle",
        "Sébastien Tellier",
        "Politics",
        "Electronic",
        105,
        "G minor",
        453,
        "",
        "Closing tracks",
    ),
]


def seed(store):
    if store.tracks():
        raise ValueError(
            "Demo is available only in an empty Dex. Use a separate data directory for a real library."
        )
    with store.connect() as db:
        for i, (
            title,
            artist,
            album,
            genre,
            bpm,
            key,
            duration,
            version,
            playlist,
        ) in enumerate(ROWS, 1):
            m = dict(
                title=title,
                artist=artist,
                album=album,
                album_artist=artist,
                genre=genre,
                bpm=bpm,
                key=key,
                duration=duration,
                version=version,
                format="FLAC",
                year="",
                label="",
            )
            rid, release = store.entities(db, "demo", str(i), m)
            db.execute(
                "INSERT INTO tracks(source,source_id,recording_id,release_id,path,available,signature,file_hash,metadata,playlists,state,scanned_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "demo",
                    str(i),
                    rid,
                    release,
                    "",
                    0,
                    "demo",
                    "demo-modjo" if i in (5, 6) else None,
                    dump(m),
                    dump([{"name": playlist, "id": str(i), "position": 1}]),
                    "demo",
                    now(),
                ),
            )
    t = store.tracks()[0]
    store.propose(
        t,
        "year",
        "1998",
        "review",
        "Illustrative release-date proposal. Demo data only.",
        "demo",
    )
    store.propose(
        t,
        "label",
        "Roulé",
        "high",
        "Illustrative label proposal. Demo data only.",
        "demo",
    )
    store.set_setting("demo", True)
    store.log(
        "demo",
        "Loaded nine illustrative entries. Values are demo fixtures, not verified catalog facts.",
    )
