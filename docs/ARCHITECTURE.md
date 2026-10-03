# Architecture

## Layers and dependency direction
`domain (evidence/domain.py, agents/state.py) -> ports (EvidenceRepository, RunStore, ReportRepository) -> services (EvidenceService, ReportService, execute_research) -> adapters (SQL repositories, Celery, providers) -> API / UI`.
Agents -> `ToolRegistry` -> tool implementations -> providers (search / HTTP / LLM). Enforced by `tests/test_architecture.py` (agents may not import network libraries or tool implementations; the engine knows nothing about tools or persistence).
Composition root: `app/services/composition.py` (+ `app/services/llm_selection.py`, `app/tools/wiring.py`). Business logic is not in route handlers or React components.

## Execution
`POST /research/{id}/start` atomically moves `planning -> queued` and enqueues a Celery job (503 + revert if the broker is down). The worker claims the run (atomic update; stale-heartbeat takeover after 60 s), loads persisted state, plans (manager + LLM, validated), and runs the engine: parallel tasks, retries, failure isolation, cooperative pause/cancel polled from the DB, resume without redoing completed work, bounded replanning, then analysis. Every engine event is persisted (event row + task/run rows + audit entry in one transaction) and streamed to the UI over SSE (`Last-Event-ID` resume).

## Data model (PostgreSQL)
users, workspaces, workspace_members, research_projects, research_tasks, agent_runs, agent_events, sources, evidence, claims, claim_sources, verification_results, conflicts, analyses, reports, report_sections, cost_records, audit_logs. Every table carries `research_id` + `workspace_id`; composite FKs `(id, research_id)` tie evidence/claims/verification to one research; unique idempotency keys make retries safe; triggers make evidence, verification, reports, analyses and audit logs immutable.

## Report pipeline
`ReportInputs` (stored records) -> `build_report` (pure; refuses to emit untraceable output) -> immutable version (`reports` + `report_sections`) -> exports render a stored version (Markdown, JSON, PDF).

## Observability
JSON logs with `request_id` (middleware), `research_id`, `task_id`, `agent`, `tool`, `tool_execution_id`; secret redaction; `cost_records` for LLM calls; `audit_logs`.
