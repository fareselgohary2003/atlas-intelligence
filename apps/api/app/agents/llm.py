"""LLM abstraction. Only structured_output is implemented; generate/stream/embed are added when an agent needs them."""
import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from app.agents.state import ConfigError, LLMOutputError, TransientError


@dataclass(frozen=True)
class Usage:
    """Token usage as reported by the provider; None when the provider did not report it (never guessed)."""
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    def structured_output(self, system: str, user: str) -> dict: ...


class OpenAICompatibleLLM:
    def __init__(self, api_key, model, base_url="https://api.openai.com/v1", timeout=60):
        if not api_key:
            raise ConfigError("LLM_API_KEY is not set. Configure it, or run with DEMO_MODE=true.")
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url.rstrip("/"), timeout

    @classmethod
    def from_env(cls):
        return cls(os.getenv("LLM_API_KEY"), os.getenv("LLM_MODEL", "gpt-4o-mini"),
                   os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))

    def structured_output(self, system: str, user: str) -> dict:
        return self.structured_output_ex(system, user)[0]

    def structured_output_ex(self, system: str, user: str):
        """-> (parsed JSON object, Usage). Providers report usage differently; absent fields stay None."""
        body = {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        req = urllib.request.Request(self.base_url + "/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read(5_000_000)
        except urllib.error.HTTPError as e:
            if e.code in (408, 429) or e.code >= 500:
                raise TransientError(f"LLM HTTP {e.code}")
            if e.code in (401, 403):
                raise ConfigError("LLM credentials were rejected")
            raise LLMOutputError(f"LLM HTTP {e.code}")
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            raise TransientError(f"LLM unreachable: {e}")
        try:
            data = json.loads(raw)
        except ValueError:
            raise LLMOutputError("LLM returned a non-JSON response")
        try:
            parsed = json.loads(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError):
            raise LLMOutputError("LLM returned malformed JSON")
        if not isinstance(parsed, dict):
            raise LLMOutputError("LLM output must be a JSON object")
        u = data.get("usage") if isinstance(data, dict) else None
        num = lambda k: u.get(k) if isinstance(u, dict) and isinstance(u.get(k), int) and not isinstance(u.get(k), bool) and u.get(k) >= 0 else None
        return parsed, Usage(num("prompt_tokens"), num("completion_tokens"))
