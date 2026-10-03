"""SQLAlchemy implementation of RunStore. Each call uses its own short session, so it is safe to call from the
engine's main loop and from runner threads."""
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select, update

from app.agents.events import public_event
from app.agents.state import ResearchState, Task
from app.models import AgentEvent, AgentRun, ResearchProject as R, ResearchTask as RT
from app.services.audit import audit

AUDITED = {"RESEARCH_STARTED", "RESEARCH_PAUSED", "RESEARCH_CANCELLED", "RESEARCH_COMPLETED", "RESEARCH_FAILED",
           "RESEARCH_REPLANNED"}
DONE = ("completed", "failed", "skipped")
AUDIT_ACTION = {**{k: k for k in AUDITED}, "AGENT_STARTED": "TASK_STARTED", "TASK_FAILED": "TASK_FAILED"}  # event kind -> audit action
RUN_STATUS = {"TASK_COMPLETED": "completed", "TASK_FAILED": "failed", "TASK_RETRY": "retrying"}


def _now():
    return datetime.now(timezone.utc)


def _aware(d):
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


class SqlRunStore:
    def __init__(self, session_factory, heartbeat_ttl=60, poll_interval=1.0):
        self.sf, self.ttl, self.poll_interval, self._polled = session_factory, heartbeat_ttl, poll_interval, {}

    def claim(self, research_id) -> bool:
        rid, now = uuid.UUID(str(research_id)), _now()
        stale = or_(R.status == "queued", and_(R.status == "researching", R.heartbeat_at < now - timedelta(seconds=self.ttl)))
        with self.sf() as db:  # a redelivered message or crashed worker can reclaim only when the heartbeat is stale
            res = db.execute(update(R).where(R.id == rid, stale).values(
                status="researching", started_at=func.coalesce(R.started_at, now), heartbeat_at=now))
            db.commit()
            return res.rowcount == 1

    def load_state(self, research_id) -> ResearchState:
        rid = uuid.UUID(str(research_id))
        with self.sf() as db:
            p = db.get(R, rid)
            if p is None:
                raise LookupError(f"research {research_id} not found")
            scope = [f"{k}: {v}" for k, v in (("Industry", p.industry), ("Geography", p.geography),
                     ("Target customer", p.target_customer), ("Time range", p.time_range),
                     ("Known competitors", ", ".join(p.competitors or []))) if v]
            s = ResearchState(str(p.id), str(p.workspace_id), p.objective + ("\n\nScope:\n" + "\n".join(scope) if scope else ""))
            for r in db.scalars(select(RT).where(RT.research_id == rid).order_by(RT.created_at, RT.key)):
                s.tasks[r.key] = Task(r.key, r.title, r.agent, r.depends_on, r.status, r.attempts, r.error, r.result)
            s.seq_base = db.scalar(select(func.coalesce(func.max(AgentEvent.seq), 0)).where(AgentEvent.research_id == rid))
            s.replans = db.scalar(select(func.count()).select_from(AgentEvent).where(
                AgentEvent.research_id == rid, AgentEvent.kind == "RESEARCH_REPLANNED"))
            s.errors = [{"task_id": t.id, "error": t.error} for t in s.tasks.values() if t.status.value == "failed"]
            return s

    def record(self, state: ResearchState, ev: dict) -> None:
        now = datetime.fromtimestamp(ev["ts"], timezone.utc)
        with self.sf() as db:
            p = db.get(R, uuid.UUID(state.research_id))
            db.add(AgentEvent(research_id=p.id, workspace_id=p.workspace_id, seq=ev["seq"], kind=ev["kind"],
                              task_key=ev.get("task_id"), agent=ev.get("agent"), payload=public_event(ev), ts=now))
            tid = ev.get("task_id")
            if tid in state.tasks:
                row = self._sync_task(db, p, state.tasks[tid])
                self._track_run(db, p, row, ev, now)
                total = db.scalar(select(func.count()).select_from(RT).where(RT.research_id == p.id))
                done = db.scalar(select(func.count()).select_from(RT).where(RT.research_id == p.id, RT.status.in_(DONE)))
                p.progress = int(100 * done / total) if total else 0
            if ev["kind"] in AUDIT_ACTION:  # same transaction as the event row
                audit(db, p.workspace_id, None, AUDIT_ACTION[ev["kind"]], "research", p.id,
                      {k: ev[k] for k in ("status", "error", "new_tasks", "reasons", "task_id", "agent", "attempt") if k in ev})
            db.commit()

    @staticmethod
    def _sync_task(db, p, t: Task) -> RT:
        row = db.scalar(select(RT).where(RT.research_id == p.id, RT.key == t.id))
        if row is None:
            row = RT(research_id=p.id, workspace_id=p.workspace_id, key=t.id)
            db.add(row)
        row.title, row.agent, row.depends_on = t.title, t.agent, t.depends_on
        row.status, row.attempts, row.error, row.result = t.status.value, t.attempts, t.error, t.result
        db.flush()
        return row

    @staticmethod
    def _track_run(db, p, row, ev, now):
        kind = ev["kind"]
        if kind == "AGENT_STARTED":
            db.add(AgentRun(research_id=p.id, workspace_id=p.workspace_id, task_id=row.id, agent=row.agent,
                            attempt=ev.get("attempt", 1), status="running", started_at=now))
        elif kind in RUN_STATUS:
            run = db.scalar(select(AgentRun).where(AgentRun.task_id == row.id, AgentRun.status == "running")
                            .order_by(AgentRun.attempt.desc()))
            if run:
                run.status, run.finished_at = RUN_STATUS[kind], now
                run.duration_ms = int((now - _aware(run.started_at)).total_seconds() * 1000)
                run.summary, run.error = ev.get("summary"), ev.get("error")
                c = ev.get("counts") or {}
                run.tool_calls_count, run.source_count = c.get("tool_calls", 0), c.get("sources", 0)
                run.evidence_count, run.claim_count = c.get("evidence", 0), c.get("claims", 0)

    def poll_control(self, research_id):
        t, last = time.monotonic(), self._polled.get(research_id)
        if last and t - last[0] < self.poll_interval:
            return last[1]
        with self.sf() as db:
            p = db.get(R, uuid.UUID(str(research_id)))
            p.heartbeat_at = _now()
            ctl = p.control_state
            db.commit()
        self._polled[research_id] = (t, ctl)
        return ctl

    def finish(self, state: ResearchState, status: str, error: str | None = None) -> None:
        with self.sf() as db:
            p = db.get(R, uuid.UUID(state.research_id))
            p.status, p.run_error, p.control_state = status, error, None
            if status != "paused":
                p.finished_at = _now()
            if status == "completed":
                p.progress = 100
            db.commit()
