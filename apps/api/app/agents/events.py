"""Public event contract. Only whitelisted fields ever leave the engine (DB payloads, API, SSE), so an agent
cannot leak reasoning text by adding extra keys to an event."""
import datetime as dt

PUBLIC_KEYS = {"kind", "seq", "ts", "task_id", "agent", "attempt", "status", "title", "depends_on", "summary",
               "error", "duration_ms", "confidence", "tool", "action", "source", "task_count", "new_tasks", "replans", "ok", "error_category", "result_meta", "counts", "progress", "claim_id", "outcome", "conflict_type", "reason_code", "reasons", "execution_id"}
SOURCE_KEYS = ("title", "publisher", "type", "url")


def public_event(ev: dict) -> dict:
    out = {k: v for k, v in ev.items() if k in PUBLIC_KEYS}
    if isinstance(ev.get("ts"), (int, float)):
        out["ts"] = dt.datetime.fromtimestamp(ev["ts"], dt.timezone.utc).isoformat()
    for key, limit in (("summary", 500), ("error", 300)):
        if isinstance(out.get(key), str):
            out[key] = out[key][:limit]
    for mk in ("result_meta", "counts"):
        if mk in out:
            m = out[mk] if isinstance(out[mk], dict) else {}
            out[mk] = {str(k)[:40]: (v[:120] if isinstance(v, str) else v) for k, v in list(m.items())[:10]
                       if v is None or isinstance(v, (str, int, float, bool))}
    if "reasons" in out:
        out["reasons"] = [str(x)[:40] for x in list(out["reasons"])[:10]] if isinstance(out["reasons"], (list, tuple)) else []
    if "source" in out:
        src = out["source"] if isinstance(out["source"], dict) else {}
        out["source"] = {k: src.get(k) for k in SOURCE_KEYS if k in src}
    return out
