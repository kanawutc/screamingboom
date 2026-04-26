import type {
  Crawl,
  CrawlComparisonResponse,
  CrawlCreate,
  CrawlSummary,
  CrawledUrl,
  CrawledUrlDetail,
  ComparisonChangeType,
  CursorPage,
  CustomExtractionItem,
  CustomSearchItem,
  ExternalLink,
  ExternalLinkFilterParams,
  ExtractionRule,
  ExtractionRuleCreate,
  ExtractionRuleUpdate,
  Issue,
  IssueFilterParams,
  IssueSummary,
  PageLink,
  PaginationItem,
  Project,
  ProjectCreate,
  ProjectUpdate,
  StructuredDataItem,
  UrlFilterParams,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = { ...options?.headers as Record<string, string> };
  // Only set Content-Type for requests that have a body
  if (options?.body) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
  }
  const res = await fetch(url, {
    ...options,
    headers,
  });
  if (!res.ok) {
    let errorMessage: string;
    try {
      const body = await res.json();
      errorMessage = body.detail || body.error || body.message || res.statusText;
    } catch {
      errorMessage = await res.text().catch(() => res.statusText);
    }
    throw new ApiError(res.status, errorMessage);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== null && v !== undefined && v !== ""
  );
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

export const projectsApi = {
  create: (data: ProjectCreate) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  list: (cursor?: string | null, limit = 50) =>
    request<CursorPage<Project>>(`/projects${qs({ cursor, limit })}`),

  get: (id: string) => request<Project>(`/projects/${id}`),

  update: (id: string, data: ProjectUpdate) =>
    request<Project>(`/projects/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    request<void>(`/projects/${id}`, { method: "DELETE" }),
};

export const crawlsApi = {
  start: (projectId: string, data: CrawlCreate) =>
    request<Crawl>(`/projects/${projectId}/crawls`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listAll: (cursor?: string | null, limit = 50) =>
    request<CursorPage<CrawlSummary>>(`/crawls${qs({ cursor, limit })}`),

  listForProject: (projectId: string, cursor?: string | null, limit = 50) =>
    request<CursorPage<CrawlSummary>>(
      `/projects/${projectId}/crawls${qs({ cursor, limit })}`
    ),

  get: (crawlId: string) => request<Crawl>(`/crawls/${crawlId}`),

  pause: (crawlId: string) =>
    request<{ status: string; crawl_id: string }>(`/crawls/${crawlId}/pause`, {
      method: "POST",
    }),

  resume: (crawlId: string) =>
    request<{ status: string; crawl_id: string }>(`/crawls/${crawlId}/resume`, {
      method: "POST",
    }),

  stop: (crawlId: string) =>
    request<{ status: string; crawl_id: string }>(`/crawls/${crawlId}/stop`, {
      method: "POST",
    }),

  delete: (crawlId: string) =>
    request<void>(`/crawls/${crawlId}`, { method: "DELETE" }),

  continueCrawl: (crawlId: string, additionalUrls = 0) =>
    request<Crawl>(`/crawls/${crawlId}/continue`, {
      method: "POST",
      body: JSON.stringify({ additional_urls: additionalUrls }),
    }),

  compare: (
    crawlAId: string,
    crawlBId: string,
    changeType?: ComparisonChangeType | null,
    limit = 100,
    offset = 0
  ) =>
    request<CrawlComparisonResponse>(
      `/crawls/compare${qs({ crawl_a: crawlAId, crawl_b: crawlBId, change_type: changeType, limit, offset })}`
    ),
};

export const urlsApi = {
  list: (crawlId: string, params: UrlFilterParams = {}) =>
    request<CursorPage<CrawledUrl>>(
      `/crawls/${crawlId}/urls${qs({
        cursor: params.cursor,
        limit: params.limit ?? 50,
        status_code: params.status_code,
        content_type: params.content_type,
        is_indexable: params.is_indexable,
        search: params.search,
        status_code_min: params.status_code_min,
        status_code_max: params.status_code_max,
        has_issue: params.has_issue,
      })}`
    ),

  get: (crawlId: string, urlId: string) =>
    request<CrawledUrlDetail>(`/crawls/${crawlId}/urls/${urlId}`),

  inlinks: (crawlId: string, urlId: string, limit = 100) =>
    request<PageLink[]>(`/crawls/${crawlId}/urls/${urlId}/inlinks${qs({ limit })}`),

  outlinks: (crawlId: string, urlId: string, limit = 100) =>
    request<PageLink[]>(`/crawls/${crawlId}/urls/${urlId}/outlinks${qs({ limit })}`),

  exportCsv: (crawlId: string) =>
    `${API_BASE}/crawls/${crawlId}/export`,

  sitemapXml: (crawlId: string) =>
    `${API_BASE}/crawls/${crawlId}/sitemap.xml`,

  exportXlsx: (crawlId: string) =>
    `${API_BASE}/crawls/${crawlId}/export-xlsx`,

  externalLinks: (crawlId: string, params: ExternalLinkFilterParams = {}) =>
    request<CursorPage<ExternalLink>>(
      `/crawls/${crawlId}/external-links${qs({
        cursor: params.cursor,
        limit: params.limit ?? 50,
        search: params.search,
        nofollow: params.nofollow,
      })}`
    ),

  structuredData: (crawlId: string, cursor?: string | null, limit = 50) =>
    request<{ items: StructuredDataItem[]; next_cursor: string | null }>(
      `/crawls/${crawlId}/structured-data${qs({ cursor, limit })}`
    ),

  customExtractions: (crawlId: string, limit = 100) =>
    request<CustomExtractionItem[]>(
      `/crawls/${crawlId}/extractions${qs({ limit })}`
    ),

  pagination: (crawlId: string, filter?: string | null, cursor?: string | null, limit = 50) =>
    request<{ items: PaginationItem[]; next_cursor: string | null }>(
      `/crawls/${crawlId}/pagination${qs({ filter, cursor, limit })}`
    ),

  customSearches: (crawlId: string, limit = 100) =>
    request<CustomSearchItem[]>(
      `/crawls/${crawlId}/search-results${qs({ limit })}`
    ),

  linksAnalysis: (crawlId: string, limit = 50) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/links/analysis${qs({ limit })}`),

  duplicates: (crawlId: string) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/duplicates`),

  linkScores: (crawlId: string, limit = 100) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any[]>(`/crawls/${crawlId}/link-scores${qs({ limit })}`),

  contentAnalysis: (crawlId: string, limit = 100) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any[]>(`/crawls/${crawlId}/content-analysis${qs({ limit })}`),

  redirectChains: (crawlId: string, limit = 200) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any[]>(`/crawls/${crawlId}/redirects${qs({ limit })}`),

  healthScore: (crawlId: string) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/health`),

  performance: (crawlId: string, limit = 50) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/performance${qs({ limit })}`),

  cookiesAudit: (crawlId: string, limit = 200) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any[]>(`/crawls/${crawlId}/cookies${qs({ limit })}`),

  securityOverview: (crawlId: string) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/security`),

  hreflang: (crawlId: string, limit = 200) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any[]>(`/crawls/${crawlId}/hreflang${qs({ limit })}`),

  robotsTxt: (crawlId: string) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/robots-txt`),

  sitemapAnalysis: (crawlId: string) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/sitemap-analysis`),

  siteStructure: (crawlId: string, maxNodes = 500) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/site-structure${qs({ max_nodes: maxNodes })}`),

  imagesAudit: (crawlId: string, limit = 500) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/images-audit${qs({ limit })}`),

  overviewStats: (crawlId: string) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>(`/crawls/${crawlId}/overview-stats`),

  headingHierarchy: (crawlId: string, limit = 200) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any[]>(`/crawls/${crawlId}/heading-hierarchy${qs({ limit })}`),
};

export const extractionRulesApi = {
  list: (projectId: string) =>
    request<ExtractionRule[]>(`/projects/${projectId}/extraction-rules`),

  create: (projectId: string, data: ExtractionRuleCreate) =>
    request<ExtractionRule>(`/projects/${projectId}/extraction-rules`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (projectId: string, ruleId: string, data: ExtractionRuleUpdate) =>
    request<ExtractionRule>(`/projects/${projectId}/extraction-rules/${ruleId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (projectId: string, ruleId: string) =>
    request<void>(`/projects/${projectId}/extraction-rules/${ruleId}`, {
      method: "DELETE",
    }),
};

export const issuesApi = {
  list: (crawlId: string, params: IssueFilterParams = {}) =>
    request<CursorPage<Issue>>(
      `/crawls/${crawlId}/issues${qs({
        cursor: params.cursor,
        limit: params.limit ?? 50,
        severity: params.severity,
        category: params.category,
        issue_type: params.issue_type,
      })}`
    ),

  summary: (crawlId: string) =>
    request<IssueSummary>(`/crawls/${crawlId}/issues/summary`),
};

export const healthApi = {
  check: () => request<{ status: string }>("/health"),
};

export function getCrawlWsUrl(crawlId: string): string {
  if (typeof window === "undefined") return "";

  // If API_BASE is an absolute URL (e.g. http://localhost:8000/api/v1), derive WS from it
  if (API_BASE.startsWith("http://") || API_BASE.startsWith("https://")) {
    const url = new URL(API_BASE);
    const wsProto = url.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${url.host}${url.pathname}/crawls/${crawlId}/ws`;
  }

  // Relative API_BASE — use current page host
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${API_BASE}/crawls/${crawlId}/ws`;
}

export { ApiError };
