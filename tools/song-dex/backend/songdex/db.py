from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .audio import year_of


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def cosmetic(value):
    """Text without case, accents, punctuation style or spacing differences."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


# Fields the collection does not use; providers' values for them are not suggested.
IGNORED_FIELDS = {"album_artist"}


def unchanged(track, field, value, source):
    """True when a suggestion would not really change the track."""
    if source != "manual" and field in IGNORED_FIELDS:
        return True
    current = str(track["metadata"].get(field, ""))
    tagged = str(track["file_metadata"].get(field, ""))
    if source == "manual":
        return current == str(value) and (
            not track["available"] or tagged == str(value)
        )
    # Providers follow their own style guide; a restyled spelling is not a correction.
    return cosmetic(current) == cosmetic(value) and (
        not track["available"] or not tagged or cosmetic(tagged) == cosmetic(value)
    )


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS songs(id INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS recordings(id INTEGER PRIMARY KEY, song_id INTEGER REFERENCES songs(id), identity TEXT UNIQUE NOT NULL, version TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS releases(id INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tracks(
 id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, source_id TEXT NOT NULL,
 recording_id INTEGER REFERENCES recordings(id), release_id INTEGER REFERENCES releases(id),
 path TEXT NOT NULL, available INTEGER NOT NULL, signature TEXT NOT NULL, file_hash TEXT,
 metadata TEXT NOT NULL, file_metadata TEXT NOT NULL DEFAULT '{}', accepted TEXT NOT NULL DEFAULT '{}',
 overrides TEXT NOT NULL DEFAULT '{}', playlists TEXT NOT NULL DEFAULT '[]', evidence TEXT NOT NULL DEFAULT '[]',
 state TEXT NOT NULL DEFAULT 'unmatched', error TEXT, scanned_at TEXT NOT NULL,
 UNIQUE(source, source_id));
CREATE TABLE IF NOT EXISTS proposals(
 id INTEGER PRIMARY KEY, track_id INTEGER NOT NULL REFERENCES tracks(id), field TEXT NOT NULL,
 old_value TEXT NOT NULL, new_value TEXT NOT NULL, confidence TEXT NOT NULL,
 reason TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 signature TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS proposal_unique ON proposals(track_id, field, new_value, source);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
 payload TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
 message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, state TEXT NOT NULL, manifest TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, track_id INTEGER, kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS manual_edits(track_id INTEGER REFERENCES tracks(id), field TEXT, value TEXT NOT NULL,
 file_status TEXT NOT NULL, library_status TEXT NOT NULL, baseline TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(track_id,field));
CREATE TABLE IF NOT EXISTS local_writes(id TEXT PRIMARY KEY, track_id INTEGER REFERENCES tracks(id),
 kind TEXT NOT NULL, state TEXT NOT NULL, manifest TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY, state TEXT NOT NULL, plan TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tag_sessions(id TEXT PRIMARY KEY, tracks TEXT NOT NULL, checked TEXT NOT NULL DEFAULT '[]',
 position INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assignments(track_id INTEGER NOT NULL REFERENCES tracks(id), kind TEXT NOT NULL,
 target TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
 PRIMARY KEY(track_id,kind,target));
CREATE TABLE IF NOT EXISTS scan_items(job_id TEXT NOT NULL, track_id INTEGER NOT NULL, position INTEGER NOT NULL,
 catalog TEXT NOT NULL DEFAULT 'queued', genre TEXT NOT NULL DEFAULT 'queued', tags TEXT NOT NULL DEFAULT 'queued',
 PRIMARY KEY(job_id,track_id));
CREATE TABLE IF NOT EXISTS approval_queue(proposal_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL);
"""


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        root.chmod(0o700)
        self.path = root / "songdex.sqlite3"
        with self.connect() as db:
            db.executescript(SCHEMA)
            if "my_tags" not in {
                r["name"] for r in db.execute("PRAGMA table_info(tracks)")
            }:
                db.execute(
                    "ALTER TABLE tracks ADD COLUMN my_tags TEXT NOT NULL DEFAULT '[]'"
                )
            if "my_tags_loaded" not in {
                r["name"] for r in db.execute("PRAGMA table_info(tracks)")
            }:
                db.execute(
                    "ALTER TABLE tracks ADD COLUMN my_tags_loaded INTEGER NOT NULL DEFAULT 0"
                )
            if "stats" not in {
                r["name"] for r in db.execute("PRAGMA table_info(tracks)")
            }:
                db.execute(
                    "ALTER TABLE tracks ADD COLUMN stats TEXT NOT NULL DEFAULT '{}'"
                )
            # Why a scan suggested a My Tag or playlist ('suggested' assignments).
            if "reasons" not in {
                r["name"] for r in db.execute("PRAGMA table_info(assignments)")
            }:
                db.execute(
                    "ALTER TABLE assignments ADD COLUMN reasons TEXT NOT NULL DEFAULT '[]'"
                )
        self.recover()
        self.normalize_years()
        self.prune_cosmetic()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def recover(self):
        """Mark work left mid-flight, so it can be resumed, restored or cleared."""
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET state='interrupted', message='Interrupted; resume from saved progress' WHERE state='running'"
            )
            db.execute(
                "UPDATE operations SET state='recovery_required' WHERE state IN ('preparing','writing','restoring')"
            )
            # A write still preparing never reached its destination: nothing to recover.
            db.execute("UPDATE local_writes SET state='failed' WHERE state='preparing'")
            db.execute(
                "UPDATE local_writes SET state='recovery_required' WHERE state IN ('writing','restoring')"
            )
            db.execute("UPDATE imports SET state='interrupted' WHERE state='running'")

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO settings VALUES (?,?)", (key, dump(value))
            )

    def tracks(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM tracks ORDER BY id").fetchall()
        return [self.decode(row) for row in rows]

    def track(self, track_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
        if not row:
            raise ValueError("Track not found")
        return self.decode(row)

    @staticmethod
    def decode(row):
        item = dict(row)
        for key in (
            "metadata",
            "file_metadata",
            "accepted",
            "overrides",
            "playlists",
            "evidence",
            "my_tags",
            "stats",
        ):
            item[key] = json.loads(item[key])
        return item

    def log(self, kind, detail, track_id=None):
        with self.connect() as db:
            db.execute(
                "INSERT INTO history(track_id,kind,detail,created_at) VALUES (?,?,?,?)",
                (track_id, kind, detail, now()),
            )

    def normalize_years(self):
        """Earlier scans stored a file's full date as its year; keep only the year."""
        with self.connect() as db:
            for row in db.execute("SELECT id,file_metadata FROM tracks").fetchall():
                data = json.loads(row["file_metadata"])
                if data.get("year") and data["year"] != year_of(data["year"]):
                    data["year"] = year_of(data["year"])
                    db.execute(
                        "UPDATE tracks SET file_metadata=? WHERE id=?",
                        (dump(data), row["id"]),
                    )
            for row in db.execute(
                "SELECT track_id,baseline FROM manual_edits WHERE field='year'"
            ).fetchall():
                baseline = json.loads(row["baseline"])
                if baseline["file"] != year_of(baseline["file"]):
                    baseline["file"] = year_of(baseline["file"])
                    db.execute(
                        "UPDATE manual_edits SET baseline=? WHERE track_id=? AND field='year'",
                        (dump(baseline), row["track_id"]),
                    )

    def prune_cosmetic(self):
        """Retire pending suggestions that only restyle a value (case, accents, punctuation)."""
        tracks = {t["id"]: t for t in self.tracks()}
        with self.connect() as db:
            for p in db.execute(
                "SELECT id,track_id,field,new_value,source FROM proposals WHERE status='pending'"
            ).fetchall():
                if unchanged(
                    tracks[p["track_id"]], p["field"], p["new_value"], p["source"]
                ):
                    db.execute(
                        "UPDATE proposals SET status='cosmetic' WHERE id=?", (p["id"],)
                    )

    def proposals(self):
        with self.connect() as db:
            # Discogs' terms: their data is not shown once it is over six hours old.
            db.execute(
                "UPDATE proposals SET status='stale' WHERE status='pending' AND source LIKE 'https://www.discogs.com/%' AND created_at < ?",
                ((datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),),
            )
            db.execute(
                "DELETE FROM cache WHERE key LIKE 'https://api.discogs.com/%' AND created_at < ?",
                ((datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),),
            )
            # A suggestion is for the value it was made against. Once the track has
            # left rekordbox, or that field holds something else, it no longer applies.
            db.execute(
                """UPDATE proposals SET status='stale' WHERE status='pending' AND EXISTS (
                SELECT 1 FROM tracks t WHERE t.id=proposals.track_id AND (
                 t.state='removed' OR proposals.old_value NOT IN (
                  COALESCE(CAST(json_extract(t.metadata, '$.' || proposals.field) AS TEXT), ''),
                  COALESCE(CAST(json_extract(t.accepted, '$.' || proposals.field) AS TEXT),
                   CAST(json_extract(t.metadata, '$.' || proposals.field) AS TEXT), ''))))"""
            )
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM proposals WHERE status='pending' ORDER BY track_id,field"
                )
            ]

    def propose(self, track, field, value, confidence, reason, source):
        if (
            not value
            or field in track["overrides"]
            or unchanged(track, field, value, source)
        ):
            return
        with self.connect() as db:
            if source != "manual" and any(
                cosmetic(row["new_value"]) == cosmetic(value)
                and row["source"] != source
                for row in db.execute(
                    "SELECT new_value,source FROM proposals WHERE track_id=? AND field=? AND status='pending'",
                    (track["id"], field),
                )
            ):
                # Another source already suggests this value.
                return
            db.execute(
                "INSERT INTO proposals(track_id,field,old_value,new_value,confidence,reason,source,signature,created_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(track_id,field,new_value,source) DO UPDATE SET old_value=excluded.old_value,confidence=excluded.confidence,reason=excluded.reason,signature=excluded.signature,status='pending',created_at=excluded.created_at WHERE proposals.status='stale'",
                (
                    track["id"],
                    field,
                    str(track["metadata"].get(field, "")),
                    str(value),
                    confidence,
                    reason,
                    source,
                    track["signature"],
                    now(),
                ),
            )

    def entities(self, db, source, source_id, metadata):
        # Local identities are deliberately conservative. Catalog links remain evidence
        # until a recording/release is resolved, rather than merging similar titles.
        identity = f"{source}:{source_id}"
        db.execute("INSERT OR IGNORE INTO songs(identity) VALUES (?)", (identity,))
        sid = db.execute(
            "SELECT id FROM songs WHERE identity=?", (identity,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO recordings(song_id,identity,version) VALUES (?,?,?) ON CONFLICT(identity) DO UPDATE SET version=excluded.version",
            (sid, identity, metadata.get("version", "")),
        )
        rid = db.execute(
            "SELECT id FROM recordings WHERE identity=?", (identity,)
        ).fetchone()[0]
        album = metadata.get("album", "")
        release = None
        if album:
            identity = dump(
                [metadata.get("album_artist") or metadata.get("artist"), album]
            )
            db.execute(
                "INSERT OR IGNORE INTO releases(identity,title) VALUES (?,?)",
                (identity, album),
            )
            release = db.execute(
                "SELECT id FROM releases WHERE identity=?", (identity,)
            ).fetchone()[0]
        return rid, release
