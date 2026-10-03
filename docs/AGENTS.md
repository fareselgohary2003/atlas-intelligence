# Agents

Registered in `app/agents/catalog.py` (single source of truth); the Research Manager plans only for registered agents. Tool access is default-deny and enforced by the `ToolRegistry`.

| Agent id | Purpose | Allowed tools |
|---|---|---|
| `research_manager` | Plans, schedules verification + analysis, turns gaps into follow-ups (bounded) | none (orchestrator) |
| `market` | Market size, growth, segments, trends | web_search, fetch_url, extract_page_content, save_source, create_claim, create_evidence, request_research, update_task |
| `customer` | Needs, pain points, demand signals | same research tool set |
| `competitor` | Competitor identity, product, customers, positioning; pricing availability is explicit | same research tool set |
| `pricing` | Pricing models/plans/prices; never infers a missing price | same research tool set |
| `regulation` | What sources state about regulation (not legal advice; disclaimer in output) | same research tool set |
| `risk` | Risks that sources document | same research tool set |
| `fact_checker` | Verifies claims, reports conflicts, proposes follow-ups with reason codes | list_claims, list_conflicts, verify_claim, request_research, update_task |
| `analyst` | Labelled inferences (opportunity/uncertainty/risk) citing verified or partially verified claims | list_claims, list_conflicts, save_analysis, update_task |

Least privilege is tested (`tests/test_graph_catalog.py`): only the fact checker can verify, only the analyst can save analysis, verifier and analyst can never create facts.

## Task lifecycle
`Task(pending) -> running -> completed | failed | skipped | cancelled`. Transient tool failures retry (engine `max_attempts`); permanent failures skip only dependents. `verify` and `analyze` tasks are *settled-policy* tasks: they run after their dependencies finish even if some failed. Agents return a result dict (`summary`, `confidence`, `counts`, `follow_up_tasks`, `metadata`); they expose concise activity summaries, never reasoning.

## Research pipeline (research agents)
search -> fetch -> extract -> save_source -> LLM extraction of verbatim findings (validated) -> create_claim -> create_evidence (service rejects ungrounded excerpts) -> gap detection -> follow-up *proposals*. Only the manager turns proposals into tasks (deterministic ids, ranked by reason priority before the cap).

## Events
`RESEARCH_STARTED, PLAN_CREATED, TASK_CREATED, AGENT_STARTED, TOOL_STARTED/COMPLETED/FAILED, SOURCE_FOUND, SOURCE_SAVED, CLAIM_CREATED, EVIDENCE_CREATED, VERIFICATION_STARTED/COMPLETED, CONFLICT_DETECTED, RESEARCH_GAP_DETECTED, REPLAN_REQUESTED, RESEARCH_REPLANNED, ANALYSIS_REQUESTED, ANALYSIS_SAVED, TASK_PROGRESS/COMPLETED/RETRY/FAILED/SKIPPED/CANCELLED, RESEARCH_PAUSED/CANCELLED/COMPLETED/FAILED`. Only whitelisted fields leave the engine (`app/agents/events.py`).
