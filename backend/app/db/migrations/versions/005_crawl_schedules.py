"""Add crawl_schedules table for recurring crawls.

Revision ID: 005_crawl_schedules
Revises: 004_custom_rules
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_crawl_schedules"
down_revision: Union[str, None] = "004_custom_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crawl_schedules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("crawl_config", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_crawl_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_crawl_schedules_project_id", "crawl_schedules", ["project_id"])
    op.create_index("ix_crawl_schedules_next_run_at", "crawl_schedules", ["next_run_at"])
    op.create_index("ix_crawl_schedules_is_active", "crawl_schedules", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_crawl_schedules_is_active")
    op.drop_index("ix_crawl_schedules_next_run_at")
    op.drop_index("ix_crawl_schedules_project_id")
    op.drop_table("crawl_schedules")
