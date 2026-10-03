# Demo mode

Fully offline and deterministic: no LLM key, no search key, no internet. Everything is fictional and marked MOCK/DEMO.

```bash
# .env
DEMO_MODE=true
WEB_SEARCH_PROVIDER=demo
LLM_PROVIDER=demo
docker compose up --build        # UNVERIFIED path; the worker must be running
```
Sign in as `demo@atlas.dev` / `demo1234`, open **Saudi B2B SaaS Market Opportunity**, press **Start**. Watch the plan (6 research tasks + verification), live activity, conflicts (18% vs 21% growth is a *definition* difference, not a contradiction), follow-up tasks with reason codes, the analysis step, then open Claims/Evidence/Graph and **Generate** a report (export Markdown/JSON/PDF).

## What is real vs mock
- `app/demo/provider.py`: 8 fictional pages on the reserved `.invalid` TLD (never a real URL). `DemoSearchProvider`/`DemoFetcher` do no network access.
- `app/demo/llm.py` (`DemoLLM`): deterministic planner/extractor/analyst. It emits findings **only** for those pages and builds analysis text only from the claims it is given.
- Selection: `LLM_PROVIDER=demo` is refused unless `DEMO_MODE=true`; `create_search_provider` rejects `demo`. Missing production credentials never fall back to demo.
- Every demo record has `is_demo=true`; reports carry the banner "DEMO / MOCK DATA".

## Verified
`apps/api/tests/test_analyst_e2e.py` runs the whole pipeline offline in-process (in-memory repositories): plan -> 6 agents -> sources/evidence/claims -> fact checker -> conflicts -> gaps -> replanning (<= cap) -> analyst -> report -> citations -> exports, asserts traceability end to end, usage without invented numbers, and determinism (identical output across runs). The Postgres/Celery/browser path of the same flow is **not verified**.
