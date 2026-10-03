"""HTML/text -> normalized content. Independent of search and fetch. Stdlib html.parser tolerates malformed markup."""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app.tools.base import ToolError

MAX_INPUT_CHARS = 3_000_000
MAX_TEXT_CHARS = 200_000
MAX_LINKS = 50
SKIP = {"script", "style", "noscript", "template", "svg", "iframe", "nav", "footer", "aside", "form"}
BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "main",
         "blockquote", "pre", "table", "ul", "ol"}
META_KEEP = ("description", "author", "og:site_name", "og:title", "og:type", "article:modified_time", "keywords")
DATE_KEYS = ("article:published_time", "og:article:published_time", "datepublished", "citation_publication_date",
             "dc.date", "dc.date.issued", "date", "pubdate", "publishdate")


def parse_date(s):
    if not isinstance(s, str) or not s.strip():
        return None
    s, d = s.strip(), None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = parsedate_to_datetime(s)
        except (TypeError, ValueError, IndexError):
            return None
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return d if 1900 <= d.year <= 2100 else None


@dataclass
class ExtractedContent:
    title: str | None
    text: str
    metadata: dict
    canonical_url: str | None
    published_at: datetime | None
    links: list = field(default_factory=list)
    language: str | None = None

    @property
    def is_empty(self):
        return len(self.text) < 50

    def to_dict(self):
        return {"title": self.title, "text": self.text, "metadata": self.metadata, "canonical_url": self.canonical_url,
                "published_at": self.published_at.isoformat() if self.published_at else None,
                "links": self.links, "language": self.language, "char_count": len(self.text)}


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = self.main = 0
        self.body, self.main_parts, self.title_parts, self.ld = [], [], [], []
        self.in_title = self.in_ld = self.in_h1 = self.h1_done = False
        self.h1, self.meta, self.links, self.canonical, self.lang = [], {}, [], None, None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang") or None
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"].strip())
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = self.canonical or a.get("href")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script" and "ld+json" in a.get("type", "").lower():
            self.in_ld = True
        elif tag == "h1" and not self.h1_done:
            self.in_h1 = True
        if tag in SKIP and not self.in_ld:
            self.skip += 1
        if tag in ("article", "main"):
            self.main += 1
        if tag in BLOCK:
            self._add("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script":
            self.in_ld = False
        elif tag == "h1" and self.in_h1:
            self.in_h1, self.h1_done = False, True
        if tag in SKIP and self.skip:
            self.skip -= 1
        if tag in ("article", "main") and self.main:
            self.main -= 1
        if tag in BLOCK:
            self._add("\n")

    def _add(self, s):
        if not self.skip:
            self.body.append(s)
            if self.main:
                self.main_parts.append(s)

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        elif self.in_ld:
            self.ld.append(data)
        elif not self.skip:
            data = re.sub(r"\s+", " ", data)  # HTML collapses whitespace; only block tags break lines
            self._add(data)
            if self.in_h1:
                self.h1.append(data)


def _norm(parts) -> str:
    lines = [re.sub(r"[ \t\r\f\v\xa0]+", " ", l).strip() for l in "".join(parts).split("\n")]
    out, blank = [], False
    for l in lines:
        if l:
            out.append(l)
            blank = False
        elif not blank and out:
            out.append("")
            blank = True
    return "\n".join(out).strip()[:MAX_TEXT_CHARS]


def _ld_date(blobs):
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("datePublished"), str):
                return o["datePublished"]
            o = list(o.values())
        if isinstance(o, list):
            for i in o:
                r = walk(i)
                if r:
                    return r
    for b in blobs:
        try:
            r = walk(json.loads(b))
        except ValueError:
            continue
        if r:
            return r


def _host(u):
    h = (urlsplit(u).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def extract_content(text: str, content_type: str, base_url: str) -> ExtractedContent:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in ("text/html", "application/xhtml+xml", "text/plain"):
        raise ToolError("unsupported_content", "Unsupported content type for extraction")
    if not isinstance(text, str) or "\x00" in text[:1024]:
        raise ToolError("unsupported_content", "Content looks like binary data")
    text = text[:MAX_INPUT_CHARS]
    if ctype == "text/plain":
        return ExtractedContent(None, _norm([text]), {}, None, None)
    p = _P()
    try:
        p.feed(text)
        p.close()
    except Exception:
        raise ToolError("unsupported_content", "HTML could not be parsed")
    main = _norm(p.main_parts)
    body = main if len(main) >= 200 else _norm(p.body)
    title = _norm(p.title_parts) or p.meta.get("og:title") or _norm(p.h1) or None
    meta = {k: p.meta[k][:500] for k in META_KEEP if k in p.meta}
    published = next((d for d in (parse_date(p.meta.get(k)) for k in DATE_KEYS) if d), None) \
        or parse_date(_ld_date(p.ld))
    canonical = None
    if p.canonical:
        cand = urljoin(base_url, p.canonical.strip())
        if urlsplit(cand).scheme in ("http", "https") and _host(cand) == _host(base_url):
            canonical = cand  # cross-host canonicals are ignored so a page cannot claim another site's identity
        else:
            meta["canonical_rejected"] = True
    links = []
    for href in p.links:
        u = urljoin(base_url, href.strip()).split("#")[0]
        if urlsplit(u).scheme in ("http", "https") and u not in links:
            links.append(u)
        if len(links) >= MAX_LINKS:
            break
    return ExtractedContent(title[:300] if title else None, body, meta, canonical, published, links, p.lang)
