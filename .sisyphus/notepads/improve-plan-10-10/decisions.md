# Decisions — improve-plan-10-10

## Architecture Decisions
- V1 is single-user (no auth, no multi-tenant)
- Feature 6.5 (Collaboration) deferred to V2
- HASH partitioning: crawled_urls + url_issues only; page_links stays unpartitioned
- No Kubernetes, no Prometheus/Grafana, no TLS in Docker Compose
- No working code files in PLAN.md — documentation only

## Insertion Points (planned)
- Table of Contents: after title (line 5-8 area), before "สรุป Feature"
- Architecture: replace lines 26-52
- Project Structure: new section after Architecture, before Phase 1
- DB Schema: replace current simplified schema (~lines 789-832)
- Crawler Engine Deep Dive: new section after DB Schema
- WebSocket Protocol: new section after Crawler Engine
- API Specification: new section after WebSocket Protocol
- Performance Strategy: new section after API Spec
- Error Handling: new section after Performance
- Testing Strategy: new section after Error Handling
- Docker Compose: expand Quick Start (~lines 908-920)
- Feature Dependency Graph: last section before URL References

## Wave Execution Order
1. T1 (quick) → T2 (deep) → T3 (unspecified-high) [sequential]
2. T4 + T5 + T6 [parallel after Wave 1]
3. T7 + T8 + T9 [parallel after Wave 2]
4. T10 + T11 [parallel after Wave 3]
5. T12 → T13 [sequential]
6. T14 [after all]
7. F1 + F2 + F3 + F4 [parallel verification]
