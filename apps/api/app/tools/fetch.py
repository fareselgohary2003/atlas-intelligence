"""Bounded HTTP fetcher. Every hop (including redirects) is SSRF-validated and connects to the validated IP."""
import http.client
import re
import socket
import ssl
import time
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterator
from urllib.parse import urljoin

from app.tools.base import ToolError
from app.tools.ssrf import ALLOWED_PORTS, Target, system_resolver, validate_url

REDIRECTS = (301, 302, 303, 307, 308)


@dataclass
class FetchConfig:
    max_bytes: int = 2_000_000          # limit for both compressed and decompressed body
    max_redirects: int = 5
    connect_timeout: float = 5.0
    total_timeout: float = 20.0
    allowed_types: tuple = ("text/html", "application/xhtml+xml", "text/plain")
    allowed_ports: tuple = ALLOWED_PORTS
    user_agent: str = "AtlasResearchBot/0.1"


@dataclass
class RawResponse:
    status: int
    headers: dict                        # lower-case names
    chunks: Callable[[int], Iterator[bytes]]
    close: Callable[[], None]


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        raw = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)  # SNI + cert check use the hostname


class HttpTransport:
    """Connects to a pre-validated IP but speaks for the original hostname (Host header, SNI, cert verification)."""
    def request(self, target: Target, headers: dict, connect_timeout: float, read_timeout: float) -> RawResponse:
        for ip in target.ips:
            cls = _PinnedHTTPS if target.scheme == "https" else _PinnedHTTP
            conn = cls(target.host, ip, target.port, connect_timeout)
            try:
                conn.connect()
                conn.sock.settimeout(read_timeout)
                conn.request("GET", target.path, headers=headers)
                r = conn.getresponse()
            except (OSError, http.client.HTTPException):
                conn.close()
                continue

            def chunks(n, r=r):
                while True:
                    c = r.read(n)
                    if not c:
                        return
                    yield c
            return RawResponse(r.status, {k.lower(): v for k, v in r.getheaders()}, chunks, conn.close)
        raise ToolError("network", "Could not connect to the host", True)


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    text: str
    size: int
    redirects: list
    fetched_at: datetime


class Fetcher:
    def __init__(self, transport=None, resolver=system_resolver, config=None, clock=time.monotonic):
        self.transport, self.resolver = transport or HttpTransport(), resolver
        self.cfg, self.clock = config or FetchConfig(), clock

    def fetch(self, url: str, cancel=None) -> FetchResult:
        c, start, current, chain = self.cfg, self.clock(), url, []
        headers = {"User-Agent": c.user_agent, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
                   "Accept-Encoding": "gzip, deflate", "Connection": "close"}  # never any cookies or auth headers
        for _ in range(c.max_redirects + 1):
            target = validate_url(current, self.resolver, c.allowed_ports)  # re-validated on EVERY hop
            remaining = c.total_timeout - (self.clock() - start)
            if remaining <= 0:
                raise ToolError("timeout", "Fetch timed out")
            try:
                resp = self.transport.request(target, headers, min(c.connect_timeout, remaining), remaining)
            except TimeoutError:
                raise ToolError("timeout", "Connection timed out")
            try:
                if resp.status in REDIRECTS:
                    loc = resp.headers.get("location")
                    if not loc:
                        raise ToolError("upstream", "Redirect without a Location header")
                    chain.append(current)
                    current = urljoin(current, loc)
                    continue
                if not 200 <= resp.status < 300:
                    raise ToolError("upstream_transient" if resp.status in (408, 429) or resp.status >= 500 else "upstream",
                                    f"Server responded with HTTP {resp.status}")
                return self._body(resp, current, chain, start, cancel)
            finally:
                resp.close()
        raise ToolError("upstream", "Too many redirects")

    def _body(self, resp, url, chain, start, cancel) -> FetchResult:
        c = self.cfg
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype not in c.allowed_types:
            raise ToolError("unsupported_content", f"Unsupported content type '{ctype[:60] or 'missing'}'")
        enc = resp.headers.get("content-encoding", "identity").strip().lower() or "identity"
        if enc not in ("identity", "gzip", "deflate"):
            raise ToolError("unsupported_content", "Unsupported content encoding")
        cl = resp.headers.get("content-length", "")
        if cl.isdigit() and int(cl) > c.max_bytes:
            raise ToolError("too_large", "Response exceeds the size limit")
        raw = bytearray()
        try:
            for chunk in resp.chunks(65536):
                if cancel is not None and cancel.is_set():
                    raise ToolError("timeout", "Fetch cancelled")
                if self.clock() - start > c.total_timeout:
                    raise ToolError("timeout", "Fetch timed out")
                raw += chunk
                if len(raw) > c.max_bytes:
                    raise ToolError("too_large", "Response exceeds the size limit")
        except TimeoutError:
            raise ToolError("timeout", "Read timed out")
        except (OSError, http.client.HTTPException):
            raise ToolError("network", "Connection failed while reading the response", True)
        body = self._inflate(bytes(raw), enc) if enc != "identity" else bytes(raw)
        return FetchResult(url, 200, ctype, _decode(body, resp.headers.get("content-type", "")), len(body), chain,
                           datetime.now(timezone.utc))

    def _inflate(self, data: bytes, enc: str) -> bytes:
        for wbits in ([16 + zlib.MAX_WBITS] if enc == "gzip" else [zlib.MAX_WBITS, -zlib.MAX_WBITS]):
            d = zlib.decompressobj(wbits)
            try:
                out = d.decompress(data, self.cfg.max_bytes + 1)  # hard output cap: decompression bombs stop here
            except zlib.error:
                continue
            if len(out) > self.cfg.max_bytes:
                raise ToolError("too_large", "Decompressed response exceeds the size limit")
            if d.eof:
                return out
        raise ToolError("upstream", "Malformed compressed response")


def _decode(body: bytes, content_type_header: str) -> str:
    if b"\x00" in body[:1024] and not body.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ToolError("unsupported_content", "Response looks like binary data")
    m = re.search(r"charset=([\w.:-]+)", content_type_header, re.I) or \
        re.search(rb"<meta[^>]+charset=[\"']?([\w.:-]+)", body[:2048], re.I)
    if body.startswith(b"\xef\xbb\xbf"):
        return body.decode("utf-8-sig", "replace")
    if m:
        name = m.group(1).decode("ascii", "ignore") if isinstance(m.group(1), bytes) else m.group(1)
        try:
            return body.decode(name, "replace")
        except LookupError:
            pass  # unknown charset label: fall through to detection
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("cp1252", "replace")
