import copy
import json
import re
import unittest

from app.evidence.domain import DuplicateError, EvidenceError, Scope
from app.reporting.builder import DEMO_BANNER, ReportInputs, build_report, validate_report
from app.reporting.export import to_json, to_markdown, to_pdf
from app.reporting.service import ReportService
from tests.evidence_contract import cand
from tests.factories import NOW
from tests.test_factchecker import ALL, MARKET_TITLE, market_llm
from tests.test_agents import Stack


class MemInputs:  # test double: reads the in-memory evidence repository
    def __init__(self, repo, tasks=(), demo=False):
        self.repo, self.tasks, self.demo = repo, list(tasks), demo

    def research(self, rid):
        rc = self.repo.research_context(rid)
        return None if rc is None else {"id": rid, "workspace_id": rc["workspace_id"], "title": "Saudi B2B SaaS", "objective": "Analyze the opportunity for a B2B SaaS launch in Saudi Arabia.",
                                        "geography": "Saudi Arabia", "is_demo": self.demo}

    def snapshot(self, rid, at):
        claims = self.repo.list_claims(rid, limit=1000)
        return ReportInputs(self.research(rid), claims, self.repo.list_evidence(rid, limit=1000), self.repo.list_sources(rid, limit=1000),
                            {c.id: v for c in claims if (v := self.repo.latest_verification(rid, c.id))}, self.repo.list_conflicts(rid), self.tasks, at,
                            self.repo.list_analysis(rid))


class MemReports:
    def __init__(self):
        self.rows = []

    def add_report(self, rec, audit_hook=None):
        if any(r.research_id == rec.research_id and r.version == rec.version for r in self.rows):
            raise DuplicateError()
        self.rows.append(copy.deepcopy(rec))
        if audit_hook:
            audit_hook(None, rec)

    def latest_report(self, rid):
        rs = [r for r in self.rows if r.research_id == rid]
        return copy.deepcopy(max(rs, key=lambda r: r.version)) if rs else None

    def list_versions(self, rid):
        return [{"id": r.id, "version": r.version, "title": r.title, "is_demo": r.is_demo, "created_at": r.created_at.isoformat()}
                for r in sorted((r for r in self.rows if r.research_id == rid), key=lambda r: -r.version)]

    def get_report(self, rid, v):
        return next((copy.deepcopy(r) for r in self.rows if r.research_id == rid and r.version == v), None)


def scenario():
    s = Stack(market_llm(), agents=ALL)
    st = s.state()
    s.run("market", MARKET_TITLE, st)
    s.run("fact_checker", "Verify", st, tid="verify")
    sc = Scope("wA", "rA", "t9", "market")
    text = "MOCK: analysts say the market shrank by 30% in 2025 according to a fictional bulletin. " * 2
    src, _, _ = s.svc.save_source(sc, cand("https://bulletin.mock.invalid/x", text), text)
    bad, _ = s.svc.create_claim(sc, "The Saudi B2B SaaS market grew 30% in 2025", "market_growth")
    s.svc.create_evidence(sc, src.id, "the market shrank by 30% in 2025", bad.id, "contradicts")
    s.svc.verify_claim(Scope("wA", "rA", None, "fact_checker"), bad.id)
    nodata, _ = s.svc.create_claim(sc, "Regulators intend to approve all SaaS products", "regulation")  # never gets evidence
    s.svc.verify_claim(Scope("wA", "rA", None, "fact_checker"), nodata.id)
    fresh, _ = s.svc.create_claim(sc, "Customers prefer annual contracts", "customer_need")  # evidence but never verified
    s.svc.create_evidence(sc, src.id, "analysts say the market shrank by 30% in 2025", fresh.id)
    tasks = [{"key": "t1", "title": MARKET_TITLE, "agent": "market", "status": "completed", "error": None},
             {"key": "t2", "title": "Pricing", "agent": "pricing", "status": "failed", "error": "boom"}]
    return s, MemInputs(s.repo, tasks, demo=True), {"bad": bad, "nodata": nodata, "fresh": fresh}


class ReportBuilderTests(unittest.TestCase):
    def setUp(self):
        self.s, self.inp, self.c = scenario()
        self.report = build_report(self.inp.snapshot("rA", NOW))
        self.sec = {x["key"]: x for x in self.report["sections"]}

    def findings(self):
        return [f for x in self.report["sections"] for f in x["findings"]]

    def test_required_sections_in_order(self):
        self.assertEqual([x["title"] for x in self.report["sections"]], [
            "Executive Summary", "Research Objective", "Methodology", "Key Findings", "Market Analysis", "Customer & Demand Analysis", "Competitor Analysis",
            "Pricing Analysis", "Regulatory Considerations", "Risk Analysis", "Opportunities", "Conflicts / Uncertainties", "Evidence Quality",
            "Research Gaps", "Conclusion", "Sources", "Claims and Supporting Evidence"])

    def test_every_finding_is_a_stored_claim_with_resolving_citations(self):
        claim_texts = {c.text for c in self.s.repo.list_claims("rA")}
        self.assertTrue(self.findings())
        for f in self.findings():
            self.assertIn(f["text"], claim_texts)  # nothing is invented: findings are stored claims verbatim
            self.assertTrue(f["evidence"] and f["citations"])
        self.assertEqual(validate_report(self.report), [])
        nums = [c["n"] for c in self.report["citations"]]
        self.assertEqual(nums, list(range(1, len(nums) + 1)))
        self.assertTrue(all(c["url"].startswith("https://") and c["retrieved_at"] for c in self.report["citations"]))

    def test_evidence_excerpts_are_quoted_from_stored_evidence(self):
        stored = {e.id: e.excerpt for e in self.s.repo.list_evidence("rA")}
        for f in self.findings():
            for e in f["evidence"]:
                self.assertEqual(e["excerpt"], stored[e["id"]])

    def test_status_groups_never_overstate(self):
        by_text = {f["text"]: f for f in self.sec["claims_appendix"]["findings"]}
        self.assertEqual(by_text["The Saudi B2B SaaS market grew 30% in 2025"]["group"], "contradicted")
        self.assertEqual(by_text["Customers prefer annual contracts"]["label"], "UNVERIFIED")  # has evidence but no verification
        self.assertTrue(all(f["group"] == "verified" and f["status"] == "supported" for f in self.sec["key_findings"]["findings"]))
        self.assertTrue(all(f["group"] in ("partial", "verified") for f in self.sec["market"]["findings"] if f["claim_type"] != "market_growth" or f["text"] != "The Saudi B2B SaaS market grew 30% in 2025"))

    def test_contradicted_finding_cites_contradicting_evidence_only(self):
        f = next(f for f in self.findings() if f["text"].startswith("The Saudi B2B SaaS market grew 30%"))
        stances = {e.id: e.stance for e in self.s.repo.list_evidence("rA")}
        self.assertTrue(all(stances[e["id"]] == "contradicts" for e in f["evidence"]))

    def test_claim_without_evidence_is_a_gap_not_a_finding(self):
        self.assertNotIn(self.c["nodata"].text, [f["text"] for f in self.findings()])
        gaps = " ".join(p["text"] for p in self.sec["gaps"]["paragraphs"])
        self.assertIn(self.c["nodata"].text, gaps)
        self.assertIn("Task 'Pricing' (pricing) failed", gaps)
        self.assertEqual(self.report["stats"]["unsupported_claims"], 1)

    def test_a_supported_status_without_evidence_cannot_become_a_finding(self):
        snap = self.inp.snapshot("rA", NOW)
        c = snap.claims[0]
        c.status = "supported"
        snap.evidence = [e for e in snap.evidence if e.claim_id != c.id]  # corrupted data: 'supported' with no evidence
        rep = build_report(snap)
        self.assertNotIn(c.text, [f["text"] for x in rep["sections"] for f in x["findings"]])

    def test_conflicts_preserve_both_sides(self):
        conf = self.sec["conflicts"]["conflicts"]
        self.assertEqual([c["conflict_type"] for c in conf], ["different_definition"])
        self.assertTrue(conf[0]["claim_a"]["text"] and conf[0]["claim_b"]["text"] and conf[0]["claim_a"]["citations"] and conf[0]["claim_b"]["citations"])
        self.assertIn("not a contradiction", conf[0]["explanation"])

    def test_demo_provenance_is_explicit(self):
        self.assertTrue(self.report["is_demo"])
        self.assertEqual(self.report["provenance"], DEMO_BANNER)
        self.assertIn(DEMO_BANNER, [p["text"] for p in self.sec["executive_summary"]["paragraphs"]])
        self.assertIn("not legal advice", " ".join(p["text"] for p in self.sec["regulatory"]["paragraphs"]))
        self.assertIn("Not generated", self.sec["opportunities"]["paragraphs"][0]["text"])  # no invented opportunities

    def test_empty_research_builds_an_honest_report(self):
        from tests.memrepo import MemRepo
        repo = MemRepo()
        repo.register_research("rZ", "wZ")
        rep = build_report(MemInputs(repo).snapshot("rZ", NOW))
        self.assertEqual((rep["stats"]["claims"], rep["citations"]), (0, []))
        self.assertIn("No claims were recorded", rep["sections"][0]["paragraphs"][-1]["text"])
        self.assertFalse(rep["is_demo"])
        self.assertTrue(all(any(p["kind"] == "gap" for p in x["paragraphs"]) for x in rep["sections"] if x["key"] in ("market", "pricing", "risk")))

    def test_builder_refuses_to_emit_a_report_that_fails_traceability(self):
        from unittest import mock
        with mock.patch("app.reporting.builder.validate_report", return_value=["finding x has no evidence or citations"]):
            with self.assertRaises(ValueError) as cm:
                build_report(self.inp.snapshot("rA", NOW))
        self.assertIn("traceability", str(cm.exception))

    def test_tampering_is_detected(self):
        rep = copy.deepcopy(self.report)
        next(f for x in rep["sections"] for f in x["findings"])["citations"].append(99)
        self.assertTrue(any("unknown source [99]" in p for p in validate_report(rep)))
        rep = copy.deepcopy(self.report)
        next(f for x in rep["sections"] for f in x["findings"])["evidence"] = []
        self.assertTrue(any("no evidence" in p for p in validate_report(rep)))

    def test_gaps_detected_when_claims_are_only_partially_supported_or_conflicted(self):
        # Scenario where findings are partially supported (single source) and conflicts exist
        rep = self.report
        gaps_sec = next(s for s in rep["sections"] if s["key"] == "gaps")
        gap_texts = [p["text"] for p in gaps_sec["paragraphs"] if p["kind"] == "gap"]
        self.assertTrue(any("Corroboration gap" in t for t in gap_texts))
        self.assertTrue(any("Unresolved conflict" in t for t in gap_texts))
        self.assertNotIn("No gaps were detected in the recorded data.", [p["text"] for p in gaps_sec["paragraphs"]])


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.s, self.inp, _ = scenario()
        self.report = build_report(self.inp.snapshot("rA", NOW))

    def test_markdown_keeps_citations_and_labels(self):
        md = to_markdown(self.report)
        self.assertIn(DEMO_BANNER, md)
        self.assertRegex(md, r"\[1\] .*https://")
        self.assertIn("**PARTIALLY SUPPORTED**", md)
        self.assertIn("**CONTRADICTED**", md)
        self.assertIn("## 16. Sources", md)
        cited = set(re.findall(r"\[(\d+)\]", md))
        self.assertTrue({str(c["n"]) for c in self.report["citations"]} <= cited)

    def test_json_round_trips(self):
        self.assertEqual(json.loads(to_json(self.report)), json.loads(json.dumps(self.report, default=str)))

    def test_pdf_structure_is_valid(self):
        pdf = to_pdf(self.report)
        self.assertTrue(pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF"))
        xref = int(re.search(rb"startxref\n(\d+)", pdf).group(1))
        self.assertTrue(pdf[xref:].startswith(b"xref"))
        offs = [int(m) for m in re.findall(rb"(\d{10}) 00000 n", pdf)]
        for i, o in enumerate(offs, 1):
            self.assertTrue(pdf[o:].startswith(b"%d 0 obj" % i))
        self.assertEqual(int(re.search(rb"/Count (\d+)", pdf).group(1)), pdf.count(b"/Type /Page "))
        self.assertIn(b"Executive Summary", pdf)
        self.assertIn(b"DEMO / MOCK DATA", pdf)

    def test_pdf_escapes_special_characters_and_survives_non_latin_text(self):
        rep = copy.deepcopy(self.report)
        rep["title"] = "Report (draft) \\ \u0645\u0631\u062d\u0628\u0627"
        pdf = to_pdf(rep)
        self.assertIn(b"\\(draft\\)", pdf)
        self.assertIn(b"????", pdf)  # documented limitation: Latin-1 only

    def test_exports_do_not_mutate_the_report(self):
        before = copy.deepcopy(self.report)
        to_markdown(self.report), to_json(self.report), to_pdf(self.report)
        self.assertEqual(self.report, before)


class ReportServiceTests(unittest.TestCase):
    def setUp(self):
        self.s, self.inp, _ = scenario()
        self.repo = MemReports()
        self.svc = ReportService(self.inp, self.repo, clock=lambda: NOW)
        self.sc = Scope("wA", "rA")

    def test_versions_are_immutable_and_increment(self):
        r1 = self.svc.generate(self.sc)
        frozen = json.dumps(r1.content, sort_keys=True, default=str)
        self.s.svc.create_claim(Scope("wA", "rA", "t1", "market"), "A brand new market claim without evidence", "trend")
        r2 = self.svc.generate(self.sc)
        self.assertEqual((r1.version, r2.version), (1, 2))
        self.assertEqual(json.dumps(self.repo.get_report("rA", 1).content, sort_keys=True, default=str), frozen)  # v1 unchanged
        self.assertEqual(self.svc.get(self.sc).version, 2)
        self.assertEqual(self.svc.get(self.sc, 1).version, 1)

    def test_scope_is_enforced_and_missing_reports_are_not_found(self):
        for bad in (Scope("wB", "rA"), Scope("wA", "unknown")):
            with self.assertRaises(EvidenceError) as cm:
                self.svc.generate(bad)
            self.assertEqual(cm.exception.code, "not_found")
        with self.assertRaises(EvidenceError):
            self.svc.get(self.sc)  # nothing generated yet
        with self.assertRaises(EvidenceError):
            self.svc.get(Scope("wB", "rA"))

    def test_export_formats_and_read_only_behaviour(self):
        self.svc.generate(self.sc)
        counts = (len(self.s.repo.list_claims("rA")), len(self.s.repo.list_evidence("rA")), len(self.s.repo.list_sources("rA")))
        for fmt, ctype, name in (("md", "text/markdown", ".md"), ("json", "application/json", ".json"),
                                  ("pdf", "application/pdf", ".pdf"), ("csv", "text/csv", ".csv")):
            payload, ct, fn = self.svc.export(self.sc, fmt)
            self.assertTrue(ct.startswith(ctype) and fn.endswith(name) and payload)
        self.assertEqual(counts, (len(self.s.repo.list_claims("rA")), len(self.s.repo.list_evidence("rA")), len(self.s.repo.list_sources("rA"))))
        self.assertEqual(len(self.repo.rows), 1)  # exporting never creates a report
        with self.assertRaises(EvidenceError) as cm:
            self.svc.export(self.sc, "docx")
        self.assertEqual(cm.exception.code, "invalid")

    def test_csv_export_structure_and_injection_safety(self):
        """CSV must have UTF-8 BOM, required headers, and safely neutralise spreadsheet injection."""
        import csv, io
        from app.reporting.export import to_csv, _csv_safe

        # Injection safety: any cell starting with =, +, -, @ must be tab-prefixed
        for dangerous in ("=SUM(A1)", "+1+1", "-CMD", "@SUM"):
            self.assertTrue(_csv_safe(dangerous).startswith("\t"), f"injection not defused: {dangerous!r}")
        # Normal values are unchanged
        for safe in ("hello", "123", "", None, "No formula here"):
            result = _csv_safe(safe)
            self.assertFalse(result.startswith("\t"), f"safe value incorrectly prefixed: {safe!r}")

        # Build a minimal report and check CSV output
        self.svc.generate(self.sc)
        payload, ct, fn = self.svc.export(self.sc, "csv")
        self.assertTrue(ct.startswith("text/csv"))
        self.assertTrue(fn.endswith(".csv"))
        self.assertIsInstance(payload, bytes)
        # UTF-8 BOM must be present (for Excel compatibility)
        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"), "CSV missing UTF-8 BOM for Excel compatibility")
        # Must parse as valid CSV
        text = payload.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        self.assertTrue(len(rows) >= 1, "CSV must have at least a header row")
        header = rows[0]
        for required_col in ("Section", "Claim", "Status", "Confidence", "Citations"):
            self.assertIn(required_col, header, f"Missing required CSV column: {required_col}")

    def test_audit_hook_runs_once_per_persisted_version(self):
        seen = []
        self.svc.generate(self.sc, audit_hook=lambda db, rec: seen.append(rec.version))
        self.svc.generate(self.sc, audit_hook=lambda db, rec: seen.append(rec.version))
        self.assertEqual(seen, [1, 2])

    def test_version_race_is_retried(self):
        class Racy(MemReports):
            def add_report(self, rec, audit_hook=None):
                if not getattr(self, "raced", False):
                    self.raced = True
                    other = copy.deepcopy(rec)
                    super().add_report(other)  # another worker won version 1
                super().add_report(rec, audit_hook)
        svc = ReportService(self.inp, Racy(), clock=lambda: NOW)
        self.assertEqual(svc.generate(self.sc).version, 2)


if __name__ == "__main__":
    unittest.main()
