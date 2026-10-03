"""Phase 3-8: sources, evidence, claims, claim_sources, verification_results, conflicts; agent_runs counters + idempotency.
Composite FKs (id, research_id) make it impossible at DB level for evidence/claims to reference another research's rows.
Postgres triggers make evidence and verification rows immutable and claim text/type immutable."""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
FK = lambda cols, ref: sa.ForeignKeyConstraint(cols, ref, ondelete="CASCADE")


def base():
    now = sa.func.now()
    return [sa.Column("id", sa.Uuid, primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now)]


def owner():
    return [sa.Column("research_id", sa.Uuid, sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)]


def demo():
    return sa.Column("is_demo", sa.Boolean, nullable=False, server_default=sa.false())


def upgrade():
    op.create_table("sources", *base(), *owner(),
        sa.Column("url", sa.String(2048), nullable=False), sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False), sa.Column("title", sa.Text), sa.Column("publisher", sa.String(255), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_text", sa.Text), sa.Column("meta", sa.JSON, nullable=False), sa.Column("aliases", sa.JSON, nullable=False), demo(),
        sa.UniqueConstraint("research_id", "canonical_url"), sa.UniqueConstraint("research_id", "content_hash"),
        sa.UniqueConstraint("id", "research_id"))
    op.create_table("claims", *base(), *owner(),
        sa.Column("text", sa.Text, nullable=False), sa.Column("claim_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, index=True), sa.Column("confidence", sa.String(12), nullable=False),
        sa.Column("attributes", sa.JSON, nullable=False), sa.Column("created_by_agent", sa.String(30)),
        sa.Column("task_key", sa.String(64)), sa.Column("idempotency_key", sa.String(64), nullable=False), demo(),
        sa.UniqueConstraint("research_id", "idempotency_key"), sa.UniqueConstraint("id", "research_id"))
    op.create_table("evidence", *base(), *owner(),
        sa.Column("source_id", sa.Uuid, nullable=False, index=True), sa.Column("claim_id", sa.Uuid, index=True),
        sa.Column("task_key", sa.String(64)), sa.Column("agent_id", sa.String(30)), sa.Column("excerpt", sa.Text, nullable=False),
        sa.Column("location", sa.JSON, nullable=False), sa.Column("stance", sa.String(12), nullable=False),
        sa.Column("quality", sa.JSON, nullable=False), sa.Column("meta", sa.JSON, nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False), demo(),
        sa.UniqueConstraint("research_id", "idempotency_key"),
        FK(["source_id", "research_id"], ["sources.id", "sources.research_id"]),
        FK(["claim_id", "research_id"], ["claims.id", "claims.research_id"]))
    op.create_table("claim_sources", *base(), *owner(),
        sa.Column("claim_id", sa.Uuid, nullable=False, index=True), sa.Column("source_id", sa.Uuid, nullable=False, index=True),
        sa.Column("stance", sa.String(12), nullable=False), sa.Column("evidence_count", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("claim_id", "source_id", "stance"),
        FK(["source_id", "research_id"], ["sources.id", "sources.research_id"]),
        FK(["claim_id", "research_id"], ["claims.id", "claims.research_id"]))
    op.create_table("verification_results", *base(), *owner(),
        sa.Column("claim_id", sa.Uuid, nullable=False, index=True), sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("confidence", sa.String(12), nullable=False), sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("evidence_ids", sa.JSON, nullable=False), sa.Column("factors", sa.JSON, nullable=False),
        sa.Column("verifier", sa.String(40), nullable=False), demo(),
        FK(["claim_id", "research_id"], ["claims.id", "claims.research_id"]))
    op.create_table("conflicts", *base(), *owner(),
        sa.Column("claim_id", sa.Uuid, nullable=False, index=True), sa.Column("other_claim_id", sa.Uuid),
        sa.Column("source_a_id", sa.Uuid), sa.Column("source_b_id", sa.Uuid),
        sa.Column("evidence_a_id", sa.Uuid), sa.Column("evidence_b_id", sa.Uuid),
        sa.Column("conflict_type", sa.String(32), nullable=False), sa.Column("severity", sa.String(8), nullable=False),
        sa.Column("status", sa.String(12), nullable=False), sa.Column("resolution_status", sa.String(24), nullable=False),
        sa.Column("explanation", sa.Text, nullable=False), sa.Column("dimensions", sa.JSON, nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False), sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False), demo(),
        sa.UniqueConstraint("research_id", "idempotency_key"),
        FK(["claim_id", "research_id"], ["claims.id", "claims.research_id"]),
        FK(["other_claim_id", "research_id"], ["claims.id", "claims.research_id"]))
    for c in (sa.Column("tool_calls_count", sa.Integer, nullable=False, server_default="0"),
              sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
              sa.Column("evidence_count", sa.Integer, nullable=False, server_default="0"),
              sa.Column("claim_count", sa.Integer, nullable=False, server_default="0"), sa.Column("meta", sa.JSON)):
        op.add_column("agent_runs", c)
    op.create_unique_constraint("uq_agent_runs_task_attempt", "agent_runs", ["task_id", "attempt"])
    if op.get_bind().dialect.name == "postgresql":  # immutability guards (UPDATE only; cascading deletes stay possible)
        op.execute("""CREATE FUNCTION atlas_forbid_update() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql""")
        for t in ("evidence", "verification_results"):
            op.execute(f"CREATE TRIGGER {t}_immutable BEFORE UPDATE ON {t} FOR EACH ROW EXECUTE FUNCTION atlas_forbid_update()")
        op.execute("""CREATE FUNCTION atlas_claim_core_immutable() RETURNS trigger AS $$
            BEGIN IF NEW.text IS DISTINCT FROM OLD.text OR NEW.claim_type IS DISTINCT FROM OLD.claim_type
                     OR NEW.research_id IS DISTINCT FROM OLD.research_id OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
                  THEN RAISE EXCEPTION 'claim text/type/research are immutable'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql""")
        op.execute("CREATE TRIGGER claims_core_immutable BEFORE UPDATE ON claims FOR EACH ROW EXECUTE FUNCTION atlas_claim_core_immutable()")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for t, f in (("evidence", "atlas_forbid_update"), ("verification_results", "atlas_forbid_update"), ("claims", "atlas_claim_core_immutable")):
            trig = f"{t}_immutable" if t != "claims" else "claims_core_immutable"
            op.execute(f"DROP TRIGGER IF EXISTS {trig} ON {t}")
        op.execute("DROP FUNCTION IF EXISTS atlas_forbid_update()")
        op.execute("DROP FUNCTION IF EXISTS atlas_claim_core_immutable()")
    op.drop_constraint("uq_agent_runs_task_attempt", "agent_runs")
    for c in ("meta", "claim_count", "evidence_count", "source_count", "tool_calls_count"):
        op.drop_column("agent_runs", c)
    for t in ("conflicts", "verification_results", "claim_sources", "evidence", "claims", "sources"):
        op.drop_table(t)
