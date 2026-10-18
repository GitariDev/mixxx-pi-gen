from fastapi.testclient import TestClient
from songdex.api import create_app


def test_security_and_demo(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/state", headers={"host": "evil.example"}).status_code == 400
    assert (
        client.get("/api/state", headers={"origin": "https://evil.example"}).status_code
        == 403
    )
    assert client.post("/api/demo").status_code == 403
    state = client.get("/api/state").json()
    headers = {"x-songdex-token": state["token"]}
    assert client.post("/api/demo", headers=headers).status_code == 200
    state = client.get("/api/state").json()
    assert len(state["tracks"]) == 9
    assert not state["capability"]["enabled"]
    assert (
        client.post(
            "/api/apply", headers=headers, json={"ids": [state["proposals"][0]["id"]]}
        ).status_code
        == 409
    )
    assert client.post("/api/scan", headers=headers).status_code == 409
    assert (
        client.post(
            "/api/tracks/1/manual",
            headers=headers,
            json={"field": "bpm", "value": "180"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/tracks/1/manual",
            headers=headers,
            json={"field": "title", "value": "Reviewed title"},
        ).status_code
        == 200
    )
    state = client.get("/api/state").json()
    assert any(p["source"] == "manual" for p in state["proposals"])


def test_suggestion_can_be_corrected_before_approving(tmp_path):
    client = TestClient(create_app(tmp_path))
    headers = {"x-songdex-token": client.get("/api/state").json()["token"]}
    client.post("/api/demo", headers=headers)
    state = client.get("/api/state").json()
    p = state["proposals"][0]
    siblings = [
        q["id"]
        for q in state["proposals"]
        if (q["track_id"], q["field"]) == (p["track_id"], p["field"])
    ]

    def edit(value, proposal=p["id"]):
        return client.post(
            f"/api/proposals/{proposal}/edit", headers=headers, json={"value": value}
        )

    # Nothing is replaced by a value that is not a change, or by an invalid one.
    assert edit(p["old_value"] or " ").status_code in (409, 422)
    assert edit(p["new_value"]).json()["id"] == p["id"]
    fixed = edit("Corrected by hand")
    assert fixed.status_code == 200
    after = client.get("/api/state").json()["proposals"]
    (mine,) = [q for q in after if q["id"] == fixed.json()["id"]]
    assert (mine["new_value"], mine["source"]) == ("Corrected by hand", "manual")
    assert p["new_value"] in mine["reason"]
    assert not {q["id"] for q in after} & set(siblings)
    assert edit("Too late").status_code == 409


def test_review_follows_the_latest_scan(tmp_path):
    client = TestClient(create_app(tmp_path))
    state = client.get("/api/state").json()
    headers = {"x-songdex-token": state["token"]}
    assert (state["scan"], state["suggested"], state["queued"]) == (None, [], [])
    live = client.get("/api/review").json()
    assert set(live) == {"jobs", "proposals", "scan", "suggested", "queued"}
    # Nothing to scan in an empty Dex, and demo entries are never looked up.
    response = client.post("/api/lookup", headers=headers, json={"scope": "all"})
    assert response.status_code == 409 and "No tracks" in response.json()["detail"]
    client.post("/api/demo", headers=headers)
    response = client.post("/api/lookup", headers=headers, json={"scope": "new"})
    assert response.status_code == 409 and "Demo" in response.json()["detail"]
    assert client.post("/api/lookup/stop", headers=headers).status_code == 409


def test_audio_is_served_with_a_standard_type(tmp_path, audio_file):
    app = create_app(tmp_path / "dex")
    client = TestClient(app)
    headers = {"x-songdex-token": client.get("/api/state").json()["token"]}
    client.post("/api/demo", headers=headers)
    for ext, kind in [("flac", "audio/flac"), ("m4a", "audio/mp4")]:
        path = audio_file(ext)
        with app.state.store.connect() as db:
            db.execute("UPDATE tracks SET path=?,available=1 WHERE id=1", (str(path),))
        response = client.get("/api/tracks/1/audio", headers={"range": "bytes=0-"})
        assert response.status_code == 206
        assert response.headers["content-type"] == kind
