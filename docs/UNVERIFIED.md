# Atlas Intelligence Verification Status

## Executed and Verified

### 1. Test Suites
- **Python Backend (`apps/api`)**: 255 tests passed (0 failures) via `pytest apps/api/tests`.
  - Includes database persistence contract, SQLite integration tests, auth/session isolation, and security/SSRF guards.
  - Includes report generation pipeline (`to_markdown`, `to_json`, `to_pdf`) verifying all 17 canonical sections, citations, and `[DEMO]` badges.
  - Includes regression test `test_gaps_detected_when_claims_are_only_partially_supported_or_conflicted` confirming research gaps are surfaced when claims are single-source or conflicted.
- **Frontend Unit Tests (`apps/web`)**: 9 tests passed (0 failures) via `node --test apps/web/tests/lib.test.mjs`.
  - Metric calculations, claim verification labels, CSRF handling, event merging, phase ordering, and graph layout tests.
- **Frontend Type & Production Build**: `next build` executed and succeeded with 0 errors across all 16 static/dynamic routes.

### 2. Code Audits & Behavior Fixes
- **Visual Insights Market Figures**: Removed hardcoded CAGR/YoY numbers and false claims of government/market reports. Visualizations are now dynamically populated from persisted claims and categories in the database. Added prominent Amber banner when `is_demo` is active.
- **Verbatim Citations Aggregation**: Fixed data unpacking in `VisualAnalyticsView.tsx` so endpoint arrays populate verified claims, harvested citation counts, and data tables identically to the Evidence view.
- **Research Gaps Engine**: Updated `apps/api/app/reporting/builder.py` so single-source uncorroborated claims and unresolved conflicts trigger explicit gap findings rather than declaring "No gaps were detected".
- **Dashboard vs Research Metrics**: Updated `/api/research/summary` and `apps/web/app/dashboard/page.tsx` to clearly separate workspace-wide aggregates from project-specific figures, with clear badges when demo data is present.
- **Provider Fallback Safeguards**: Audited `app/services/llm_selection.py` and `app/tools/search.py` confirming that `ConfigError` is raised on missing keys in production mode (`DEMO_MODE=false`), preventing silent fallback to demo data.

---

## NOT Executed / Unverified Runtime Behavior

The following runtime behaviors could not be executed in this environment and remain unverified:

| Runtime Area | Reason Not Executed | Verification Command / Steps Required |
|---|---|---|
| **Live External Web Search** | Real Brave Search API key was not configured (`DEMO_MODE=true` was used). | Set `DEMO_MODE=false`, `WEB_SEARCH_PROVIDER=brave`, `WEB_SEARCH_API_KEY=...`, run a live brief, and inspect network search hits. |
| **Live Production LLM Provider** | Real LLM API key (OpenAI/Anthropic/Gemini) was not configured in the test environment. | Set `DEMO_MODE=false`, `LLM_API_KEY=...`, and verify live completions against external endpoints. |
| **PostgreSQL Production Target** | Environment executed on SQLite (`DATABASE_URL=sqlite:///./atlas.db`). | Run `alembic upgrade head` on PostgreSQL 15+ and test database-level immutability triggers. |
| **Redis & Celery Worker Daemon** | Background execution was tested via in-process local worker threads rather than a distributed Celery cluster. | Start `redis-server` and `celery -A app.core.celery_app worker -l info` and verify distributed task delivery. |
| **Docker Compose Orchestration** | Tests ran directly on local host environment without Docker container virtualization. | Run `docker compose up --build` and verify service health checks (`curl http://localhost:8000/api/health/ready`). |
| **Multi-Worker Distributed Heartbeat Reclaim** | Hard worker failure under multi-node distributed Celery was not physically simulated. | Terminate worker with SIGKILL mid-task and confirm another Celery worker reclaims the task after 60s. |
| **Complex Non-Latin PDF Glyph Rendering** | Report PDF generator uses FPDF with Latin-1 character mapping. | Export report containing Arabic or non-Latin text and verify appropriate font embedding. |
