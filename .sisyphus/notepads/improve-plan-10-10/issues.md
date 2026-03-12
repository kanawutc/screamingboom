# Issues — improve-plan-10-10

## Known Issues (pre-execution)
- PLAN.md has no Table of Contents — navigation difficult at 972+ lines
- Old draft `.sisyphus/drafts/seo-spider-clone.md` has wrong tech stack (React+Vite, SQLite-WASM) — contradicts PLAN.md; do NOT use for reference
- BeautifulSoup4 and Celery appear in current Tech Stack table — must be replaced

## File Edit Pattern
- EVERY task must: Read PLAN.md → Edit at specific insertion point → Save → Verify with grep
- Tasks in same wave edit different sections — no conflicts
- Wave 1 is sequential because T2 rewrites Architecture (lines 26-52) and T3 rewrites DB Schema (~lines 789-832) — different sections but same file, so sequential for safety

## Resolved Issues
- selectolax/XPath contradiction: solved with dual-parser (selectolax primary + lxml secondary)
- Single-user vs multi-user: V1 single-user, Feature 6.5 deferred to V2
