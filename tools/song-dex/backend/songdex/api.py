from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import audio, demo, rekordbox
from .backups import Backups
from .db import Store, unchanged
from .duplicates import Duplicates
from .editing import Editing, revision
from .importing import Importing, default_music_folder, new_to_rekordbox
from .operations import Operations
from .providers import discogs_auth, genre_name
from .scanning import Scanning, scope
from .scanning import stop as stop_scan
from .service import Service
from .tagging import Tagging


class Selection(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)


class Manual(BaseModel):
    field: str
    value: str = Field(min_length=1, max_length=255)


class Value(BaseModel):
    value: str = Field(min_length=1, max_length=255)


class Settings(BaseModel):
    rekordbox_db: str
    acoustid_key: str | None = None
    discogs_token: str | None = None
    discogs_key: str | None = None
    discogs_secret: str | None = None
    music_folder: str | None = None


class Edit(BaseModel):
    changes: dict[str, str]
    revision: str


class Merge(BaseModel):
    keep: int
    remove: list[int] = Field(min_length=1, max_length=50)
    okay: bool = False


class Merges(BaseModel):
    merges: list[Merge] = Field(min_length=1, max_length=500)


class Groups(BaseModel):
    groups: list[list[int]] = Field(min_length=1, max_length=500)


class BackupSelection(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=5000)


class Browse(BaseModel):
    path: str = ""


class ImportPreview(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=200)
    mode: str = "move"


class Lookup(BaseModel):
    scope: str
    kind: str | None = None
    ids: list[int] = Field(default=[], max_length=20000)


class Suggested(BaseModel):
    track_id: int
    kind: str
    target: str


class SuggestedSelection(BaseModel):
    items: list[Suggested] = Field(min_length=1, max_length=20000)


class Choice(BaseModel):
    tags: list[str] = Field(default=[], max_length=500)
    playlists: list[str] = Field(default=[], max_length=500)
    position: int = 0


def create_app(root=None):
    root = (
        Path(
            root
            or os.environ.get(
                "SONGDEX_DATA", Path(__file__).resolve().parents[2] / ".data"
            )
        )
        .expanduser()
        .resolve()
    )
    store = Store(root)
    service = Service(store)
    operations = Operations(service)
    editing, importing = Editing(service), Importing(service)
    duplicates = Duplicates(operations)
    tagging = Tagging(service)
    backups = Backups(service)
    backups.prune()
    app = FastAPI(title="Song Dex", docs_url=None, redoc_url=None)
    app.state.store, app.state.service = store, service
    token = secrets.token_urlsafe(32)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        origin = request.headers.get("origin")
        allowed = {
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://127.0.0.1:5178",
            "http://localhost:5178",
        }
        if origin and origin not in allowed:
            return JSONResponse(
                {"detail": "Foreign browser origin is not allowed"}, status_code=403
            )
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(
                {"detail": "Cross-site access is not allowed"}, status_code=403
            )
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not secrets.compare_digest(
                request.headers.get("x-songdex-token", ""), token
            ):
                return JSONResponse(
                    {"detail": "Refresh Song Dex before making changes"},
                    status_code=403,
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; media-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def bad_request(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/state")
    def state():
        service.settle()
        with store.connect() as db:
            jobs = [
                dict(r)
                for r in db.execute(
                    "SELECT id,kind,state,progress,total,message,created_at FROM jobs ORDER BY created_at DESC LIMIT 20"
                )
            ]
            history = [
                dict(r)
                for r in db.execute("SELECT * FROM history ORDER BY id DESC LIMIT 100")
            ]
            ops = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM operations ORDER BY created_at DESC LIMIT 30"
                )
            ]
            local_writes = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM local_writes ORDER BY created_at DESC LIMIT 100"
                )
            ]
            imports = [
                dict(r)
                for r in db.execute(
                    "SELECT id,state,created_at FROM imports ORDER BY created_at DESC LIMIT 20"
                )
            ]
        for op in ops:
            op["manifest"] = json.loads(op["manifest"])
        for op in local_writes:
            op["manifest"] = json.loads(op["manifest"])
        tracks = store.tracks()
        for track in tracks:
            track["revision"] = revision(track)
        return {
            "token": token,
            "tracks": tracks,
            "manual_edits": editing.statuses(),
            "edits_waiting": len(editing.pending()),
            "local_writes": local_writes,
            "imports": imports,
            "proposals": store.proposals(),
            "jobs": jobs,
            "history": history,
            "operations": ops,
            "duplicates": duplicates.groups(tracks),
            "duplicates_dismissed": len(store.setting("duplicates_dismissed", [])),
            "capability": rekordbox.capability(root),
            "last_scan": store.setting("last_scan"),
            "relocation_review": store.setting("relocation_review", []),
            "tag_sessions": tagging.summaries(),
            "assignments": tagging.assignments("pending"),
            "assignments_ready": len(tagging.waiting()),
            "choices": tagging.choices(),
            **review(),
            "settings": {
                "rekordbox_db": store.setting(
                    "rekordbox_db", str(rekordbox.DEFAULT_DB)
                ),
                "acoustid_configured": bool(store.setting("acoustid_key")),
                "discogs_configured": bool(discogs_auth(store)),
                "demo": store.setting("demo", False),
                "music_folder": store.setting("music_folder", default_music_folder()),
            },
        }

    def review():
        """What the review screen follows while a scan runs."""
        return {
            "scan": Scanning(service).latest(),
            "suggested": tagging.suggested(),
            "queued": editing.queued(),
        }

    @app.get("/api/review")
    def live_review():
        with store.connect() as db:
            jobs = [
                dict(r)
                for r in db.execute(
                    "SELECT id,kind,state,progress,total,message,created_at FROM jobs ORDER BY created_at DESC LIMIT 20"
                )
            ]
        return {"jobs": jobs, "proposals": store.proposals(), **review()}

    @app.get("/api/genres")
    def genres():
        """Every Noise at Once genre names, most popular first, for the genre picker."""
        names = (Path(__file__).parent / "genres.txt").read_text().splitlines()
        return {"genres": [genre_name(n) for n in names if n]}

    @app.post("/api/settings")
    def settings(body: Settings):
        if not service.lock.acquire(False):
            raise ValueError("Wait for the current operation before changing settings")
        try:
            path = Path(body.rekordbox_db).expanduser().resolve()
            if path.name != "master.db":
                raise ValueError("Library path must end with master.db")
            music = (
                Path(body.music_folder).expanduser().resolve()
                if body.music_folder
                else None
            )
            if music and not music.is_dir():
                raise ValueError("Choose an existing music folder on a connected drive")
            store.set_setting("rekordbox_db", str(path))
            if music:
                store.set_setting("music_folder", str(music))
            if body.acoustid_key is not None:
                store.set_setting("acoustid_key", body.acoustid_key.strip())
            for name in ("discogs_token", "discogs_key", "discogs_secret"):
                if getattr(body, name) is not None:
                    store.set_setting(name, getattr(body, name).strip())
            return {"saved": True}
        finally:
            service.lock.release()

    @app.post("/api/tracks/{track_id}/edit")
    def edit(track_id: int, body: Edit):
        return editing.save(track_id, body.changes, body.revision)

    @app.post("/api/tracks/{track_id}/sync")
    def sync_edit(track_id: int):
        return editing.sync(track_id)

    @app.post("/api/local-writes/{write_id}/restore")
    def restore_edit(write_id: str):
        return editing.restore(write_id)

    @app.post("/api/availability")
    def availability():
        return {"job_id": service.start("availability", {})}

    @app.post("/api/my-tags/load")
    def load_my_tags():
        return service.load_my_tags()

    @app.post("/api/files/browse")
    def browse(body: Browse):
        return importing.browse(body.path)

    @app.post("/api/imports/preview")
    def preview(body: ImportPreview):
        if not service.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            if store.setting("demo"):
                raise ValueError("Exit the demo before importing music")
            return importing.preview(body.paths, body.mode)
        finally:
            service.lock.release()

    @app.get("/api/imports/{import_id}")
    def import_receipt(import_id: str):
        return importing.get(import_id)

    @app.post("/api/imports/{import_id}/start")
    def import_start(import_id: str):
        if importing.get(import_id)["state"] not in (
            "preview",
            "partial",
            "running",
            "interrupted",
        ):
            raise ValueError("This import has already completed")
        return {"job_id": service.start("import_music", {"import_id": import_id})}

    @app.get("/api/imports/{import_id}/playlist")
    def import_playlist(import_id: str):
        receipt = importing.get(import_id)
        paths = [e["destination"] for e in receipt["entries"] if new_to_rekordbox(e)]
        if not paths:
            raise ValueError("No completed tracks to export")
        return Response(
            "#EXTM3U\n" + "\n".join(paths) + "\n",
            media_type="audio/x-mpegurl",
            headers={
                "Content-Disposition": 'attachment; filename="Song Dex imports.m3u8"'
            },
        )

    @app.get("/api/tagging/{session_id}")
    def tag_session(session_id: str):
        return tagging.session(session_id)

    @app.post("/api/tagging/{session_id}/tracks/{track_id}")
    def tag_track(session_id: str, track_id: int, body: Choice):
        return tagging.choose(
            session_id, track_id, body.tags, body.playlists, body.position
        )

    @app.post("/api/tagging/{session_id}/check")
    def tag_check(session_id: str):
        tagging.row(session_id)
        return {"job_id": service.start("tag_check", {"session_id": session_id})}

    @app.post("/api/tagging/{session_id}/finish")
    def tag_finish(session_id: str):
        return tagging.finish(session_id)

    @app.post("/api/assignments/write")
    def write_assignments():
        return tagging.write()

    @app.post("/api/demo")
    def load_demo():
        if not service.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            demo.seed(store)
        finally:
            service.lock.release()
        return {"loaded": True}

    @app.post("/api/demo/clear")
    def clear_demo():
        if not store.setting("demo") or service.lock.locked():
            raise ValueError("No idle demo is loaded")
        with store.connect() as db:
            db.execute(
                "DELETE FROM proposals WHERE track_id IN (SELECT id FROM tracks WHERE source='demo')"
            )
            db.execute(
                "DELETE FROM manual_edits WHERE track_id IN (SELECT id FROM tracks WHERE source='demo')"
            )
            db.execute(
                "DELETE FROM local_writes WHERE track_id IN (SELECT id FROM tracks WHERE source='demo')"
            )
            db.execute("DELETE FROM tracks WHERE source='demo'")
        store.set_setting("demo", False)
        return {"cleared": True}

    @app.post("/api/scan")
    def scan():
        if store.setting("demo"):
            raise ValueError("Exit demo in Settings before importing your library")
        return {"job_id": service.start("scan", {})}

    def start_lookup(name, kind=None, ids=None):
        if store.setting("demo"):
            raise ValueError("Demo entries do not make provider requests")
        chosen, label = scope(store.tracks(), name, kind, ids)
        return {
            "job_id": service.start("enrich", {"ids": chosen, "label": label}),
            "message": f"Scanning {len(chosen)} tracks; results appear as they come in",
        }

    @app.post("/api/lookup")
    def lookup(body: Lookup):
        return start_lookup(body.scope, body.kind, body.ids)

    @app.post("/api/lookup/stop")
    def stop_lookup():
        return stop_scan(store)

    @app.post("/api/enrich")
    def enrich(refresh: bool = False, missing: str = ""):
        if missing == "genre":
            return start_lookup("type", "genre")
        return start_lookup("all" if refresh else "new")

    @app.post("/api/suggestions/approve")
    def approve_suggestions(body: SuggestedSelection):
        n = tagging.decide([i.model_dump() for i in body.items], True)
        return {
            "approved": n,
            "message": f"{n} My Tag and playlist choices are waiting for rekordbox",
        }

    @app.post("/api/suggestions/reject")
    def reject_suggestions(body: SuggestedSelection):
        return {"rejected": tagging.decide([i.model_dump() for i in body.items], False)}

    @app.post("/api/jobs/{job_id}/resume")
    def resume(job_id: str):
        with store.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row or row["state"] not in ("failed", "interrupted"):
            raise ValueError("This job cannot be resumed")
        return {"job_id": service.start(row["kind"], None, job_id)}

    @app.post("/api/proposals/reject")
    def reject(body: Selection):
        with store.connect() as db:
            db.executemany(
                "UPDATE proposals SET status='rejected' WHERE id=? AND status='pending'",
                [(i,) for i in body.ids],
            )
        store.log("review", "Rejected selected proposals")
        return {"rejected": len(body.ids)}

    @app.post("/api/proposals/approve")
    def approve(body: Selection):
        return editing.approve(body.ids)

    @app.post("/api/edits/sync")
    def sync_edits():
        if not editing.pending():
            raise ValueError("No saved edits are waiting to sync")
        return {"job_id": service.start("sync_edits", {})}

    def correct(track_id, field, value, reason, changed=False):
        """Put the user's own value up for one field, in place of what was suggested."""
        if field not in audio.FIELDS:
            raise ValueError("This field is preserved and cannot be changed")
        value = value.strip()
        if not value:
            raise ValueError("Empty values cannot erase existing metadata")
        if field == "year" and (not value.isdigit() or not 1000 <= int(value) <= 2999):
            raise ValueError("Year must be four digits")
        track = store.track(track_id)
        track["overrides"].pop(field, None)
        if changed and unchanged(track, field, value, "manual"):
            raise ValueError(
                "That is already the track's value; reject the suggestion instead"
            )
        with store.connect() as db:
            db.execute(
                "UPDATE proposals SET status='superseded' WHERE track_id=? AND field=? AND status='pending'",
                (track_id, field),
            )
            db.execute(
                "DELETE FROM proposals WHERE track_id=? AND field=? AND new_value=? AND source='manual'",
                (track_id, field, value),
            )
        store.propose(track, field, value, "high", reason, "manual")
        return value

    @app.post("/api/tracks/{track_id}/manual")
    def manual(track_id: int, body: Manual):
        correct(
            track_id,
            body.field,
            body.value,
            "Your manual correction; locked after applying",
        )
        return {"saved": True}

    @app.post("/api/proposals/{proposal_id}/edit")
    def edit_proposal(proposal_id: int, body: Value):
        """Replace a suggested value with a corrected one, ready to approve."""
        found = [p for p in store.proposals() if p["id"] == proposal_id]
        if not found:
            raise ValueError("That suggestion is no longer waiting; refresh the review")
        p = found[0]
        if body.value.strip() == p["new_value"]:
            return {"saved": True, "id": p["id"]}
        value = correct(
            p["track_id"],
            p["field"],
            body.value,
            f"Your correction of the suggested value “{p['new_value']}”",
            changed=True,
        )
        with store.connect() as db:
            row = db.execute(
                "SELECT id FROM proposals WHERE track_id=? AND field=? AND new_value=? AND source='manual' AND status='pending'",
                (p["track_id"], p["field"], value),
            ).fetchone()
        return {"saved": True, "id": row["id"]}

    @app.post("/api/apply")
    def apply(body: Selection):
        return operations.apply(body.ids)

    @app.post("/api/duplicates/merge")
    def merge_duplicates(body: Merges):
        return duplicates.merge([m.model_dump() for m in body.merges])

    @app.post("/api/duplicates/dismiss")
    def dismiss_duplicates(body: Groups):
        return duplicates.dismiss(body.groups)

    @app.post("/api/duplicates/reset-dismissed")
    def reset_dismissed_duplicates():
        return duplicates.reset_dismissed()

    @app.get("/api/backups")
    def list_backups():
        return backups.list()

    @app.post("/api/backups/delete")
    def delete_backups(body: BackupSelection):
        return backups.delete(body.ids)

    @app.post("/api/operations/{opid}/restore")
    def restore(opid: str):
        return operations.restore(opid)

    @app.get("/api/tracks/{track_id}/audio")
    def stream(track_id: int):
        track = store.track(track_id)
        if (
            not track["available"]
            or Path(track["path"]).suffix.lower() not in audio.PLAYABLE
        ):
            raise HTTPException(404, "Audio unavailable")
        return FileResponse(track["path"])

    @app.get("/api/tracks/{track_id}/artwork")
    def artwork(track_id: int):
        track = store.track(track_id)
        try:
            art = audio.artwork(track["path"]) if track["available"] else None
        except Exception:
            art = None
        if not art or art[1] not in ("image/jpeg", "image/png"):
            raise HTTPException(404, "No embedded artwork")
        return Response(art[0], media_type=art[1])

    dist = Path(__file__).resolve().parents[2] / "frontend/dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
    return app
