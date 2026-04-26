"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/crawl/StatusBadge";
import { projectsApi, crawlsApi } from "@/lib/api-client";
import {
  ArrowLeft,
  Globe,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Clock,
  ExternalLink,
} from "lucide-react";
import type { CrawlSummary } from "@/types";

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(secs: number | null): string {
  if (!secs) return "\u2014";
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
}

function TrendIndicator({ current, previous, inverse = false }: { current: number; previous: number; inverse?: boolean }) {
  if (previous === 0 && current === 0) return <Minus className="h-3 w-3 text-gray-400" />;
  const diff = current - previous;
  const pct = previous > 0 ? Math.round((diff / previous) * 100) : 0;
  const isGood = inverse ? diff < 0 : diff > 0;
  const isBad = inverse ? diff > 0 : diff < 0;

  if (diff === 0) return <Minus className="h-3 w-3 text-gray-400" />;
  return (
    <span className={`flex items-center gap-0.5 text-xs ${isGood ? "text-green-600" : isBad ? "text-red-600" : "text-gray-500"}`}>
      {diff > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {pct !== 0 && <span>{Math.abs(pct)}%</span>}
    </span>
  );
}

function MiniChart({ data, color = "#6cc04a" }: { data: number[]; color?: string }) {
  if (data.length < 2) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const w = 200;
  const h = 40;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x},${y}`;
  });
  const pathD = `M ${points.join(" L ")}`;
  const areaD = `${pathD} L ${w},${h} L 0,${h} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-10" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0.05" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#grad-${color.replace("#", "")})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
}

export default function ProjectDetailPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const router = useRouter();

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId),
  });

  const { data: statsData, isLoading: statsLoading } = useQuery({
    queryKey: ["project-stats", projectId],
    queryFn: () => projectsApi.stats(projectId),
  });

  const { data: trendsData, isLoading: trendsLoading } = useQuery({
    queryKey: ["project-trends", projectId],
    queryFn: () => projectsApi.trends(projectId),
  });

  const { data: crawlsData } = useQuery({
    queryKey: ["project-crawls", projectId],
    queryFn: () => crawlsApi.listForProject(projectId, null, 50),
  });

  const crawls = crawlsData?.items ?? [];
  const trends = trendsData?.trends ?? [];
  const history = statsData?.crawl_history ?? [];
  const latest = history[0] || null;
  const previous = history[1] || null;

  const urlsTrend = trends.map((t: any) => t.urls_crawled as number);
  const errorsTrend = trends.map((t: any) => t.errors as number);
  const issuesTrend = trends.map((t: any) => t.total_issues as number);
  const responseTimeTrend = trends.map((t: any) => (t.avg_response_ms ?? 0) as number);

  return (
    <div className="space-y-6 p-6 overflow-auto flex-1">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Globe className="h-5 w-5 text-gray-400" />
            {project?.name || "Loading..."}
          </h1>
          {project && (
            <p className="text-sm text-muted-foreground font-mono">{project.domain}</p>
          )}
        </div>
        <div className="ml-auto flex gap-2">
          <Link href="/crawls/new">
            <Button size="sm">New Crawl</Button>
          </Link>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-gray-500">URLs Crawled</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold">{latest?.urls_crawled?.toLocaleString() ?? "\u2014"}</span>
              {previous && latest && (
                <TrendIndicator current={latest.urls_crawled} previous={previous.urls_crawled} />
              )}
            </div>
            <MiniChart data={urlsTrend} color="#6cc04a" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-gray-500">Errors</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-bold ${(latest?.errors ?? 0) > 0 ? "text-red-600" : ""}`}>
                {latest?.errors?.toLocaleString() ?? "\u2014"}
              </span>
              {previous && latest && (
                <TrendIndicator current={latest.errors} previous={previous.errors} inverse />
              )}
            </div>
            <MiniChart data={errorsTrend} color="#ef4444" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-gray-500 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> Issues
            </CardTitle>
          </CardHeader>
          <CardContent>
            {trends.length > 0 ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold">{trends[trends.length - 1]?.total_issues?.toLocaleString() ?? "\u2014"}</span>
                  {trends.length >= 2 && (
                    <TrendIndicator
                      current={trends[trends.length - 1]?.total_issues ?? 0}
                      previous={trends[trends.length - 2]?.total_issues ?? 0}
                      inverse
                    />
                  )}
                </div>
                <MiniChart data={issuesTrend} color="#f59e0b" />
              </>
            ) : (
              <span className="text-2xl font-bold text-gray-300">{"\u2014"}</span>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-gray-500 flex items-center gap-1">
              <Clock className="h-3 w-3" /> Avg Response
            </CardTitle>
          </CardHeader>
          <CardContent>
            {trends.length > 0 ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold">
                    {trends[trends.length - 1]?.avg_response_ms ? `${trends[trends.length - 1].avg_response_ms}ms` : "\u2014"}
                  </span>
                  {trends.length >= 2 && trends[trends.length - 1]?.avg_response_ms && (
                    <TrendIndicator
                      current={trends[trends.length - 1]?.avg_response_ms ?? 0}
                      previous={trends[trends.length - 2]?.avg_response_ms ?? 0}
                      inverse
                    />
                  )}
                </div>
                <MiniChart data={responseTimeTrend} color="#3b82f6" />
              </>
            ) : (
              <span className="text-2xl font-bold text-gray-300">{"\u2014"}</span>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Trend Details Table */}
      {trends.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Crawl Trends</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr className="border-b">
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Date</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">URLs</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Errors</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Issues</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Critical</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Warnings</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Avg Response</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Duration</th>
                    <th className="text-center py-2 px-2 font-medium text-gray-600 w-16"></th>
                  </tr>
                </thead>
                <tbody>
                  {[...trends].reverse().map((t: any, i: number) => (
                    <tr key={t.crawl_id} className="border-b border-gray-100 hover:bg-blue-50/30">
                      <td className="py-1.5 px-2 text-gray-700">{formatDate(t.started_at)}</td>
                      <td className="py-1.5 px-2 text-right font-mono">{t.urls_crawled?.toLocaleString()}</td>
                      <td className={`py-1.5 px-2 text-right font-mono ${t.errors > 0 ? "text-red-600" : "text-gray-400"}`}>
                        {t.errors}
                      </td>
                      <td className="py-1.5 px-2 text-right font-mono">{t.total_issues}</td>
                      <td className={`py-1.5 px-2 text-right font-mono ${t.critical_issues > 0 ? "text-red-600 font-semibold" : "text-gray-400"}`}>
                        {t.critical_issues}
                      </td>
                      <td className={`py-1.5 px-2 text-right font-mono ${t.warnings > 0 ? "text-amber-600" : "text-gray-400"}`}>
                        {t.warnings}
                      </td>
                      <td className="py-1.5 px-2 text-right font-mono text-gray-600">
                        {t.avg_response_ms ? `${t.avg_response_ms}ms` : "-"}
                      </td>
                      <td className="py-1.5 px-2 text-right text-gray-500">{formatDuration(t.duration_secs)}</td>
                      <td className="py-1.5 px-2 text-center">
                        <Link href={`/crawls/${t.crawl_id}`} className="text-blue-600 hover:text-blue-800">
                          <ExternalLink className="h-3 w-3 inline" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Crawl History */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">All Crawls</CardTitle>
        </CardHeader>
        <CardContent>
          {crawls.length === 0 ? (
            <p className="text-center text-gray-400 py-8">No crawls yet for this project.</p>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr className="border-b">
                    <th className="text-left py-2 px-2 font-medium text-gray-600 w-20">Status</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Mode</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">URLs</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Errors</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Started</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Completed</th>
                    <th className="text-center py-2 px-2 font-medium text-gray-600 w-16"></th>
                  </tr>
                </thead>
                <tbody>
                  {crawls.map((c: CrawlSummary) => (
                    <tr key={c.id} className="border-b border-gray-100 hover:bg-blue-50/30">
                      <td className="py-1.5 px-2"><StatusBadge status={c.status} /></td>
                      <td className="py-1.5 px-2 text-gray-600 capitalize">{c.mode}</td>
                      <td className="py-1.5 px-2 text-right font-mono">{c.crawled_urls_count.toLocaleString()}</td>
                      <td className={`py-1.5 px-2 text-right font-mono ${c.error_count > 0 ? "text-red-600" : "text-gray-400"}`}>
                        {c.error_count}
                      </td>
                      <td className="py-1.5 px-2 text-gray-500">{formatDate(c.started_at)}</td>
                      <td className="py-1.5 px-2 text-gray-500">{formatDate(c.completed_at)}</td>
                      <td className="py-1.5 px-2 text-center">
                        <Link href={`/crawls/${c.id}`}>
                          <Button variant="ghost" size="sm" className="h-6 text-xs">View</Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
