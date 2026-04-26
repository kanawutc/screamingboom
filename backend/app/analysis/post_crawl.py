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
        # Pagination post-crawl analysis
        total += await _detect_non_200_pagination_urls(conn, crawl_id)
        total += await _detect_unlinked_pagination_urls(conn, crawl_id)
        total += await _detect_pagination_loops(conn, crawl_id)
        total += await _detect_pagination_sequence_errors(conn, crawl_id)

    # Link Score calculation (runs outside the connection context)
    from app.analysis.link_score import calculate_link_scores
    try:
        pages_scored = await calculate_link_scores(pool, crawl_id)
        logger.info("link_score_calculated", crawl_id=str(crawl_id), pages_scored=pages_scored)
    except Exception as e:
        logger.warning("link_score_failed", crawl_id=str(crawl_id), error=str(e))

    logger.info("post_crawl_analysis_complete", crawl_id=str(crawl_id), issues_created=total)
    return total


# ---------------------------------------------------------------------------
# Duplicate detection helpers
# ---------------------------------------------------------------------------


_ALLOWED_DUPLICATE_COLUMNS = frozenset({"title", "meta_description", "h1"})


async def _detect_duplicates(
    conn: asyncpg.Connection,
    crawl_id: uuid.UUID,
    column: str,
    issue_type: str,
    label: str,
) -> int:
    """Generic duplicate detection: GROUP BY column HAVING COUNT > 1."""
    if column not in _ALLOWED_DUPLICATE_COLUMNS:
        raise ValueError(f"Invalid column for duplicate detection: {column}")

    defn = ISSUE_REGISTRY[issue_type]

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


# ---------------------------------------------------------------------------
# Pagination post-crawl analysis (rel="next" / rel="prev")
# ---------------------------------------------------------------------------


async def _detect_non_200_pagination_urls(
    conn: asyncpg.Connection, crawl_id: uuid.UUID
) -> int:
    """Find pages whose rel=next/prev point to non-200 URLs."""
    defn = ISSUE_REGISTRY["non_200_pagination_url"]

    query = """
        WITH pagination_pages AS (
            SELECT id, url,
                   seo_data->'pagination'->>'rel_next' AS rel_next,
                   seo_data->'pagination'->>'rel_prev' AS rel_prev
            FROM crawled_urls
            WHERE crawl_id = $1
              AND seo_data->'pagination' IS NOT NULL
        )
        SELECT pp.id AS source_id, pp.url,
               'rel_next' AS attr, pp.rel_next AS pag_url, ct.status_code
        FROM pagination_pages pp
        JOIN crawled_urls ct ON ct.url = pp.rel_next AND ct.crawl_id = $1
        WHERE pp.rel_next IS NOT NULL AND ct.status_code != 200
        UNION ALL
        SELECT pp.id AS source_id, pp.url,
               'rel_prev' AS attr, pp.rel_prev AS pag_url, ct.status_code
        FROM pagination_pages pp
        JOIN crawled_urls ct ON ct.url = pp.rel_prev AND ct.crawl_id = $1
        WHERE pp.rel_prev IS NOT NULL AND ct.status_code != 200
    """

    rows = await conn.fetch(query, crawl_id)
    if not rows:
        return 0

    issue_records = []
    for row in rows:
        issue_records.append(
            (
                uuid.uuid4(),
                crawl_id,
                row["source_id"],
                "non_200_pagination_url",
                defn.severity.value,
                defn.category.value,
                json.dumps(
                    {
                        "pagination_url": row["pag_url"][:200],
                        "attribute": row["attr"],
                        "status_code": row["status_code"],
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


async def _detect_unlinked_pagination_urls(
    conn: asyncpg.Connection, crawl_id: uuid.UUID
) -> int:
    """Find pagination URLs that are not linked to by any page."""
    defn = ISSUE_REGISTRY["unlinked_pagination_url"]

    query = """
        WITH pag_urls AS (
            SELECT id AS source_id,
                   seo_data->'pagination'->>'rel_next' AS pag_url,
                   'rel_next' AS attr
            FROM crawled_urls
            WHERE crawl_id = $1
              AND seo_data->'pagination'->>'rel_next' IS NOT NULL
            UNION ALL
            SELECT id AS source_id,
                   seo_data->'pagination'->>'rel_prev' AS pag_url,
                   'rel_prev' AS attr
            FROM crawled_urls
            WHERE crawl_id = $1
              AND seo_data->'pagination'->>'rel_prev' IS NOT NULL
        )
        SELECT pu.source_id, pu.pag_url, pu.attr
        FROM pag_urls pu
        WHERE NOT EXISTS (
            SELECT 1 FROM page_links pl
            WHERE pl.crawl_id = $1
              AND pl.target_url = pu.pag_url
              AND pl.link_type = 'internal'
        )
    """

    rows = await conn.fetch(query, crawl_id)
    if not rows:
        return 0

    issue_records = []
    for row in rows:
        issue_records.append(
            (
                uuid.uuid4(),
                crawl_id,
                row["source_id"],
                "unlinked_pagination_url",
                defn.severity.value,
                defn.category.value,
                json.dumps(
                    {
                        "pagination_url": row["pag_url"][:200],
                        "attribute": row["attr"],
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


async def _detect_pagination_loops(
    conn: asyncpg.Connection, crawl_id: uuid.UUID
) -> int:
    """Detect pagination chains that loop back to a previously visited URL."""
    defn = ISSUE_REGISTRY["pagination_loop"]

    # Walk rel_next chains up to 500 hops to detect loops
    query = """
        WITH RECURSIVE chain AS (
            -- Seed: first pages (have rel_next but no rel_prev)
            SELECT url,
                   seo_data->'pagination'->>'rel_next' AS next_url,
                   ARRAY[url] AS visited,
                   1 AS depth,
                   FALSE AS is_loop,
                   id AS source_id
            FROM crawled_urls
            WHERE crawl_id = $1
              AND seo_data->'pagination'->>'rel_next' IS NOT NULL
              AND seo_data->'pagination'->>'rel_prev' IS NULL

            UNION ALL

            SELECT cu.url,
                   cu.seo_data->'pagination'->>'rel_next' AS next_url,
                   c.visited || cu.url,
                   c.depth + 1,
                   cu.url = ANY(c.visited) AS is_loop,
                   cu.id AS source_id
            FROM chain c
            JOIN crawled_urls cu ON cu.url = c.next_url AND cu.crawl_id = $1
            WHERE c.depth < 500
              AND NOT c.is_loop
              AND cu.seo_data->'pagination'->>'rel_next' IS NOT NULL
        )
        SELECT source_id, url, next_url
        FROM chain
        WHERE is_loop = TRUE
    """

    rows = await conn.fetch(query, crawl_id)
    if not rows:
        return 0

    issue_records = []
    for row in rows:
        issue_records.append(
            (
                uuid.uuid4(),
                crawl_id,
                row["source_id"],
                "pagination_loop",
                defn.severity.value,
                defn.category.value,
                json.dumps(
                    {
                        "url": row["url"][:200],
                        "loops_to": row["next_url"][:200] if row["next_url"] else None,
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


async def _detect_pagination_sequence_errors(
    conn: asyncpg.Connection, crawl_id: uuid.UUID
) -> int:
    """Find pages where rel=next/prev don't reciprocate correctly.

    If page A has rel_next=B, then B should have rel_prev=A.
    If page A has rel_prev=C, then C should have rel_next=A.
    """
    defn = ISSUE_REGISTRY["pagination_sequence_error"]

    query = """
        WITH pag AS (
            SELECT id, url,
                   seo_data->'pagination'->>'rel_next' AS rel_next,
                   seo_data->'pagination'->>'rel_prev' AS rel_prev
            FROM crawled_urls
            WHERE crawl_id = $1
              AND seo_data->'pagination' IS NOT NULL
        )
        -- Check: A.rel_next = B, but B.rel_prev != A
        SELECT a.id AS source_id, a.url, 'rel_next' AS direction,
               a.rel_next AS expected_target,
               COALESCE(b.rel_prev, '(none)') AS actual_back_ref
        FROM pag a
        JOIN pag b ON b.url = a.rel_next
        WHERE a.rel_next IS NOT NULL
          AND (b.rel_prev IS NULL OR b.rel_prev != a.url)

        UNION ALL

        -- Check: A.rel_prev = C, but C.rel_next != A
        SELECT a.id AS source_id, a.url, 'rel_prev' AS direction,
               a.rel_prev AS expected_target,
               COALESCE(c.rel_next, '(none)') AS actual_back_ref
        FROM pag a
        JOIN pag c ON c.url = a.rel_prev
        WHERE a.rel_prev IS NOT NULL
          AND (c.rel_next IS NULL OR c.rel_next != a.url)
    """

    rows = await conn.fetch(query, crawl_id)
    if not rows:
        return 0

    issue_records = []
    for row in rows:
        issue_records.append(
            (
                uuid.uuid4(),
                crawl_id,
                row["source_id"],
                "pagination_sequence_error",
                defn.severity.value,
                defn.category.value,
                json.dumps(
                    {
                        "direction": row["direction"],
                        "expected_target": row["expected_target"][:200],
                        "actual_back_ref": row["actual_back_ref"][:200],
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
