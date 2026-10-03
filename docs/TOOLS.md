# Tools, providers and the SSRF model (Slice 2)

## Dependency direction
`Agents -> ToolRegistry -> tool implementations -> providers (search / HTTP / LLM)`.
Agents import only `app.tools.base` and `app.tools.registry` (enforced by `tests/test_architecture.py`).
Swapping a search vendor, fetch implementation or storage layer does not touch agent code.

## ToolRegistry (`app/tools/registry.py`)
- `register(ToolDefinition)` (duplicates rejected), `get`, `grant(agent, tools)`, `describe(agent)`, `execute(name, args, ctx)`.
- **Default deny:** an agent can call only tools granted to it. Unauthorized calls are logged and returned as `unauthorized`.
- `ToolDefinition`: name, description, input `Schema`, output `Schema`, `execute`, `timeout`, `summarize` (safe event metadata), `metadata`, `config`.
- `execute` never raises. It returns `ToolResult(ok, data | error_category, error, retryable, duration_ms)`.
  `ToolResult.unwrap()` converts to engine semantics: retryable -> `TransientError` (engine retries), `config` -> `ConfigError`, else `ToolFailure`.
- Error categories: validation, unauthorized, unknown_tool, timeout, config, network, upstream, upstream_transient, security,
  unsupported_content, too_large, empty_content, internal. Unexpected exceptions become `internal` with a generic message; details go to server logs only.
- Timeout: the call runs in a worker pool; on timeout the registry sets `ctx.cancel` (fetches stop between chunks/hops). Python cannot kill a thread, so a non-cooperative tool keeps running until it returns.
- Events: `TOOL_STARTED`, `TOOL_COMPLETED`, `TOOL_FAILED` with tool, agent, task_id, duration_ms, ok, error_category, and scalar-only `result_meta`. Arguments (queries, URLs, prompts) are never included. `public_event` whitelists fields again before storage/SSE.

## Built-in tools (`app/tools/builtin.py`)
`web_search`, `fetch_url`, `extract_page_content`, `normalize_source`. Providers are injected; `app/tools/wiring.py` builds the production registry from env.
Evidence tools (`app/tools/evidence_tools.py`, all scope-bound by `ToolContext`, never by arguments): `save_source`, `create_evidence`, `create_claim`, `verify_claim`, `save_analysis`, `list_claims`, `list_conflicts`, `create_research_task`, `request_research`, `update_task`. Grants per agent: `docs/AGENTS.md`.

## Search providers (`app/tools/search.py`)
`WebSearchProvider.search(query, SearchOptions) -> list[SearchResult]`. Registry of providers in `PROVIDERS` (currently `brave`).
Missing `WEB_SEARCH_PROVIDER` / `WEB_SEARCH_API_KEY`, an unknown provider, or rejected credentials raise `ConfigError` -> tool failure `config`. There is no fallback provider and no fake results in production code.

## SSRF model (`app/tools/ssrf.py`, `app/tools/fetch.py`)
Per hop (initial URL and every redirect):
1. Reject control chars/backslashes, overlong URLs, non-http(s) schemes, embedded credentials, ports outside 80/443/8080/8443, `localhost`, `.local`, `.internal` etc.
2. Parse literals including inet_aton forms (`2130706433`, `0x7f.0.0.1`, `0177.0.0.1`, `127.1`) and IPv6.
3. Otherwise resolve DNS **once** and check **every** returned address: must be globally routable and non-multicast; IPv4-mapped, 6to4, NAT64, Teredo and IPv4-compatible IPv6 are unwrapped/blocked.
4. **Pinning:** the transport connects to the validated IP while sending the original Host header and TLS SNI/cert name, so a second DNS answer (rebinding) is never used.
5. Redirects are followed manually (max 5), each re-validated; only then is the socket opened.
Also: response cap (2 MB compressed and decompressed, zlib output limit against bombs), connect and total deadlines, content-type allow-list, no cookies/auth headers ever sent.

## Configuration
`WEB_SEARCH_PROVIDER`, `WEB_SEARCH_API_KEY` (see `.env.example`). Fetch limits live in `FetchConfig`.

## Known MVP limitations
- Source-type detection is a domain heuristic (gov/edu/forum); everything else is `other` unless the caller overrides.
- Content hash is exact-after-normalization; near-duplicate detection is not implemented.
- `SourceDeduper` is per-process memory; persistent uniqueness arrives with the `sources` table.
- No robots.txt handling, no JavaScript rendering (JS-only pages extract as empty), no PDF support.
- DNS is resolved with the system resolver (blocking); a hostile resolver that lies consistently is out of scope.
- The Brave adapter's response mapping is written from its documented schema and untested against the live API.
- Tool timeouts are cooperative for non-fetch tools.
