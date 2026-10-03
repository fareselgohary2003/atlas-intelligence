"""WebSearchProvider abstraction. Agents never see a vendor. Missing configuration is an explicit ConfigError."""
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.agents.state import ConfigError
from app.tools.base import ToolError
from app.tools.extract import parse_date
from app.tools.sources import domain_of


@dataclass
class SearchOptions:
    count: int = 10
    country: str | None = None
    language: str | None = None
    freshness: str | None = None  # day | week | month | year


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    publisher: str
    published_at: datetime | None = None
    rank: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        d = self.__dict__.copy()
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        return d


class WebSearchProvider(Protocol):
    name: str
    def search(self, query: str, options: SearchOptions) -> list[SearchResult]: ...


def _http_get(url, headers, timeout):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(5_000_000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except (urllib.error.URLError, TimeoutError) as e:
        raise ToolError("network", "Search provider unreachable", True) from e


def _clean(v) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(v or ""))).strip()


class BraveSearchProvider:
    """Brave Search API. Response field names follow Brave's documented web-search schema and have NOT been
    verified against the live API in this environment (no network)."""
    name = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key, http_get=_http_get, timeout=10):
        if not api_key:
            raise ConfigError("WEB_SEARCH_API_KEY is not set")
        self._key, self._get, self._timeout = api_key, http_get, timeout

    def search(self, query, options: SearchOptions):
        params = {"q": query[:400], "count": options.count}
        for k, v in (("country", options.country), ("search_lang", options.language), ("freshness", options.freshness)):
            if v:
                params[k] = v
        status, body = self._get(self.endpoint + "?" + urllib.parse.urlencode(params),
                                 {"Accept": "application/json", "X-Subscription-Token": self._key}, self._timeout)
        if status in (401, 403):
            raise ConfigError("Search provider rejected the credentials")
        if status == 429 or status >= 500:
            raise ToolError("upstream_transient", f"Search provider returned HTTP {status}")
        if status != 200:
            raise ToolError("upstream", f"Search provider returned HTTP {status}")
        try:
            items = json.loads(body)["web"]["results"]
        except (ValueError, KeyError, TypeError):
            raise ToolError("upstream", "Search provider returned an unexpected response")
        out = []
        for i in items if isinstance(items, list) else []:
            url = i.get("url") if isinstance(i, dict) else None
            if not isinstance(url, str) or not re.match(r"https?://", url, re.I):
                continue  # untrusted result URLs: only http(s) survives
            snippet = _clean(i.get("description"))
            host = (i.get("meta_url") or {}).get("hostname") if isinstance(i.get("meta_url"), dict) else None
            out.append(SearchResult(_clean(i.get("title"))[:300], url, snippet[:600],
                                    domain_of(url) or str(host or ""), parse_date(i.get("page_age")), len(out) + 1))
        return out


PROVIDERS = {"brave": BraveSearchProvider}  # register future providers here


def create_search_provider(name, api_key) -> WebSearchProvider:
    if not name:
        raise ConfigError("WEB_SEARCH_PROVIDER is not set")
    if name not in PROVIDERS:
        raise ConfigError(f"Unknown WEB_SEARCH_PROVIDER '{name[:30]}'. Supported: {', '.join(PROVIDERS)}")
    return PROVIDERS[name](api_key)
