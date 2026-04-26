// ─── Enums ───────────────────────────────────────────────────────────
export type CrawlStatus =
  | "idle"
  | "configuring"
  | "queued"
  | "crawling"
  | "paused"
  | "completing"
  | "completed"
  | "failed"
  | "cancelled";

export type CrawlMode = "spider" | "list";

export type IssueSeverity = "critical" | "warning" | "info" | "opportunity";

// ─── Custom Rules ────────────────────────────────────────────────────
export type ExtractionMethod = "xpath" | "css" | "regex";
export type ExtractType = "text" | "html" | "inner_html" | "attribute";

export interface CustomExtractorCreate {
  name: string;
  method: ExtractionMethod;
  selector: string;
  extract_type?: ExtractType;
  attribute_name?: string | null;
}

export interface CustomSearchCreate {
  name: string;
  pattern: string;
  is_regex?: boolean;
  case_sensitive?: boolean;
  contains?: boolean;
}

// ─── Pagination ──────────────────────────────────────────────────────
export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  total_count?: number | null;
}

// ─── Project ─────────────────────────────────────────────────────────
export interface Project {
  id: string;
  name: string;
  domain: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  domain: string;
  settings?: Record<string, unknown>;
}

export interface ProjectUpdate {
  name?: string;
  domain?: string;
  settings?: Record<string, unknown>;
}

// ─── Crawl Config ────────────────────────────────────────────────────
export interface CrawlConfig {
  max_urls: number;
  max_depth: number;
  max_threads: number;
  rate_limit_rps: number;
  user_agent: string;
  respect_robots: boolean;
  include_patterns: string[];
  exclude_patterns: string[];
  url_rewrites: { pattern: string; replacement: string }[];
  strip_query_params: string[];
  render_js: boolean;
}

export const DEFAULT_CRAWL_CONFIG: CrawlConfig = {
  max_urls: 10000,
  max_depth: 10,
  max_threads: 5,
  rate_limit_rps: 2.0,
  user_agent: "SEOSpider/1.0",
  respect_robots: true,
  include_patterns: [],
  exclude_patterns: [],
  url_rewrites: [],
  strip_query_params: [],
  render_js: false,
};

// ─── Crawl ───────────────────────────────────────────────────────────
export interface Crawl {
  id: string;
  project_id: string;
  status: CrawlStatus;
  mode: CrawlMode;
  config: CrawlConfig;
  started_at: string | null;
  completed_at: string | null;
  total_urls: number;
  crawled_urls_count: number;
  error_count: number;
  created_at: string;
}

export interface CrawlSummary {
  id: string;
  project_id: string;
  status: CrawlStatus;
  mode: CrawlMode;
  config: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  total_urls: number;
  crawled_urls_count: number;
  error_count: number;
  created_at: string;
}

export interface CrawlCreate {
  start_url: string;
  mode: CrawlMode;
  urls?: string[];
  config?: Partial<CrawlConfig>;
  custom_extractors?: CustomExtractorCreate[];
  custom_searches?: CustomSearchCreate[];
}

// ─── Crawled URL ─────────────────────────────────────────────────────
export interface CrawledUrl {
  id: string;
  crawl_id: string;
  url: string;
  status_code: number | null;
  content_type: string | null;
  title: string | null;
  title_length: number | null;
  title_pixel_width: number | null;
  meta_description: string | null;
  meta_desc_length: number | null;
  h1: string[] | null;
  h2: string[] | null;
  canonical_url: string | null;
  robots_meta: string[] | null;
  is_indexable: boolean;
  indexability_reason: string | null;
  word_count: number | null;
  crawl_depth: number;
  response_time_ms: number | null;
  redirect_url: string | null;
  link_score: number | null;
  text_ratio: number | null;
  readability_score: number | null;
  avg_words_per_sentence: number | null;
  crawled_at: string;
}

export interface CrawledUrlDetail extends CrawledUrl {
  redirect_chain: string[] | null;
  seo_data: Record<string, unknown>;
}

// ─── Links ───────────────────────────────────────────────────────────
export interface PageLink {
  source_url?: string;
  target_url?: string;
  anchor_text: string | null;
  link_type: string;
  rel_attrs: string[];
  link_position: string | null;
  is_javascript: boolean;
}

export interface ExternalLink {
  id: number;
  target_url: string;
  source_url: string;
  source_url_id: string;
  anchor_text: string | null;
  rel_attrs: string[];
  link_position: string | null;
  is_javascript: boolean;
}

export interface ExternalLinkFilterParams {
  cursor?: string | null;
  limit?: number;
  search?: string;
  nofollow?: boolean;
}

// ─── WebSocket Messages ──────────────────────────────────────────────
export interface WsProgressMessage {
  type: "progress";
  crawl_id: string;
  crawled_count: number;
  error_count: number;
  urls_in_frontier?: number;
  elapsed_seconds: number;
  paused: boolean;
}

export interface WsStatusChangeMessage {
  type: "status_change";
  crawl_id: string;
  status: CrawlStatus;
  crawled_count: number;
  error_count: number;
  error?: string;
}

export interface WsPingMessage {
  type: "ping";
}

export type WsMessage = WsProgressMessage | WsStatusChangeMessage | WsPingMessage;

// ─── URL Filter Params ───────────────────────────────────────────────
export interface UrlFilterParams {
  cursor?: string | null;
  limit?: number;
  status_code?: number | null;
  content_type?: string | null;
  is_indexable?: boolean | null;
  search?: string | null;
  status_code_min?: number | null;
  status_code_max?: number | null;
  has_issue?: string | null;
}

// ─── Issues ──────────────────────────────────────────────────────────
export interface Issue {
  id: string;
  crawl_id: string;
  url_id: string;
  url: string;
  issue_type: string;
  severity: IssueSeverity;
  category: string;
  description: string;
  details: Record<string, unknown>;
}

export interface IssueSummary {
  total: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
}

export interface IssueFilterParams {
  cursor?: string | null;
  limit?: number;
  severity?: string | null;
  category?: string | null;
  issue_type?: string | null;
}

// ─── Structured Data ─────────────────────────────────────────────────
export interface StructuredDataBlock {
  type: string;
  data: Record<string, unknown>;
  issues: { level: "error" | "warning"; message: string }[];
  is_valid: boolean;
}

export interface StructuredDataItem {
  url_id: string;
  url: string;
  blocks: StructuredDataBlock[];
  block_count: number;
  has_errors: boolean;
}

// ─── Custom Extraction Rules ─────────────────────────────────────────
export interface ExtractionRule {
  id: string;
  project_id: string;
  name: string;
  selector: string;
  selector_type: "css" | "xpath";
  extract_type: "text" | "html" | "attribute" | "count";
  attribute_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtractionRuleCreate {
  name: string;
  selector: string;
  selector_type: "css" | "xpath";
  extract_type: "text" | "html" | "attribute" | "count";
  attribute_name?: string | null;
}

export interface ExtractionRuleUpdate {
  name?: string;
  selector?: string;
  selector_type?: "css" | "xpath";
  extract_type?: "text" | "html" | "attribute" | "count";
  attribute_name?: string | null;
}

export interface CustomExtractionItem {
  url_id: string;
  url: string;
  extractions: Record<string, string | number | boolean | null>;
}

export interface PaginationItem {
  url_id: string;
  url: string;
  status_code: number | null;
  rel_next: string | null;
  rel_prev: string | null;
  is_indexable: boolean;
  indexability_reason: string | null;
}

export interface CustomSearchItem {
  url_id: string;
  url: string;
  search_results: Record<string, number>;
}

// ─── Crawl Comparison ────────────────────────────────────────────────
export interface CrawlComparisonUrl {
  url: string;
  change_type: "added" | "removed" | "changed" | "unchanged";
  a_status_code: number | null;
  a_title: string | null;
  a_word_count: number | null;
  a_response_time_ms: number | null;
  a_is_indexable: boolean | null;
  b_status_code: number | null;
  b_title: string | null;
  b_word_count: number | null;
  b_response_time_ms: number | null;
  b_is_indexable: boolean | null;
}

export interface CrawlComparisonSummary {
  total_urls_a: number;
  total_urls_b: number;
  added: number;
  removed: number;
  changed: number;
  unchanged: number;
}

export interface CrawlComparisonResponse {
  crawl_a_id: string;
  crawl_b_id: string;
  summary: CrawlComparisonSummary;
  urls: CrawlComparisonUrl[];
  total_count: number;
}

export type ComparisonChangeType = "added" | "removed" | "changed" | "unchanged";

// ─── Schedules ──────────────────────────────────────────────────────
export interface ScheduleCrawlConfig {
  start_url?: string | null;
  max_urls?: number;
  max_depth?: number;
  max_threads?: number;
  rate_limit_rps?: number;
  user_agent?: string;
  respect_robots?: boolean;
  include_patterns?: string[];
  exclude_patterns?: string[];
}

export interface ScheduleCreate {
  name: string;
  cron_expression: string;
  crawl_config?: ScheduleCrawlConfig;
  is_active?: boolean;
}

export interface ScheduleUpdate {
  name?: string;
  cron_expression?: string;
  crawl_config?: ScheduleCrawlConfig;
  is_active?: boolean;
}

export interface CrawlSchedule {
  id: string;
  project_id: string;
  name: string;
  cron_expression: string;
  crawl_config: ScheduleCrawlConfig;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  last_crawl_id: string | null;
  created_at: string;
  updated_at: string;
}
