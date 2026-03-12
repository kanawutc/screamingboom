"""Initial schema: 6 core tables for Sprint 1.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === projects ===
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("settings", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_projects_domain", "projects", ["domain"])

    # === crawls ===
    op.create_table(
        "crawls",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column(
            "project_id",
            sa.UUID(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="idle", nullable=False),
        sa.Column("mode", sa.String(10), server_default="spider", nullable=False),
        sa.Column("config", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_urls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("crawled_urls_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('idle','configuring','queued','crawling','paused','completing','completed','failed','cancelled')",
            name="ck_crawls_status",
        ),
        sa.CheckConstraint("mode IN ('spider','list')", name="ck_crawls_mode"),
    )
    op.create_index("idx_crawls_project_id", "crawls", ["project_id"])
    op.execute(
        "CREATE INDEX idx_crawls_status ON crawls (status) WHERE status IN ('crawling', 'paused', 'queued')"
    )

    # === crawled_urls (HASH partitioned by crawl_id) ===
    # Must use raw SQL for partitioned tables — Alembic can't autogenerate partition DDL
    op.execute("""
        CREATE TABLE crawled_urls (
            id              UUID DEFAULT gen_random_uuid(),
            crawl_id        UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
            url             TEXT NOT NULL,
            url_hash        BYTEA NOT NULL,
            status_code     SMALLINT,
            content_type    VARCHAR(100),
            redirect_url    TEXT,
            redirect_chain  JSONB DEFAULT '[]',
            response_time_ms INTEGER,
            title           TEXT,
            title_length    SMALLINT,
            title_pixel_width SMALLINT,
            meta_description TEXT,
            meta_desc_length SMALLINT,
            h1              TEXT[],
            h2              TEXT[],
            canonical_url   TEXT,
            robots_meta     TEXT[],
            is_indexable    BOOLEAN NOT NULL DEFAULT true,
            indexability_reason VARCHAR(100),
            word_count      INTEGER,
            content_hash    BYTEA,
            crawl_depth     SMALLINT NOT NULL DEFAULT 0,
            seo_data        JSONB NOT NULL DEFAULT '{}',
            search_vector   TSVECTOR,
            crawled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, crawl_id)
        ) PARTITION BY HASH (crawl_id)
    """)

    # 4 HASH partitions (Sprint 1 simplicity — expandable later)
    for i in range(4):
        op.execute(
            f"CREATE TABLE crawled_urls_{i} PARTITION OF crawled_urls FOR VALUES WITH (MODULUS 4, REMAINDER {i})"
        )

    # Indexes on crawled_urls
    op.execute("CREATE INDEX idx_crawled_urls_crawl_hash ON crawled_urls (crawl_id, url_hash)")
    op.execute("CREATE INDEX idx_crawled_urls_status_code ON crawled_urls (crawl_id, status_code)")
    op.execute(
        "CREATE INDEX idx_crawled_urls_search_vector ON crawled_urls USING GIN (search_vector)"
    )
    op.execute("CREATE INDEX idx_crawled_urls_seo_data ON crawled_urls USING GIN (seo_data)")
    op.execute(
        "CREATE INDEX idx_crawled_urls_not_indexable ON crawled_urls (crawl_id) WHERE is_indexable = false"
    )
    op.execute(
        "CREATE INDEX idx_crawled_urls_errors ON crawled_urls (crawl_id, status_code) WHERE status_code >= 400"
    )

    # TSVECTOR auto-update trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_crawled_url_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.meta_description, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.url, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trig_crawled_url_search_vector
        BEFORE INSERT OR UPDATE OF title, meta_description, url
        ON crawled_urls
        FOR EACH ROW EXECUTE FUNCTION update_crawled_url_search_vector()
    """)

    # === page_links ===
    op.create_table(
        "page_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "crawl_id", sa.UUID(), sa.ForeignKey("crawls.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_url_id", sa.UUID(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("target_url_hash", sa.LargeBinary(), nullable=False),
        sa.Column("anchor_text", sa.Text(), nullable=True),
        sa.Column("link_type", sa.String(20), server_default="internal", nullable=False),
        sa.Column("rel_attrs", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("link_position", sa.String(20), nullable=True),
        sa.Column("is_javascript", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint(
            "link_type IN ('internal','external','resource')", name="ck_page_links_type"
        ),
    )
    op.create_index("idx_page_links_crawl_source", "page_links", ["crawl_id", "source_url_id"])
    op.create_index("idx_page_links_crawl_target", "page_links", ["crawl_id", "target_url_hash"])
    op.execute(
        "CREATE INDEX idx_page_links_nofollow ON page_links (crawl_id) WHERE 'nofollow' = ANY(rel_attrs)"
    )

    # === url_issues (HASH partitioned by crawl_id) ===
    op.execute("""
        CREATE TABLE url_issues (
            id          UUID DEFAULT gen_random_uuid(),
            crawl_id    UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
            url_id      UUID NOT NULL,
            issue_type  VARCHAR(100) NOT NULL,
            severity    VARCHAR(20) NOT NULL DEFAULT 'warning',
            category    VARCHAR(50) NOT NULL,
            details     JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (id, crawl_id),
            CHECK (severity IN ('critical','warning','info','opportunity'))
        ) PARTITION BY HASH (crawl_id)
    """)

    for i in range(4):
        op.execute(
            f"CREATE TABLE url_issues_{i} PARTITION OF url_issues FOR VALUES WITH (MODULUS 4, REMAINDER {i})"
        )

    op.execute("CREATE INDEX idx_url_issues_crawl_type ON url_issues (crawl_id, issue_type)")
    op.execute("CREATE INDEX idx_url_issues_crawl_severity ON url_issues (crawl_id, severity)")
    op.execute("CREATE INDEX idx_url_issues_url_id ON url_issues (crawl_id, url_id)")

    # === redirects ===
    op.create_table(
        "redirects",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "crawl_id", sa.UUID(), sa.ForeignKey("crawls.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "chain_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("hop_number", sa.SmallInteger(), server_default="1", nullable=False),
    )
    op.create_index("idx_redirects_crawl_chain", "redirects", ["crawl_id", "chain_id"])
    op.create_index("idx_redirects_source_url", "redirects", ["crawl_id", "source_url"])


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trig_crawled_url_search_vector ON crawled_urls")
    op.execute("DROP FUNCTION IF EXISTS update_crawled_url_search_vector()")
    op.drop_table("redirects")
    op.execute("DROP TABLE IF EXISTS url_issues CASCADE")
    op.execute("DROP TABLE IF EXISTS crawled_urls CASCADE")
    op.drop_table("page_links")
    op.drop_table("crawls")
    op.drop_table("projects")
