"""SSRF guard. validate_url() resolves once, checks EVERY address, and returns the IPs the caller must connect to
(pinning), so DNS cannot change between check and use. Pure logic + injectable resolver: testable offline."""
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

from app.tools.base import ToolError

ALLOWED_PORTS = (80, 443, 8080, 8443)
BLOCKED_NAMES = {"localhost"}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain", ".lan", ".home.arpa")


class SecurityError(ToolError):
    def __init__(self, message):
        super().__init__("security", message, False)


@dataclass(frozen=True)
class Target:
    url: str
    scheme: str
    host: str
    port: int
    path: str
    ips: tuple


def parse_legacy_ipv4(host: str):
    """inet_aton-style forms (2130706433, 0x7f.1, 0177.0.0.1, 127.1) that libc resolvers accept as IPv4 literals."""
    parts = host.split(".")
    if not 1 <= len(parts) <= 4 or "" in parts:
        return None
    nums = []
    for p in parts:
        if re.fullmatch(r"0[xX][0-9a-fA-F]+", p):
            nums.append(int(p, 16))
        elif re.fullmatch(r"0[0-7]*", p):
            nums.append(int(p, 8))
        elif re.fullmatch(r"[1-9][0-9]*", p):
            nums.append(int(p))
        else:
            return None
    *head, last = nums
    if any(h > 255 for h in head) or last >= 256 ** (4 - len(head)):
        return None
    val = 0
    for h in head:
        val = (val << 8) | h
    return str(ipaddress.IPv4Address((val << (8 * (4 - len(head)))) | last))


def ip_is_public(ip) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.teredo or int(ip) < 2 ** 32:  # Teredo tunnels; IPv4-compatible ::a.b.c.d
            return False
        emb = ip.ipv4_mapped or ip.sixtofour
        if emb is None and ip.packed[:12] == bytes.fromhex("0064ff9b0000000000000000"):  # NAT64
            emb = ipaddress.IPv4Address(ip.packed[12:])
        if emb is not None and not ip_is_public(emb):
            return False
    return ip.is_global and not ip.is_multicast


def system_resolver(host: str, port: int) -> list:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ToolError("network", "DNS resolution failed", True)
    return list(dict.fromkeys(i[4][0].split("%")[0] for i in infos))


def _bad(msg="Malformed URL"):
    raise SecurityError(msg)


def validate_url(url, resolver=system_resolver, allowed_ports=ALLOWED_PORTS) -> Target:
    if not isinstance(url, str) or not url or len(url) > 2048:
        _bad()
    if "\\" in url or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        _bad()
    try:
        sp = urlsplit(url)
        port = sp.port
    except ValueError:
        _bad()
    scheme = sp.scheme.lower()
    if scheme not in ("http", "https"):
        _bad("Only http and https URLs are allowed")
    if sp.username is not None or sp.password is not None or "@" in sp.netloc:
        _bad("URLs with embedded credentials are not allowed")
    host = (sp.hostname or "").rstrip(".")
    if not host or "%" in host:
        _bad()
    port = port or (443 if scheme == "https" else 80)
    if port not in allowed_ports:
        _bad("Port is not allowed")
    if host in BLOCKED_NAMES or host.endswith(BLOCKED_SUFFIXES):
        _bad("Host is not allowed")
    literal = parse_legacy_ipv4(host)
    if literal is None and ":" in host:
        try:
            literal = str(ipaddress.IPv6Address(host))
        except ValueError:
            _bad()
    if literal:
        ips = [literal]
    else:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            _bad()
        ips = resolver(host, port)
        if not ips:
            raise ToolError("network", "Host did not resolve", True)
    for ip in ips:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            _bad("Host resolved to an invalid address")
        if not ip_is_public(addr):
            _bad("URL resolves to a non-public address")
    path = quote(sp.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if sp.query:
        path += "?" + quote(sp.query, safe="/%:@!$&'()*+,;=-._~?")
    return Target(url, scheme, host, port, path, tuple(ips))
