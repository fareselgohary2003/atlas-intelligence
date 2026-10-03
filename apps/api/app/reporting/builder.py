"""Deterministic, evidence-traceable report builder. Pure function of stored records: no LLM, no invented facts.
Every finding's text IS a stored claim, cited to sources through stored evidence. Claims without evidence are never findings;
they are listed as gaps. Unverified claims are labelled UNVERIFIED, never presented as facts."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

AREAS = (("market", "Market Analysis", ("market_size", "market_growth", "market_segment", "trend")),
         ("customer", "Customer & Demand Analysis", ("adoption", "customer_need")),
         ("competitor", "Competitor Analysis", ("competitor_profile", "positioning")),
         ("pricing", "Pricing Analysis", ("pricing",)),
         ("regulatory", "Regulatory Considerations", ("regulation",)),
         ("risk", "Risk Analysis", ("risk",)))
GROUP = {"supported": "verified", "partially_supported": "partial", "insufficient_evidence": "uncertain", "proposed": "uncertain", "contradicted": "contradicted"}
LABEL = {"verified": "VERIFIED", "partial": "PARTIALLY SUPPORTED", "uncertain": "UNVERIFIED", "contradicted": "CONTRADICTED"}
CONF_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNVERIFIED": 3}
DEMO_BANNER = "DEMO / MOCK DATA: this report was generated from fictional mock sources and does not describe the real world."
DISCLAIMER = "Regulatory content records what sources state; it is not legal advice."


@dataclass
class ReportInputs:
    research: dict                  # id, title, objective, industry, geography, target_customer, time_range, is_demo
    claims: list
    evidence: list
    sources: list
    verifications: dict             # claim_id -> latest VerificationRecord
    conflicts: list
    tasks: list                     # [{"key","title","agent","status","error"}]
    generated_at: datetime
    analysis: list = field(default_factory=list)   # AnalysisRecord: inferences citing claims


def _p(text, kind="text"):
    return {"kind": kind, "text": text}


def build_report(inp: ReportInputs) -> dict:
    src = {s.id: s for s in inp.sources}
    ev_by_claim = defaultdict(list)
    for e in inp.evidence:
        if e.claim_id:
            ev_by_claim[e.claim_id].append(e)
    claims = sorted(inp.claims, key=lambda c: (c.created_at, c.id))
    numbers: dict = {}

    def cite(source_id):
        return numbers.setdefault(source_id, len(numbers) + 1)

    findings, unsupported = {}, []

    def make_finding(c):
        group = GROUP[c.status]
        want = "contradicts" if group == "contradicted" else "supports"
        ev = [e for e in ev_by_claim.get(c.id, []) if e.stance == want and e.source_id in src]
        if not ev:
            unsupported.append(c)
            return None
        v = inp.verifications.get(c.id)
        cites = sorted({cite(e.source_id) for e in ev})
        return {"claim_id": c.id, "text": c.text, "claim_type": c.claim_type, "status": c.status, "group": group, "label": LABEL[group],
                "confidence": c.confidence, "rationale": v.rationale if v else None, "citations": cites, "is_demo": c.is_demo,
                "attributes": {k: c.attributes[k] for k in ("metric", "value", "unit", "period", "geography", "definition") if k in c.attributes},
                "evidence": [{"id": e.id, "n": cite(e.source_id), "excerpt": e.excerpt, "location": e.location} for e in ev]}

    area_of = {t: (k, title) for k, title, types in AREAS for t in types}
    by_area = {k: [] for k, _, _ in AREAS}
    for k, _, types in AREAS:  # deterministic numbering: area order, then claim order
        for c in claims:
            if c.claim_type in types:
                f = make_finding(c)
                if f:
                    findings[c.id] = f
                    by_area[k].append(f)
    for c in claims:
        if c.id not in findings and c not in unsupported and c.claim_type not in area_of:
            f = make_finding(c)
            if f:
                findings[c.id] = f
    counts = Counter(GROUP[c.status] for c in claims)
    by_kind = {"opportunity": [], "uncertainty": [], "risk_inference": []}
    omitted = []
    for a in sorted(inp.analysis, key=lambda a: (a.created_at, a.id)):
        basis = [findings.get(cid) for cid in a.basis_claim_ids]
        if not basis or any(b is None for b in basis):  # an inference is shown only if every claim it rests on is an evidence-backed finding
            omitted.append(a)
            continue
        by_kind[a.kind].append({"analysis_id": a.id, "kind": a.kind, "label": "UNCERTAINTY" if a.kind == "uncertainty" else "INFERENCE", "text": a.text,
                                "citations": sorted({n for b in basis for n in b["citations"]}), "is_demo": a.is_demo,
                                "basis": [{"claim_id": b["claim_id"], "text": b["text"], "label": b["label"], "citations": b["citations"]} for b in basis]})
    n_analysis = sum(len(v) for v in by_kind.values())
    is_demo = bool(inp.research.get("is_demo")) or any(x.is_demo for x in (*claims, *inp.sources, *inp.evidence))

    def tally(fs):
        n = Counter(f["group"] for f in fs)
        return f"{len(fs)} evidence-backed finding(s): {n['verified']} verified, {n['partial']} partially supported, {n['uncertain']} unverified, {n['contradicted']} contradicted."

    sections = []
    verified = sorted((f for f in findings.values() if f["group"] == "verified"), key=lambda f: (CONF_ORDER.get(f["confidence"], 9), f["claim_id"]))
    exec_p = [_p(DEMO_BANNER, "note")] if is_demo else []
    exec_p.append(_p(f"This report is based on {len(inp.sources)} source(s), {len(inp.evidence)} evidence excerpt(s) and {len(claims)} claim(s). "
                     f"{counts['verified']} claim(s) are supported, {counts['partial']} partially supported, {counts['contradicted']} contradicted "
                     f"and {counts['uncertain']} unverified or lacking evidence."))
    if n_analysis:
        exec_p.append(_p(f"{n_analysis} analytical inference(s) are included and labelled INFERENCE or UNCERTAINTY; they are not sourced facts."))
    if not claims:
        exec_p.append(_p("No claims were recorded for this research; there are no findings to report.", "gap"))
    sections.append({"key": "executive_summary", "title": "Executive Summary", "paragraphs": exec_p, "findings": verified[:5]})
    obj = inp.research
    scope = [f"{k}: {obj[v]}" for k, v in (("Industry", "industry"), ("Geography", "geography"), ("Target customer", "target_customer"), ("Time range", "time_range")) if obj.get(v)]
    sections.append({"key": "objective", "title": "Research Objective", "paragraphs": [_p(obj.get("objective", ""))] + ([_p("Scope - " + "; ".join(scope))] if scope else []), "findings": []})
    per_agent = defaultdict(Counter)
    for t in inp.tasks:
        per_agent[t["agent"]][t["status"]] += 1
    meth = [_p(f"{a}: {sum(c.values())} task(s), {c['completed']} completed" + (f", {c['failed']} failed" if c["failed"] else "") + (f", {c['skipped']} skipped" if c["skipped"] else "") + ".")
            for a, c in sorted(per_agent.items())] or [_p("No task records are available for this research.", "gap")]
    meth.append(_p("Sources are retrieved through SSRF-protected fetching and deduplicated. Evidence excerpts must appear verbatim in the stored source text. "
                   "Claims start unverified and are verified by deterministic rules (evidence integrity, quote grounding, independent corroboration, "
                   "contradictions, freshness). Conflicts are classified before being called contradictions."))
    sections.append({"key": "methodology", "title": "Methodology", "paragraphs": meth, "findings": []})
    sections.append({"key": "key_findings", "title": "Key Findings", "findings": verified,
                     "paragraphs": [_p(tally(verified))] if verified else [_p("No claim reached the supported state; see the area sections for partially supported findings.", "gap")]})
    gaps = []
    for k, title, types in AREAS:
        fs = by_area[k]
        paras = [_p(tally(fs))] if fs else [_p("No evidence-backed findings were recorded for this area.", "gap")]
        if not fs:
            gaps.append(f"{title}: no evidence-backed findings.")
        if k == "regulatory":
            paras.append(_p(DISCLAIMER, "note"))
        sections.append({"key": k, "title": title, "paragraphs": paras, "findings": fs, "analysis": by_kind["risk_inference"] if k == "risk" else []})
    opp = by_kind["opportunity"]
    sections.append({"key": "opportunities", "title": "Opportunities", "findings": [], "analysis": opp, "paragraphs": (
        [_p("Opportunities below are INFERENCES drawn from the cited claims, not sourced facts.", "note")] if opp else
        [_p("Not generated: no analysis items were recorded. Opportunities are inferences produced by the Analyst step and appear only when they cite "
            "verified or partially verified claims.", "gap")])})
    by_id = {c.id: c for c in claims}
    conf_items = []
    for x in inp.conflicts:
        a, b = by_id.get(x.claim_id), by_id.get(x.other_claim_id) if x.other_claim_id else None
        side = lambda c, sid: None if c is None else {"id": c.id, "text": c.text, "citations": [cite(sid)] if sid in src else findings.get(c.id, {}).get("citations", [])}
        conf_items.append({"conflict_id": x.id, "conflict_type": x.conflict_type, "severity": x.severity, "resolution_status": x.resolution_status,
                           "explanation": x.explanation, "claim_a": side(a, x.source_a_id), "claim_b": side(b, x.source_b_id)})
    uncertain = [f for f in findings.values() if f["group"] in ("uncertain", "contradicted")]
    unc_p = [_p(f"{len(conf_items)} conflict(s) recorded.")] if conf_items else [_p("No conflicts were detected.")]
    sections.append({"key": "conflicts", "title": "Conflicts / Uncertainties", "paragraphs": unc_p, "findings": uncertain, "conflicts": conf_items, "analysis": by_kind["uncertainty"]})
    quals = [e.quality.get("total") for e in inp.evidence if isinstance(e.quality.get("total"), (int, float))]
    lv = Counter(e.quality.get("level") for e in inp.evidence if e.quality.get("level"))
    st = Counter(s.source_type for s in inp.sources)
    qp = [_p(f"Sources by type: {', '.join(f'{n} {t}' for t, n in sorted(st.items())) or 'none'}."),
          _p(f"Evidence quality levels: {', '.join(f'{n} {k}' for k, n in sorted(lv.items())) or 'none'}" + (f"; mean score {sum(quals) / len(quals):.2f}." if quals else ".")),
          _p("Quality scores are transparent heuristics (source type, recency, directness, specificity, extraction), not probabilities.", "note")]
    sections.append({"key": "evidence_quality", "title": "Evidence Quality", "paragraphs": qp, "findings": []})
    failed = [t for t in inp.tasks if t["status"] in ("failed", "skipped")]
    gap_p = [_p(g, "gap") for g in gaps] + [_p(f"Task '{t['title']}' ({t['agent']}) {t['status']}.", "gap") for t in failed]
    gap_p += [_p(f"Analysis item omitted because a claim it cites has no evidence-backed finding: {a.text[:90]}", "gap") for a in omitted]
    gap_p += [_p(f"Claim has no supporting evidence and is not reported as a finding: {c.text}", "gap") for c in unsupported]
    if claims and counts["verified"] == 0 and counts["partial"] > 0:
        gap_p.append(_p(f"Corroboration gap: {counts['partial']} finding(s) are partially supported by single sources and lack independent corroboration to reach fully supported status.", "gap"))
    elif counts["partial"] > 0:
        gap_p.append(_p(f"Corroboration gap: {counts['partial']} finding(s) remain partially supported and require independent corroboration.", "gap"))
    if counts["uncertain"] > 0:
        gap_p.append(_p(f"Verification gap: {counts['uncertain']} claim(s) remain unverified or lack conclusive verification.", "gap"))
    for conf in conf_items:
        gap_p.append(_p(f"Unresolved conflict ({conf['conflict_type'].replace('_', ' ')}): {conf['explanation']}", "gap"))
    for k, title, _ in AREAS:
        fs = by_area[k]
        if fs and all(f["group"] != "verified" for f in fs):
            gap_p.append(_p(f"{title}: findings in this area lack fully verified support and rely on single-source or unverified evidence.", "gap"))
    sections.append({"key": "gaps", "title": "Research Gaps", "paragraphs": gap_p or [_p("No gaps were detected in the recorded data.")], "findings": []})
    sections.append({"key": "conclusion", "title": "Conclusion", "findings": [], "paragraphs": [
        _p(f"Of {len(claims)} recorded claim(s), {counts['verified']} are supported, {counts['partial']} partially supported, {counts['contradicted']} contradicted "
           f"and {counts['uncertain']} unverified. This report states nothing beyond the recorded claims and their evidence."),
        _p("Unverified and partially supported findings should be treated as leads, not conclusions.", "note")]})
    citations = [{"n": n, "source_id": sid, "title": src[sid].title, "url": src[sid].url, "publisher": src[sid].publisher,
                  "published_at": src[sid].published_at.isoformat() if src[sid].published_at else None,
                  "retrieved_at": src[sid].retrieved_at.isoformat(), "source_type": src[sid].source_type, "is_demo": src[sid].is_demo}
                 for sid, n in sorted(numbers.items(), key=lambda kv: kv[1])]
    extra = len(inp.sources) - len(citations)
    sections.append({"key": "sources", "title": "Sources", "findings": [], "paragraphs": [_p(f"{extra} additional collected source(s) were not cited.")] if extra else []})
    appendix = [findings[c.id] for c in claims if c.id in findings]
    sections.append({"key": "claims_appendix", "title": "Claims and Supporting Evidence", "findings": appendix,
                     "paragraphs": [_p(f"{len(unsupported)} claim(s) without evidence are omitted here and listed under Research Gaps.", "gap")] if unsupported else []})
    report = {"title": f"Research Report: {obj.get('title', 'Untitled')}", "research_id": obj.get("id"), "generated_at": inp.generated_at.isoformat(),
              "is_demo": is_demo, "provenance": DEMO_BANNER if is_demo else None, "sections": sections, "citations": citations,
              "stats": {"sources": len(inp.sources), "evidence": len(inp.evidence), "claims": len(claims), "by_group": dict(counts),
                        "conflicts": len(inp.conflicts), "unsupported_claims": len(unsupported), "analysis": n_analysis}}
    problems = validate_report(report)
    if problems:
        raise ValueError("Report failed traceability validation: " + "; ".join(problems[:3]))
    return report


def validate_report(report: dict) -> list:
    """Traceability audit: every finding needs evidence and citations that resolve to listed sources."""
    nums = {c["n"] for c in report.get("citations", [])}
    problems = []
    for s in report.get("sections", []):
        for f in s.get("findings", []):
            if not f.get("evidence") or not f.get("citations"):
                problems.append(f"finding {f.get('claim_id')} has no evidence or citations")
            problems += [f"finding {f.get('claim_id')} cites unknown source [{n}]" for n in f.get("citations", []) if n not in nums]
            problems += [f"evidence {e.get('id')} cites unknown source [{e.get('n')}]" for e in f.get("evidence", []) if e.get("n") not in nums]
        for a in s.get("analysis", []):
            if not a.get("basis") or not a.get("citations") or a.get("label") not in ("INFERENCE", "UNCERTAINTY"):
                problems.append(f"analysis {a.get('analysis_id')} lacks basis, citations or an inference label")
            problems += [f"analysis {a.get('analysis_id')} cites unknown source [{n}]" for n in a.get("citations", []) if n not in nums]
        for c in s.get("conflicts", []):
            for side in ("claim_a", "claim_b"):
                problems += [f"conflict {c['conflict_id']} cites unknown source [{n}]" for n in ((c.get(side) or {}).get("citations", [])) if n not in nums]
    return problems
