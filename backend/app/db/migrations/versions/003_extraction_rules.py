"""Add extraction_rules table for custom CSS/XPath extraction.

Revision ID: 003_extraction_rules
Revises: 002_perf_indexes
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_extraction_rules"
down_revision: Union[str, None] = "002_perf_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS extraction_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            selector TEXT NOT NULL,
            selector_type VARCHAR(10) NOT NULL DEFAULT 'css'
                CHECK (selector_type IN ('css', 'xpath')),
            extract_type VARCHAR(20) NOT NULL DEFAULT 'text'
                CHECK (extract_type IN ('text', 'html', 'attribute', 'count')),
            attribute_name VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_extraction_rules_project ON extraction_rules (project_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS extraction_rules")
