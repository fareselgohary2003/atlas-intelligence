from celery import Celery
import os
from app.core.config import settings

celery_app = Celery("atlas", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
                       broker_connection_timeout=2)


@celery_app.task(name="atlas.run_research")
def run_research_task(research_id: str):
    from app.observability.logging import bind_context, clear_context
    clear_context()
    bind_context(research_id=research_id, worker="celery")

    env = dict(os.environ)
    if settings.demo_mode:
        env["DEMO_MODE"] = "true"
        env.setdefault("LLM_PROVIDER", "demo")
        env.setdefault("WEB_SEARCH_PROVIDER", "demo")

    from app.core.db import SessionLocal
    from app.repositories.runs import SqlRunStore
    from app.services.composition import build_runners, build_usage, make_llm_factory
    from app.services.execution import execute_research
    llm_factory = make_llm_factory(env)
    runners = build_runners(env, SessionLocal, llm_factory)
    recorder, prices = build_usage(env, SessionLocal)
    return execute_research(research_id, SqlRunStore(SessionLocal), llm_factory, runners, recorder=recorder, prices=prices,
                            max_parallel=settings.max_parallel, max_replans=settings.max_replans)
