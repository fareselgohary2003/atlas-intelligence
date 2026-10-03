import json
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import WRITE, audit, current_user
from app.api.research import load
from app.core.db import SessionLocal, get_db
from app.models import AgentEvent, ResearchProject as R, ResearchTask as RT, User
from app.workers.queue import QueueUnavailable, enqueue_research

router = APIRouter(prefix="/api/research", tags=["runs"])
FINISHED = {"completed", "needs_review", "failed", "cancelled"}
STREAM_MAX_SECONDS = 1800


def session_factory():
    return SessionLocal  # dependency so tests can substitute a session factory


def iso(d):
    return d.isoformat() if d else None


def _guarded(db: Session, p: R, from_states: set, values: dict, verb: str, action: str, user: User):
    """Atomic compare-and-set on status. Losing the race (or a duplicate request) yields 409, never a double run."""
    res = db.execute(update(R).where(R.id == p.id, R.status.in_(from_states)).values(**values))
    if res.rowcount != 1:
        db.rollback()
        db.refresh(p)
        raise HTTPException(409, f"Cannot {verb} research that is '{p.status}'")
    audit(db, p.workspace_id, user.id, action, "research", p.id)
    db.commit()


def _enqueue_or_revert(db: Session, p: R, user: User, revert_to: str, queued_status="queued"):
    try:
        enqueue_research(str(p.id))
    except QueueUnavailable:
        db.execute(update(R).where(R.id == p.id, R.status == queued_status).values(status=revert_to))
        audit(db, p.workspace_id, user.id, "RESEARCH_ENQUEUE_FAILED", "research", p.id)
        db.commit()
        raise HTTPException(503, "The research queue is unavailable. Nothing was started; try again shortly.")


@router.post("/{rid}/start", status_code=202)
def start(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid, WRITE)
    _guarded(db, p, {"planning"}, {"status": "queued", "control_state": None, "run_error": None}, "start", "RESEARCH_START_REQUESTED", user)
    _enqueue_or_revert(db, p, user, "planning")
    return {"status": "queued"}


@router.post("/{rid}/resume", status_code=202)
def resume(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid, WRITE)
    _guarded(db, p, {"paused"}, {"status": "queued", "control_state": None}, "resume", "RESEARCH_RESUMED", user)
    _enqueue_or_revert(db, p, user, "paused")
    return {"status": "queued"}


@router.post("/{rid}/pause", status_code=202)
def pause(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid, WRITE)
    _guarded(db, p, {"queued", "researching"}, {"control_state": "pause"}, "pause", "RESEARCH_PAUSE_REQUESTED", user)
    return {"status": "pausing"}  # the worker pauses after in-flight tasks finish


@router.post("/{rid}/cancel", status_code=202)
def cancel(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid, WRITE)
    res = db.execute(update(R).where(R.id == p.id, R.status.in_({"planning", "queued", "paused"}))
                     .values(status="cancelled", control_state=None, finished_at=func.now()))
    if res.rowcount == 1:  # nothing is running, so cancel immediately
        audit(db, p.workspace_id, user.id, "RESEARCH_CANCELLED", "research", p.id)
        db.commit()
        return {"status": "cancelled"}
    db.rollback()
    _guarded(db, p, {"researching"}, {"control_state": "cancel"}, "cancel", "RESEARCH_CANCEL_REQUESTED", user)
    return {"status": "cancelling"}


@router.get("/{rid}/status")
def status(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid)
    counts = dict(db.execute(select(RT.status, func.count()).where(RT.research_id == p.id).group_by(RT.status)).all())
    replans = db.scalar(select(func.count()).select_from(AgentEvent).where(
        AgentEvent.research_id == p.id, AgentEvent.kind == "RESEARCH_REPLANNED"))
    return {"status": p.status, "progress": p.progress, "control_state": p.control_state, "tasks": counts,
            "replans": replans, "error": p.run_error, "started_at": iso(p.started_at), "finished_at": iso(p.finished_at)}


@router.get("/{rid}/tasks")
def tasks(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid)
    rows = db.scalars(select(RT).where(RT.research_id == p.id).order_by(RT.created_at, RT.key)).all()
    return [{"id": t.key, "title": t.title, "agent": t.agent, "depends_on": t.depends_on, "status": t.status,
             "attempts": t.attempts, "error": (t.error or "")[:300] or None,
             "summary": (t.result or {}).get("summary"), "confidence": (t.result or {}).get("confidence")} for t in rows]


@router.get("/{rid}/events")
def events(rid: str, after_seq: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid)
    rows = db.scalars(select(AgentEvent).where(AgentEvent.research_id == p.id, AgentEvent.seq > after_seq)
                      .order_by(AgentEvent.seq).limit(limit)).all()
    return [{**e.payload, "seq": e.seq} for e in rows]


@router.get("/{rid}/events/stream")
def stream(rid: str, after_seq: int = 0, last_event_id: str | None = Header(None),
           user: User = Depends(current_user), db: Session = Depends(get_db), sf=Depends(session_factory)):
    pid = load(db, user, rid).id  # authorization happens once, before streaming
    cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else after_seq

    def gen():
        nonlocal cursor
        started = last_ping = time.monotonic()
        while time.monotonic() - started < STREAM_MAX_SECONDS:
            try:
                with sf() as s:  # short session per poll; no connection is held while idle
                    rows = s.scalars(select(AgentEvent).where(AgentEvent.research_id == pid, AgentEvent.seq > cursor)
                                     .order_by(AgentEvent.seq).limit(200)).all()
                    state = s.scalar(select(R.status).where(R.id == pid))
                    out = [(e.seq, e.kind, json.dumps({**e.payload, "seq": e.seq})) for e in rows]
            except SQLAlchemyError:
                yield "event: error\ndata: {\"message\": \"Event store temporarily unavailable\"}\n\n"
                return  # client reconnects with Last-Event-ID and resumes without gaps
            for seq, kind, data in out:
                cursor = seq
                yield f"id: {seq}\ndata: {data}\n\n"  # unnamed events: the browser EventSource onmessage receives every kind
            if not out and (state in FINISHED or state in ("paused", None)):
                yield "event: end\ndata: {}\n\n"
                return
            if not out:
                if time.monotonic() - last_ping > 15:
                    last_ping = time.monotonic()
                    yield ": ping\n\n"
                time.sleep(1)
        yield "event: end\ndata: {\"reconnect\": true}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
