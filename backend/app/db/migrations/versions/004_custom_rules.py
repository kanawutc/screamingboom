"""Add custom extractors, searches, and result tables for Sprint 4.

Revision ID: 004_custom_rules
Revises: 003_extraction_rules
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_custom_rules"
down_revision: Union[str, None] = "003_extraction_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Custom Extractors
    op.create_table(
        "custom_extractors",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("crawl_id", sa.UUID(), sa.ForeignKey("crawls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("selector", sa.Text(), nullable=False),
        sa.Column("extract_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("attribute_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Custom Extractions (results)
    op.create_table(
        "custom_extractions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("crawl_id", sa.UUID(), sa.ForeignKey("crawls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url_id", sa.UUID(), nullable=False),
        sa.Column("extractor_id", sa.UUID(), sa.ForeignKey("custom_extractors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extracted_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_custom_extractions_url", "custom_extractions", ["url_id"])
    op.create_index("idx_custom_extractions_crawl", "custom_extractions", ["crawl_id"])
    op.create_foreign_key(
        "fk_custom_extractions_url",
        "custom_extractions",
        "crawled_urls",
        ["url_id", "crawl_id"],
        ["id", "crawl_id"],
        ondelete="CASCADE",
    )

    # Custom Searches
    op.create_table(
        "custom_searches",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("crawl_id", sa.UUID(), sa.ForeignKey("crawls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("is_regex", sa.Boolean(), server_default="false"),
        sa.Column("case_sensitive", sa.Boolean(), server_default="false"),
        sa.Column("contains", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Custom Search Results
    op.create_table(
        "custom_search_results",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("crawl_id", sa.UUID(), sa.ForeignKey("crawls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url_id", sa.UUID(), nullable=False),
        sa.Column("search_id", sa.UUID(), sa.ForeignKey("custom_searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("found_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_custom_search_results_url", "custom_search_results", ["url_id"])
    op.create_index("idx_custom_search_results_crawl", "custom_search_results", ["crawl_id"])
    op.create_foreign_key(
        "fk_custom_search_results_url",
        "custom_search_results",
        "crawled_urls",
        ["url_id", "crawl_id"],
        ["id", "crawl_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_table("custom_search_results")
    op.drop_table("custom_searches")
    op.drop_table("custom_extractions")
    op.drop_table("custom_extractors")
