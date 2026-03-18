# Frontend — AGENTS.md

## Stack
Next.js 16 (App Router, standalone output), React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui (Radix), Zustand 5, TanStack React Query 5, Lucide React icons.

## Architecture
- App Router with `(dashboard)` route group.
- All pages are client components (heavy interactivity).
- Data fetching via React Query with 5s refetch intervals for live data.
- Real-time updates via WebSocket hook + Zustand store.
- API calls through typed `lib/api-client.ts` (never use raw fetch).
- Settings persisted to localStorage.

## Implementation Status

### Pages (6/6 fully implemented)

| Page | Path | Status | Key Features |
|------|------|--------|-------------|
| Dashboard | `(dashboard)/page.tsx` | Complete | Stats cards, active crawls, projects table, recent crawls |
| Crawls List | `crawls/page.tsx` | Complete | Filters (status/project), pagination, stop/delete actions |
| Crawl Detail | `crawls/[crawlId]/page.tsx` | Complete | 14 tabs, sub-filters, live progress, bottom detail panel, export CSV/XLSX |
| New Crawl | `crawls/new/page.tsx` | Complete | Spider/list mode, config options, UA presets, custom extraction rules builder |
| Compare | `crawls/compare/page.tsx` | Complete | Project/crawl selectors, change type filters, diff table |
| Settings | `settings/page.tsx` | Complete | Crawl defaults, UA presets, robots.txt toggle, localStorage |

### Components

| Component | Path | Status |
|-----------|------|--------|
| Sidebar | `components/layout/Sidebar.tsx` | Complete — dark theme, nav, "New Crawl" button |
| Topbar | `components/layout/Topbar.tsx` | Stub — minimal, not integrated |
| StatusBadge | `components/crawl/StatusBadge.tsx` | Complete — color-coded for all 9 crawl statuses |
| shadcn/ui | `components/ui/` | 13 components: button, card, input, select, table, tabs, badge, dialog, dropdown-menu, progress, separator, toast, sonner |

### Core Libraries

| File | Purpose | Status |
|------|---------|--------|
| `lib/api-client.ts` | Typed API client (projectsApi, crawlsApi, urlsApi, issuesApi, extractionRulesApi, healthApi) | Complete |
| `hooks/use-crawl-websocket.ts` | WebSocket with auto-reconnect (max 10 attempts, 3s delay) | Complete |
| `stores/crawl-store.ts` | Zustand: activeCrawlId, progress, liveStatus, wsConnected | Complete |
| `types/index.ts` | Full TypeScript types for all domain models | Complete |
| `lib/query-client.ts` | React Query config (30s staleTime, 1 retry) | Complete |
| `lib/utils.ts` | `cn()` for Tailwind class merging | Complete |

## Coding Conventions
- **Components**: Function components only. No class components.
- **State**: Zustand for global (crawl state), useState for local (forms, UI).
- **Data fetching**: React Query `useQuery`/`useMutation`. Never `useEffect` + fetch.
- **Styling**: Tailwind utility classes. Use `cn()` from `lib/utils.ts` for conditional classes.
- **Imports**: `@/` path alias for all imports (maps to project root).
- **Icons**: Lucide React (`lucide-react` package).
- **Error handling**: ApiError class in api-client.ts. Display via toast (sonner).
- **Types**: All props typed. Use types from `types/index.ts` — never inline type definitions for domain models.

## API Client Usage

```typescript
import { crawlsApi } from '@/lib/api-client'

// In React Query
const { data } = useQuery({
  queryKey: ['crawl', crawlId],
  queryFn: () => crawlsApi.get(crawlId),
  refetchInterval: 5000,
})
```

## WebSocket Usage

```typescript
import { useCrawlWebSocket } from '@/hooks/use-crawl-websocket'

// In crawl detail page
useCrawlWebSocket(crawlId)
// Progress auto-updates in Zustand store (useCrawlStore)
```

## Next.js Config
- `output: 'standalone'` for Docker deployment.
- API rewrites: `/api/*` and `/ws/*` proxy to `http://backend:8000`.
- No SSR for dashboard pages (all client components).

## What's NOT Built Yet
- Authentication/authorization
- Dark mode toggle (next-themes installed but unused)
- Project settings/editing UI
- Crawl scheduling/automation
- Report generation pages
- Visualizations (D3.js force-directed graphs)
- Email notifications
