import logging
import threading
from app.core.config import settings

log = logging.getLogger("atlas.queue")


class QueueUnavailable(Exception):
    """The broker could not accept the job."""


def enqueue_research(research_id: str) -> None:
    from app.workers.celery_app import run_research_task
    # In demo mode or if Celery broker is not reached, spawn a background daemon thread
    if settings.demo_mode:
        t = threading.Thread(target=run_research_task, args=[research_id], daemon=True)
        t.start()
        log.info(f"Spawned local research worker thread for {research_id}")
        return

    try:
        run_research_task.apply_async(args=[research_id], expires=3600, retry=True,
                                      retry_policy={"max_retries": 1, "interval_start": 0, "interval_max": 0.2})
    except Exception as e:
        log.warning(f"Celery enqueue failed ({e}), falling back to local thread")
        try:
            t = threading.Thread(target=run_research_task, args=[research_id], daemon=True)
            t.start()
        except Exception as inner_e:
            raise QueueUnavailable(str(inner_e)) from inner_e
