"""Real sockets against a throwaway local HTTP server (loopback only, no external network)."""
import gzip
import http.server
import socket
import threading
import unittest

from app.tools.base import ToolError
from app.tools.fetch import Fetcher, HttpTransport
from app.tools.ssrf import Target, system_resolver

HITS = []


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        HITS.append({"path": self.path, "host": self.headers.get("Host"), "cookie": self.headers.get("Cookie"),
                     "auth": self.headers.get("Authorization")})
        body = gzip.compress(b"<html>hello</html>") if self.path == "/gz" else b"<html>hello</html>" * 1000
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        if self.path == "/gz":
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        HITS.clear()

    def target(self, path="/x", ips=("127.0.0.1",), port=None):
        return Target(f"http://example.test{path}", "http", "example.test", port or self.port, path, ips)

    def test_connects_to_pinned_ip_but_sends_original_host_header(self):
        r = HttpTransport().request(self.target(), {"User-Agent": "t"}, 2, 2)
        body = b"".join(r.chunks(4096))
        r.close()
        self.assertEqual((r.status, len(body)), (200, len(b"<html>hello</html>") * 1000))
        self.assertEqual(HITS[0]["host"], f"example.test:{self.port}")  # hostname, not the IP we dialled
        self.assertEqual(r.headers["content-type"], "text/html")

    def test_falls_through_unreachable_ip_and_reports_connect_failure(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead = s.getsockname()[1]
        s.close()
        with self.assertRaises(ToolError) as cm:
            HttpTransport().request(self.target(port=dead), {}, 1, 1)
        self.assertEqual((cm.exception.category, cm.exception.retryable), ("network", True))

    def test_fetcher_never_contacts_loopback_even_over_real_sockets(self):
        f = Fetcher(HttpTransport(), system_resolver)
        for url in (f"http://127.0.0.1:{self.port}/x", f"http://localhost:{self.port}/x", "http://2130706433/x"):
            with self.assertRaises(ToolError) as cm:
                f.fetch(url)
            self.assertEqual(cm.exception.category, "security", url)
        self.assertEqual(HITS, [])


if __name__ == "__main__":
    unittest.main()
