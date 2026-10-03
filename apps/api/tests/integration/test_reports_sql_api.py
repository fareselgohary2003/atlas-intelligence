"""UNEXECUTED in the authoring environment (needs sqlalchemy, fastapi, httpx, pytest)."""
import json

from app.evidence.domain import Scope
from app.evidence.service import EvidenceService
from app.models import AuditLog
from app.observability.usage import UsageRecord
from app.reporting.service import ReportService
from app.repositories.evidence import SqlEvidenceRepository
from app.repositories.reports import SqlReportInputs, SqlReportRepository, SqlUsageRecorder
from sqlalchemy import select
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


def actions(client):
    with client.sf() as db:
        return [a.action for a in db.scalars(select(AuditLog))]


def test_generate_get_export_and_audit(client):
    h, _, rid = seeded(client)
    r = client.post(f"/api/research/{rid}/report", headers=h)
    assert r.status_code == 201 and r.json()["version"] == 1 and r.json()["stats"]["claims"] == 1
    assert client.post(f"/api/research/{rid}/report", headers=h).json()["version"] == 2
    g = client.get(f"/api/research/{rid}/report", headers=h).json()
    assert g["version"] == 2 and [s["key"] for s in g["content"]["sections"]][0] == "executive_summary" and g["content"]["citations"]
    assert client.get(f"/api/research/{rid}/report?version=1", headers=h).json()["version"] == 1
    for fmt, ctype in (("md", "text/markdown"), ("json", "application/json"), ("pdf", "application/pdf")):
        e = client.get(f"/api/research/{rid}/report/export?format={fmt}", headers=h)
        assert e.status_code == 200 and e.headers["content-type"].startswith(ctype) and "attachment" in e.headers["content-disposition"]
    assert client.get(f"/api/research/{rid}/report/export?format=docx", headers=h).status_code == 422
    assert client.get(f"/api/research/{rid}/report?version=99", headers=h).status_code == 404
    a = actions(client)
    assert a.count("REPORT_GENERATED") == 2 and a.count("REPORT_EXPORTED") == 3


def test_authorization_and_isolation(client):
    h, ws, rid = seeded(client)
    client.post(f"/api/research/{rid}/report", headers=h)
    h2, _ = signup(client, "b@x.com", "Other")
    for method, path in (("post", "report"), ("get", "report"), ("get", "report/export"), ("get", "usage")):
        assert getattr(client, method)(f"/api/research/{rid}/{path}", headers=h2).status_code == 404
    hv, _ = signup(client, "v@x.com", "V")
    client.post(f"/api/workspaces/{ws}/members", json={"email": "v@x.com", "role": "viewer"}, headers=h)
    assert client.post(f"/api/research/{rid}/report", headers=hv).status_code == 403
    assert client.get(f"/api/research/{rid}/report", headers=hv).status_code == 200
    client.cookies.clear()
    assert client.get(f"/api/research/{rid}/report").status_code == 401


def test_sql_report_versions_are_immutable_and_sections_reassembled(client):
    h, ws, rid = seeded(client)
    svc = ReportService(SqlReportInputs(client.sf, SqlEvidenceRepository(client.sf)), SqlReportRepository(client.sf))
    hooks = []
    r1 = svc.generate(Scope(ws, rid), audit_hook=lambda db, rec: hooks.append(rec.version))
    got = SqlReportRepository(client.sf).get_report(rid, 1)
    assert json.dumps(got.content, sort_keys=True, default=str) == json.dumps(r1.content, sort_keys=True, default=str)
    assert [s["key"] for s in got.content["sections"]] == [s["key"] for s in r1.content["sections"]] and hooks == [1]


def test_usage_and_dashboard_use_real_rows_and_never_invent_cost(client):
    h, ws, rid = seeded(client)
    rec = SqlUsageRecorder(client.sf)
    rec.record(UsageRecord("00000000-0000-0000-0000-000000000001", rid, ws, "t1", "market", "p", "m", 100, 50, 0.0002, 10, True, None, None))
    rec.record(UsageRecord("00000000-0000-0000-0000-000000000002", rid, ws, "t1", "market", "p", "m", None, None, None, 20, False, "transient", None))
    u = client.get(f"/api/research/{rid}/usage", headers=h).json()
    assert (u["calls"], u["input_tokens"], u["estimated_cost"], u["cost_complete"]) == (2, 100, 0.0002, False)
    assert u["by_agent"][0]["failed_calls"] == 1 and u["by_agent"][0]["calls_with_cost"] == 1
    m = client.get(f"/api/research/summary?workspace_id={ws}", headers=h).json()
    assert (m["sources"], m["claims"], m["evidence"], m["usage"]["calls"]) == (1, 1, 1, 2) and m["avg_duration_seconds"] is None
    lst = client.get(f"/api/research?workspace_id={ws}", headers=h).json()["items"][0]
    assert (lst["sources_count"], lst["claims_count"]) == (1, 1)
    empty = client.get(f"/api/research/{rid}/usage", headers=signup(client, "c@x.com", "C")[0])
    assert empty.status_code == 404
