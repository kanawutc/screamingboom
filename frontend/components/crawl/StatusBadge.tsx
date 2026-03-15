"use client";

import { Badge } from "@/components/ui/badge";
import type { CrawlStatus } from "@/types";

const STATUS_CONFIG: Record<
  CrawlStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" ; className?: string }
> = {
  idle: { label: "Idle", variant: "secondary" },
  configuring: { label: "Configuring", variant: "secondary" },
  queued: { label: "Queued", variant: "outline", className: "border-blue-400 text-blue-600" },
  crawling: { label: "Crawling", variant: "default", className: "bg-green-600 hover:bg-green-700" },
  paused: { label: "Paused", variant: "outline", className: "border-yellow-400 text-yellow-600" },
  completing: { label: "Completing", variant: "default", className: "bg-blue-600 hover:bg-blue-700" },
  completed: { label: "Completed", variant: "default", className: "bg-emerald-600 hover:bg-emerald-700" },
  failed: { label: "Failed", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "secondary", className: "bg-gray-500 text-white hover:bg-gray-600" },
};

export function StatusBadge({ status }: { status: CrawlStatus }) {
  const config = STATUS_CONFIG[status] ?? { label: status, variant: "secondary" as const };
  return (
    <Badge variant={config.variant} className={config.className}>
      {config.label}
    </Badge>
  );
}
