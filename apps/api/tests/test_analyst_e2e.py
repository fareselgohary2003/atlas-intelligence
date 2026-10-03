import json
import unittest

from app.agents.analyst import AnalystAgent, parse_items
from app.agents.graph import Engine
from app.agents.manager import ResearchManager
from app.agents.state import ConfigError, LLMOutputError, ResearchState, Task
from app.demo.llm import DemoLLM, FINDINGS
from app.demo.provider import PAGES
from app.evidence.domain import EvidenceError, Scope
from app.observability.usage import PriceTable
from app.reporting.builder import DEMO_BANNER, build_report, validate_report
from app.reporting.export import to_json, to_markdown, to_pdf
from app.services.llm_selection import make_llm_factory
from app.tools.base import ToolContext
from tests.factories import NOW
from tests.test_agents import FindingsLLM, Stack
from tests.test_factchecker import ALL, Scripted
from tests.test_reporting import MemInputs

ALL9 = ALL + (AnalystAgent,)
GOAL = "Analyze the opportunity for launching a B2B SaaS product in Saudi Arabia."


class Rec:
    def __init__(self):
        self.rows = []

    def record(self, r):
        self.rows.append(r)


def pipeline(recorder=None):
    s = Stack(DemoLLM(), agents=ALL9)
    runners = s.agents.runners(lambda: DemoLLM(), s.fu, recorder=recorder, prices=PriceTable()) if recorder else s.runners
    st = ResearchState("rA", "wA", GOAL)
    m = ResearchManager(DemoLLM(), agents=s.agents.names())
    m.plan(st)
    Engine(st, runners, m, max_replans=2).run()
    return s, st


def tasks_of(st):
    return [{"key": t.id, "title": t.title, "agent": t.agent, "status": t.status.value, "error": t.error} for t in st.tasks.values()]


class DemoLLMTests(unittest.TestCase):
    def test_only_emits_findings_for_the_fictional_mock_pages(self):
        llm = DemoLLM()
        sys_prompt = 'You extract evidence from ONE source: "claim_type":"<market_size|market_growth|risk>"'
        sys_prompt = "from ONE source " + sys_prompt
        for url in ("https://example.com/real-page", "https://www.gov.sa/x", "http://10.0.0.1/", ""):
            self.assertEqual(llm.structured_output(sys_prompt, json.dumps({"source_url": url})), {"findings": []})
        self.assertTrue(all(u.endswith(tuple("abcdefghijklmnopqrstuvwxyz0123456789-")) and ".mock.invalid/" in u for u in FINDINGS))
        self.assertTrue(set(FINDINGS) <= set(PAGES))

    def test_extraction_respects_the_agent_s_allowed_claim_types(self):
        url = next(u for u in FINDINGS if "acme" in u)
        out = DemoLLM().structured_output('from ONE source "claim_type":"<pricing>"', json.dumps({"source_url": url}))
        self.assertEqual([f["claim_type"] for f in out["findings"]], ["pricing"])

    def test_plan_only_for_registered_agents_and_unknown_prompts_fail(self):
        plan = DemoLLM().structured_output("You are the research planning agent ... one of: market, risk>", "goal")
        self.assertEqual({t["agent"] for t in plan["tasks"]}, {"market", "risk"})
        with self.assertRaises(LLMOutputError):
            DemoLLM().structured_output("something else entirely", "x")

    def test_excerpts_are_verbatim_mock_sentences(self):
        for url, fs in FINDINGS.items():
            for f in fs:
                self.assertIn(f["excerpt"], PAGES[url][2])

    def test_demo_llm_cannot_be_selected_without_demo_mode(self):
        with self.assertRaises(ConfigError):
            make_llm_factory({"LLM_PROVIDER": "demo"})()
        self.assertIsInstance(make_llm_factory({"LLM_PROVIDER": "demo", "DEMO_MODE": "true"})(), DemoLLM)
        with self.assertRaises(ConfigError):
            make_llm_factory({})()  # no key: loud failure, never a silent demo fallback
        self.assertEqual(make_llm_factory({"LLM_API_KEY": "k"})().model, "gpt-4o-mini")


class AnalysisServiceTests(unittest.TestCase):
    def setUp(self):
        self.s = Stack(FindingsLLM(), agents=ALL9)
        self.sc = Scope("wA", "rA", "t1", "analyst")
        self.claims = {}
        for name, text, status in (("ok", "Growth was 18% between 2022 and 2025", "supported"), ("part", "Customers prefer annual contracts", "partially_supported"),
                                   ("prop", "An unverified proposition about pricing", "proposed")):
            c, _ = self.s.svc.create_claim(Scope("wA", "rA", "t0", "market"), text, "trend")
            if status != "proposed":
                self.s.repo.set_claim_status("rA", c.id, status, "LOW", NOW)
            self.claims[name] = c

    def save(self, text, ids, kind="opportunity", scope=None):
        return self.s.svc.save_analysis(scope or self.sc, kind, text, ids)

    def test_accepts_inferences_that_only_reuse_figures_from_cited_claims(self):
        rec, created = self.save("Inference: growth of 18% between 2022 and 2025 may indicate room for new entrants.", [self.claims["ok"].id])
        self.assertTrue(created)
        self.assertEqual((rec.kind, rec.agent_id, rec.basis_claim_ids), ("opportunity", "analyst", [self.claims["ok"].id]))
        again, created2 = self.save("inference:  GROWTH of 18% between 2022 and 2025 may indicate room for new entrants.", [self.claims["ok"].id])
        self.assertEqual((again.id, created2), (rec.id, False))

    def test_rejects_invented_figures_unverified_or_foreign_claims_and_bad_shapes(self):
        cases = [("Inference: the market will reach 50% growth by 2030 according to trends.", [self.claims["ok"].id], "invalid"),
                 ("Inference: customers may prefer annual contracts in the next 3 years.", [self.claims["part"].id], "invalid"),
                 ("Inference: an unverified proposition should drive strategy decisions.", [self.claims["prop"].id], "invalid"),
                 ("Inference: a claim that does not exist should not be citable here.", ["nope"], "not_found"),
                 ("too short", [self.claims["ok"].id], "invalid"), ("Inference: valid text without any basis claims cited at all here.", [], "invalid"),
                 ("Inference: a long enough text citing too many claims to be acceptable.", [self.claims["ok"].id] + [f"x{i}" for i in range(9)], "invalid")]
        for text, ids, code in cases:
            with self.assertRaises(EvidenceError, msg=text) as cm:
                self.save(text, ids)
            self.assertEqual(cm.exception.code, code, text)
        with self.assertRaises(EvidenceError):
            self.save("Inference: a perfectly fine sentence without any numbers at all.", [self.claims["ok"].id], kind="prophecy")
        self.assertEqual(self.s.repo.list_analysis("rA"), [])

    def test_cross_research_claims_cannot_be_cited(self):
        other, _ = self.s.svc.create_claim(Scope("wB", "rB", "t", "market"), "Growth was 18% in another workspace research", "trend")
        self.s.repo.set_claim_status("rB", other.id, "supported", "HIGH", NOW)
        with self.assertRaises(EvidenceError) as cm:
            self.save("Inference: growth of 18% might matter for this research as well.", [other.id])
        self.assertEqual(cm.exception.code, "not_found")

    def test_tool_permissions(self):
        t = self.s.tools
        analyst, market = ToolContext("analyst", "a", "rA", "wA"), ToolContext("market", "t", "rA", "wA")
        args = {"kind": "opportunity", "text": "Inference: growth of 18% between 2022 and 2025 may indicate room.", "basis_claim_ids": [self.claims["ok"].id]}
        self.assertEqual(t.execute("save_analysis", args, market).error_category, "unauthorized")
        self.assertTrue(t.execute("save_analysis", args, analyst).ok)
        for tool in ("create_claim", "create_evidence", "save_source", "verify_claim"):
            self.assertEqual(t.execute(tool, {}, analyst).error_category, "unauthorized", tool)

    def test_agent_handles_empty_malformed_and_partially_invalid_llm_output(self):
        st = ResearchState("rZ", "wZ", "g")
        s2 = Stack(FindingsLLM(), agents=ALL9)
        s2.repo.register_research("rZ", "wZ")
        res = s2.runners["analyst"](st, Task("analyze", "x", "analyst"))
        self.assertEqual((res["status"], res["metadata"]["saved"]), ("insufficient", 0))  # no claims: the LLM is never consulted
        ok = self.claims["ok"].id

        class Bad:
            def structured_output(self, s, u): return {"nonsense": True}
        runner = self.s.agents.runners(lambda: Bad(), self.s.fu)["analyst"]
        with self.assertRaises(LLMOutputError):
            runner(ResearchState("rA", "wA", "g"), Task("analyze", "x", "analyst"))

        class Mixed:
            def structured_output(self, s, u):
                return {"items": [{"kind": "opportunity", "text": "Inference: growth of 18% between 2022 and 2025 may matter.", "basis_claim_ids": [ok]},
                                  {"kind": "opportunity", "text": "Inference: growth will reach 99% soon according to nobody.", "basis_claim_ids": [ok]},
                                  {"kind": "bogus", "text": "x", "basis_claim_ids": [ok]}, "garbage"]}
        res = self.s.agents.runners(lambda: Mixed(), self.s.fu)["analyst"](ResearchState("rA", "wA", "g"), Task("analyze", "x", "analyst"))
        self.assertEqual((res["metadata"]["saved"], res["metadata"]["invalid_items"], len(res["metadata"]["rejected"])), (1, 2, 1))
        self.assertIn("introduces figures", res["metadata"]["rejected"][0])
        self.assertEqual(parse_items({"items": []}), ([], 0))

    def test_report_omits_an_inference_whose_basis_has_no_evidence_backed_finding(self):
        rec, _ = self.save("Inference: growth of 18% between 2022 and 2025 may indicate room for entrants.", [self.claims["ok"].id])  # claim has no evidence
        rep = build_report(MemInputs(self.s.repo).snapshot("rA", NOW))
        sec = {x["key"]: x for x in rep["sections"]}
        self.assertEqual(sec["opportunities"]["analysis"], [])
        self.assertIn("Analysis item omitted", " ".join(p["text"] for p in sec["gaps"]["paragraphs"]))
        self.assertEqual(rep["stats"]["analysis"], 0)


class EngineFinalizationTests(unittest.TestCase):
    def test_analysis_is_scheduled_once_after_everything_and_is_not_a_replan(self):
        plan = {"tasks": [{"id": f"t{i}", "title": f"T{i}", "agent": "market", "depends_on": []} for i in (1, 2, 3)]}
        st = ResearchState("r", "w", "g")
        m = ResearchManager(Scripted(plan), agents=("market", "fact_checker", "analyst"))
        m.plan(st)
        order = []
        ok = lambda s, t: order.append(t.id) or {}
        Engine(st, {"market": ok, "fact_checker": ok, "analyst": ok}, m, max_replans=0).run()
        self.assertEqual((order[-2:], st.replans, st.status), (["verify", "analyze"], 0, "completed"))
        self.assertEqual(set(st.tasks["analyze"].depends_on), {"t1", "t2", "t3", "verify"})
        self.assertEqual([e["kind"] for e in st.events].count("ANALYSIS_REQUESTED"), 1)
        self.assertEqual(m.finalize(st), [])  # never scheduled twice

    def test_analyst_still_runs_when_research_failed(self):
        plan = {"tasks": [{"id": f"t{i}", "title": f"T{i}", "agent": "market", "depends_on": []} for i in (1, 2, 3)]}
        st = ResearchState("r", "w", "g")
        m = ResearchManager(Scripted(plan), agents=("market", "fact_checker", "analyst"))
        m.plan(st)
        ran = []

        def market(s, t):
            if t.id == "t1":
                raise ValueError("boom")
            return {}
        Engine(st, {"market": market, "fact_checker": lambda s, t: ran.append(t.id) or {}, "analyst": lambda s, t: ran.append(t.id) or {}}, m).run()
        self.assertEqual((ran, st.status), (["verify", "analyze"], "needs_review"))


class EndToEndDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = Rec()
        cls.s, cls.st = pipeline(cls.rec)
        cls.inp = MemInputs(cls.s.repo, tasks_of(cls.st), demo=True)
        cls.report = build_report(cls.inp.snapshot("rA", NOW))

    def test_orchestration_ran_every_agent_then_verification_then_analysis(self):
        st = self.st
        self.assertEqual({t.agent for t in st.tasks.values() if t.id.startswith("t")}, {"market", "customer", "competitor", "pricing", "regulation", "risk"})
        self.assertEqual(st.status, "completed")
        self.assertTrue(all(t.status.value == "completed" for t in st.tasks.values()))
        self.assertEqual(st.tasks["analyze"].agent, "analyst")
        self.assertTrue(1 <= st.replans <= 2)
        done = [e["task_id"] for e in st.events if e["kind"] == "TASK_COMPLETED"]
        self.assertEqual(done[-1], "analyze")
        self.assertLess(done.index("verify"), done.index("analyze"))

    def test_lifecycle_events_cover_the_whole_pipeline(self):
        kinds = {e["kind"] for e in self.st.events}
        for k in ("PLAN_CREATED", "TASK_CREATED", "AGENT_STARTED", "TOOL_STARTED", "TOOL_COMPLETED", "SOURCE_FOUND", "SOURCE_SAVED", "CLAIM_CREATED",
                  "EVIDENCE_CREATED", "VERIFICATION_STARTED", "VERIFICATION_COMPLETED", "CONFLICT_DETECTED", "RESEARCH_GAP_DETECTED", "REPLAN_REQUESTED",
                  "RESEARCH_REPLANNED", "ANALYSIS_REQUESTED", "ANALYSIS_SAVED", "TASK_COMPLETED", "RESEARCH_COMPLETED"):
            self.assertIn(k, kinds)
        req = next(e for e in self.st.events if e["kind"] == "REPLAN_REQUESTED")
        self.assertIn("LOW_SOURCE_QUALITY", req["reasons"])
        created = [e for e in self.st.events if e["kind"] == "TASK_CREATED" and e["task_id"].startswith(("f-", "v-"))]
        self.assertTrue(created and all(e.get("reason_code") for e in created))
        seqs = [e["seq"] for e in self.st.events]
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))

    def test_claims_cover_all_dimensions_and_every_claim_went_through_verification(self):
        r = self.s.repo
        claims = r.list_claims("rA")
        self.assertEqual({c.claim_type for c in claims}, {"market_size", "market_growth", "customer_need", "competitor_profile", "pricing", "regulation", "risk"})
        self.assertEqual([c.text for c in claims if c.status == "proposed"], [])
        for c in claims:
            v = r.latest_verification("rA", c.id)
            self.assertIsNotNone(v, c.text)
            self.assertEqual((v.verifier, v.research_id), ("rules/1", "rA"))
            self.assertIn(c.status, ("supported", "partially_supported", "contradicted", "insufficient_evidence"))
        # one weak, single-source item per claim => never reported as verified
        self.assertFalse([c for c in claims if c.status == "supported" and r.claim_sources("rA", c.id)[0]["evidence_count"] < 1])

    def test_conflicts_are_classified_not_blindly_contradictions(self):
        conf = self.s.repo.list_conflicts("rA")
        self.assertEqual([(c.conflict_type, c.resolution_status, c.severity) for c in conf], [("different_definition", "explained_by_scope", "info")])

    def test_pricing_availability_is_explicit(self):
        r = self.st.tasks["t4"].result["metadata"]["pricing"]
        self.assertEqual((r["AcmeSoft Arabia"]["pricing_status"], r["NimbusHR"]["pricing_status"]), ("available", "unavailable"))

    def test_everything_is_marked_demo_and_isolated_from_production_data(self):
        r = self.s.repo
        for coll in (r.list_sources("rA"), r.list_claims("rA"), r.list_evidence("rA"), r.list_analysis("rA")):
            self.assertTrue(coll and all(x.is_demo for x in coll))
        self.assertTrue(all(".mock.invalid/" in s.url for s in r.list_sources("rA")))
        self.assertEqual((r.list_claims("rB"), r.list_sources("rB"), r.list_evidence("rB")), ([], [], []))  # nothing leaked into another research

    def test_analysis_is_labelled_inference_and_cites_only_verified_or_partial_claims(self):
        items = self.s.repo.list_analysis("rA")
        self.assertEqual({a.kind for a in items}, {"opportunity", "uncertainty", "risk_inference"})
        for a in items:
            for cid in a.basis_claim_ids:
                self.assertIn(self.s.repo.get_claim("rA", cid).status, ("supported", "partially_supported"))

    def test_report_is_fully_traceable_end_to_end(self):
        rep, r = self.report, self.s.repo
        self.assertEqual(validate_report(rep), [])
        self.assertTrue(rep["is_demo"] and rep["provenance"] == DEMO_BANNER)
        texts = {c.text for c in r.list_claims("rA")}
        sources = {s.id: s for s in r.list_sources("rA")}
        evidence = {e.id: e for e in r.list_evidence("rA")}
        cit = {c["n"]: c for c in rep["citations"]}
        findings = [f for s in rep["sections"] for f in s["findings"]]
        self.assertTrue(findings)
        for f in findings:
            self.assertIn(f["text"], texts)
            self.assertTrue(r.latest_verification("rA", f["claim_id"]) is not None)
            for ev in f["evidence"]:
                e = evidence[ev["id"]]
                self.assertEqual(e.claim_id, f["claim_id"])
                self.assertEqual(sources[e.source_id].url, cit[ev["n"]]["url"])  # claim -> evidence -> source -> citation
                self.assertIn(ev["excerpt"], " ".join(sources[e.source_id].content_text.split()))  # quote really is in the stored source text
        sec = {s["key"]: s for s in rep["sections"]}
        self.assertTrue(sec["opportunities"]["analysis"])
        for a in (x for s in rep["sections"] for x in s.get("analysis", [])):
            self.assertIn(a["label"], ("INFERENCE", "UNCERTAINTY"))
            self.assertTrue(a["basis"] and a["citations"])
        self.assertEqual(rep["stats"]["unsupported_claims"], 0)

    def test_exports_keep_citations_labels_and_demo_provenance(self):
        md = to_markdown(self.report)
        for needle in (DEMO_BANNER, "**INFERENCE**", "**PARTIALLY SUPPORTED**", "## 11. Opportunities", ".mock.invalid/"):
            self.assertIn(needle, md)
        self.assertEqual(json.loads(to_json(self.report))["stats"]["claims"], len(self.s.repo.list_claims("rA")))
        pdf = to_pdf(self.report)
        self.assertTrue(pdf.startswith(b"%PDF-1.4") and b"INFERENCE" in pdf)

    def test_usage_is_recorded_without_inventing_tokens_or_cost(self):
        rows = self.rec.rows
        self.assertTrue(rows)
        self.assertTrue({"market", "analyst"} <= {r.agent for r in rows})
        self.assertTrue(all(r.input_tokens is None and r.output_tokens is None and r.estimated_cost is None for r in rows))  # DemoLLM reports none
        self.assertTrue(all(r.research_id == "rA" and r.workspace_id == "wA" and r.ok for r in rows))

    def test_the_pipeline_is_deterministic(self):
        def signature(s, st):
            claims = sorted((c.text, c.claim_type, c.status, c.confidence) for c in s.repo.list_claims("rA"))
            analysis = sorted((a.kind, a.text) for a in s.repo.list_analysis("rA"))
            rep = build_report(MemInputs(s.repo, tasks_of(st), demo=True).snapshot("rA", NOW))
            fnd = sorted((f["text"], f["group"], f["confidence"]) for x in rep["sections"] for f in x["findings"])
            return claims, analysis, fnd, st.replans, sorted(st.tasks)
        self.assertEqual(signature(*pipeline()), signature(self.s, self.st))


if __name__ == "__main__":
    unittest.main()
