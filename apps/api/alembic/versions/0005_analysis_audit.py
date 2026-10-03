"""analyses (analyst inferences, immutable) + immutable audit_logs"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    now = sa.func.now()
    op.create_table("analyses",
        sa.Column("id", sa.Uuid, primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("research_id", sa.Uuid, sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False), sa.Column("text", sa.Text, nullable=False), sa.Column("basis_claim_ids", sa.JSON, nullable=False),
        sa.Column("agent_id", sa.String(30)), sa.Column("task_key", sa.String(64)), sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("is_demo", sa.Boolean, nullable=False, server_default=sa.false()), sa.UniqueConstraint("research_id", "idempotency_key"))
    op.create_index("ix_audit_logs_ws_created", "audit_logs", ["workspace_id", "created_at"])
    if op.get_bind().dialect.name == "postgresql":  # atlas_forbid_update() is created in 0003
        for t in ("analyses", "audit_logs"):
            op.execute(f"CREATE TRIGGER {t}_immutable BEFORE UPDATE ON {t} FOR EACH ROW EXECUTE FUNCTION atlas_forbid_update()")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for t in ("analyses", "audit_logs"):
            op.execute(f"DROP TRIGGER IF EXISTS {t}_immutable ON {t}")
    op.drop_index("ix_audit_logs_ws_created", "audit_logs")
    op.drop_table("analyses")
