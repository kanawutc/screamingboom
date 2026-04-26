"""Link Score: Internal PageRank calculation (D=0.85, 10 iterations).

Computes an internal link equity score for every crawled URL.
Score normalized to 1-100 logarithmic scale.

Algorithm:
  LS(p) = (1-D)/N + D * Σ(LS(q) / outlinks(q))
  where q links to p internally

Nofollow links: don't pass score but count in outlink denominator.
Redirects: flow score to final target.
"""

import math
import uuid

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

DAMPING = 0.85
ITERATIONS = 10


async def calculate_link_scores(pool: asyncpg.Pool, crawl_id: uuid.UUID) -> int:
    """Calculate and store link scores for all URLs in a crawl.

    Returns number of URLs scored.
    """
    async with pool.acquire() as conn:
        # Step 1: Get all HTML pages (nodes in the graph)
        nodes = await conn.fetch(
            """
            SELECT id, url
            FROM crawled_urls
            WHERE crawl_id = $1
              AND content_type LIKE 'text/html%'
              AND status_code = 200
            """,
            crawl_id,
        )

        if len(nodes) < 2:
            logger.info("link_score_skip", crawl_id=str(crawl_id), reason="too_few_pages")
            return 0

        url_ids = {str(n["id"]) for n in nodes}
        id_to_idx = {str(n["id"]): i for i, n in enumerate(nodes)}
        n = len(nodes)

        # Step 2: Get internal links (edges)
        # rel_attrs is a text[] column; nofollow is stored as 'nofollow' in the array
        edges = await conn.fetch(
            """
            SELECT
                pl.source_url_id,
                cu_target.id AS target_url_id,
                COALESCE('nofollow' = ANY(pl.rel_attrs), false) AS is_nofollow
            FROM page_links pl
            JOIN crawled_urls cu_target
                ON pl.target_url_hash = cu_target.url_hash
                AND pl.crawl_id = cu_target.crawl_id
            WHERE pl.crawl_id = $1
              AND pl.link_type = 'internal'
              AND cu_target.status_code = 200
              AND cu_target.content_type LIKE 'text/html%'
            """,
            crawl_id,
        )

        # Build adjacency: outlinks per source, inlinks per target
        # outlink_count[i] = total outlinks from node i (including nofollow)
        # inlinks[j] = list of (source_idx, passes_score)
        outlink_count = [0] * n
        inlinks: list[list[tuple[int, bool]]] = [[] for _ in range(n)]

        for edge in edges:
            src_id = str(edge["source_url_id"])
            tgt_id = str(edge["target_url_id"])

            if src_id not in id_to_idx or tgt_id not in id_to_idx:
                continue

            src_idx = id_to_idx[src_id]
            tgt_idx = id_to_idx[tgt_id]
            is_nofollow = edge["is_nofollow"]

            outlink_count[src_idx] += 1
            # Nofollow links count in denominator but don't pass score
            if not is_nofollow:
                inlinks[tgt_idx].append((src_idx, True))

        # Step 3: PageRank iterations
        scores = [1.0 / n] * n
        base = (1 - DAMPING) / n

        for iteration in range(ITERATIONS):
            new_scores = [0.0] * n
            for j in range(n):
                incoming = 0.0
                for src_idx, _ in inlinks[j]:
                    if outlink_count[src_idx] > 0:
                        incoming += scores[src_idx] / outlink_count[src_idx]
                new_scores[j] = base + DAMPING * incoming
            scores = new_scores

        # Step 4: Normalize to 1-100 log scale
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0

        if max_score > min_score:
            normalized = []
            for s in scores:
                # Log transform for better distribution
                ratio = (s - min_score) / (max_score - min_score)
                # Avoid log(0)
                log_score = math.log10(ratio * 99 + 1) / math.log10(100)
                normalized.append(max(1, round(log_score * 99 + 1)))
        else:
            normalized = [50] * n  # All equal

        # Step 5: Store scores in seo_data JSONB
        update_records = []
        for i, node in enumerate(nodes):
            update_records.append((normalized[i], crawl_id, node["id"]))

        await conn.executemany(
            """
            UPDATE crawled_urls
            SET seo_data = COALESCE(seo_data, '{}'::jsonb) || jsonb_build_object('link_score', $1::int)
            WHERE crawl_id = $2 AND id = $3
            """,
            update_records,
        )

        logger.info(
            "link_score_complete",
            crawl_id=str(crawl_id),
            pages_scored=n,
            max_raw=round(max_score, 8),
            min_raw=round(min_score, 8),
        )

        return n
