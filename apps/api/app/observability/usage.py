"""LLM usage/cost metering behind the LLMProvider abstraction. Tokens come from the provider (None when unreported);
cost is only estimated when explicit prices are configured. Nothing here ever logs or stores prompts or responses."""
import logging
import time
from dataclasses import dataclass

from app.agents.llm import Usage
from app.agents.state import ConfigError, LLMOutputError, TransientError
from app.evidence.domain import new_id, now

log = logging.getLogger("atlas.usage")


@dataclass
class UsageRecord:
    id: str
    research_id: str
    workspace_id: str
    task_key: str | None
    agent: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    duration_ms: int
    ok: bool
    error_category: str | None
    created_at: object


class PriceTable:
    """USD per 1K tokens for the configured model. Unset prices => cost stays None (never a made-up number)."""
    def __init__(self, input_per_1k=None, output_per_1k=None):
        self.input_per_1k, self.output_per_1k = input_per_1k, output_per_1k

    @classmethod
    def from_env(cls, env):
        def get(k):
            v = env.get(k)
            if v in (None, ""):
                return None
            try:
                f = float(v)
                assert f >= 0
                return f
            except (ValueError, AssertionError):
                raise ConfigError(f"{k} must be a non-negative number")
        return cls(get("LLM_PRICE_INPUT_PER_1K"), get("LLM_PRICE_OUTPUT_PER_1K"))

    def estimate(self, usage: Usage):
        if None in (self.input_per_1k, self.output_per_1k, usage.input_tokens, usage.output_tokens):
            return None
        return round(usage.input_tokens / 1000 * self.input_per_1k + usage.output_tokens / 1000 * self.output_per_1k, 6)


def _category(e: Exception) -> str:
    return "transient" if isinstance(e, TransientError) else "config" if isinstance(e, ConfigError) else "invalid_output" if isinstance(e, LLMOutputError) else "error"


class MeteredLLM:
    """Decorator: same structured_output() interface, plus a UsageRecord per call (success or failure)."""
    def __init__(self, inner, recorder, *, research_id, workspace_id, agent, task_key=None, prices=None, clock=time.monotonic):
        self.inner, self.recorder, self.prices, self.clock = inner, recorder, prices or PriceTable(), clock
        self.ctx = (research_id, workspace_id, task_key, agent)

    def structured_output(self, system: str, user: str) -> dict:
        t0 = self.clock()
        try:
            if hasattr(self.inner, "structured_output_ex"):
                out, usage = self.inner.structured_output_ex(system, user)
            else:
                out, usage = self.inner.structured_output(system, user), Usage()
        except Exception as e:
            self._record(t0, Usage(), False, _category(e))
            raise
        self._record(t0, usage, True, None)
        return out

    def _record(self, t0, usage, ok, category):
        r, w, t, a = self.ctx
        rec = UsageRecord(new_id(), r, w, t, a, str(getattr(self.inner, "name", type(self.inner).__name__)), str(getattr(self.inner, "model", "unknown")),
                          usage.input_tokens, usage.output_tokens, self.prices.estimate(usage) if ok else None,
                          int((self.clock() - t0) * 1000), ok, category, now())
        try:
            self.recorder.record(rec)
        except Exception:
            log.exception("could not record LLM usage")  # metering must never break research
