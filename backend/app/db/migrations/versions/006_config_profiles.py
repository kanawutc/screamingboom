"""Add config_profiles table for reusable crawl configurations.

Revision ID: 006_config_profiles
Revises: 005_crawl_schedules
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_config_profiles"
down_revision: Union[str, None] = "005_crawl_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "config_profiles",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), server_default="", nullable=False),
        sa.Column("config", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed default profiles
    op.execute("""
        INSERT INTO config_profiles (name, description, config, is_default) VALUES
        ('Default', 'Standard crawl settings', '{"max_urls": 10000, "max_depth": 10, "max_threads": 5, "rate_limit_rps": 2, "user_agent": "SEOSpider/1.0", "respect_robots": true}'::jsonb, true),
        ('Light Audit', 'Quick scan — 500 pages, shallow depth', '{"max_urls": 500, "max_depth": 3, "max_threads": 3, "rate_limit_rps": 2, "user_agent": "SEOSpider/1.0", "respect_robots": true}'::jsonb, false),
        ('Deep Crawl', 'Full site crawl — 100k pages, deep', '{"max_urls": 100000, "max_depth": 50, "max_threads": 10, "rate_limit_rps": 5, "user_agent": "SEOSpider/1.0", "respect_robots": true}'::jsonb, false),
        ('Googlebot', 'Crawl as Googlebot', '{"max_urls": 10000, "max_depth": 10, "max_threads": 5, "rate_limit_rps": 2, "user_agent": "googlebot", "respect_robots": true}'::jsonb, false),
        ('Aggressive', 'Fast crawl — high concurrency', '{"max_urls": 50000, "max_depth": 20, "max_threads": 20, "rate_limit_rps": 10, "user_agent": "SEOSpider/1.0", "respect_robots": false}'::jsonb, false)
    """)


def downgrade() -> None:
    op.drop_table("config_profiles")
