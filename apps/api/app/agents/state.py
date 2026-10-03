"""ResearchState and task model. Stdlib only; persistence is layered on via the on_event hook."""
import threading
import time
from enum import Enum


class TransientError(Exception):
    """Retryable: timeouts, 429, 5xx."""


class ConfigError(Exception):
    """Missing/invalid configuration. Never retried and never replaced with fake output."""


class LLMOutputError(Exception):
    """Model returned malformed or invalid output."""


class PlanError(Exception):
    """A generated plan failed validation."""


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


AGENTS = ("market", "competitor", "customer", "pricing", "regulation", "risk")


class Task:
    def __init__(self, id, title, agent, depends_on=None, status=TaskStatus.PENDING, attempts=0, error=None, result=None, reason=None):
        self.reason = reason  # why this task exists when created by replanning (a REASON_CODE); persisted via events
        self.id, self.title, self.agent = id, title, agent
        self.depends_on = list(depends_on or [])
        self.status, self.attempts, self.error, self.result = TaskStatus(status), attempts, error, result

    def to_dict(self):
        return {"id": self.id, "title": self.title, "agent": self.agent, "depends_on": self.depends_on,
                "status": self.status.value, "attempts": self.attempts, "error": self.error, "result": self.result}


class ResearchState:
    def __init__(self, research_id, workspace_id, user_goal, on_event=None):
        self.research_id, self.workspace_id, self.user_goal = research_id, workspace_id, user_goal
        self.tasks: dict[str, Task] = {}
        self.events: list[dict] = []
        self.errors: list[dict] = []
        self.replans = 0
        self.cancelled = False
        self.status = "planning"
        self.seq_base = 0  # events already persisted by earlier runs of this research
        self.on_event = on_event  # persistence / SSE hook; called for every event
        self._lock = threading.Lock()

    def emit(self, kind: str, **data) -> dict:
        with self._lock:
            ev = {"seq": self.seq_base + len(self.events) + 1, "ts": time.time(), "kind": kind, **data}
            self.events.append(ev)
        if self.on_event:
            self.on_event(ev)
        return ev

    def cancel(self):
        self.cancelled = True

    def reset_interrupted(self):
        """Resume support: a task that was RUNNING when the process died is re-queued. Completed work is kept."""
        for t in self.tasks.values():
            if t.status is TaskStatus.RUNNING:
                t.status = TaskStatus.PENDING

    def to_dict(self):
        return {"research_id": self.research_id, "workspace_id": self.workspace_id, "user_goal": self.user_goal,
                "tasks": [t.to_dict() for t in self.tasks.values()], "errors": self.errors,
                "replans": self.replans, "status": self.status}

    @classmethod
    def from_dict(cls, d, on_event=None):
        s = cls(d["research_id"], d["workspace_id"], d["user_goal"], on_event)
        s.tasks = {t["id"]: Task(**t) for t in d["tasks"]}
        s.errors, s.replans, s.status = d["errors"], d["replans"], d["status"]
        return s
