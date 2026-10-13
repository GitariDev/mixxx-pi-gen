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
