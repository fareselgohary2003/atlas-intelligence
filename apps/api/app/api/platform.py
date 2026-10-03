"""Workspace-level read endpoints: agent catalog + real run statistics, and non-secret configuration display."""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.catalog import agent_definitions
from app.api.deps import current_user, membership
from app.core import security
from app.core.config import settings
from app.core.db import get_db
from app.models import AgentRun, User

router = APIRouter(prefix="/api", tags=["platform"])


@router.get("/agents")
def agents(workspace_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, workspace_id)
    w = uuid.UUID(workspace_id)
    stats = {}
    for agent, status, n, avg, src, ev, cl, last in db.execute(select(
            AgentRun.agent, AgentRun.status, func.count(), func.avg(AgentRun.duration_ms), func.coalesce(func.sum(AgentRun.source_count), 0),
            func.coalesce(func.sum(AgentRun.evidence_count), 0), func.coalesce(func.sum(AgentRun.claim_count), 0), func.max(AgentRun.started_at))
            .where(AgentRun.workspace_id == w).group_by(AgentRun.agent, AgentRun.status)):
        s = stats.setdefault(agent, {"runs": 0, "by_status": {}, "sources": 0, "evidence": 0, "claims": 0, "last_run": None, "_dur": []})
        s["runs"] += n
        s["by_status"][status] = n
        s["sources"] += int(src)
        s["evidence"] += int(ev)
        s["claims"] += int(cl)
        s["last_run"] = max(filter(None, [s["last_run"], last]), default=None)
        if avg is not None and status in ("completed", "failed"):
            s["_dur"].append(float(avg))
    out = []
    for d in agent_definitions():
        s = stats.get(d.id)
        if s:
            durs = s.pop("_dur")
            s["avg_duration_ms"] = round(sum(durs) / len(durs)) if durs else None
            s["last_run"] = s["last_run"].isoformat() if s["last_run"] else None
        out.append({"id": d.id, "name": d.name, "description": d.description, "capabilities": list(d.capabilities),
                    "allowed_tools": list(d.allowed_tools), "stats": s})  # stats is None when the agent has never run (UI: "No data yet")
    return out


@router.get("/agents/{agent_id}/runs")
def agent_runs(agent_id: str, workspace_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, workspace_id)
    if agent_id not in {d.id for d in agent_definitions()}:
        raise HTTPException(404, "Unknown agent")
    q = select(AgentRun).where(AgentRun.workspace_id == uuid.UUID(workspace_id), AgentRun.agent == agent_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AgentRun.started_at.desc(), AgentRun.id).limit(limit).offset(offset)).all()
    return {"total": total, "items": [{"id": str(r.id), "research_id": str(r.research_id), "attempt": r.attempt, "status": r.status,
                                       "started_at": r.started_at.isoformat(), "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                                       "duration_ms": r.duration_ms, "summary": (r.summary or "")[:300] or None, "error": (r.error or "")[:300] or None,
                                       "counts": {"tool_calls": r.tool_calls_count, "sources": r.source_count, "evidence": r.evidence_count, "claims": r.claim_count}}
                                      for r in rows]}


@router.get("/settings/config")
def config(workspace_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Non-secret configuration for display. Secrets are reported only as 'configured: true/false'."""
    m = membership(db, user, workspace_id)
    env = os.environ
    host = lambda u: (u or "").split("//")[-1].split("/")[0] or None
    prim = getattr(security.get_limiter(), "primary", None)
    return {"role": m.role,
            "demo": {"demo_mode": env.get("DEMO_MODE", "").lower() == "true", "llm_provider": env.get("LLM_PROVIDER") or "openai-compatible",
                     "search_provider": env.get("WEB_SEARCH_PROVIDER") or None},
            "llm": {"model": env.get("LLM_MODEL", "gpt-4o-mini"), "endpoint_host": host(env.get("LLM_BASE_URL", "https://api.openai.com/v1")),
                    "api_key_configured": bool(env.get("LLM_API_KEY"))},
            "search": {"provider": env.get("WEB_SEARCH_PROVIDER") or None, "api_key_configured": bool(env.get("WEB_SEARCH_API_KEY"))},
            "pricing": {"input_per_1k": env.get("LLM_PRICE_INPUT_PER_1K") or None, "output_per_1k": env.get("LLM_PRICE_OUTPUT_PER_1K") or None,
                        "configured": bool(env.get("LLM_PRICE_INPUT_PER_1K") and env.get("LLM_PRICE_OUTPUT_PER_1K"))},
            "security": {"cookie_secure": settings.cookie_secure, "cookie_samesite": settings.cookie_samesite, "session_ttl_minutes": settings.jwt_expire_minutes,
                         "api_rate_limit_per_minute": settings.api_rate_limit, "rate_limiter": type(prim).__name__ if prim else "unknown",
                         "jwt_secret_is_default": settings.jwt_secret == "dev-only-change-me"},
            "research": {"max_replans": settings.max_replans, "max_parallel_tasks": settings.max_parallel}}
