import unittest

from app.evidence.conflicts import classify_pair, stance_conflicts
from app.evidence.domain import can_transition, clean_attributes, EvidenceError
from app.evidence.verification import (assess_stances, cluster_sources, evidence_quality, number_in_text, verify)
from tests.factories import NOW, claim, ev, src


class NoJudge:
    def assess(self, *a):
        raise AssertionError("judge must not be called")


def run(c, pairs, **kw):
    return verify(c, [e for e, _ in pairs], {s.id: s for _, s in pairs}, at=NOW, **kw)


class VerificationTests(unittest.TestCase):
    def test_supported_by_two_independent_sources(self):
        c, s1, s2 = claim(), src("gov.example", "government", 1), src("news.example", "news", 1)
        r = run(c, [(ev(s1, c), s1), (ev(s2, c), s2)])
        self.assertEqual(r.outcome, "supported")
        self.assertIn(r.confidence, ("HIGH", "MEDIUM"))
        self.assertEqual(r.factors["independent_supporting"], 2)
        self.assertAlmostEqual(r.factors["total"], sum(r.factors["weights"][k] * v for k, v in r.factors["components"].items()) / sum(r.factors["weights"].values()), 2)
        self.assertNotIn("I think", r.rationale)

    def test_single_authoritative_direct_source_is_supported_but_capped(self):
        c, s = claim(), src("stats.example", "government", 0.5)
        r = run(c, [(ev(s, c), s)])
        self.assertEqual((r.outcome, r.confidence), ("supported", "MEDIUM"))

    def test_single_weak_source_is_partially_supported(self):
        c, s = claim(), src("blog.example", "forum", 1)
        r = run(c, [(ev(s, c), s)])
        self.assertEqual((r.outcome, r.confidence), ("partially_supported", "LOW"))

    def test_contradicted_and_contested(self):
        c, s1, s2 = claim(), src("a.example", "news"), src("b.example", "news")
        self.assertEqual(run(c, [(ev(s1, c, "contradicts"), s1)]).outcome, "contradicted")
        r = run(c, [(ev(s1, c), s1), (ev(s2, c, "contradicts"), s2)])
        self.assertEqual((r.outcome, r.confidence), ("partially_supported", "LOW"))
        self.assertIn("Contested", r.rationale)

    def test_insufficient_without_calling_the_judge(self):
        c, s = claim(), src()
        self.assertEqual(run(c, [], judge=NoJudge()).outcome, "insufficient_evidence")
        empty = ev(s, c, excerpt="   ")
        r = run(c, [(empty, s)], judge=NoJudge())
        self.assertEqual((r.outcome, r.confidence), ("insufficient_evidence", "UNVERIFIED"))
        self.assertIn("empty_excerpt", r.factors["issues"])

    def test_integrity_violations_are_excluded(self):
        c, s = claim(), src()
        foreign = ev(s, c, rid="OTHER")
        missing = ev(src(), c)
        r = verify(c, [foreign, missing], {s.id: s}, at=NOW)
        self.assertEqual(r.outcome, "insufficient_evidence")
        self.assertEqual(set(r.factors["issues"]), {"evidence_wrong_research", "source_missing"})
        other_rs = src(rid="OTHER")
        r = verify(c, [ev(other_rs, c)], {other_rs.id: other_rs}, at=NOW)
        self.assertIn("source_missing", r.factors["issues"])

    def test_numeric_grounding(self):
        c, s = claim(value=9.9), src("stats.example", "government")
        r = run(c, [(ev(s, c, excerpt="Market size hit USD 2.1 billion in 2024."), s)])
        self.assertEqual(r.outcome, "insufficient_evidence")
        self.assertIn("ungrounded_value", r.factors)
        self.assertTrue(number_in_text(1200000, "revenue of 1,200,000 riyals"))
        self.assertFalse(number_in_text("x", "5"))

    def test_duplicate_sources_count_once(self):
        c, s1, s2 = claim(), src("a.example", "news", h="same"), src("b.example", "news", h="same")
        s3 = src("a.example", "news")  # same publisher domain as s1
        r = run(c, [(ev(s1, c), s1), (ev(s2, c), s2), (ev(s3, c), s3)])
        self.assertEqual(r.factors["independent_supporting"], 1)
        self.assertIn("count once", r.rationale)
        self.assertEqual(len(cluster_sources([(ev(s1, c), s1), (ev(s2, c), s2)])), 1)

    def test_freshness_caps_confidence(self):
        c, s1, s2 = claim(), src("gov.example", "government", 8), src("uni.example", "academic", None)
        r = run(c, [(ev(s1, c), s1), (ev(s2, c), s2)])
        self.assertEqual(r.outcome, "supported")
        self.assertEqual(r.confidence, "LOW")
        self.assertIn("freshness", r.factors)

    def test_judge_can_reclassify_and_bad_judge_output_falls_back(self):
        c, s = claim(), src("gov.example", "government")
        e = ev(s, c)

        class Unrelated:
            def assess(self, *a): return {"verdict": "unrelated"}

        class Garbage:
            def assess(self, *a): return "nonsense"

        class Boom:
            def assess(self, *a): raise RuntimeError("llm down")
        self.assertEqual(run(c, [(e, s)], judge=Unrelated()).outcome, "insufficient_evidence")
        for j in (Garbage(), Boom()):
            r = run(c, [(e, s)], judge=j)
            self.assertEqual(r.outcome, "supported")
            self.assertIn("judge_unavailable_for_some_evidence", r.factors["notes"])
        self.assertEqual(run(c, [(e, s)], judge=Unrelated()).verifier, "rules+judge/1")

    def test_quality_components_are_explained(self):
        s = src("stats.example", "government", 0.5)
        q = evidence_quality(s, "USD 2.1 billion", {"value": 2.1}, True, NOW)
        self.assertEqual(set(q["components"]), {"authority", "recency", "directness", "specificity", "extraction"})
        self.assertTrue(all(v["note"] for v in q["components"].values()))
        self.assertEqual(q["level"], "HIGH")
        self.assertLess(evidence_quality(src("f.example", "forum", None), "opinion", {}, False, NOW)["total"], q["total"])

    def test_state_transitions_and_attribute_cleaning(self):
        self.assertTrue(can_transition("proposed", "supported"))
        self.assertTrue(can_transition("supported", "contradicted"))
        self.assertFalse(can_transition("supported", "proposed"))
        self.assertFalse(can_transition("proposed", "bogus"))
        self.assertEqual(clean_attributes({"value": "1,200", "metric": " m  s ", "junk": 1}), {"metric": "m s", "value": 1200.0})
        for bad in ({"value": "abc"}, {"value": True}, {"pricing_status": "free"}, "x"):
            with self.assertRaises(EvidenceError):
                clean_attributes(bad)


def pair(v1, v2, a1=None, a2=None, h1="h1", h2="h2", metric="market growth"):
    a, b = claim(value=v1, metric=metric, unit="percent", **(a1 or {})), claim(value=v2, metric=metric, unit="percent", **(a2 or {}))
    return classify_pair(a, b, {"hashes": {h1}, "source_id": "sa", "evidence_id": "ea"}, {"hashes": {h2}, "source_id": "sb", "evidence_id": "eb"})


class ConflictTests(unittest.TestCase):
    def test_different_time_period_is_not_a_contradiction(self):
        f = pair(10, 25, {"period": "2024"}, {"period": "2025"})
        self.assertEqual((f.conflict_type, f.severity, f.resolution_status), ("different_time_period", "info", "explained_by_scope"))
        self.assertIn("not a contradiction", f.explanation)

    def test_scope_dimension_differences(self):
        for dim, t in (("geography", "different_geography"), ("definition", "different_definition"),
                       ("methodology", "different_methodology"), ("population", "different_population")):
            f = pair(10, 25, {dim: "x"}, {dim: "y"})
            self.assertEqual((f.conflict_type, f.resolution_status), (t, "explained_by_scope"), dim)
        f = pair(18, 21, {"geography": "Saudi Arabia"}, {"geography": "GCC"})
        self.assertNotEqual(f.conflict_type, "direct_contradiction")

    def test_numerical_disagreement_with_matching_scope(self):
        f = pair(18, 21, {"period": "2022-2025", "geography": "KSA"}, {"period": "2022-2025", "geography": "KSA"})
        self.assertEqual((f.conflict_type, f.severity, f.resolution_status), ("numerical_disagreement", "medium", "unresolved"))  # 14% gap >= 10% => medium
        self.assertIn("between 18 and 21", f.explanation)

    def test_direct_contradiction_needs_same_stated_scope_and_large_gap(self):
        same = {"period": "2024", "geography": "KSA"}
        f = pair(10, 40, same, dict(same))
        self.assertEqual((f.conflict_type, f.severity), ("direct_contradiction", "high"))
        g = pair(10, 40)  # scope not stated: cannot rule out a scope difference
        self.assertEqual((g.conflict_type, g.resolution_status), ("numerical_disagreement", "needs_review"))

    def test_agreement_and_incomparable_claims_yield_nothing(self):
        self.assertIsNone(pair(20, 20.1))
        self.assertIsNone(classify_pair(claim(value=1, metric="a"), claim(value=9, metric="b"), {}, {}))
        self.assertIsNone(classify_pair(claim(value=1, unit="usd"), claim(value=9, unit="sar"), {}, {}))
        self.assertIsNone(classify_pair(claim(value=None), claim(value=9), {}, {}))

    def test_duplicate_or_derived_source_takes_precedence(self):
        f = pair(10, 40, {"period": "2024"}, {"period": "2025"}, h1="same", h2="same")
        self.assertEqual(f.conflict_type, "duplicate_or_derived_source")

    def test_key_is_deterministic_and_order_independent(self):
        a, b = claim(value=1, cid="a"), claim(value=9, cid="b")
        pa, pb = {"hashes": {"x"}}, {"hashes": {"y"}}
        self.assertEqual(classify_pair(a, b, pa, pb).key, classify_pair(b, a, pb, pa).key)

    def test_stance_conflict_between_independent_sources(self):
        c, s1, s2, s3 = claim(), src("a.example"), src("b.example"), src("c.example")
        st, _, _ = assess_stances(c, [ev(s1, c), ev(s2, c, "contradicts")], {s.id: s for s in (s1, s2)})
        f = stance_conflicts(c, st)
        self.assertEqual((f[0].conflict_type, f[0].source_a_id, f[0].source_b_id), ("direct_contradiction", s1.id, s2.id))
        same_pub = src("a.example")  # same publisher on both sides: internally inconsistent, not an independent dispute
        st, _, _ = assess_stances(c, [ev(s1, c), ev(same_pub, c, "contradicts")], {s1.id: s1, same_pub.id: same_pub})
        self.assertEqual(stance_conflicts(c, st), [])
        st, _, _ = assess_stances(c, [ev(s1, c), ev(s2, c), ev(s3, c, "contradicts")], {s.id: s for s in (s1, s2, s3)})
        self.assertIn("2 independent source(s) support and 1 contradict", stance_conflicts(c, st)[0].explanation)


if __name__ == "__main__":
    unittest.main()
