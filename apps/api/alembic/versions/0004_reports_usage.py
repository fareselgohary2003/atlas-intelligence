"""reports (immutable versions), report_sections, cost_records"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def base():
    now = sa.func.now()
    return [sa.Column("id", sa.Uuid, primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now)]


def owner():
    return [sa.Column("research_id", sa.Uuid, sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)]


def upgrade():
    op.create_table("reports", *base(), *owner(), sa.Column("version", sa.Integer, nullable=False), sa.Column("title", sa.Text, nullable=False),
                    sa.Column("is_demo", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("content", sa.JSON, nullable=False),
                    sa.UniqueConstraint("research_id", "version"))
    op.create_table("report_sections", *base(), *owner(),
                    sa.Column("report_id", sa.Uuid, sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True),
                    sa.Column("position", sa.Integer, nullable=False), sa.Column("key", sa.String(40), nullable=False),
                    sa.Column("title", sa.String(120), nullable=False), sa.Column("content", sa.JSON, nullable=False),
                    sa.UniqueConstraint("report_id", "position"))
    op.create_table("cost_records", *base(), *owner(),
                    sa.Column("task_key", sa.String(64)), sa.Column("agent", sa.String(30), nullable=False, index=True),
                    sa.Column("provider", sa.String(40), nullable=False), sa.Column("model", sa.String(80), nullable=False),
                    sa.Column("input_tokens", sa.Integer), sa.Column("output_tokens", sa.Integer), sa.Column("estimated_cost", sa.Float),
                    sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("ok", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("error_category", sa.String(20)))
    if op.get_bind().dialect.name == "postgresql":  # generated reports are immutable; a new generation is a new version
        for t in ("reports", "report_sections"):
            op.execute(f"CREATE TRIGGER {t}_immutable BEFORE UPDATE ON {t} FOR EACH ROW EXECUTE FUNCTION atlas_forbid_update()")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for t in ("reports", "report_sections"):
            op.execute(f"DROP TRIGGER IF EXISTS {t}_immutable ON {t}")
    for t in ("cost_records", "report_sections", "reports"):
        op.drop_table(t)
