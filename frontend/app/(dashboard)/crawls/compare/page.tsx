"use client";

import { useQuery } from "@tanstack/react-query";
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
import { crawlsApi, projectsApi } from "@/lib/api-client";
import Link from "next/link";
import { useState, useMemo } from "react";
import {
  ArrowLeftRight,
  Plus,
  Minus,
  RefreshCw,
  Equal,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
} from "lucide-react";
import type {
  CrawlSummary,
  Project,
  ComparisonChangeType,
  CrawlComparisonUrl,
} from "@/types";

const CHANGE_TYPE_CONFIG: Record<
  string,
  { label: string; color: string; bg: string; icon: React.ReactNode }
> = {
  added: {
    label: "Added",
    color: "text-green-600",
    bg: "bg-green-500/10",
    icon: <Plus className="h-3.5 w-3.5" />,
  },
  removed: {
    label: "Removed",
    color: "text-red-600",
    bg: "bg-red-500/10",
    icon: <Minus className="h-3.5 w-3.5" />,
  },
  changed: {
    label: "Changed",
    color: "text-yellow-600",
    bg: "bg-yellow-500/10",
    icon: <RefreshCw className="h-3.5 w-3.5" />,
  },
  unchanged: {
    label: "Unchanged",
    color: "text-muted-foreground",
    bg: "bg-muted/50",
    icon: <Equal className="h-3.5 w-3.5" />,
  },
};

function ChangeTypeBadge({ type }: { type: string }) {
  const config = CHANGE_TYPE_CONFIG[type];
  if (!config) return <span>{type}</span>;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.color} ${config.bg}`}
    >
      {config.icon}
      {config.label}
    </span>
  );
}

function CrawlLabel(crawl: CrawlSummary) {
  const startUrl =
    (crawl.config as Record<string, unknown>)?.start_url as string;
  let short = "";
  try {
    const u = new URL(startUrl || "");
    short = u.hostname;
  } catch {
    short = startUrl || "unknown";
  }
  const date = new Date(crawl.created_at).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${short} — ${crawl.crawled_urls_count} URLs — ${date}`;
}

function DiffCell({
  a,
  b,
  changeType,
}: {
  a: string | number | boolean | null | undefined;
  b: string | number | boolean | null | undefined;
  changeType: string;
}) {
  const aStr = a == null ? "—" : String(a);
  const bStr = b == null ? "—" : String(b);

  if (changeType === "added") {
    return <span className="text-green-600">{bStr}</span>;
  }
  if (changeType === "removed") {
    return <span className="text-red-600 line-through">{aStr}</span>;
  }
  if (changeType === "changed" && aStr !== bStr) {
    return (
      <span>
        <span className="text-red-500 line-through text-xs">{aStr}</span>
        <span className="mx-1">→</span>
        <span className="text-green-600 text-xs">{bStr}</span>
      </span>
    );
  }
  return <span className="text-muted-foreground">{bStr}</span>;
}

export default function ComparePage() {
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [crawlAId, setCrawlAId] = useState<string>("");
  const [crawlBId, setCrawlBId] = useState<string>("");
  const [changeFilter, setChangeFilter] = useState<
    ComparisonChangeType | "all"
  >("all");
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(null, 100),
  });
  const projects = projectsData?.items ?? [];

  const { data: crawlsData } = useQuery({
    queryKey: ["project-crawls", selectedProject],
    queryFn: () =>
      selectedProject
        ? crawlsApi.listForProject(selectedProject, null, 200)
        : crawlsApi.listAll(null, 200),
    enabled: true,
  });

  const completedCrawls = useMemo(() => {
    const all = crawlsData?.items ?? [];
    return all.filter(
      (c: CrawlSummary) =>
        (c.status === "completed" || c.status === "cancelled") &&
        c.crawled_urls_count > 0
    );
  }, [crawlsData]);

  const crawlBOptions = useMemo(() => {
    return completedCrawls.filter((c: CrawlSummary) => c.id !== crawlAId);
  }, [completedCrawls, crawlAId]);

  const canCompare = !!crawlAId && !!crawlBId && crawlAId !== crawlBId;

  // Use a safe page value that resets to 0 atomically with filter changes
  const safePage = useMemo(() => page, [page]);

  const {
    data: comparison,
    isLoading: isComparing,
    error: compareError,
  } = useQuery({
    queryKey: [
      "crawl-comparison",
      crawlAId,
      crawlBId,
      changeFilter,
      safePage,
    ],
    queryFn: () =>
      crawlsApi.compare(
        crawlAId,
        crawlBId,
        changeFilter === "all" ? null : changeFilter,
        pageSize,
        page * pageSize
      ),
    enabled: canCompare,
  });

  const totalPages = comparison
    ? Math.max(1, Math.ceil(comparison.total_count / pageSize))
    : 1;

  return (
    <div className="space-y-6 p-6 overflow-auto flex-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/crawls">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Crawls
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <ArrowLeftRight className="h-7 w-7 text-[#6cc04a]" />
              Compare Crawls
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Compare two crawls to see URL-level differences
            </p>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Select Crawls</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm font-medium mb-1.5">Project (optional)</p>
              <select
                value={selectedProject}
                onChange={(e) => {
                  setSelectedProject(e.target.value);
                  setCrawlAId("");
                  setCrawlBId("");
                  setPage(0);
                }}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">All Projects</option>
                {projects.map((p: Project) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <p className="text-sm font-medium mb-1.5">
                Crawl A{" "}
                <span className="text-muted-foreground font-normal">
                  (baseline)
                </span>
              </p>
              <select
                value={crawlAId}
                onChange={(e) => {
                  setCrawlAId(e.target.value);
                  setPage(0);
                }}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select crawl...</option>
                {completedCrawls.map((c: CrawlSummary) => (
                  <option key={c.id} value={c.id}>
                    {CrawlLabel(c)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <p className="text-sm font-medium mb-1.5">
                Crawl B{" "}
                <span className="text-muted-foreground font-normal">
                  (comparison)
                </span>
              </p>
              <select
                value={crawlBId}
                onChange={(e) => {
                  setCrawlBId(e.target.value);
                  setPage(0);
                }}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                disabled={!crawlAId}
              >
                <option value="">Select crawl...</option>
                {crawlBOptions.map((c: CrawlSummary) => (
                  <option key={c.id} value={c.id}>
                    {CrawlLabel(c)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {canCompare && comparison && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {(
              [
                ["added", comparison.summary.added],
                ["removed", comparison.summary.removed],
                ["changed", comparison.summary.changed],
                ["unchanged", comparison.summary.unchanged],
              ] as [string, number][]
            ).map(([type, count]) => {
              const config = CHANGE_TYPE_CONFIG[type];
              const isActive =
                changeFilter === type || changeFilter === "all";
              return (
                <Card
                  key={type}
                  className={`cursor-pointer transition-all hover:ring-2 hover:ring-ring ${
                    changeFilter === type ? "ring-2 ring-[#6cc04a]" : ""
                  }`}
                  onClick={() => {
                    setChangeFilter(
                      changeFilter === type
                        ? "all"
                        : (type as ComparisonChangeType)
                    );
                    setPage(0);
                  }}
                >
                  <CardContent className="pt-4 pb-3 px-4">
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-sm font-medium ${
                          isActive
                            ? config.color
                            : "text-muted-foreground"
                        }`}
                      >
                        {config.label}
                      </span>
                      <span className={config.color}>{config.icon}</span>
                    </div>
                    <p
                      className={`text-2xl font-bold mt-1 ${
                        isActive ? "" : "text-muted-foreground"
                      }`}
                    >
                      {count.toLocaleString()}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  URL Differences
                  {changeFilter !== "all" && (
                    <span className="ml-2 text-sm font-normal text-muted-foreground">
                      — showing{" "}
                      {CHANGE_TYPE_CONFIG[changeFilter]?.label.toLowerCase()}{" "}
                      only
                    </span>
                  )}
                </CardTitle>
                <div className="flex items-center gap-2">
                  <p className="text-sm text-muted-foreground">
                    {comparison.summary.total_urls_a.toLocaleString()} vs{" "}
                    {comparison.summary.total_urls_b.toLocaleString()} URLs
                  </p>
                  {changeFilter !== "all" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setChangeFilter("all");
                        setPage(0);
                      }}
                    >
                      Clear Filter
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {isComparing ? (
                <p className="text-muted-foreground py-8 text-center">
                  Comparing crawls...
                </p>
              ) : compareError ? (
                <p className="text-red-500 py-8 text-center">
                  Error: {(compareError as Error).message}
                </p>
              ) : comparison.urls.length === 0 ? (
                <p className="text-muted-foreground py-8 text-center">
                  No URL differences found
                  {changeFilter !== "all" ? " for this filter" : ""}.
                </p>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[100px]">Change</TableHead>
                          <TableHead className="min-w-[300px]">URL</TableHead>
                          <TableHead className="w-[120px]">
                            Status Code
                          </TableHead>
                          <TableHead className="min-w-[200px]">
                            Title
                          </TableHead>
                          <TableHead className="w-[120px]">
                            Word Count
                          </TableHead>
                          <TableHead className="w-[120px]">
                            Response (ms)
                          </TableHead>
                          <TableHead className="w-[100px]">
                            Indexable
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {comparison.urls.map(
                          (row: CrawlComparisonUrl, idx: number) => (
                            <TableRow key={`${row.url}-${idx}`}>
                              <TableCell>
                                <ChangeTypeBadge type={row.change_type} />
                              </TableCell>
                              <TableCell className="font-mono text-xs max-w-[300px] truncate">
                                <span title={row.url}>{row.url}</span>
                              </TableCell>
                              <TableCell>
                                <DiffCell
                                  a={row.a_status_code}
                                  b={row.b_status_code}
                                  changeType={row.change_type}
                                />
                              </TableCell>
                              <TableCell className="max-w-[200px] truncate text-xs">
                                <DiffCell
                                  a={row.a_title}
                                  b={row.b_title}
                                  changeType={row.change_type}
                                />
                              </TableCell>
                              <TableCell>
                                <DiffCell
                                  a={row.a_word_count}
                                  b={row.b_word_count}
                                  changeType={row.change_type}
                                />
                              </TableCell>
                              <TableCell>
                                <DiffCell
                                  a={row.a_response_time_ms}
                                  b={row.b_response_time_ms}
                                  changeType={row.change_type}
                                />
                              </TableCell>
                              <TableCell>
                                <DiffCell
                                  a={
                                    row.a_is_indexable == null
                                      ? null
                                      : row.a_is_indexable
                                        ? "Yes"
                                        : "No"
                                  }
                                  b={
                                    row.b_is_indexable == null
                                      ? null
                                      : row.b_is_indexable
                                        ? "Yes"
                                        : "No"
                                  }
                                  changeType={row.change_type}
                                />
                              </TableCell>
                            </TableRow>
                          )
                        )}
                      </TableBody>
                    </Table>
                  </div>

                  {totalPages > 1 && (
                    <div className="flex items-center justify-between mt-4 pt-4 border-t">
                      <p className="text-sm text-muted-foreground">
                        Showing {page * pageSize + 1}–
                        {Math.min(
                          (page + 1) * pageSize,
                          comparison.total_count
                        )}{" "}
                        of {comparison.total_count.toLocaleString()}
                      </p>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPage((p) => Math.max(0, p - 1))}
                          disabled={page === 0}
                        >
                          <ChevronLeft className="h-4 w-4 mr-1" />
                          Prev
                        </Button>
                        <span className="text-sm text-muted-foreground px-2">
                          Page {page + 1} of {totalPages}
                        </span>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setPage((p) => Math.min(totalPages - 1, p + 1))
                          }
                          disabled={page >= totalPages - 1}
                        >
                          Next
                          <ChevronRight className="h-4 w-4 ml-1" />
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {canCompare && !comparison && isComparing && (
        <Card>
          <CardContent className="py-12 text-center">
            <ArrowLeftRight className="h-8 w-8 text-muted-foreground mx-auto mb-3 animate-pulse" />
            <p className="text-muted-foreground">Comparing crawls...</p>
          </CardContent>
        </Card>
      )}

      {!canCompare && (
        <Card>
          <CardContent className="py-12 text-center">
            <ArrowLeftRight className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
            <p className="text-muted-foreground">
              Select two different crawls above to compare them
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
