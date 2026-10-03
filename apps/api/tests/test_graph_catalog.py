import unittest

from app.agents.catalog import AGENT_CLASSES, MANAGER, agent_definitions
from app.evidence.graph import build_graph
from app.tools.builtin import build_default_registry
from app.tools.evidence_tools import FollowUpBuffer, register_evidence_tools
from tests.test_analyst_e2e import pipeline


class CatalogTests(unittest.TestCase):
    def test_every_required_agent_exists_with_capabilities_and_valid_tools(self):
        defs = {d.id: d for d in agent_definitions()}
        self.assertEqual(set(defs), {"research_manager", "market", "customer", "competitor", "pricing", "regulation", "risk", "fact_checker", "analyst"})
        reg = build_default_registry(lambda: None, None)
        register_evidence_tools(reg, None, FollowUpBuffer())
        for d in defs.values():
            self.assertTrue(d.name and d.description and d.capabilities, d.id)
            self.assertTrue(set(d.allowed_tools) <= set(reg.names()), (d.id, set(d.allowed_tools) - set(reg.names())))
        self.assertEqual(MANAGER.allowed_tools, ())
        self.assertEqual(len(AGENT_CLASSES), len({c.definition.id for c in AGENT_CLASSES}))

    def test_least_privilege_across_the_agent_set(self):
        defs = {d.id: set(d.allowed_tools) for d in agent_definitions()}
        writers = {"create_claim", "create_evidence", "save_source"}
        for a in ("fact_checker", "analyst"):
            self.assertFalse(defs[a] & writers, a)  # verifier and analyst never create facts
        self.assertEqual([a for a, t in defs.items() if "verify_claim" in t], ["fact_checker"])
        self.assertEqual([a for a, t in defs.items() if "save_analysis" in t], ["analyst"])
        for a in ("market", "customer", "competitor", "pricing", "regulation", "risk"):
            self.assertFalse(defs[a] & {"verify_claim", "save_analysis", "list_claims"}, a)


class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s, cls.st = pipeline()
        r = cls.s.repo
        cls.args = (r.list_claims("rA"), r.list_evidence("rA"), r.list_sources("rA"), r.list_conflicts("rA"))
        cls.g = build_graph(*cls.args)

    def test_graph_is_internally_consistent_and_built_from_stored_records(self):
        g = self.g
        ids = {n["id"] for n in g["nodes"]}
        self.assertEqual(len(ids), len(g["nodes"]))
        self.assertTrue(all(e["source"] in ids and e["target"] in ids for e in g["edges"]))
        claims, evidence, sources, _ = self.args
        self.assertEqual({n["id"] for n in g["nodes"] if n["type"] == "claim"}, {f"c:{c.id}" for c in claims})
        self.assertEqual({n["id"] for n in g["nodes"] if n["type"] == "evidence"}, {f"e:{e.id}" for e in evidence if e.claim_id})
        for n in (n for n in g["nodes"] if n["type"] == "evidence"):
            self.assertEqual(sum(1 for e in g["edges"] if e["type"] == "from_source" and e["source"] == n["id"]), 1)
            self.assertEqual(sum(1 for e in g["edges"] if e["type"] == "has_evidence" and e["target"] == n["id"]), 1)
        self.assertTrue(all(n["is_demo"] for n in g["nodes"]))
        self.assertTrue(all(n["url"].startswith("https://") for n in g["nodes"] if n["type"] == "source"))

    def test_conflicts_appear_as_claim_to_claim_edges_with_their_classification(self):
        edges = [e for e in self.g["edges"] if e["type"] == "conflicts_with"]
        self.assertEqual([(e["conflict_type"], e["resolution_status"]) for e in edges], [("different_definition", "explained_by_scope")])
        flagged = [n for n in self.g["nodes"] if n["type"] == "claim" and n["has_conflict"]]
        self.assertEqual(len(flagged), 2)
        self.assertEqual(self.g["counts"]["conflicts"], 1)

    def test_limit_truncates_and_never_dangles(self):
        g = build_graph(*self.args, limit=2)
        self.assertTrue(g["truncated"] and g["counts"]["claims"] == 2)
        ids = {n["id"] for n in g["nodes"]}
        self.assertTrue(all(e["source"] in ids and e["target"] in ids for e in g["edges"]))
        self.assertEqual(build_graph([], [], [], []), {"nodes": [], "edges": [], "truncated": False, "counts": {"claims": 0, "evidence": 0, "sources": 0, "conflicts": 0}})

    def test_bulk_reads_match_per_item_reads(self):
        r, ids = self.s.repo, [c.id for c in self.args[0]]
        vs = r.latest_verifications("rA", ids)
        self.assertEqual({k: v.id for k, v in vs.items()}, {c: r.latest_verification("rA", c).id for c in ids})
        cs = r.claim_sources_bulk("rA", ids)
        self.assertEqual({c: cs[c] for c in ids}, {c: r.claim_sources("rA", c) for c in ids})
        sids = [s.id for s in self.args[2]]
        self.assertEqual(set(r.sources_by_ids("rA", sids)), set(sids))
        self.assertEqual(r.sources_by_ids("rB", sids), {})  # other research sees nothing
        usage = r.source_usage("rA", sids)
        self.assertEqual(sum(u["evidence"] for u in usage.values()), len([e for e in self.args[1] if e.source_id in sids]))


if __name__ == "__main__":
    unittest.main()
