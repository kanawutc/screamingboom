# Sprint 1 Foundation — Decisions

## [2026-03-11T11:27:19Z] Session: ses_323f72f60ffe3BrBLGS3ovV1XZ

### Tech Stack (ALL FINAL — sourced from Metis consultation)
- **DB IDs**: UUID `gen_random_uuid()` for crawled_urls + url_issues (NOT BIGSERIAL — avoids sequence contention on HASH-partitioned tables)
- **Partitions**: 4 HASH partitions for Sprint 1 (not 16)
- **ARQ**: `job_timeout=7200`, `max_tries=1`, `health_check_interval=30`, `max_jobs=1`
- **aiohttp**: `TCPConnector(limit=0, limit_per_host=2, ttl_dns_cache=300)`, always consume response body
- **Redis frontier**: crawl depth (integer) as sorted set score for BFS, ZADD NX
- **asyncpg COPY**: Try COPY first, on failure fall back to individual INSERTs
- **Alembic**: psycopg2 sync driver in env.py, op.execute() for partition DDL
- **Parser**: selectolax primary, lxml XPath fallback
- **pybloom-live**: Must verify Python 3.12 compatibility first (Task 1); fallback = rbloom or Python set()

### Scope Decisions
- url_issues table: created in schema but remains EMPTY until Sprint 2
- Single crawl at a time: ARQ max_jobs=1
- 4 frontend pages only: dashboard, crawl list, new crawl form, crawl detail
- 16 API endpoints max
- No auth/login system in Sprint 1

### WebSocket
- CrawlBroadcaster pattern: one Redis subscription per crawl_id, fan-out to asyncio.Queue per client
- Nginx needs: `proxy_read_timeout 3600s`, `map $http_upgrade` directive

### Docker
- macOS: WATCHPACK_POLLING=true, WATCHFILES_FORCE_POLLING=true, VirtioFS
- Separate `migrate` service with `service_completed_successfully` condition for Alembic
