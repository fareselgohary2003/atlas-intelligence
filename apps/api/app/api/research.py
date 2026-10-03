import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, WRITE, audit, current_user, membership
from app.core.db import get_db
from app.models import AgentRun, Claim, Conflict, CostRecord, Evidence, Source
from app.models import ResearchProject as R
from app.models import User
from app.schemas import ResearchIn, ResearchPatch

router = APIRouter(prefix="/api/research", tags=["research"])
STATUSES = ["planning", "queued", "paused", "cancelled", "researching", "verifying", "analyzing", "completed", "needs_review", "failed"]
ACTIVE = {"queued", "researching", "verifying", "analyzing"}
SORTABLE = {"created_at": R.created_at, "title": R.title, "progress": R.progress, "status": R.status}


def _counts(db: Session, ids: list) -> dict:
    """Real per-research counts from the evidence tables (two grouped queries per page, no N+1)."""
    out = {i: {"sources": 0, "claims": 0, "verified": 0} for i in ids}
    if not ids:
        return out
    for rid, n in db.execute(select(Source.research_id, func.count()).where(Source.research_id.in_(ids)).group_by(Source.research_id)):
        out[rid]["sources"] = n
    for rid, st, n in db.execute(select(Claim.research_id, Claim.status, func.count()).where(Claim.research_id.in_(ids)).group_by(Claim.research_id, Claim.status)):
        out[rid]["claims"] += n
        out[rid]["verified"] += n if st == "supported" else 0
    return out


def out(p: R, counts: dict | None = None):
    c = counts or {"sources": 0, "claims": 0, "verified": 0}
    return {"id": str(p.id), "workspace_id": str(p.workspace_id), "title": p.title, "objective": p.objective,
            "industry": p.industry, "geography": p.geography, "target_customer": p.target_customer,
            "time_range": p.time_range, "competitors": p.competitors, "depth": p.depth, "status": p.status,
            "progress": p.progress, "sources_count": c["sources"], "claims_count": c["claims"], "verified_claims": c["verified"],
            "confidence": None, "is_demo": p.is_demo, "owner": p.owner.name,
            "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat()}


def load(db: Session, user: User, rid: str, roles=None) -> R:
    try:
        p = db.get(R, uuid.UUID(rid))
    except ValueError:
        p = None
    if not p:
        raise HTTPException(404, "Research not found")
    membership(db, user, p.workspace_id, roles)  # 404 for non-members
    return p


@router.post("", status_code=201)
def create(body: ResearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, body.workspace_id, WRITE)
    title = (body.title or body.objective.strip().split("\n")[0])[:80]
    p = R(workspace_id=uuid.UUID(body.workspace_id), owner_id=user.id, title=title, objective=body.objective,
          industry=body.industry, geography=body.geography, target_customer=body.target_customer,
          time_range=body.time_range, competitors=body.competitors, depth=body.depth, status="planning")
    db.add(p)
    db.flush()
    audit(db, p.workspace_id, user.id, "USER_CREATED_RESEARCH", "research", p.id, {"title": p.title})
    db.commit()
    return out(p)


@router.get("/summary")
def summary(workspace_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Dashboard metrics computed from stored data only. Missing data is None/0 (the UI shows 'No data yet')."""
    membership(db, user, workspace_id)
    w = uuid.UUID(workspace_id)
    by = dict(db.execute(select(R.status, func.count()).where(R.workspace_id == w).group_by(R.status)).all())
    count = lambda model, *where: db.scalar(select(func.count()).select_from(model).where(model.workspace_id == w, *where)) or 0
    spans = [(f - s).total_seconds() for s, f in db.execute(select(R.started_at, R.finished_at).where(
        R.workspace_id == w, R.status == "completed", R.started_at.is_not(None), R.finished_at.is_not(None)).limit(500))]
    calls, tin, tout, priced, cost = db.execute(select(func.count(), func.coalesce(func.sum(CostRecord.input_tokens), 0),
                                                       func.coalesce(func.sum(CostRecord.output_tokens), 0), func.count(CostRecord.estimated_cost),
                                                       func.sum(CostRecord.estimated_cost)).where(CostRecord.workspace_id == w)).one()
    return {"by_status": by, "total": sum(by.values()), "active": sum(n for s, n in by.items() if s in ACTIVE), "completed": by.get("completed", 0),
            "sources": count(Source), "claims": count(Claim), "verified_claims": count(Claim, Claim.status == "supported"),
            "evidence": count(Evidence), "conflicts": count(Conflict), "agent_runs": count(AgentRun),
            "demo_projects": count(R, R.is_demo == True), "demo_claims": count(Claim, Claim.is_demo == True),
            "avg_duration_seconds": round(sum(spans) / len(spans), 1) if spans else None,
            "usage": {"calls": calls, "input_tokens": int(tin), "output_tokens": int(tout), "calls_with_cost": priced,
                      "estimated_cost": None if cost is None else round(float(cost), 6)}}


@router.get("")
def list_research(workspace_id: str, q: str = "", status: str = "", sort: str = "-created_at",
                  page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, workspace_id)
    key = sort.lstrip("-")
    if key not in SORTABLE or (status and status not in STATUSES):
        raise HTTPException(422, "Invalid sort or status")
    stmt = select(R).where(R.workspace_id == uuid.UUID(workspace_id))
    if q:
        stmt = stmt.where(or_(R.title.ilike(f"%{q}%"), R.objective.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(R.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = SORTABLE[key].desc() if sort.startswith("-") else SORTABLE[key].asc()
    rows = db.scalars(stmt.order_by(col).offset((page - 1) * page_size).limit(page_size)).all()
    counts = _counts(db, [p.id for p in rows])
    return {"items": [out(p, counts[p.id]) for p in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/{rid}")
def get_one(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid)
    return out(p, _counts(db, [p.id])[p.id])


@router.patch("/{rid}")
def patch(rid: str, body: ResearchPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid, WRITE)
    if p.status not in ("planning", "needs_review"):
        raise HTTPException(409, "Research can only be edited before it starts")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    audit(db, p.workspace_id, user.id, "RESEARCH_UPDATED", "research", p.id)
    db.commit()
    return out(p)


@router.delete("/{rid}", status_code=204)
def delete(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid)
    m = membership(db, user, p.workspace_id)
    if m.role not in ADMIN and p.owner_id != user.id:
        raise HTTPException(403, "Only admins or the project owner can delete research")
    audit(db, p.workspace_id, user.id, "RESEARCH_DELETED", "research", p.id, {"title": p.title})
    db.delete(p)
    db.commit()
