"""Source normalization: canonical URLs, hashes, duplicate detection. Produces candidates for the future Source model;
nothing here persists or invents data."""
import hashlib
import posixpath
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SOURCE_TYPES = ("government", "company", "academic", "research", "news", "forum", "other")
TRACKING = re.compile(r"^(utm_.*|gclid|fbclid|mc_cid|mc_eid|igshid|msclkid|yclid)$", re.I)
FORUMS = {"reddit.com", "news.ycombinator.com", "stackoverflow.com", "stackexchange.com", "quora.com"}


def domain_of(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower().rstrip(".")
    return h[4:] if h.startswith("www.") else h


def normalize_url(url: str) -> str:
    sp = urlsplit(url.strip())
    host = (sp.hostname or "").lower().rstrip(".")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    host = f"[{host}]" if ":" in host else host
    default = 443 if sp.scheme.lower() == "https" else 80
    netloc = host if sp.port in (None, default) else f"{host}:{sp.port}"
    path = posixpath.normpath(sp.path) if sp.path else "/"
    path = "/" if path in (".", "") else path
    query = urlencode(sorted((k, v) for k, v in parse_qsl(sp.query, keep_blank_values=True) if not TRACKING.match(k)))
    return urlunsplit((sp.scheme.lower(), netloc, path, query, ""))  # fragment dropped, trailing slash dropped


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).casefold().encode()).hexdigest()


def classify_source_type(domain: str) -> str:
    """Heuristic by domain only. Callers with better knowledge (e.g. an agent) may override."""
    if re.search(r"(^|\.)(gov|mil)(\.[a-z]{2})?$", domain) or re.search(r"(^|\.)go\.[a-z]{2}$", domain):
        return "government"
    if re.search(r"(^|\.)edu(\.[a-z]{2})?$", domain) or re.search(r"(^|\.)ac\.[a-z]{2}$", domain):
        return "academic"
    if domain in FORUMS or any(domain.endswith("." + f) for f in FORUMS) or domain.startswith(("forum.", "community.")):
        return "forum"
    return "other"


@dataclass
class SourceCandidate:
    url: str
    canonical_url: str
    domain: str
    title: str | None
    publisher: str
    published_at: datetime | None
    retrieved_at: datetime
    source_type: str
    content_hash: str
    is_demo: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        d = self.__dict__.copy()
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        d["retrieved_at"] = self.retrieved_at.isoformat()
        return d


def make_candidate(*, url, text, title=None, publisher=None, published_at=None, canonical_url=None,
                   source_type=None, is_demo=False, metadata=None, retrieved_at=None) -> SourceCandidate:
    if source_type is not None and source_type not in SOURCE_TYPES:
        raise ValueError("invalid source_type")
    norm = normalize_url(url)
    dom = domain_of(norm)
    return SourceCandidate(norm, normalize_url(canonical_url) if canonical_url else norm, dom, title,
                           publisher or dom, published_at, retrieved_at or datetime.now(timezone.utc),
                           source_type or classify_source_type(dom), content_hash(text), is_demo, metadata or {})


class SourceDeduper:
    """In-memory, per research run. Persistent uniqueness is enforced by DB constraints when the sources table lands."""
    def __init__(self):
        self._urls, self._hashes, self._lock = {}, {}, threading.Lock()

    def register(self, c: SourceCandidate):
        """Returns None if new (and remembers it), else ('url'|'content', url_of_first_seen)."""
        with self._lock:
            for kind, key, seen in (("url", c.canonical_url, self._urls), ("content", c.content_hash, self._hashes)):
                if key in seen:
                    return kind, seen[key]
            self._urls[c.canonical_url] = self._hashes[c.content_hash] = c.url
            return None
