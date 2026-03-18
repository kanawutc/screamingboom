# Crawler Pipeline — AGENTS.md

## Pipeline Flow

```
Seed → Frontier (Redis ZADD) → Pop (ZPOPMIN) → Robots Check → Fetch (aiohttp) → Parse (selectolax) → Inline Analysis → Batch Insert (asyncpg COPY) → Enqueue Discovered Links → Publish Progress (Redis pub/sub)
```

## Files & Responsibilities

| File | Class/Functions | Purpose |
|------|----------------|---------|
| `engine.py` | `CrawlEngine` | BFS orchestrator. Coordinates all components. Manages state (paused/stopped). Aborts after 50 consecutive domain failures. |
| `frontier.py` | `URLFrontier` | Redis sorted set (`crawl:{id}:frontier`) + in-memory Bloom filter (1M cap, 0.1% FP). BFS via depth-as-score. `add()`, `pop()`, `add_batch()`. |
| `fetcher.py` | `FetcherPool` | aiohttp with TCPConnector (limit_per_host=2, DNS cache 300s). Manual redirect following (max 10 hops, loop detection). Exponential backoff: 1/2/4/8s for 5XX, 30/60/120s for 429. Returns `FetchResult`. |
| `parser.py` | `parse()` | selectolax HTML parser. Extracts 10+ fields: title, meta_description, robots_meta, canonical, headings (H1-H6), links, images, hreflang, pagination, JSON-LD, OG tags. Returns `PageData` dataclass. |
| `inserter.py` | `BatchInserter` | 4 buffers (urls, links, redirects, issues). Flush at 500 items or 2s. Uses asyncpg COPY (50k rows/sec). Falls back to individual INSERTs on COPY failure for error isolation. |
| `robots.py` | `RobotsChecker` | 3-tier cache: in-memory → Redis (1h TTL) → fetch from origin. Treats fetch failures as "allow all" (permissive). |
| `utils.py` | `normalize_url()`, `url_hash()` | URL normalization (lowercase scheme/host, strip fragments, resolve relative). MD5 hash for dedup. |

## Data Types

- `FetchResult`: url, final_url, status_code, headers, body, content_type, response_time_ms, redirect_chain, error
- `PageData`: title, title_count, meta_description, meta_desc_count, canonical_url, canonical_count, robots_meta, h1, h2, headings_sequence, links, images, hreflang, json_ld_blocks, og_tags, word_count, content_hash, pagination, mixed_content_urls, security_headers, custom_extractions

## Error Handling

| Component | Failure | Recovery |
|-----------|---------|----------|
| Fetcher | Connection error / timeout | Retry 3x with exponential backoff |
| Fetcher | 429 (rate limit) | Backoff 30/60/120s |
| Fetcher | Redirect loop | Return error result, no retry |
| Parser | Invalid HTML | Log warning, return partial data |
| Inserter | COPY fails | Fallback to row-by-row INSERT |
| Robots | Fetch fails | Allow all (permissive) |
| Engine | 50 consecutive failures | Abort crawl |
| Engine | Unreachable start URL | Fail immediately |

## Redis Keys

- `crawl:{crawl_id}:frontier` — sorted set (URL queue, score=depth)
- `crawl:{crawl_id}:events` — pub/sub channel (progress updates)
- `crawl:{crawl_id}:control` — pub/sub channel (pause/resume/stop commands)
- `robots:{domain}` — cached robots.txt content (1h TTL)

## Key Design Decisions

1. BFS not DFS — sorted set score = depth ensures breadth-first.
2. Bloom filter is in-memory, not persisted — acceptable for single-crawl dedup.
3. Manual redirect following — needed to track full chain for SEO analysis.
4. selectolax over BeautifulSoup — 35x faster HTML parsing.
5. asyncpg COPY over INSERT — 10x throughput for batch writes.
6. Progress throttled to every 10 URLs or 0.5s — prevents WebSocket flood.
