import unittest

from app.agents.competitor import CompetitorResearchAgent
from app.agents.customer import CustomerResearchAgent
from app.agents.factchecker import FactCheckerAgent
from app.agents.graph import Engine
from app.agents.manager import ResearchManager
from app.agents.market import MarketResearchAgent
from app.agents.pricing import PricingAgent
from app.agents.regulation import RegulationResearchAgent
from app.agents.risk import RiskAgent
from app.agents.state import PlanError, ResearchState, Task
from app.demo.provider import PAGES
from app.evidence.domain import Scope
from app.tools.base import ToolContext
from tests.evidence_contract import cand
from tests.test_agents import ACME, DEMAND, GA, GB, REG, RISK, SIZE, FindingsLLM, Stack, finding

ALL = (MarketResearchAgent, CustomerResearchAgent, CompetitorResearchAgent, PricingAgent, RegulationResearchAgent, RiskAgent, FactCheckerAgent)
MARKET_TITLE = "Market size and growth of Saudi B2B SaaS"


def market_llm():
    a = {"geography": "Saudi Arabia"}
    return FindingsLLM({
        SIZE: {"findings": [finding(SIZE, "The Saudi B2B SaaS market was USD 2.1 billion in 2024", "market_size",
                                    {**a, "metric": "market size", "value": 2.1, "unit": "usd billion", "period": "2024"})]},
        GA: {"findings": [finding(GA, "The market grew at 18% CAGR from 2022 to 2025", "market_growth",
                                  {**a, "metric": "market growth", "value": 18, "unit": "percent", "period": "2022-2025", "definition": "narrow"})]},
        GB: {"findings": [finding(GB, "The market grew at 21% CAGR from 2022 to 2025", "market_growth",
                                  {**a, "metric": "market growth", "value": 21, "unit": "percent", "period": "2022-2025", "definition": "broad"})]}})


def kinds(state):
    return [e["kind"] for e in state.events]


class Scripted:
    def __init__(self, *r):
        self.r = list(r)

    def structured_output(self, s, u):
        return self.r.pop(0) if self.r else {"tasks": []}


class FactCheckerTests(unittest.TestCase):
    def test_verifies_claims_records_scope_conflict_and_low_quality_gaps(self):
        s = Stack(market_llm(), agents=ALL)
        st = s.state()
        s.run("market", MARKET_TITLE, st)
        res, _ = s.run("fact_checker", "Verify claims", st, tid="verify")
        claims = s.repo.list_claims("rA")
        self.assertEqual(len(claims), 3)
        self.assertEqual({c.status for c in claims}, {"partially_supported"})  # one non-authoritative source each
        self.assertEqual(res["metadata"]["outcomes"], {"partially_supported": 3})
        conflicts = s.repo.list_conflicts("rA")
        self.assertEqual([(c.conflict_type, c.resolution_status) for c in conflicts], [("different_definition", "explained_by_scope")])
        self.assertEqual(res["metadata"]["gap_reasons"], ["LOW_SOURCE_QUALITY"] * 3)  # a scope difference is not a research gap
        for c in claims:
            v = s.repo.latest_verification("rA", c.id)
            self.assertEqual((v.verifier, len(s.repo.list_verifications("rA", c.id))), ("rules/1", 1))
        for k in ("VERIFICATION_STARTED", "VERIFICATION_COMPLETED", "CONFLICT_DETECTED", "RESEARCH_GAP_DETECTED", "SOURCE_SAVED", "CLAIM_CREATED", "EVIDENCE_CREATED"):
            self.assertIn(k, kinds(st))
        self.assertEqual(kinds(st).count("RESEARCH_GAP_DETECTED"), 3)
        self.assertTrue(all(f["reason_code"] == "LOW_SOURCE_QUALITY" and f["agent"] == "market" for f in res["follow_up_tasks"]))
        self.assertEqual((res["counts"]["claims"], res["counts"]["evidence"], res["counts"]["sources"]), (0, 0, 0))  # verifier creates nothing

    def test_gaps_for_unsupported_claims_and_unresolved_contradictions(self):
        s = Stack(FindingsLLM(), agents=ALL)
        sc = Scope("wA", "rA", "t1", "market")
        orphan, _ = s.svc.create_claim(sc, "Regulators will approve the product next year", "regulation")  # no evidence at all
        attrs = {"metric": "market size", "unit": "usd billion", "period": "2024", "geography": "KSA"}
        for tag, val in (("a", 2.1), ("b", 5)):
            text = f"MOCK: the market was USD {val} billion in 2024. " * 3
            src, _, _ = s.svc.save_source(sc, cand(f"https://{tag}.mock.invalid/x", text), text)
            c, _ = s.svc.create_claim(sc, f"Market size was USD {val} billion in 2024", "market_size", {**attrs, "value": val})
            s.svc.create_evidence(sc, src.id, f"the market was USD {val} billion in 2024", c.id)
        st = s.state()
        res, _ = s.run("fact_checker", "Verify claims", st, tid="verify")
        self.assertEqual(set(res["metadata"]["gap_reasons"]), {"INSUFFICIENT_EVIDENCE", "LOW_SOURCE_QUALITY", "CONFLICT_DETECTED"})
        self.assertEqual([(c.conflict_type, c.severity, c.resolution_status) for c in s.repo.list_conflicts("rA")], [("direct_contradiction", "high", "unresolved")])
        self.assertEqual(s.repo.get_claim("rA", orphan.id).status, "insufficient_evidence")
        by_code = {f["reason_code"]: f for f in res["follow_up_tasks"]}
        self.assertEqual(by_code["INSUFFICIENT_EVIDENCE"]["agent"], "regulation")
        self.assertEqual(kinds(st).count("RESEARCH_GAP_DETECTED"), len(res["metadata"]["gap_reasons"]))
        # re-run: settled claims are not re-verified again; the insufficient one is (new evidence may have arrived)
        res2, _ = s.run("fact_checker", "Verify claims", st, tid="verify2")
        self.assertEqual(res2["metadata"]["claims_checked"], 1)
        self.assertEqual(len(s.repo.list_verifications("rA", orphan.id)), 2)
        other = [c for c in s.repo.list_claims("rA") if c.id != orphan.id][0]
        self.assertEqual(len(s.repo.list_verifications("rA", other.id)), 1)  # history append-only, no duplicates

    def test_nothing_to_verify(self):
        s = Stack(FindingsLLM(), agents=ALL)
        res, _ = s.run("fact_checker", "Verify", tid="verify")
        self.assertEqual((res["summary"], res["follow_up_tasks"]), ("No claims were awaiting verification.", []))

    def test_permissions_separate_generation_from_verification(self):
        s = Stack(FindingsLLM(), agents=ALL)
        fc, mk = ToolContext("fact_checker", "t", "rA", "wA"), ToolContext("market", "t", "rA", "wA")
        for tool, args in (("create_claim", {"text": "Some claim text here", "claim_type": "trend"}),
                           ("create_evidence", {"source_id": "x" * 8, "excerpt": "some excerpt text"}),
                           ("save_source", {"url": "https://a.mock.invalid/x", "text": "t" * 60})):
            self.assertEqual(s.tools.execute(tool, args, fc).error_category, "unauthorized", tool)
        for tool, args in (("verify_claim", {"claim_id": "x"}), ("list_claims", {}), ("list_conflicts", {})):
            self.assertEqual(s.tools.execute(tool, args, mk).error_category, "unauthorized", tool)
        self.assertTrue(s.tools.execute("list_claims", {}, fc).ok)
        self.assertEqual(s.tools.execute("list_claims", {"statuses": ["bogus"]}, fc).error_category, "validation")
        other = ToolContext("fact_checker", "t", "rB", "wA")  # research/workspace mismatch
        self.assertEqual(s.tools.execute("list_claims", {}, other).error_category, "validation")


class NewAgentTests(unittest.TestCase):
    def run_case(self, agent, title, url, claim, ctype, attrs, idx=1):
        s = Stack(FindingsLLM({url: {"findings": [finding(url, claim, ctype, attrs, excerpt=PAGES[url][2][idx])]}}), agents=ALL)
        res, _ = s.run(agent, title)
        cl, ev = s.repo.list_claims("rA"), s.repo.list_evidence("rA")
        self.assertEqual((res["status"], [c.claim_type for c in cl], [c.status for c in cl]), ("completed", [ctype], ["proposed"]))
        self.assertTrue(all(e.agent_id == agent and e.location["basis"] == "whitespace_normalized_text" and e.is_demo for e in ev))
        self.assertTrue(all(c.is_demo for c in cl))
        return res

    def test_customer(self):
        self.run_case("customer", "Customer demand and pain points in Saudi SMB software", DEMAND, "64% of Saudi medium-sized businesses cite manual reporting as their main pain point",
                      "customer_need", {"metric": "share citing manual reporting", "value": 64, "unit": "percent", "customer_segment": "medium-sized businesses"})

    def test_regulation_carries_a_disclaimer(self):
        res = self.run_case("regulation", "Regulation and data protection compliance requirements", REG,
                            "The mock Data Protection Regulation requires local storage of residents' personal data", "regulation", {"regulator": "Mock Data Protection Authority"})
        self.assertIn("not legal advice", res["metadata"]["disclaimer"])

    def test_risk(self):
        self.run_case("risk", "Risks and adoption barriers for SaaS in Saudi Arabia", RISK,
                      "Long procurement cycles are documented as an adoption barrier", "risk", {"risk_category": "adoption"})

    def test_pricing_table(self):
        res = self.run_case("pricing", "Pricing plans for HR software vendors", ACME, "AcmeSoft Arabia lists a Team plan at USD 49 per user per month", "pricing",
                            {"company": "AcmeSoft Arabia", "plan": "Team", "price": "49", "currency": "USD", "pricing_status": "available"}, idx=2)
        row = res["metadata"]["pricing"]["AcmeSoft Arabia"]
        self.assertEqual((row["pricing_status"], row["plans"][0]["plan"]), ("available", "Team"))


PLAN2 = {"tasks": [{"id": "t1", "title": "A", "agent": "market", "depends_on": []}, {"id": "t2", "title": "B", "agent": "competitor", "depends_on": []}]}
FIVE = ("market", "competitor", "fact_checker")


class ManagerReplanningTests(unittest.TestCase):
    def test_plan_appends_verification_and_reserves_system_agents(self):
        st = ResearchState("r", "w", "g")
        ResearchManager(Scripted({"tasks": PLAN2["tasks"] + [{"id": "t3", "title": "C", "agent": "market", "depends_on": []}]}), agents=FIVE).plan(st)
        v = st.tasks["verify"]
        self.assertEqual((v.agent, v.depends_on), ("fact_checker", ["t1", "t2", "t3"]))
        bad = {"tasks": PLAN2["tasks"] + [{"id": "t3", "title": "C", "agent": "fact_checker", "depends_on": []}]}
        with self.assertRaises(PlanError):
            ResearchManager(Scripted(bad), agents=FIVE).plan(ResearchState("r", "w", "g"))
        reserved = {"tasks": PLAN2["tasks"] + [{"id": "verify", "title": "C", "agent": "market", "depends_on": []}]}
        with self.assertRaises(PlanError):
            ResearchManager(Scripted(reserved), agents=FIVE).plan(ResearchState("r", "w", "g"))

    def test_follow_ups_carry_reasons_and_schedule_reverification(self):
        st = ResearchState("r", "w", "g")
        st.tasks["verify"] = Task("verify", "v", "fact_checker", status="completed", result={"follow_up_tasks": [
            {"key": "k1", "title": "Find corroboration", "agent": "market", "reason_code": "LOW_SOURCE_QUALITY"},
            {"key": "k2", "title": "Sneaky verify request", "agent": "fact_checker", "reason_code": "CLAIM_UNSUPPORTED"}]})
        m = ResearchManager(Scripted(), agents=FIVE)
        got = m.follow_up_tasks(st)
        self.assertEqual([(t.agent, t.reason) for t in got], [("market", "LOW_SOURCE_QUALITY"), ("fact_checker", "VERIFICATION_FOLLOW_UP")])
        self.assertEqual(got[1].depends_on, [got[0].id])
        self.assertEqual(len(st.errors), 1)  # agents cannot request the verifier directly

    def test_verification_runs_even_when_research_tasks_fail(self):
        st = ResearchState("r", "w", "g")
        ResearchManager(Scripted({"tasks": PLAN2["tasks"] + [{"id": "t4", "title": "D", "agent": "market", "depends_on": []}]}), agents=FIVE).plan(st)
        st.tasks["t3"] = Task("t3", "dep", "market", ["t1"])  # ordinary dependent of a failing task
        ran = []

        def boom(s, t):
            raise ValueError("bad")
        ok = lambda s, t: ran.append(t.id) or {}
        Engine(st, {"market": lambda s, t: boom(s, t) if t.id in ("t1", "t3") else ok(s, t), "competitor": ok, "fact_checker": ok}).run()
        self.assertEqual(st.tasks["t1"].status.value, "failed")
        self.assertEqual(st.tasks["t3"].status.value, "skipped")  # normal tasks still skip on a failed dependency
        self.assertEqual((st.tasks["verify"].status.value, sorted(ran), ran[-1]), ("completed", ["t2", "t4", "verify"], "verify"))  # verifier runs last, on what exists
        self.assertEqual(st.status, "needs_review")

    def test_full_loop_is_bounded_records_reasons_and_leaves_no_unverified_claims(self):
        s = Stack(market_llm(), agents=ALL)
        plan = {"tasks": [{"id": "t1", "title": MARKET_TITLE, "agent": "market", "depends_on": []},
                          {"id": "t2", "title": "Customer demand and pain points in Saudi software", "agent": "customer", "depends_on": []},
                          {"id": "t3", "title": "Competitor landscape for HR software vendors", "agent": "competitor", "depends_on": []}]}
        st = s.state()
        m = ResearchManager(Scripted(plan), agents=s.agents.names())
        m.plan(st)
        Engine(st, s.runners, m, max_replans=2).run()
        self.assertLessEqual(st.replans, 2)
        self.assertTrue(all(t.status.value in ("completed", "failed", "skipped") for t in st.tasks.values()))
        self.assertIn(st.status, ("completed", "needs_review"))
        req = [e for e in st.events if e["kind"] == "REPLAN_REQUESTED"]
        self.assertTrue(req and req[0]["reasons"])
        self.assertTrue(all(e.get("reason_code") for e in st.events if e["kind"] == "TASK_CREATED" and e["task_id"].startswith(("f-", "v-"))))
        self.assertTrue(any(t.startswith("v-") for t in st.tasks))
        self.assertEqual([c.status for c in s.repo.list_claims("rA") if c.status == "proposed"], [])  # every claim went through verification


if __name__ == "__main__":
    unittest.main()
