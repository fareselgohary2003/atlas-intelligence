"""Repository-agnostic contract for EvidenceService. Subclass with make_env(); run against MemRepo here and against
SqlEvidenceRepository in tests/integration (unexecuted where sqlalchemy is missing)."""
from datetime import datetime, timezone

from app.evidence.domain import EvidenceError, Scope
from app.evidence.service import EvidenceService
from app.tools.sources import make_candidate
from tests.factories import NOW

TEXT = ("MOCK corpus. The Saudi B2B SaaS market reached USD 2.1 billion in 2024 according to the analyst report. "
        "Growth was 18% per year between 2022 and 2025 under a narrow definition.")
PUB = datetime(2026, 3, 1, tzinfo=timezone.utc)
ATTRS = {"metric": "market size", "value": 2.1, "unit": "usd billion", "period": "2024"}
CLAIM = "The market reached USD 2.1 billion in 2024"


def cand(url="https://example.com/r", text=TEXT, **kw):
    return make_candidate(url=url, text=text, published_at=kw.pop("published_at", PUB), **kw)


class NoJudge:
    called = False

    def assess(self, *a):
        NoJudge.called = True
        raise AssertionError("judge must not be called")


class EvidenceContract:
    def make_env(self):
        """-> (repo, {"A": (workspace_id, research_id), "B": (...), "D": (...) demo research})"""
        raise NotImplementedError

    def setUp(self):
        self.repo, self.env = self.make_env()
        self.svc = EvidenceService(self.repo, clock=lambda: NOW)

    def sc(self, k="A", task="t1", agent="market"):
        w, r = self.env[k]
        return Scope(w, r, task, agent)

    def src_claim(self, k="A", url="https://example.com/r", text=TEXT):
        s, _, _ = self.svc.save_source(self.sc(k), cand(url, text), text)
        c, _ = self.svc.create_claim(self.sc(k), CLAIM, "market_size", ATTRS)
        return s, c

    # ---- sources
    def test_source_persistence_and_normalization(self):
        s, created, via = self.svc.save_source(self.sc(), cand("https://Example.com/r?utm_source=x#f"), TEXT)
        self.assertEqual((created, via, s.url, s.domain, s.content_text, s.is_demo), (True, None, "https://example.com/r", "example.com", TEXT, False))
        got = self.repo.get_source(self.env["A"][1], s.id)
        self.assertEqual((got.id, got.content_hash, got.published_at.year), (s.id, s.content_hash, 2026))

    def test_source_dedup_by_url_canonical_and_hash_keeps_history(self):
        rid = self.env["A"][1]
        s, _, _ = self.svc.save_source(self.sc(), cand(), TEXT)
        s2, created, via = self.svc.save_source(self.sc(), cand("https://example.com/r?utm_campaign=y"), TEXT)
        self.assertEqual((s2.id, created, via), (s.id, False, "canonical_url"))
        amp = cand("https://example.com/r-amp", TEXT + " Different words.", canonical_url="https://example.com/r")
        self.assertEqual(self.svc.save_source(self.sc(), amp, TEXT + " Different words.")[1:], (False, "canonical_url"))
        mirror = cand("https://mirror.example.org/copy", TEXT)
        self.assertEqual(self.svc.save_source(self.sc(), mirror, TEXT)[1:], (False, "content_hash"))
        self.assertEqual(len(self.repo.list_sources(rid)), 1)
        aliases = self.repo.get_source(rid, s.id).aliases
        self.assertEqual({a["via"] for a in aliases}, {"canonical_url", "content_hash"})
        self.assertEqual({a["url"] for a in aliases}, {"https://example.com/r-amp", "https://mirror.example.org/copy"})

    def test_dedup_is_per_research(self):
        a, _, _ = self.svc.save_source(self.sc("A"), cand(), TEXT)
        b, created, _ = self.svc.save_source(self.sc("B"), cand(), TEXT)
        self.assertTrue(created)
        self.assertNotEqual(a.id, b.id)

    def test_scope_must_match_research_workspace(self):
        wa, rb = self.env["A"][0], self.env["B"][1]
        for bad in (Scope(wa, rb), Scope(wa, "00000000-0000-0000-0000-000000000000")):
            with self.assertRaises(EvidenceError) as cm:
                self.svc.save_source(bad, cand(), TEXT)
            self.assertEqual(cm.exception.code, "not_found")

    def test_demo_flags(self):
        self.assertFalse(self.svc.save_source(self.sc("A"), cand(), TEXT)[0].is_demo)
        self.assertTrue(self.svc.save_source(self.sc("D"), cand(), TEXT)[0].is_demo)
        self.assertTrue(self.svc.save_source(self.sc("A"), cand("https://mock.invalid/x", TEXT + " x"), TEXT + " x")[0].is_demo)
        forced = EvidenceService(self.repo, force_demo=True, clock=lambda: NOW)
        self.assertTrue(forced.save_source(self.sc("B"), cand(), TEXT)[0].is_demo)

    # ---- claims
    def test_claim_creation_defaults_and_idempotency(self):
        c, created = self.svc.create_claim(self.sc(), CLAIM, "market_size", {"value": "2.1", "metric": "market size"})
        self.assertEqual((created, c.status, c.confidence, c.created_by_agent, c.task_key, c.attributes["value"]),
                         (True, "proposed", "UNVERIFIED", "market", "t1", 2.1))
        c2, created2 = self.svc.create_claim(self.sc(agent="competitor", task="t9"), "  the MARKET reached usd 2.1 billion   in 2024 ", "market_size")
        self.assertEqual((c2.id, created2, c2.created_by_agent), (c.id, False, "market"))
        self.assertTrue(self.svc.create_claim(self.sc(), CLAIM, "trend")[1])
        self.assertEqual(len(self.repo.list_claims(self.env["A"][1])), 2)

    def test_claim_validation(self):
        for text, ctype, attrs in (("short", "trend", None), (CLAIM, "bogus", None), (CLAIM, "trend", {"value": "abc"}), (CLAIM, "trend", "x")):
            with self.assertRaises(EvidenceError) as cm:
                self.svc.create_claim(self.sc(), text, ctype, attrs)
            self.assertEqual(cm.exception.code, "invalid")

    # ---- evidence
    def test_evidence_provenance_location_quality_and_link(self):
        s, c = self.src_claim()
        e, created = self.svc.create_evidence(self.sc(), s.id, "reached USD 2.1 billion   in 2024", c.id)
        rid, wid = self.env["A"][1], self.env["A"][0]
        self.assertEqual((created, e.agent_id, e.task_key, e.research_id, e.workspace_id, e.source_id, e.claim_id, e.stance),
                         (True, "market", "t1", rid, wid, s.id, c.id, "supports"))
        hay = " ".join(TEXT.split())
        self.assertEqual(hay[e.location["start"]:e.location["end"]].lower(), "reached usd 2.1 billion in 2024")
        self.assertEqual(e.quality["components"]["extraction"]["score"], 1.0)
        self.assertTrue(0 <= e.quality["total"] <= 1 and all(v["note"] for v in e.quality["components"].values()))
        self.assertEqual(self.repo.claim_sources(rid, c.id), [{"source_id": s.id, "stance": "supports", "evidence_count": 1}])
        self.assertEqual(self.repo.get_claim(rid, c.id).status, "proposed")  # evidence creation never verifies a claim

    def test_ungrounded_excerpt_is_rejected(self):
        s, c = self.src_claim()
        with self.assertRaises(EvidenceError) as cm:
            self.svc.create_evidence(self.sc(), s.id, "The market reached USD 9.9 billion in 2024", c.id)
        self.assertEqual(cm.exception.code, "ungrounded")
        self.assertEqual(self.repo.list_evidence(self.env["A"][1]), [])

    def test_evidence_idempotency_and_multiple_excerpts_per_source(self):
        rid = self.env["A"][1]
        s, c = self.src_claim()
        e1, _ = self.svc.create_evidence(self.sc(), s.id, "reached USD 2.1 billion in 2024", c.id)
        e1b, again = self.svc.create_evidence(self.sc(task="t1-retry"), s.id, "REACHED usd 2.1 billion in 2024", c.id)
        self.assertEqual((e1b.id, again), (e1.id, False))
        other, _ = self.svc.create_claim(self.sc(), "Growth was 18% per year", "market_growth")
        self.assertTrue(self.svc.create_evidence(self.sc(), s.id, "reached USD 2.1 billion in 2024", other.id)[1])  # other claim => own record
        self.assertTrue(self.svc.create_evidence(self.sc(), s.id, "Growth was 18% per year", c.id)[1])
        self.assertEqual(len(self.repo.list_evidence(rid, claim_id=c.id)), 2)
        self.assertEqual(self.repo.claim_sources(rid, c.id)[0]["evidence_count"], 2)

    def test_invalid_references_leak_no_existence_information(self):
        sA, cA = self.src_claim("A")
        sB, cB = self.src_claim("B")
        msgs = []
        for src_id, claim_id in ((sB.id, None), ("does-not-exist", None), (sA.id, cB.id), (sA.id, "does-not-exist")):
            with self.assertRaises(EvidenceError) as cm:
                self.svc.create_evidence(self.sc("A"), src_id, "reached USD 2.1 billion in 2024", claim_id)
            self.assertEqual(cm.exception.code, "not_found")
            msgs.append(cm.exception.message)
        self.assertEqual(msgs[0], msgs[1])
        self.assertEqual(msgs[2], msgs[3])
        self.assertEqual(self.repo.list_evidence(self.env["A"][1]), [])

    def test_evidence_field_validation(self):
        s, c = self.src_claim()
        for excerpt, stance in (("short", "supports"), ("reached USD 2.1 billion in 2024", "maybe")):
            with self.assertRaises(EvidenceError) as cm:
                self.svc.create_evidence(self.sc(), s.id, excerpt, c.id, stance)
            self.assertEqual(cm.exception.code, "invalid")

    # ---- verification & conflicts
    def two_sources(self, k="A"):
        s1, _, _ = self.svc.save_source(self.sc(k), cand("https://stats.gov.example/r", TEXT, source_type="government"), TEXT)
        t2 = TEXT + " Trade press summary of the same figures."
        s2, _, _ = self.svc.save_source(self.sc(k), cand("https://news.example/x", t2), t2)
        return s1, s2

    def test_verification_lifecycle_history_and_immutable_evidence(self):
        rid = self.env["A"][1]
        s1, s2 = self.two_sources()
        _, c = self.src_claim()
        for s in (s1, s2):
            self.svc.create_evidence(self.sc(), s.id, "reached USD 2.1 billion in 2024", c.id)
        before = [(e.id, e.excerpt, e.quality) for e in self.repo.list_evidence(rid, claim_id=c.id)]
        v1 = self.svc.verify_claim(self.sc(agent="fact_checker"), c.id)
        self.assertEqual((v1.outcome, v1.verifier), ("supported", "rules/1"))
        self.assertEqual(self.repo.get_claim(rid, c.id).status, "supported")
        self.svc.verify_claim(self.sc(agent="fact_checker"), c.id)
        self.assertEqual(len(self.repo.list_verifications(rid, c.id)), 2)
        self.assertEqual(self.repo.latest_verification(rid, c.id).outcome, "supported")
        self.assertEqual([(e.id, e.excerpt, e.quality) for e in self.repo.list_evidence(rid, claim_id=c.id)], before)
        self.assertEqual(set(v1.evidence_ids), {e[0] for e in before})

    def test_claim_without_evidence_is_insufficient_and_judge_is_not_consulted(self):
        svc = EvidenceService(self.repo, judge=NoJudge(), clock=lambda: NOW)
        c, _ = svc.create_claim(self.sc(), CLAIM, "market_size", ATTRS)
        v = svc.verify_claim(self.sc(), c.id)
        self.assertEqual((v.outcome, v.confidence, NoJudge.called), ("insufficient_evidence", "UNVERIFIED", False))
        self.assertEqual(self.repo.get_claim(self.env["A"][1], c.id).status, "insufficient_evidence")

    def test_conflict_is_classified_persisted_and_idempotent(self):
        rid = self.env["A"][1]
        ta, tb = "Analyst A: growth was 18% per year (narrow definition).", "Analyst B: growth was 21% per year (broad definition)."
        sa, _, _ = self.svc.save_source(self.sc(), cand("https://a.example/g", ta), ta)
        sb, _, _ = self.svc.save_source(self.sc(), cand("https://b.example/g", tb), tb)
        base = {"metric": "market growth", "unit": "percent", "period": "2022-2025", "geography": "Saudi Arabia"}
        ga, _ = self.svc.create_claim(self.sc(), "Market growth was 18% per year", "market_growth", {**base, "value": 18, "definition": "narrow"})
        gb, _ = self.svc.create_claim(self.sc(), "Market growth was 21% per year", "market_growth", {**base, "value": 21, "definition": "broad"})
        self.svc.create_evidence(self.sc(), sa.id, "growth was 18% per year", ga.id)
        self.svc.create_evidence(self.sc(), sb.id, "growth was 21% per year", gb.id)
        self.svc.verify_claim(self.sc(), ga.id)
        found = self.repo.list_conflicts(rid, claim_id=ga.id)
        self.assertEqual([(c.conflict_type, c.severity, c.resolution_status) for c in found], [("different_definition", "info", "explained_by_scope")])
        self.assertEqual({found[0].claim_id, found[0].other_claim_id}, {ga.id, gb.id})
        self.svc.verify_claim(self.sc(), ga.id)
        self.svc.verify_claim(self.sc(), gb.id)
        self.assertEqual(len(self.repo.list_conflicts(rid)), 1)
        self.assertEqual(self.repo.get_claim(rid, ga.id).status, "partially_supported")  # single non-authoritative source

    # ---- security
    def test_verify_and_conflicts_cannot_cross_workspaces(self):
        _, cB = self.src_claim("B")
        with self.assertRaises(EvidenceError) as cm:
            self.svc.verify_claim(self.sc("A"), cB.id)
        self.assertEqual(cm.exception.code, "not_found")
        self.assertEqual(self.repo.list_verifications(self.env["B"][1], cB.id), [])
        self.assertEqual(self.repo.list_conflicts(self.env["A"][1]), [])
