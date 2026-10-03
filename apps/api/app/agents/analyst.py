"""Analyst: synthesizes verified / partially verified claims into labelled INFERENCES. It reads claims (not sources), may not create
facts, and every saved item is checked by EvidenceService (existing supported/partial claims only, no new figures)."""
import json

from app.agents.framework import Agent, AgentContext, AgentDefinition, AgentResult, AgentTask
from app.agents.state import LLMOutputError
from app.evidence.domain import ANALYSIS_KINDS

ANALYST_SYSTEM = (
    "You are the analyst of an enterprise research platform. Synthesize ONLY the provided claims into inferences. "
    'Return ONLY JSON: {"items":[{"kind":"opportunity|uncertainty|risk_inference","text":"<the inference>","basis_claim_ids":["<claim id>"]}]}. '
    "Rules: every item must cite one or more provided claim ids; do not introduce facts, names or numbers that are not in the cited claims; "
    "phrase opportunities and risks as inferences, not as facts; describe weakly supported claims as uncertainties.")


def parse_items(raw):
    items = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise LLMOutputError("Analyst output must contain an 'items' list")
    ok, bad = [], 0
    for i in items[:12]:
        try:
            kind, text, ids = i["kind"], str(i["text"]), [str(x) for x in i["basis_claim_ids"]]
            assert kind in ANALYSIS_KINDS and ids
        except (KeyError, TypeError, AssertionError, AttributeError):
            bad += 1
            continue
        ok.append({"kind": kind, "text": text, "basis_claim_ids": ids})
    return ok, bad


class AnalystAgent(Agent):
    definition = AgentDefinition("analyst", "Analyst Agent",
                                 "Synthesizes verified and partially verified claims into labelled inferences: opportunities, uncertainties and risks.",
                                 ("opportunity_synthesis", "uncertainty_analysis", "risk_inference"),
                                 ("list_claims", "list_conflicts", "save_analysis", "update_task"))

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        claims = ctx.call("list_claims", {"statuses": ["supported", "partially_supported"], "limit": 200})["claims"]
        if not claims:
            return AgentResult("insufficient", "No verified or partially verified claims are available to analyse.", metadata={"saved": 0})
        conflicts = ctx.call("list_conflicts", {})["conflicts"]
        payload = {"goal": task.goal[:1000], "claims": claims,
                   "conflicts": [{k: c[k] for k in ("claim_id", "conflict_type", "resolution_status", "explanation")} for c in conflicts]}
        items, invalid = parse_items(ctx.llm.structured_output(ANALYST_SYSTEM, json.dumps(payload)))  # malformed output fails the task visibly
        saved, rejected = [], []
        for it in items:
            out, res = ctx.try_call("save_analysis", it)
            if out is None:
                rejected.append(res.error)
                continue
            ctx.event("ANALYSIS_SAVED", action=it["kind"])
            saved.append(out["analysis_id"])
        counts = {k: sum(1 for i in items if i["kind"] == k) for k in ANALYSIS_KINDS}
        return AgentResult("completed" if saved else "insufficient",
                           f"Recorded {len(saved)} inference(s) from {len(claims)} claim(s); {len(rejected) + invalid} rejected.",
                           metadata={"saved": len(saved), "analysis_ids": saved, "rejected": rejected[:10], "invalid_items": invalid, "proposed_by_kind": counts})
