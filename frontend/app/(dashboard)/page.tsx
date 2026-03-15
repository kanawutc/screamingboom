"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/crawl/StatusBadge";
import { projectsApi, crawlsApi } from "@/lib/api-client";
import Link from "next/link";
import {
  Globe,
  Activity,
  Link2,
  AlertTriangle,
  Square,
  Trash2,
  ExternalLink,
  FolderOpen,
} from "lucide-react";
import type { Project, CrawlSummary } from "@/types";

function formatDuration(startedAt: string | null, completedAt: string | null): string {
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
  if (total === 0 && crawled === 0) return <span className="text-muted-foreground">{"\u2014"}</span>;
  if (total === 0) return <span className="text-xs text-muted-foreground">{crawled.toLocaleString()} crawled</span>;
  const pct = Math.min(100, Math.round((crawled / total) * 100));
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-[#6cc04a] rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {crawled.toLocaleString()}/{total.toLocaleString()}
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const queryClient = useQueryClient();

  const { data: projectsData, isLoading: projectsLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(null, 100),
  });

  const { data: crawlsData, isLoading: crawlsLoading } = useQuery({
    queryKey: ["all-crawls"],
    queryFn: () => crawlsApi.listAll(null, 100),
    refetchInterval: 5000,
  });

  const projects = projectsData?.items ?? [];
  const allCrawls = crawlsData?.items ?? [];

  const projectMap = new Map<string, Project>(projects.map((p) => [p.id, p]));

  const totalProjects = projects.length;
  const totalCrawls = allCrawls.length;
  const totalUrlsCrawled = allCrawls.reduce(
    (sum: number, c: CrawlSummary) => sum + c.crawled_urls_count,
    0
  );
  const activeCrawls = allCrawls.filter(
    (c: CrawlSummary) => c.status === "crawling" || c.status === "queued" || c.status === "paused"
  );
  const totalErrors = allCrawls.reduce(
    (sum: number, c: CrawlSummary) => sum + c.error_count,
    0
  );

  const [pendingActions, setPendingActions] = useState<Set<string>>(new Set());

  const handleStop = async (crawlId: string) => {
    setPendingActions((prev) => new Set(prev).add(`stop-${crawlId}`));
    try {
      await crawlsApi.stop(crawlId);
      queryClient.invalidateQueries({ queryKey: ["all-crawls"] });
    } finally {
      setPendingActions((prev) => { const next = new Set(prev); next.delete(`stop-${crawlId}`); return next; });
    }
  };

  const handleDeleteCrawl = async (crawlId: string) => {
    setPendingActions((prev) => new Set(prev).add(`del-${crawlId}`));
    try {
      await crawlsApi.delete(crawlId);
      queryClient.invalidateQueries({ queryKey: ["all-crawls"] });
    } finally {
      setPendingActions((prev) => { const next = new Set(prev); next.delete(`del-${crawlId}`); return next; });
    }
  };

  const handleDeleteProject = async (projectId: string) => {
    setPendingActions((prev) => new Set(prev).add(`delp-${projectId}`));
    try {
      await projectsApi.delete(projectId);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["all-crawls"] });
    } finally {
      setPendingActions((prev) => { const next = new Set(prev); next.delete(`delp-${projectId}`); return next; });
    }
  };

  const isLoading = projectsLoading || crawlsLoading;

  const recentCrawls = allCrawls.slice(0, 20);

  // Compute per-project crawl counts and last activity
  const projectCrawlCounts = new Map<string, number>();
  const projectLastCrawl = new Map<string, string>();
  allCrawls.forEach((c: CrawlSummary) => {
    projectCrawlCounts.set(c.project_id, (projectCrawlCounts.get(c.project_id) || 0) + 1);
    const existing = projectLastCrawl.get(c.project_id);
    if (!existing || c.created_at > existing) {
      projectLastCrawl.set(c.project_id, c.created_at);
    }
  });

  const projectsWithStats = projects
    .map((p: Project) => ({
      ...p,
      crawlCount: projectCrawlCounts.get(p.id) || 0,
      lastCrawlAt: projectLastCrawl.get(p.id) || null,
    }))
    .sort((a, b) => b.crawlCount - a.crawlCount);

  return (
    <div className="space-y-6 p-6 overflow-auto flex-1">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <Link href="/crawls/new">
          <Button>New Crawl</Button>
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <Card
          className="cursor-pointer hover:border-[#6cc04a]/50 transition-colors"
          onClick={() => document.getElementById("projects-section")?.scrollIntoView({ behavior: "smooth" })}
        >
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Projects</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {isLoading ? "\u2014" : totalProjects}
            </p>
          </CardContent>
        </Card>
        <Link href="/crawls">
          <Card className="cursor-pointer hover:border-[#6cc04a]/50 transition-colors h-full">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Crawls</CardTitle>
              <Link2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {isLoading ? "\u2014" : totalCrawls}
              </p>
            </CardContent>
          </Card>
        </Link>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">URLs Crawled</CardTitle>
            <ExternalLink className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {isLoading ? "\u2014" : totalUrlsCrawled.toLocaleString()}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Crawls</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${activeCrawls.length > 0 ? "text-[#6cc04a]" : ""}`}>
              {isLoading ? "\u2014" : activeCrawls.length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Errors</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${totalErrors > 0 ? "text-red-500" : ""}`}>
              {isLoading ? "\u2014" : totalErrors.toLocaleString()}
            </p>
          </CardContent>
        </Card>
      </div>

      {activeCrawls.length > 0 && (
        <Card className="border-[#6cc04a]/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#6cc04a] opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#6cc04a]" />
              </span>
              Active Crawls
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead className="text-right">Errors</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeCrawls.map((crawl: CrawlSummary) => (
                  <TableRow key={crawl.id}>
                    <TableCell><StatusBadge status={crawl.status} /></TableCell>
                    <TableCell className="font-mono text-xs max-w-[200px] truncate">
                      {getStartUrl(crawl.config)}
                    </TableCell>
                    <TableCell>
                      <ProgressBar crawled={crawl.crawled_urls_count} total={crawl.total_urls} />
                    </TableCell>
                    <TableCell className="text-right">
                      {crawl.error_count > 0 ? (
                        <span className="text-red-500">{crawl.error_count}</span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground text-sm">
                      {formatDuration(crawl.started_at, crawl.completed_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Link href={`/crawls/${crawl.id}`}>
                          <Button variant="ghost" size="sm">View</Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleStop(crawl.id)}
                          disabled={pendingActions.has(`stop-${crawl.id}`)}
                          title="Stop crawl"
                        >
                          <Square className="h-3.5 w-3.5 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card id="projects-section">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4" />
            Projects
          </CardTitle>
          <span className="text-sm text-muted-foreground">{isLoading ? "" : `${projects.length} total`}</span>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground py-4 text-center">Loading...</p>
          ) : projectsWithStats.length === 0 ? (
            <p className="text-muted-foreground py-4 text-center">No projects yet. Start a crawl to create one.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Domain</TableHead>
                  <TableHead className="text-right">Crawls</TableHead>
                  <TableHead className="text-right">Last Activity</TableHead>
                  <TableHead className="text-right">Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projectsWithStats.map((p) => (
                  <TableRow key={p.id} className={p.crawlCount === 0 ? "opacity-50" : ""}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground font-mono max-w-[200px] truncate">{p.domain}</TableCell>
                    <TableCell className="text-right">
                      {p.crawlCount > 0 ? (
                        <span className="inline-flex items-center rounded-full bg-[#6cc04a]/10 px-2 py-0.5 text-xs font-medium text-[#6cc04a]">
                          {p.crawlCount}
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-xs">none</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">
                      {p.lastCrawlAt ? formatTime(p.lastCrawlAt) : "\u2014"}
                    </TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">
                      {formatTime(p.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (confirm(`Delete project "${p.name}" and all its crawl data?`)) {
                            handleDeleteProject(p.id);
                          }
                        }}
                        disabled={pendingActions.has(`delp-${p.id}`)}
                        title="Delete project"
                      >
                        <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Crawls</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground py-8 text-center">Loading...</p>
          ) : recentCrawls.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground mb-4">
                No crawls yet. Start your first crawl!
              </p>
              <Link href="/crawls/new">
                <Button variant="outline">Create Crawl</Button>
              </Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Project</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead className="text-right">Errors</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead className="text-right">Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentCrawls.map((crawl: CrawlSummary) => {
                  const project = projectMap.get(crawl.project_id);
                  const isActive = ["crawling", "queued", "paused"].includes(crawl.status);
                  return (
                    <TableRow key={crawl.id}>
                      <TableCell><StatusBadge status={crawl.status} /></TableCell>
                      <TableCell className="font-mono text-xs max-w-[180px] truncate" title={String(crawl.config?.start_url || "")}>
                        {getStartUrl(crawl.config)}
                      </TableCell>
                      <TableCell className="text-sm max-w-[120px] truncate">
                        <span
                          className="text-muted-foreground hover:text-foreground cursor-pointer hover:underline"
                          onClick={() => document.getElementById("projects-section")?.scrollIntoView({ behavior: "smooth" })}
                        >
                          {project?.name || crawl.project_id.slice(0, 8) + "..."}
                        </span>
                      </TableCell>
                      <TableCell>
                        <ProgressBar crawled={crawl.crawled_urls_count} total={crawl.total_urls} />
                      </TableCell>
                      <TableCell className="text-right">
                        {crawl.error_count > 0 ? (
                          <span className="text-red-500">{crawl.error_count}</span>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground text-sm">
                        {formatDuration(crawl.started_at, crawl.completed_at)}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground text-sm">
                        {formatTime(crawl.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Link href={`/crawls/${crawl.id}`}>
                            <Button variant="ghost" size="sm">View</Button>
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
                                if (confirm("Delete this crawl and all its data?")) {
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
          )}
        </CardContent>
      </Card>
    </div>
  );
}
