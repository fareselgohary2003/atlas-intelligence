import json
import unittest

from app.agents.competitor import CompetitorResearchAgent
from app.agents.framework import AgentDefinition, AgentRegistry, Agent
from app.agents.graph import Engine
from app.agents.manager import ResearchManager
from app.agents.market import MarketResearchAgent
from app.agents.state import ConfigError, PlanError, ResearchState, Task, TransientError
from app.demo.provider import PAGES, DemoFetcher, DemoSearchProvider
from app.evidence.service import EvidenceService
from app.tools.base import ToolContext, ToolError
from app.tools.builtin import build_default_registry
from app.tools.evidence_tools import FollowUpBuffer, register_evidence_tools
from tests.factories import NOW
from tests.memrepo import MemRepo

SIZE, GA, GB, ACME, NIMBUS, DEMAND, REG, RISK = list(PAGES)
fact = lambda url: PAGES[url][2][1]


class FindingsLLM:  # test double: canned extraction output per source URL
    def __init__(self, by_url=None, exc=None):
        self.by_url, self.exc, self.calls = by_url or {}, exc, []

    def structured_output(self, system, user):
        p = json.loads(user)
        self.calls.append(p["source_url"])
        if self.exc:
            raise self.exc
        return self.by_url.get(p["source_url"], {"findings": []})


def finding(url, claim, ctype, attrs=None, excerpt=None, stance="supports"):
    return {"excerpt": excerpt or fact(url), "claim": claim, "claim_type": ctype, "stance": stance, "attributes": attrs or {}}


class Stack:
    def __init__(self, llm, provider=None, fetcher=None, agents=(MarketResearchAgent, CompetitorResearchAgent)):
        self.repo = MemRepo()
        for r, w in (("rA", "wA"), ("rB", "wB")):
            self.repo.register_research(r, w)
        self.svc = EvidenceService(self.repo, force_demo=True, clock=lambda: NOW)
        prov = provider or DemoSearchProvider()
        self.tools = build_default_registry(lambda: prov, fetcher or DemoFetcher())
        self.fu = FollowUpBuffer()
        register_evidence_tools(self.tools, self.svc, self.fu)
        self.agents = AgentRegistry(self.tools)
        for a in agents:
            self.agents.register(a())
        self.llm = llm
        self.runners = self.agents.runners(lambda: llm, self.fu)

    def state(self, rid="rA", wid="wA"):
        return ResearchState(rid, wid, "Analyze the Saudi Arabia B2B SaaS opportunity")

    def run(self, agent, title, state=None, tid="t1", attempts=1):
        st = state or self.state()
        t = Task(tid, title, agent, attempts=attempts)
        return self.runners[agent](st, t), st

    def counts(self, rid="rA"):
        return tuple(len(x) for x in (self.repo.list_sources(rid), self.repo.list_claims(rid), self.repo.list_evidence(rid)))


class RegistryTests(unittest.TestCase):
    def test_registration_capabilities_tools_and_unknown_agents(self):
        s = Stack(FindingsLLM())
        self.assertEqual(s.agents.names(), ("competitor", "market"))
        with self.assertRaises(ValueError):
            s.agents.register(MarketResearchAgent())  # duplicate

        class Bad(Agent):
            definition = AgentDefinition("bad", "Bad", "d", ("x",), ("no_such_tool",))
            def run(self, task, ctx): ...

        class NoCaps(Agent):
            definition = AgentDefinition("nocaps", "N", "d", (), ())
            def run(self, task, ctx): ...
        for a in (Bad(), NoCaps()):
            with self.assertRaises(ValueError):
                s.agents.register(a)
        with self.assertRaises(ValueError):
            s.agents.get("ghost")
        self.assertEqual(set(s.runners), {"market", "competitor"})

    def test_allowed_tools_are_enforced_and_verification_is_not_granted(self):
        s = Stack(FindingsLLM())
        ctx = ToolContext("market", "t1", "rA", "wA")
        self.assertEqual(s.tools.execute("verify_claim", {"claim_id": "x"}, ctx).error_category, "unauthorized")
        self.assertEqual(s.tools.execute("create_research_task", {"title": "abcdef", "agent": "market"}, ctx).error_category, "unauthorized")
        self.assertNotIn("verify_claim", [t["name"] for t in s.tools.describe("market")])
        self.assertEqual(s.tools.execute("web_search", {"query": "market size"}, ToolContext("stranger", "t", "rA", "wA")).error_category, "unauthorized")


class MarketAgentTests(unittest.TestCase):
    def llm(self):
        return FindingsLLM({
            SIZE: {"findings": [finding(SIZE, "The Saudi B2B SaaS market was USD 2.1 billion in 2024", "market_size",
                                        {"metric": "market size", "value": 2.1, "unit": "usd billion", "period": "2024", "geography": "Saudi Arabia"}),
                                finding(SIZE, "The market is worth USD 9 billion", "market_size", {"value": 9},
                                        excerpt="The market is worth USD 9 billion according to nobody.")]},
            GA: {"findings": [finding(GA, "The market grew at 18% CAGR from 2022 to 2025", "market_growth",
                                      {"metric": "market growth", "value": 18, "unit": "percent", "period": "2022-2025", "definition": "narrow"}), {"junk": 1}]}})

    def test_end_to_end_sources_evidence_claims_without_verification(self):
        s = Stack(self.llm())
        res, st = s.run("market", "Market size and growth of Saudi B2B SaaS")
        self.assertEqual(res["status"], "completed")
        n_src = s.counts()[0]
        self.assertGreaterEqual(n_src, 3)  # the demo search matches any query word; capped by max_sources
        self.assertLessEqual(n_src, 6)
        self.assertEqual(s.counts()[1:], (2, 2))  # 2 grounded claims, 2 evidence
        self.assertEqual(res["counts"]["claims"], 2)
        self.assertEqual(res["counts"]["evidence"], 2)
        self.assertEqual(res["counts"]["sources"], n_src)
        self.assertGreater(res["counts"]["tool_calls"], 5)
        self.assertEqual(res["metadata"]["rejected_findings"], ["ungrounded"])
        self.assertEqual(res["metadata"]["invalid_findings"], 1)
        self.assertIn(res["confidence"], ("HIGH", "MEDIUM", "LOW"))
        self.assertTrue(all(c.status == "proposed" and c.is_demo for c in s.repo.list_claims("rA")))  # generated, not verified
        self.assertTrue(all(x.is_demo for x in s.repo.list_sources("rA")))
        ev = s.repo.list_evidence("rA")
        self.assertTrue(all(e.agent_id == "market" and e.task_key == "t1" and e.location["basis"] for e in ev))
        self.assertEqual(s.repo.list_verifications("rA", res["created_claims"][0]), [])

    def test_tool_events_are_safe_and_attributed(self):
        s = Stack(self.llm())
        _, st = s.run("market", "Market size and growth of Saudi B2B SaaS")
        tool_events = [e for e in st.events if e["kind"].startswith("TOOL_")]
        self.assertTrue(tool_events)
        self.assertTrue(all(e["agent"] == "market" and e["task_id"] == "t1" for e in tool_events))
        blob = json.dumps(tool_events)
        for private in ("Saudi B2B SaaS", "USD 2.1 billion", "mock.invalid/saudi"):
            self.assertNotIn(private, blob)  # no queries, excerpts or URLs in events
        self.assertIn("TASK_PROGRESS", [e["kind"] for e in st.events])

    def test_gap_becomes_a_follow_up_proposal(self):
        s = Stack(FindingsLLM({SIZE: {"findings": [finding(SIZE, "The Saudi B2B SaaS market was USD 2.1 billion in 2024", "market_size")]}}))
        res, _ = s.run("market", "Market size and growth of Saudi B2B SaaS")
        self.assertEqual([f["kind"] for f in res["follow_up_tasks"]], ["request"])
        self.assertIn("market growth", res["follow_up_tasks"][0]["title"])
        self.assertIn("no grounded evidence for: market growth", res["summary"])
        res2, _ = s.run("market", "Market growth of Saudi B2B SaaS", tid="f-abc123")  # follow-ups do not chain further
        self.assertEqual(res2["follow_up_tasks"], [])

    def test_retry_is_idempotent(self):
        s = Stack(self.llm())
        r1, _ = s.run("market", "Market size and growth of Saudi B2B SaaS")
        before = s.counts()
        r2, _ = s.run("market", "Market size and growth of Saudi B2B SaaS", attempts=2)
        self.assertEqual(s.counts(), before)
        self.assertEqual((r1["created_claims"], r1["created_evidence"], r1["created_sources"]),
                         (r2["created_claims"], r2["created_evidence"], r2["created_sources"]))
        self.assertEqual(len(r2["follow_up_tasks"]), len(r1["follow_up_tasks"]))

    def test_search_failure_is_a_visible_failure(self):
        class Down:
            name = "x"
            def search(self, q, o): raise ConfigError("WEB_SEARCH_API_KEY is not set")
        s = Stack(self.llm(), provider=Down())
        with self.assertRaises(ConfigError):
            s.run("market", "Market size of Saudi B2B SaaS")
        self.assertEqual(s.counts(), (0, 0, 0))

        class Flaky(Down):
            def search(self, q, o): raise ToolError("upstream_transient", "HTTP 429")
        with self.assertRaises(TransientError):  # the engine will retry the task
            Stack(self.llm(), provider=Flaky()).run("market", "Market size of Saudi B2B SaaS")

    def test_fetch_failures_are_recorded_not_fatal(self):
        class Partial(DemoFetcher):
            def fetch(self, url, cancel=None):
                if url == GA:
                    raise ToolError("upstream", "HTTP 404")
                return super().fetch(url, cancel)
        s = Stack(self.llm(), fetcher=Partial())
        res, _ = s.run("market", "Market size and growth of Saudi B2B SaaS")
        self.assertEqual(res["metadata"]["fetch_failures"], [{"host": "analyst-two.mock.invalid", "category": "upstream"}])
        self.assertIn("1 page(s) could not be retrieved", res["summary"])

        class AllDown(DemoFetcher):
            def fetch(self, url, cancel=None): raise ToolError("network", "boom")
        res, _ = Stack(self.llm(), fetcher=AllDown()).run("market", "Market size of Saudi B2B SaaS")
        self.assertEqual((res["status"], res["counts"]["claims"]), ("insufficient", 0))

    def test_llm_failures(self):
        res, _ = Stack(FindingsLLM({SIZE: {"nonsense": 1}})).run("market", "Market size of Saudi B2B SaaS")
        self.assertEqual((res["metadata"]["extraction_failures"], res["status"]), (1, "insufficient"))
        with self.assertRaises(TransientError):
            Stack(FindingsLLM(exc=TransientError("429"))).run("market", "Market size of Saudi B2B SaaS")

        def no_llm():
            raise ConfigError("LLM_API_KEY is not set")
        s = Stack(FindingsLLM())
        runner = s.agents.runners(no_llm, s.fu)["market"]
        with self.assertRaises(ConfigError):
            runner(s.state(), Task("t1", "Market size", "market"))


class CompetitorAgentTests(unittest.TestCase):
    def test_pricing_status_is_explicit_and_never_invented(self):
        llm = FindingsLLM({
            ACME: {"findings": [finding(ACME, "AcmeSoft Arabia sells HR software to medium-sized businesses", "competitor_profile", {"company": "AcmeSoft Arabia"}, PAGES[ACME][2][1]),
                                finding(ACME, "AcmeSoft Arabia lists a Team plan at USD 49 per user per month", "pricing",
                                        {"company": "AcmeSoft Arabia", "price": "49", "currency": "USD", "pricing_status": "available"}, PAGES[ACME][2][2])]},
            NIMBUS: {"findings": [finding(NIMBUS, "NimbusHR targets enterprise customers in the Gulf", "competitor_profile", {"company": "NimbusHR"}, PAGES[NIMBUS][2][1]),
                                  finding(NIMBUS, "NimbusHR does not publish pricing", "pricing", {"company": "NimbusHR", "pricing_status": "unavailable"}, PAGES[NIMBUS][2][2])]}})
        res, _ = Stack(llm).run("competitor", "Competitor landscape and pricing for HR software vendors")
        comps = res["metadata"]["competitors"]
        self.assertEqual(comps["AcmeSoft Arabia"]["pricing_status"], "available")
        self.assertEqual(comps["NimbusHR"]["pricing_status"], "unavailable")
        self.assertEqual(res["counts"]["claims"], 4)

    def test_profile_only_company_defaults_to_pricing_unavailable(self):
        llm = FindingsLLM({NIMBUS: {"findings": [finding(NIMBUS, "NimbusHR targets enterprise customers in the Gulf", "competitor_profile", {"company": "NimbusHR"}, PAGES[NIMBUS][2][1])]}})
        res, _ = Stack(llm).run("competitor", "Competitor NimbusHR vendor landscape")
        self.assertEqual(res["metadata"]["competitors"]["NimbusHR"]["pricing_status"], "unavailable")


class ManagerIntegrationTests(unittest.TestCase):
    def test_follow_up_flows_through_manager_and_engine_with_a_hard_cap(self):
        s = Stack(FindingsLLM({SIZE: {"findings": [finding(SIZE, "The Saudi B2B SaaS market was USD 2.1 billion in 2024", "market_size")]},
                               GA: {"findings": [finding(GA, "The market grew at 18% CAGR from 2022 to 2025", "market_growth")]}}))
        plan = {"tasks": [{"id": "t1", "title": "Market size and growth of Saudi B2B SaaS", "agent": "market", "depends_on": []},
                          {"id": "t2", "title": "Competitor vendor landscape", "agent": "competitor", "depends_on": []},
                          {"id": "t3", "title": "Market segments of Saudi B2B SaaS", "agent": "market", "depends_on": []}]}

        class Scripted:
            r = [plan]
            def structured_output(self, sys, user): return self.r.pop(0) if self.r else {"tasks": []}
        st = s.state()
        m = ResearchManager(Scripted(), agents=s.agents.names())
        m.plan(st)
        Engine(st, s.runners, m, max_replans=1).run()
        ups = [t for t in st.tasks.values() if t.id.startswith("f-")]
        self.assertGreaterEqual(len(ups), 1)
        self.assertEqual(st.replans, 1)  # hard cap respected even though follow-ups keep being proposed
        self.assertTrue(all(t.status.value in ("completed", "failed") for t in st.tasks.values()))
        self.assertIn("RESEARCH_REPLANNED", [e["kind"] for e in st.events])
        ids_before = set(st.tasks)
        m.follow_up_tasks(st)  # idempotent: the same proposals map to the same task ids
        self.assertEqual(set(st.tasks), ids_before)

    def test_manager_only_plans_registered_agents_and_ignores_bad_proposals(self):
        class L:
            def structured_output(self, s, u):
                return {"tasks": [{"id": "a", "title": "T a", "agent": "risk", "depends_on": []}] * 1 +
                        [{"id": "b", "title": "T b", "agent": "market", "depends_on": []}, {"id": "c", "title": "T c", "agent": "market", "depends_on": []}]}
        st = ResearchState("r", "w", "g")
        with self.assertRaises(PlanError):
            ResearchManager(L(), agents=("market", "competitor")).plan(st)
        st.tasks["t1"] = Task("t1", "x", "market", status="completed", result={"follow_up_tasks": [
            {"key": "k1", "title": "Ghost work", "agent": "ghost"}, {"key": "k2", "title": "", "agent": "market"},
            {"key": "k3", "title": "Real follow-up", "agent": "market"}]})
        got = ResearchManager(L(), agents=("market",)).follow_up_tasks(st)
        self.assertEqual([t.title for t in got], ["Real follow-up"])
        ResearchManager(L(), agents=("market",)).follow_up_tasks(st)
        self.assertEqual(len(st.errors), 2)  # invalid proposals recorded once, not repeatedly


class ToolSecurityTests(unittest.TestCase):
    def test_scope_cannot_be_supplied_or_forged_via_arguments(self):
        s = Stack(FindingsLLM())
        ctx = ToolContext("market", "t1", "rA", "wA")
        for field in ("research_id", "workspace_id"):
            r = s.tools.execute("create_claim", {"text": "The market was large in 2024", "claim_type": "trend", field: "rB"}, ctx)
            self.assertEqual((r.ok, r.error_category), (False, "validation"))
        self.assertEqual(s.tools.execute("create_claim", {"text": "The market was large in 2024", "claim_type": "trend"},
                                         ToolContext("market", "t1", "rA", None)).error_category, "validation")
        self.assertEqual(s.counts(), (0, 0, 0))

    def test_agent_in_one_workspace_cannot_touch_anothers_records(self):
        s = Stack(FindingsLLM())
        ctxB = ToolContext("market", "t1", "rB", "wB")
        src = s.tools.execute("save_source", {"url": "https://x.mock.invalid/a", "text": "MOCK text long enough to be stored as a source for tests. " * 3}, ctxB).unwrap()
        cl = s.tools.execute("create_claim", {"text": "Claim recorded in workspace B", "claim_type": "trend"}, ctxB).unwrap()
        ctxA = ToolContext("market", "t1", "rA", "wA")
        for args in ({"source_id": src["source_id"], "excerpt": "MOCK text long enough to be stored"},
                     {"source_id": "bogus-id-value", "excerpt": "MOCK text long enough to be stored"}):
            r = s.tools.execute("create_evidence", args, ctxA)
            self.assertEqual((r.ok, r.error_category, r.error), (False, "validation", "Source not found in this research"))
        self.assertEqual(s.tools.execute("create_claim", {"text": "Claim recorded in workspace B", "claim_type": "trend"}, ctxA).data["created"], True)
        self.assertNotEqual(cl["claim_id"], None)
        wrong = ToolContext("market", "t1", "rB", "wA")  # research/workspace mismatch is refused
        self.assertEqual(s.tools.execute("create_claim", {"text": "Forged workspace pairing here", "claim_type": "trend"}, wrong).error_category, "validation")
        self.assertEqual(s.counts("rA")[1], 1)


if __name__ == "__main__":
    unittest.main()
