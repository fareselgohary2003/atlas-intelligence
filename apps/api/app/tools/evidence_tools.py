"""Evidence-oriented tools. They call EvidenceService only (never repositories) and take scope from the trusted ToolContext,
never from arguments, so an agent cannot address another research or workspace."""
import threading
from urllib.parse import urlsplit

from app.evidence.domain import ANALYSIS_KINDS, CLAIM_STATUSES, CLAIM_TYPES, STANCES, EvidenceError, Scope, digest, norm_text
from app.tools.base import Field, Schema, ToolContext, ToolDefinition, ToolError
from app.tools.extract import parse_date
from app.tools.sources import SOURCE_TYPES, make_candidate

EVIDENCE_TOOLS = ("save_source", "create_evidence", "create_claim", "verify_claim", "save_analysis", "list_claims", "list_conflicts", "create_research_task",
                  "request_research", "update_task")
REASON_CODES = ("VERIFICATION_FAILED", "INSUFFICIENT_EVIDENCE", "CONFLICT_DETECTED", "MISSING_DIMENSION", "LOW_SOURCE_QUALITY", "CLAIM_UNSUPPORTED")


class FollowUpBuffer:
    """Follow-up PROPOSALS from agents, keyed by (research, task). Only the Research Manager turns them into tasks."""
    def __init__(self):
        self._d, self._lock = {}, threading.Lock()

    def add(self, research_id, task_id, item) -> bool:
        with self._lock:
            items = self._d.setdefault((research_id, task_id), {})
            created = item["key"] not in items
            items[item["key"]] = item
            return created

    def take(self, research_id, task_id) -> list:
        with self._lock:
            return list(self._d.pop((research_id, task_id), {}).values())


def _scope(ctx: ToolContext) -> Scope:
    if not ctx.research_id or not ctx.workspace_id:
        raise ToolError("validation", "This tool requires a research context")
    return Scope(str(ctx.workspace_id), str(ctx.research_id), ctx.task_id, ctx.agent)


def _guard(fn):
    def run(a, ctx):
        try:
            return fn(a, ctx)
        except EvidenceError as e:
            raise ToolError("validation", e.message) from e
    return run


def register_evidence_tools(reg, service, follow_ups: FollowUpBuffer):
    def save_source(a, ctx):
        if urlsplit(a["url"]).scheme not in ("http", "https"):
            raise ToolError("validation", "Source URL must be http(s)")
        if len(a["text"].strip()) < 50:
            raise ToolError("empty_content", "Page has too little text to use as a source")
        cand = make_candidate(url=a["url"], text=a["text"], title=a.get("title"), publisher=a.get("publisher"),
                              published_at=parse_date(a.get("published_at")), canonical_url=a.get("canonical_url"),
                              source_type=a.get("source_type"), metadata=a["metadata"])
        rec, created, via = service.save_source(_scope(ctx), cand, a["text"])
        return {"source_id": rec.id, "created": created, "duplicate_via": via, "is_demo": rec.is_demo,
                "domain": rec.domain, "source_type": rec.source_type}

    reg.register(ToolDefinition(
        "save_source", "Persist a retrieved page as a Source (deduplicated by canonical URL, URL and content hash).",
        Schema(url=Field(str, max_length=2048), text=Field(str, max_length=3_000_000), title=Field(str, False, max_length=300),
               publisher=Field(str, False, max_length=200), published_at=Field(str, False), canonical_url=Field(str, False),
               source_type=Field(str, False, choices=SOURCE_TYPES), metadata=Field(dict, False, {})),
        Schema(source_id=Field(str), created=Field(bool), duplicate_via=Field(str, False), is_demo=Field(bool),
               domain=Field(str), source_type=Field(str)),
        _guard(save_source), timeout=15, summarize=lambda o: {"created": o["created"], "duplicate_via": o.get("duplicate_via"),
                                                              "is_demo": o["is_demo"], "domain": o["domain"]},
        metadata={"writes": "source"}))

    def create_claim(a, ctx):
        c, created = service.create_claim(_scope(ctx), a["text"], a["claim_type"], a["attributes"])
        return {"claim_id": c.id, "created": created, "status": c.status}

    reg.register(ToolDefinition(
        "create_claim", "Record a candidate claim (status 'proposed'; never verified by its creator).",
        Schema(text=Field(str, max_length=600), claim_type=Field(str, choices=CLAIM_TYPES), attributes=Field(dict, False, {})),
        Schema(claim_id=Field(str), created=Field(bool), status=Field(str)), _guard(create_claim), timeout=10,
        summarize=lambda o: {"created": o["created"], "status": o["status"]}, metadata={"writes": "claim"}))

    def create_evidence(a, ctx):
        e, created = service.create_evidence(_scope(ctx), a["source_id"], a["excerpt"], a.get("claim_id"), a["stance"])
        return {"evidence_id": e.id, "created": created, "grounded": e.location.get("basis") != "unverified",
                "quality_level": e.quality["level"], "quality_total": float(e.quality["total"])}

    reg.register(ToolDefinition(
        "create_evidence", "Attach a verbatim excerpt of a saved source to a claim. Rejected if the excerpt is not in the source text.",
        Schema(source_id=Field(str, max_length=64), excerpt=Field(str, max_length=1500), claim_id=Field(str, False, max_length=64),
               stance=Field(str, False, "supports", choices=STANCES)),
        Schema(evidence_id=Field(str), created=Field(bool), grounded=Field(bool), quality_level=Field(str), quality_total=Field(float)),
        _guard(create_evidence), timeout=10, summarize=lambda o: {"created": o["created"], "grounded": o["grounded"], "quality": o["quality_level"]},
        metadata={"writes": "evidence"}))

    def verify_claim(a, ctx):
        v = service.verify_claim(_scope(ctx), a["claim_id"])
        return {"verification_id": v.id, "outcome": v.outcome, "confidence": v.confidence, "rationale": v.rationale,
                "evidence_ids": list(v.evidence_ids)}

    reg.register(ToolDefinition(
        "verify_claim", "Verify a claim against its linked evidence (deterministic rules first). Fact-checker use only.",
        Schema(claim_id=Field(str, max_length=64)),
        Schema(verification_id=Field(str), outcome=Field(str), confidence=Field(str), rationale=Field(str), evidence_ids=Field(list)),
        _guard(verify_claim), timeout=30, summarize=lambda o: {"outcome": o["outcome"], "confidence": o["confidence"]},
        metadata={"writes": "verification"}))

    def save_analysis(a, ctx):
        rec, created = service.save_analysis(_scope(ctx), a["kind"], a["text"], a["basis_claim_ids"])
        return {"analysis_id": rec.id, "created": created, "kind": rec.kind}

    reg.register(ToolDefinition(
        "save_analysis", "Record an INFERENCE (opportunity, uncertainty or risk inference) that cites verified or partially verified claims. Analyst only.",
        Schema(kind=Field(str, choices=ANALYSIS_KINDS), text=Field(str, max_length=900), basis_claim_ids=Field(list, max_length=8, item_type=str)),
        Schema(analysis_id=Field(str), created=Field(bool), kind=Field(str)), _guard(save_analysis), timeout=10,
        summarize=lambda o: {"created": o["created"], "kind": o["kind"]}, metadata={"writes": "analysis"}))

    def list_claims(a, ctx):
        st = a.get("statuses")
        if st and any(x not in CLAIM_STATUSES for x in st):
            raise ToolError("validation", "Unknown claim status filter")
        rows = service.list_claims(_scope(ctx), st, a["limit"])
        return {"claims": [{"id": c.id, "text": c.text, "claim_type": c.claim_type, "status": c.status, "confidence": c.confidence} for c in rows],
                "count": len(rows)}

    reg.register(ToolDefinition(
        "list_claims", "List this research's claims (optionally by status). Read-only; no source text is returned.",
        Schema(statuses=Field(list, False, max_length=5, item_type=str), limit=Field(int, False, 100, minimum=1, maximum=200)),
        Schema(claims=Field(list, item_type=dict), count=Field(int)), _guard(list_claims), timeout=10,
        summarize=lambda o: {"count": o["count"]}, metadata={"writes": None}))

    def list_conflicts(a, ctx):
        rows = service.list_conflicts(_scope(ctx))
        return {"conflicts": [{"id": c.id, "claim_id": c.claim_id, "other_claim_id": c.other_claim_id, "conflict_type": c.conflict_type,
                               "severity": c.severity, "resolution_status": c.resolution_status, "explanation": c.explanation} for c in rows]}

    reg.register(ToolDefinition(
        "list_conflicts", "List detected conflicts for this research. Read-only.", Schema(),
        Schema(conflicts=Field(list, item_type=dict)), _guard(list_conflicts), timeout=10,
        summarize=lambda o: {"count": len(o["conflicts"])}, metadata={"writes": None}))

    def propose(kind):
        def run(a, ctx):
            if not ctx.research_id or not ctx.task_id:
                raise ToolError("validation", "This tool requires a task context")
            title = a["title"] if kind == "task" else a["question"]
            agent = a.get("agent") or ctx.agent
            key = digest(kind, norm_text(title), agent)  # deterministic: a retried task proposes the same follow-up once
            created = follow_ups.add(str(ctx.research_id), ctx.task_id,
                                     {"key": key, "kind": kind, "title": title, "agent": agent, "reason": a.get("reason", ""),
                                      "reason_code": a.get("reason_code")})
            return {"follow_up_id": key[:12], "created": created}
        return run

    reg.register(ToolDefinition(
        "create_research_task", "Propose a follow-up research task (the Research Manager decides whether to add it).",
        Schema(title=Field(str, min_length=5, max_length=200), agent=Field(str, min_length=1, max_length=30), reason=Field(str, False, max_length=300),
               reason_code=Field(str, False, choices=REASON_CODES)),
        Schema(follow_up_id=Field(str), created=Field(bool)), propose("task"), timeout=5, summarize=lambda o: {"created": o["created"]},
        metadata={"writes": "proposal"}))
    reg.register(ToolDefinition(
        "request_research", "Ask the Research Manager to investigate a gap (proposal only).",
        Schema(question=Field(str, min_length=10, max_length=300), agent=Field(str, False, max_length=30), reason=Field(str, False, max_length=300),
               reason_code=Field(str, False, choices=REASON_CODES)),
        Schema(follow_up_id=Field(str), created=Field(bool)), propose("request"), timeout=5, summarize=lambda o: {"created": o["created"]},
        metadata={"writes": "proposal"}))

    def update_task(a, ctx):
        if ctx.emit:
            ctx.emit("TASK_PROGRESS", agent=ctx.agent, task_id=ctx.task_id, progress=a["progress"], action="progress",
                     summary=a.get("note"))
        return {"ok": True}

    reg.register(ToolDefinition(
        "update_task", "Report progress on the agent's own task (status changes belong to the engine).",
        Schema(progress=Field(int, minimum=0, maximum=100), note=Field(str, False, max_length=200)),
        Schema(ok=Field(bool)), update_task, timeout=5, summarize=lambda o: {}, metadata={"writes": "event"}))
