"""Fact Checker: verifies claims through the verify_claim tool (deterministic rules in EvidenceService), reports conflicts and turns
weaknesses into follow-up PROPOSALS with reason codes. It creates no sources, evidence or claims."""
from collections import Counter

from app.agents.framework import Agent, AgentContext, AgentDefinition, AgentResult, AgentTask

CLAIM_AGENT = {"market_size": "market", "market_growth": "market", "market_segment": "market", "trend": "market", "adoption": "customer",
               "customer_need": "customer", "competitor_profile": "competitor", "positioning": "competitor", "pricing": "pricing",
               "regulation": "regulation", "risk": "risk", "other": "market"}


class FactCheckerAgent(Agent):
    definition = AgentDefinition("fact_checker", "Fact Checker Agent",
                                 "Verifies proposed claims against grounded evidence, surfaces conflicts and requests follow-up research.",
                                 ("claim_verification", "conflict_detection", "gap_detection"),
                                 ("list_claims", "list_conflicts", "verify_claim", "request_research", "update_task"))
    max_proposals = 6

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        pending = sorted(ctx.call("list_claims", {"statuses": ["proposed", "insufficient_evidence"], "limit": 200})["claims"],
                         key=lambda c: (c["claim_type"], c["text"], c["id"]))  # stable order regardless of task scheduling
        before = {c["id"] for c in ctx.call("list_conflicts", {})["conflicts"]}
        ctx.event("VERIFICATION_STARTED", counts={"claims": len(pending)})
        checked, failures = {}, []
        for c in pending:
            r, res = ctx.try_call("verify_claim", {"claim_id": c["id"]})
            if r is None:
                failures.append(res.error_category)
                continue
            checked[c["id"]] = (c, r)
        conflicts = ctx.call("list_conflicts", {})["conflicts"]
        new = [x for x in conflicts if x["id"] not in before]
        for x in new:
            ctx.event("CONFLICT_DETECTED", claim_id=x["claim_id"], conflict_type=x["conflict_type"], action=x["resolution_status"], summary=x["severity"])
        tally = Counter(r["outcome"] for _, r in checked.values())
        ctx.event("VERIFICATION_COMPLETED", counts=dict(tally))
        proposals = []

        def propose(code, claim, ask):
            if len(proposals) >= self.max_proposals:
                return
            ctx.event("RESEARCH_GAP_DETECTED", claim_id=claim["id"], reason_code=code)
            ctx.try_call("request_research", {"question": f"{ask}: {claim['text'][:180]}", "reason_code": code, "reason": code.lower(),
                                              "agent": CLAIM_AGENT.get(claim["claim_type"], "market")})
            proposals.append(code)

        for c, r in checked.values():
            if r["outcome"] == "insufficient_evidence":
                propose("INSUFFICIENT_EVIDENCE", c, "Find grounded evidence for")
            elif r["outcome"] == "contradicted":
                propose("VERIFICATION_FAILED", c, "Re-examine the contradicted claim")
            elif r["outcome"] == "partially_supported" and r["confidence"] == "LOW":
                propose("LOW_SOURCE_QUALITY", c, "Find independent corroboration for")
        by_id = {c["id"]: c for c in ctx.call("list_claims", {"limit": 200})["claims"]}
        for x in conflicts:  # scope differences (explained_by_scope) are not gaps; unresolved medium/high conflicts are
            if x["resolution_status"] in ("unresolved", "needs_review") and x["severity"] in ("medium", "high") and x["claim_id"] in by_id:
                propose("CONFLICT_DETECTED", by_id[x["claim_id"]], "Find evidence to resolve the conflict about")
        summary = ("No claims were awaiting verification." if not pending else
                   f"Verified {len(checked)} claim(s) ({', '.join(f'{n} {k}' for k, n in sorted(tally.items())) or 'none'}); "
                   f"{len(new)} new conflict(s); {len(proposals)} follow-up(s) requested.")
        return AgentResult("completed", summary, follow_up_tasks=ctx.follow_ups.take(task.research_id, task.id),
                           metadata={"outcomes": dict(tally), "verify_failures": failures, "new_conflicts": len(new),
                                     "conflicts_total": len(conflicts), "gap_reasons": proposals, "claims_checked": len(checked)})
