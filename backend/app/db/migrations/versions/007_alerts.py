"""Add alerts table for automated crawl monitoring.

Revision ID: 007_alerts
Revises: 006_config_profiles
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_alerts"
down_revision: Union[str, None] = "006_config_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("crawl_id", sa.UUID(), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("metric_before", sa.Float(), nullable=True),
        sa.Column("metric_after", sa.Float(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alerts_project_id", "alerts", ["project_id"])
    op.create_index("ix_alerts_crawl_id", "alerts", ["crawl_id"])
    op.create_index("ix_alerts_is_read", "alerts", ["is_read"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_created_at")
    op.drop_index("ix_alerts_is_read")
    op.drop_index("ix_alerts_crawl_id")
    op.drop_index("ix_alerts_project_id")
    op.drop_table("alerts")
