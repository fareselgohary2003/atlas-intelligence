"""SQLAlchemy EvidenceRepository. Records map 1:1 to columns (same field names), so conversion is generic.
Every query filters by research_id; malformed ids are treated as 'not found'."""
import uuid
from dataclasses import fields
from datetime import timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.evidence.domain import (AnalysisRecord, ClaimRecord, ConflictRecord, DuplicateError, EvidenceRecord, SourceRecord, VerificationRecord)
from app.models import Analysis, Claim, ClaimSource, Conflict, Evidence, ResearchProject, Source, VerificationResult

UUID_FIELDS = {"id", "research_id", "workspace_id", "source_id", "claim_id", "other_claim_id", "source_a_id", "source_b_id",
               "evidence_a_id", "evidence_b_id"}


def _uid(v):
    try:
        return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))
    except (ValueError, AttributeError, TypeError):
        return None


def _row(model, rec):
    return model(**{f.name: (_uid(getattr(rec, f.name)) if f.name in UUID_FIELDS and getattr(rec, f.name) is not None else getattr(rec, f.name))
                    for f in fields(rec)})


def _rec(cls, row):
    out = {}
    for f in fields(cls):
        v = getattr(row, f.name)
        if f.name in UUID_FIELDS and v is not None:
            v = str(v)
        elif hasattr(v, "tzinfo") and v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes
        out[f.name] = v
    return cls(**out)


def _is_unique(e: IntegrityError) -> bool:
    m = str(e.orig).lower()
    return "unique" in m or "duplicate key" in m


class SqlEvidenceRepository:
    def __init__(self, session_factory):
        self.sf = session_factory

    def _insert(self, db, row):
        try:
            db.add(row)
            db.flush()
        except IntegrityError as e:
            db.rollback()
            if _is_unique(e):
                raise DuplicateError() from e
            raise

    def _one(self, model, cls, rid, *where):
        r = _uid(rid)
        if r is None:
            return None
        with self.sf() as db:
            row = db.scalar(select(model).where(model.research_id == r, *where).limit(1))
            return _rec(cls, row) if row else None

    def _list(self, model, cls, rid, *where, limit=100, offset=0, order=None):
        r = _uid(rid)
        if r is None:
            return []
        with self.sf() as db:
            q = select(model).where(model.research_id == r, *where).order_by(order if order is not None else model.created_at, model.id)
            return [_rec(cls, x) for x in db.scalars(q.limit(limit).offset(offset))]

    def research_context(self, research_id):
        r = _uid(research_id)
        if r is None:
            return None
        with self.sf() as db:
            p = db.get(ResearchProject, r)
            return None if p is None else {"workspace_id": str(p.workspace_id), "is_demo": p.is_demo}

    # sources
    def find_source_by_urls(self, rid, urls):
        return self._one(Source, SourceRecord, rid, or_(Source.url.in_(urls), Source.canonical_url.in_(urls)))

    def find_source_by_hash(self, rid, h):
        return self._one(Source, SourceRecord, rid, Source.content_hash == h)

    def add_source(self, s):
        with self.sf() as db:
            self._insert(db, _row(Source, s))
            db.commit()

    def append_alias(self, rid, sid, alias):
        r, s = _uid(rid), _uid(sid)
        with self.sf() as db:
            row = db.scalar(select(Source).where(Source.id == s, Source.research_id == r)) if r and s else None
            if row is not None:
                row.aliases = [*row.aliases, alias]  # reassign so the JSON change is detected
                db.commit()

    def get_source(self, rid, sid):
        s = _uid(sid)
        return None if s is None else self._one(Source, SourceRecord, rid, Source.id == s)

    def list_sources(self, rid, limit=100, offset=0):
        return self._list(Source, SourceRecord, rid, limit=limit, offset=offset)

    # claims
    def get_claim_by_key(self, rid, key):
        return self._one(Claim, ClaimRecord, rid, Claim.idempotency_key == key)

    def add_claim(self, c):
        with self.sf() as db:
            self._insert(db, _row(Claim, c))
            db.commit()

    def get_claim(self, rid, cid):
        c = _uid(cid)
        return None if c is None else self._one(Claim, ClaimRecord, rid, Claim.id == c)

    def set_claim_status(self, rid, cid, status, confidence, at):
        with self.sf() as db:
            db.execute(update(Claim).where(Claim.id == _uid(cid), Claim.research_id == _uid(rid))
                       .values(status=status, confidence=confidence, updated_at=at))
            db.commit()

    def list_claims(self, rid, limit=100, offset=0):
        return self._list(Claim, ClaimRecord, rid, limit=limit, offset=offset)

    # evidence (+ claim<->source link in the same transaction)
    def get_evidence_by_key(self, rid, key):
        return self._one(Evidence, EvidenceRecord, rid, Evidence.idempotency_key == key)

    def add_evidence(self, e):
        with self.sf() as db:
            self._insert(db, _row(Evidence, e))
            if e.claim_id:
                link = db.scalar(select(ClaimSource).where(ClaimSource.claim_id == _uid(e.claim_id), ClaimSource.source_id == _uid(e.source_id),
                                                           ClaimSource.stance == e.stance))
                if link:
                    link.evidence_count += 1
                else:
                    db.add(ClaimSource(research_id=_uid(e.research_id), workspace_id=_uid(e.workspace_id), claim_id=_uid(e.claim_id),
                                       source_id=_uid(e.source_id), stance=e.stance, evidence_count=1))
            db.commit()

    def get_evidence(self, rid, eid):
        e = _uid(eid)
        return None if e is None else self._one(Evidence, EvidenceRecord, rid, Evidence.id == e)

    def list_evidence(self, rid, claim_id=None, limit=100, offset=0):
        where = [] if claim_id is None else [Evidence.claim_id == _uid(claim_id)]
        return self._list(Evidence, EvidenceRecord, rid, *where, limit=limit, offset=offset)

    def claim_sources(self, rid, cid):
        r, c = _uid(rid), _uid(cid)
        if r is None or c is None:
            return []
        with self.sf() as db:
            rows = db.scalars(select(ClaimSource).where(ClaimSource.research_id == r, ClaimSource.claim_id == c).order_by(ClaimSource.created_at, ClaimSource.id))
            return [{"source_id": str(x.source_id), "stance": x.stance, "evidence_count": x.evidence_count} for x in rows]

    # verification (append-only)
    def add_verification(self, v):
        with self.sf() as db:
            self._insert(db, _row(VerificationResult, v))
            db.commit()

    def list_verifications(self, rid, cid):
        return self._list(VerificationResult, VerificationRecord, rid, VerificationResult.claim_id == _uid(cid))

    def latest_verification(self, rid, cid):
        vs = self.list_verifications(rid, cid)
        return vs[-1] if vs else None

    # conflicts
    def get_conflict_by_key(self, rid, key):
        return self._one(Conflict, ConflictRecord, rid, Conflict.idempotency_key == key)

    def add_conflict(self, c):
        with self.sf() as db:
            self._insert(db, _row(Conflict, c))
            db.commit()

    def list_conflicts(self, rid, claim_id=None):
        where = [] if claim_id is None else [or_(Conflict.claim_id == _uid(claim_id), Conflict.other_claim_id == _uid(claim_id))]
        return self._list(Conflict, ConflictRecord, rid, *where, limit=1000, order=Conflict.detected_at)

    # analysis (inferences)
    def add_analysis(self, a):
        with self.sf() as db:
            self._insert(db, _row(Analysis, a))
            db.commit()

    def get_analysis_by_key(self, rid, key):
        return self._one(Analysis, AnalysisRecord, rid, Analysis.idempotency_key == key)

    def list_analysis(self, rid):
        return self._list(Analysis, AnalysisRecord, rid, limit=1000)

    # bulk reads: one query per collection instead of one per row
    def latest_verifications(self, rid, claim_ids):
        r, ids = _uid(rid), [i for i in (_uid(c) for c in claim_ids) if i]
        if r is None or not ids:
            return {}
        out = {}
        with self.sf() as db:
            for v in db.scalars(select(VerificationResult).where(VerificationResult.research_id == r, VerificationResult.claim_id.in_(ids))
                                .order_by(VerificationResult.created_at, VerificationResult.id)):
                out[str(v.claim_id)] = _rec(VerificationRecord, v)
        return out

    def claim_sources_bulk(self, rid, claim_ids):
        r, ids = _uid(rid), [i for i in (_uid(c) for c in claim_ids) if i]
        out = {str(i): [] for i in ids}
        if r is None or not ids:
            return out
        with self.sf() as db:
            for x in db.scalars(select(ClaimSource).where(ClaimSource.research_id == r, ClaimSource.claim_id.in_(ids)).order_by(ClaimSource.created_at, ClaimSource.id)):
                out[str(x.claim_id)].append({"source_id": str(x.source_id), "stance": x.stance, "evidence_count": x.evidence_count})
        return out

    def sources_by_ids(self, rid, ids):
        r, u = _uid(rid), [i for i in (_uid(x) for x in ids) if i]
        if r is None or not u:
            return {}
        with self.sf() as db:
            return {str(s.id): _rec(SourceRecord, s) for s in db.scalars(select(Source).where(Source.research_id == r, Source.id.in_(u)))}

    def source_usage(self, rid, ids):
        r, u = _uid(rid), [i for i in (_uid(x) for x in ids) if i]
        out = {str(i): {"evidence": 0, "claims": 0} for i in u}
        if r is None or not u:
            return out
        with self.sf() as db:
            for sid, n, c in db.execute(select(Evidence.source_id, func.count(), func.count(func.distinct(Evidence.claim_id))).where(
                    Evidence.research_id == r, Evidence.source_id.in_(u)).group_by(Evidence.source_id)):
                out[str(sid)] = {"evidence": n, "claims": c}
        return out
