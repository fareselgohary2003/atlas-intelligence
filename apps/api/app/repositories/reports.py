"""SQLAlchemy adapters for reports, report inputs and LLM usage."""
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.evidence.domain import DuplicateError, VerificationRecord
from app.models import CostRecord, Report, ReportSection, ResearchProject, ResearchTask, VerificationResult
from app.reporting.builder import ReportInputs
from app.reporting.service import ReportRecord
from app.repositories.evidence import _rec, _uid

LIMIT = 5000  # MVP cap per collection when building a report


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


class SqlReportRepository:
    def __init__(self, session_factory):
        self.sf = session_factory

    def add_report(self, rec: ReportRecord, audit_hook=None) -> None:
        head = {k: v for k, v in rec.content.items() if k != "sections"}
        with self.sf() as db:
            try:
                db.add(Report(id=_uid(rec.id), research_id=_uid(rec.research_id), workspace_id=_uid(rec.workspace_id), version=rec.version,
                              title=rec.title, is_demo=rec.is_demo, content=head))
                db.flush()
            except IntegrityError as e:
                db.rollback()
                if "unique" in str(e.orig).lower() or "duplicate key" in str(e.orig).lower():
                    raise DuplicateError() from e
                raise
            for i, s in enumerate(rec.content["sections"]):
                db.add(ReportSection(report_id=_uid(rec.id), research_id=_uid(rec.research_id), workspace_id=_uid(rec.workspace_id),
                                     position=i, key=s["key"], title=s["title"], content=s))
            if audit_hook:
                audit_hook(db, rec)  # audit row commits (or rolls back) together with the report
            db.commit()

    def _load(self, db, row):
        if row is None:
            return None
        secs = db.scalars(select(ReportSection).where(ReportSection.report_id == row.id).order_by(ReportSection.position)).all()
        return ReportRecord(str(row.id), str(row.research_id), str(row.workspace_id), row.version, row.title, row.is_demo,
                            {**row.content, "sections": [s.content for s in secs]}, _aware(row.created_at))

    def latest_report(self, research_id):
        r = _uid(research_id)
        if r is None:
            return None
        with self.sf() as db:
            return self._load(db, db.scalar(select(Report).where(Report.research_id == r).order_by(Report.version.desc()).limit(1)))

    def list_versions(self, research_id):
        r = _uid(research_id)
        if r is None:
            return []
        with self.sf() as db:
            return [{"id": str(x.id), "version": x.version, "title": x.title, "is_demo": x.is_demo, "created_at": _aware(x.created_at).isoformat()}
                    for x in db.scalars(select(Report).where(Report.research_id == r).order_by(Report.version.desc()))]

    def get_report(self, research_id, version):
        r = _uid(research_id)
        if r is None:
            return None
        with self.sf() as db:
            return self._load(db, db.scalar(select(Report).where(Report.research_id == r, Report.version == version)))


class SqlReportInputs:
    def __init__(self, session_factory, evidence_repo):
        self.sf, self.repo = session_factory, evidence_repo

    def research(self, research_id):
        r = _uid(research_id)
        if r is None:
            return None
        with self.sf() as db:
            p = db.get(ResearchProject, r)
            return None if p is None else {"id": str(p.id), "workspace_id": str(p.workspace_id), "title": p.title, "objective": p.objective, "industry": p.industry,
                                           "geography": p.geography, "target_customer": p.target_customer, "time_range": p.time_range, "is_demo": p.is_demo}

    def snapshot(self, research_id, at) -> ReportInputs:
        rid = _uid(research_id)
        with self.sf() as db:  # single query per collection: no per-claim lookups
            latest = {}
            for v in db.scalars(select(VerificationResult).where(VerificationResult.research_id == rid).order_by(VerificationResult.created_at, VerificationResult.id)):
                latest[str(v.claim_id)] = _rec(VerificationRecord, v)
            tasks = [{"key": t.key, "title": t.title, "agent": t.agent, "status": t.status, "error": t.error}
                     for t in db.scalars(select(ResearchTask).where(ResearchTask.research_id == rid).order_by(ResearchTask.created_at, ResearchTask.key))]
        return ReportInputs(self.research(research_id), self.repo.list_claims(research_id, LIMIT), self.repo.list_evidence(research_id, limit=LIMIT),
                            self.repo.list_sources(research_id, LIMIT), latest, self.repo.list_conflicts(research_id), tasks, at,
                            self.repo.list_analysis(research_id))


class SqlUsageRecorder:
    def __init__(self, session_factory):
        self.sf = session_factory

    def record(self, u) -> None:
        with self.sf() as db:
            db.add(CostRecord(id=_uid(u.id), research_id=_uid(u.research_id), workspace_id=_uid(u.workspace_id), task_key=u.task_key, agent=u.agent,
                              provider=u.provider[:40], model=u.model[:80], input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                              estimated_cost=u.estimated_cost, duration_ms=u.duration_ms, ok=u.ok, error_category=u.error_category))
            db.commit()
