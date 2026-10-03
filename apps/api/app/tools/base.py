"""Tool contract: typed schemas, results, and one error taxonomy shared by every tool."""
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from app.agents.state import ConfigError, TransientError

RETRYABLE = {"timeout", "network", "upstream_transient"}
# validation unauthorized unknown_tool timeout config network upstream upstream_transient security
# unsupported_content too_large empty_content internal


class ToolError(Exception):
    def __init__(self, category: str, message: str, retryable: bool | None = None):
        super().__init__(message)
        self.category, self.message = category, message
        self.retryable = category in RETRYABLE if retryable is None else retryable


class ToolFailure(Exception):
    """Raised by ToolResult.unwrap() for non-retryable failures."""
    def __init__(self, category, message):
        super().__init__(f"{category}: {message}")
        self.category = category


@dataclass(frozen=True)
class Field:
    type: Any = str
    required: bool = True
    default: Any = None
    min_length: int | None = None
    max_length: int | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple | None = None
    item_type: Any = None
    description: str = ""


def _check(name: str, f: Field, v):
    t = f.type
    ok = (not isinstance(v, bool) and isinstance(v, int)) if t is int else \
         (not isinstance(v, bool) and isinstance(v, (int, float))) if t is float else isinstance(v, t)
    if not ok:
        raise ToolError("validation", f"'{name}' must be of type {t.__name__}")  # never echo the value
    if t is float:
        v = float(v)
    if isinstance(v, (str, list, dict)):
        if f.min_length is not None and len(v) < f.min_length:
            raise ToolError("validation", f"'{name}' is too short")
        if f.max_length is not None and len(v) > f.max_length:
            raise ToolError("validation", f"'{name}' is too long")
    if t in (int, float):
        if (f.minimum is not None and v < f.minimum) or (f.maximum is not None and v > f.maximum):
            raise ToolError("validation", f"'{name}' is out of range")
    if f.choices is not None and v not in f.choices:
        raise ToolError("validation", f"'{name}' has an unsupported value")
    if t is list and f.item_type and not all(isinstance(i, f.item_type) for i in v):
        raise ToolError("validation", f"'{name}' has items of the wrong type")
    return v


class Schema:
    def __init__(self, **fields: Field):
        self.fields = fields

    def validate(self, data, allow_unknown=False) -> dict:
        if not isinstance(data, dict):
            raise ToolError("validation", "Arguments must be an object")
        errors, out = [], {}
        if not allow_unknown:
            errors += [f"unknown field '{k}'" for k in data if k not in self.fields]
        for name, f in self.fields.items():
            if data.get(name) is None:
                if f.required:
                    errors.append(f"'{name}' is required")
                elif f.default is not None:
                    out[name] = f.default
                continue
            try:
                out[name] = _check(name, f, data[name])
            except ToolError as e:
                errors.append(e.message)
        if errors:
            raise ToolError("validation", "; ".join(errors))
        return out

    def describe(self) -> dict:
        return {n: {"type": f.type.__name__, "required": f.required, "description": f.description,
                    **({"choices": list(f.choices)} if f.choices else {})} for n, f in self.fields.items()}


@dataclass
class ToolContext:
    agent: str
    task_id: str | None = None
    research_id: str | None = None
    workspace_id: str | None = None           # trusted, set by the engine; tools never take it from arguments
    emit: Callable[..., None] | None = None   # emit(kind, **safe_fields); the engine's state.emit fits
    cancel: threading.Event | None = None     # set by the registry on timeout; tools should poll it


@dataclass
class ToolDefinition:
    name: str
    description: str
    input: Schema
    output: Schema
    execute: Callable[[dict, ToolContext], dict]
    timeout: float = 30.0
    summarize: Callable[[dict], dict] = lambda out: {}  # safe, small metadata for events
    metadata: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)          # non-secret tool configuration, for introspection


@dataclass
class ToolResult:
    tool: str
    ok: bool
    data: dict | None = None
    error_category: str | None = None
    error: str | None = None
    retryable: bool = False
    duration_ms: int = 0

    def unwrap(self) -> dict:
        """Bridge to the engine: retryable failures become TransientError so the engine retries the task."""
        if self.ok:
            return self.data
        if self.error_category == "config":
            raise ConfigError(self.error)
        if self.retryable:
            raise TransientError(self.error)
        raise ToolFailure(self.error_category, self.error)
