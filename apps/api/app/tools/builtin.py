"""Built-in tool definitions. They close over injected providers; agents only ever see the registry."""

from app.tools.base import Field, Schema, ToolDefinition, ToolError
from app.tools.extract import extract_content, parse_date
from app.tools.registry import ToolRegistry
from app.tools.search import SearchOptions
from app.tools.sources import SOURCE_TYPES, make_candidate

RESEARCH_TOOLS = ("web_search", "fetch_url", "extract_page_content", "normalize_source")


def build_default_registry(search_provider, fetcher, agents=(), max_workers=8) -> ToolRegistry:
    """search_provider: zero-arg callable returning a WebSearchProvider (raises ConfigError when unconfigured)."""
    reg = ToolRegistry(max_workers)

    def web_search(a, ctx):
        provider = search_provider()
        res = provider.search(a["query"], SearchOptions(a["count"], a.get("country"), a.get("language"), a.get("freshness")))
        return {"provider": provider.name, "results": [r.to_dict() for r in res]}

    reg.register(ToolDefinition(
        "web_search", "Search the web and return result titles, URLs and snippets (not page content).",
        Schema(query=Field(str, min_length=2, max_length=400), count=Field(int, False, 10, minimum=1, maximum=20),
               country=Field(str, False, max_length=2), language=Field(str, False, max_length=8),
               freshness=Field(str, False, choices=("day", "week", "month", "year"))),
        Schema(provider=Field(str), results=Field(list, item_type=dict)), web_search, timeout=20,
        summarize=lambda o: {"provider": o["provider"], "results": len(o["results"])},  # query text is never logged
        metadata={"network": True, "side_effects": False}))

    def fetch_url(a, ctx):
        r = fetcher.fetch(a["url"], cancel=ctx.cancel)
        return {"url": r.url, "status": r.status, "content_type": r.content_type, "text": r.text, "size": r.size,
                "redirects": r.redirects, "fetched_at": r.fetched_at.isoformat()}

    reg.register(ToolDefinition(
        "fetch_url", "Fetch a public http(s) page (SSRF-protected, size/time limited).",
        Schema(url=Field(str, min_length=8, max_length=2048)),
        Schema(url=Field(str), status=Field(int), content_type=Field(str), text=Field(str), size=Field(int),
               redirects=Field(list), fetched_at=Field(str)),
        fetch_url, timeout=30,
        summarize=lambda o: {"status": o["status"], "bytes": o["size"], "content_type": o["content_type"],
                             "redirects": len(o["redirects"]), "host": o["url"].split("/")[2][:80]},
        metadata={"network": True, "side_effects": False}))

    def extract(a, ctx):
        c = extract_content(a["html"], a["content_type"], a["base_url"]).to_dict()
        return c

    reg.register(ToolDefinition(
        "extract_page_content", "Extract title, main text, metadata, canonical URL and date from fetched HTML/text.",
        Schema(html=Field(str, max_length=3_000_000), content_type=Field(str, False, "text/html"),
               base_url=Field(str, max_length=2048)),
        Schema(title=Field(str, False), text=Field(str), metadata=Field(dict), canonical_url=Field(str, False),
               published_at=Field(str, False), links=Field(list), language=Field(str, False), char_count=Field(int)),
        extract, timeout=15,
        summarize=lambda o: {"chars": o["char_count"], "has_title": bool(o.get("title")), "has_date": bool(o.get("published_at"))},
        metadata={"network": False, "side_effects": False}))

    def normalize(a, ctx):
        if len(a["text"].strip()) < 50:
            raise ToolError("empty_content", "Page has too little text to use as a source")
        published = parse_date(a.get("published_at"))
        return make_candidate(url=a["url"], text=a["text"], title=a.get("title"), publisher=a.get("publisher"),
                              published_at=published, canonical_url=a.get("canonical_url"),
                              source_type=a.get("source_type"), is_demo=a["is_demo"], metadata=a["metadata"]).to_dict()

    reg.register(ToolDefinition(
        "normalize_source", "Build a normalized source candidate (canonical URL, hash, domain, type) from a fetched page.",
        Schema(url=Field(str, max_length=2048), text=Field(str, max_length=3_000_000), title=Field(str, False, max_length=300),
               publisher=Field(str, False, max_length=200), published_at=Field(str, False), canonical_url=Field(str, False),
               source_type=Field(str, False, choices=SOURCE_TYPES), is_demo=Field(bool, False, False),
               metadata=Field(dict, False, {})),
        Schema(url=Field(str), canonical_url=Field(str), domain=Field(str), title=Field(str, False), publisher=Field(str),
               published_at=Field(str, False), retrieved_at=Field(str), source_type=Field(str), content_hash=Field(str),
               is_demo=Field(bool), metadata=Field(dict)),
        normalize, timeout=5, summarize=lambda o: {"domain": o["domain"], "source_type": o["source_type"]},
        metadata={"network": False, "side_effects": False}))

    for agent in agents:
        reg.grant(agent, RESEARCH_TOOLS)
    return reg
