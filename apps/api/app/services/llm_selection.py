"""LLM provider selection (stdlib only, so it is testable without the database stack)."""


def make_llm_factory(env):
    """LLM selection. The deterministic DemoLLM requires BOTH DEMO_MODE=true and LLM_PROVIDER=demo; otherwise the configured
    OpenAI-compatible provider is used and missing credentials fail loudly (never a silent switch to demo)."""
    from app.agents.llm import OpenAICompatibleLLM
    if env.get("LLM_PROVIDER") == "demo":
        if env.get("DEMO_MODE", "").lower() != "true":
            from app.agents.state import ConfigError
            return lambda: (_ for _ in ()).throw(ConfigError("LLM_PROVIDER=demo requires DEMO_MODE=true"))
        from app.demo.llm import DemoLLM
        return DemoLLM
    return lambda: OpenAICompatibleLLM(env.get("LLM_API_KEY"), env.get("LLM_MODEL", "gpt-4o-mini"), env.get("LLM_BASE_URL", "https://api.openai.com/v1"))
