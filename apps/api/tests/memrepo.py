"""In-memory EvidenceRepository TEST DOUBLE. It mirrors the port's contract (scoping, unique keys) and is used only by tests;
the same contract tests run against the SQL repository in tests/integration (unexecuted here)."""
import copy
import functools
import threading

from app.evidence.domain import DuplicateError


def _locked(fn):
    @functools.wraps(fn)
    def w(self, *a, **k):
        with self._lock:
            return fn(self, *a, **k)
    return w


class MemRepo:
    def __init__(self):
        self._lock = threading.RLock()  # engine tasks run in parallel; the double must be atomic like a DB unique index
        self.research, self.sources, self.claims, self.evidence = {}, {}, {}, {}
        self.verifs, self.conflicts, self.links = [], {}, {}

    def register_research(self, rid, wid, is_demo=False):
        self.research[rid] = {"workspace_id": wid, "is_demo": is_demo}

    def research_context(self, rid):
        return dict(self.research[rid]) if rid in self.research else None

    def _own(self, d, rid):
        return [v for v in d.values() if v.research_id == rid]

    def find_source_by_urls(self, rid, urls):
        return next((copy.deepcopy(s) for s in self._own(self.sources, rid) if s.url in urls or s.canonical_url in urls), None)

    def find_source_by_hash(self, rid, h):
        return next((copy.deepcopy(s) for s in self._own(self.sources, rid) if s.content_hash == h), None)

    @_locked
    def add_source(self, s):
        if any(x.canonical_url == s.canonical_url or x.content_hash == s.content_hash for x in self._own(self.sources, s.research_id)):
            raise DuplicateError()
        self.sources[s.id] = copy.deepcopy(s)

    @_locked
    def append_alias(self, rid, sid, alias):
        if sid in self.sources and self.sources[sid].research_id == rid:
            self.sources[sid].aliases.append(alias)

    def get_source(self, rid, sid):
        s = self.sources.get(sid)
        return copy.deepcopy(s) if s and s.research_id == rid else None

    def list_sources(self, rid, limit=100, offset=0):
        return copy.deepcopy(self._own(self.sources, rid)[offset:offset + limit])

    def get_claim_by_key(self, rid, key):
        return next((copy.deepcopy(c) for c in self._own(self.claims, rid) if c.idempotency_key == key), None)

    @_locked
    def add_claim(self, c):
        if self.get_claim_by_key(c.research_id, c.idempotency_key):
            raise DuplicateError()
        self.claims[c.id] = copy.deepcopy(c)

    def get_claim(self, rid, cid):
        c = self.claims.get(cid)
        return copy.deepcopy(c) if c and c.research_id == rid else None

    @_locked
    def set_claim_status(self, rid, cid, status, confidence, at):
        c = self.claims[cid]
        assert c.research_id == rid
        c.status, c.confidence, c.updated_at = status, confidence, at

    def list_claims(self, rid, limit=100, offset=0):
        return copy.deepcopy(self._own(self.claims, rid)[offset:offset + limit])

    def get_evidence_by_key(self, rid, key):
        return next((copy.deepcopy(e) for e in self._own(self.evidence, rid) if e.idempotency_key == key), None)

    @_locked
    def add_evidence(self, e):
        if self.get_evidence_by_key(e.research_id, e.idempotency_key):
            raise DuplicateError()
        s, c = self.sources.get(e.source_id), self.claims.get(e.claim_id) if e.claim_id else None
        assert s and s.research_id == e.research_id and (e.claim_id is None or (c and c.research_id == e.research_id))  # composite-FK analogue
        self.evidence[e.id] = copy.deepcopy(e)
        if e.claim_id:
            k = (e.claim_id, e.source_id, e.stance)
            self.links[k] = self.links.get(k, 0) + 1

    def get_evidence(self, rid, eid):
        e = self.evidence.get(eid)
        return copy.deepcopy(e) if e and e.research_id == rid else None

    def list_evidence(self, rid, claim_id=None, limit=100, offset=0):
        rows = [e for e in self._own(self.evidence, rid) if claim_id is None or e.claim_id == claim_id]
        return copy.deepcopy(rows[offset:offset + limit])

    def claim_sources(self, rid, cid):
        return [{"source_id": s, "stance": st, "evidence_count": n} for (c, s, st), n in self.links.items()
                if c == cid and self.claims[c].research_id == rid]

    @_locked
    def add_verification(self, v):
        self.verifs.append(copy.deepcopy(v))

    def list_verifications(self, rid, cid):
        return copy.deepcopy([v for v in self.verifs if v.research_id == rid and v.claim_id == cid])

    def latest_verification(self, rid, cid):
        vs = self.list_verifications(rid, cid)
        return vs[-1] if vs else None

    def get_conflict_by_key(self, rid, key):
        return next((copy.deepcopy(c) for c in self._own(self.conflicts, rid) if c.idempotency_key == key), None)

    @_locked
    def add_conflict(self, c):
        if self.get_conflict_by_key(c.research_id, c.idempotency_key):
            raise DuplicateError()
        self.conflicts[c.id] = copy.deepcopy(c)

    def latest_verifications(self, rid, claim_ids):
        out = {}
        for v in self.verifs:
            if v.research_id == rid and v.claim_id in claim_ids:
                out[v.claim_id] = copy.deepcopy(v)
        return out

    def claim_sources_bulk(self, rid, claim_ids):
        return {c: self.claim_sources(rid, c) for c in claim_ids if c in self.claims and self.claims[c].research_id == rid}

    def sources_by_ids(self, rid, ids):
        return {i: copy.deepcopy(self.sources[i]) for i in ids if i in self.sources and self.sources[i].research_id == rid}

    def source_usage(self, rid, ids):
        ev = [e for e in self.evidence.values() if e.research_id == rid and e.source_id in ids]
        return {i: {"evidence": sum(e.source_id == i for e in ev), "claims": len({e.claim_id for e in ev if e.source_id == i and e.claim_id})} for i in ids}

    @_locked
    def add_analysis(self, a):
        if self.get_analysis_by_key(a.research_id, a.idempotency_key):
            raise DuplicateError()
        self.analysis = getattr(self, "analysis", {})
        self.analysis[a.id] = copy.deepcopy(a)

    def get_analysis_by_key(self, rid, key):
        return next((copy.deepcopy(a) for a in getattr(self, "analysis", {}).values() if a.research_id == rid and a.idempotency_key == key), None)

    def list_analysis(self, rid):
        return copy.deepcopy([a for a in getattr(self, "analysis", {}).values() if a.research_id == rid])

    def list_conflicts(self, rid, claim_id=None):
        return copy.deepcopy([c for c in self._own(self.conflicts, rid)
                              if claim_id is None or claim_id in (c.claim_id, c.other_claim_id)])
