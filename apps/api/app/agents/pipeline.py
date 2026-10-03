"""Shared research pipeline: search -> fetch -> extract -> save_source -> LLM extraction of verbatim findings -> claims + evidence
-> gap detection. Subclasses declare WHAT to look for; all infrastructure access goes through AgentContext/ToolRegistry.
Agents create claims but never verify them (verify_claim is not in their allowed tools)."""
import json
from urllib.parse import urlsplit

from app.agents.framework import Agent, AgentContext, AgentResult, AgentTask
from app.agents.state import LLMOutputError
from app.evidence.verification import level


RESEARCH_TOOLS = ("web_search", "fetch_url", "extract_page_content", "save_source", "create_claim", "create_evidence", "request_research", "update_task")


def extraction_prompt(kind: str, claim_types: tuple, attributes: str, rules: str = "") -> str:
    return (f"You extract {kind} evidence for a research task from ONE source. Return ONLY JSON: "
            '{"findings":[{"excerpt":"<text copied EXACTLY from the source>","claim":"<one factual statement the excerpt supports>",'
            f'"claim_type":"<{"|".join(claim_types)}>","stance":"supports|contradicts","attributes":{{{attributes}}}}}]}}. '
            "Rules: copy excerpts verbatim; never estimate, compute or invent facts; omit attributes the source does not state; "
            f'{rules} If nothing relevant is present return {{"findings":[]}}.')


def grounded_in(text: str, excerpt: str) -> bool:
    return " ".join(excerpt.split()).lower() in " ".join(text.split()).lower()


def parse_findings(raw, allowed_types):
    items = raw.get("findings") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise LLMOutputError("Extraction output must contain a 'findings' list")
    ok, bad = [], 0
    for i in items[:20]:
        try:
            ex, cl = " ".join(str(i["excerpt"]).split()), " ".join(str(i["claim"]).split())
            ct, st, at = i["claim_type"], i.get("stance", "supports"), i.get("attributes") or {}
            assert 10 <= len(ex) <= 1000 and 10 <= len(cl) <= 500 and ct in allowed_types
            assert st in ("supports", "contradicts") and isinstance(at, dict)
        except (KeyError, TypeError, AssertionError, AttributeError):
            bad += 1
            continue
        ok.append({"excerpt": ex, "claim": cl, "claim_type": ct, "stance": st, "attributes": at})
    return ok, bad


class ResearchPipelineAgent(Agent):
    dimensions: tuple = ()        # (label, claim_type, title keywords)
    claim_types: tuple = ()
    query_suffixes: tuple = ()
    extract_system: str = ""
    max_sources, results_per_query, max_gap_requests, source_chars = 6, 5, 2, 8000

    def queries(self, task: AgentTask) -> list:
        base = task.title.strip()
        return list(dict.fromkeys([base] + [f"{base} {s}" for s in self.query_suffixes]))[:3]

    def expected_dimensions(self, task: AgentTask) -> list:
        t = task.title.lower()
        hit = [d for d in self.dimensions if any(k in t for k in d[2])]
        return hit or list(self.dimensions[:1])

    def finalize(self, task, claims: list, md: dict) -> None:
        """Agent-specific structured findings (added to result.metadata)."""

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        md = {"queries": [], "fetch_failures": [], "extraction_failures": 0, "invalid_findings": 0, "rejected_findings": [],
              "confidence_basis": "mean evidence quality; claims remain unverified"}
        results, seen = [], set()
        for q in self.queries(task):
            md["queries"].append(q)
            out = ctx.call("web_search", {"query": q, "count": self.results_per_query})  # search failure = visible task failure
            for r in out["results"]:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    results.append(r)
        ctx.event("SOURCE_FOUND", counts={"results": len(results)})
        ctx.progress(25, f"{len(results)} search results")
        saved = []
        for r in results[:self.max_sources]:
            fail = lambda cat: md["fetch_failures"].append({"host": urlsplit(r["url"]).hostname, "category": cat})
            page, res = ctx.try_call("fetch_url", {"url": r["url"]})
            if page is None:
                fail(res.error_category)
                continue
            ext, res = ctx.try_call("extract_page_content", {"html": page["text"], "content_type": page["content_type"], "base_url": page["url"]})
            if ext is None:
                fail(res.error_category)
                continue
            args = {"url": page["url"], "text": ext["text"], "title": ext.get("title"), "publisher": r.get("publisher"),
                    "published_at": ext.get("published_at") or r.get("published_at"), "canonical_url": ext.get("canonical_url"),
                    "metadata": {"search_rank": r.get("rank")}}
            src, res = ctx.try_call("save_source", {k: v for k, v in args.items() if v is not None})
            if src is None:
                fail(res.error_category)
                continue
            saved.append({"id": src["source_id"], "title": ext.get("title"), "text": ext["text"], "url": page["url"]})
            ctx.event("SOURCE_SAVED", source={"publisher": src["domain"], "type": src["source_type"]}, action="created" if src["created"] else "matched")
        ctx.progress(55, f"{len(saved)} sources saved")
        claims, evidence, quality = {}, {}, []
        for s in saved:
            try:
                raw = ctx.llm.structured_output(self.extract_system, json.dumps(
                    {"task": task.title, "goal": task.goal[:1000], "source_url": s["url"], "source_title": s["title"],
                     "source_text": s["text"][:self.source_chars]}))
                findings, bad = parse_findings(raw, self.claim_types)
            except LLMOutputError:
                md["extraction_failures"] += 1
                continue
            md["invalid_findings"] += bad
            for f in findings:
                if not grounded_in(s["text"], f["excerpt"]):
                    md["rejected_findings"].append("ungrounded")  # pre-check: no claim is created for an invented quote
                    continue
                cl, res = ctx.try_call("create_claim", {"text": f["claim"], "claim_type": f["claim_type"], "attributes": f["attributes"]})
                if cl is None:
                    md["rejected_findings"].append(res.error_category)
                    continue
                ev, res = ctx.try_call("create_evidence", {"source_id": s["id"], "excerpt": f["excerpt"], "claim_id": cl["claim_id"], "stance": f["stance"]})
                if ev is None:
                    md["rejected_findings"].append(res.error_category)
                    continue
                if cl["created"]:
                    ctx.event("CLAIM_CREATED", claim_id=cl["claim_id"], action=f["claim_type"])
                if ev["created"]:
                    ctx.event("EVIDENCE_CREATED", claim_id=cl["claim_id"])
                claims[cl["claim_id"]] = {"claim_id": cl["claim_id"], "claim_type": f["claim_type"], "attributes": f["attributes"], "source_id": s["id"]}
                evidence[ev["evidence_id"]] = ev["quality_total"]
        self.finalize(task, list(claims.values()), md)
        follow = []
        if not task.id.startswith("f-"):  # follow-up tasks do not request further follow-ups (bounded depth)
            covered = {c["claim_type"] for c in claims.values()}
            for label, ctype, _ in self.expected_dimensions(task):
                if ctype not in covered and len(follow) < self.max_gap_requests:
                    _, res = ctx.try_call("request_research", {"question": f"Find grounded evidence on {label} for: {task.title}",
                                                               "agent": self.definition.id, "reason": "No grounded evidence found in this task"})
                    follow.append(label)
        proposals = ctx.follow_ups.take(task.research_id, task.id)
        conf = level(sum(evidence.values()) / len(evidence)) if evidence else None
        gaps = f"; no grounded evidence for: {', '.join(follow)}" if follow else ""
        fails = f"; {len(md['fetch_failures'])} page(s) could not be retrieved" if md["fetch_failures"] else ""
        return AgentResult("completed" if claims else "insufficient",
                           f"Saved {len(saved)} source(s), recorded {len(claims)} claim(s) with {len(evidence)} evidence excerpt(s){fails}{gaps}.",
                           sorted({s["id"] for s in saved}), sorted(evidence), sorted(claims), proposals, conf, md)
