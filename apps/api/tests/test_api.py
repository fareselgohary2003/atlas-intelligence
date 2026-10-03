def signup(c, email, ws="Acme"):
    r = c.post("/api/auth/signup", json={"email": email, "password": "password123", "name": "T", "workspace_name": ws, "issue_token": True})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return h, c.get("/api/auth/me", headers=h).json()["workspaces"][0]["id"]


BODY = {"objective": "Analyze the B2B SaaS market in Saudi Arabia for mid-sized firms."}


def test_signup_login_me(client):
    signup(client, "a@x.com")
    assert client.post("/api/auth/login", json={"email": "a@x.com", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"}).status_code == 200
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401


def test_research_crud_and_summary(client):
    h, ws = signup(client, "a@x.com")
    r = client.post("/api/research", json={**BODY, "workspace_id": ws}, headers=h)
    assert r.status_code == 201 and r.json()["status"] == "planning" and r.json()["depth"] == "deep"
    rid = r.json()["id"]
    lst = client.get(f"/api/research?workspace_id={ws}&q=saudi", headers=h).json()
    assert lst["total"] == 1
    assert client.patch(f"/api/research/{rid}", json={"title": "New"}, headers=h).json()["title"] == "New"
    assert client.get(f"/api/research/summary?workspace_id={ws}", headers=h).json()["total"] == 1
    assert client.delete(f"/api/research/{rid}", headers=h).status_code == 204
    actions = [a["action"] for a in client.get(f"/api/workspaces/{ws}/audit", headers=h).json()["items"]]
    assert "USER_CREATED_RESEARCH" in actions and "RESEARCH_DELETED" in actions


def test_workspace_isolation(client):
    h1, ws1 = signup(client, "a@x.com")
    h2, _ = signup(client, "b@x.com", "Other")
    rid = client.post("/api/research", json={**BODY, "workspace_id": ws1}, headers=h1).json()["id"]
    assert client.get(f"/api/research/{rid}", headers=h2).status_code == 404
    assert client.get(f"/api/research?workspace_id={ws1}", headers=h2).status_code == 404


def test_viewer_cannot_write(client):
    h1, ws = signup(client, "a@x.com")
    h2, _ = signup(client, "v@x.com", "V")
    assert client.post(f"/api/workspaces/{ws}/members", json={"email": "v@x.com", "role": "viewer"}, headers=h1).status_code == 201
    assert client.post("/api/research", json={**BODY, "workspace_id": ws}, headers=h2).status_code == 403
    assert client.get(f"/api/research?workspace_id={ws}", headers=h2).status_code == 200
