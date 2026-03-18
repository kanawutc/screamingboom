# SEO Spider — Product Requirements Document

## Product Vision
Self-hosted, open-source SEO crawling and analysis tool modeled after Screaming Frog SEO Spider. Crawls websites, detects 300+ SEO issues, and provides real-time progress monitoring. Single-user, self-hosted via Docker Compose.

## Target Users
- SEO professionals managing multiple client sites
- Web developers auditing their own sites
- Marketing teams monitoring site health
- Agencies needing self-hosted (data privacy) SEO tooling

## Core Value Proposition
- Free, self-hosted alternative to Screaming Frog ($259/year)
- No URL limits (Screaming Frog free: 500 URL cap)
- Real-time WebSocket progress (vs Screaming Frog's desktop app)
- API-first: every feature accessible via REST API
- AI-ready: Phase 4 adds LLM-powered analysis

## Phases & Scope

### Phase 1: Core Crawl Engine (12 features) — COMPLETE
Spider/list mode crawling, URL discovery, HTTP handling, robots.txt, user agent config, crawl limits, include/exclude patterns, URL rewriting, CDN config, authentication. JS rendering deferred.

### Phase 2: SEO Analysis & Audit (15 features) — IN PROGRESS
Titles, meta descriptions, headings, images, canonicals, directives, URL quality, security, broken links, internal links, content analysis, duplicate detection, indexability, SERP preview, issues system.
- Backend: 9 of 15 rule modules implemented
- Frontend: All 6 pages implemented with 14 analysis tabs

### Phase 3: Advanced Analysis (15 features) — PLANNED
Structured data validation, hreflang audit, XML sitemap audit/generator, redirect audit, link score (PageRank), orphan pages, accessibility (AXE), spelling/grammar, crawl comparison, PDF audit, cookie audit, pagination audit, mobile usability, Core Web Vitals.

### Phase 4: Integrations & AI (8 features) — PLANNED
Custom extraction (CSS/XPath/Regex), custom search, AI integration (OpenAI/Gemini/Anthropic/Ollama), vector embeddings, Google Analytics, Google Search Console, PageSpeed Insights, link metrics (Ahrefs/Moz).

### Phase 5: Reports & Automation (7 features) — PLANNED
Export system (CSV/XLSX/Sheets), pre-built reports, visualizations (D3.js/Three.js), scheduling, configuration profiles, crawl storage management, segments.

### Phase 6: Bonus Features (6 features) — PLANNED
SEO score dashboard, AI fix suggestions, automated alerts, audit report generator, real-time collaboration (V2), plugin system.

## Non-Functional Requirements
- Crawl throughput: 20-50 pages/sec
- API response p95: < 200ms
- Support 1M+ URLs per crawl
- Memory: < 2GB for 100k URLs, < 8GB for 1M URLs
- Export 100k rows CSV in < 30s

## Out of Scope (V1)
- Multi-user authentication/authorization
- SaaS/cloud deployment
- Mobile app
- Real-time collaboration
- White-label/branding

## Related Documents
- `prd/tech-specs.md` — Full technical specification
- `prd/features.json` — Machine-readable feature tracking
- `PLAN.md` — Detailed implementation plan (57 features)
- `CLAUDE.md` — AI agent instructions
