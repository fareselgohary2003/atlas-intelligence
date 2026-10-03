import gzip
import unittest
import zlib

from app.tools.base import ToolError
from app.tools.fetch import FetchConfig, Fetcher, RawResponse

PUB = "93.184.216.34"


class Resolver:
    def __init__(self, table=None):
        self.table, self.calls = table or {}, []

    def __call__(self, host, port):
        self.calls.append(host)
        v = self.table.get(host, [PUB])
        return v.pop(0) if v and isinstance(v[0], list) else v  # list-of-lists = different answer per call


def resp(status=200, body=b"<html>ok</html>", ctype="text/html; charset=utf-8", extra=None, chunk=1024):
    h = {"content-type": ctype, **(extra or {})}
    return RawResponse(status, h, lambda n: (body[i:i + chunk] for i in range(0, len(body), chunk)), lambda: None)


class FakeTransport:
    def __init__(self, routes):
        self.routes, self.seen = routes, []

    def request(self, target, headers, ct, rt):
        self.seen.append((target.url, target.ips, headers))
        r = self.routes[target.url]
        return r() if callable(r) else r


def fetcher(routes, resolver=None, **cfg):
    t = FakeTransport(routes)
    return Fetcher(t, resolver or Resolver(), FetchConfig(**cfg)), t


class FetchTests(unittest.TestCase):
    def err(self, f, url="http://example.com/"):
        with self.assertRaises(ToolError) as cm:
            f.fetch(url)
        return cm.exception

    def test_success_and_no_credentials_headers(self):
        f, t = fetcher({"http://example.com/": resp(body="héllo".encode())})
        r = f.fetch("http://example.com/")
        self.assertEqual((r.status, r.text, r.content_type), (200, "héllo", "text/html"))
        hdrs = {k.lower() for k in t.seen[0][2]}
        self.assertFalse(hdrs & {"cookie", "authorization"})

    def test_redirect_followed_and_recorded(self):
        f, _ = fetcher({"http://example.com/a": resp(301, extra={"location": "/b"}), "http://example.com/b": resp()})
        r = f.fetch("http://example.com/a")
        self.assertEqual((r.url, r.redirects), ("http://example.com/b", ["http://example.com/a"]))

    def test_redirect_to_private_or_bad_scheme_is_blocked(self):
        for loc in ("http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "ftp://example.com/x",
                    "file:///etc/passwd", "http://2130706433/", "http://internal.example/"):
            f, t = fetcher({"http://example.com/": resp(302, extra={"location": loc})},
                           Resolver({"internal.example": ["10.0.0.9"]}))
            e = self.err(f)
            self.assertEqual(e.category, "security", loc)
            self.assertEqual(len(t.seen), 1)  # the forbidden target was never contacted

    def test_redirect_via_hostname_resolving_to_private_is_blocked(self):
        f, _ = fetcher({"http://example.com/": resp(302, extra={"location": "http://evil.example/"})},
                       Resolver({"evil.example": ["192.168.0.5"]}))
        self.assertEqual(self.err(f).category, "security")

    def test_excessive_redirects_and_missing_location(self):
        f, _ = fetcher({"http://example.com/": resp(302, extra={"location": "/"})}, max_redirects=3)
        self.assertEqual(self.err(f).message, "Too many redirects")
        f, _ = fetcher({"http://example.com/": resp(302)})
        self.assertEqual(self.err(f).category, "upstream")

    def test_dns_rebinding_connection_uses_validated_ip_and_single_resolution(self):
        res = Resolver({"rebind.example": [[PUB], ["127.0.0.1"]]})  # second lookup would answer loopback
        f, t = fetcher({"http://rebind.example/": resp()}, res)
        f.fetch("http://rebind.example/")
        self.assertEqual(t.seen[0][1], (PUB,))
        self.assertEqual(res.calls, ["rebind.example"])

    def test_size_limits(self):
        f, _ = fetcher({"http://example.com/": resp(extra={"content-length": "999999"})}, max_bytes=1000)
        self.assertEqual(self.err(f).category, "too_large")
        f, _ = fetcher({"http://example.com/": resp(body=b"a" * 5000)}, max_bytes=1000)  # no Content-Length
        self.assertEqual(self.err(f).category, "too_large")

    def test_decompression_bomb_and_encodings(self):
        bomb = gzip.compress(b"0" * 5_000_000)
        f, _ = fetcher({"http://example.com/": resp(body=bomb, extra={"content-encoding": "gzip"})}, max_bytes=100_000)
        self.assertLess(len(bomb), 100_000)
        self.assertEqual(self.err(f).category, "too_large")
        f, _ = fetcher({"http://example.com/": resp(body=gzip.compress(b"<p>zipped</p>"), extra={"content-encoding": "gzip"})})
        self.assertEqual(f.fetch("http://example.com/").text, "<p>zipped</p>")
        for wb in (zlib.MAX_WBITS, -zlib.MAX_WBITS):  # zlib-wrapped and raw deflate
            c = zlib.compressobj(wbits=wb)
            data = c.compress(b"<p>deflated</p>") + c.flush()
            f, _ = fetcher({"http://example.com/": resp(body=data, extra={"content-encoding": "deflate"})})
            self.assertEqual(f.fetch("http://example.com/").text, "<p>deflated</p>")
        f, _ = fetcher({"http://example.com/": resp(body=b"not gzip", extra={"content-encoding": "gzip"})})
        self.assertEqual(self.err(f).category, "upstream")
        f, _ = fetcher({"http://example.com/": resp(extra={"content-encoding": "br"})})
        self.assertEqual(self.err(f).category, "unsupported_content")

    def test_content_types_and_binary(self):
        for ct in ("application/pdf", "image/png", "application/octet-stream", ""):
            f, _ = fetcher({"http://example.com/": resp(ctype=ct)})
            self.assertEqual(self.err(f).category, "unsupported_content", ct)
        f, _ = fetcher({"http://example.com/": resp(body=b"\x00\x01\x02binary", ctype="text/html")})
        self.assertEqual(self.err(f).category, "unsupported_content")

    def test_status_codes(self):
        for code, cat, retry in ((404, "upstream", False), (403, "upstream", False), (429, "upstream_transient", True),
                                 (503, "upstream_transient", True), (500, "upstream_transient", True)):
            f, _ = fetcher({"http://example.com/": resp(code)})
            e = self.err(f)
            self.assertEqual((e.category, e.retryable), (cat, retry), code)

    def test_charset_detection(self):
        f, _ = fetcher({"http://example.com/": resp(body="café".encode("latin-1"), ctype="text/html; charset=iso-8859-1")})
        self.assertEqual(f.fetch("http://example.com/").text, "café")
        meta = b'<html><head><meta charset="windows-1252"></head><body>caf\xe9</body></html>'
        f, _ = fetcher({"http://example.com/": resp(body=meta, ctype="text/html")})
        self.assertIn("café", f.fetch("http://example.com/").text)
        f, _ = fetcher({"http://example.com/": resp(body=b"caf\xe9", ctype="text/html; charset=bogus-charset")})
        self.assertIn("caf", f.fetch("http://example.com/").text)  # unknown label falls back instead of crashing

    def test_total_timeout_and_cancellation(self):
        now = {"t": 0.0}

        def slow_body(n):
            for _ in range(3):
                now["t"] += 10
                yield b"x"
        r = RawResponse(200, {"content-type": "text/html"}, slow_body, lambda: None)
        t = FakeTransport({"http://example.com/": r})
        f = Fetcher(t, Resolver(), FetchConfig(total_timeout=15), clock=lambda: now["t"])
        self.assertEqual(self.err(f).category, "timeout")

        import threading
        ev = threading.Event()
        ev.set()
        f, _ = fetcher({"http://example.com/": resp()})
        with self.assertRaises(ToolError) as cm:
            f.fetch("http://example.com/", cancel=ev)
        self.assertEqual(cm.exception.category, "timeout")

    def test_connection_failure_while_reading_is_retryable(self):
        def broken(n):
            yield b"x"
            raise ConnectionResetError()
        f, _ = fetcher({"http://example.com/": RawResponse(200, {"content-type": "text/html"}, broken, lambda: None)})
        e = self.err(f)
        self.assertEqual((e.category, e.retryable), ("network", True))

    def test_response_is_always_closed(self):
        closed = []
        r = RawResponse(404, {}, lambda n: iter(()), lambda: closed.append(1))
        f, _ = fetcher({"http://example.com/": r})
        self.err(f)
        self.assertEqual(closed, [1])


if __name__ == "__main__":
    unittest.main()
