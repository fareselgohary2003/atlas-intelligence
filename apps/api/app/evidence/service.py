"""EvidenceService: the only write path for sources, evidence, claims, verifications and conflicts.
Enforces scope ownership, provenance, grounding, idempotency and append-only history over any EvidenceRepository."""
from app.evidence.conflicts import classify_pair, stance_conflicts
from app.evidence.domain import (ANALYSIS_KINDS, CLAIM_TYPES, AnalysisRecord, STANCES, ClaimRecord, ConflictRecord, DuplicateError, EvidenceError,
                                 EvidenceRecord, Scope, SourceRecord, VerificationRecord, can_transition,
                                 clean_attributes, digest, new_id, norm_text, now)
from app.evidence.verification import assess_stances, evidence_quality, numbers_in, verify_stanced

MAX_CONTENT = 200_000
NOT_FOUND = "{} not found in this research"  # identical for missing and foreign ids: no existence oracle


def locate(content: str, excerpt: str):
    hay, needle = " ".join(content.split()), " ".join(excerpt.split())
    i = hay.lower().find(needle.lower())
    return None if i < 0 else {"start": i, "end": i + len(needle), "basis": "whitespace_normalized_text"}


class EvidenceService:
    def __init__(self, repo, *, force_demo=False, judge=None, clock=now):
        self.repo, self.force_demo, self.judge, self.clock = repo, force_demo, judge, clock

    def _demo(self, scope: Scope) -> bool:
        rc = self.repo.research_context(scope.research_id)
        if rc is None or str(rc["workspace_id"]) != str(scope.workspace_id):
            raise EvidenceError("not_found", "Research not found in this workspace")
        return scope.is_demo or rc["is_demo"] or self.force_demo

    def _find_source(self, rid, cand):
        hit = self.repo.find_source_by_urls(rid, [cand.url, cand.canonical_url])
        if hit:
            return hit, "canonical_url" if hit.canonical_url == cand.canonical_url else "url"
        hit = self.repo.find_source_by_hash(rid, cand.content_hash)
        return (hit, "content_hash") if hit else (None, None)

    def _alias(self, scope, hit, cand, via):
        known = {hit.url, hit.canonical_url, *(a.get("url") for a in hit.aliases)}
        if cand.url not in known:  # history is appended, never overwritten
            self.repo.append_alias(scope.research_id, hit.id, {"url": cand.url, "canonical_url": cand.canonical_url, "via": via,
                                                               "seen_at": self.clock().isoformat(), "task_id": scope.task_id, "agent": scope.agent})

    def save_source(self, scope: Scope, cand, content_text: str):
        """cand: SourceCandidate. Returns (SourceRecord, created, duplicate_via)."""
        demo, rid = self._demo(scope), scope.research_id
        hit, via = self._find_source(rid, cand)
        if hit:
            self._alias(scope, hit, cand, via)
            return hit, False, via
        rec = SourceRecord(new_id(), rid, scope.workspace_id, cand.url, cand.canonical_url, cand.domain, cand.title, cand.publisher,
                           cand.published_at, cand.retrieved_at, cand.source_type, cand.content_hash, content_text[:MAX_CONTENT],
                           dict(cand.metadata), [], demo or cand.is_demo or cand.domain.endswith(".invalid"), self.clock())
        try:
            self.repo.add_source(rec)
        except DuplicateError:  # lost a race with a concurrent worker: return the winner
            hit, via = self._find_source(rid, cand)
            if hit is None:
                raise
            return hit, False, via
        return rec, True, None

    def create_claim(self, scope: Scope, text: str, claim_type: str, attributes=None):
        demo, rid = self._demo(scope), scope.research_id
        text = " ".join(str(text).split())
        if not 10 <= len(text) <= 500:
            raise EvidenceError("invalid", "Claim text must be 10-500 characters")
        if claim_type not in CLAIM_TYPES:
            raise EvidenceError("invalid", "Unknown claim_type")
        attrs = clean_attributes(attributes)
        key = digest(rid, norm_text(text), claim_type)
        hit = self.repo.get_claim_by_key(rid, key)
        if hit:
            return hit, False
        t = self.clock()
        rec = ClaimRecord(new_id(), rid, scope.workspace_id, text, claim_type, "proposed", "UNVERIFIED", attrs,
                          scope.agent, scope.task_id, key, demo, t, t)  # born unverified: generation != verification
        try:
            self.repo.add_claim(rec)
        except DuplicateError:
            return self.repo.get_claim_by_key(rid, key), False
        return rec, True

    def create_evidence(self, scope: Scope, source_id: str, excerpt: str, claim_id=None, stance="supports", meta=None):
        demo, rid = self._demo(scope), scope.research_id
        excerpt = " ".join(str(excerpt).split())
        if not 10 <= len(excerpt) <= 1000:
            raise EvidenceError("invalid", "Excerpt must be 10-1000 characters")
        if stance not in STANCES:
            raise EvidenceError("invalid", "Unknown stance")
        src = self.repo.get_source(rid, source_id)
        if src is None:
            raise EvidenceError("not_found", NOT_FOUND.format("Source"))
        claim = None
        if claim_id is not None:
            claim = self.repo.get_claim(rid, claim_id)
            if claim is None:
                raise EvidenceError("not_found", NOT_FOUND.format("Claim"))
        if src.content_text:
            loc = locate(src.content_text, excerpt)
            if loc is None:
                raise EvidenceError("ungrounded", "Excerpt does not appear in the source text")
            grounded = True
        else:
            loc, grounded = {"basis": "unverified"}, False
        key = digest(rid, src.id, norm_text(excerpt), claim_id or "")
        hit = self.repo.get_evidence_by_key(rid, key)
        if hit:
            return hit, False
        rec = EvidenceRecord(new_id(), rid, scope.workspace_id, src.id, claim_id, scope.task_id, scope.agent, excerpt, loc, stance,
                             evidence_quality(src, excerpt, claim.attributes if claim else {}, grounded, self.clock()),
                             dict(meta or {}), key, demo or src.is_demo, self.clock())
        try:
            self.repo.add_evidence(rec)
        except DuplicateError:
            return self.repo.get_evidence_by_key(rid, key), False
        return rec, True

    def _prov(self, rid, claim_id):
        evs = [e for e in self.repo.list_evidence(rid, claim_id=claim_id, limit=200) if e.stance == "supports"]
        srcs = [self.repo.get_source(rid, e.source_id) for e in evs]
        srcs = [s for s in srcs if s]
        return {"hashes": {s.content_hash for s in srcs}, "source_id": srcs[0].id if srcs else None,
                "evidence_id": evs[0].id if evs else None}

    def _persist_conflict(self, scope, demo, f):
        if self.repo.get_conflict_by_key(scope.research_id, f.key):
            return
        rec = ConflictRecord(new_id(), scope.research_id, scope.workspace_id, f.claim_id, f.other_claim_id, f.source_a_id,
                             f.source_b_id, f.evidence_a_id, f.evidence_b_id, f.conflict_type, f.severity, "detected",
                             f.resolution_status, f.explanation, f.dimensions, f.key, demo, self.clock())
        try:
            self.repo.add_conflict(rec)
        except DuplicateError:
            pass

    def verify_claim(self, scope: Scope, claim_id: str) -> VerificationRecord:
        demo, rid = self._demo(scope), scope.research_id
        claim = self.repo.get_claim(rid, claim_id)
        if claim is None:
            raise EvidenceError("not_found", NOT_FOUND.format("Claim"))
        evidence = self.repo.list_evidence(rid, claim_id=claim_id, limit=500)
        sources = {}
        for e in evidence:
            s = self.repo.get_source(rid, e.source_id)
            if s:
                sources[s.id] = s
        stanced, issues, notes = assess_stances(claim, evidence, sources, self.judge)  # judge runs at most once per evidence
        findings = stance_conflicts(claim, stanced)
        if claim.attributes.get("metric") and "value" in claim.attributes:
            mine = self._prov(rid, claim.id)
            for other in self.repo.list_claims(rid, limit=1000):
                if other.id != claim.id and other.attributes.get("metric"):
                    f = classify_pair(claim, other, mine, self._prov(rid, other.id))
                    if f:
                        findings.append(f)
        for f in findings:
            self._persist_conflict(scope, demo, f)
        out = verify_stanced(claim, stanced, issues, notes, at=self.clock(), verifier="rules+judge/1" if self.judge else "rules/1",
                             open_conflicts=self.repo.list_conflicts(rid, claim_id=claim.id))
        rec = VerificationRecord(new_id(), rid, scope.workspace_id, claim.id, out.outcome, out.confidence, out.rationale,
                                 out.evidence_ids, out.factors, out.verifier, demo or claim.is_demo, self.clock())
        self.repo.add_verification(rec)  # append-only history
        if can_transition(claim.status, out.outcome):
            self.repo.set_claim_status(rid, claim.id, out.outcome, out.confidence, self.clock())
        return rec

    def list_claims(self, scope: Scope, statuses=None, limit=200):
        self._demo(scope)
        rows = self.repo.list_claims(scope.research_id, limit=1000)
        return [c for c in rows if not statuses or c.status in statuses][:limit]

    def list_conflicts(self, scope: Scope):
        self._demo(scope)
        return self.repo.list_conflicts(scope.research_id)

    def save_analysis(self, scope: Scope, kind: str, text: str, basis_claim_ids: list):
        """Stores an inference. Guards: cites 1-8 existing claims of this research that are supported/partially_supported, and every figure
        in the text must already appear in a cited claim (text or value attribute): the analyst cannot introduce statistics."""
        demo, rid = self._demo(scope), scope.research_id
        if kind not in ANALYSIS_KINDS:
            raise EvidenceError("invalid", "Unknown analysis kind")
        text = " ".join(str(text).split())
        if not 20 <= len(text) <= 700:
            raise EvidenceError("invalid", "Analysis text must be 20-700 characters")
        ids = list(dict.fromkeys(str(i) for i in basis_claim_ids))
        if not 1 <= len(ids) <= 8:
            raise EvidenceError("invalid", "Analysis must cite between 1 and 8 claims")
        allowed = []
        for cid in ids:
            c = self.repo.get_claim(rid, cid)
            if c is None:
                raise EvidenceError("not_found", NOT_FOUND.format("Claim"))
            if c.status not in ("supported", "partially_supported"):
                raise EvidenceError("invalid", "Analysis may only cite verified or partially verified claims")
            allowed += numbers_in(c.text)
            if isinstance(c.attributes.get("value"), (int, float)):
                allowed.append(float(c.attributes["value"]))
        if any(not any(abs(n - a) <= 1e-9 * max(1.0, abs(a)) for a in allowed) for n in numbers_in(text)):
            raise EvidenceError("invalid", "Analysis introduces figures that are not in the cited claims")
        key = digest(rid, kind, norm_text(text))
        hit = self.repo.get_analysis_by_key(rid, key)
        if hit:
            return hit, False
        rec = AnalysisRecord(new_id(), rid, scope.workspace_id, kind, text, ids, scope.agent, scope.task_id, key, demo, self.clock())
        try:
            self.repo.add_analysis(rec)
        except DuplicateError:
            return self.repo.get_analysis_by_key(rid, key), False
        return rec, True

    def list_analysis(self, scope: Scope):
        self._demo(scope)
        return self.repo.list_analysis(scope.research_id)
