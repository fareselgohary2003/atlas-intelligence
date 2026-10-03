"""Structured JSON logging with correlation context and secret redaction."""
import contextvars
import json
import logging
import re
import sys
from datetime import datetime, timezone

_ctx: contextvars.ContextVar = contextvars.ContextVar("atlas_ctx", default={})
REDACT_KEYS = re.compile(r"(authorization|api[_-]?key|password|passwd|secret|token|cookie|jwt|bearer|credential)", re.I)
PATTERNS = (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=\-]+", re.I), re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}"),
            re.compile(r"\beyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}"),
            re.compile(r"((?:api[_-]?key|password|secret|token)=)[^&\s]+", re.I))
STD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}
REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")


def bind_context(**kw):
    """Attach correlation ids (request_id, research_id, task_id, agent, tool, tool_execution_id...) to every log line in this context."""
    _ctx.set({**_ctx.get(), **{k: v for k, v in kw.items() if v is not None}})


def clear_context():
    _ctx.set({})


def current_context() -> dict:
    return dict(_ctx.get())


def valid_request_id(v) -> bool:
    return isinstance(v, str) and bool(REQUEST_ID.fullmatch(v))


def redact_text(s: str) -> str:
    for p in PATTERNS:
        s = p.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", s)
    return s


def _clean(k, v):
    if REDACT_KEYS.search(str(k)):
        return "[REDACTED]"
    if isinstance(v, str):
        return redact_text(v)
    if isinstance(v, dict):
        return {str(a): _clean(a, b) for a, b in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(k, x) for x in v][:50]
    return v if v is None or isinstance(v, (int, float, bool)) else redact_text(str(v))


class JsonFormatter(logging.Formatter):
    def format(self, record):
        out = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(), "level": record.levelname, "logger": record.name,
               "msg": redact_text(record.getMessage()), **{k: _clean(k, v) for k, v in _ctx.get().items()}}
        for k, v in record.__dict__.items():
            if k not in STD:
                out[k] = _clean(k, v)
        if record.exc_info:
            out["error_type"] = record.exc_info[0].__name__
            out["error"] = redact_text(str(record.exc_info[1]))[:500]  # message only; no frames/locals that could hold secrets
        return json.dumps(out, default=str, ensure_ascii=False)


def configure_logging(level="INFO", stream=None):
    h = logging.StreamHandler(stream or sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(level)
