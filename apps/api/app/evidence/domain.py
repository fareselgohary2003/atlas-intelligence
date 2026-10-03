"""Evidence-layer domain. SOURCE (retrieved) -> EVIDENCE (excerpt) -> CLAIM (proposition) -> VERIFICATION (assessment).
Stdlib only. Persistence is behind EvidenceRepository."""
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

CLAIM_STATUSES = ("proposed", "supported", "partially_supported", "contradicted", "insufficient_evidence")
VERIFIED_STATES = CLAIM_STATUSES[1:]
STANCES = ("supports", "contradicts", "context")
ANALYSIS_KINDS = ("opportunity", "uncertainty", "risk_inference")
CLAIM_TYPES = ("market_size", "market_growth", "market_segment", "trend", "adoption", "competitor_profile", "pricing",
               "positioning", "customer_need", "regulation", "risk", "other")
STR_ATTRS = ("metric", "unit", "period", "geography", "definition", "methodology", "population", "company", "product",
             "target_customers", "price", "currency", "risk_category", "plan", "regulator", "customer_segment")


class EvidenceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class DuplicateError(Exception):
    """Raised by repositories on a unique-constraint violation (lets the service resolve races idempotently)."""


def now():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid.uuid4())


def norm_text(s) -> str:
    return " ".join(str(s).split()).casefold()


def digest(*parts) -> str:
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()


def can_transition(old: str, new: str) -> bool:
    """Generation and verification are separate: a claim is born 'proposed' and can only move to a verified state
    (re-verification with new evidence may move between verified states); it never returns to 'proposed'."""
    return old in CLAIM_STATUSES and new in VERIFIED_STATES


def clean_attributes(raw) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise EvidenceError("invalid", "attributes must be an object")
    out = {}
    for k in STR_ATTRS:
        v = raw.get(k)
        if v not in (None, ""):
            out[k] = " ".join(str(v).split())[:200]
    if raw.get("value") not in (None, ""):
        v = raw["value"]
        try:
            if isinstance(v, bool):
                raise ValueError
            out["value"] = float(str(v).replace(",", "")) if isinstance(v, str) else float(v)
        except (TypeError, ValueError):
            raise EvidenceError("invalid", "attribute 'value' must be a number")
    if raw.get("pricing_status") not in (None, ""):
        if raw["pricing_status"] not in ("available", "unavailable"):
            raise EvidenceError("invalid", "pricing_status must be 'available' or 'unavailable'")
        out["pricing_status"] = raw["pricing_status"]
    return out


@dataclass(frozen=True)
class Scope:
    """Trusted execution context built by the engine/worker, never from tool arguments."""
    workspace_id: str
    research_id: str
    task_id: str | None = None
    agent: str | None = None
    is_demo: bool = False


@dataclass
class SourceRecord:
    id: str
    research_id: str
    workspace_id: str
    url: str
    canonical_url: str
    domain: str
    title: str | None
    publisher: str
    published_at: datetime | None
    retrieved_at: datetime
    source_type: str
    content_hash: str
    content_text: str | None
    meta: dict
    aliases: list
    is_demo: bool
    created_at: datetime


@dataclass
class ClaimRecord:
    id: str
    research_id: str
    workspace_id: str
    text: str
    claim_type: str
    status: str
    confidence: str
    attributes: dict
    created_by_agent: str | None
    task_key: str | None
    idempotency_key: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class EvidenceRecord:  # immutable once written
    id: str
    research_id: str
    workspace_id: str
    source_id: str
    claim_id: str | None
    task_key: str | None
    agent_id: str | None
    excerpt: str
    location: dict
    stance: str
    quality: dict
    meta: dict
    idempotency_key: str
    is_demo: bool
    created_at: datetime


@dataclass
class VerificationRecord:  # append-only history
    id: str
    research_id: str
    workspace_id: str
    claim_id: str
    outcome: str
    confidence: str
    rationale: str
    evidence_ids: list
    factors: dict
    verifier: str
    is_demo: bool
    created_at: datetime


@dataclass
class ConflictRecord:
    id: str
    research_id: str
    workspace_id: str
    claim_id: str
    other_claim_id: str | None
    source_a_id: str | None
    source_b_id: str | None
    evidence_a_id: str | None
    evidence_b_id: str | None
    conflict_type: str
    severity: str
    status: str
    resolution_status: str
    explanation: str
    dimensions: dict
    idempotency_key: str
    is_demo: bool
    detected_at: datetime


@dataclass
class AnalysisRecord:
    """An INFERENCE by the Analyst: it must cite verified/partially verified claims and may not add figures of its own."""
    id: str
    research_id: str
    workspace_id: str
    kind: str
    text: str
    basis_claim_ids: list
    agent_id: str | None
    task_key: str | None
    idempotency_key: str
    is_demo: bool
    created_at: datetime


class EvidenceRepository(Protocol):
    """Every method is scoped by research_id; implementations must never return rows from another research."""
    def research_context(self, research_id: str) -> dict | None: ...           # {"workspace_id", "is_demo"}
    def find_source_by_urls(self, research_id: str, urls: list) -> SourceRecord | None: ...  # url OR canonical_url
    def find_source_by_hash(self, research_id: str, content_hash: str) -> SourceRecord | None: ...
    def add_source(self, s: SourceRecord) -> None: ...                          # DuplicateError on unique violation
    def append_alias(self, research_id: str, source_id: str, alias: dict) -> None: ...
    def get_source(self, research_id: str, source_id: str) -> SourceRecord | None: ...
    def list_sources(self, research_id: str, limit: int = 100, offset: int = 0) -> list: ...
    def get_claim_by_key(self, research_id: str, key: str) -> ClaimRecord | None: ...
    def add_claim(self, c: ClaimRecord) -> None: ...
    def get_claim(self, research_id: str, claim_id: str) -> ClaimRecord | None: ...
    def set_claim_status(self, research_id: str, claim_id: str, status: str, confidence: str, at: datetime) -> None: ...
    def list_claims(self, research_id: str, limit: int = 100, offset: int = 0) -> list: ...
    def get_evidence_by_key(self, research_id: str, key: str) -> EvidenceRecord | None: ...
    def add_evidence(self, e: EvidenceRecord) -> None: ...  # also maintains the claim<->source link in the same transaction
    def get_evidence(self, research_id: str, evidence_id: str) -> EvidenceRecord | None: ...
    def list_evidence(self, research_id: str, claim_id: str | None = None, limit: int = 100, offset: int = 0) -> list: ...
    def claim_sources(self, research_id: str, claim_id: str) -> list: ...      # [{"source_id","stance","evidence_count"}]
    def add_verification(self, v: VerificationRecord) -> None: ...
    def latest_verification(self, research_id: str, claim_id: str) -> VerificationRecord | None: ...
    def list_verifications(self, research_id: str, claim_id: str) -> list: ...
    def get_conflict_by_key(self, research_id: str, key: str) -> ConflictRecord | None: ...
    def add_conflict(self, c: ConflictRecord) -> None: ...
    def list_conflicts(self, research_id: str, claim_id: str | None = None) -> list: ...  # claim on either side
    def latest_verifications(self, research_id: str, claim_ids: list) -> dict: ...   # claim_id -> VerificationRecord (one query)
    def claim_sources_bulk(self, research_id: str, claim_ids: list) -> dict: ...   # claim_id -> [{source_id, stance, evidence_count}]
    def sources_by_ids(self, research_id: str, ids: list) -> dict: ...             # id -> SourceRecord
    def source_usage(self, research_id: str, ids: list) -> dict: ...               # id -> {evidence, claims}
    def add_analysis(self, a: AnalysisRecord) -> None: ...
    def get_analysis_by_key(self, research_id: str, key: str) -> AnalysisRecord | None: ...
    def list_analysis(self, research_id: str) -> list: ...
