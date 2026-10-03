# Setup

## With Docker (UNVERIFIED: not run in the authoring environment)
1. `cp .env.example .env`; set `JWT_SECRET` to a long random value; set `POSTGRES_PASSWORD`; behind HTTPS set `COOKIE_SECURE=true`.
2. `docker compose up --build`. Order: `db` + `redis` healthy -> `api` (runs `alembic upgrade head`, seeds demo rows only if `DEMO_MODE=true`, serves on :8000) -> `worker` (Celery) + `web` (:3000).
3. Health: `GET /api/health` (liveness), `GET /api/health/ready` (database reachable). Volumes `pgdata` and `redisdata` persist data. Postgres/Redis publish no host ports.
4. Production research needs `LLM_API_KEY` and `WEB_SEARCH_API_KEY`; the Settings page shows whether each is configured (never the value).

## Without Docker
```bash
# API
cd apps/api && pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://atlas:atlas@localhost:5432/atlas REDIS_URL=redis://localhost:6379/0 JWT_SECRET=...
alembic upgrade head && uvicorn app.main:app --reload
celery -A app.workers.celery_app worker -l info          # in another shell: research runs in the worker, not in the request
# Web
cd apps/web && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```
The browser and API must be same-site (e.g. `localhost:3000` and `localhost:8000`) for the session cookie; set `CORS_ORIGINS` to the web origin.

## Migrations
`apps/api/alembic/versions`: 0001 core, 0002 engine tables, 0003 evidence + composite FKs + immutability triggers, 0004 reports/usage, 0005 analyses + immutable audit log. Hand-written; reviewed but never executed. After the first run verify `alembic downgrade base` and `upgrade head` both succeed.

## Environment variables
See `.env.example` (every variable is commented). No real secret belongs in the repository.
