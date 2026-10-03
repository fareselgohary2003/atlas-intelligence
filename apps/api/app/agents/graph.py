"""Dynamic task-graph executor: parallel, retries, failure isolation, cancellation, resume, replanning."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from app.agents.state import ConfigError, ResearchState, Task, TaskStatus, TransientError

T = TaskStatus
SETTLED = {T.COMPLETED, T.FAILED, T.SKIPPED, T.CANCELLED}


class Engine:
    def __init__(self, state: ResearchState, runners: dict, manager=None, max_parallel=4, max_attempts=3, max_replans=2, control=None, settled_agents=("fact_checker", "analyst")):
        self.settled_agents = tuple(settled_agents)
        self.control = control  # callable -> None | 'pause' | 'cancel'; polled every loop iteration
        self.s, self.runners, self.manager = state, runners, manager
        self.max_parallel, self.max_attempts, self.max_replans = max_parallel, max_attempts, max_replans

    def _ready(self) -> list[Task]:
        changed = True
        while changed:  # a skipped task can cascade to its dependents
            changed = False
            for t in self.s.tasks.values():
                if t.status is T.PENDING and t.agent not in self.settled_agents and any(self.s.tasks[d].status in (T.FAILED, T.SKIPPED, T.CANCELLED) for d in t.depends_on):
                    t.status, t.error, changed = T.SKIPPED, "A dependency did not complete", True
                    self.s.emit("TASK_SKIPPED", task_id=t.id)
        return [t for t in self.s.tasks.values()
                if t.status is T.PENDING and (all(self.s.tasks[d].status is T.COMPLETED for d in t.depends_on) or
                                              (t.agent in self.settled_agents and all(self.s.tasks[d].status in SETTLED for d in t.depends_on)))]

    def _call(self, task: Task):
        runner = self.runners.get(task.agent)
        if runner is None:
            raise ConfigError(f"No runner registered for agent '{task.agent}'")
        return runner(self.s, task)  # runs in a worker thread; must not mutate shared state directly

    def _fail(self, t: Task, e: Exception):
        t.status, t.error = T.FAILED, f"{type(e).__name__}: {e}"
        self.s.errors.append({"task_id": t.id, "error": t.error})
        self.s.emit("TASK_FAILED", task_id=t.id, agent=t.agent, error=t.error)

    def _finish(self, fut, t: Task):
        try:
            res = fut.result()
        except TransientError as e:
            if t.attempts < self.max_attempts:
                t.status = T.PENDING
                self.s.emit("TASK_RETRY", task_id=t.id, attempt=t.attempts, error=str(e))
            else:
                self._fail(t, e)
        except Exception as e:  # permanent failure: recorded, dependents skipped, other work continues
            self._fail(t, e)
        else:
            t.status, t.result = T.COMPLETED, res
            self.s.emit("TASK_COMPLETED", task_id=t.id, agent=t.agent, summary=(res or {}).get("summary"),
                        counts=(res or {}).get("counts"))

    def _replan(self) -> bool:
        s = self.s
        if not self.manager or s.replans >= self.max_replans:
            return False
        try:
            new = self.manager.review(s)
        except Exception as e:  # a failed review must never crash a run that has usable results
            s.errors.append({"task_id": None, "error": f"Replanning failed: {e}"})
            s.emit("REPLAN_FAILED", error=str(e))
            return False
        if not new:
            return False
        reasons = sorted({t.reason for t in new if getattr(t, "reason", None)})
        s.emit("REPLAN_REQUESTED", reasons=reasons, task_count=len(new))
        s.replans += 1
        self.manager._add(s, new)
        s.emit("RESEARCH_REPLANNED", new_tasks=[t.id for t in new], replans=s.replans, reasons=reasons)
        return True

    def _finalize(self) -> bool:
        fin = getattr(self.manager, "finalize", None)
        if fin is None:
            return False
        try:
            new = fin(self.s)
        except Exception as e:
            self.s.errors.append({"task_id": None, "error": f"Finalization failed: {e}"})
            return False
        if not new:
            return False
        self.manager._add(self.s, new)
        self.s.emit("ANALYSIS_REQUESTED", new_tasks=[t.id for t in new])
        return True

    def run(self) -> ResearchState:
        s = self.s
        s.reset_interrupted()
        s.status = "researching"
        s.emit("RESEARCH_STARTED")
        running: dict = {}
        paused = False
        with ThreadPoolExecutor(self.max_parallel) as pool:
            while True:
                ctl = self.control() if self.control else None
                if ctl == "cancel":
                    s.cancel()
                paused = ctl == "pause"
                if s.cancelled:
                    for t in s.tasks.values():
                        if t.status is T.PENDING:
                            t.status = T.CANCELLED
                            s.emit("TASK_CANCELLED", task_id=t.id)  # persisted like every other state change
                elif not paused:
                    for t in self._ready():
                        if len(running) >= self.max_parallel:
                            break
                        t.status, t.attempts = T.RUNNING, t.attempts + 1
                        s.emit("AGENT_STARTED", task_id=t.id, agent=t.agent, attempt=t.attempts)
                        running[pool.submit(self._call, t)] = t
                if not running:
                    if s.cancelled or paused:
                        break
                    if self._replan() or self._finalize():
                        continue
                    break
                done, _ = wait(running, return_when=FIRST_COMPLETED, timeout=0.2)
                for f in done:
                    self._finish(f, running.pop(f))
        if paused and not s.cancelled and any(t.status is T.PENDING for t in s.tasks.values()):
            s.status = "paused"
            s.emit("RESEARCH_PAUSED", status="paused")
            return s
        statuses = {t.status for t in s.tasks.values()}
        if s.cancelled:
            s.status, kind = "cancelled", "RESEARCH_CANCELLED"
        elif statuses <= {T.COMPLETED}:
            s.status, kind = "completed", "RESEARCH_COMPLETED"
        elif T.COMPLETED in statuses:
            s.status, kind = "needs_review", "RESEARCH_COMPLETED"  # partial: some tasks failed or were skipped
        else:
            s.status, kind = "failed", "RESEARCH_FAILED"
        s.emit(kind, status=s.status)
        return s
