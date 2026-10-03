import threading
import unittest

from app.agents.graph import Engine
from app.agents.llm import OpenAICompatibleLLM
from app.agents.manager import ResearchManager
from app.agents.state import ConfigError, PlanError, ResearchState, TaskStatus as T, TransientError
from app.agents.manager import validate_tasks


class Scripted:  # test double: returns queued JSON. Lives in tests only, never in app code.
    def __init__(self, *r):
        self.r = list(r)

    def structured_output(self, system, user):
        return self.r.pop(0) if self.r else {"tasks": []}  # exhausted script = manager says 'sufficient'


def plan(*specs):
    return {"tasks": [{"id": i, "title": f"Task {i}", "agent": a, "depends_on": d} for i, a, d in specs]}


def make(*specs, manager_llm=None):
    s = ResearchState("r1", "w1", "goal")
    m = ResearchManager(Scripted(plan(*specs)) if manager_llm is None else manager_llm)
    if manager_llm is None:
        m.plan(s)
    return s, m


ok = lambda s, t: {"summary": f"done {t.id}"}


class EngineTests(unittest.TestCase):
    def test_plan_validation(self):
        with self.assertRaises(PlanError):
            validate_tasks(plan(("a", "market", ["b"]), ("b", "risk", ["a"]), ("c", "pricing", [])), set(), 3, 15)
        with self.assertRaises(PlanError):
            validate_tasks(plan(("a", "wizard", []), ("b", "risk", []), ("c", "pricing", [])), set(), 3, 15)
        with self.assertRaises(PlanError):
            validate_tasks("not json object", set(), 3, 15)
        with self.assertRaises(PlanError):
            validate_tasks(plan(("a", "market", ["zzz"]), ("b", "risk", []), ("c", "pricing", [])), set(), 3, 15)

    def test_plan_emits_events(self):
        s, _ = make(("a", "market", []), ("b", "risk", []), ("c", "pricing", ["a"]))
        kinds = [e["kind"] for e in s.events]
        self.assertEqual(kinds[0], "PLAN_CREATED")
        self.assertEqual(kinds.count("TASK_CREATED"), 3)

    def test_parallel_and_dependency_order(self):
        s, m = make(("a", "market", []), ("b", "competitor", []), ("c", "pricing", ["a", "b"]))
        barrier = threading.Barrier(2, timeout=3)  # only passes if a and b truly run concurrently
        order = []

        def run(state, t):
            if t.id in "ab":
                barrier.wait()
            order.append(t.id)
            return {"summary": t.id}
        Engine(s, {k: run for k in ("market", "competitor", "pricing")}, m).run()
        self.assertEqual(s.status, "completed")
        self.assertEqual(order[-1], "c")

    def test_transient_retry_then_success_and_exhaustion(self):
        s, m = make(("a", "market", []), ("b", "risk", []), ("c", "pricing", []))
        calls = {"a": 0}

        def flaky(state, t):
            calls["a"] += 1
            if calls["a"] < 3:
                raise TransientError("429")
            return {}

        def always(state, t):
            raise TransientError("503")
        Engine(s, {"market": flaky, "risk": always, "pricing": ok}, m, max_attempts=3).run()
        self.assertEqual((s.tasks["a"].status, s.tasks["a"].attempts), (T.COMPLETED, 3))
        self.assertEqual((s.tasks["b"].status, s.tasks["b"].attempts), (T.FAILED, 3))
        self.assertEqual(s.status, "needs_review")

    def test_permanent_failure_skips_dependents_only(self):
        s, m = make(("a", "market", []), ("b", "risk", ["a"]), ("c", "pricing", []))

        def boom(state, t):
            raise ValueError("bad")
        Engine(s, {"market": boom, "risk": ok, "pricing": ok}, m).run()
        self.assertEqual(s.tasks["a"].attempts, 1)  # not retried
        self.assertEqual(s.tasks["b"].status, T.SKIPPED)
        self.assertEqual(s.tasks["c"].status, T.COMPLETED)
        self.assertEqual(s.status, "needs_review")

    def test_missing_runner_is_a_visible_failure(self):
        s, m = make(("a", "market", []), ("b", "risk", []), ("c", "pricing", []))
        Engine(s, {"risk": ok, "pricing": ok}, m).run()
        self.assertIn("No runner", s.tasks["a"].error)

    def test_cancellation(self):
        s, m = make(("a", "market", []), ("b", "risk", ["a"]), ("c", "pricing", ["b"]))

        def cancel(state, t):
            state.cancel()
            return {}
        Engine(s, {"market": cancel, "risk": ok, "pricing": ok}, m).run()
        self.assertEqual(s.status, "cancelled")
        self.assertEqual({s.tasks[i].status for i in "bc"}, {T.CANCELLED})

    def test_replanning_adds_tasks_and_respects_cap(self):
        llm = Scripted(plan(("t1", "market", []), ("t2", "risk", []), ("t3", "pricing", [])),
                       plan(("t9", "competitor", ["t1"])), plan(("t10", "customer", [])))
        s, m = make(manager_llm=llm)
        m.plan(s)
        Engine(s, {k: ok for k in ("market", "risk", "pricing", "competitor", "customer")}, m, max_replans=1).run()
        self.assertEqual(s.replans, 1)
        self.assertEqual(s.tasks["t9"].status, T.COMPLETED)
        self.assertNotIn("t10", s.tasks)
        self.assertIn("RESEARCH_REPLANNED", [e["kind"] for e in s.events])

    def test_bad_replan_output_is_recorded_not_fatal(self):
        llm = Scripted(plan(("a", "market", []), ("b", "risk", []), ("c", "pricing", [])), {"nonsense": True})
        s, m = make(manager_llm=llm)
        m.plan(s)
        Engine(s, {k: ok for k in ("market", "risk", "pricing")}, m).run()
        self.assertEqual(s.status, "completed")
        self.assertIn("REPLAN_FAILED", [e["kind"] for e in s.events])

    def test_resume_skips_completed_work(self):
        s, m = make(("a", "market", []), ("b", "risk", ["a"]), ("c", "pricing", ["b"]))
        s.tasks["a"].status, s.tasks["b"].status = T.COMPLETED, T.RUNNING  # simulated crash mid-task
        s2 = ResearchState.from_dict(s.to_dict())
        ran = []
        Engine(s2, {k: (lambda st, t: ran.append(t.id) or {}) for k in ("market", "risk", "pricing")}).run()
        self.assertEqual(ran, ["b", "c"])
        self.assertEqual(s2.status, "completed")

    def test_pause_leaves_pending_tasks_pending(self):
        s, m = make(("a", "market", []), ("b", "risk", ["a"]), ("c", "pricing", ["b"]))
        ctl = {"v": None}
        Engine(s, {"market": lambda st, t: ctl.update(v="pause") or {}, "risk": ok, "pricing": ok}, m, control=lambda: ctl["v"]).run()
        self.assertEqual(s.status, "paused")
        self.assertEqual((s.tasks["a"].status, s.tasks["b"].status), (T.COMPLETED, T.PENDING))

    def test_llm_requires_credentials(self):
        with self.assertRaises(ConfigError):
            OpenAICompatibleLLM(None, "m")


if __name__ == "__main__":
    unittest.main()
