"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { projectsApi, schedulesApi } from "@/lib/api-client";
import {
  Clock,
  Plus,
  Trash2,
  Play,
  Pause,
  Calendar,
  Globe,
  RefreshCw,
} from "lucide-react";
import type {
  Project,
  CrawlSchedule,
  ScheduleCreate,
  ScheduleCrawlConfig,
} from "@/types";

const CRON_PRESETS = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Every 12 hours", value: "0 */12 * * *" },
  { label: "Daily at midnight", value: "0 0 * * *" },
  { label: "Daily at 2am", value: "0 2 * * *" },
  { label: "Weekly (Monday 2am)", value: "0 2 * * 1" },
  { label: "Weekly (Sunday midnight)", value: "0 0 * * 0" },
  { label: "Monthly (1st at 2am)", value: "0 2 1 * *" },
  { label: "Custom", value: "custom" },
];

function describeCron(cron: string): string {
  const parts = cron.split(" ");
  if (parts.length !== 5) return cron;
  const [min, hour, dom, , dow] = parts;

  if (min === "0" && hour === "*") return "Every hour";
  if (min === "0" && hour.startsWith("*/"))
    return `Every ${hour.replace("*/", "")} hours`;
  if (dom === "1" && dow === "*" && min === "0")
    return `Monthly on 1st at ${hour}:00`;
  if (dow !== "*" && dom === "*") {
    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const day = days[parseInt(dow)] || dow;
    return `Weekly on ${day} at ${hour}:${min.padStart(2, "0")}`;
  }
  if (dom === "*" && dow === "*" && hour !== "*")
    return `Daily at ${hour}:${min.padStart(2, "0")}`;
  return cron;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function SchedulesPage() {
  const queryClient = useQueryClient();
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [dialogOpen, setDialogOpen] = useState(false);

  // Form state
  const [formName, setFormName] = useState("");
  const [cronPreset, setCronPreset] = useState("0 2 * * 1");
  const [customCron, setCustomCron] = useState("");
  const [startUrl, setStartUrl] = useState("");
  const [maxUrls, setMaxUrls] = useState(10000);
  const [maxDepth, setMaxDepth] = useState(10);
  const [maxThreads, setMaxThreads] = useState(5);
  const [rateLimitRps, setRateLimitRps] = useState(2);

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(null, 200),
  });
  const projects = projectsData?.items ?? [];

  const { data: schedules = [], isLoading } = useQuery({
    queryKey: ["schedules", selectedProjectId],
    queryFn: () => schedulesApi.list(selectedProjectId),
    enabled: !!selectedProjectId,
  });

  const createMutation = useMutation({
    mutationFn: (data: ScheduleCreate) =>
      schedulesApi.create(selectedProjectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules", selectedProjectId] });
      setDialogOpen(false);
      resetForm();
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({
      scheduleId,
      is_active,
    }: {
      scheduleId: string;
      is_active: boolean;
    }) => schedulesApi.update(selectedProjectId, scheduleId, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules", selectedProjectId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (scheduleId: string) =>
      schedulesApi.delete(selectedProjectId, scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules", selectedProjectId] });
    },
  });

  function resetForm() {
    setFormName("");
    setCronPreset("0 2 * * 1");
    setCustomCron("");
    setStartUrl("");
    setMaxUrls(10000);
    setMaxDepth(10);
    setMaxThreads(5);
    setRateLimitRps(2);
  }

  function handleCreate() {
    const cronExpr = cronPreset === "custom" ? customCron : cronPreset;
    if (!formName.trim() || !cronExpr.trim()) return;

    const config: ScheduleCrawlConfig = {
      max_urls: maxUrls,
      max_depth: maxDepth,
      max_threads: maxThreads,
      rate_limit_rps: rateLimitRps,
    };
    if (startUrl.trim()) config.start_url = startUrl.trim();

    createMutation.mutate({
      name: formName.trim(),
      cron_expression: cronExpr,
      crawl_config: config,
      is_active: true,
    });
  }

  // Auto-select first project
  if (!selectedProjectId && projects.length > 0) {
    setSelectedProjectId(projects[0].id);
  }

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Crawl Schedules</h1>
          <p className="text-sm text-gray-500">
            Configure recurring crawls for your projects
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={selectedProjectId}
            onValueChange={setSelectedProjectId}
          >
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Select a project..." />
            </SelectTrigger>
            <SelectContent>
              {projects.map((p: Project) => (
                <SelectItem key={p.id} value={p.id}>
                  <span className="flex items-center gap-2">
                    <Globe className="h-3.5 w-3.5 text-gray-400" />
                    {p.name}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button
                size="sm"
                disabled={!selectedProjectId}
                className="bg-[#6cc04a] hover:bg-[#5aaa3c]"
              >
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                New Schedule
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Create Crawl Schedule</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-2">
                <div>
                  <label className="text-xs font-medium text-gray-600">
                    Schedule Name
                  </label>
                  <Input
                    placeholder="e.g. Weekly SEO Audit"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-600">
                    Frequency
                  </label>
                  <Select value={cronPreset} onValueChange={setCronPreset}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CRON_PRESETS.map((p) => (
                        <SelectItem key={p.value} value={p.value}>
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {cronPreset === "custom" && (
                    <Input
                      placeholder="e.g. 0 2 * * 1,4"
                      value={customCron}
                      onChange={(e) => setCustomCron(e.target.value)}
                      className="mt-2"
                    />
                  )}
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-600">
                    Start URL (optional — defaults to project domain)
                  </label>
                  <Input
                    placeholder="https://example.com"
                    value={startUrl}
                    onChange={(e) => setStartUrl(e.target.value)}
                    className="mt-1"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600">
                      Max URLs
                    </label>
                    <Input
                      type="number"
                      value={maxUrls}
                      onChange={(e) => setMaxUrls(Number(e.target.value))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">
                      Max Depth
                    </label>
                    <Input
                      type="number"
                      value={maxDepth}
                      onChange={(e) => setMaxDepth(Number(e.target.value))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">
                      Threads
                    </label>
                    <Input
                      type="number"
                      value={maxThreads}
                      onChange={(e) => setMaxThreads(Number(e.target.value))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">
                      Rate Limit (req/s)
                    </label>
                    <Input
                      type="number"
                      step="0.5"
                      value={rateLimitRps}
                      onChange={(e) => setRateLimitRps(Number(e.target.value))}
                      className="mt-1"
                    />
                  </div>
                </div>

                <Button
                  onClick={handleCreate}
                  disabled={
                    !formName.trim() ||
                    (cronPreset === "custom" && !customCron.trim()) ||
                    createMutation.isPending
                  }
                  className="w-full bg-[#6cc04a] hover:bg-[#5aaa3c]"
                >
                  {createMutation.isPending ? (
                    <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Calendar className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  Create Schedule
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {!selectedProjectId ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-500">
            <Clock className="mx-auto mb-3 h-10 w-10 text-gray-300" />
            <p className="text-sm">Select a project to manage its crawl schedules</p>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-500">
            <RefreshCw className="mx-auto mb-3 h-6 w-6 animate-spin text-gray-400" />
            <p className="text-sm">Loading schedules...</p>
          </CardContent>
        </Card>
      ) : schedules.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-500">
            <Calendar className="mx-auto mb-3 h-10 w-10 text-gray-300" />
            <p className="text-sm font-medium">No schedules yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Create a schedule to automatically crawl on a recurring basis
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">
              {schedules.length} Schedule{schedules.length !== 1 ? "s" : ""}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Name</TableHead>
                  <TableHead>Frequency</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead>Next Run</TableHead>
                  <TableHead className="text-right pr-6">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedules.map((s: CrawlSchedule) => (
                  <TableRow key={s.id}>
                    <TableCell className="pl-6 font-medium text-sm">
                      {s.name}
                    </TableCell>
                    <TableCell className="text-xs text-gray-600">
                      <span className="flex items-center gap-1.5">
                        <Clock className="h-3 w-3 text-gray-400" />
                        {describeCron(s.cron_expression)}
                      </span>
                      <span className="text-[10px] text-gray-400 font-mono mt-0.5 block">
                        {s.cron_expression}
                      </span>
                    </TableCell>
                    <TableCell>
                      {s.is_active ? (
                        <Badge
                          variant="default"
                          className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100"
                        >
                          Active
                        </Badge>
                      ) : (
                        <Badge variant="secondary">Paused</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-gray-500">
                      {formatDate(s.last_run_at)}
                    </TableCell>
                    <TableCell className="text-xs text-gray-500">
                      {s.is_active ? formatDate(s.next_run_at) : "—"}
                    </TableCell>
                    <TableCell className="text-right pr-6">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            toggleMutation.mutate({
                              scheduleId: s.id,
                              is_active: !s.is_active,
                            })
                          }
                          title={s.is_active ? "Pause" : "Resume"}
                        >
                          {s.is_active ? (
                            <Pause className="h-3.5 w-3.5 text-amber-600" />
                          ) : (
                            <Play className="h-3.5 w-3.5 text-emerald-600" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (
                              confirm(
                                `Delete schedule "${s.name}"?`
                              )
                            ) {
                              deleteMutation.mutate(s.id);
                            }
                          }}
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5 text-red-500" />
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
    </div>
  );
}
