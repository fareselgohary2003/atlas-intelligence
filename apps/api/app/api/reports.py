"""Report + usage endpoints. Routes only translate HTTP <-> ReportService; report logic lives in app/reporting."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import WRITE, audit, current_user
from app.api.research import load
from app.core.db import SessionLocal, get_db
from app.evidence.domain import EvidenceError, Scope
from app.models import CostRecord, User
from app.reporting.service import ReportService
from app.repositories.evidence import SqlEvidenceRepository
from app.repositories.reports import SqlReportInputs, SqlReportRepository

router = APIRouter(prefix="/api/research", tags=["reports"])
log = logging.getLogger("atlas.reports")
STATUS = {"not_found": 404, "invalid": 422, "conflict": 409}


def report_service() -> ReportService:
    return ReportService(SqlReportInputs(SessionLocal, SqlEvidenceRepository(SessionLocal)), SqlReportRepository(SessionLocal))


def _fail(e: EvidenceError):
    raise HTTPException(STATUS.get(e.code, 400), e.message)


def _meta(rec):
    return {"id": rec.id, "version": rec.version, "title": rec.title, "is_demo": rec.is_demo, "created_at": rec.created_at.isoformat(), "stats": rec.content["stats"]}


@router.post("/{rid}/report", status_code=201)
def generate(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db), svc: ReportService = Depends(report_service)):
    p = load(db, user, rid, WRITE)
    try:
        rec = svc.generate(Scope(str(p.workspace_id), str(p.id)), audit_hook=lambda s, r: audit(s, p.workspace_id, user.id, "REPORT_GENERATED", "research", p.id, {"version": r.version}))
    except EvidenceError as e:
        _fail(e)
    except ValueError:  # traceability validation failure: a bug, never exposed as report content
        log.exception("report failed validation for research %s", rid)
        raise HTTPException(500, "Report generation failed integrity validation")
    return _meta(rec)


@router.get("/{rid}/report/versions")
def report_versions(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db), svc: ReportService = Depends(report_service)):
    p = load(db, user, rid)
    try:
        return svc.versions(Scope(str(p.workspace_id), str(p.id)))
    except EvidenceError as e:
        _fail(e)


@router.get("/{rid}/report")
def get_report(rid: str, version: int | None = Query(None, ge=1), user: User = Depends(current_user), db: Session = Depends(get_db),
               svc: ReportService = Depends(report_service)):
    p = load(db, user, rid)
    try:
        rec = svc.get(Scope(str(p.workspace_id), str(p.id)), version)
    except EvidenceError as e:
        _fail(e)
    return {**_meta(rec), "content": rec.content}


@router.get("/{rid}/report/export")
def export_report(rid: str, format: str = Query("md"), version: int | None = Query(None, ge=1), user: User = Depends(current_user),
                  db: Session = Depends(get_db), svc: ReportService = Depends(report_service)):
    p = load(db, user, rid)
    try:
        payload, ctype, name = svc.export(Scope(str(p.workspace_id), str(p.id)), format, version)
    except EvidenceError as e:
        _fail(e)
    audit(db, p.workspace_id, user.id, "REPORT_EXPORTED", "research", p.id, {"format": format, "version": version})
    db.commit()
    return Response(payload, media_type=ctype, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{rid}/usage")
def usage(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = load(db, user, rid)
    q = select(CostRecord.agent, func.count(), func.count(CostRecord.input_tokens), func.coalesce(func.sum(CostRecord.input_tokens), 0),
               func.coalesce(func.sum(CostRecord.output_tokens), 0), func.count(CostRecord.estimated_cost), func.sum(CostRecord.estimated_cost),
               func.coalesce(func.sum(CostRecord.duration_ms), 0), func.coalesce(func.sum(case((CostRecord.ok.is_(False), 1), else_=0)), 0)
               ).where(CostRecord.research_id == p.id).group_by(CostRecord.agent).order_by(CostRecord.agent)
    by_agent = [{"agent": a, "calls": n, "calls_with_tokens": nt, "input_tokens": int(i), "output_tokens": int(o), "calls_with_cost": nc,
                 "estimated_cost": None if c is None else round(float(c), 6), "duration_ms": int(d), "failed_calls": int(f)}
                for a, n, nt, i, o, nc, c, d, f in db.execute(q)]
    priced = [r["estimated_cost"] for r in by_agent if r["estimated_cost"] is not None]
    calls = sum(r["calls"] for r in by_agent)
    return {"by_agent": by_agent, "calls": calls, "input_tokens": sum(r["input_tokens"] for r in by_agent), "output_tokens": sum(r["output_tokens"] for r in by_agent),
            "estimated_cost": round(sum(priced), 6) if priced else None,
            "cost_complete": bool(calls) and all(r["calls_with_cost"] == r["calls"] for r in by_agent),  # False => cost covers only priced calls
            "note": "Tokens and cost appear only when the provider reports usage and prices are configured (LLM_PRICE_*)."}
