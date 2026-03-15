"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/crawl/StatusBadge";
import { projectsApi, crawlsApi } from "@/lib/api-client";
import Link from "next/link";
import { useState, useMemo } from "react";
import {
  Square,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Filter,
  ArrowLeftRight,
} from "lucide-react";
import type { Project, CrawlSummary, CrawlStatus } from "@/types";

// ─── Helpers ────────────────────────────────────────────────────────

function formatDuration(
  startedAt: string | null,
  completedAt: string | null
): string {
  if (!startedAt) return "\u2014";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getStartUrl(config: Record<string, unknown>): string {
  const url = (config?.start_url as string) || "";
  try {
    const u = new URL(url);
    return u.hostname + (u.pathname !== "/" ? u.pathname : "");
  } catch {
    return url || "\u2014";
  }
}

function ProgressBar({ crawled, total }: { crawled: number; total: number }) {
  if (total === 0 && crawled === 0)
    return <span className="text-muted-foreground">{"\u2014"}</span>;
  if (total === 0)
    return <span className="text-xs text-muted-foreground">{crawled.toLocaleString()} crawled</span>;
  const pct = Math.min(100, Math.round((crawled / total) * 100));
  return (
    <div className="flex items-center gap-2 min-w-[140px]">
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-[#6cc04a] rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {crawled.toLocaleString()}/{total.toLocaleString()} ({pct}%)
      </span>
    </div>
  );
}

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "crawling", label: "Crawling" },
  { value: "queued", label: "Queued" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

// ─── Page Component ─────────────────────────────────────────────────

export default function CrawlsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("all");
  const [projectFilter, setProjectFilter] = useState("all");
  const [page, setPage] = useState(0);
  const pageSize = 25;

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(null, 100),
  });

  const { data: crawlsData, isLoading } = useQuery({
    queryKey: ["all-crawls-list"],
    queryFn: () => crawlsApi.listAll(null, 500),
    refetchInterval: 5000,
  });

  const projects = projectsData?.items ?? [];
  const allCrawls = crawlsData?.items ?? [];
  const projectMap = new Map<string, Project>(projects.map((p) => [p.id, p]));

  const filteredCrawls = useMemo(() => {
    let result = allCrawls;
    if (statusFilter !== "all") {
      result = result.filter(
        (c: CrawlSummary) => c.status === statusFilter
      );
    }
    if (projectFilter !== "all") {
      result = result.filter(
        (c: CrawlSummary) => c.project_id === projectFilter
      );
    }
    return result;
  }, [allCrawls, statusFilter, projectFilter]);

  const totalFiltered = filteredCrawls.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const paginatedCrawls = filteredCrawls.slice(
    safePage * pageSize,
    (safePage + 1) * pageSize
  );

  const activeCrawlCount = allCrawls.filter(
    (c: CrawlSummary) =>
      c.status === "crawling" || c.status === "queued" || c.status === "paused"
  ).length;

  const [pendingActions, setPendingActions] = useState<Set<string>>(new Set());

  const handleStop = async (crawlId: string) => {
    setPendingActions((prev) => new Set(prev).add(`stop-${crawlId}`));
    try {
      await crawlsApi.stop(crawlId);
      queryClient.invalidateQueries({ queryKey: ["all-crawls-list"] });
    } finally {
      setPendingActions((prev) => { const next = new Set(prev); next.delete(`stop-${crawlId}`); return next; });
    }
  };

  const handleDeleteCrawl = async (crawlId: string) => {
    setPendingActions((prev) => new Set(prev).add(`del-${crawlId}`));
    try {
      await crawlsApi.delete(crawlId);
      queryClient.invalidateQueries({ queryKey: ["all-crawls-list"] });
    } finally {
      setPendingActions((prev) => { const next = new Set(prev); next.delete(`del-${crawlId}`); return next; });
    }
  };

  return (
    <div className="space-y-6 p-6 overflow-auto flex-1">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Crawls</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? "Loading..."
              : `${totalFiltered} crawl${totalFiltered !== 1 ? "s" : ""}${
                  statusFilter !== "all" || projectFilter !== "all"
                    ? " (filtered)"
                    : ""
                }${
                  activeCrawlCount > 0
                    ? ` · ${activeCrawlCount} active`
                    : ""
                }`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/crawls/compare">
            <Button variant="outline">
              <ArrowLeftRight className="h-4 w-4 mr-2" />
              Compare
            </Button>
          </Link>
          <Link href="/crawls/new">
            <Button>New Crawl</Button>
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <select
          value={projectFilter}
          onChange={(e) => {
            setProjectFilter(e.target.value);
            setPage(0);
          }}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All Projects</option>
          {projects.map((p: Project) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        {(statusFilter !== "all" || projectFilter !== "all") && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setStatusFilter("all");
              setProjectFilter("all");
              setPage(0);
            }}
          >
            Clear Filters
          </Button>
        )}
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {statusFilter !== "all" || projectFilter !== "all"
              ? "Filtered Crawls"
              : "All Crawls"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground py-8 text-center">
              Loading crawls...
            </p>
          ) : filteredCrawls.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground mb-4">
                {statusFilter !== "all" || projectFilter !== "all"
                  ? "No crawls match the current filters."
                  : "No crawls yet. Start your first crawl!"}
              </p>
              {statusFilter === "all" && projectFilter === "all" && (
                <Link href="/crawls/new">
                  <Button variant="outline">Create Crawl</Button>
                </Link>
              )}
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[100px]">Status</TableHead>
                      <TableHead>Target URL</TableHead>
                      <TableHead>Project</TableHead>
                      <TableHead className="w-[70px]">Mode</TableHead>
                      <TableHead className="min-w-[180px]">Progress</TableHead>
                      <TableHead className="text-right w-[70px]">
                        Errors
                      </TableHead>
                      <TableHead className="text-right w-[90px]">
                        Duration
                      </TableHead>
                      <TableHead className="text-right w-[120px]">
                        Created
                      </TableHead>
                      <TableHead className="text-right w-[100px]">
                        Actions
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedCrawls.map((crawl: CrawlSummary) => {
                      const project = projectMap.get(crawl.project_id);
                      const isActive = ["crawling", "queued", "paused"].includes(
                        crawl.status
                      );
                      return (
                        <TableRow key={crawl.id}>
                          <TableCell>
                            <StatusBadge status={crawl.status} />
                          </TableCell>
                          <TableCell
                            className="font-mono text-xs max-w-[200px] truncate"
                            title={String(crawl.config?.start_url || "")}
                          >
                            <Link
                              href={`/crawls/${crawl.id}`}
                              className="hover:underline"
                            >
                              {getStartUrl(crawl.config)}
                            </Link>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground max-w-[140px] truncate">
                            {project?.name ||
                              crawl.project_id.slice(0, 8) + "..."}
                          </TableCell>
                          <TableCell className="capitalize text-sm">
                            {crawl.mode}
                          </TableCell>
                          <TableCell>
                            <ProgressBar
                              crawled={crawl.crawled_urls_count}
                              total={crawl.total_urls}
                            />
                          </TableCell>
                          <TableCell className="text-right">
                            {crawl.error_count > 0 ? (
                              <span className="text-red-500 font-medium">
                                {crawl.error_count.toLocaleString()}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">0</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right text-muted-foreground text-sm">
                            {formatDuration(
                              crawl.started_at,
                              crawl.completed_at
                            )}
                          </TableCell>
                          <TableCell className="text-right text-muted-foreground text-sm">
                            {formatTime(crawl.created_at)}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Link href={`/crawls/${crawl.id}`}>
                                <Button variant="ghost" size="sm">
                                  View
                                </Button>
                              </Link>
                              {isActive ? (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleStop(crawl.id)}
                                  disabled={pendingActions.has(`stop-${crawl.id}`)}
                                  title="Stop crawl"
                                >
                                  <Square className="h-3.5 w-3.5 text-red-500" />
                                </Button>
                              ) : (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    if (
                                      confirm(
                                        "Delete this crawl and all its data?"
                                      )
                                    ) {
                                      handleDeleteCrawl(crawl.id);
                                    }
                                  }}
                                  disabled={pendingActions.has(`del-${crawl.id}`)}
                                  title="Delete crawl"
                                >
                                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>

              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <p className="text-sm text-muted-foreground">
                  Showing {totalFiltered > 0 ? safePage * pageSize + 1 : 0}
                  {"\u2013"}
                  {Math.min((safePage + 1) * pageSize, totalFiltered)} of{" "}
                  {totalFiltered}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={safePage === 0}
                  >
                    <ChevronLeft className="h-4 w-4 mr-1" />
                    Prev
                  </Button>
                  <span className="text-sm text-muted-foreground px-2">
                    Page {safePage + 1} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setPage((p) => Math.min(totalPages - 1, p + 1))
                    }
                    disabled={safePage >= totalPages - 1}
                  >
                    Next
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
