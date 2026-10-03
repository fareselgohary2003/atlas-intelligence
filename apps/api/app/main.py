import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from contextlib import asynccontextmanager
from app.api import auth, evidence, platform, reports, research, runs, workspaces
from app.core import security
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.observability.logging import bind_context, clear_context, configure_logging, valid_request_id
from app.seed import main as seed_main

configure_logging(settings.log_level)
log = logging.getLogger("atlas.http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    try:
        seed_main()
    except Exception:
        log.exception("seeding failed")
    yield


app = FastAPI(title="Atlas Intelligence API", version="1.0.0", lifespan=lifespan)

origins = list({o.strip() for o in settings.cors_origins.split(",") if o.strip()} | {
    "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    rid = request.headers.get("X-Request-ID", "")
    rid = rid if valid_request_id(rid) else uuid.uuid4().hex
    clear_context()
    bind_context(request_id=rid, method=request.method, path=request.url.path)
    started = time.monotonic()
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/health"):
        ok, retry = security.get_limiter().hit("api:" + (request.client.host if request.client else "?"), settings.api_rate_limit, 60)
        if not ok:
            r = JSONResponse({"detail": "Rate limit exceeded"}, status_code=429, headers={"Retry-After": str(retry), "X-Request-ID": rid})
            log.warning("rate limited")
            return r
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error")  # details stay in logs; clients get a generic message
        return JSONResponse({"detail": "Internal server error"}, status_code=500, headers={"X-Request-ID": rid})
    response.headers["X-Request-ID"] = rid
    log.info("request", extra={"status": response.status_code, "duration_ms": int((time.monotonic() - started) * 1000)})
    return response


for r in (auth.router, workspaces.router, research.router, runs.router, evidence.router, reports.router, platform.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "demo_mode": settings.demo_mode}


@app.get("/api/health/ready")
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
    except Exception:
        log.exception("readiness check failed")
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ready"}
