"""UNEXECUTED in the authoring environment (needs fastapi, sqlalchemy, httpx, pytest)."""
import uuid

from app.evidence.domain import Scope
from app.evidence.service import EvidenceService
from app.repositories.evidence import SqlEvidenceRepository
from tests.evidence_contract import ATTRS, CLAIM, TEXT, cand
from tests.test_api import BODY, signup


def seeded(client):
    h, ws = signup(client, "a@x.com")
    rid = client.post("/api/research", json={**BODY, "workspace_id": ws}, headers=h).json()["id"]
    svc = EvidenceService(SqlEvidenceRepository(client.sf))
    sc = Scope(ws, rid, "t1", "market")
    s, _, _ = svc.save_source(sc, cand(), TEXT)
    c, _ = svc.create_claim(sc, CLAIM, "market_size", ATTRS)
    svc.create_evidence(sc, s.id, "reached USD 2.1 billion in 2024", c.id)
    svc.verify_claim(Scope(ws, rid, None, "fact_checker"), c.id)
    return h, ws, rid


def test_lists_return_records_without_full_text(client):
    h, _, rid = seeded(client)
    src = client.get(f"/api/research/{rid}/sources", headers=h).json()
    assert len(src) == 1 and "content_text" not in src[0]
    ev = client.get(f"/api/research/{rid}/evidence", headers=h).json()
    assert ev[0]["excerpt"] == "reached USD 2.1 billion in 2024" and ev[0]["is_demo"] is False
    cl = client.get(f"/api/research/{rid}/claims", headers=h).json()
    assert cl[0]["status"] in ("partially_supported", "supported") and cl[0]["verification"]["verifier"] == "rules/1"
    assert client.get(f"/api/research/{rid}/conflicts", headers=h).json() == []


def test_other_workspace_gets_404_everywhere(client):
    h, _, rid = seeded(client)
    h2, _ = signup(client, "b@x.com", "Other")
    for path in ("sources", "evidence", "claims", "conflicts"):
        assert client.get(f"/api/research/{rid}/{path}", headers=h2).status_code == 404
    assert client.get(f"/api/research/{uuid.uuid4()}/claims", headers=h).status_code == 404
    assert client.get(f"/api/research/{rid}/sources?limit=0", headers=h).status_code == 422
