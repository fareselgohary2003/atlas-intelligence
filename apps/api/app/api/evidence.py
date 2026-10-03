"""Read-only evidence endpoints. Authorization: authenticated user -> workspace membership -> research (via research.load).
Lists use bulk repository reads (one query per collection) and never include full source text."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.research import load
from app.core.db import SessionLocal, get_db
from app.evidence.graph import build_graph
from app.models import User
from app.repositories.evidence import SqlEvidenceRepository

router = APIRouter(prefix="/api/research", tags=["evidence"])


def evidence_repo():
    return SqlEvidenceRepository(SessionLocal)  # dependency so tests can substitute a repository


def _out(rec, drop=()):
    return jsonable_encoder({k: v for k, v in asdict(rec).items() if k not in drop})


def _src_summary(s):
    return {"id": s.id, "title": s.title, "url": s.url, "publisher": s.publisher, "source_type": s.source_type, "domain": s.domain,
            "published_at": s.published_at.isoformat() if s.published_at else None, "retrieved_at": s.retrieved_at.isoformat(), "is_demo": s.is_demo}


@router.get("/{rid}/sources")
def sources(rid: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
            user: User = Depends(current_user), db: Session = Depends(get_db), repo=Depends(evidence_repo)):
    p = load(db, user, rid)
    rows = repo.list_sources(str(p.id), limit, offset)
    usage = repo.source_usage(str(p.id), [s.id for s in rows])
    return [{**_out(s, drop=("content_text",)), "evidence_count": usage[s.id]["evidence"], "claim_count": usage[s.id]["claims"]} for s in rows]


@router.get("/{rid}/evidence")
def evidence(rid: str, claim_id: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
             user: User = Depends(current_user), db: Session = Depends(get_db), repo=Depends(evidence_repo)):
    p = load(db, user, rid)
    rows = repo.list_evidence(str(p.id), claim_id, limit, offset)
    srcs = repo.sources_by_ids(str(p.id), list({e.source_id for e in rows}))  # embedded source summary: no per-row lookups in the UI
    return [{**_out(e), "source": _src_summary(srcs[e.source_id]) if e.source_id in srcs else None} for e in rows]


@router.get("/{rid}/claims")
def claims(rid: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
           user: User = Depends(current_user), db: Session = Depends(get_db), repo=Depends(evidence_repo)):
    p = load(db, user, rid)
    rows = repo.list_claims(str(p.id), limit, offset)
    ids = [c.id for c in rows]
    ver, links = repo.latest_verifications(str(p.id), ids), repo.claim_sources_bulk(str(p.id), ids)  # two queries total, not 2 per claim
    return [{**_out(c), "sources": links.get(c.id, []), "evidence_count": sum(x["evidence_count"] for x in links.get(c.id, [])),
             "verification": None if c.id not in ver else {"outcome": ver[c.id].outcome, "confidence": ver[c.id].confidence, "rationale": ver[c.id].rationale,
                                                          "verifier": ver[c.id].verifier, "factors": ver[c.id].factors, "at": ver[c.id].created_at.isoformat()}} for c in rows]


@router.get("/{rid}/conflicts")
def conflicts(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db), repo=Depends(evidence_repo)):
    p = load(db, user, rid)
    return [_out(c) for c in repo.list_conflicts(str(p.id))]


@router.get("/{rid}/analysis")
def analysis(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db), repo=Depends(evidence_repo)):
    p = load(db, user, rid)
    return [{**_out(a), "label": "UNCERTAINTY" if a.kind == "uncertainty" else "INFERENCE"} for a in repo.list_analysis(str(p.id))]


@router.get("/{rid}/graph")
def graph(rid: str, limit: int = Query(100, ge=1, le=300), user: User = Depends(current_user), db: Session = Depends(get_db), repo=Depends(evidence_repo)):
    p = load(db, user, rid)
    q = str(p.id)
    return build_graph(repo.list_claims(q, 1000), repo.list_evidence(q, limit=5000), repo.list_sources(q, 1000), repo.list_conflicts(q), limit)
