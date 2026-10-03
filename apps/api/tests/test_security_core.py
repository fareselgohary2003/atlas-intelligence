import base64
import io
import json
import logging
import threading
import unittest

from app.core import tokens
from app.core.ratelimit import MemoryLimiter, RedisLimiter, SafeLimiter, account_key, create_limiter
from app.observability.logging import JsonFormatter, bind_context, clear_context, current_context, redact_text, valid_request_id
from app.tools.base import Field, Schema, ToolContext, ToolDefinition
from app.tools.registry import ToolRegistry

SECRET = "unit-test-secret-value"


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


class TokenTests(unittest.TestCase):
    def test_round_trip_and_claims(self):
        tok, jti = tokens.issue("user-1", SECRET, 60, now=1000)
        c = tokens.decode(tok, SECRET, now=1001)
        self.assertEqual((c["sub"], c["jti"], c["exp"], c["iat"]), ("user-1", jti, 1060, 1000))
        self.assertNotEqual(tokens.issue("user-1", SECRET, 60)[1], tokens.issue("user-1", SECRET, 60)[1])

    def test_rejects_forgery_tampering_expiry_and_algorithm_confusion(self):
        tok, _ = tokens.issue("u", SECRET, 60, now=1000)
        h, b, s = tok.split(".")
        bad = [("wrong secret", lambda: tokens.decode(tok, "other-secret", now=1001)),
               ("expired", lambda: tokens.decode(tok, SECRET, now=1060)),
               ("tampered payload", lambda: tokens.decode(f"{h}.{b64({'sub': 'admin', 'exp': 9999999999, 'jti': 'x'})}.{s}", SECRET, now=1001)),
               ("alg none", lambda: tokens.decode(f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b}.", SECRET, now=1001)),
               ("alg none keeping sig", lambda: tokens.decode(f"{b64({'alg': 'none'})}.{b}.{s}", SECRET, now=1001)),
               ("RS256 header", lambda: tokens.decode(f"{b64({'alg': 'RS256'})}.{b}.{s}", SECRET, now=1001)),
               ("empty", lambda: tokens.decode("", SECRET)), ("garbage", lambda: tokens.decode("a.b.c", SECRET)),
               ("two parts", lambda: tokens.decode("a.b", SECRET)), ("not base64", lambda: tokens.decode("%%%.%%%.%%%", SECRET))]
        for name, fn in bad:
            with self.assertRaises(tokens.TokenError, msg=name):
                fn()
        for claims in ({"sub": "u", "jti": "j"}, {"sub": "u", "jti": "j", "exp": "9999999999"}, {"sub": "u", "jti": "j", "exp": True},
                       {"exp": 9999999999, "jti": "j"}, {"sub": "u", "exp": 9999999999}, {"sub": 5, "jti": "j", "exp": 9999999999}):
            with self.assertRaises(tokens.TokenError, msg=str(claims)):
                tokens.decode(tokens.encode(claims, SECRET), SECRET, now=1)

    def test_algorithm_header_must_be_hs256_even_when_the_signature_is_valid(self):
        for alg in ("none", "HS512", "RS256", ""):
            h, b = b64({"alg": alg, "typ": "JWT"}), b64({"sub": "u", "exp": 9999999999, "jti": "j"})
            tok = f"{h}.{b}.{tokens._sign(f'{h}.{b}'.encode(), SECRET)}"  # correctly signed with OUR key, wrong declared algorithm
            with self.assertRaises(tokens.TokenError, msg=alg):
                tokens.decode(tok, SECRET, now=1)

    def test_csrf_is_bound_to_the_session(self):
        t1, t2 = tokens.csrf_token(SECRET, "jti-1"), tokens.csrf_token(SECRET, "jti-2")
        self.assertNotEqual(t1, t2)
        self.assertTrue(tokens.verify_csrf(SECRET, "jti-1", t1))
        for bad in (t2, "", None, 5, t1 + "x", t1.upper() if t1 != t1.upper() else "zz"):
            self.assertFalse(tokens.verify_csrf(SECRET, "jti-1", bad), bad)
        self.assertFalse(tokens.verify_csrf("other-secret", "jti-1", t1))


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeRedis:  # test double with the three commands RedisLimiter uses
    def __init__(self):
        self.v, self.ttl_s = {}, {}

    def incr(self, k):
        self.v[k] = self.v.get(k, 0) + 1
        return self.v[k]

    def expire(self, k, s):
        self.ttl_s[k] = s

    def ttl(self, k):
        return self.ttl_s.get(k, -1)

    def delete(self, k):
        self.v.pop(k, None)


class RateLimitTests(unittest.TestCase):
    def test_sliding_window_blocks_then_recovers(self):
        c = Clock()
        lim = MemoryLimiter(c)
        self.assertEqual([lim.hit("k", 3, 10)[0] for _ in range(4)], [True, True, True, False])
        allowed, retry = lim.hit("k", 3, 10)
        self.assertEqual((allowed, retry >= 1), (False, True))
        c.t = 10.5
        self.assertTrue(lim.hit("k", 3, 10)[0])
        self.assertTrue(lim.hit("other", 3, 10)[0])  # keys are independent

    def test_reset(self):
        lim = MemoryLimiter(Clock())
        for _ in range(3):
            lim.hit("k", 3, 10)
        lim.reset("k")
        self.assertTrue(lim.hit("k", 3, 10)[0])

    def test_redis_limiter_counts_expires_and_reports_retry(self):
        r = FakeRedis()
        lim = RedisLimiter(r)
        res = [lim.hit("ip:1", 2, 60) for _ in range(3)]
        self.assertEqual([x[0] for x in res], [True, True, False])
        self.assertEqual((r.ttl_s["atlas:rl:ip:1"], res[2][1]), (60, 60))
        lim.reset("ip:1")
        self.assertTrue(lim.hit("ip:1", 2, 60)[0])

    def test_backend_failure_falls_back_in_process_and_is_logged(self):
        class Down:
            def hit(self, *a): raise ConnectionError("redis down")
            def reset(self, *a): raise ConnectionError("redis down")
        lim = SafeLimiter(Down(), MemoryLimiter(Clock()))
        with self.assertLogs("atlas.ratelimit", "ERROR"):
            self.assertEqual([lim.hit("k", 2, 10)[0] for _ in range(3)], [True, True, False])  # still limiting, just per-process

    def test_create_limiter_without_redis_is_in_process_and_account_keys_hide_emails(self):
        self.assertIsInstance(create_limiter({}).primary, MemoryLimiter)
        k = account_key(" Alice@Example.com ")
        self.assertEqual(k, account_key("alice@example.com"))
        self.assertNotIn("alice", k)


class LoggingTests(unittest.TestCase):
    def capture(self):
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        h.setFormatter(JsonFormatter())
        lg = logging.getLogger("atlas.test." + str(id(buf)))
        lg.handlers[:] = [h]
        lg.setLevel(logging.DEBUG)
        lg.propagate = False
        clear_context()
        return lg, buf

    def lines(self, buf):
        return [json.loads(l) for l in buf.getvalue().splitlines()]

    def test_json_lines_carry_correlation_context(self):
        lg, buf = self.capture()
        bind_context(request_id="req-12345678", research_id="r1", task_id="t1", agent="market", skipped=None)
        lg.info("hello", extra={"duration_ms": 12})
        rec = self.lines(buf)[0]
        self.assertEqual((rec["level"], rec["msg"], rec["request_id"], rec["research_id"], rec["task_id"], rec["agent"], rec["duration_ms"]),
                         ("INFO", "hello", "req-12345678", "r1", "t1", "market", 12))
        self.assertNotIn("skipped", rec)

    def test_secrets_never_reach_logs(self):
        lg, buf = self.capture()
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1In0.abcdefghijk"
        lg.info("calling with Authorization: Bearer abc.def-123 and key sk-LIVEKEY12345 jwt " + jwt + " https://x/?api_key=hunter2&a=1")
        lg.info("extra", extra={"authorization": "Bearer zzz", "api_key": "sk-12345678", "payload": {"password": "pw", "ok": 1, "note": "token=abc123"},
                                "cookie": "atlas_session=xyz", "items": ["Bearer qqq"]})
        try:
            raise RuntimeError("failed with sk-SECRETKEY99 and password=topsecret")
        except RuntimeError:
            lg.exception("boom")
        blob = buf.getvalue()
        for secret in ("abc.def-123", "LIVEKEY12345", jwt, "hunter2", "zzz", "sk-12345678", "pw\"", "abc123", "atlas_session=xyz", "qqq", "SECRETKEY99", "topsecret"):
            self.assertNotIn(secret, blob, secret)
        self.assertIn("[REDACTED]", blob)
        self.assertEqual(self.lines(buf)[-1]["error_type"], "RuntimeError")
        self.assertNotIn("Traceback", blob)

    def test_context_is_isolated_per_thread_and_cleared(self):
        clear_context()
        bind_context(research_id="main")
        seen = {}

        def worker():
            clear_context()
            bind_context(research_id="worker", task_id="t9")
            seen["w"] = current_context()
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        self.assertEqual((seen["w"], current_context()), ({"research_id": "worker", "task_id": "t9"}, {"research_id": "main"}))
        clear_context()
        self.assertEqual(current_context(), {})

    def test_request_id_validation(self):
        self.assertTrue(valid_request_id("abc-1234_5.6"))
        for bad in ("", "short", "x" * 65, "has space 1234", "new\nline1234", None, 5):
            self.assertFalse(valid_request_id(bad), bad)
        self.assertEqual(redact_text("Bearer a.b.c"), "Bearer [REDACTED]")

    def test_tool_logs_include_tool_execution_and_agent_context(self):
        lg_name = "atlas.tools"
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        h.setFormatter(JsonFormatter())
        lg = logging.getLogger(lg_name)
        old = (lg.handlers[:], lg.level, lg.propagate)
        lg.handlers[:], lg.propagate = [h], False
        lg.setLevel(logging.INFO)
        try:
            reg = ToolRegistry()
            seen = {}
            reg.register(ToolDefinition("echo", "d", Schema(text=Field(str)), Schema(echo=Field(str)),
                                        lambda a, c: seen.update(ctx=current_context()) or {"echo": a["text"]}, timeout=2))
            reg.grant("market", ["echo"])
            clear_context()
            bind_context(research_id="r1", task_id="t1", agent="market", request_id="req-12345678")
            events = []
            r = reg.execute("echo", {"text": "x"}, ToolContext("market", "t1", "r1", "w1", emit=lambda k, **f: events.append((k, f))))
            self.assertTrue(r.ok)
            rec = [json.loads(l) for l in buf.getvalue().splitlines()][-1]
            self.assertEqual((rec["msg"], rec["tool"], rec["agent"], rec["task_id"], rec["research_id"]), ("tool completed", "echo", "market", "t1", "r1"))
            self.assertEqual(rec["tool_execution_id"], seen["ctx"]["tool_execution_id"])  # same id inside the tool thread
            self.assertEqual(seen["ctx"]["request_id"], "req-12345678")  # propagated into the worker thread
            self.assertTrue(all(f.get("execution_id") == rec["tool_execution_id"] for k, f in events if k in ("TOOL_STARTED", "TOOL_COMPLETED")))
            self.assertNotIn("tool_execution_id", current_context())  # not leaked to the caller
        finally:
            lg.handlers[:], lg.level, lg.propagate = old


if __name__ == "__main__":
    unittest.main()
