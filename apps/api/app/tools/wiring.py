import os

from app.tools.builtin import build_default_registry
from app.tools.evidence_tools import FollowUpBuffer, register_evidence_tools
from app.tools.fetch import Fetcher
from app.tools.search import create_search_provider


def is_demo_mode(env=os.environ) -> bool:
    """The demo provider needs BOTH switches; missing credentials never fall back to it."""
    return env.get("DEMO_MODE", "").lower() == "true" and env.get("WEB_SEARCH_PROVIDER") == "demo"


def build_tool_stack(env, service):
    if is_demo_mode(env):
        from app.demo.provider import DemoFetcher, DemoSearchProvider
        provider, fetcher = DemoSearchProvider(), DemoFetcher()
        getter = lambda: provider
    else:
        name, key = env.get("WEB_SEARCH_PROVIDER"), env.get("WEB_SEARCH_API_KEY")
        getter, fetcher = (lambda: create_search_provider(name, key)), Fetcher()
    reg, follow_ups = build_default_registry(getter, fetcher), FollowUpBuffer()
    register_evidence_tools(reg, service, follow_ups)
    return reg, follow_ups
