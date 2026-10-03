import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def now():
    return datetime.now(timezone.utc)


class Common:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(Common, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))


class Workspace(Common, Base):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True)


class WorkspaceMember(Common, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))  # owner | admin | researcher | viewer
    user: Mapped[User] = relationship()


class ResearchProject(Common, Base):
    __tablename__ = "research_projects"
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(120))
    geography: Mapped[str | None] = mapped_column(String(120))
    target_customer: Mapped[str | None] = mapped_column(String(200))
    time_range: Mapped[str | None] = mapped_column(String(60))
    competitors: Mapped[list] = mapped_column(JSON, default=list)
    depth: Mapped[str] = mapped_column(String(20), default="deep")
    status: Mapped[str] = mapped_column(String(20), default="planning", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    sources_count: Mapped[int] = mapped_column(Integer, default=0)  # populated by Phase 4
    claims_count: Mapped[int] = mapped_column(Integer, default=0)   # populated by Phase 4
    confidence: Mapped[str | None] = mapped_column(String(12))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    control_state: Mapped[str | None] = mapped_column(String(10))  # pause | cancel request for the worker
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_error: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[User] = relationship()


class AuditLog(Common, Base):
    __tablename__ = "audit_logs"
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    user: Mapped[User | None] = relationship()


class ResearchTask(Common, Base):
    __tablename__ = "research_tasks"
    __table_args__ = (UniqueConstraint("research_id", "key"),)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))  # engine-level task id, e.g. "t1"
    title: Mapped[str] = mapped_column(String(200))
    agent: Mapped[str] = mapped_column(String(30))
    depends_on: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)


class AgentRun(Common, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (UniqueConstraint("task_id", "attempt"),)  # a redelivered worker cannot create a second run for an attempt
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_tasks.id", ondelete="CASCADE"), index=True)
    agent: Mapped[str] = mapped_column(String(30))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    tool_calls_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict | None] = mapped_column(JSON)


class AgentEvent(Common, Base):
    __tablename__ = "agent_events"
    __table_args__ = (UniqueConstraint("research_id", "seq"),)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))
    task_key: Mapped[str | None] = mapped_column(String(64))
    agent: Mapped[str | None] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # public fields only (see agents/events.py)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Source(Common, Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("research_id", "canonical_url"), UniqueConstraint("research_id", "content_hash"),
                      UniqueConstraint("id", "research_id"))  # (id, research_id) target for composite FKs
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    canonical_url: Mapped[str] = mapped_column(String(2048))
    domain: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(20))
    content_hash: Mapped[str] = mapped_column(String(64))
    content_text: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    aliases: Mapped[list] = mapped_column(JSON, default=list)  # append-only log of duplicate URLs seen
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Claim(Common, Base):
    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("research_id", "idempotency_key"), UniqueConstraint("id", "research_id"))
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(24), default="proposed", index=True)
    confidence: Mapped[str] = mapped_column(String(12), default="UNVERIFIED")
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_agent: Mapped[str | None] = mapped_column(String(30))
    task_key: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Evidence(Common, Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("research_id", "idempotency_key"),
                      ForeignKeyConstraint(["source_id", "research_id"], ["sources.id", "sources.research_id"], ondelete="CASCADE"),
                      ForeignKeyConstraint(["claim_id", "research_id"], ["claims.id", "claims.research_id"], ondelete="CASCADE"))
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(index=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    task_key: Mapped[str | None] = mapped_column(String(64))
    agent_id: Mapped[str | None] = mapped_column(String(30))
    excerpt: Mapped[str] = mapped_column(Text)
    location: Mapped[dict] = mapped_column(JSON, default=dict)
    stance: Mapped[str] = mapped_column(String(12))
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ClaimSource(Common, Base):
    __tablename__ = "claim_sources"
    __table_args__ = (UniqueConstraint("claim_id", "source_id", "stance"),
                      ForeignKeyConstraint(["source_id", "research_id"], ["sources.id", "sources.research_id"], ondelete="CASCADE"),
                      ForeignKeyConstraint(["claim_id", "research_id"], ["claims.id", "claims.research_id"], ondelete="CASCADE"))
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(index=True)
    stance: Mapped[str] = mapped_column(String(12))
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)


class VerificationResult(Common, Base):
    __tablename__ = "verification_results"
    __table_args__ = (ForeignKeyConstraint(["claim_id", "research_id"], ["claims.id", "claims.research_id"], ondelete="CASCADE"),)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(index=True)
    outcome: Mapped[str] = mapped_column(String(24))
    confidence: Mapped[str] = mapped_column(String(12))
    rationale: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    factors: Mapped[dict] = mapped_column(JSON, default=dict)
    verifier: Mapped[str] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Conflict(Common, Base):
    __tablename__ = "conflicts"
    __table_args__ = (UniqueConstraint("research_id", "idempotency_key"),
                      ForeignKeyConstraint(["claim_id", "research_id"], ["claims.id", "claims.research_id"], ondelete="CASCADE"),
                      ForeignKeyConstraint(["other_claim_id", "research_id"], ["claims.id", "claims.research_id"], ondelete="CASCADE"))
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(index=True)
    other_claim_id: Mapped[uuid.UUID | None] = mapped_column()
    source_a_id: Mapped[uuid.UUID | None] = mapped_column()
    source_b_id: Mapped[uuid.UUID | None] = mapped_column()
    evidence_a_id: Mapped[uuid.UUID | None] = mapped_column()
    evidence_b_id: Mapped[uuid.UUID | None] = mapped_column()
    conflict_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(12), default="detected")
    resolution_status: Mapped[str] = mapped_column(String(24))
    explanation: Mapped[str] = mapped_column(Text)
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Analysis(Common, Base):
    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("research_id", "idempotency_key"),)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    basis_claim_ids: Mapped[list] = mapped_column(JSON)
    agent_id: Mapped[str | None] = mapped_column(String(30))
    task_key: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Report(Common, Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("research_id", "version"),)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[dict] = mapped_column(JSON)  # header: title, provenance, citations, stats (sections live in report_sections)


class ReportSection(Common, Base):
    __tablename__ = "report_sections"
    __table_args__ = (UniqueConstraint("report_id", "position"),)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[dict] = mapped_column(JSON)


class CostRecord(Common, Base):
    __tablename__ = "cost_records"
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    task_key: Mapped[str | None] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(30), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int | None] = mapped_column(Integer)      # None = provider did not report
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float | None] = mapped_column(Float)    # None = no configured price or no token counts
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error_category: Mapped[str | None] = mapped_column(String(20))
