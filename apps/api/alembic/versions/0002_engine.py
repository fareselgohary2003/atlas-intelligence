"""Phase 2: research_tasks, agent_runs, agent_events + run-control columns"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def base():
    now = sa.func.now()
    return [sa.Column("id", sa.Uuid, primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now)]


def owner(table_ref="research_projects"):
    return [sa.Column("research_id", sa.Uuid, sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)]


def upgrade():
    for c in (sa.Column("control_state", sa.String(10)), sa.Column("started_at", sa.DateTime(timezone=True)),
              sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
              sa.Column("run_error", sa.Text)):
        op.add_column("research_projects", c)
    op.create_table("research_tasks", *base(), *owner(),
        sa.Column("key", sa.String(64), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("agent", sa.String(30), nullable=False), sa.Column("depends_on", sa.JSON, nullable=False),
        sa.Column("status", sa.String(12), nullable=False, index=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text), sa.Column("result", sa.JSON),
        sa.UniqueConstraint("research_id", "key"))
    op.create_table("agent_runs", *base(), *owner(),
        sa.Column("task_id", sa.Uuid, sa.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent", sa.String(30), nullable=False), sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("duration_ms", sa.Integer),
        sa.Column("summary", sa.Text), sa.Column("error", sa.Text))
    op.create_table("agent_events", *base(), *owner(),
        sa.Column("seq", sa.Integer, nullable=False), sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("task_key", sa.String(64)), sa.Column("agent", sa.String(30)),
        sa.Column("payload", sa.JSON, nullable=False), sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("research_id", "seq"))
    op.create_index("ix_agent_events_research_seq", "agent_events", ["research_id", "seq"])


def downgrade():
    for t in ("agent_events", "agent_runs", "research_tasks"):
        op.drop_table(t)
    for c in ("run_error", "heartbeat_at", "finished_at", "started_at", "control_state"):
        op.drop_column("research_projects", c)
