import logging

from app.agents.graph import Engine
from app.agents.manager import ResearchManager
from app.agents.state import AGENTS, ConfigError, LLMOutputError, PlanError, TransientError

log = logging.getLogger("atlas.execution")
KNOWN = (ConfigError, LLMOutputError, PlanError, TransientError)


def _fail(state, store, message):
    state.status = "failed"
    state.errors.append({"task_id": None, "error": message})
    try:
        state.emit("RESEARCH_FAILED", status="failed", error=message)
        store.finish(state, "failed", message)
    except Exception:
        log.exception("could not persist failure for research %s", state.research_id)


def execute_research(research_id, store, llm_factory, runners, max_parallel=4, recorder=None, prices=None, max_replans=2) -> str:
    """Runs (or resumes) one research. Idempotent: a duplicate delivery fails to claim and does nothing."""
    if not store.claim(research_id):
        return "not_claimed"
    state = store.load_state(research_id)
    state.on_event = lambda ev: store.record(state, ev)
    try:
        llm = llm_factory()
        if recorder is not None:
            from app.observability.usage import MeteredLLM
            llm = MeteredLLM(llm, recorder, research_id=state.research_id, workspace_id=state.workspace_id, agent="research_manager", prices=prices)
        manager = ResearchManager(llm, agents=tuple(runners) or AGENTS)  # plan only for agents that exist
        if not state.tasks:
            manager.plan(state)
        Engine(state, runners, manager, max_parallel=max_parallel, max_replans=max_replans, control=lambda: store.poll_control(research_id)).run()
    except KNOWN as e:
        _fail(state, store, f"{type(e).__name__}: {e}")
        return "failed"
    except Exception:
        log.exception("research %s crashed", research_id)  # details stay in server logs, not in the API
        _fail(state, store, "Internal error during research execution")
        return "failed"
    store.finish(state, state.status)
    return state.status
