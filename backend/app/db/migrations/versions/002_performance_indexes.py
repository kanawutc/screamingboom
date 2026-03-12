"""Add performance indexes: trigram search, category filter, canonical verification.

Revision ID: 002_perf_indexes
Revises: 001_initial
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "002_perf_indexes"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_crawled_urls_url_trigram "
        "ON crawled_urls USING GIN (url gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_url_issues_crawl_category "
        "ON url_issues (crawl_id, category)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_crawled_urls_canonical "
        "ON crawled_urls (crawl_id, canonical_url) WHERE canonical_url IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_crawled_urls_url_trigram")
    op.execute("DROP INDEX IF EXISTS idx_url_issues_crawl_category")
    op.execute("DROP INDEX IF EXISTS idx_crawled_urls_canonical")
