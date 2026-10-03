"""Phase 1 schema: users, workspaces, members, research_projects, audit_logs"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def base():
    now = sa.func.now()
    return [
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    ]


def upgrade():
    op.create_table("users", *base(),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False))
    op.create_table("workspaces", *base(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False, unique=True))
    op.create_table("workspace_members", *base(),
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id"))
    op.create_table("research_projects", *base(),
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("owner_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("objective", sa.Text, nullable=False),
        sa.Column("industry", sa.String(120)), sa.Column("geography", sa.String(120)),
        sa.Column("target_customer", sa.String(200)), sa.Column("time_range", sa.String(60)),
        sa.Column("competitors", sa.JSON, nullable=False),
        sa.Column("depth", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sources_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("claims_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confidence", sa.String(12)),
        sa.Column("is_demo", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_table("audit_logs", *base(),
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40)), sa.Column("entity_id", sa.String(64)),
        sa.Column("meta", sa.JSON, nullable=False))


def downgrade():
    for t in ("audit_logs", "research_projects", "workspace_members", "workspaces", "users"):
        op.drop_table(t)
