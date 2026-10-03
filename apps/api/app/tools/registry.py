"""ToolRegistry: agents depend on this, never on tool implementations or provider SDKs."""
import contextvars
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import replace

from app.agents.state import ConfigError, TransientError
from app.observability.logging import bind_context
from app.tools.base import ToolContext, ToolDefinition, ToolError, ToolResult

log = logging.getLogger("atlas.tools")


def _safe_meta(meta: dict) -> dict:
    return {str(k)[:40]: (v[:120] if isinstance(v, str) else v) for k, v in list((meta or {}).items())[:10]
            if v is None or isinstance(v, (str, int, float, bool))}


class ToolRegistry:
    def __init__(self, max_workers: int = 8):
        self._tools: dict[str, ToolDefinition] = {}
        self._grants: dict[str, set] = {}
        self._pool = ThreadPoolExecutor(max_workers, thread_name_prefix="tool")

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def names(self) -> list:
        return sorted(self._tools)

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolError("unknown_tool", "Unknown tool")

    def grant(self, agent: str, tool_names) -> None:
        unknown = [n for n in tool_names if n not in self._tools]
        if unknown:
            raise ValueError(f"Cannot grant unregistered tools: {unknown}")
        self._grants.setdefault(agent, set()).update(tool_names)

    def describe(self, agent: str) -> list[dict]:
        """What an agent (or its LLM) may call. Default deny: no grant, no tools."""
        return [{"name": t.name, "description": t.description, "input": t.input.describe(), "metadata": t.metadata}
                for n, t in self._tools.items() if n in self._grants.get(agent, ())]

    def _emit(self, ctx: ToolContext, kind: str, **fields):
        if not ctx.emit:
            return
        try:
            ctx.emit(kind, agent=ctx.agent, task_id=ctx.task_id, **fields)
        except Exception:
            log.exception("tool event emit failed")  # telemetry failure must not change the tool outcome

    def _fail(self, name, ctx, err: ToolError, start) -> ToolResult:
        ms = int((time.monotonic() - start) * 1000)
        name = name[:60] if isinstance(name, str) else "?"
        self._emit(ctx, "TOOL_FAILED", tool=name, ok=False, error_category=err.category, error=err.message, duration_ms=ms)
        log.info("tool failed", extra={"tool": name, "agent": ctx.agent, "task_id": ctx.task_id,
                                       "category": err.category, "duration_ms": ms})
        return ToolResult(name, False, None, err.category, err.message, err.retryable, ms)

    def execute(self, name: str, args: dict, ctx: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            tool = self.get(name)
            if name not in self._grants.get(ctx.agent, ()):
                log.warning("unauthorized tool call", extra={"tool": name, "agent": ctx.agent})
                raise ToolError("unauthorized", f"Agent '{ctx.agent}' is not permitted to use this tool")
            clean = tool.input.validate(args)
        except ToolError as e:
            return self._fail(name, ctx, e, start)

        exec_id = uuid.uuid4().hex[:12]
        self._emit(ctx, "TOOL_STARTED", tool=name, execution_id=exec_id)
        cancel = threading.Event()
        cv = contextvars.copy_context()  # the tool thread inherits request/research/task/agent ids; the tool id is bound in the copy only
        cv.run(bind_context, tool=name, tool_execution_id=exec_id)
        fut = self._pool.submit(cv.run, tool.execute, clean, replace(ctx, cancel=cancel))
        err, out = None, None
        try:
            out = fut.result(timeout=tool.timeout)
        except FutureTimeout:
            cancel.set()  # cooperative: fetches stop between chunks/hops
            fut.cancel()
            err = ToolError("timeout", f"Tool timed out after {tool.timeout:g}s")
        except ToolError as e:
            err = e
        except ConfigError as e:
            err = ToolError("config", str(e))
        except TransientError as e:
            err = ToolError("upstream_transient", str(e))
        except Exception:
            log.exception("tool crashed: %s", name)
            err = ToolError("internal", "Tool failed unexpectedly")
        if err is None:
            try:
                out = tool.output.validate(out)  # guards against a buggy tool leaking odd shapes
            except ToolError:
                log.error("tool %s returned output violating its schema", name)
                err = ToolError("internal", "Tool returned an invalid result")
        if err:
            return self._fail(name, ctx, err, start)
        ms = int((time.monotonic() - start) * 1000)
        try:
            meta = _safe_meta(tool.summarize(out))
        except Exception:
            log.exception("summarize failed for tool %s", name)  # metadata is best-effort; the result stands
            meta = {}
        self._emit(ctx, "TOOL_COMPLETED", tool=name, ok=True, duration_ms=ms, result_meta=meta, execution_id=exec_id)
        log.info("tool completed", extra={"tool": name, "tool_execution_id": exec_id, "agent": ctx.agent, "task_id": ctx.task_id, "duration_ms": ms})
        return ToolResult(name, True, out, duration_ms=ms)
