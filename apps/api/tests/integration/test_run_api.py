"""UNEXECUTED in the authoring environment (needs fastapi, sqlalchemy, httpx). Run: cd apps/api && pytest tests/integration"""
import pytest

from app.workers.queue import QueueUnavailable
from tests.test_api import BODY, signup


@pytest.fixture
def project(client, monkeypatch):
    monkeypatch.setattr("app.api.runs.enqueue_research", lambda rid: None)
    h, ws = signup(client, "a@x.com")
    rid = client.post("/api/research", json={**BODY, "workspace_id": ws}, headers=h).json()["id"]
    return client, h, ws, rid


def test_start_is_idempotent_by_conflict(project):
    c, h, _, rid = project
    assert c.post(f"/api/research/{rid}/start", headers=h).status_code == 202
    assert c.post(f"/api/research/{rid}/start", headers=h).status_code == 409
    assert c.get(f"/api/research/{rid}/status", headers=h).json()["status"] == "queued"


def test_enqueue_failure_reverts_status_and_returns_503(project, monkeypatch):
    c, h, _, rid = project

    def down(_):
        raise QueueUnavailable("redis down")
    monkeypatch.setattr("app.api.runs.enqueue_research", down)
    assert c.post(f"/api/research/{rid}/start", headers=h).status_code == 503
    assert c.get(f"/api/research/{rid}/status", headers=h).json()["status"] == "planning"


def test_cancel_before_start_then_cancel_again_conflicts(project):
    c, h, _, rid = project
    assert c.post(f"/api/research/{rid}/cancel", headers=h).json()["status"] == "cancelled"
    assert c.post(f"/api/research/{rid}/cancel", headers=h).status_code == 409
    assert c.post(f"/api/research/{rid}/resume", headers=h).status_code == 409


def test_isolation_and_invalid_ids(project):
    c, h, _, rid = project
    h2, _ = signup(c, "b@x.com", "Other")
    for path in ("start", "pause", "cancel", "resume"):
        assert c.post(f"/api/research/{rid}/{path}", headers=h2).status_code == 404
    for path in ("status", "tasks", "events", "events/stream"):
        assert c.get(f"/api/research/{rid}/{path}", headers=h2).status_code == 404
    assert c.get("/api/research/not-a-uuid/status", headers=h).status_code == 404


def test_viewer_cannot_start(project):
    c, h, ws, rid = project
    hv, _ = signup(c, "v@x.com", "V")
    c.post(f"/api/workspaces/{ws}/members", json={"email": "v@x.com", "role": "viewer"}, headers=h)
    assert c.post(f"/api/research/{rid}/start", headers=hv).status_code == 403
