"""Composition root: the only place that wires repositories, providers, tools and agents together."""

from app.agents.framework import AgentRegistry
from app.agents.catalog import AGENT_CLASSES
from app.agents.framework import AgentRegistry
from app.evidence.service import EvidenceService
from app.repositories.evidence import SqlEvidenceRepository
from app.services.llm_selection import make_llm_factory  # noqa: F401  (re-exported)
from app.tools.wiring import build_tool_stack, is_demo_mode


def build_usage(env, session_factory):
    from app.observability.usage import PriceTable
    from app.repositories.reports import SqlUsageRecorder
    return SqlUsageRecorder(session_factory), PriceTable.from_env(env)


def build_runners(env, session_factory, llm_factory) -> dict:
    service = EvidenceService(SqlEvidenceRepository(session_factory), force_demo=is_demo_mode(env))
    tools, follow_ups = build_tool_stack(env, service)
    agents = AgentRegistry(tools)
    for cls in AGENT_CLASSES:
        agents.register(cls())
    recorder, prices = build_usage(env, session_factory)
    return agents.runners(llm_factory, follow_ups, recorder, prices)
