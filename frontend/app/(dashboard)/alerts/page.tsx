"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { alertsApi } from "@/lib/api-client";
import {
  Bell,
  CheckCheck,
  Trash2,
  AlertTriangle,
  AlertCircle,
  Info,
  TrendingDown,
  TrendingUp,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import type { AlertItem } from "@/types";

const SEVERITY_STYLES: Record<string, { bg: string; text: string; icon: typeof AlertTriangle }> = {
  critical: { bg: "bg-red-50 border-red-200", text: "text-red-700", icon: AlertCircle },
  warning: { bg: "bg-amber-50 border-amber-200", text: "text-amber-700", icon: AlertTriangle },
  info: { bg: "bg-blue-50 border-blue-200", text: "text-blue-700", icon: Info },
};

const TYPE_LABELS: Record<string, string> = {
  health_regression: "Health Regression",
  health_improvement: "Health Improvement",
  low_health: "Low Health Score",
  error_spike: "Error Rate Spike",
  high_errors: "High Error Count",
  critical_issues: "Critical Issues",
  issues_increased: "Issues Increased",
  slow_site: "Slow Response Times",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString();
}

export default function AlertsPage() {
  const queryClient = useQueryClient();

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => alertsApi.list(undefined, false, 100),
    refetchInterval: 30000,
  });

  const { data: unreadData } = useQuery({
    queryKey: ["alerts-unread"],
    queryFn: () => alertsApi.unreadCount(),
    refetchInterval: 30000,
  });

  const markReadMutation = useMutation({
    mutationFn: (alertId: string) => alertsApi.markRead(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["alerts-unread"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (alertId: string) => alertsApi.delete(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["alerts-unread"] });
    },
  });

  const unreadCount = unreadData?.unread_count ?? 0;
  const unreadAlerts = alerts.filter((a: AlertItem) => !a.is_read);
  const readAlerts = alerts.filter((a: AlertItem) => a.is_read);

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Alerts
            {unreadCount > 0 && (
              <Badge className="bg-red-500 text-white ml-1">{unreadCount}</Badge>
            )}
          </h1>
          <p className="text-sm text-gray-500">
            Automated monitoring alerts from crawl analysis
          </p>
        </div>
      </div>

      {isLoading ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-500">
            <RefreshCw className="mx-auto mb-3 h-6 w-6 animate-spin text-gray-400" />
            <p className="text-sm">Loading alerts...</p>
          </CardContent>
        </Card>
      ) : alerts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-500">
            <Bell className="mx-auto mb-3 h-10 w-10 text-gray-300" />
            <p className="text-sm font-medium">No alerts yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Alerts are generated automatically after each crawl completes
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {unreadAlerts.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-700 mb-2">
                Unread ({unreadAlerts.length})
              </h2>
              <div className="space-y-2">
                {unreadAlerts.map((alert: AlertItem) => {
                  const style = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.info;
                  const Icon = style.icon;
                  return (
                    <Card key={alert.id} className={`border ${style.bg}`}>
                      <CardContent className="py-3 px-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3 flex-1">
                            <Icon className={`h-4 w-4 mt-0.5 ${style.text}`} />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-0.5">
                                <span className="text-sm font-semibold text-gray-900">
                                  {alert.title}
                                </span>
                                <Badge variant="secondary" className="text-[10px]">
                                  {TYPE_LABELS[alert.alert_type] || alert.alert_type}
                                </Badge>
                              </div>
                              <p className="text-xs text-gray-600">{alert.description}</p>
                              {(alert.metric_before !== null || alert.metric_after !== null) && (
                                <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                                  {alert.metric_before !== null && (
                                    <span>Before: {alert.metric_before}</span>
                                  )}
                                  {alert.metric_before !== null && alert.metric_after !== null && (
                                    alert.metric_after > alert.metric_before
                                      ? <TrendingUp className="h-3 w-3 text-emerald-500" />
                                      : <TrendingDown className="h-3 w-3 text-red-500" />
                                  )}
                                  {alert.metric_after !== null && (
                                    <span>After: {alert.metric_after}</span>
                                  )}
                                </div>
                              )}
                              <div className="flex items-center gap-3 mt-1.5">
                                <span className="text-[10px] text-gray-400">
                                  {formatDate(alert.created_at)}
                                </span>
                                <Link
                                  href={`/crawls/${alert.crawl_id}`}
                                  className="text-[10px] text-blue-500 hover:underline flex items-center gap-0.5"
                                >
                                  View Crawl <ExternalLink className="h-2.5 w-2.5" />
                                </Link>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => markReadMutation.mutate(alert.id)}
                              title="Mark as read"
                            >
                              <CheckCheck className="h-3.5 w-3.5 text-gray-400" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => deleteMutation.mutate(alert.id)}
                              title="Delete"
                            >
                              <Trash2 className="h-3.5 w-3.5 text-gray-400" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {readAlerts.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-500 mb-2">
                Read ({readAlerts.length})
              </h2>
              <div className="space-y-2">
                {readAlerts.map((alert: AlertItem) => (
                  <Card key={alert.id} className="border border-gray-100 opacity-60">
                    <CardContent className="py-2.5 px-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs text-gray-600 truncate">
                            {alert.title}
                          </span>
                          <span className="text-[10px] text-gray-400 shrink-0">
                            {formatDate(alert.created_at)}
                          </span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteMutation.mutate(alert.id)}
                        >
                          <Trash2 className="h-3 w-3 text-gray-400" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
