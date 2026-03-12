# Sprint 1 Foundation — Issues & Gotchas

## [2026-03-11T11:27:19Z] Session: ses_323f72f60ffe3BrBLGS3ovV1XZ
### Known Risk Areas (from Metis + research)
- pybloom-live last release 2021 — Python 3.12 compatibility uncertain (Task 1 must verify this FIRST)
- asyncpg COPY on HASH-partitioned tables: all-or-nothing per batch — need error isolation
- ARQ default job_timeout=300s SILENTLY kills long crawls — MUST override to 7200
- Docker macOS volume mounts require VirtioFS for performance
- Nginx default proxy_read_timeout=60s kills WebSocket connections — MUST set to 3600s
- Alembic cannot auto-generate HASH partition DDL — use op.execute() raw SQL
