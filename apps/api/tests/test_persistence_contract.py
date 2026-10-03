"""Engine <-> persistence contract, verified against an in-memory RunStore (stdlib only).
This proves the executor/engine/store protocol. It does NOT prove the SQL implementation (see tests/integration)."""
import unittest

from app.agents.events import public_event
from app.agents.state import ConfigError, ResearchState, Task, TaskStatus as T
from app.services.execution import execute_research


class MemStore:  # test double implementing the RunStore protocol
    def __init__(self):
        self.status, self.control, self.tasks, self.events, self.finished = "queued", None, {}, [], None

    def claim(self, rid):
        if self.status != "queued":
            return False
        self.status = "researching"
        return True

    def load_state(self, rid):
        s = ResearchState(rid, "w1", "Analyze the market")
        s.tasks = {k: Task(**v) for k, v in self.tasks.items()}
        s.seq_base = len(self.events)
        return s

    def record(self, state, ev):
        self.events.append(public_event(ev))
        if ev.get("task_id") in state.tasks:
            self.tasks[ev["task_id"]] = state.tasks[ev["task_id"]].to_dict()

    def poll_control(self, rid):
        return self.control

    def finish(self, state, status, error=None):
        self.status, self.finished = status, (status, error)


class Scripted:
    def __init__(self, *r):
        self.r = list(r)

    def structured_output(self, system, user):
        return self.r.pop(0) if self.r else {"tasks": []}


PLAN = {"tasks": [{"id": "a", "title": "A", "agent": "market", "depends_on": []},
                  {"id": "b", "title": "B", "agent": "risk", "depends_on": ["a"]},
                  {"id": "c", "title": "C", "agent": "pricing", "depends_on": ["b"]}]}
ok = lambda s, t: {"summary": f"done {t.id}"}
R3 = {"market": ok, "risk": ok, "pricing": ok}


class ContractTests(unittest.TestCase):
    def test_full_run_persists_ordered_events_and_task_rows(self):
        st = MemStore()
        self.assertEqual(execute_research("r1", st, lambda: Scripted(PLAN), R3), "completed")
        seqs = [e["seq"] for e in st.events]
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))
        kinds = [e["kind"] for e in st.events]
        self.assertEqual(kinds[0], "PLAN_CREATED")
        self.assertIn("RESEARCH_STARTED", kinds)
        self.assertEqual(kinds[-1], "RESEARCH_COMPLETED")
        self.assertEqual({t["status"] for t in st.tasks.values()}, {"completed"})
        self.assertEqual(st.finished, ("completed", None))

    def test_duplicate_delivery_is_a_noop(self):
        st = MemStore()
        execute_research("r1", st, lambda: Scripted(PLAN), R3)
        n = len(st.events)
        self.assertEqual(execute_research("r1", st, lambda: Scripted(PLAN), R3), "not_claimed")
        self.assertEqual(len(st.events), n)

    def test_pause_then_resume_continues_without_rerunning_or_seq_collisions(self):
        st, ran = MemStore(), []

        def a(s, t):
            ran.append(t.id)
            st.control = "pause"
            return {}
        runners = {"market": a, "risk": lambda s, t: ran.append(t.id) or {}, "pricing": lambda s, t: ran.append(t.id) or {}}
        self.assertEqual(execute_research("r1", st, lambda: Scripted(PLAN), runners), "paused")
        self.assertEqual(st.tasks["b"]["status"], "pending")
        self.assertEqual(st.events[-1]["kind"], "RESEARCH_PAUSED")
        st.status, st.control = "queued", None  # what the resume endpoint does
        self.assertEqual(execute_research("r1", st, lambda: Scripted(), runners), "completed")
        self.assertEqual(ran, ["a", "b", "c"])
        seqs = [e["seq"] for e in st.events]
        self.assertEqual(seqs, sorted(set(seqs)))  # strictly increasing, no duplicates (DB unique constraint holds)

    def test_cancel_via_control(self):
        st = MemStore()
        runners = {**R3, "market": lambda s, t: setattr(st, "control", "cancel") or {}}
        self.assertEqual(execute_research("r1", st, lambda: Scripted(PLAN), runners), "cancelled")
        self.assertEqual({st.tasks[k]["status"] for k in "bc"}, {"cancelled"})

    def test_missing_llm_config_fails_explicitly(self):
        st = MemStore()

        def no_llm():
            raise ConfigError("LLM_API_KEY is not set")
        self.assertEqual(execute_research("r1", st, no_llm, R3), "failed")
        self.assertIn("LLM_API_KEY", st.finished[1])
        self.assertEqual(st.events[-1]["kind"], "RESEARCH_FAILED")

    def test_unexpected_error_is_logged_not_leaked(self):
        st = MemStore()

        class Boom:
            def structured_output(self, *a):
                raise RuntimeError("db password=hunter2")
        with self.assertLogs("atlas.execution", "ERROR"):
            self.assertEqual(execute_research("r1", st, lambda: Boom(), R3), "failed")
        self.assertNotIn("hunter2", st.finished[1])
        self.assertNotIn("hunter2", str(st.events))

    def test_public_event_drops_non_whitelisted_fields(self):
        ev = {"kind": "TASK_COMPLETED", "seq": 1, "ts": 0, "task_id": "a", "reasoning": "secret", "chain_of_thought": "x",
              "summary": "s" * 900, "source": {"title": "T", "internal": "no"}}
        out = public_event(ev)
        self.assertNotIn("reasoning", out)
        self.assertNotIn("chain_of_thought", out)
        self.assertEqual(len(out["summary"]), 500)
        self.assertEqual(out["source"], {"title": "T"})
        self.assertTrue(out["ts"].startswith("1970-01-01"))


if __name__ == "__main__":
    unittest.main()
