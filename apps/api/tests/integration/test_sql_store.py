"""UNEXECUTED in the authoring environment (needs sqlalchemy). Exercises SqlRunStore end to end on SQLite;
Postgres-specific behaviour still needs a run against the compose database."""
import uuid

from sqlalchemy import select

from app.models import AgentEvent, AgentRun, AuditLog, ResearchProject, ResearchTask, User, Workspace
from app.repositories.runs import SqlRunStore
from app.services.execution import execute_research
from tests.test_persistence_contract import PLAN, R3, Scripted


def seed(sf, status="queued"):
    with sf() as db:
        u, w = User(email="a@x.com", name="A", password_hash="x"), Workspace(name="W", slug="w")
        db.add_all([u, w]); db.flush()
        p = ResearchProject(workspace_id=w.id, owner_id=u.id, title="T", objective="Analyze the market", status=status)
        db.add(p); db.commit()
        return str(p.id), w.id


def test_full_run_persists_everything_and_audits_in_txn(sf):
    rid, wid = seed(sf)
    assert execute_research(rid, SqlRunStore(sf), lambda: Scripted(PLAN), R3) == "completed"
    with sf() as db:
        p = db.get(ResearchProject, uuid.UUID(rid))
        assert (p.status, p.progress) == ("completed", 100) and p.finished_at
        assert {t.status for t in db.scalars(select(ResearchTask))} == {"completed"}
        assert {r.status for r in db.scalars(select(AgentRun))} == {"completed"}
        seqs = [e.seq for e in db.scalars(select(AgentEvent).order_by(AgentEvent.seq))]
        assert seqs == list(range(1, len(seqs) + 1))
        actions = {a.action for a in db.scalars(select(AuditLog))}
        assert {"RESEARCH_STARTED", "RESEARCH_COMPLETED", "TASK_STARTED"} <= actions


def test_claim_is_exclusive_and_stale_heartbeat_is_reclaimable(sf):
    rid, _ = seed(sf)
    st = SqlRunStore(sf, heartbeat_ttl=0)
    assert st.claim(rid) is True
    assert SqlRunStore(sf, heartbeat_ttl=3600).claim(rid) is False  # fresh heartbeat: another worker owns it
    assert st.claim(rid) is True  # ttl=0 treats the heartbeat as stale (crashed worker)
