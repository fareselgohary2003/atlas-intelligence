"""UNEXECUTED in the authoring environment (needs fastapi, sqlalchemy, httpx, pytest): sessions/CSRF, members, audit filters, agents, settings, graph."""

from sqlalchemy import select

from app.evidence.domain import Scope
from app.evidence.service import EvidenceService
from app.models import AuditLog
from app.repositories.evidence import SqlEvidenceRepository
from tests.evidence_contract import ATTRS, CLAIM, TEXT, cand
from tests.test_api import BODY, signup


def cookie_signup(client, email="c@x.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "password123", "name": "C", "workspace_name": "W"})
    assert r.status_code == 201 and "access_token" not in r.json()  # no token in the body unless explicitly requested
    sc = r.headers.get_list("set-cookie")
    assert any("atlas_session" in c and "HttpOnly" in c for c in sc) and any("atlas_csrf" in c and "HttpOnly" not in c for c in sc)
    return client.cookies.get("atlas_csrf")


def test_cookie_session_requires_csrf_on_unsafe_methods(client):
    csrf = cookie_signup(client)
    me = client.get("/api/auth/me").json()
    ws = me["workspaces"][0]["id"]
    body = {**BODY, "workspace_id": ws}
    assert client.post("/api/research", json=body).status_code == 403                                   # cookie without CSRF header
    assert client.post("/api/research", json=body, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.post("/api/research", json=body, headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/research", json=body, headers={"X-CSRF-Token": csrf}).status_code == 201
    assert client.get("/api/research?workspace_id=" + ws).status_code == 200                           # safe methods need no CSRF
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_bearer_clients_skip_csrf_and_bad_tokens_are_rejected(client):
    h, ws = signup(client, "b@x.com")
    assert client.post("/api/research", json={**BODY, "workspace_id": ws}, headers=h).status_code == 201
    for bad in ("garbage", "a.b.c", ""):
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_login_is_rate_limited_per_ip_and_per_account_and_audited(client):
    signup(client, "r@x.com")
    for _ in range(10):
        assert client.post("/api/auth/login", json={"email": "r@x.com", "password": "bad-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "r@x.com", "password": "password123"}).status_code == 429  # account cap reached
    assert "Retry-After" in client.post("/api/auth/login", json={"email": "r@x.com", "password": "x"}).headers


def test_login_writes_an_audit_row(client):
    signup(client, "l@x.com")
    assert client.post("/api/auth/login", json={"email": "l@x.com", "password": "password123"}).status_code == 200
    with client.sf() as db:
        assert "USER_LOGIN" in [a.action for a in db.scalars(select(AuditLog))]


def test_members_roles_and_audit_filters(client):
    h, ws = signup(client, "o@x.com")
    h2, _ = signup(client, "m@x.com", "Other")
    uid = client.get("/api/auth/me", headers=h2).json()["id"]
    assert client.post(f"/api/workspaces/{ws}/members", json={"email": "m@x.com", "role": "viewer"}, headers=h).status_code == 201
    assert client.patch(f"/api/workspaces/{ws}/members/{uid}", json={"role": "researcher"}, headers=h).status_code == 200
    assert client.patch(f"/api/workspaces/{ws}/members/{uid}", json={"role": "owner"}, headers=h).status_code == 422
    assert client.patch(f"/api/workspaces/{ws}/members/{uid}", json={"role": "admin"}, headers=h2).status_code == 403  # researcher cannot manage roles
    owner = client.get(f"/api/workspaces/{ws}/members", headers=h).json()[0]["user_id"]
    assert client.delete(f"/api/workspaces/{ws}/members/{owner}", headers=h).status_code == 403   # owners are protected
    assert client.delete(f"/api/workspaces/{ws}/members/{uid}", headers=h).status_code == 204
    a = client.get(f"/api/workspaces/{ws}/audit?action=ROLE_CHANGED", headers=h).json()
    assert a["total"] == 1 and a["items"][0]["meta"] == {"from": "viewer", "to": "researcher"}
    assert client.get(f"/api/workspaces/{ws}/audit?limit=0", headers=h).status_code == 422
    assert client.get(f"/api/workspaces/{ws}", headers=h2).status_code in (404, 405)


def test_agents_and_settings_expose_no_secrets(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-SHOULD-NEVER-APPEAR")
    monkeypatch.setenv("WEB_SEARCH_API_KEY", "brave-SHOULD-NEVER-APPEAR")
    h, ws = signup(client, "s@x.com")
    ag = client.get(f"/api/agents?workspace_id={ws}", headers=h).json()
    assert {a["id"] for a in ag} == {"research_manager", "market", "customer", "competitor", "pricing", "regulation", "risk", "fact_checker", "analyst"}
    assert all(a["stats"] is None for a in ag)  # never ran: "No data yet", not zeros
    assert client.get(f"/api/agents/ghost/runs?workspace_id={ws}", headers=h).status_code == 404
    cfg = client.get(f"/api/settings/config?workspace_id={ws}", headers=h)
    assert cfg.json()["llm"]["api_key_configured"] is True and "SHOULD-NEVER-APPEAR" not in cfg.text
    h2, _ = signup(client, "t@x.com", "Other")
    assert client.get(f"/api/agents?workspace_id={ws}", headers=h2).status_code == 404


def test_graph_and_report_versions_endpoints(client):
    h, ws = signup(client, "g@x.com")
    rid = client.post("/api/research", json={**BODY, "workspace_id": ws}, headers=h).json()["id"]
    assert client.get(f"/api/research/{rid}/graph", headers=h).json()["nodes"] == []
    svc, sc = EvidenceService(SqlEvidenceRepository(client.sf)), Scope(ws, rid, "t1", "market")
    s, _, _ = svc.save_source(sc, cand(), TEXT)
    c, _ = svc.create_claim(sc, CLAIM, "market_size", ATTRS)
    svc.create_evidence(sc, s.id, "reached USD 2.1 billion in 2024", c.id)
    g = client.get(f"/api/research/{rid}/graph", headers=h).json()
    assert g["counts"] == {"claims": 1, "evidence": 1, "sources": 1, "conflicts": 0}
    h2, _ = signup(client, "h@x.com", "Other")
    assert client.get(f"/api/research/{rid}/graph", headers=h2).status_code == 404
    assert client.get(f"/api/research/{rid}/report/versions", headers=h).json() == []
    client.post(f"/api/research/{rid}/report", headers=h)
    assert [v["version"] for v in client.get(f"/api/research/{rid}/report/versions", headers=h).json()] == [1]
