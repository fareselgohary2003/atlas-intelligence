# Evidence system (Slice 3)

## Layers (never collapsed)
SOURCE (retrieved page) -> EVIDENCE (verbatim excerpt of a source) -> CLAIM (proposition) -> VERIFICATION (append-only assessment)
-> [ANALYSIS, REPORT: later slices]. Claims are born `proposed`; only `verify_claim` (not granted to research agents) moves them.

## Write path
All writes go through `EvidenceService` (`app/evidence/service.py`) over the `EvidenceRepository` port; tools call the service, never
repositories. The scope (workspace, research, task, agent) comes from the engine's `ToolContext`, never from tool arguments.
- **Ownership:** every call checks `research.workspace_id == scope.workspace_id`; every repository query filters by `research_id`;
  DB composite FKs `(id, research_id)` make cross-research references impossible. Foreign and missing ids return the same message.
- **Grounding:** `create_evidence` rejects excerpts not found (whitespace/case-insensitive) in the stored source text and records the offset.
- **Idempotency keys:** claim = sha(research, normalized text, type); evidence = sha(research, source, normalized excerpt, claim);
  conflict = sha(type, sorted claim ids); follow-up task id = sha(parent task, proposal key); source = canonical URL / URL / content-hash
  lookup (+ unique constraints as race backstop); agent_runs unique (task, attempt).
- **Immutability:** evidence, verification rows and claim text/type never change (the service exposes no update; Postgres triggers enforce it).
  Duplicate sources keep one stable id; extra URLs are appended to `aliases`.

## Verification (`app/evidence/verification.py`)
Deterministic rules first: evidence/source exist and belong to the same research, non-empty excerpt, numeric value present in a supporting
excerpt, independence clustering (same content hash or publisher = one source), freshness (<= 5 years), unresolved direct contradictions.
No valid evidence => `insufficient_evidence` with no LLM call. An optional judge only reclassifies stance per excerpt.
Decision: >=2 independent supporters => supported; 1 authoritative+direct => supported (confidence capped MEDIUM); 1 weaker => partially_supported (LOW);
supporters and contradictors => partially_supported (LOW, "contested"); only contradictors => contradicted.

## Evidence quality (heuristic, explainable)
Per evidence: authority, recency, directness, specificity, extraction (each with a note). Per claim also independence and corroboration.
Weights are stored with the components; level HIGH >= .75, MEDIUM >= .5, else LOW. A heuristic, not a probability.

## Conflicts (`app/evidence/conflicts.py`)
Same metric+unit, values differ > 1%. Classified before flagging: shared source => `duplicate_or_derived_source`; differing period / geography /
definition / methodology / population => scope type, severity `info`, `explained_by_scope` (NOT a contradiction); same stated period+geography and
gap >= 30% => `direct_contradiction`; otherwise `numerical_disagreement` (`needs_review` when scope is not stated on both sides).
Independent supporting vs contradicting evidence on one claim also yields `direct_contradiction`.

## Agents
`AgentRegistry` validates definitions, grants tools (default deny) and produces engine runners. The Research Manager plans only for registered
agents and turns agent follow-up *proposals* into tasks (bounded by `max_replans`; follow-up tasks do not request further follow-ups).
`MarketResearchAgent` and `CompetitorResearchAgent` share `ResearchPipelineAgent` (search -> fetch -> extract -> save_source -> LLM extraction of
verbatim findings -> claims + evidence -> gap detection). Pricing is `available` only when a grounded pricing claim states a price.

## Demo mode
`app/demo/provider.py`: fictional pages on the reserved `.invalid` TLD; every record `is_demo=true`. Needs `DEMO_MODE=true` AND
`WEB_SEARCH_PROVIDER=demo`; `create_search_provider` rejects "demo", so production cannot select it. Extraction still needs `LLM_API_KEY`.

## Known limitations
- Attributes (metric/value/period/geography/definition...) come from an LLM; conflict classification is only as good as they are.
- Numeric grounding matches the number as written; no unit conversion ("2 billion" vs 2000000000).
- Stance is asserted by the extracting agent unless a judge is configured.
- Only market and competitor agents exist; customer/pricing/regulation/risk agents, the Fact Checker agent, analysis and reports come later.
- The claims list endpoint does one verification lookup per claim (N+1, page size <= 200).

## Fact checker, replanning, reports, usage (slices 4-5)
- `FactCheckerAgent` lists claims still `proposed`/`insufficient_evidence`, calls `verify_claim`, reports new conflicts and proposes follow-ups
  with reason codes (INSUFFICIENT_EVIDENCE, VERIFICATION_FAILED, LOW_SOURCE_QUALITY, CONFLICT_DETECTED). Scope differences are not gaps.
  The manager appends a `verify` task to every plan (runs when dependencies have *settled*, so a failed research task cannot block verification)
  and a `v-*` re-verification task after each replan. `max_replans` is a hard cap; follow-up tasks do not request further follow-ups.
- Reports (`app/reporting`): pure function of stored records. Every finding is a stored claim quoted verbatim with citations resolved through stored
  evidence; claims without evidence are gaps, unverified claims are labelled UNVERIFIED, contradicted claims cite contradicting evidence.
  `validate_report` runs on every build and refuses to emit an untraceable report. Versions are immutable; exports (md/json/pdf) render a stored version.
  The "Opportunities" section is intentionally "not generated": it needs the (not yet built) Analyst synthesis step.
- Usage: `MeteredLLM` records per-call tokens (as reported by the provider), latency and failures; cost only when `LLM_PRICE_*` are set. Never stores prompts.
