"""Research Manager: plans tasks and decides whether more research is needed. Output is validated, never trusted."""
import hashlib
import json

from app.agents.state import AGENTS, PlanError, ResearchState, Task, TaskStatus

PLAN_TEMPLATE = (
    "You are the research planning agent of an enterprise research platform. Break the user's research goal "
    "into concrete research tasks. Return ONLY JSON: "
    '{"tasks":[{"id":"t1","title":"...","agent":"<one of: {agents}>","depends_on":["<task ids>"]}]}. '
    "Use 3 to 15 tasks. Independent tasks must not depend on each other. Do not add analysis or report tasks."
)
REVIEW_SYSTEM = (
    "You are the research manager reviewing progress. Given task outcomes, decide whether important information "
    "is still missing. Return ONLY JSON in the same schema as planning; return {\"tasks\":[]} if the research is "
    "sufficient. Add at most 5 tasks, using new unique ids."
)


def validate_tasks(raw, existing_ids, lo, hi, agents=AGENTS) -> list[Task]:
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        raise PlanError("Plan must be an object with a 'tasks' list")
    seen, tasks = set(existing_ids), []
    for item in raw["tasks"]:
        try:
            tid, title, agent = str(item["id"]), str(item["title"]).strip()[:200], item["agent"]
            deps = [str(d) for d in item.get("depends_on", [])]
        except (KeyError, TypeError, AttributeError):
            raise PlanError("Malformed task entry")
        if agent not in agents or not title or tid in seen:
            raise PlanError(f"Invalid task '{tid}' (unknown agent, empty title or duplicate id)")
        seen.add(tid)
        tasks.append(Task(tid, title, agent, deps))
    if not lo <= len(tasks) <= hi:
        raise PlanError(f"Expected {lo}-{hi} tasks, got {len(tasks)}")
    new_ids = {t.id for t in tasks}
    for t in tasks:
        if any(d not in seen for d in t.depends_on):
            raise PlanError(f"Task '{t.id}' depends on an unknown task")
    # cycle check among new tasks (Kahn)
    indeg = {t.id: sum(d in new_ids for d in t.depends_on) for t in tasks}
    queue = [i for i, n in indeg.items() if n == 0]
    done = 0
    while queue:
        cur = queue.pop()
        done += 1
        for t in tasks:
            if cur in t.depends_on:
                indeg[t.id] -= 1
                if indeg[t.id] == 0:
                    queue.append(t.id)
    if done != len(tasks):
        raise PlanError("Plan contains a dependency cycle")
    return tasks


SYSTEM_AGENTS = ("fact_checker", "analyst")  # scheduled by the manager itself; the LLM may not plan them and agents may not request them


class ResearchManager:
    def __init__(self, llm, agents=AGENTS, max_follow_ups=5):
        self.llm, self.agents, self.max_follow_ups = llm, tuple(agents), max_follow_ups
        self.planning_agents = tuple(a for a in self.agents if a not in SYSTEM_AGENTS)

    def _add(self, state: ResearchState, tasks: list[Task]):
        for t in tasks:
            state.tasks[t.id] = t
            state.emit("TASK_CREATED", task_id=t.id, title=t.title, agent=t.agent, depends_on=t.depends_on,
                       reason_code=getattr(t, "reason", None))

    def plan(self, state: ResearchState) -> list[Task]:
        raw = self.llm.structured_output(PLAN_TEMPLATE.replace("{agents}", ", ".join(self.planning_agents)), state.user_goal)
        tasks = validate_tasks(raw, set(), 3, 15, self.planning_agents)
        if any(t.id == "verify" for t in tasks):
            raise PlanError("Task id 'verify' is reserved")
        state.emit("PLAN_CREATED", task_count=len(tasks))
        self._add(state, tasks)
        if "fact_checker" in self.agents:  # every research plan ends with verification of what was collected
            v = Task("verify", "Verify claims against collected evidence", "fact_checker", [t.id for t in tasks])
            self._add(state, [v])
            return tasks + [v]
        return tasks

    def finalize(self, state: ResearchState) -> list[Task]:
        """Called by the engine when no more research is pending: schedule the single analysis step (not counted as a replan)."""
        if "analyst" in self.agents and "analyze" not in state.tasks:
            return [Task("analyze", "Synthesize verified findings into opportunities, uncertainties and risks", "analyst",
                         list(state.tasks), reason="SYNTHESIS")]
        return []

    PRIORITY = ("VERIFICATION_FAILED", "CONFLICT_DETECTED", "INSUFFICIENT_EVIDENCE", "MISSING_DIMENSION", "LOW_SOURCE_QUALITY")

    def follow_up_tasks(self, state: ResearchState) -> list[Task]:
        """Agents PROPOSE follow-ups in their results; only the manager turns them into tasks (deterministic ids => retry-safe).
        Proposals are ranked by reason priority then title BEFORE the cap applies, so which follow-ups are kept never depends on
        task scheduling order. Each task records its reason; a verification task is appended so new evidence gets checked."""
        cands = {}
        for t in list(state.tasks.values()):
            if t.status is not TaskStatus.COMPLETED:
                continue
            for item in (t.result or {}).get("follow_up_tasks") or []:
                tid = "f-" + hashlib.sha256(f"{t.id}|{item.get('key', '')}".encode()).hexdigest()[:12]
                title = str(item.get("title", "")).strip()[:200]
                if tid in state.tasks or tid in cands:
                    continue
                if item.get("agent") not in self.planning_agents or not title:
                    msg = f"Ignored follow-up {tid}: unknown agent or empty title"
                    if not any(e.get("error") == msg for e in state.errors):
                        state.errors.append({"task_id": t.id, "error": msg})
                    continue
                code = item.get("reason_code") or "MISSING_DIMENSION"
                rank = self.PRIORITY.index(code) if code in self.PRIORITY else len(self.PRIORITY)
                cands[tid] = (rank, title, tid, item["agent"], code)
        out = [Task(tid, title, agent, [], reason=code) for _, title, tid, agent, code in sorted(cands.values())[:self.max_follow_ups]]
        if out and "fact_checker" in self.agents:
            vid = "v-" + hashlib.sha256(",".join(sorted(t.id for t in out)).encode()).hexdigest()[:12]
            if vid not in state.tasks:
                out.append(Task(vid, "Re-verify claims after follow-up research", "fact_checker", [t.id for t in out], reason="VERIFICATION_FOLLOW_UP"))
        return out

    def review(self, state: ResearchState) -> list[Task]:
        ups = self.follow_up_tasks(state)
        if ups:
            return ups  # no LLM call needed; the engine's max_replans still bounds the loop
        summary = [{"id": t.id, "title": t.title, "agent": t.agent, "status": t.status.value, "error": t.error,
                    "summary": (t.result or {}).get("summary")} for t in state.tasks.values()]
        prompt = json.dumps({"goal": state.user_goal, "tasks": summary})
        return validate_tasks(self.llm.structured_output(REVIEW_SYSTEM, prompt), set(state.tasks), 0, 5, self.planning_agents)
