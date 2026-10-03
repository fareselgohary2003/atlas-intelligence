import http.server
import json
import threading
import time
import unittest

from app.agents.llm import OpenAICompatibleLLM, Usage
from app.agents.state import ConfigError, LLMOutputError, TransientError
from app.observability.usage import MeteredLLM, PriceTable
from tests.test_agents import ACME, Stack, finding, PAGES
from tests.test_factchecker import ALL


class Recorder:
    def __init__(self, fail=False):
        self.rows, self.fail = [], fail

    def record(self, rec):
        if self.fail:
            raise RuntimeError("db down")
        self.rows.append(rec)


class ExLLM:
    name, model = "fake-provider", "fake-model"

    def __init__(self, exc=None, usage=Usage(100, 50)):
        self.exc, self.usage = exc, usage

    def structured_output_ex(self, s, u):
        if self.exc:
            raise self.exc
        return {"findings": []}, self.usage


class PlainLLM:
    def structured_output(self, s, u):
        return {"ok": 1}


class MeteringTests(unittest.TestCase):
    def meter(self, inner, rec=None, prices=None):
        return MeteredLLM(inner, rec or Recorder(), research_id="r", workspace_id="w", agent="market", task_key="t1", prices=prices)

    def test_price_table(self):
        p = PriceTable(0.001, 0.002)
        self.assertEqual(p.estimate(Usage(100, 50)), 0.0002)
        self.assertIsNone(p.estimate(Usage(None, 50)))  # unreported tokens => no cost
        self.assertIsNone(PriceTable().estimate(Usage(100, 50)))  # no configured prices => no cost
        self.assertEqual(PriceTable.from_env({"LLM_PRICE_INPUT_PER_1K": "0.5", "LLM_PRICE_OUTPUT_PER_1K": "1.5"}).output_per_1k, 1.5)
        self.assertIsNone(PriceTable.from_env({}).input_per_1k)
        for bad in ("abc", "-1"):
            with self.assertRaises(ConfigError):
                PriceTable.from_env({"LLM_PRICE_INPUT_PER_1K": bad})

    def test_success_records_tokens_cost_and_context(self):
        rec = Recorder()
        out = self.meter(ExLLM(), rec, PriceTable(0.001, 0.002)).structured_output("SYSTEM PROMPT SECRET", "USER PROMPT SECRET")
        self.assertEqual(out, {"findings": []})
        r = rec.rows[0]
        self.assertEqual((r.agent, r.task_key, r.provider, r.model, r.input_tokens, r.output_tokens, r.estimated_cost, r.ok),
                         ("market", "t1", "fake-provider", "fake-model", 100, 50, 0.0002, True))
        self.assertNotIn("SECRET", repr(r))  # prompts are never stored

    def test_failures_are_recorded_and_reraised(self):
        for exc, cat in ((TransientError("429"), "transient"), (ConfigError("k"), "config"), (LLMOutputError("bad"), "invalid_output"), (RuntimeError("x"), "error")):
            rec = Recorder()
            with self.assertRaises(type(exc)):
                self.meter(ExLLM(exc), rec).structured_output("s", "u")
            self.assertEqual((rec.rows[0].ok, rec.rows[0].error_category, rec.rows[0].estimated_cost), (False, cat, None))

    def test_provider_without_usage_reporting_yields_none_not_zero(self):
        rec = Recorder()
        self.meter(PlainLLM(), rec, PriceTable(1, 1)).structured_output("s", "u")
        self.assertEqual((rec.rows[0].input_tokens, rec.rows[0].estimated_cost, rec.rows[0].model), (None, None, "unknown"))

    def test_recorder_failure_never_breaks_the_call(self):
        with self.assertLogs("atlas.usage", "ERROR"):
            self.assertEqual(self.meter(ExLLM(), Recorder(fail=True)).structured_output("s", "u"), {"findings": []})

    def test_agent_runs_are_metered_per_call_with_task_context(self):
        class UsageLLM(ExLLM):
            def structured_output_ex(self, s, u):
                p = json.loads(u)
                fs = [finding(ACME, "AcmeSoft Arabia lists a Team plan at USD 49 per user per month", "pricing", {"company": "AcmeSoft Arabia", "price": "49"}, PAGES[ACME][2][2])] if p["source_url"] == ACME else []
                return {"findings": fs}, Usage(100, 50)
        rec = Recorder()
        s = Stack(UsageLLM(), agents=ALL)
        runner = s.agents.runners(lambda: UsageLLM(), s.fu, recorder=rec, prices=PriceTable(0.001, 0.002))["pricing"]
        from app.agents.state import Task
        res = runner(s.state(), Task("t1", "Pricing plans for HR software vendors", "pricing"))
        self.assertGreaterEqual(len(rec.rows), 1)
        self.assertTrue(all((r.agent, r.task_key, r.research_id, r.workspace_id, r.input_tokens, r.estimated_cost) == ("pricing", "t1", "rA", "wA", 100, 0.0002) for r in rec.rows))
        self.assertEqual(res["counts"]["claims"], 1)


class Server:
    """Throwaway OpenAI-compatible endpoint on loopback (test only)."""
    def __init__(self, status=200, body=None, delay=0):
        self.status, self.body, self.delay, self.seen = status, body, delay, []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                outer.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": json.loads(self.rfile.read(n))})
                time.sleep(outer.delay)
                payload = outer.body if isinstance(outer.body, bytes) else json.dumps(outer.body).encode()
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def chat(content, usage=None):
    d = {"choices": [{"message": {"content": content}}]}
    if usage is not None:
        d["usage"] = usage
    return d


class OpenAICompatibleOverHttpTests(unittest.TestCase):
    def call(self, status=200, body=None, delay=0, timeout=2):
        srv = Server(status, body, delay)
        self.addCleanup(srv.close)
        llm = OpenAICompatibleLLM("sk-TOPSECRET", "test-model", srv.url, timeout=timeout)
        return llm, srv

    def test_request_shape_and_usage_parsing(self):
        llm, srv = self.call(body=chat('{"findings": []}', {"prompt_tokens": 12, "completion_tokens": 7}))
        out, usage = llm.structured_output_ex("sys", "user")
        self.assertEqual((out, usage), ({"findings": []}, Usage(12, 7)))
        req = srv.seen[0]
        self.assertEqual((req["path"], req["auth"], req["body"]["model"], req["body"]["response_format"]), ("/v1/chat/completions", "Bearer sk-TOPSECRET", "test-model", {"type": "json_object"}))
        self.assertEqual([m["role"] for m in req["body"]["messages"]], ["system", "user"])

    def test_missing_or_malformed_usage_is_none(self):
        for usage in (None, {}, {"prompt_tokens": "12", "completion_tokens": -1}, {"prompt_tokens": True}):
            llm, _ = self.call(body=chat('{"a": 1}', usage))
            self.assertEqual(llm.structured_output_ex("s", "u")[1], Usage(None, None), usage)

    def test_error_statuses_map_to_retry_config_or_invalid_and_never_leak_the_key(self):
        for status, exc in ((429, TransientError), (500, TransientError), (503, TransientError), (401, ConfigError), (403, ConfigError), (400, LLMOutputError)):
            llm, _ = self.call(status=status, body={"error": "x"})
            with self.assertRaises(exc, msg=status) as cm:
                llm.structured_output("s", "u")
            self.assertNotIn("TOPSECRET", str(cm.exception))

    def test_malformed_model_output_fails_safely(self):
        for body in (b"not json at all", chat("not json"), chat("[1, 2]"), chat('"a string"'), {"choices": []}, {"nothing": 1}, chat(None)):
            llm, _ = self.call(body=body)
            with self.assertRaises(LLMOutputError, msg=body):
                llm.structured_output("s", "u")

    def test_timeout_and_unreachable_are_transient(self):
        llm, _ = self.call(body=chat("{}"), delay=1.0, timeout=0.2)
        with self.assertRaises(TransientError):
            llm.structured_output("s", "u")
        dead = OpenAICompatibleLLM("k", "m", "http://127.0.0.1:1/v1", timeout=1)
        with self.assertRaises(TransientError):
            dead.structured_output("s", "u")

    def test_requires_a_key(self):
        with self.assertRaises(ConfigError):
            OpenAICompatibleLLM("", "m")


if __name__ == "__main__":
    unittest.main()
