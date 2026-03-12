"""Post-crawl analysis: cross-URL SQL-based checks.

Runs during the COMPLETING state after all URLs have been crawled and inserted.
Uses SQL GROUP BY / JOIN queries — never loads all URLs into memory.
"""

import json
import uuid

import asyncpg
import structlog

from app.analysis.issue_registry import ISSUE_REGISTRY

logger = structlog.get_logger(__name__)


async def run_post_crawl_analysis(pool: asyncpg.Pool, crawl_id: uuid.UUID) -> int:
    """Execute all post-crawl SQL-based analysis. Returns total issues created."""
    total = 0

    async with pool.acquire() as conn:
        total += await _detect_duplicate_titles(conn, crawl_id)
        total += await _detect_duplicate_meta_descriptions(conn, crawl_id)
        total += await _detect_duplicate_h1s(conn, crawl_id)
        total += await _detect_broken_links(conn, crawl_id)
        total += await _verify_canonical_targets(conn, crawl_id)

    logger.info("post_crawl_analysis_complete", crawl_id=str(crawl_id), issues_created=total)
    return total


# ---------------------------------------------------------------------------
# Duplicate detection helpers
# ---------------------------------------------------------------------------


async def _detect_duplicates(
    conn: asyncpg.Connection,
    crawl_id: uuid.UUID,
    column: str,
    issue_type: str,
    label: str,
) -> int:
    """Generic duplicate detection: GROUP BY column HAVING COUNT > 1."""
    defn = ISSUE_REGISTRY[issue_type]

    # Find duplicate values
    query = f"""
        SELECT {column}, array_agg(id) as url_ids, COUNT(*) as cnt
        FROM crawled_urls
        WHERE crawl_id = $1
          AND {column} IS NOT NULL
          AND {column} != ''
          AND content_type LIKE 'text/html%'
        GROUP BY {column}
        HAVING COUNT(*) > 1
    """
    rows = await conn.fetch(query, crawl_id)

    if not rows:
        return 0

    # Build issue records for each URL in each duplicate group
    issue_records = []
    for row in rows:
        duplicate_value = row[column]
        url_ids = row["url_ids"]
        count = row["cnt"]

        for uid in url_ids:
            issue_records.append(
                (
                    uuid.uuid4(),
                    crawl_id,
                    uid,
                    issue_type,
                    defn.severity.value,
                    defn.category.value,
                    json.dumps(
                        {
                            label: str(duplicate_value)[:200],
                            "duplicate_count": count,
                        }
                    ),
                )
            )

    # Batch insert
    if issue_records:
        await conn.copy_records_to_table(
            "url_issues",
            records=issue_records,
            columns=["id", "crawl_id", "url_id", "issue_type", "severity", "category", "details"],
        )

    return len(issue_records)


async def _detect_duplicate_titles(conn: asyncpg.Connection, crawl_id: uuid.UUID) -> int:
    return await _detect_duplicates(conn, crawl_id, "title", "duplicate_title", "title")


async def _detect_duplicate_meta_descriptions(conn: asyncpg.Connection, crawl_id: uuid.UUID) -> int:
    return await _detect_duplicates(
        conn, crawl_id, "meta_description", "duplicate_meta_description", "meta_description"
    )


async def _detect_duplicate_h1s(conn: asyncpg.Connection, crawl_id: uuid.UUID) -> int:
    """Detect duplicate H1s using the first H1 from the h1 array."""
    defn = ISSUE_REGISTRY["duplicate_h1"]

    query = """
        SELECT h1[1] as first_h1, array_agg(id) as url_ids, COUNT(*) as cnt
        FROM crawled_urls
        WHERE crawl_id = $1
          AND h1 IS NOT NULL
          AND array_length(h1, 1) > 0
          AND content_type LIKE 'text/html%'
        GROUP BY h1[1]
        HAVING COUNT(*) > 1
    """
    rows = await conn.fetch(query, crawl_id)

    if not rows:
        return 0

    issue_records = []
    for row in rows:
        h1_value = row["first_h1"]
        url_ids = row["url_ids"]
        count = row["cnt"]

        for uid in url_ids:
            issue_records.append(
                (
                    uuid.uuid4(),
                    crawl_id,
                    uid,
                    "duplicate_h1",
                    defn.severity.value,
                    defn.category.value,
                    json.dumps(
                        {
                            "h1": str(h1_value)[:200],
                            "duplicate_count": count,
                        }
                    ),
                )
            )

    if issue_records:
        await conn.copy_records_to_table(
            "url_issues",
            records=issue_records,
            columns=["id", "crawl_id", "url_id", "issue_type", "severity", "category", "details"],
        )

    return len(issue_records)


# ---------------------------------------------------------------------------
# Broken links detection (F2.9)
# ---------------------------------------------------------------------------


async def _detect_broken_links(conn: asyncpg.Connection, crawl_id: uuid.UUID) -> int:
    """Find internal links pointing to 4xx/5xx URLs."""
    defn_4xx = ISSUE_REGISTRY["broken_link_4xx"]
    defn_5xx = ISSUE_REGISTRY["broken_link_5xx"]

    query = """
        SELECT
            pl.source_url_id,
            pl.target_url,
            pl.anchor_text,
            cu_target.status_code
        FROM page_links pl
        JOIN crawled_urls cu_target
            ON pl.target_url_hash = cu_target.url_hash
            AND pl.crawl_id = cu_target.crawl_id
        WHERE pl.crawl_id = $1
          AND pl.link_type = 'internal'
          AND cu_target.status_code >= 400
    """
    rows = await conn.fetch(query, crawl_id)

    if not rows:
        return 0

    issue_records = []
    for row in rows:
        status_code = row["status_code"]
        if status_code >= 500:
            issue_type = "broken_link_5xx"
            defn = defn_5xx
        else:
            issue_type = "broken_link_4xx"
            defn = defn_4xx

        issue_records.append(
            (
                uuid.uuid4(),
                crawl_id,
                row["source_url_id"],
                issue_type,
                defn.severity.value,
                defn.category.value,
                json.dumps(
                    {
                        "target_url": row["target_url"][:200],
                        "status_code": status_code,
                        "anchor_text": (row["anchor_text"] or "")[:100],
                    }
                ),
            )
        )

    if issue_records:
        await conn.copy_records_to_table(
            "url_issues",
            records=issue_records,
            columns=["id", "crawl_id", "url_id", "issue_type", "severity", "category", "details"],
        )

    return len(issue_records)


# ---------------------------------------------------------------------------
# Canonical cross-URL verification
# ---------------------------------------------------------------------------


async def _verify_canonical_targets(conn: asyncpg.Connection, crawl_id: uuid.UUID) -> int:
    """Find canonicals pointing to non-indexable URLs or uncrawled URLs."""
    defn = ISSUE_REGISTRY["non_indexable_canonical"]

    # Canonical targets that were crawled but are non-indexable
    query = """
        SELECT cu.id as source_id, cu.url, cu.canonical_url
        FROM crawled_urls cu
        JOIN crawled_urls cu_target
            ON cu_target.url = cu.canonical_url
            AND cu_target.crawl_id = cu.crawl_id
        WHERE cu.crawl_id = $1
          AND cu.canonical_url IS NOT NULL
          AND cu.canonical_url != cu.url
          AND cu_target.is_indexable = false
          AND cu.content_type LIKE 'text/html%'
    """

    rows = await conn.fetch(query, crawl_id)

    issue_records = []
    for row in rows:
        issue_records.append(
            (
                uuid.uuid4(),
                crawl_id,
                row["source_id"],
                "non_indexable_canonical",
                defn.severity.value,
                defn.category.value,
                json.dumps(
                    {
                        "canonical_url": row["canonical_url"][:200],
                        "reason": "target_non_indexable",
                    }
                ),
            )
        )

    if issue_records:
        await conn.copy_records_to_table(
            "url_issues",
            records=issue_records,
            columns=["id", "crawl_id", "url_id", "issue_type", "severity", "category", "details"],
        )

    return len(issue_records)
