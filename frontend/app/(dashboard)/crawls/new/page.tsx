"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { projectsApi, crawlsApi, extractionRulesApi } from "@/lib/api-client";
import type { CrawlMode, CrawlConfig, Project, ExtractionRule, ExtractionRuleCreate } from "@/types";
import { DEFAULT_CRAWL_CONFIG } from "@/types";
import { Plus, Trash2, Braces } from "lucide-react";

const UA_PRESETS: Record<string, string> = {
  default: "SEOSpider/1.0",
  googlebot_desktop:
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
  googlebot_mobile:
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
  bingbot:
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
  chrome_desktop:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
};

export default function NewCrawlPage() {
  const router = useRouter();
  const [mode, setMode] = useState<CrawlMode>("spider");
  const [startUrl, setStartUrl] = useState("");
  const [listUrlsText, setListUrlsText] = useState("");
  const [config, setConfig] = useState<CrawlConfig>(() => {
    // Load saved defaults from Settings page (localStorage)
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("seo-spider-settings");
        if (stored) {
          const s = JSON.parse(stored);
          return {
            ...DEFAULT_CRAWL_CONFIG,
            max_urls: s.maxUrls ?? DEFAULT_CRAWL_CONFIG.max_urls,
            max_depth: s.maxDepth ?? DEFAULT_CRAWL_CONFIG.max_depth,
            max_threads: s.concurrency ?? DEFAULT_CRAWL_CONFIG.max_threads,
            rate_limit_rps: s.rateLimitRps ?? DEFAULT_CRAWL_CONFIG.rate_limit_rps,
            user_agent: s.userAgent ?? DEFAULT_CRAWL_CONFIG.user_agent,
            respect_robots: s.respectRobots ?? DEFAULT_CRAWL_CONFIG.respect_robots,
          };
        }
      } catch { /* ignore corrupt data */ }
    }
    return { ...DEFAULT_CRAWL_CONFIG };
  });
  const [uaPreset, setUaPreset] = useState(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("seo-spider-settings");
        if (stored) {
          const s = JSON.parse(stored);
          if (s.userAgentPreset) return s.userAgentPreset;
        }
      } catch { /* ignore */ }
    }
    return "default";
  });
  const [error, setError] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [localRules, setLocalRules] = useState<ExtractionRuleCreate[]>([]);

  // Fetch or create default project
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(null, 100),
  });

  const projects = projectsData?.items ?? [];

  // Mutation to create project + start crawl
  const startCrawlMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      // Refetch projects to avoid stale closure creating duplicates
      const freshProjects = (await projectsApi.list(null, 100)).items ?? [];

      if (mode === "list") {
        // Parse URLs from textarea
        const rawLines = listUrlsText
          .split("\n")
          .map((l) => l.trim())
          .filter((l) => l.length > 0);

        if (rawLines.length === 0)
          throw new Error("Please enter at least one URL to crawl");

        // Normalize: auto-prepend https:// and deduplicate
        const urls = [
          ...new Set(
            rawLines.map((u) =>
              u.startsWith("http://") || u.startsWith("https://")
                ? u
                : "https://" + u
            )
          ),
        ];

        // Validate all URLs
        for (const u of urls) {
          try {
            new URL(u);
          } catch {
            throw new Error(`Invalid URL: ${u}`);
          }
        }

        // Extract domain from first URL
        const domain = new URL(urls[0]).hostname;

        // Find or create project
        let project = freshProjects.find((p: Project) => p.domain === domain);
        if (!project) {
          project = await projectsApi.create({
            name: domain,
            domain: domain,
          });
        }

        // Save extraction rules to project before starting crawl
        const validRules = localRules.filter((r) => r.name.trim() && r.selector.trim());
        for (const rule of validRules) {
          await extractionRulesApi.create(project.id, rule);
        }

        const crawl = await crawlsApi.start(project.id, {
          start_url: urls[0],
          mode: "list",
          urls,
          config,
        });

        return crawl;
      }

      // Spider mode
      let url = startUrl.trim();
      if (!url) throw new Error("Please enter a URL to crawl");
      if (!url.startsWith("http://") && !url.startsWith("https://")) {
        url = "https://" + url;
      }

      let domain: string;
      try {
        domain = new URL(url).hostname;
      } catch {
        throw new Error("Invalid URL. Please enter a valid URL.");
      }

      let project = freshProjects.find((p: Project) => p.domain === domain);
      if (!project) {
        project = await projectsApi.create({
          name: domain,
          domain: domain,
        });
      }

      // Save extraction rules to project before starting crawl
      const validRules = localRules.filter((r) => r.name.trim() && r.selector.trim());
      for (const rule of validRules) {
        await extractionRulesApi.create(project.id, rule);
      }

      const crawl = await crawlsApi.start(project.id, {
        start_url: url,
        mode,
        config,
      });

      return crawl;
    },
    onSuccess: (crawl) => {
      router.push(`/crawls/${crawl.id}`);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const updateConfig = (partial: Partial<CrawlConfig>) => {
    setConfig((prev) => ({ ...prev, ...partial }));
  };

  const handleUaPresetChange = (preset: string) => {
    setUaPreset(preset);
    updateConfig({ user_agent: UA_PRESETS[preset] ?? UA_PRESETS.default });
  };

  const addRule = () => {
    setLocalRules((prev) => [
      ...prev,
      { name: "", selector: "", selector_type: "css", extract_type: "text", attribute_name: null },
    ]);
  };

  const updateRule = (index: number, partial: Partial<ExtractionRuleCreate>) => {
    setLocalRules((prev) => prev.map((r, i) => (i === index ? { ...r, ...partial } : r)));
  };

  const removeRule = (index: number) => {
    setLocalRules((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-6 max-w-2xl p-6 overflow-auto flex-1">
      <h1 className="text-3xl font-bold">New Crawl</h1>

      {/* Mode selector */}
      <Tabs value={mode} onValueChange={(v) => setMode(v as CrawlMode)}>
        <TabsList>
          <TabsTrigger value="spider">Spider Mode</TabsTrigger>
          <TabsTrigger value="list">List Mode</TabsTrigger>
        </TabsList>

        <TabsContent value="spider" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Start URL</CardTitle>
            </CardHeader>
            <CardContent>
              <Input
                placeholder="https://example.com"
                value={startUrl}
                onChange={(e) => setStartUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") startCrawlMutation.mutate();
                }}
              />
              <p className="text-xs text-muted-foreground mt-1">
                The crawler will discover and follow links starting from this
                URL.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="list" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>URLs to Crawl</CardTitle>
            </CardHeader>
            <CardContent>
              <textarea
                className="flex min-h-[160px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 font-mono"
                placeholder={"https://example.com/page-1\nhttps://example.com/page-2\nhttps://example.com/page-3"}
                value={listUrlsText}
                onChange={(e) => setListUrlsText(e.target.value)}
                rows={8}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Enter one URL per line. Only these URLs will be crawled — no
                link discovery.
                {listUrlsText.trim() && (
                  <span className="ml-1 font-medium">
                    ({listUrlsText.split("\n").filter((l) => l.trim()).length}{" "}
                    URL{listUrlsText.split("\n").filter((l) => l.trim()).length !== 1 ? "s" : ""})
                  </span>
                )}
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Crawl Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium mb-1 block">
                Max URLs
              </label>
              <Input
                type="number"
                min={0}
                max={100000000}
                value={config.max_urls}
                onChange={(e) =>
                  updateConfig({ max_urls: parseInt(e.target.value) || 0 })
                }
              />
              <p className="text-xs text-muted-foreground mt-1">0 = unlimited</p>
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">
                Max Depth
              </label>
              <Input
                type="number"
                min={1}
                max={100}
                value={config.max_depth}
                onChange={(e) =>
                  updateConfig({ max_depth: parseInt(e.target.value) || 10 })
                }
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">
                Concurrency (Threads)
              </label>
              <Input
                type="number"
                min={1}
                max={50}
                value={config.max_threads}
                onChange={(e) =>
                  updateConfig({
                    max_threads: parseInt(e.target.value) || 5,
                  })
                }
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">
                Rate Limit (req/s)
              </label>
              <Input
                type="number"
                min={0.1}
                max={100}
                step={0.5}
                value={config.rate_limit_rps}
                onChange={(e) =>
                  updateConfig({
                    rate_limit_rps: parseFloat(e.target.value) || 2.0,
                  })
                }
              />
            </div>
          </div>

          {/* User Agent */}
          <div>
            <label className="text-sm font-medium mb-1 block">
              User Agent
            </label>
            <Select value={uaPreset} onValueChange={handleUaPresetChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">SEO Spider (Default)</SelectItem>
                <SelectItem value="googlebot_desktop">
                  Googlebot Desktop
                </SelectItem>
                <SelectItem value="googlebot_mobile">
                  Googlebot Mobile
                </SelectItem>
                <SelectItem value="bingbot">Bingbot</SelectItem>
                <SelectItem value="chrome_desktop">Chrome Desktop</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground mt-1 font-mono truncate">
              {config.user_agent}
            </p>
          </div>

          {/* Robots.txt */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="respect-robots"
              checked={config.respect_robots}
              onChange={(e) =>
                updateConfig({ respect_robots: e.target.checked })
              }
              className="rounded"
            />
            <label htmlFor="respect-robots" className="text-sm font-medium">
              Respect robots.txt
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Custom Extraction Rules */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Braces className="h-4 w-4" />
              Custom Extraction Rules
            </CardTitle>
            <Button variant="outline" size="sm" onClick={addRule} className="gap-1">
              <Plus className="h-3.5 w-3.5" />
              Add Rule
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {localRules.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No extraction rules configured. Add rules to extract custom data from each crawled page using CSS selectors or XPath.
            </p>
          ) : (
            localRules.map((rule, i) => (
              <div key={i} className="flex items-start gap-2 p-3 rounded-md border border-gray-200 bg-gray-50">
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <Input
                    placeholder="Rule name (e.g. price)"
                    value={rule.name}
                    onChange={(e) => updateRule(i, { name: e.target.value })}
                    className="text-sm"
                  />
                  <Input
                    placeholder={rule.selector_type === "css" ? "CSS selector (e.g. .price)" : "XPath (e.g. //h1)"}
                    value={rule.selector}
                    onChange={(e) => updateRule(i, { selector: e.target.value })}
                    className="text-sm font-mono"
                  />
                  <Select
                    value={rule.selector_type}
                    onValueChange={(v) => updateRule(i, { selector_type: v as "css" | "xpath" })}
                  >
                    <SelectTrigger className="text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="css">CSS Selector</SelectItem>
                      <SelectItem value="xpath">XPath</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select
                    value={rule.extract_type}
                    onValueChange={(v) => updateRule(i, { extract_type: v as "text" | "html" | "attribute" | "count" })}
                  >
                    <SelectTrigger className="text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="text">Inner Text</SelectItem>
                      <SelectItem value="html">Inner HTML</SelectItem>
                      <SelectItem value="attribute">Attribute Value</SelectItem>
                      <SelectItem value="count">Element Count</SelectItem>
                    </SelectContent>
                  </Select>
                  {rule.extract_type === "attribute" && (
                    <Input
                      placeholder="Attribute name (e.g. href)"
                      value={rule.attribute_name ?? ""}
                      onChange={(e) => updateRule(i, { attribute_name: e.target.value || null })}
                      className="text-sm font-mono col-span-2"
                    />
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeRule(i)}
                  className="text-gray-400 hover:text-red-500 mt-0.5"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {error && (
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Submit */}
      <div className="flex gap-3">
        <Button
          size="lg"
          onClick={() => startCrawlMutation.mutate()}
          disabled={
            startCrawlMutation.isPending ||
            (mode === "spider" && !startUrl.trim()) ||
            (mode === "list" && !listUrlsText.trim())
          }
        >
          {startCrawlMutation.isPending ? "Starting..." : "Start Crawl"}
        </Button>
        <Button variant="outline" size="lg" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
