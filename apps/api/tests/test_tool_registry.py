import time
import unittest

from app.agents.state import ConfigError, TransientError
from app.tools.base import Field, Schema, ToolContext, ToolDefinition, ToolError, ToolFailure
from app.tools.builtin import build_default_registry
from app.tools.registry import ToolRegistry
from app.agents.events import public_event

IN = Schema(text=Field(str, max_length=50), n=Field(int, False, 1, minimum=1, maximum=5))
OUT = Schema(echo=Field(str))


def tool(name="echo", fn=None, timeout=2, **kw):
    return ToolDefinition(name, "test tool", kw.pop("input", IN), kw.pop("output", OUT),
                          fn or (lambda a, c: {"echo": a["text"]}), timeout=timeout,
                          summarize=lambda o: {"len": len(o["echo"]), "nested": {"x": 1}, "secret": None}, **kw)


class Rec:
    def __init__(self):
        self.events = []

    def __call__(self, kind, **f):
        self.events.append({"kind": kind, **f})


def setup(*tools, grant=("echo",)):
    reg = ToolRegistry()
    for t in tools or (tool(),):
        reg.register(t)
    reg.grant("market", list(grant))
    rec = Rec()
    return reg, rec, ToolContext("market", "t1", "r1", emit=rec)


class RegistryTests(unittest.TestCase):
    def test_register_lookup_duplicate_and_grant_validation(self):
        reg, _, _ = setup()
        with self.assertRaises(ValueError):
            reg.register(tool())
        with self.assertRaises(ToolError) as cm:
            reg.get("nope")
        self.assertEqual(cm.exception.category, "unknown_tool")
        with self.assertRaises(ValueError):
            reg.grant("market", ["ghost"])

    def test_success_events_metadata_and_defaults(self):
        reg, rec, ctx = setup()
        r = reg.execute("echo", {"text": "hi"}, ctx)
        self.assertTrue(r.ok)
        self.assertEqual(r.unwrap(), {"echo": "hi"})
        self.assertEqual([e["kind"] for e in rec.events], ["TOOL_STARTED", "TOOL_COMPLETED"])
        done = rec.events[1]
        self.assertEqual((done["tool"], done["agent"], done["task_id"], done["ok"]), ("echo", "market", "t1", True))
        self.assertIn("duration_ms", done)
        self.assertEqual(done["result_meta"], {"len": 2, "secret": None})  # nested dict dropped: only scalars may appear in events

    def test_validation_errors_do_not_echo_values_and_skip_execution(self):
        ran = []
        reg, rec, ctx = setup(tool(fn=lambda a, c: ran.append(1) or {"echo": ""}))
        for bad in ({}, {"text": 5}, {"text": "x" * 51}, {"text": "ok", "n": 0}, {"text": "ok", "n": True},
                    {"text": "ok", "extra": 1}, "not a dict"):
            r = reg.execute("echo", bad, ctx)
            self.assertEqual((r.ok, r.error_category), (False, "validation"), bad)
        r = reg.execute("echo", {"text": "SECRET-VALUE", "n": 99}, ctx)
        self.assertNotIn("SECRET-VALUE", r.error + str(rec.events))
        self.assertEqual(ran, [])

    def test_agent_authorization_default_deny(self):
        reg, rec, _ = setup()
        r = reg.execute("echo", {"text": "x"}, ToolContext("risk", "t9", emit=rec))
        self.assertEqual(r.error_category, "unauthorized")
        self.assertEqual(rec.events[-1]["kind"], "TOOL_FAILED")
        self.assertEqual(reg.describe("risk"), [])
        self.assertEqual([t["name"] for t in reg.describe("market")], ["echo"])
        self.assertEqual(reg.execute("ghost", {}, ToolContext("market", emit=rec)).error_category, "unknown_tool")

    def test_timeout_sets_cancel_and_is_retryable(self):
        seen = {}

        def slow(a, ctx):
            seen["cancel"] = ctx.cancel
            ctx.cancel.wait(2)
            return {"echo": "late"}
        reg, rec, ctx = setup(tool(fn=slow, timeout=0.1))
        r = reg.execute("echo", {"text": "x"}, ctx)
        self.assertEqual((r.ok, r.error_category, r.retryable), (False, "timeout", True))
        time.sleep(0.05)
        self.assertTrue(seen["cancel"].is_set())
        with self.assertRaises(TransientError):
            r.unwrap()

    def test_summarize_failure_cannot_break_a_successful_call(self):
        t = tool()
        t.summarize = lambda o: o["missing"]
        reg, rec, ctx = setup(t)
        with self.assertLogs("atlas.tools", "ERROR"):
            r = reg.execute("echo", {"text": "x"}, ctx)
        self.assertTrue(r.ok)
        self.assertEqual(rec.events[-1]["result_meta"], {})

    def test_exception_normalization(self):
        def boom(a, c):
            raise RuntimeError("db password=hunter2")
        cases = ((boom, "internal", False), (lambda a, c: (_ for _ in ()).throw(ConfigError("no key")), "config", False),
                 (lambda a, c: (_ for _ in ()).throw(TransientError("429")), "upstream_transient", True),
                 (lambda a, c: (_ for _ in ()).throw(ToolError("security", "blocked")), "security", False))
        for fn, cat, retry in cases:
            reg, rec, ctx = setup(tool(fn=fn))
            with self.assertLogs("atlas.tools", "ERROR") if cat == "internal" else _null():
                r = reg.execute("echo", {"text": "x"}, ctx)
            self.assertEqual((r.error_category, r.retryable), (cat, retry))
            self.assertNotIn("hunter2", str(r.error) + str(rec.events))
        with self.assertRaises(ConfigError):
            reg2, _, c2 = setup(tool(fn=cases[1][0]))
            reg2.execute("echo", {"text": "x"}, c2).unwrap()
        with self.assertRaises(ToolFailure):
            reg3, _, c3 = setup(tool(fn=cases[3][0]))
            reg3.execute("echo", {"text": "x"}, c3).unwrap()

    def test_bad_tool_output_is_contained(self):
        reg, _, ctx = setup(tool(fn=lambda a, c: {"echo": 123}))
        with self.assertLogs("atlas.tools", "ERROR"):
            r = reg.execute("echo", {"text": "x"}, ctx)
        self.assertEqual(r.error_category, "internal")

    def test_emitter_failure_does_not_break_the_tool(self):
        reg, _, _ = setup()

        def bad_emit(*a, **k):
            raise RuntimeError("db down")
        with self.assertLogs("atlas.tools", "ERROR"):
            r = reg.execute("echo", {"text": "x"}, ToolContext("market", emit=bad_emit))
        self.assertTrue(r.ok)

    def test_events_carry_no_arguments_or_secrets_and_survive_the_public_filter(self):
        secret = "sk-LIVE-SECRET"
        reg = build_default_registry(lambda: (_ for _ in ()).throw(ConfigError("WEB_SEARCH_API_KEY is not set")), None, ["market"])
        rec = Rec()
        r = reg.execute("web_search", {"query": f"confidential strategy {secret}"}, ToolContext("market", "t1", emit=rec))
        self.assertEqual(r.error_category, "config")  # explicit failure, no fake results
        self.assertNotIn(secret, str(rec.events))
        for ev in rec.events:
            pub = public_event({**ev, "ts": 0, "seq": 1, "reasoning": "x"})
            self.assertNotIn("reasoning", pub)
            self.assertEqual(pub["tool"], "web_search")

    def test_builtin_pipeline_fetch_extract_normalize_with_injected_fetcher(self):
        from app.tools.fetch import FetchResult
        from datetime import datetime, timezone
        html = "<html><head><title>T</title></head><body><article>" + "Market grew strongly this year. " * 20 + "</article></body></html>"

        class F:
            def fetch(self, url, cancel=None):
                return FetchResult("https://example.com/r", 200, "text/html", html, len(html), [], datetime.now(timezone.utc))
        reg = build_default_registry(lambda: None, F(), ["market"])
        ctx = ToolContext("market", "t1", emit=Rec())
        page = reg.execute("fetch_url", {"url": "https://example.com/r"}, ctx).unwrap()
        ext = reg.execute("extract_page_content", {"html": page["text"], "content_type": page["content_type"], "base_url": page["url"]}, ctx).unwrap()
        src = reg.execute("normalize_source", {"url": page["url"], "text": ext["text"], "title": ext["title"], "is_demo": False}, ctx).unwrap()
        self.assertEqual((src["domain"], src["is_demo"], src["title"]), ("example.com", False, "T"))
        self.assertEqual(len(src["content_hash"]), 64)
        empty = reg.execute("normalize_source", {"url": "https://a.com/", "text": "tiny"}, ctx)
        self.assertEqual(empty.error_category, "empty_content")


class _null:
    def __enter__(self): return self
    def __exit__(self, *a): return False


if __name__ == "__main__":
    unittest.main()
