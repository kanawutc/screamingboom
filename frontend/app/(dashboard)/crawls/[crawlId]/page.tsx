"use client";

import React, { use, useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/crawl/StatusBadge";
import { crawlsApi, urlsApi, issuesApi } from "@/lib/api-client";
import SerpPreview from "@/components/crawl/SerpPreview";
import { useCrawlWebSocket } from "@/hooks/use-crawl-websocket";
import { useCrawlStore } from "@/stores/crawl-store";
import type { Crawl, CrawledUrl, CrawlStatus, Issue, IssueSeverity, CrawledUrlDetail, PageLink, ExternalLink as ExternalLinkData, StructuredDataItem, CustomExtractionItem, PaginationItem, CustomSearchItem } from "@/types";
import {
  Pause, Play, Square, Trash2, ArrowLeft, ExternalLink as ExternalLinkIcon, Globe,
  FileText, AlertTriangle, Hash, Type, Heading1, Heading2, Image,
  X, Download, Search, Link2, Shield, Navigation, FileCode2, Sheet, Braces,
  FastForward, Network, Copy, Cookie, Lock, Languages, Timer, Bot, Map, LayoutDashboard,
} from "lucide-react";
import Link from "next/link";

const ACTIVE_STATUSES: CrawlStatus[] = ["queued", "crawling", "paused", "completing"];
const ALL_VALUE = "__all__";

function isActive(s: CrawlStatus) { return ACTIVE_STATUSES.includes(s); }

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const min = Math.floor(seconds / 60);
  const sec = Math.floor(seconds % 60);
  return `${min}m ${sec}s`;
}

function truncateUrl(url: string, maxLen = 80): string {
  return url.length <= maxLen ? url : url.slice(0, maxLen) + "\u2026";
}

type TabKey = "overview" | "internal" | "external" | "response_codes" | "redirects" | "page_titles" | "meta_desc" | "h1" | "h2" | "images" | "canonicals" | "directives" | "structured_data" | "custom_extraction" | "pagination" | "custom_search" | "content" | "performance" | "cookies" | "security" | "hreflang" | "links_analysis" | "duplicates" | "robots_txt" | "sitemaps" | "issues";

interface TabDef { key: TabKey; label: string; icon: React.ReactNode; }

const TABS: TabDef[] = [
  { key: "overview", label: "Overview", icon: <LayoutDashboard className="h-3 w-3" /> },
  { key: "internal", label: "Internal", icon: <Globe className="h-3 w-3" /> },
  { key: "external", label: "External", icon: <ExternalLinkIcon className="h-3 w-3" /> },
  { key: "response_codes", label: "Response Codes", icon: <Hash className="h-3 w-3" /> },
  { key: "redirects", label: "Redirects", icon: <Navigation className="h-3 w-3" /> },
  { key: "page_titles", label: "Page Titles", icon: <Type className="h-3 w-3" /> },
  { key: "meta_desc", label: "Meta Description", icon: <FileText className="h-3 w-3" /> },
  { key: "h1", label: "H1", icon: <Heading1 className="h-3 w-3" /> },
  { key: "h2", label: "H2", icon: <Heading2 className="h-3 w-3" /> },
  { key: "images", label: "Images", icon: <Image className="h-3 w-3" /> },
  { key: "canonicals", label: "Canonicals", icon: <Link2 className="h-3 w-3" /> },
  { key: "directives", label: "Directives", icon: <Shield className="h-3 w-3" /> },
  { key: "structured_data", label: "Structured Data", icon: <FileCode2 className="h-3 w-3" /> },
  { key: "custom_extraction", label: "Custom Extraction", icon: <Braces className="h-3 w-3" /> },
  { key: "pagination", label: "Pagination", icon: <Navigation className="h-3 w-3" /> },
  { key: "custom_search", label: "Custom Search", icon: <Search className="h-3 w-3" /> },
  { key: "content", label: "Content", icon: <FileText className="h-3 w-3" /> },
  { key: "performance", label: "Performance", icon: <Timer className="h-3 w-3" /> },
  { key: "cookies", label: "Cookies", icon: <Cookie className="h-3 w-3" /> },
  { key: "security", label: "Security", icon: <Lock className="h-3 w-3" /> },
  { key: "hreflang", label: "Hreflang", icon: <Languages className="h-3 w-3" /> },
  { key: "links_analysis", label: "Links", icon: <Network className="h-3 w-3" /> },
  { key: "duplicates", label: "Duplicates", icon: <Copy className="h-3 w-3" /> },
  { key: "robots_txt", label: "Robots.txt", icon: <Bot className="h-3 w-3" /> },
  { key: "sitemaps", label: "Sitemaps", icon: <Map className="h-3 w-3" /> },
  { key: "issues", label: "Issues", icon: <AlertTriangle className="h-3 w-3" /> },
];

interface SubFilter {
  label: string;
  filter: Record<string, string | number | undefined>;
}

const SUB_FILTERS: Record<TabKey, SubFilter[]> = {
  overview: [
    { label: "All", filter: {} },
  ],
  internal: [
    { label: "All", filter: {} },
    { label: "HTML", filter: { content_type: "text/html" } },
    { label: "JavaScript", filter: { content_type: "javascript" } },
    { label: "CSS", filter: { content_type: "css" } },
    { label: "Images", filter: { content_type: "image/" } },
    { label: "Other", filter: { content_type: "other" } },
  ],
  external: [
    { label: "All", filter: {} },
    { label: "Follow", filter: { nofollow: "false" } },
    { label: "Nofollow", filter: { nofollow: "true" } },
  ],
  response_codes: [
    { label: "All", filter: {} },
    { label: "2xx Success", filter: { status_code_min: 200, status_code_max: 299 } },
    { label: "3xx Redirect", filter: { status_code_min: 300, status_code_max: 399 } },
    { label: "4xx Client Error", filter: { status_code_min: 400, status_code_max: 499 } },
    { label: "5xx Server Error", filter: { status_code_min: 500, status_code_max: 599 } },
  ],
  redirects: [
    { label: "All", filter: {} },
  ],
  page_titles: [
    { label: "All", filter: {} },
    { label: "Missing", filter: { has_issue: "missing_title" } },
    { label: "Duplicate", filter: { has_issue: "duplicate_title" } },
    { label: "Over 60 Chars", filter: { has_issue: "title_too_long" } },
    { label: "Below 30 Chars", filter: { has_issue: "title_too_short" } },
    { label: "Same as H1", filter: { has_issue: "title_same_as_h1" } },
    { label: "Multiple", filter: { has_issue: "multiple_titles" } },
  ],
  meta_desc: [
    { label: "All", filter: {} },
    { label: "Missing", filter: { has_issue: "missing_meta_description" } },
    { label: "Duplicate", filter: { has_issue: "duplicate_meta_description" } },
    { label: "Over 155 Chars", filter: { has_issue: "meta_description_too_long" } },
    { label: "Below 70 Chars", filter: { has_issue: "meta_description_too_short" } },
    { label: "Multiple", filter: { has_issue: "multiple_meta_descriptions" } },
  ],
  h1: [
    { label: "All", filter: {} },
    { label: "Missing", filter: { has_issue: "missing_h1" } },
    { label: "Duplicate", filter: { has_issue: "duplicate_h1" } },
    { label: "Multiple", filter: { has_issue: "multiple_h1" } },
    { label: "Over 70 Chars", filter: { has_issue: "h1_too_long" } },
  ],
  h2: [
    { label: "All", filter: {} },
  ],
  images: [
    { label: "All", filter: { content_type: "image/" } },
    { label: "Missing Alt", filter: { has_issue: "missing_alt_text" } },
    { label: "Alt Too Long", filter: { has_issue: "alt_text_too_long" } },
  ],
  canonicals: [
    { label: "All", filter: {} },
    { label: "Missing", filter: { has_issue: "missing_canonical" } },
    { label: "Self-Referencing", filter: { has_issue: "self_referencing_canonical" } },
    { label: "Multiple", filter: { has_issue: "multiple_canonicals" } },
    { label: "Mismatch", filter: { has_issue: "canonical_mismatch" } },
  ],
  directives: [
    { label: "All", filter: {} },
    { label: "Noindex", filter: { has_issue: "has_noindex" } },
    { label: "Nofollow", filter: { has_issue: "has_nofollow" } },
    { label: "Noindex + Nofollow", filter: { has_issue: "has_noindex_nofollow" } },
    { label: "Multiple Robots Meta", filter: { has_issue: "multiple_robots_meta" } },
  ],
  structured_data: [
    { label: "All", filter: {} },
  ],
  custom_extraction: [
    { label: "All", filter: {} },
  ],
  pagination: [
    { label: "Contains Pagination", filter: { pagination_filter: "contains" } },
    { label: "First Page", filter: { pagination_filter: "first_page" } },
    { label: "Paginated 2+", filter: { pagination_filter: "paginated_2_plus" } },
    { label: "URL Not In Anchor", filter: { pagination_filter: "url_not_in_anchor" } },
    { label: "Non-200", filter: { pagination_filter: "non_200" } },
    { label: "Unlinked", filter: { pagination_filter: "unlinked" } },
    { label: "Non-Indexable", filter: { pagination_filter: "non_indexable" } },
    { label: "Multiple", filter: { pagination_filter: "multiple" } },
    { label: "Loop", filter: { pagination_filter: "loop" } },
    { label: "Sequence Error", filter: { pagination_filter: "sequence_error" } },
  ],
  custom_search: [
    { label: "All", filter: {} },
  ],
  content: [
    { label: "All", filter: {} },
  ],
  performance: [
    { label: "All", filter: {} },
  ],
  cookies: [
    { label: "All", filter: {} },
  ],
  security: [
    { label: "All", filter: {} },
  ],
  hreflang: [
    { label: "All", filter: {} },
  ],
  links_analysis: [
    { label: "All", filter: {} },
  ],
  duplicates: [
    { label: "All", filter: {} },
  ],
  robots_txt: [
    { label: "All", filter: {} },
  ],
  sitemaps: [
    { label: "All", filter: {} },
  ],
  issues: [
    { label: "All", filter: {} },
    { label: "Critical", filter: { severity: "critical" } },
    { label: "Warning", filter: { severity: "warning" } },
    { label: "Info", filter: { severity: "info" } },
    { label: "Opportunity", filter: { severity: "opportunity" } },
  ],
};

function statusCodeColor(code: number | null): string {
  if (code == null) return "text-gray-400";
  if (code === 0) return "text-red-600";
  if (code >= 200 && code < 300) return "text-green-700";
  if (code >= 300 && code < 400) return "text-blue-600";
  if (code >= 400 && code < 500) return "text-orange-600";
  return "text-red-600";
}

function severityDot(severity: IssueSeverity): string {
  const map: Record<IssueSeverity, string> = { critical: "bg-red-500", warning: "bg-yellow-500", info: "bg-blue-500", opportunity: "bg-green-500" };
  return map[severity] ?? "bg-gray-400";
}

export default function CrawlDetailPage({ params }: { params: Promise<{ crawlId: string }> }) {
  const { crawlId } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [activeSubFilter, setActiveSubFilter] = useState(0);
  const [selectedUrlId, setSelectedUrlId] = useState<string | null>(null);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [urlCursor, setUrlCursor] = useState<string | null>(null);
  const [issueCursor, setIssueCursor] = useState<string | null>(null);
  const [extCursor, setExtCursor] = useState<string | null>(null);
  const [sdCursor, setSdCursor] = useState<string | null>(null);
  const [ceCursor, setCeCursor] = useState<string | null>(null);
  const [pagCursor, setPagCursor] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const { progress, liveStatus, setActiveCrawl } = useCrawlStore();

  useEffect(() => { setActiveCrawl(crawlId); return () => setActiveCrawl(null); }, [crawlId, setActiveCrawl]);

  const { data: crawl, isLoading: crawlLoading, refetch: refetchCrawl } = useQuery({
    queryKey: ["crawl", crawlId],
    queryFn: () => crawlsApi.get(crawlId),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && isActive(data.status) ? 5000 : false;
    },
  });

  const effectiveStatus = liveStatus ?? crawl?.status;
  const wsEnabled = !!effectiveStatus && isActive(effectiveStatus);

  useCrawlWebSocket(crawlId, { enabled: wsEnabled });

  useEffect(() => { if (liveStatus && !isActive(liveStatus)) refetchCrawl(); }, [liveStatus, refetchCrawl]);
  useEffect(() => { setUrlCursor(null); setExtCursor(null); setSdCursor(null); setCeCursor(null); setPagCursor(null); setActiveSubFilter(0); setSearchText(""); setSearchInput(""); }, [activeTab]);
  useEffect(() => { setUrlCursor(null); setIssueCursor(null); setExtCursor(null); setSdCursor(null); setCeCursor(null); setPagCursor(null); }, [activeSubFilter]);

  const currentSubFilters = SUB_FILTERS[activeTab];
  const currentFilter = currentSubFilters[activeSubFilter]?.filter ?? {};

  const urlQueryParams = useMemo(() => {
    const p: Record<string, string | number | boolean | null | undefined> = { cursor: urlCursor, limit: 100 };
    if (currentFilter.content_type) p.content_type = currentFilter.content_type as string;
    if (currentFilter.status_code) p.status_code = Number(currentFilter.status_code);
    if (currentFilter.status_code_min) p.status_code_min = Number(currentFilter.status_code_min);
    if (currentFilter.status_code_max) p.status_code_max = Number(currentFilter.status_code_max);
    if (currentFilter.has_issue) p.has_issue = currentFilter.has_issue as string;
    if (currentFilter.is_indexable !== undefined) p.is_indexable = currentFilter.is_indexable === "true";
    if (searchText.trim()) p.search = searchText.trim();
    return p;
  }, [urlCursor, currentFilter, searchText]);

  const { data: urlsData, isLoading: urlsLoading } = useQuery({
    queryKey: ["crawl-urls", crawlId, urlQueryParams],
    queryFn: () =>
      urlsApi.list(crawlId, {
        cursor: urlQueryParams.cursor as string | null,
        limit: urlQueryParams.limit as number,
        status_code: urlQueryParams.status_code as number | undefined,
        content_type: urlQueryParams.content_type as string | undefined,
        is_indexable: urlQueryParams.is_indexable as boolean | undefined,
        search: urlQueryParams.search as string | undefined,
        status_code_min: urlQueryParams.status_code_min as number | undefined,
        status_code_max: urlQueryParams.status_code_max as number | undefined,
        has_issue: urlQueryParams.has_issue as string | undefined,
      }),
    enabled: !!crawl && activeTab !== "overview" && activeTab !== "issues" && activeTab !== "external" && activeTab !== "structured_data" && activeTab !== "custom_extraction" && activeTab !== "pagination" && activeTab !== "custom_search" && activeTab !== "content" && activeTab !== "performance" && activeTab !== "cookies" && activeTab !== "security" && activeTab !== "hreflang" && activeTab !== "redirects" && activeTab !== "links_analysis" && activeTab !== "duplicates" && activeTab !== "robots_txt" && activeTab !== "sitemaps",
  });

  const extNofollowFilter = currentFilter.nofollow as string | undefined;
  const { data: extData, isLoading: extLoading } = useQuery({
    queryKey: ["crawl-external-links", crawlId, extCursor, extNofollowFilter, searchText],
    queryFn: () =>
      urlsApi.externalLinks(crawlId, {
        cursor: extCursor,
        limit: 100,
        search: searchText.trim() || undefined,
        nofollow: extNofollowFilter === "true" ? true : extNofollowFilter === "false" ? false : undefined,
      }),
    enabled: !!crawl && activeTab === "external",
  });

  const { data: sdData, isLoading: sdLoading } = useQuery({
    queryKey: ["crawl-structured-data", crawlId, sdCursor],
    queryFn: () => urlsApi.structuredData(crawlId, sdCursor, 50),
    enabled: !!crawl && activeTab === "structured_data",
  });

  const { data: ceData, isLoading: ceLoading } = useQuery({
    queryKey: ["crawl-custom-extractions", crawlId],
    queryFn: () => urlsApi.customExtractions(crawlId, 100),
    enabled: !!crawl && activeTab === "custom_extraction",
  });

  const pagFilterVal = (currentFilter as Record<string, string>).pagination_filter as string | undefined;
  const { data: pagData, isLoading: pagLoading } = useQuery({
    queryKey: ["crawl-pagination", crawlId, pagCursor, pagFilterVal, activeSubFilter],
    queryFn: () => urlsApi.pagination(crawlId, pagFilterVal ?? "contains", pagCursor, 100),
    enabled: !!crawl && activeTab === "pagination",
  });

  const { data: csData, isLoading: csLoading } = useQuery({
    queryKey: ["crawl-custom-searches", crawlId],
    queryFn: () => urlsApi.customSearches(crawlId, 100),
    enabled: !!crawl && activeTab === "custom_search",
  });

  const { data: issuesData, isLoading: issuesLoading } = useQuery({
    queryKey: ["crawl-issues", crawlId, issueCursor, activeSubFilter],
    queryFn: () => issuesApi.list(crawlId, { cursor: issueCursor, limit: 100, severity: currentFilter.severity as string | undefined }),
    enabled: !!crawl && activeTab === "issues",
  });

  const isTerminal = !!effectiveStatus && !isActive(effectiveStatus) && effectiveStatus !== "idle" && effectiveStatus !== "configuring";

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: linksAnalysisData, isLoading: linksLoading } = useQuery<any>({
    queryKey: ["crawl-links-analysis", crawlId],
    queryFn: () => urlsApi.linksAnalysis(crawlId),
    enabled: !!crawl && activeTab === "links_analysis" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: linkScoresData } = useQuery<any[]>({
    queryKey: ["crawl-link-scores", crawlId],
    queryFn: () => urlsApi.linkScores(crawlId),
    enabled: !!crawl && activeTab === "links_analysis" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: contentAnalysisData, isLoading: contentLoading } = useQuery<any[]>({
    queryKey: ["crawl-content-analysis", crawlId],
    queryFn: () => urlsApi.contentAnalysis(crawlId),
    enabled: !!crawl && activeTab === "content" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: redirectsData, isLoading: redirectsLoading } = useQuery<any[]>({
    queryKey: ["crawl-redirects", crawlId],
    queryFn: () => urlsApi.redirectChains(crawlId),
    enabled: !!crawl && activeTab === "redirects" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: perfData, isLoading: perfLoading } = useQuery<any>({
    queryKey: ["crawl-performance", crawlId],
    queryFn: () => urlsApi.performance(crawlId),
    enabled: !!crawl && activeTab === "performance" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: cookiesData, isLoading: cookiesLoading } = useQuery<any[]>({
    queryKey: ["crawl-cookies", crawlId],
    queryFn: () => urlsApi.cookiesAudit(crawlId),
    enabled: !!crawl && activeTab === "cookies" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: securityData, isLoading: securityLoading } = useQuery<any>({
    queryKey: ["crawl-security", crawlId],
    queryFn: () => urlsApi.securityOverview(crawlId),
    enabled: !!crawl && activeTab === "security" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: hreflangData, isLoading: hreflangLoading } = useQuery<any[]>({
    queryKey: ["crawl-hreflang", crawlId],
    queryFn: () => urlsApi.hreflang(crawlId),
    enabled: !!crawl && activeTab === "hreflang" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: duplicatesData, isLoading: duplicatesLoading } = useQuery<any>({
    queryKey: ["crawl-duplicates", crawlId],
    queryFn: () => urlsApi.duplicates(crawlId),
    enabled: !!crawl && activeTab === "duplicates" && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: robotsTxtData, isLoading: robotsLoading } = useQuery<any>({
    queryKey: ["crawl-robots-txt", crawlId],
    queryFn: () => urlsApi.robotsTxt(crawlId),
    enabled: !!crawl && activeTab === "robots_txt",
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: sitemapData, isLoading: sitemapLoading } = useQuery<any>({
    queryKey: ["crawl-sitemap-analysis", crawlId],
    queryFn: () => urlsApi.sitemapAnalysis(crawlId),
    enabled: !!crawl && activeTab === "sitemaps",
  });

  const { data: issueSummary } = useQuery({
    queryKey: ["crawl-issues-summary", crawlId],
    queryFn: () => issuesApi.summary(crawlId),
    enabled: !!crawl && isTerminal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: healthScore } = useQuery<any>({
    queryKey: ["crawl-health", crawlId],
    queryFn: () => urlsApi.healthScore(crawlId),
    enabled: !!crawl && isTerminal,
  });

  const { data: selectedUrlDetail } = useQuery({
    queryKey: ["url-detail", crawlId, selectedUrlId],
    queryFn: () => urlsApi.get(crawlId, selectedUrlId!),
    enabled: !!selectedUrlId && detailPanelOpen,
  });

  const urls = urlsData?.items ?? [];
  const urlsNextCursor = urlsData?.next_cursor ?? null;
  const issues = issuesData?.items ?? [];
  const issuesNextCursor = issuesData?.next_cursor ?? null;
  const extLinks = extData?.items ?? [];
  const extNextCursor = extData?.next_cursor ?? null;
  const sdItems = sdData?.items ?? [];
  const sdNextCursor = sdData?.next_cursor ?? null;
  const ceItems = ceData?.items ?? [];
  const ceNextCursor = ceData?.next_cursor ?? null;
  const pagItems = pagData?.items ?? [];
  const pagNextCursor = pagData?.next_cursor ?? null;
  const csItems = Array.isArray(csData) ? csData : [];

  const crawledCount = progress?.crawled_count ?? crawl?.crawled_urls_count ?? 0;
  const errorCount = progress?.error_count ?? crawl?.error_count ?? 0;
  const elapsed = progress?.elapsed_seconds ?? null;
  const maxUrls = (crawl?.config as { max_urls?: number })?.max_urls ?? 10000;
  const progressPct = maxUrls > 0 ? Math.min((crawledCount / maxUrls) * 100, 100) : 0;

  // Live URLs/sec rate tracking
  const prevProgressRef = useRef<{ count: number; time: number } | null>(null);
  const [urlsPerSec, setUrlsPerSec] = useState<number | null>(null);

  useEffect(() => {
    if (progress && isActive(effectiveStatus ?? "idle")) {
      const now = Date.now();
      const prev = prevProgressRef.current;
      if (prev && prev.count < progress.crawled_count) {
        const dt = (now - prev.time) / 1000;
        if (dt > 0.1) {
          const rate = (progress.crawled_count - prev.count) / dt;
          // Smooth with previous value to avoid jitter
          setUrlsPerSec((old) => old != null ? old * 0.3 + rate * 0.7 : rate);
        }
      }
      prevProgressRef.current = { count: progress.crawled_count, time: now };
    } else if (!isActive(effectiveStatus ?? "idle")) {
      // Crawl finished — compute final average rate
      if (crawledCount > 0 && elapsed && elapsed > 0) {
        setUrlsPerSec(crawledCount / elapsed);
      } else {
        setUrlsPerSec(null);
      }
      prevProgressRef.current = null;
    }
  }, [progress, effectiveStatus, crawledCount, elapsed]);

  const [showContinueDialog, setShowContinueDialog] = useState(false);
  const [continueAdditionalUrls, setContinueAdditionalUrls] = useState(0);

  const pauseMutation = useMutation({ mutationFn: () => crawlsApi.pause(crawlId), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["crawl", crawlId] }) });
  const resumeMutation = useMutation({ mutationFn: () => crawlsApi.resume(crawlId), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["crawl", crawlId] }) });
  const stopMutation = useMutation({ mutationFn: () => crawlsApi.stop(crawlId), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["crawl", crawlId] }) });
  const deleteMutation = useMutation({ mutationFn: () => crawlsApi.delete(crawlId), onSuccess: () => router.push("/crawls") });
  const continueMutation = useMutation({
    mutationFn: () => crawlsApi.continueCrawl(crawlId, continueAdditionalUrls),
    onSuccess: (newCrawl) => {
      setShowContinueDialog(false);
      router.push(`/crawls/${newCrawl.id}`);
    },
  });

  const refreshUrls = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["crawl-urls", crawlId] });
    queryClient.invalidateQueries({ queryKey: ["crawl-external-links", crawlId] });
  }, [queryClient, crawlId]);
  useEffect(() => { if (!wsEnabled) return; const interval = setInterval(refreshUrls, 5000); return () => clearInterval(interval); }, [wsEnabled, refreshUrls]);

  function handleRowClick(url: CrawledUrl) { setSelectedUrlId(url.id); setDetailPanelOpen(true); }
  function handleExport() { window.open(urlsApi.exportCsv(crawlId), "_blank"); }
  function handleSitemapDownload() { window.open(urlsApi.sitemapXml(crawlId), "_blank"); }
  function handleExportXlsx() { window.open(urlsApi.exportXlsx(crawlId), "_blank"); }
  function handleSearch(e: React.FormEvent) { e.preventDefault(); setSearchText(searchInput); setUrlCursor(null); }

  if (crawlLoading) return <div className="flex items-center justify-center h-full"><p className="text-sm text-gray-500">Loading crawl...</p></div>;
  if (!crawl) return <div className="flex flex-col items-center justify-center h-full gap-3"><p className="text-sm text-gray-500">Crawl not found.</p><Link href="/crawls" className="text-sm text-[#6cc04a] hover:underline">&larr; Back to Crawls</Link></div>;

  const startUrl = (crawl.config as { start_url?: string })?.start_url;
  const overviewStats = buildOverviewStats(crawl, crawledCount, errorCount, issueSummary, urlsPerSec, elapsed);

  return (
    <div className="flex flex-col h-full">
      {/* TOP BAR */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-white border-b border-gray-200 flex-shrink-0">
        <Link href="/crawls" className="text-gray-400 hover:text-gray-600 p-0.5"><ArrowLeft className="h-3.5 w-3.5" /></Link>
        <div className="flex-1 flex items-center gap-2 bg-gray-50 border border-gray-200 rounded px-2.5 py-1 text-xs">
          <Globe className="h-3 w-3 text-[#6cc04a] flex-shrink-0" />
          <span className="truncate text-gray-700 font-medium">{startUrl ?? "\u2014"}</span>
        </div>
        <StatusBadge status={effectiveStatus ?? crawl.status} />
        <button onClick={handleExport} className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-[#6cc04a]" title="Export CSV"><Download className="h-3.5 w-3.5" /></button>
        <button onClick={handleExportXlsx} className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-[#6cc04a]" title="Export Excel"><Sheet className="h-3.5 w-3.5" /></button>
        <button onClick={handleSitemapDownload} className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-[#6cc04a]" title="Download Sitemap XML"><FileCode2 className="h-3.5 w-3.5" /></button>
        <div className="flex items-center gap-1">
          {effectiveStatus === "crawling" && <button onClick={() => pauseMutation.mutate()} disabled={pauseMutation.isPending} className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-yellow-600" title="Pause"><Pause className="h-3.5 w-3.5" /></button>}
          {effectiveStatus === "paused" && <button onClick={() => resumeMutation.mutate()} disabled={resumeMutation.isPending} className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-green-600" title="Resume"><Play className="h-3.5 w-3.5" /></button>}
          {isActive(effectiveStatus ?? crawl.status) && effectiveStatus !== "queued" && <button onClick={() => stopMutation.mutate()} disabled={stopMutation.isPending} className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-red-600" title="Stop"><Square className="h-3.5 w-3.5" /></button>}
          {!isActive(effectiveStatus ?? crawl.status) && (
            <>
              <button onClick={() => setShowContinueDialog(true)} className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-[#6cc04a]" title="Continue Crawl"><FastForward className="h-3.5 w-3.5" /></button>
              {confirmDelete ? (
                <div className="flex items-center gap-1">
                  <button onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending} className="px-2 py-0.5 rounded bg-red-500 text-white text-[10px] font-semibold hover:bg-red-600">{deleteMutation.isPending ? "..." : "Confirm"}</button>
                  <button onClick={() => setConfirmDelete(false)} className="p-0.5 rounded hover:bg-gray-100 text-gray-400"><X className="h-3 w-3" /></button>
                </div>
              ) : (
                <button onClick={() => setConfirmDelete(true)} className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-red-500" title="Delete Crawl"><Trash2 className="h-3.5 w-3.5" /></button>
              )}
            </>
          )}
        </div>
      </div>

      {isActive(effectiveStatus ?? crawl.status) && <div className="h-1 bg-gray-200 flex-shrink-0"><div className="h-full bg-[#6cc04a] transition-all duration-500" style={{ width: `${progressPct}%` }} /></div>}

      {/* CONTINUE CRAWL DIALOG */}
      {showContinueDialog && (
        <div className="px-3 py-2 bg-green-50 border-b border-green-200 flex items-center gap-3 flex-shrink-0">
          <FastForward className="h-4 w-4 text-[#6cc04a] flex-shrink-0" />
          <span className="text-xs text-gray-700 font-medium">Continue crawl from uncrawled links</span>
          <label className="text-xs text-gray-500 flex items-center gap-1.5">
            Additional URLs:
            <input
              type="number"
              min={0}
              value={continueAdditionalUrls}
              onChange={(e) => setContinueAdditionalUrls(Math.max(0, parseInt(e.target.value) || 0))}
              className="w-24 px-2 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:border-[#6cc04a] focus:ring-1 focus:ring-[#6cc04a]/30"
              placeholder="0 = unlimited"
            />
          </label>
          <span className="text-[10px] text-gray-400">(0 = unlimited)</span>
          <button
            onClick={() => continueMutation.mutate()}
            disabled={continueMutation.isPending}
            className="px-3 py-1 rounded bg-[#6cc04a] text-white text-xs font-semibold hover:bg-[#5aa83e] disabled:opacity-50"
          >
            {continueMutation.isPending ? "Starting..." : "Start"}
          </button>
          <button onClick={() => setShowContinueDialog(false)} className="p-0.5 rounded hover:bg-green-100 text-gray-400"><X className="h-3 w-3" /></button>
          {continueMutation.isError && <span className="text-xs text-red-600">{(continueMutation.error as Error).message}</span>}
        </div>
      )}

      {/* TABS */}
      <div className="sf-tabs">
        {TABS.map((tab) => (
          <button key={tab.key} className={`sf-tab flex items-center gap-1.5 ${activeTab === tab.key ? "active" : ""}`} onClick={() => setActiveTab(tab.key)}>
            {tab.icon}
            {tab.label}
            {tab.key === "issues" && issueSummary && issueSummary.total > 0 && <span className="ml-1 px-1.5 py-0 rounded-full bg-red-100 text-red-700 text-[9px] font-bold">{issueSummary.total}</span>}
          </button>
        ))}
      </div>

      {/* FILTER BAR + SEARCH */}
      <div className="sf-filter-bar flex items-center gap-2">
        <div className="flex items-center gap-0 flex-1">
          {currentSubFilters.map((sf, i) => (
            <button key={i} className={`sf-filter-btn ${activeSubFilter === i ? "active" : ""}`} onClick={() => setActiveSubFilter(i)}>{sf.label}</button>
          ))}
        </div>
        {activeTab !== "issues" && (
          <form onSubmit={handleSearch} className="flex items-center gap-1">
            <div className="relative">
              <Search className="absolute left-1.5 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Filter URLs..."
                className="pl-6 pr-2 py-0.5 text-[11px] border border-gray-300 rounded w-44 focus:outline-none focus:border-[#6cc04a] focus:ring-1 focus:ring-[#6cc04a]/30"
              />
            </div>
            {searchText && (
              <button type="button" onClick={() => { setSearchText(""); setSearchInput(""); setUrlCursor(null); }} className="p-0.5 text-gray-400 hover:text-gray-600"><X className="h-3 w-3" /></button>
            )}
          </form>
        )}
      </div>

      {/* MAIN CONTENT */}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-auto">
            {activeTab === "overview" ? (
              <OverviewPanel crawl={crawl} crawledCount={crawledCount} errorCount={errorCount} issueSummary={issueSummary} healthScore={healthScore} perfData={perfData} urlsPerSec={urlsPerSec} elapsed={elapsed} isTerminal={isTerminal} />
            ) : activeTab === "issues" ? (
              <IssuesTable issues={issues} loading={issuesLoading} crawlActive={isActive(effectiveStatus ?? crawl.status)} />
            ) : activeTab === "external" ? (
              <ExternalLinksTable links={extLinks} loading={extLoading} crawlActive={isActive(effectiveStatus ?? crawl.status)} onSourceClick={(urlId) => { setSelectedUrlId(urlId); setDetailPanelOpen(true); }} />
            ) : activeTab === "structured_data" ? (
              <StructuredDataTable items={sdItems} loading={sdLoading} crawlActive={isActive(effectiveStatus ?? crawl.status)} />
            ) : activeTab === "custom_extraction" ? (
              <CustomExtractionTable items={ceItems} loading={ceLoading} crawlActive={isActive(effectiveStatus ?? crawl.status)} />
            ) : activeTab === "pagination" ? (
              <PaginationAuditTable items={pagItems} loading={pagLoading} crawlActive={isActive(effectiveStatus ?? crawl.status)} />
            ) : activeTab === "custom_search" ? (
              <CustomSearchTable items={csItems} loading={csLoading} crawlActive={isActive(effectiveStatus ?? crawl.status)} />
            ) : activeTab === "redirects" ? (
              <RedirectsPanel data={redirectsData} loading={redirectsLoading} isTerminal={isTerminal} />
            ) : activeTab === "content" ? (
              <ContentAnalysisPanel data={contentAnalysisData} loading={contentLoading} isTerminal={isTerminal} />
            ) : activeTab === "performance" ? (
              <PerformancePanel data={perfData} loading={perfLoading} isTerminal={isTerminal} />
            ) : activeTab === "cookies" ? (
              <CookiesPanel data={cookiesData} loading={cookiesLoading} isTerminal={isTerminal} />
            ) : activeTab === "security" ? (
              <SecurityPanel data={securityData} loading={securityLoading} isTerminal={isTerminal} totalPages={crawledCount} />
            ) : activeTab === "hreflang" ? (
              <HreflangPanel data={hreflangData} loading={hreflangLoading} isTerminal={isTerminal} />
            ) : activeTab === "links_analysis" ? (
              <LinksAnalysisPanel data={linksAnalysisData} loading={linksLoading} isTerminal={isTerminal} linkScores={linkScoresData} />
            ) : activeTab === "duplicates" ? (
              <DuplicatesPanel data={duplicatesData} loading={duplicatesLoading} isTerminal={isTerminal} />
            ) : activeTab === "robots_txt" ? (
              <RobotsTxtPanel data={robotsTxtData} loading={robotsLoading} />
            ) : activeTab === "sitemaps" ? (
              <SitemapPanel data={sitemapData} loading={sitemapLoading} />
            ) : (
              <UrlTable urls={urls} loading={urlsLoading} activeTab={activeTab} selectedUrlId={selectedUrlId} onRowClick={handleRowClick} crawlActive={isActive(effectiveStatus ?? crawl.status)} />
            )}
          </div>

          {/* PAGINATION */}
          <div className="flex items-center justify-between px-3 py-1 bg-white border-t border-gray-200 text-[11px] text-gray-500 flex-shrink-0">
            {activeTab === "overview" || activeTab === "robots_txt" || activeTab === "sitemaps" ? (
              <span>{crawledCount.toLocaleString()} URLs crawled{errorCount > 0 ? ` · ${errorCount} errors` : ""}</span>
            ) : activeTab === "issues" ? (
              <>
                <span>Showing {issues.length} issues</span>
                <div className="flex gap-2">
                  <button onClick={() => setIssueCursor(null)} disabled={!issueCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">First</button>
                  <button onClick={() => setIssueCursor(issuesNextCursor)} disabled={!issuesNextCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">Next &rarr;</button>
                </div>
              </>
            ) : activeTab === "external" ? (
              <>
                <span>Showing {extLinks.length} external links{searchText ? ` matching "${searchText}"` : ""}</span>
                <div className="flex gap-2">
                  <button onClick={() => setExtCursor(null)} disabled={!extCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">First</button>
                  <button onClick={() => setExtCursor(extNextCursor)} disabled={!extNextCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">Next &rarr;</button>
                </div>
              </>
            ) : activeTab === "structured_data" ? (
              <>
                <span>Showing {sdItems.length} pages with structured data</span>
                <div className="flex gap-2">
                  <button onClick={() => setSdCursor(null)} disabled={!sdCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">First</button>
                  <button onClick={() => setSdCursor(sdNextCursor)} disabled={!sdNextCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">Next &rarr;</button>
                </div>
              </>
            ) : activeTab === "custom_extraction" ? (
              <>
                <span>Showing {ceItems.length} pages with custom extractions limit 100</span>
              </>
            ) : activeTab === "custom_search" ? (
              <>
                <span>Showing {csItems.length} pages with custom searches limit 100</span>
              </>
            ) : activeTab === "pagination" ? (
              <>
                <span>Showing {pagItems.length} pages with pagination</span>
                <div className="flex gap-2">
                  <button onClick={() => setPagCursor(null)} disabled={!pagCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">First</button>
                  <button onClick={() => setPagCursor(pagNextCursor)} disabled={!pagNextCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">Next &rarr;</button>
                </div>
              </>
            ) : (
              <>
                <span>Showing {urls.length} URLs{searchText ? ` matching "${searchText}"` : ""}</span>
                <div className="flex gap-2">
                  <button onClick={() => setUrlCursor(null)} disabled={!urlCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">First</button>
                  <button onClick={() => setUrlCursor(urlsNextCursor)} disabled={!urlsNextCursor} className="px-2 py-0.5 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">Next &rarr;</button>
                </div>
              </>
            )}
          </div>

          {/* BOTTOM DETAIL PANEL */}
          {detailPanelOpen && selectedUrlId && (
            <>
              <div className="sf-resize-handle h-[3px] cursor-row-resize" />
              <BottomDetailPanel crawlId={crawlId} urlId={selectedUrlId} detail={selectedUrlDetail ?? null} onClose={() => { setDetailPanelOpen(false); setSelectedUrlId(null); }} />
            </>
          )}
        </div>

        {/* RIGHT SIDEBAR */}
        <div className="w-56 flex-shrink-0 border-l border-gray-200 bg-white overflow-y-auto">
          <div className="sf-panel-header">Overview</div>
          {/* Health Score */}
          {healthScore && (
            <div className="px-2 py-2 border-b border-gray-200 text-center">
              <div className={`text-3xl font-bold ${
                healthScore.score >= 90 ? "text-green-600" :
                healthScore.score >= 75 ? "text-blue-600" :
                healthScore.score >= 60 ? "text-amber-600" :
                "text-red-600"
              }`}>{healthScore.score}</div>
              <div className="text-[10px] text-gray-400 uppercase tracking-wide">SEO Health</div>
              <div className={`text-xs font-bold mt-0.5 ${
                healthScore.grade === "A" ? "text-green-600" :
                healthScore.grade === "B" ? "text-blue-600" :
                healthScore.grade === "C" ? "text-amber-600" :
                "text-red-600"
              }`}>Grade {healthScore.grade}</div>
              <div className="mt-1 grid grid-cols-2 gap-1 text-[9px]">
                <div className="text-gray-400">Status <span className="text-gray-600 font-medium">{healthScore.components.status_codes}</span></div>
                <div className="text-gray-400">Index <span className="text-gray-600 font-medium">{healthScore.components.indexability}</span></div>
                <div className="text-gray-400">Issues <span className="text-gray-600 font-medium">{healthScore.components.issues}</span></div>
                <div className="text-gray-400">Speed <span className="text-gray-600 font-medium">{healthScore.components.performance}</span></div>
              </div>
            </div>
          )}
          {/* SERP Preview for selected URL */}
          {selectedUrlDetail && (
            <div className="px-2 py-2 border-b border-gray-200">
              <SerpPreview
                url={selectedUrlDetail.url}
                title={selectedUrlDetail.title}
                titlePixelWidth={selectedUrlDetail.title_pixel_width}
                metaDescription={selectedUrlDetail.meta_description}
                metaDescLength={selectedUrlDetail.meta_desc_length}
              />
            </div>
          )}
          {overviewStats.map((section, si) => (
            <div key={si}>
              <div className="px-2.5 pt-2 pb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{section.title}</div>
              {section.items.map((item, ii) => (
                <div key={ii} className="sf-overview-item">
                  <span className="sf-overview-label">{item.label}</span>
                  <span className={`sf-overview-value ${item.color ?? ""}`}>{item.value}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* STATUS BAR */}
      <div className="sf-status-bar">
        <span><strong className="text-gray-700">{crawledCount.toLocaleString()}</strong> URLs crawled</span>
        <span><strong className="text-gray-700">{(crawl.total_urls ?? 0).toLocaleString()}</strong> URLs found</span>
        {urlsPerSec != null && <span><strong className="text-gray-700">{urlsPerSec < 0.1 ? urlsPerSec.toFixed(2) : urlsPerSec.toFixed(1)}</strong> URLs/sec</span>}
        {errorCount > 0 && <span className="text-red-600"><strong>{errorCount.toLocaleString()}</strong> errors</span>}
        {elapsed !== null && <span>Elapsed: {formatDuration(elapsed)}</span>}
        {isTerminal && issueSummary && <span><strong className="text-gray-700">{issueSummary.total}</strong> issues</span>}
        <span className="ml-auto text-[10px] text-gray-400">{crawl.mode === "spider" ? "Spider Mode" : "List Mode"} &middot; {maxUrls === 0 ? "Unlimited" : `Max ${maxUrls.toLocaleString()}`}</span>
      </div>
    </div>
  );
}

function UrlTable({ urls, loading, activeTab, selectedUrlId, onRowClick, crawlActive }: {
  urls: CrawledUrl[]; loading: boolean; activeTab: TabKey; selectedUrlId: string | null; onRowClick: (url: CrawledUrl) => void; crawlActive: boolean;
}) {
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading URLs...</div>;
  if (urls.length === 0) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">{crawlActive ? "Crawl in progress \u2014 URLs will appear shortly..." : "No URLs found matching filters."}</div>;

  const columns = getColumnsForTab(activeTab);
  return (
    <table className="sf-table w-full">
      <thead><tr>{columns.map((col) => <th key={col.key} className={col.align === "right" ? "text-right" : "text-left"} style={col.width ? { width: col.width } : undefined}>{col.label}</th>)}</tr></thead>
      <tbody>
        {urls.map((url) => (
          <tr key={url.id} className={`cursor-pointer ${selectedUrlId === url.id ? "selected" : ""}`} onClick={() => onRowClick(url)}>
            {columns.map((col) => <td key={col.key} className={col.align === "right" ? "text-right" : ""}>{col.render(url)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface ColDef { key: string; label: string; width?: string; align?: "left" | "right"; render: (url: CrawledUrl) => React.ReactNode; }

function getColumnsForTab(tab: TabKey): ColDef[] {
  const addressCol: ColDef = {
    key: "address", label: "Address", width: "35%", render: (url) => (
      <div className="flex items-center gap-1">
        <span className="truncate" title={url.url}>{truncateUrl(url.url)}</span>
        <a href={url.url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 text-gray-300 hover:text-gray-600" onClick={(e) => e.stopPropagation()}><ExternalLinkIcon className="h-2.5 w-2.5" /></a>
      </div>
    )
  };
  const statusCol: ColDef = { key: "status", label: "Status Code", width: "80px", align: "right", render: (url) => <span className={`font-mono font-semibold ${statusCodeColor(url.status_code)}`}>{url.status_code ?? "\u2014"}</span> };
  const contentTypeCol: ColDef = { key: "content_type", label: "Content Type", width: "130px", render: (url) => <span className="text-gray-500">{url.content_type?.split(";")[0] ?? "\u2014"}</span> };
  const titleCol: ColDef = { key: "title", label: "Title 1", width: "25%", render: (url) => <span className="text-gray-700" title={url.title ?? ""}>{url.title ?? "\u2014"}</span> };
  const titleLenCol: ColDef = { key: "title_len", label: "Title Len", width: "70px", align: "right", render: (url) => <span className="text-gray-500">{url.title_length ?? "\u2014"}</span> };
  const titlePxCol: ColDef = { key: "title_px", label: "Title Px", width: "70px", align: "right", render: (url) => <span className="text-gray-500">{url.title_pixel_width ? `${url.title_pixel_width}px` : "\u2014"}</span> };
  const metaDescCol: ColDef = { key: "meta_desc", label: "Meta Description 1", width: "25%", render: (url) => <span className="text-gray-500" title={url.meta_description ?? ""}>{url.meta_description ?? "\u2014"}</span> };
  const metaDescLenCol: ColDef = { key: "meta_desc_len", label: "Meta Len", width: "70px", align: "right", render: (url) => <span className="text-gray-500">{url.meta_desc_length ?? "\u2014"}</span> };
  const h1Col: ColDef = { key: "h1_val", label: "H1-1", width: "25%", render: (url) => <span className="text-gray-700">{url.h1?.[0] ?? "\u2014"}</span> };
  const h1LenCol: ColDef = { key: "h1_len", label: "H1 Len", width: "60px", align: "right", render: (url) => <span className="text-gray-500">{url.h1?.[0] ? url.h1[0].length : "\u2014"}</span> };
  const h1CountCol: ColDef = { key: "h1_count", label: "H1 Count", width: "65px", align: "right", render: (url) => <span className="text-gray-500">{url.h1?.length ?? 0}</span> };
  const h2Col: ColDef = { key: "h2_val", label: "H2-1", width: "25%", render: (url) => <span className="text-gray-700">{url.h2?.[0] ?? "\u2014"}</span> };
  const h2LenCol: ColDef = { key: "h2_len", label: "H2 Len", width: "60px", align: "right", render: (url) => <span className="text-gray-500">{url.h2?.[0] ? url.h2[0].length : "\u2014"}</span> };
  const h2CountCol: ColDef = { key: "h2_count", label: "H2 Count", width: "65px", align: "right", render: (url) => <span className="text-gray-500">{url.h2?.length ?? 0}</span> };
  const canonicalCol: ColDef = { key: "canonical", label: "Canonical Link Element", width: "30%", render: (url) => <span className="text-gray-600 truncate block" title={url.canonical_url ?? ""}>{url.canonical_url ?? "\u2014"}</span> };
  const robotsCol: ColDef = { key: "robots", label: "Meta Robots", width: "20%", render: (url) => <span className="text-gray-600">{url.robots_meta?.join(", ") ?? "\u2014"}</span> };
  const indexableCol: ColDef = { key: "indexable", label: "Indexability", width: "85px", render: (url) => <span className={url.is_indexable ? "text-green-700 font-medium" : "text-gray-400"}>{url.is_indexable ? "Indexable" : "Non-Indexable"}</span> };
  const indexReasonCol: ColDef = { key: "idx_reason", label: "Indexability Status", width: "120px", render: (url) => <span className="text-gray-500">{url.indexability_reason ?? "\u2014"}</span> };
  const depthCol: ColDef = { key: "depth", label: "Depth", width: "55px", align: "right", render: (url) => <span className="text-gray-500">{url.crawl_depth}</span> };
  const wordCountCol: ColDef = { key: "word_count", label: "Word Count", width: "80px", align: "right", render: (url) => <span className="text-gray-500">{url.word_count ?? "\u2014"}</span> };
  const responseTimeCol: ColDef = { key: "response_time", label: "Resp. Time", width: "80px", align: "right", render: (url) => <span className="text-gray-500">{url.response_time_ms != null ? `${url.response_time_ms}ms` : "\u2014"}</span> };

  switch (tab) {
    case "internal": return [addressCol, statusCol, contentTypeCol, titleCol, indexableCol, depthCol, wordCountCol, responseTimeCol];
    case "response_codes": return [addressCol, statusCol, contentTypeCol, indexableCol, { ...responseTimeCol, width: "90px" }, { key: "redirect", label: "Redirect URI", width: "20%", render: (url) => <span className="text-blue-600 truncate block">{url.redirect_url ?? "\u2014"}</span> }];
    case "page_titles": return [addressCol, statusCol, titleCol, titleLenCol, titlePxCol, indexableCol];
    case "meta_desc": return [addressCol, statusCol, metaDescCol, metaDescLenCol, indexableCol];
    case "h1": return [addressCol, statusCol, h1Col, h1LenCol, h1CountCol, indexableCol];
    case "h2": return [addressCol, statusCol, h2Col, h2LenCol, h2CountCol, indexableCol];
    case "images": return [addressCol, statusCol, contentTypeCol, responseTimeCol];
    case "canonicals": return [addressCol, statusCol, canonicalCol, indexableCol, indexReasonCol];
    case "directives": return [addressCol, robotsCol, indexableCol, indexReasonCol, statusCol];
    default: return [addressCol, statusCol, contentTypeCol, titleCol, indexableCol, depthCol, responseTimeCol];
  }
}

function IssuesTable({ issues, loading, crawlActive }: { issues: Issue[]; loading: boolean; crawlActive: boolean; }) {
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading issues...</div>;
  if (issues.length === 0) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">{crawlActive ? "Issues appear after crawl analysis completes..." : "No issues found \u2014 great job!"}</div>;
  return (
    <table className="sf-table w-full">
      <thead><tr><th style={{ width: "35%" }}>URL</th><th style={{ width: "15%" }}>Issue Type</th><th style={{ width: "80px" }}>Severity</th><th style={{ width: "12%" }}>Category</th><th>Description</th></tr></thead>
      <tbody>
        {issues.map((issue) => (
          <tr key={issue.id}>
            <td><span className="truncate block" title={issue.url}>{truncateUrl(issue.url)}</span></td>
            <td className="text-gray-600">{issue.issue_type.replace(/_/g, " ")}</td>
            <td><span className="inline-flex items-center gap-1.5"><span className={`inline-block h-2 w-2 rounded-full ${severityDot(issue.severity)}`} /><span className="capitalize text-gray-600">{issue.severity}</span></span></td>
            <td className="text-gray-500 capitalize">{issue.category.replace(/_/g, " ")}</td>
            <td className="text-gray-500">{issue.description}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ExternalLinksTable({ links, loading, crawlActive, onSourceClick }: {
  links: ExternalLinkData[]; loading: boolean; crawlActive: boolean; onSourceClick: (urlId: string) => void;
}) {
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading external links...</div>;
  if (links.length === 0) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">{crawlActive ? "Crawl in progress \u2014 external links will appear shortly..." : "No external links found."}</div>;
  return (
    <table className="sf-table w-full">
      <thead><tr>
        <th style={{ width: "35%" }}>Target URL</th>
        <th style={{ width: "25%" }}>Source Page</th>
        <th style={{ width: "20%" }}>Anchor Text</th>
        <th style={{ width: "8%" }}>Follow</th>
        <th style={{ width: "7%" }}>Position</th>
        <th style={{ width: "5%" }}>JS</th>
      </tr></thead>
      <tbody>
        {links.map((link) => (
          <tr key={link.id}>
            <td>
              <div className="flex items-center gap-1">
                <a href={link.target_url} target="_blank" rel="noopener noreferrer" className="truncate text-blue-600 hover:underline" title={link.target_url}>{truncateUrl(link.target_url, 60)}</a>
                <ExternalLinkIcon className="h-2.5 w-2.5 flex-shrink-0 text-gray-300" />
              </div>
            </td>
            <td>
              <button className="truncate block text-gray-700 hover:text-[#6cc04a] hover:underline text-left" title={link.source_url} onClick={() => onSourceClick(link.source_url_id)}>{truncateUrl(link.source_url, 45)}</button>
            </td>
            <td className="text-gray-600">{link.anchor_text || "\u2014"}</td>
            <td>{link.rel_attrs?.includes("nofollow") ? <span className="text-orange-600 font-medium">Nofollow</span> : <span className="text-green-700">Follow</span>}</td>
            <td className="text-gray-500 capitalize">{link.link_position ?? "\u2014"}</td>
            <td className="text-gray-500">{link.is_javascript ? "Yes" : "No"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function StructuredDataTable({ items, loading, crawlActive }: {
  items: StructuredDataItem[]; loading: boolean; crawlActive: boolean;
}) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading structured data...</div>;
  if (items.length === 0) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">{crawlActive ? "Crawl in progress — structured data will appear shortly..." : "No pages with structured data found."}</div>;

  return (
    <table className="sf-table w-full">
      <thead><tr>
        <th style={{ width: "3%" }}></th>
        <th style={{ width: "37%" }}>URL</th>
        <th style={{ width: "25%" }}>Schema Types</th>
        <th style={{ width: "10%" }} className="text-right">Blocks</th>
        <th style={{ width: "12%" }}>Validation</th>
        <th style={{ width: "13%" }}>Issues</th>
      </tr></thead>
      <tbody>
        {items.map((item) => {
          const isExpanded = expandedRow === item.url_id;
          const types = item.blocks.map(b => b.type).join(", ");
          const errorCount = item.blocks.reduce((sum, b) => sum + b.issues.filter(i => i.level === "error").length, 0);
          const warnCount = item.blocks.reduce((sum, b) => sum + b.issues.filter(i => i.level === "warning").length, 0);
          return (
            <React.Fragment key={item.url_id}>
              <tr className="cursor-pointer hover:bg-gray-50" onClick={() => setExpandedRow(isExpanded ? null : item.url_id)}>
                <td className="text-center text-gray-400 text-[10px]">{isExpanded ? "▼" : "▶"}</td>
                <td>
                  <div className="flex items-center gap-1">
                    <span className="truncate" title={item.url}>{truncateUrl(item.url, 55)}</span>
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 text-gray-300 hover:text-gray-600" onClick={(e) => e.stopPropagation()}><ExternalLinkIcon className="h-2.5 w-2.5" /></a>
                  </div>
                </td>
                <td className="text-gray-600">{types || "—"}</td>
                <td className="text-right text-gray-600">{item.block_count}</td>
                <td>
                  {item.has_errors ? (
                    <span className="inline-flex items-center gap-1 text-red-600 font-medium"><span className="inline-block h-2 w-2 rounded-full bg-red-500" />Errors</span>
                  ) : warnCount > 0 ? (
                    <span className="inline-flex items-center gap-1 text-yellow-600 font-medium"><span className="inline-block h-2 w-2 rounded-full bg-yellow-500" />Warnings</span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-green-700 font-medium"><span className="inline-block h-2 w-2 rounded-full bg-green-500" />Valid</span>
                  )}
                </td>
                <td className="text-gray-500">
                  {errorCount > 0 && <span className="text-red-600 mr-2">{errorCount} error{errorCount > 1 ? "s" : ""}</span>}
                  {warnCount > 0 && <span className="text-yellow-600">{warnCount} warning{warnCount > 1 ? "s" : ""}</span>}
                  {errorCount === 0 && warnCount === 0 && "—"}
                </td>
              </tr>
              {isExpanded && (
                <tr>
                  <td colSpan={6} className="!p-0">
                    <div className="bg-gray-50 border-t border-b border-gray-200 px-4 py-2">
                      {item.blocks.map((block, bi) => (
                        <div key={bi} className="mb-3 last:mb-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-semibold text-[11px] text-gray-800">@{block.type}</span>
                            {block.is_valid ? (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">Valid</span>
                            ) : (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">Invalid</span>
                            )}
                            <span className="text-[10px] text-gray-400">{Object.keys(block.data).length} properties</span>
                          </div>
                          {block.issues.length > 0 && (
                            <div className="ml-2 mb-1.5 space-y-0.5">
                              {block.issues.map((issue, ii) => (
                                <div key={ii} className={`text-[10px] flex items-center gap-1.5 ${issue.level === "error" ? "text-red-600" : "text-yellow-600"}`}>
                                  <span className={`inline-block h-1.5 w-1.5 rounded-full flex-shrink-0 ${issue.level === "error" ? "bg-red-500" : "bg-yellow-500"}`} />
                                  {issue.message}
                                </div>
                              ))}
                            </div>
                          )}
                          <pre className="text-[10px] text-gray-600 whitespace-pre-wrap bg-white p-2 rounded border border-gray-200 max-h-32 overflow-auto">{(() => { try { return JSON.stringify(block.data, null, 2); } catch { return "Error rendering JSON-LD"; } })()}</pre>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

function CustomExtractionTable({ items, loading, crawlActive }: {
  items: CustomExtractionItem[]; loading: boolean; crawlActive: boolean;
}) {
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading custom extractions...</div>;
  if (items.length === 0) return (
    <div className="flex flex-col items-center justify-center h-32 text-xs text-gray-400 gap-1">
      {crawlActive ? "Crawl in progress — custom extractions will appear shortly..." : (
        <>
          <span>No custom extraction results found.</span>
          <span className="text-[10px]">Configure extraction rules in your project settings, then start a new crawl.</span>
        </>
      )}
    </div>
  );

  const allKeys = Array.from(new Set(items.flatMap((item) => Object.keys(item.extractions))));

  return (
    <table className="sf-table w-full">
      <thead>
        <tr>
          <th style={{ width: "35%" }}>URL</th>
          {allKeys.map((key) => (
            <th key={key}>{key}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.url_id}>
            <td>
              <div className="flex items-center gap-1">
                <span className="truncate" title={item.url}>{truncateUrl(item.url, 55)}</span>
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 text-gray-300 hover:text-gray-600" onClick={(e) => e.stopPropagation()}>
                  <ExternalLinkIcon className="h-2.5 w-2.5" />
                </a>
              </div>
            </td>
            {allKeys.map((key) => {
              const val = item.extractions[key];
              return (
                <td key={key} className="text-gray-600">
                  {val !== null && val !== undefined ? (
                    <span title={String(val)} className="block truncate max-w-[200px]">{String(val)}</span>
                  ) : (
                    <span className="text-gray-300">—</span>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PaginationAuditTable({ items, loading, crawlActive }: {
  items: PaginationItem[]; loading: boolean; crawlActive: boolean;
}) {
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading pagination data...</div>;
  if (items.length === 0) return (
    <div className="flex flex-col items-center justify-center h-32 text-xs text-gray-400 gap-1">
      {crawlActive ? "Crawl in progress — pagination data will appear shortly..." : (
        <>
          <span>No pagination data found.</span>
          <span className="text-[10px]">Pages with rel=&quot;next&quot; or rel=&quot;prev&quot; attributes will appear here.</span>
        </>
      )}
    </div>
  );

  return (
    <table className="sf-table w-full">
      <thead>
        <tr>
          <th style={{ width: "30%" }}>URL</th>
          <th style={{ width: "7%" }}>Status</th>
          <th style={{ width: "25%" }}>rel=&quot;next&quot;</th>
          <th style={{ width: "25%" }}>rel=&quot;prev&quot;</th>
          <th style={{ width: "13%" }}>Indexable</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.url_id}>
            <td>
              <div className="flex items-center gap-1">
                <span className="truncate" title={item.url}>{truncateUrl(item.url, 50)}</span>
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 text-gray-300 hover:text-gray-600" onClick={(e) => e.stopPropagation()}>
                  <ExternalLinkIcon className="h-2.5 w-2.5" />
                </a>
              </div>
            </td>
            <td>
              <span className={statusCodeColor(item.status_code)}>{item.status_code ?? "—"}</span>
            </td>
            <td>
              {item.rel_next ? (
                <span className="truncate block max-w-[260px]" title={item.rel_next}>{item.rel_next}</span>
              ) : (
                <span className="text-gray-300">—</span>
              )}
            </td>
            <td>
              {item.rel_prev ? (
                <span className="truncate block max-w-[260px]" title={item.rel_prev}>{item.rel_prev}</span>
              ) : (
                <span className="text-gray-300">—</span>
              )}
            </td>
            <td>
              {item.is_indexable ? (
                <span className="text-green-700 text-[10px] font-medium">Yes</span>
              ) : (
                <span className="text-orange-600 text-[10px] font-medium" title={item.indexability_reason ?? undefined}>No{item.indexability_reason ? ` (${item.indexability_reason})` : ""}</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CustomSearchTable({ items, loading, crawlActive }: {
  items: CustomSearchItem[]; loading: boolean; crawlActive: boolean;
}) {
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading custom searches...</div>;
  if (items.length === 0) return (
    <div className="flex flex-col items-center justify-center h-32 text-xs text-gray-400 gap-1">
      {crawlActive ? "Crawl in progress — custom searches will appear shortly..." : (
        <>
          <span>No custom search results found.</span>
          <span className="text-[10px]">Configure search rules in your project settings, then start a new crawl.</span>
        </>
      )}
    </div>
  );

  const allKeys = Array.from(new Set(items.flatMap((item) => Object.keys(item.search_results))));

  return (
    <table className="sf-table w-full">
      <thead>
        <tr>
          <th style={{ width: "35%" }}>URL</th>
          {allKeys.map((key) => (
            <th key={key} className="text-right">{key}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.url_id}>
            <td>
              <div className="flex items-center gap-1">
                <span className="truncate" title={item.url}>{truncateUrl(item.url, 55)}</span>
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 text-gray-300 hover:text-gray-600" onClick={(e) => e.stopPropagation()}>
                  <ExternalLinkIcon className="h-2.5 w-2.5" />
                </a>
              </div>
            </td>
            {allKeys.map((key) => {
              const val = item.search_results[key];
              return (
                <td key={key} className="text-right text-gray-600">
                  {val !== null && val !== undefined ? (
                    <span className="font-medium">{val > 0 ? <span className="text-[#6cc04a]">{val} hits</span> : <span className="text-gray-400">0</span>}</span>
                  ) : (
                    <span className="text-gray-300">—</span>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type DetailTab = "url" | "seo" | "content" | "inlinks" | "outlinks" | "structured" | "headers";

function BottomDetailPanel({ crawlId, urlId, detail, onClose }: { crawlId: string; urlId: string; detail: CrawledUrlDetail | null; onClose: () => void; }) {
  const [detailTab, setDetailTab] = useState<DetailTab>("url");

  const { data: inlinks } = useQuery({
    queryKey: ["inlinks", crawlId, urlId],
    queryFn: () => urlsApi.inlinks(crawlId, urlId),
    enabled: detailTab === "inlinks",
  });

  const { data: outlinks } = useQuery({
    queryKey: ["outlinks", crawlId, urlId],
    queryFn: () => urlsApi.outlinks(crawlId, urlId),
    enabled: detailTab === "outlinks",
  });

  const seoData = detail?.seo_data ?? {};
  const tabs: { key: DetailTab; label: string }[] = [
    { key: "url", label: "URL Details" },
    { key: "seo", label: "SEO Data" },
    { key: "content", label: "Content" },
    { key: "inlinks", label: `Inlinks${inlinks ? ` (${inlinks.length})` : ""}` },
    { key: "outlinks", label: `Outlinks${outlinks ? ` (${outlinks.length})` : ""}` },
    { key: "structured", label: "Structured Data" },
    { key: "headers", label: "Response Headers" },
  ];

  return (
    <div className="h-52 flex flex-col bg-white border-t border-gray-200 flex-shrink-0 overflow-hidden">
      <div className="flex items-center justify-between px-2 bg-gray-50 border-b border-gray-200 flex-shrink-0">
        <div className="flex gap-0 overflow-x-auto">
          {tabs.map((t) => (
            <button key={t.key} className={`px-3 py-1 text-[11px] font-medium border-b-2 whitespace-nowrap ${detailTab === t.key ? "border-[#6cc04a] text-green-800 bg-white" : "border-transparent text-gray-500 hover:text-gray-700"}`} onClick={() => setDetailTab(t.key)}>{t.label}</button>
          ))}
        </div>
        <button onClick={onClose} className="p-0.5 rounded hover:bg-gray-200 text-gray-400 flex-shrink-0"><X className="h-3 w-3" /></button>
      </div>

      <div className="flex-1 overflow-auto p-2 text-[11px]">
        {!detail ? <p className="text-gray-400">Loading...</p> : detailTab === "url" ? (
          <div className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-1">
            <span className="text-gray-400 font-medium">URL</span><span className="text-gray-700 truncate">{detail.url}</span>
            <span className="text-gray-400 font-medium">Status Code</span><span className={statusCodeColor(detail.status_code)}>{detail.status_code}</span>
            <span className="text-gray-400 font-medium">Content Type</span><span className="text-gray-700">{detail.content_type ?? "\u2014"}</span>
            <span className="text-gray-400 font-medium">Response Time</span><span className="text-gray-700">{detail.response_time_ms != null ? `${detail.response_time_ms}ms` : "\u2014"}</span>
            <span className="text-gray-400 font-medium">Crawl Depth</span><span className="text-gray-700">{detail.crawl_depth}</span>
            <span className="text-gray-400 font-medium">Word Count</span><span className="text-gray-700">{detail.word_count ?? "\u2014"}</span>
            <span className="text-gray-400 font-medium">Indexable</span>
            <span className={detail.is_indexable ? "text-green-700" : "text-red-600"}>{detail.is_indexable ? "Yes" : `No${detail.indexability_reason ? ` (${detail.indexability_reason})` : ""}`}</span>
            <span className="text-gray-400 font-medium">Canonical URL</span><span className="text-gray-700 truncate">{detail.canonical_url ?? "\u2014"}</span>
            {detail.redirect_url && <><span className="text-gray-400 font-medium">Redirect URL</span><span className="text-blue-600 truncate">{detail.redirect_url}</span></>}
            {detail.redirect_chain && detail.redirect_chain.length > 0 && (
              <><span className="text-gray-400 font-medium">Redirect Chain</span>
                <div className="text-gray-600">{detail.redirect_chain.map((hop, i) => <div key={i} className="truncate">{i > 0 && <span className="text-gray-400 mr-1">&rarr;</span>}{typeof hop === "string" ? hop : JSON.stringify(hop)}</div>)}</div></>
            )}
          </div>
        ) : detailTab === "seo" ? (
          <div className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-1">
            <span className="text-gray-400 font-medium">Title</span><span className="text-gray-700">{detail.title ?? "\u2014"} {detail.title_length != null && <span className="text-gray-400 ml-1">({detail.title_length} chars{detail.title_pixel_width != null ? `, ${detail.title_pixel_width}px` : ""})</span>}</span>
            <span className="text-gray-400 font-medium">Meta Description</span><span className="text-gray-700">{detail.meta_description ?? "\u2014"} {detail.meta_desc_length != null && <span className="text-gray-400 ml-1">({detail.meta_desc_length} chars)</span>}</span>
            <span className="text-gray-400 font-medium">H1</span><span className="text-gray-700">{detail.h1?.join(" | ") ?? "\u2014"}</span>
            <span className="text-gray-400 font-medium">H2</span><span className="text-gray-700">{detail.h2?.join(" | ") ?? "\u2014"}</span>
            <span className="text-gray-400 font-medium">Robots Meta</span><span className="text-gray-700">{detail.robots_meta?.join(", ") ?? "\u2014"}</span>
            {seoData.og && typeof seoData.og === "object" && !Array.isArray(seoData.og) ? (<><span className="text-gray-400 font-medium">Open Graph</span><span className="text-gray-700">{Object.entries(seoData.og as Record<string, string>).map(([k, v]) => `${k}: ${v}`).join(" | ") || "\u2014"}</span></>) : null}
            {seoData.hreflang && Array.isArray(seoData.hreflang) && (seoData.hreflang as { lang: string; href: string }[]).length > 0 ? (
              <><span className="text-gray-400 font-medium">Hreflang</span><span className="text-gray-700">{(seoData.hreflang as { lang: string; href: string }[]).map((h) => `${h.lang}: ${h.href}`).join(" | ")}</span></>
            ) : null}
            <span className="text-gray-400 font-medium">Crawled At</span><span className="text-gray-700">{new Date(detail.crawled_at).toLocaleString()}</span>
          </div>
        ) : detailTab === "content" ? (
          <div className="space-y-3">
            {/* SERP Preview */}
            <div className="bg-white rounded border border-gray-200 p-2">
              <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1 font-bold">SERP Preview</div>
              <div className="max-w-[600px]">
                <div className="text-[13px] text-[#1a0dab] font-medium leading-tight truncate">{detail.title || detail.url}</div>
                <div className="text-[11px] text-green-800 truncate">{detail.url}</div>
                <div className="text-[11px] text-gray-600 line-clamp-2 leading-relaxed">{detail.meta_description || "No meta description"}</div>
              </div>
            </div>
            {/* Content Metrics */}
            <div className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-1">
              <span className="text-gray-400 font-medium">Word Count</span><span className="text-gray-700">{detail.word_count ?? "—"}</span>
              <span className="text-gray-400 font-medium">Link Score</span><span className="text-gray-700">{detail.link_score != null ? `${detail.link_score}/100` : "—"}</span>
              <span className="text-gray-400 font-medium">Text Ratio</span><span className="text-gray-700">{detail.text_ratio != null ? `${(detail.text_ratio * 100).toFixed(1)}%` : "—"}</span>
              <span className="text-gray-400 font-medium">Readability</span><span className={`font-medium ${(detail.readability_score ?? 0) >= 60 ? "text-green-700" : (detail.readability_score ?? 0) >= 30 ? "text-yellow-600" : "text-red-600"}`}>{detail.readability_score != null ? `${detail.readability_score.toFixed(1)} (Flesch)` : "—"}</span>
              <span className="text-gray-400 font-medium">Avg Words/Sentence</span><span className="text-gray-700">{detail.avg_words_per_sentence != null ? detail.avg_words_per_sentence.toFixed(1) : "—"}</span>
              <span className="text-gray-400 font-medium">Title Length</span><span className={`${(detail.title_length ?? 0) > 60 ? "text-red-600" : (detail.title_length ?? 0) < 30 ? "text-yellow-600" : "text-green-700"}`}>{detail.title_length != null ? `${detail.title_length} chars${detail.title_pixel_width != null ? ` / ${detail.title_pixel_width}px` : ""}` : "—"}</span>
              <span className="text-gray-400 font-medium">Meta Desc Length</span><span className={`${(detail.meta_desc_length ?? 0) > 155 ? "text-red-600" : (detail.meta_desc_length ?? 0) < 70 ? "text-yellow-600" : "text-green-700"}`}>{detail.meta_desc_length != null ? `${detail.meta_desc_length} chars` : "—"}</span>
            </div>
          </div>
        ) : detailTab === "inlinks" ? (
          <LinksTable links={inlinks ?? []} direction="inlinks" />
        ) : detailTab === "outlinks" ? (
          <LinksTable links={outlinks ?? []} direction="outlinks" />
        ) : detailTab === "structured" ? (
          <div>
            {seoData.json_ld && Array.isArray(seoData.json_ld) && (seoData.json_ld as unknown[]).length > 0 ? (
              <pre className="text-[10px] text-gray-700 whitespace-pre-wrap bg-gray-50 p-2 rounded border border-gray-200 max-h-36 overflow-auto">{(() => { try { return JSON.stringify(seoData.json_ld, null, 2); } catch { return "Error rendering JSON-LD data"; } })()}</pre>
            ) : <p className="text-gray-400">No structured data (JSON-LD) found on this page.</p>}
          </div>
        ) : detailTab === "headers" ? (
          <div className="grid grid-cols-[180px_1fr] gap-x-4 gap-y-1">
            {seoData.security_headers && typeof seoData.security_headers === "object" && !Array.isArray(seoData.security_headers) ? (
              Object.entries(seoData.security_headers as Record<string, string | null>).map(([k, v]) => (
                <React.Fragment key={k}><span className="text-gray-400 font-medium">{k.replace(/_/g, "-")}</span><span className={v ? "text-gray-700" : "text-red-400"}>{v ?? "Not set"}</span></React.Fragment>
              ))
            ) : <><span className="text-gray-400">No headers data</span><span></span></>}
            {seoData.x_robots_tag ? (<><span className="text-gray-400 font-medium">X-Robots-Tag</span><span className="text-gray-700">{String(seoData.x_robots_tag)}</span></>) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function LinksTable({ links, direction }: { links: PageLink[]; direction: "inlinks" | "outlinks" }) {
  if (links.length === 0) return <p className="text-gray-400">No {direction} found.</p>;
  return (
    <table className="sf-table w-full">
      <thead><tr>
        <th style={{ width: "45%" }}>{direction === "inlinks" ? "From" : "To"}</th>
        <th style={{ width: "25%" }}>Anchor Text</th>
        <th style={{ width: "10%" }}>Type</th>
        <th style={{ width: "10%" }}>Follow</th>
        <th style={{ width: "10%" }}>JS</th>
      </tr></thead>
      <tbody>
        {links.map((link, i) => (
          <tr key={i}>
            <td><span className="truncate block text-blue-600" title={direction === "inlinks" ? link.source_url : link.target_url}>{truncateUrl((direction === "inlinks" ? link.source_url : link.target_url) ?? "", 60)}</span></td>
            <td className="text-gray-600">{link.anchor_text || "\u2014"}</td>
            <td className="text-gray-500 capitalize">{link.link_type}</td>
            <td className="text-gray-500">{link.rel_attrs?.includes("nofollow") ? "Nofollow" : "Follow"}</td>
            <td className="text-gray-500">{link.is_javascript ? "Yes" : "No"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface OverviewSection { title: string; items: { label: string; value: string | number; color?: string }[]; }

function buildOverviewStats(
  crawl: Crawl,
  crawledCount: number,
  errorCount: number,
  issueSummary: { total: number; by_severity: Record<string, number>; by_category: Record<string, number> } | undefined,
  urlsPerSec: number | null,
  elapsed: number | null
) {
  const config = crawl.config as unknown as Record<string, unknown>;
  const sections = [
    {
      title: "Crawl",
      items: [
        { label: "Status", value: crawl.status, color: "" },
        { label: "Mode", value: crawl.mode === "spider" ? "Spider" : "List", color: "" },
        { label: "URLs Found", value: (crawl.total_urls ?? 0).toLocaleString(), color: "" },
        { label: "URLs Crawled", value: crawledCount.toLocaleString(), color: "" },
        { label: "Errors", value: errorCount.toLocaleString(), color: errorCount > 0 ? "text-red-600" : "" },
        ...(urlsPerSec != null ? [{ label: "Speed", value: `${urlsPerSec < 0.1 ? urlsPerSec.toFixed(2) : urlsPerSec.toFixed(1)} URLs/s`, color: "" }] : []),
        ...(elapsed != null ? [{ label: "Duration", value: formatDuration(elapsed), color: "" }] : []),
      ],
    },
    {
      title: "Config",
      items: [
        { label: "Max URLs", value: String(config.max_urls ?? "\u221e"), color: "" },
        { label: "Max Depth", value: String(config.max_depth ?? 10), color: "" },
        { label: "User Agent", value: ((config.user_agent as string) ?? "—").slice(0, 20), color: "" },
      ],
    },
  ];

  if (issueSummary && issueSummary.total > 0) {
    sections.push({
      title: "Issues",
      items: [
        { label: "Total", value: String(issueSummary.total), color: "" },
        ...(issueSummary.by_severity.critical ? [{ label: "Critical", value: String(issueSummary.by_severity.critical), color: "text-red-600" }] : []),
        ...(issueSummary.by_severity.warning ? [{ label: "Warning", value: String(issueSummary.by_severity.warning), color: "text-yellow-600" }] : []),
        ...(issueSummary.by_severity.info ? [{ label: "Info", value: String(issueSummary.by_severity.info), color: "text-blue-600" }] : []),
        ...(issueSummary.by_severity.opportunity ? [{ label: "Opportunity", value: String(issueSummary.by_severity.opportunity), color: "text-green-600" }] : []),
      ],
    });
  }

  sections.push({
    title: "Timestamps",
    items: [
      { label: "Created", value: new Date(crawl.created_at).toLocaleString(), color: "" },
      { label: "Started", value: crawl.started_at ? new Date(crawl.started_at).toLocaleString() : "—", color: "" },
      { label: "Completed", value: crawl.completed_at ? new Date(crawl.completed_at).toLocaleString() : "—", color: "" },
    ],
  });

  return sections;
}

// ─── Links Analysis Panel (F2.10) ─────────────────────────────────────

/* eslint-disable @typescript-eslint/no-explicit-any */
function LinksAnalysisPanel({ data, loading, isTerminal, linkScores }: { data: any; loading: boolean; isTerminal: boolean; linkScores?: any[] }) {
  if (!isTerminal) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Links analysis available after crawl completes.</div>;
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Analyzing internal links...</div>;
  if (!data) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No link data available.</div>;

  const topPages = data.top_pages_by_inlinks ?? [];
  const orphans = data.orphan_pages ?? [];
  const depthDist = data.depth_distribution ?? [];
  const anchorStats = data.anchor_text_stats ?? [];
  const maxInlinks = topPages.length > 0 ? topPages[0].inlink_count : 1;
  const scores = linkScores ?? [];

  return (
    <div className="p-4 space-y-6 overflow-auto">
      {/* Depth Distribution */}
      <div>
        <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-2">Crawl Depth Distribution</h3>
        <div className="space-y-1">
          {depthDist.map((d: any) => (
            <div key={d.crawl_depth} className="flex items-center gap-2 text-xs">
              <span className="w-16 text-gray-500 text-right">Depth {d.crawl_depth}</span>
              <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                <div
                  className="h-full bg-[#6cc04a] rounded-full transition-all"
                  style={{ width: `${Math.max((d.url_count / Math.max(...depthDist.map((x: any) => x.url_count), 1)) * 100, 2)}%` }}
                />
              </div>
              <span className="w-12 text-right text-gray-700 font-medium">{d.url_count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Top Pages by Inlinks */}
      <div>
        <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-2">Top Pages by Inlinks</h3>
        <table className="sf-table w-full">
          <thead><tr><th style={{ width: "45%" }}>URL</th><th style={{ width: "25%" }}>Title</th><th className="text-right" style={{ width: "10%" }}>Inlinks</th><th className="text-right" style={{ width: "10%" }}>Depth</th></tr></thead>
          <tbody>
            {topPages.slice(0, 20).map((p: any) => (
              <tr key={p.id}>
                <td><span className="truncate block" title={p.url}>{truncateUrl(p.url, 55)}</span></td>
                <td className="text-gray-500 truncate" title={p.title}>{p.title ?? "—"}</td>
                <td className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <div className="w-12 bg-gray-100 rounded-full h-2 overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(p.inlink_count / maxInlinks) * 100}%` }} />
                    </div>
                    <span className="font-medium text-gray-700 w-6 text-right">{p.inlink_count}</span>
                  </div>
                </td>
                <td className="text-right text-gray-500">{p.crawl_depth}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Orphan Pages */}
      {orphans.length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-orange-700 uppercase tracking-wide mb-2">⚠ Orphan Pages ({orphans.length})</h3>
          <p className="text-[10px] text-gray-400 mb-1">Pages with zero internal inlinks — search engines may struggle to discover these.</p>
          <table className="sf-table w-full">
            <thead><tr><th style={{ width: "55%" }}>URL</th><th style={{ width: "25%" }}>Title</th><th className="text-right" style={{ width: "10%" }}>Status</th><th className="text-right" style={{ width: "10%" }}>Depth</th></tr></thead>
            <tbody>
              {orphans.slice(0, 20).map((p: any) => (
                <tr key={p.id}>
                  <td><span className="truncate block" title={p.url}>{truncateUrl(p.url, 60)}</span></td>
                  <td className="text-gray-500 truncate">{p.title ?? "—"}</td>
                  <td className={`text-right font-mono ${statusCodeColor(p.status_code)}`}>{p.status_code ?? "—"}</td>
                  <td className="text-right text-gray-500">{p.crawl_depth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Link Score (PageRank) */}
      {scores.length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-2">Link Score (Internal PageRank)</h3>
          <p className="text-[10px] text-gray-400 mb-2">Higher score = more internal link equity. Scale 1-100.</p>
          <table className="sf-table w-full">
            <thead><tr><th style={{ width: "45%" }}>URL</th><th style={{ width: "25%" }}>Title</th><th className="text-right" style={{ width: "15%" }}>Score</th><th className="text-right" style={{ width: "10%" }}>Depth</th></tr></thead>
            <tbody>
              {scores.slice(0, 20).map((p: any) => (
                <tr key={p.id}>
                  <td><span className="truncate block" title={p.url}>{truncateUrl(p.url, 55)}</span></td>
                  <td className="text-gray-500 truncate" title={p.title}>{p.title ?? "—"}</td>
                  <td className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <div className="w-16 bg-gray-100 rounded-full h-2 overflow-hidden">
                        <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${p.link_score}%` }} />
                      </div>
                      <span className="font-medium text-gray-700 w-6 text-right">{p.link_score}</span>
                    </div>
                  </td>
                  <td className="text-right text-gray-500">{p.crawl_depth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Top Anchor Texts */}
      {anchorStats.length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-2">Top Anchor Texts</h3>
          <div className="flex flex-wrap gap-1.5">
            {anchorStats.slice(0, 25).map((a: any, i: number) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded-full text-[11px] text-gray-700">
                {a.anchor_text.length > 30 ? a.anchor_text.slice(0, 30) + "…" : a.anchor_text}
                <span className="text-[9px] font-bold text-gray-400">{a.frequency}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Duplicates Panel (F2.12) ─────────────────────────────────────────

function DuplicatesPanel({ data, loading, isTerminal }: { data: any; loading: boolean; isTerminal: boolean }) {
  if (!isTerminal) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Duplicate detection available after crawl completes.</div>;
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Detecting duplicates...</div>;
  if (!data) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No duplicate data available.</div>;

  const exact = data.exact_duplicates ?? [];
  const near = data.near_duplicates ?? [];

  if (exact.length === 0 && near.length === 0) {
    return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No duplicate content detected — great!</div>;
  }

  return (
    <div className="p-4 space-y-6 overflow-auto">
      {/* Exact Duplicates */}
      {exact.length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-red-700 uppercase tracking-wide mb-2">Exact Duplicates ({exact.length} groups)</h3>
          <p className="text-[10px] text-gray-400 mb-2">Pages with identical content (same MD5 hash).</p>
          {exact.map((group: any, gi: number) => (
            <div key={gi} className="mb-3 p-2 bg-red-50 border border-red-200 rounded">
              <p className="text-[10px] text-red-600 font-semibold mb-1">{group.count} identical pages</p>
              {group.urls?.map((url: string, ui: number) => (
                <div key={ui} className="text-[11px] text-gray-700 truncate" title={url}>
                  <span className="text-gray-400 mr-1">{ui + 1}.</span>
                  {truncateUrl(url, 70)}
                  {group.titles?.[ui] && <span className="ml-2 text-gray-400">— {group.titles[ui]}</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* Near Duplicates */}
      {near.length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-amber-700 uppercase tracking-wide mb-2">Near Duplicates ({near.length} groups)</h3>
          <p className="text-[10px] text-gray-400 mb-2">Pages with very similar content (~95%+ similarity via SimHash).</p>
          {near.map((group: any, gi: number) => (
            <div key={gi} className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded">
              <p className="text-[10px] text-amber-600 font-semibold mb-1">{group.count} similar pages</p>
              {group.urls?.map((item: any, ui: number) => (
                <div key={ui} className="text-[11px] text-gray-700 truncate" title={item.url}>
                  <span className="text-gray-400 mr-1">{ui + 1}.</span>
                  {truncateUrl(item.url, 70)}
                  {item.title && <span className="ml-2 text-gray-400">— {item.title}</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
function ContentAnalysisPanel({ data, loading, isTerminal }: { data: any[] | undefined; loading: boolean; isTerminal: boolean }) {
  if (!isTerminal) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Content analysis available after crawl completes.</div>;
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Analyzing content...</div>;
  if (!data || data.length === 0) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No content analysis data available.</div>;

  const readabilityColor = (score: number | null) => {
    if (score == null) return "text-gray-400";
    if (score >= 60) return "text-green-700";
    if (score >= 30) return "text-amber-600";
    return "text-red-600";
  };

  const readabilityLabel = (score: number | null) => {
    if (score == null) return "N/A";
    if (score >= 80) return "Very Easy";
    if (score >= 60) return "Easy";
    if (score >= 40) return "Standard";
    if (score >= 20) return "Difficult";
    return "Very Difficult";
  };

  const avgReadability = data.reduce((sum, d) => sum + (d.readability_score ?? 0), 0) / data.filter(d => d.readability_score != null).length || 0;
  const avgTextRatio = data.reduce((sum, d) => sum + (d.text_ratio ?? 0), 0) / data.filter(d => d.text_ratio != null).length || 0;
  const avgWordCount = data.reduce((sum, d) => sum + (d.word_count ?? 0), 0) / data.length || 0;

  return (
    <div className="overflow-auto">
      {/* Summary cards */}
      <div className="flex gap-3 p-3 border-b border-gray-200">
        <div className="flex-1 p-2 bg-blue-50 rounded border border-blue-200 text-center">
          <div className="text-[10px] text-blue-500 uppercase tracking-wide">Avg Readability</div>
          <div className={`text-lg font-bold ${readabilityColor(avgReadability)}`}>{avgReadability.toFixed(1)}</div>
          <div className="text-[10px] text-gray-500">{readabilityLabel(avgReadability)}</div>
        </div>
        <div className="flex-1 p-2 bg-green-50 rounded border border-green-200 text-center">
          <div className="text-[10px] text-green-500 uppercase tracking-wide">Avg Text Ratio</div>
          <div className="text-lg font-bold text-green-700">{(avgTextRatio * 100).toFixed(1)}%</div>
        </div>
        <div className="flex-1 p-2 bg-purple-50 rounded border border-purple-200 text-center">
          <div className="text-[10px] text-purple-500 uppercase tracking-wide">Avg Word Count</div>
          <div className="text-lg font-bold text-purple-700">{Math.round(avgWordCount)}</div>
        </div>
        <div className="flex-1 p-2 bg-gray-50 rounded border border-gray-200 text-center">
          <div className="text-[10px] text-gray-500 uppercase tracking-wide">Pages Analyzed</div>
          <div className="text-lg font-bold text-gray-700">{data.length}</div>
        </div>
      </div>

      {/* Table */}
      <table className="w-full text-[11px]">
        <thead className="bg-gray-50 sticky top-0">
          <tr className="text-left text-[10px] text-gray-500 uppercase tracking-wider">
            <th className="px-3 py-1.5 font-medium">URL</th>
            <th className="px-3 py-1.5 font-medium text-right w-24">Word Count</th>
            <th className="px-3 py-1.5 font-medium text-right w-24">Text Ratio</th>
            <th className="px-3 py-1.5 font-medium text-right w-28">Readability</th>
            <th className="px-3 py-1.5 font-medium text-right w-24">Words/Sentence</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item: any, i: number) => (
            <tr key={i} className="border-t border-gray-100 hover:bg-blue-50/40">
              <td className="px-3 py-1.5 truncate max-w-[400px]" title={item.url}>{truncateUrl(item.url, 60)}</td>
              <td className="px-3 py-1.5 text-right font-mono">{item.word_count ?? "—"}</td>
              <td className="px-3 py-1.5 text-right font-mono">{item.text_ratio != null ? `${(item.text_ratio * 100).toFixed(1)}%` : "—"}</td>
              <td className="px-3 py-1.5 text-right">
                <span className={`font-mono ${readabilityColor(item.readability_score)}`}>{item.readability_score != null ? item.readability_score.toFixed(1) : "—"}</span>
                {item.readability_score != null && <span className="ml-1 text-[9px] text-gray-400">{readabilityLabel(item.readability_score)}</span>}
              </td>
              <td className="px-3 py-1.5 text-right font-mono">{item.avg_words_per_sentence != null ? item.avg_words_per_sentence.toFixed(1) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function RedirectsPanel({ data, loading, isTerminal }: { data: any[] | undefined; loading: boolean; isTerminal: boolean }) {
  if (!isTerminal) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Redirect analysis available after crawl completes.</div>;
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Analyzing redirects...</div>;
  if (!data || data.length === 0) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No redirects found — all URLs resolved directly.</div>;

  const longChains = data.filter((r: any) => r.chain_length > 2);
  const status301 = data.filter((r: any) => r.status_code === 301);
  const status302 = data.filter((r: any) => r.status_code === 302);

  return (
    <div className="overflow-auto">
      <div className="flex gap-3 p-3 border-b border-gray-200">
        <div className="flex-1 p-2 bg-blue-50 rounded border border-blue-200 text-center">
          <div className="text-[10px] text-blue-500 uppercase tracking-wide">Total Redirects</div>
          <div className="text-lg font-bold text-blue-700">{data.length}</div>
        </div>
        <div className="flex-1 p-2 bg-green-50 rounded border border-green-200 text-center">
          <div className="text-[10px] text-green-500 uppercase tracking-wide">301 Permanent</div>
          <div className="text-lg font-bold text-green-700">{status301.length}</div>
        </div>
        <div className="flex-1 p-2 bg-amber-50 rounded border border-amber-200 text-center">
          <div className="text-[10px] text-amber-500 uppercase tracking-wide">302 Temporary</div>
          <div className="text-lg font-bold text-amber-700">{status302.length}</div>
        </div>
        <div className="flex-1 p-2 bg-red-50 rounded border border-red-200 text-center">
          <div className="text-[10px] text-red-500 uppercase tracking-wide">Long Chains ({">"}2)</div>
          <div className="text-lg font-bold text-red-700">{longChains.length}</div>
        </div>
      </div>
      <table className="w-full text-[11px]">
        <thead className="bg-gray-50 sticky top-0">
          <tr className="text-left text-[10px] text-gray-500 uppercase tracking-wider">
            <th className="px-3 py-1.5 font-medium">Source URL</th>
            <th className="px-3 py-1.5 font-medium text-center w-16">Status</th>
            <th className="px-3 py-1.5 font-medium">Destination</th>
            <th className="px-3 py-1.5 font-medium text-center w-16">Hops</th>
            <th className="px-3 py-1.5 font-medium">Chain</th>
          </tr>
        </thead>
        <tbody>
          {data.map((r: any, i: number) => (
            <tr key={i} className={`border-t border-gray-100 hover:bg-blue-50/40 ${r.chain_length > 2 ? "bg-red-50/30" : ""}`}>
              <td className="px-3 py-1.5 truncate max-w-[250px]" title={r.url}>{truncateUrl(r.url, 40)}</td>
              <td className={`px-3 py-1.5 text-center font-mono font-medium ${r.status_code === 301 ? "text-green-600" : "text-amber-600"}`}>{r.status_code}</td>
              <td className="px-3 py-1.5 truncate max-w-[250px] text-blue-600" title={r.redirect_url}>{truncateUrl(r.redirect_url || "", 40)}</td>
              <td className={`px-3 py-1.5 text-center font-mono ${r.chain_length > 2 ? "text-red-600 font-bold" : ""}`}>{r.chain_length}</td>
              <td className="px-3 py-1.5">
                {r.chain && r.chain.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-0.5">
                    {r.chain.map((hop: any, j: number) => (
                      <span key={j} className="inline-flex items-center">
                        {j > 0 && <span className="text-gray-300 mx-0.5">&rarr;</span>}
                        <span className="text-[9px] px-1 py-0.5 bg-gray-100 rounded truncate max-w-[120px]" title={typeof hop === "string" ? hop : hop.url}>{truncateUrl(typeof hop === "string" ? hop : (hop.url || ""), 20)}</span>
                      </span>
                    ))}
                  </div>
                ) : <span className="text-gray-300">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PerformancePanel({ data, loading, isTerminal }: { data: any | undefined; loading: boolean; isTerminal: boolean }) {
  if (!isTerminal) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Performance analysis available after crawl completes.</div>;
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Analyzing performance...</div>;
  if (!data) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No performance data available.</div>;

  const stats = data.stats ?? {};
  const dist = data.distribution ?? [];
  const slowest = data.slowest_pages ?? [];
  const maxBucket = Math.max(...dist.map((d: any) => d.count), 1);

  const speedColor = (ms: number | null) => {
    if (ms == null) return "text-gray-400";
    if (ms < 500) return "text-green-700";
    if (ms < 1000) return "text-amber-600";
    return "text-red-600";
  };

  return (
    <div className="overflow-auto">
      {/* Summary cards */}
      <div className="flex gap-3 p-3 border-b border-gray-200">
        <div className="flex-1 p-2 bg-blue-50 rounded border border-blue-200 text-center">
          <div className="text-[10px] text-blue-500 uppercase tracking-wide">Avg Response</div>
          <div className={`text-lg font-bold ${speedColor(stats.avg_ms)}`}>{stats.avg_ms != null ? `${stats.avg_ms}ms` : "—"}</div>
        </div>
        <div className="flex-1 p-2 bg-green-50 rounded border border-green-200 text-center">
          <div className="text-[10px] text-green-500 uppercase tracking-wide">P50 (Median)</div>
          <div className={`text-lg font-bold ${speedColor(stats.p50_ms)}`}>{stats.p50_ms != null ? `${stats.p50_ms}ms` : "—"}</div>
        </div>
        <div className="flex-1 p-2 bg-amber-50 rounded border border-amber-200 text-center">
          <div className="text-[10px] text-amber-500 uppercase tracking-wide">P95</div>
          <div className={`text-lg font-bold ${speedColor(stats.p95_ms)}`}>{stats.p95_ms != null ? `${stats.p95_ms}ms` : "—"}</div>
        </div>
        <div className="flex-1 p-2 bg-red-50 rounded border border-red-200 text-center">
          <div className="text-[10px] text-red-500 uppercase tracking-wide">Slow ({">"}1s)</div>
          <div className="text-lg font-bold text-red-700">{stats.slow_count ?? 0}</div>
        </div>
        <div className="flex-1 p-2 bg-purple-50 rounded border border-purple-200 text-center">
          <div className="text-[10px] text-purple-500 uppercase tracking-wide">Pages</div>
          <div className="text-lg font-bold text-purple-700">{stats.total ?? 0}</div>
        </div>
      </div>

      {/* Distribution chart */}
      {dist.length > 0 && (
        <div className="p-3 border-b border-gray-200">
          <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-wide mb-2">Response Time Distribution</h3>
          <div className="space-y-1.5">
            {dist.map((d: any, i: number) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-[10px] text-gray-500 w-20 text-right font-mono">{d.bucket}</span>
                <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden">
                  <div className={`h-full rounded ${d.bucket === ">3s" ? "bg-red-400" : d.bucket === "1-3s" ? "bg-amber-400" : d.bucket === "500ms-1s" ? "bg-yellow-400" : "bg-green-400"}`} style={{ width: `${(d.count / maxBucket) * 100}%` }} />
                </div>
                <span className="text-[10px] text-gray-600 w-10 font-mono">{d.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slowest pages table */}
      <table className="w-full text-[11px]">
        <thead className="bg-gray-50 sticky top-0">
          <tr className="text-left text-[10px] text-gray-500 uppercase tracking-wider">
            <th className="px-3 py-1.5 font-medium">URL</th>
            <th className="px-3 py-1.5 font-medium text-right w-28">Response Time</th>
            <th className="px-3 py-1.5 font-medium text-right w-20">Status</th>
            <th className="px-3 py-1.5 font-medium w-24">Type</th>
          </tr>
        </thead>
        <tbody>
          {slowest.map((page: any, i: number) => (
            <tr key={i} className={`border-t border-gray-100 hover:bg-blue-50/40 ${page.response_time_ms > 3000 ? "bg-red-50/30" : page.response_time_ms > 1000 ? "bg-amber-50/30" : ""}`}>
              <td className="px-3 py-1.5 truncate max-w-[400px]" title={page.url}>{truncateUrl(page.url, 60)}</td>
              <td className={`px-3 py-1.5 text-right font-mono font-medium ${speedColor(page.response_time_ms)}`}>{page.response_time_ms}ms</td>
              <td className="px-3 py-1.5 text-right font-mono">{page.status_code}</td>
              <td className="px-3 py-1.5 text-gray-500 truncate">{page.content_type?.split(";")[0] ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CookiesPanel({ data, loading, isTerminal }: { data: any[] | undefined; loading: boolean; isTerminal: boolean }) {
  if (!isTerminal) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Cookie audit available after crawl completes.</div>;
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Auditing cookies...</div>;
  if (!data || data.length === 0) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No cookies detected — this site doesn&apos;t set any cookies.</div>;

  const allCookies = data.flatMap((page: any) =>
    (page.cookies || []).map((c: any) => ({ ...c, page_url: page.url }))
  );
  const thirdParty = allCookies.filter((c: any) => c.is_third_party);
  const insecure = allCookies.filter((c: any) => c.issues && c.issues.length > 0);

  return (
    <div className="overflow-auto">
      <div className="flex gap-3 p-3 border-b border-gray-200">
        <div className="flex-1 p-2 bg-blue-50 rounded border border-blue-200 text-center">
          <div className="text-[10px] text-blue-500 uppercase tracking-wide">Total Cookies</div>
          <div className="text-lg font-bold text-blue-700">{allCookies.length}</div>
        </div>
        <div className="flex-1 p-2 bg-purple-50 rounded border border-purple-200 text-center">
          <div className="text-[10px] text-purple-500 uppercase tracking-wide">Pages with Cookies</div>
          <div className="text-lg font-bold text-purple-700">{data.length}</div>
        </div>
        <div className="flex-1 p-2 bg-orange-50 rounded border border-orange-200 text-center">
          <div className="text-[10px] text-orange-500 uppercase tracking-wide">Third-Party</div>
          <div className="text-lg font-bold text-orange-700">{thirdParty.length}</div>
        </div>
        <div className="flex-1 p-2 bg-red-50 rounded border border-red-200 text-center">
          <div className="text-[10px] text-red-500 uppercase tracking-wide">Security Issues</div>
          <div className="text-lg font-bold text-red-700">{insecure.length}</div>
        </div>
      </div>
      <table className="w-full text-[11px]">
        <thead className="bg-gray-50 sticky top-0">
          <tr className="text-left text-[10px] text-gray-500 uppercase tracking-wider">
            <th className="px-3 py-1.5 font-medium">Cookie Name</th>
            <th className="px-3 py-1.5 font-medium">Domain</th>
            <th className="px-3 py-1.5 font-medium text-center w-16">Secure</th>
            <th className="px-3 py-1.5 font-medium text-center w-16">HttpOnly</th>
            <th className="px-3 py-1.5 font-medium text-center w-20">SameSite</th>
            <th className="px-3 py-1.5 font-medium text-center w-20">3rd Party</th>
            <th className="px-3 py-1.5 font-medium">Issues</th>
            <th className="px-3 py-1.5 font-medium">Page</th>
          </tr>
        </thead>
        <tbody>
          {allCookies.map((cookie: any, i: number) => (
            <tr key={i} className={`border-t border-gray-100 hover:bg-blue-50/40 ${cookie.is_third_party ? "bg-orange-50/30" : ""}`}>
              <td className="px-3 py-1.5 font-mono font-medium">{cookie.name}</td>
              <td className="px-3 py-1.5 font-mono text-gray-600">{cookie.domain}</td>
              <td className="px-3 py-1.5 text-center">{cookie.secure ? <span className="text-green-600">✓</span> : <span className="text-red-500">✗</span>}</td>
              <td className="px-3 py-1.5 text-center">{cookie.httponly ? <span className="text-green-600">✓</span> : <span className="text-red-500">✗</span>}</td>
              <td className="px-3 py-1.5 text-center font-mono">{cookie.samesite || <span className="text-gray-300">—</span>}</td>
              <td className="px-3 py-1.5 text-center">{cookie.is_third_party ? <span className="text-orange-600 font-semibold">Yes</span> : <span className="text-gray-400">No</span>}</td>
              <td className="px-3 py-1.5">{cookie.issues?.map((issue: string, j: number) => (
                <span key={j} className="inline-block mr-1 px-1 py-0.5 text-[9px] bg-red-100 text-red-700 rounded">{issue.replace(/_/g, " ")}</span>
              ))}</td>
              <td className="px-3 py-1.5 truncate max-w-[200px] text-gray-500" title={cookie.page_url}>{truncateUrl(cookie.page_url, 30)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SecurityPanel({ data, loading, isTerminal, totalPages }: { data: any | undefined; loading: boolean; isTerminal: boolean; totalPages: number }) {
  if (!isTerminal) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Security audit available after crawl completes.</div>;
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Analyzing security...</div>;
  if (!data) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No security data available.</div>;

  const httpsCount = data.https_count ?? 0;
  const httpCount = data.http_count ?? 0;
  const total = data.total_pages ?? totalPages;
  const httpsPct = total > 0 ? ((httpsCount / total) * 100).toFixed(1) : "0";
  const issues = data.issue_counts ?? {};

  const headerChecks = [
    { key: "missing_hsts", label: "Strict-Transport-Security (HSTS)", desc: "Prevents protocol downgrade attacks" },
    { key: "missing_csp", label: "Content-Security-Policy (CSP)", desc: "Prevents XSS and injection attacks" },
    { key: "missing_x_content_type_options", label: "X-Content-Type-Options", desc: "Prevents MIME type sniffing" },
    { key: "missing_x_frame_options", label: "X-Frame-Options", desc: "Prevents clickjacking" },
    { key: "mixed_content", label: "Mixed Content", desc: "HTTPS pages loading HTTP resources" },
    { key: "http_url", label: "HTTP URLs", desc: "Pages served over insecure HTTP" },
  ];

  return (
    <div className="overflow-auto">
      <div className="flex gap-3 p-3 border-b border-gray-200">
        <div className="flex-1 p-2 bg-green-50 rounded border border-green-200 text-center">
          <div className="text-[10px] text-green-500 uppercase tracking-wide">HTTPS Pages</div>
          <div className="text-lg font-bold text-green-700">{httpsCount} <span className="text-sm font-normal">({httpsPct}%)</span></div>
        </div>
        <div className="flex-1 p-2 bg-red-50 rounded border border-red-200 text-center">
          <div className="text-[10px] text-red-500 uppercase tracking-wide">HTTP Pages</div>
          <div className="text-lg font-bold text-red-700">{httpCount}</div>
        </div>
        <div className="flex-1 p-2 bg-blue-50 rounded border border-blue-200 text-center">
          <div className="text-[10px] text-blue-500 uppercase tracking-wide">Total Analyzed</div>
          <div className="text-lg font-bold text-blue-700">{total}</div>
        </div>
      </div>

      <div className="p-4 space-y-3">
        <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Security Headers</h3>
        {headerChecks.map((check) => {
          const count = issues[check.key] ?? 0;
          const coverage = total > 0 ? total - count : 0;
          const pct = total > 0 ? ((coverage / total) * 100).toFixed(0) : "100";
          const isGood = count === 0;
          return (
            <div key={check.key} className="flex items-center gap-3 p-2 rounded border border-gray-100">
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isGood ? "bg-green-500" : count > total * 0.5 ? "bg-red-500" : "bg-amber-500"}`} />
              <div className="flex-1 min-w-0">
                <div className="text-[11px] font-medium text-gray-800">{check.label}</div>
                <div className="text-[10px] text-gray-400">{check.desc}</div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className={`text-sm font-bold ${isGood ? "text-green-700" : "text-red-600"}`}>{pct}%</div>
                <div className="text-[9px] text-gray-400">{count > 0 ? `${count} missing` : "All present"}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HreflangPanel({ data, loading, isTerminal }: { data: any[] | undefined; loading: boolean; isTerminal: boolean }) {
  if (!isTerminal) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Hreflang analysis available after crawl completes.</div>;
  if (loading) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">Analyzing hreflang tags...</div>;
  if (!data || data.length === 0) return <div className="flex items-center justify-center h-32 text-xs text-gray-400">No hreflang tags found on this site.</div>;

  const allLangs = new Set<string>();
  data.forEach((page: any) => {
    (page.hreflang || []).forEach((h: any) => {
      if (h.lang) allLangs.add(h.lang);
    });
  });

  return (
    <div className="overflow-auto">
      <div className="flex gap-3 p-3 border-b border-gray-200">
        <div className="flex-1 p-2 bg-blue-50 rounded border border-blue-200 text-center">
          <div className="text-[10px] text-blue-500 uppercase tracking-wide">Pages with Hreflang</div>
          <div className="text-lg font-bold text-blue-700">{data.length}</div>
        </div>
        <div className="flex-1 p-2 bg-purple-50 rounded border border-purple-200 text-center">
          <div className="text-[10px] text-purple-500 uppercase tracking-wide">Languages</div>
          <div className="text-lg font-bold text-purple-700">{allLangs.size}</div>
          <div className="text-[9px] text-gray-400">{Array.from(allLangs).slice(0, 5).join(", ")}{allLangs.size > 5 ? "..." : ""}</div>
        </div>
      </div>
      <table className="w-full text-[11px]">
        <thead className="bg-gray-50 sticky top-0">
          <tr className="text-left text-[10px] text-gray-500 uppercase tracking-wider">
            <th className="px-3 py-1.5 font-medium">URL</th>
            <th className="px-3 py-1.5 font-medium">Language</th>
            <th className="px-3 py-1.5 font-medium">Alternate URL</th>
          </tr>
        </thead>
        <tbody>
          {data.flatMap((page: any) =>
            (page.hreflang || []).map((h: any, i: number) => (
              <tr key={`${page.url_id}-${i}`} className="border-t border-gray-100 hover:bg-blue-50/40">
                <td className="px-3 py-1.5 truncate max-w-[250px]" title={page.url}>{i === 0 ? truncateUrl(page.url, 40) : ""}</td>
                <td className="px-3 py-1.5 font-mono font-medium">{h.lang || "x-default"}</td>
                <td className="px-3 py-1.5 truncate max-w-[300px] text-gray-600" title={h.href}>{truncateUrl(h.href || "", 50)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

// ─── Overview Panel ───────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function OverviewPanel({ crawl, crawledCount, errorCount, issueSummary, healthScore, perfData, urlsPerSec, elapsed, isTerminal }: {
  crawl: Crawl; crawledCount: number; errorCount: number;
  issueSummary: any; healthScore: any; perfData: any;
  urlsPerSec: number | null; elapsed: number | null; isTerminal: boolean;
}) {
  const config = crawl.config as Record<string, any>;
  const score = healthScore?.score ?? null;
  const grade = healthScore?.grade ?? null;
  const avgMs = perfData?.average_ms ?? null;
  const p95Ms = perfData?.p95_ms ?? null;

  const gradeColor = (g: string | null) => {
    if (!g) return "text-gray-400";
    if (g === "A" || g === "A+") return "text-green-600";
    if (g === "B") return "text-blue-600";
    if (g === "C") return "text-yellow-600";
    return "text-red-600";
  };

  return (
    <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-280px)]">
      {/* Health Score + Key Metrics */}
      <div className="grid grid-cols-6 gap-3">
        <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-col items-center justify-center">
          <div className="text-[11px] text-gray-500 mb-1">Health Score</div>
          {score !== null ? (
            <>
              <div className={`text-3xl font-bold ${gradeColor(grade)}`}>{grade}</div>
              <div className="text-sm text-gray-600">{Math.round(score)}/100</div>
            </>
          ) : (
            <div className="text-lg text-gray-300">{isTerminal ? "N/A" : "..."}</div>
          )}
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-[11px] text-gray-500 mb-1">URLs Crawled</div>
          <div className="text-2xl font-bold text-gray-900">{crawledCount.toLocaleString()}</div>
          <div className="text-[10px] text-gray-400">of {(config.max_urls ?? 10000).toLocaleString()} max</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-[11px] text-gray-500 mb-1">Errors</div>
          <div className={`text-2xl font-bold ${errorCount > 0 ? "text-red-600" : "text-green-700"}`}>{errorCount.toLocaleString()}</div>
          <div className="text-[10px] text-gray-400">{crawledCount > 0 ? `${((errorCount / crawledCount) * 100).toFixed(1)}% error rate` : ""}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-[11px] text-gray-500 mb-1">Issues</div>
          <div className="text-2xl font-bold text-gray-900">{issueSummary?.total?.toLocaleString() ?? (isTerminal ? "0" : "...")}</div>
          {issueSummary?.by_severity?.critical > 0 && (
            <div className="text-[10px] text-red-600">{issueSummary.by_severity.critical} critical</div>
          )}
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-[11px] text-gray-500 mb-1">Avg Response</div>
          <div className="text-2xl font-bold text-gray-900">{avgMs != null ? `${Math.round(avgMs)}ms` : (isTerminal ? "N/A" : "...")}</div>
          {p95Ms != null && <div className="text-[10px] text-gray-400">P95: {Math.round(p95Ms)}ms</div>}
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-[11px] text-gray-500 mb-1">Speed</div>
          <div className="text-2xl font-bold text-gray-900">
            {urlsPerSec != null ? `${urlsPerSec < 1 ? urlsPerSec.toFixed(2) : urlsPerSec.toFixed(1)}` : "—"}
          </div>
          <div className="text-[10px] text-gray-400">URLs/sec{elapsed != null ? ` · ${formatDuration(elapsed)}` : ""}</div>
        </div>
      </div>

      {/* Health Score Breakdown + Issue Categories */}
      <div className="grid grid-cols-2 gap-3">
        {/* Health components */}
        {healthScore?.components && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="text-xs font-semibold text-gray-700 mb-3">Health Score Breakdown</h3>
            <div className="space-y-2">
              {(healthScore.components as any[]).map((comp: any, i: number) => (
                <div key={i}>
                  <div className="flex justify-between text-[11px] mb-0.5">
                    <span className="text-gray-600">{comp.name} ({comp.weight}%)</span>
                    <span className="font-medium text-gray-900">{Math.round(comp.score)}/100</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${comp.score >= 80 ? "bg-green-500" : comp.score >= 60 ? "bg-yellow-500" : "bg-red-500"}`}
                      style={{ width: `${Math.min(comp.score, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Issue breakdown by category */}
        {issueSummary && Object.keys(issueSummary.by_category ?? {}).length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="text-xs font-semibold text-gray-700 mb-3">Issues by Category</h3>
            <div className="space-y-1.5">
              {Object.entries(issueSummary.by_category as Record<string, number>)
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .slice(0, 10)
                .map(([cat, count]) => (
                  <div key={cat} className="flex justify-between text-[11px]">
                    <span className="text-gray-600 capitalize">{cat.replace(/_/g, " ")}</span>
                    <span className="font-medium text-gray-900">{String(count)}</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Crawl config summary */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-xs font-semibold text-gray-700 mb-3">Crawl Configuration</h3>
        <div className="grid grid-cols-4 gap-4 text-[11px]">
          <div><span className="text-gray-500">Mode:</span> <span className="font-medium">{crawl.mode === "spider" ? "Spider" : "List"}</span></div>
          <div><span className="text-gray-500">Start URL:</span> <span className="font-medium font-mono">{String(config.start_url ?? "—").slice(0, 50)}</span></div>
          <div><span className="text-gray-500">Max URLs:</span> <span className="font-medium">{(config.max_urls ?? 10000).toLocaleString()}</span></div>
          <div><span className="text-gray-500">Max Depth:</span> <span className="font-medium">{config.max_depth ?? 10}</span></div>
          <div><span className="text-gray-500">User Agent:</span> <span className="font-medium">{String(config.user_agent ?? "Default").slice(0, 30)}</span></div>
          <div><span className="text-gray-500">Respect Robots:</span> <span className="font-medium">{config.respect_robots !== false ? "Yes" : "No"}</span></div>
          <div><span className="text-gray-500">Rate Limit:</span> <span className="font-medium">{config.rate_limit_rps ?? "—"} req/s</span></div>
          <div><span className="text-gray-500">JS Rendering:</span> <span className="font-medium">{config.render_js ? "Yes" : "No"}</span></div>
        </div>
      </div>

      {/* Timestamps */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="grid grid-cols-3 gap-4 text-[11px]">
          <div><span className="text-gray-500">Created:</span> <span className="font-medium">{new Date(crawl.created_at).toLocaleString()}</span></div>
          <div><span className="text-gray-500">Started:</span> <span className="font-medium">{crawl.started_at ? new Date(crawl.started_at).toLocaleString() : "—"}</span></div>
          <div><span className="text-gray-500">Completed:</span> <span className="font-medium">{crawl.completed_at ? new Date(crawl.completed_at).toLocaleString() : "—"}</span></div>
        </div>
      </div>
    </div>
  );
}

// ─── Robots.txt Panel ─────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function RobotsTxtPanel({ data, loading }: { data: any | undefined; loading: boolean }) {
  if (loading) return <div className="flex items-center justify-center h-40 text-gray-400 text-sm">Loading robots.txt...</div>;
  if (!data) return <div className="p-4 text-gray-400 text-sm">No data available</div>;

  const directives = data.directives ?? [];
  const sitemaps = data.sitemaps ?? [];
  const agents: string[] = [...new Set<string>(directives.map((d: any) => String(d.user_agent)))];

  return (
    <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-280px)]">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-[11px] text-gray-500 mb-1">Status</div>
          <div className={`text-lg font-bold ${data.status_code === 200 ? "text-green-700" : data.status_code === 404 ? "text-orange-600" : "text-red-600"}`}>
            {data.status_code || "Error"}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-[11px] text-gray-500 mb-1">User Agents</div>
          <div className="text-lg font-bold text-gray-900">{agents.length}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-[11px] text-gray-500 mb-1">Directives</div>
          <div className="text-lg font-bold text-gray-900">{directives.length}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-[11px] text-gray-500 mb-1">Sitemaps</div>
          <div className="text-lg font-bold text-blue-700">{sitemaps.length}</div>
        </div>
      </div>

      {/* Sitemaps listed in robots.txt */}
      {sitemaps.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <h3 className="text-xs font-semibold text-gray-700 mb-2">Sitemaps declared in robots.txt</h3>
          <div className="space-y-1">
            {sitemaps.map((url: string, i: number) => (
              <div key={i} className="text-xs text-blue-600 font-mono truncate">{url}</div>
            ))}
          </div>
        </div>
      )}

      {/* Directives by user-agent */}
      {agents.map((agent: string) => (
        <div key={agent} className="bg-white rounded-lg border border-gray-200 p-3">
          <h3 className="text-xs font-semibold text-gray-700 mb-2">User-Agent: <span className="font-mono text-blue-700">{agent}</span></h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 text-gray-500">
                <th className="text-left py-1 px-2 w-32">Directive</th>
                <th className="text-left py-1 px-2">Value</th>
              </tr>
            </thead>
            <tbody>
              {directives.filter((d: any) => d.user_agent === agent).map((d: any, i: number) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className={`py-1 px-2 font-mono ${d.directive === "disallow" ? "text-red-600" : d.directive === "allow" ? "text-green-700" : "text-gray-700"}`}>
                    {d.directive}
                  </td>
                  <td className="py-1 px-2 font-mono text-gray-700">{d.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {/* Raw content */}
      <div className="bg-white rounded-lg border border-gray-200 p-3">
        <h3 className="text-xs font-semibold text-gray-700 mb-2">Raw Content — <span className="font-mono text-gray-500">{data.url}</span></h3>
        <pre className="text-xs font-mono bg-gray-50 rounded p-3 overflow-x-auto whitespace-pre max-h-80 overflow-y-auto text-gray-700">
          {data.raw_content || "(empty)"}
        </pre>
      </div>
    </div>
  );
}

// ─── Sitemap Panel ──────────���─────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function SitemapPanel({ data, loading }: { data: any | undefined; loading: boolean }) {
  if (loading) return <div className="flex items-center justify-center h-40 text-gray-400 text-sm">Analyzing sitemaps...</div>;
  if (!data) return <div className="p-4 text-gray-400 text-sm">No data available</div>;

  const sitemaps = data.sitemaps ?? [];
  const coverage = data.coverage ?? {};

  return (
    <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-280px)]">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-[11px] text-gray-500 mb-1">Sitemap URLs</div>
          <div className="text-lg font-bold text-gray-900">{data.total_sitemap_urls ?? 0}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-[11px] text-gray-500 mb-1">Crawled URLs</div>
          <div className="text-lg font-bold text-gray-900">{data.total_crawled_urls ?? 0}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-[11px] text-gray-500 mb-1">In Both</div>
          <div className="text-lg font-bold text-green-700">{coverage.in_both ?? 0}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-[11px] text-gray-500 mb-1">Coverage</div>
          <div className="text-lg font-bold text-blue-700">
            {data.total_sitemap_urls > 0 ? `${Math.round((coverage.in_both / data.total_sitemap_urls) * 100)}%` : "N/A"}
          </div>
        </div>
      </div>

      {/* Coverage breakdown */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-white rounded-lg border border-orange-200 p-3">
          <h3 className="text-xs font-semibold text-orange-700 mb-1">In Sitemap, Not Crawled ({coverage.in_sitemap_not_crawled ?? 0})</h3>
          <p className="text-[10px] text-gray-500 mb-2">URLs in sitemap.xml that weren't found during crawl</p>
          <div className="max-h-60 overflow-y-auto space-y-0.5">
            {(data.urls_in_sitemap_not_crawled ?? []).slice(0, 100).map((url: string, i: number) => (
              <div key={i} className="text-[11px] font-mono text-orange-700 truncate">{url}</div>
            ))}
            {(coverage.in_sitemap_not_crawled ?? 0) === 0 && (
              <div className="text-[11px] text-gray-400 italic">All sitemap URLs were crawled</div>
            )}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-blue-200 p-3">
          <h3 className="text-xs font-semibold text-blue-700 mb-1">Crawled, Not in Sitemap ({coverage.in_crawl_not_sitemap ?? 0})</h3>
          <p className="text-[10px] text-gray-500 mb-2">URLs found during crawl that aren't in sitemap.xml</p>
          <div className="max-h-60 overflow-y-auto space-y-0.5">
            {(data.urls_in_crawl_not_sitemap ?? []).slice(0, 100).map((url: string, i: number) => (
              <div key={i} className="text-[11px] font-mono text-blue-700 truncate">{url}</div>
            ))}
            {(coverage.in_crawl_not_sitemap ?? 0) === 0 && (
              <div className="text-[11px] text-gray-400 italic">All crawled URLs are in the sitemap</div>
            )}
          </div>
        </div>
      </div>

      {/* Sitemap files */}
      <div className="bg-white rounded-lg border border-gray-200 p-3">
        <h3 className="text-xs font-semibold text-gray-700 mb-2">Discovered Sitemaps</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-100 text-gray-500">
              <th className="text-left py-1 px-2">URL</th>
              <th className="text-left py-1 px-2 w-20">Status</th>
              <th className="text-left py-1 px-2 w-20">Type</th>
              <th className="text-right py-1 px-2 w-20">URLs</th>
            </tr>
          </thead>
          <tbody>
            {sitemaps.map((sm: any, i: number) => (
              <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-1 px-2 font-mono text-blue-600 truncate max-w-md">{sm.url}</td>
                <td className={`py-1 px-2 ${sm.status_code === 200 ? "text-green-700" : "text-red-600"}`}>
                  {sm.status_code || "Err"}
                </td>
                <td className="py-1 px-2 text-gray-600">{sm.type}</td>
                <td className="py-1 px-2 text-right text-gray-700">{sm.url_count}</td>
              </tr>
            ))}
            {sitemaps.length === 0 && (
              <tr><td colSpan={4} className="py-3 text-center text-gray-400 italic">No sitemaps found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* eslint-enable @typescript-eslint/no-explicit-any */
