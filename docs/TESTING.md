# Testing

## Executed in the authoring environment: 214 Python + 9 Node tests, 0 failures
```bash
scripts/run_tests.sh
```
Python modules (stdlib `unittest`, no packages): engine, persistence contract, SSRF, fetch, extraction/sources, search, tool registry, real-socket transport, architecture, verification/conflicts, evidence service contract, agents, fact checker/replanning, reporting, usage + OpenAI-compatible provider over local HTTP, analyst + end-to-end demo, graph/catalog, security core. Node (`node --test`): formatting that never invents numbers, CSRF header logic, event merging, phase/description (no reasoning exposed), graph layout.
Do not use `unittest discover` (it imports integration tests that need third-party packages).

## Written, NOT executed (40 test functions)
`apps/api/tests/integration/*` (SQL repository contract = the same 16 service-contract tests on SQLite, API, auth/CSRF/members/agents/settings/graph, reports, run control, SQL store) and `apps/api/tests/test_api.py`.
```bash
cd apps/api && pip install -r requirements.txt && pytest          # expect all to run; fix what fails
```
SQLite does not enforce composite FKs or Postgres triggers; run a Postgres session for those (`docs/UNVERIFIED.md`).

## Method
Contract tests share one suite between the in-memory test double and the SQL repository. Adversarial cases: cross-research/workspace references, ungrounded quotes, invented numbers in analysis, duplicate sources/claims/events, invalid agents/tools, cycles, failed dependencies, cancellation, stale workers, invalid LLM JSON, redirect-to-private-IP, DNS rebinding, token forgery/alg confusion, CSRF. Mutation checks listed in `docs/SECURITY.md` and `docs/EVIDENCE.md`. Parallel-execution determinism was checked by repeating the end-to-end suite 10-12 times.

## Bugs found by testing during development (all fixed with regression tests)
Cancelled tasks never persisted; same publisher counted as an independent dispute; `str.format` on a JSON prompt; non-JSON LLM replies unhandled; demo search ranking; report traceability validation not enforced at build time; demo analysis and follow-up selection depended on task scheduling order; JWT algorithm check untested.
