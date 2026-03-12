# Draft: PLAN.MD Improvement to 10/10

## Current Assessment
- **Current Score**: 6/10 (good feature list, poor technical depth)
- **Target Score**: 10/10 (full specification, ready for implementation)

## Research Results Summary

### From Gap Analysis (Explorer):
- API specification: 0/10 (zero endpoints documented)
- Project structure: 0/10 (no file layout)
- Testing strategy: 0/10 (zero test docs)
- Deployment: 1/10 (Docker only mentioned)
- Database schema: 2/10 (only table names)
- Performance: 2/10 (no scale strategy)
- Architecture: 3/10 (basic diagram, no flows)
- Technical: 4/10 (algorithms mentioned, not detailed)
- UI/UX: 5/10 (ASCII layout, no components)
- Features: 8/10 (missing 10 edge features)

### From Crawler Architecture Research (Librarian 1):
- **KEY CHANGE**: Use selectolax instead of BeautifulSoup4 (35x faster parsing)
- **KEY CHANGE**: Use ARQ instead of Celery (async-native, simpler)
- **KEY CHANGE**: Use asyncpg for hot path (3-10x faster than SQLAlchemy)
- Bloom filter for URL deduplication (12MB per 1M URLs)
- Two-level URL frontier (priority + politeness queues)
- Redis sorted sets for frontier management
- PostgreSQL HASH partitioning by crawl_id
- WebSocket via Redis pub/sub for decoupled real-time updates
- Batch insert with COPY (50k rows/sec vs 500/sec individual)
- Performance targets: 20-50 pages/sec, <100ms WS latency

### From Full-Stack Patterns Research (Librarian 2):
- Next.js: RSC for initial load + TanStack Query for client-side
- FastAPI: Router → Service → Repository pattern
- PostgreSQL: Full schema with JSONB for flexible SEO data
- API: Keyset/cursor pagination (not OFFSET)
- Docker: Multi-stage builds, health checks, Nginx reverse proxy
- Testing: Layered pyramid (unit → API → integration → E2E)

## Decisions Made

### Tech Stack Updates:
1. ✅ BeautifulSoup4 → **selectolax** (35x faster HTML parsing)
2. ✅ Celery → **ARQ** (async-native, Redis-backed, simpler)
3. ✅ Add **asyncpg** for bulk DB operations (hot path)
4. ✅ Keep SQLAlchemy for ORM queries (convenience)
5. ✅ Add **Bloom filter** (pybloom-live) for URL deduplication
6. ✅ Add **Nginx** reverse proxy
7. ✅ TanStack Table → confirm + add **react-virtual** for 1M+ rows
8. ✅ Add **TanStack Query** for client-side data fetching

### New Sections to Add:
1. Crawler Engine Architecture (state machine, data flow, algorithms)
2. Complete Database Schema (columns, types, indexes, relationships)
3. API Specification (all endpoints with request/response schemas)
4. Project Structure (frontend + backend directory trees)
5. WebSocket Protocol (message types, reconnection, backpressure)
6. Performance Strategy (targets, scaling, optimization)
7. Testing Strategy (unit, integration, E2E, mocking)
8. Docker Compose Configuration (full YAML with health checks)
9. Error Handling Strategy (retry, circuit breaker, graceful degradation)
10. Feature Dependency Graph (build order, critical path)

### User Preferences:
- Scope: Improve existing PLAN.md
- Depth: Full Specification (column-level DB, endpoint-level API)
