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
import { projectsApi, crawlsApi, configProfilesApi } from "@/lib/api-client";
import type { CrawlMode, CrawlConfig, Project, CustomExtractorCreate, CustomSearchCreate, ConfigProfile } from "@/types";
import { DEFAULT_CRAWL_CONFIG } from "@/types";
import { Plus, Trash2, Braces, Search, FileSliders } from "lucide-react";

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
  const [localExtractors, setLocalExtractors] = useState<CustomExtractorCreate[]>([]);
  const [localSearches, setLocalSearches] = useState<CustomSearchCreate[]>([]);

  // Fetch config profiles
  const { data: profiles = [] } = useQuery({
    queryKey: ["config-profiles"],
    queryFn: () => configProfilesApi.list(),
  });

  const applyProfile = (profile: ConfigProfile) => {
    const c = profile.config;
    setConfig((prev) => ({
      ...prev,
      max_urls: c.max_urls ?? prev.max_urls,
      max_depth: c.max_depth ?? prev.max_depth,
      max_threads: c.max_threads ?? prev.max_threads,
      rate_limit_rps: c.rate_limit_rps ?? prev.rate_limit_rps,
      user_agent: c.user_agent ?? prev.user_agent,
      respect_robots: c.respect_robots ?? prev.respect_robots,
    }));
    // Match UA preset if possible
    const ua = c.user_agent ?? "SEOSpider/1.0";
    const matchingPreset = Object.entries(UA_PRESETS).find(([, v]) => v === ua);
    if (matchingPreset) setUaPreset(matchingPreset[0]);
    else setUaPreset("default");
  };

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

        const validExtractors = localExtractors.filter((r) => r.name.trim() && r.selector.trim());
        const validSearches = localSearches.filter((s) => s.name.trim() && s.pattern.trim());

        const crawl = await crawlsApi.start(project.id, {
          start_url: urls[0],
          mode: "list",
          urls,
          config,
          custom_extractors: validExtractors,
          custom_searches: validSearches,
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
      const validExtractors = localExtractors.filter((r) => r.name.trim() && r.selector.trim());
      const validSearches = localSearches.filter((s) => s.name.trim() && s.pattern.trim());

      const crawl = await crawlsApi.start(project.id, {
        start_url: url,
        mode,
        config,
        custom_extractors: validExtractors,
        custom_searches: validSearches,
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

  const addExtractor = () => {
    setLocalExtractors((prev) => [
      ...prev,
      { name: "", selector: "", method: "css", extract_type: "text", attribute_name: null },
    ]);
  };

  const updateExtractor = (index: number, partial: Partial<CustomExtractorCreate>) => {
    setLocalExtractors((prev) => prev.map((r, i) => (i === index ? { ...r, ...partial } : r)));
  };

  const removeExtractor = (index: number) => {
    setLocalExtractors((prev) => prev.filter((_, i) => i !== index));
  };

  const addSearch = () => {
    setLocalSearches((prev) => [
      ...prev,
      { name: "", pattern: "", is_regex: false, case_sensitive: false, contains: true },
    ]);
  };

  const updateSearch = (index: number, partial: Partial<CustomSearchCreate>) => {
    setLocalSearches((prev) => prev.map((s, i) => (i === index ? { ...s, ...partial } : s)));
  };

  const removeSearch = (index: number) => {
    setLocalSearches((prev) => prev.filter((_, i) => i !== index));
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
          <div className="flex items-center justify-between">
            <CardTitle>Crawl Configuration</CardTitle>
            {profiles.length > 0 && (
              <Select
                onValueChange={(profileId) => {
                  const p = profiles.find((pr: ConfigProfile) => pr.id === profileId);
                  if (p) applyProfile(p);
                }}
              >
                <SelectTrigger className="w-48">
                  <FileSliders className="mr-1.5 h-3.5 w-3.5 text-gray-400" />
                  <SelectValue placeholder="Load Profile..." />
                </SelectTrigger>
                <SelectContent>
                  {profiles.map((p: ConfigProfile) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                      {p.is_default && (
                        <span className="ml-1 text-xs text-gray-400">(default)</span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
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

          {/* Authentication */}
          <div className="border-t pt-4">
            <label className="text-sm font-medium mb-2 block">
              Authentication (optional)
            </label>
            <Select
              value={config.auth_type || "none"}
              onValueChange={(v) => updateConfig({ auth_type: v === "none" ? null : v })}
            >
              <SelectTrigger className="mb-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No Authentication</SelectItem>
                <SelectItem value="basic">HTTP Basic Auth</SelectItem>
                <SelectItem value="bearer">Bearer Token</SelectItem>
              </SelectContent>
            </Select>
            {config.auth_type === "basic" && (
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="Username"
                  value={config.auth_username || ""}
                  onChange={(e) => updateConfig({ auth_username: e.target.value || null })}
                />
                <Input
                  type="password"
                  placeholder="Password"
                  value={config.auth_password || ""}
                  onChange={(e) => updateConfig({ auth_password: e.target.value || null })}
                />
              </div>
            )}
            {config.auth_type === "bearer" && (
              <Input
                placeholder="Bearer token"
                value={config.auth_token || ""}
                onChange={(e) => updateConfig({ auth_token: e.target.value || null })}
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* URL Filtering */}
      <Card>
        <CardHeader>
          <CardTitle>URL Filtering & Rewriting</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium mb-1 block">
                Include Patterns
              </label>
              <textarea
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                placeholder={"*/blog/*\n*/products/*"}
                value={config.include_patterns.join("\n")}
                onChange={(e) =>
                  updateConfig({
                    include_patterns: e.target.value
                      .split("\n")
                      .map((l) => l.trim())
                      .filter((l) => l.length > 0),
                  })
                }
                rows={3}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Only crawl URLs matching these glob patterns. Leave empty to crawl all.
              </p>
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">
                Exclude Patterns
              </label>
              <textarea
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                placeholder={"*/tag/*\n*/page/*\n*.pdf"}
                value={config.exclude_patterns.join("\n")}
                onChange={(e) =>
                  updateConfig({
                    exclude_patterns: e.target.value
                      .split("\n")
                      .map((l) => l.trim())
                      .filter((l) => l.length > 0),
                  })
                }
                rows={3}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Skip URLs matching these glob patterns.
              </p>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-1 block">
              Strip Query Parameters
            </label>
            <Input
              placeholder="utm_source, utm_medium, fbclid, ref (comma-separated)"
              value={config.strip_query_params.join(", ")}
              onChange={(e) =>
                updateConfig({
                  strip_query_params: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter((s) => s.length > 0),
                })
              }
            />
            <p className="text-xs text-muted-foreground mt-1">
              Remove these query parameters from URLs before crawling to reduce duplicates.
            </p>
          </div>

          {/* JS Rendering Toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="render-js"
              checked={config.render_js}
              onChange={(e) =>
                updateConfig({ render_js: e.target.checked })
              }
              className="rounded"
            />
            <label htmlFor="render-js" className="text-sm font-medium">
              Enable JavaScript Rendering
            </label>
            <span className="text-xs text-muted-foreground">
              (Uses headless Chrome — slower but captures dynamic content)
            </span>
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
            <Button variant="outline" size="sm" onClick={addExtractor} className="gap-1">
              <Plus className="h-3.5 w-3.5" />
              Add Rule
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {localExtractors.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No extraction rules configured. Add rules to extract custom data from each crawled page using CSS selectors, XPath, or Regex.
            </p>
          ) : (
            localExtractors.map((extractor, i) => (
              <div key={i} className="flex items-start gap-2 p-3 rounded-md border border-gray-200 bg-gray-50">
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <Input
                    placeholder="Rule name (e.g. price)"
                    value={extractor.name}
                    onChange={(e) => updateExtractor(i, { name: e.target.value })}
                    className="text-sm"
                  />
                  <Input
                    placeholder={extractor.method === "css" ? "CSS selector (e.g. .price)" : extractor.method === "xpath" ? "XPath (e.g. //h1)" : "Regex (e.g. \\d+)"}
                    value={extractor.selector}
                    onChange={(e) => updateExtractor(i, { selector: e.target.value })}
                    className="text-sm font-mono"
                  />
                  <Select
                    value={extractor.method}
                    onValueChange={(v) => updateExtractor(i, { method: v as "css" | "xpath" | "regex" })}
                  >
                    <SelectTrigger className="text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="css">CSS Selector</SelectItem>
                      <SelectItem value="xpath">XPath</SelectItem>
                      <SelectItem value="regex">Regex</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select
                    value={extractor.extract_type || "text"}
                    onValueChange={(v) => updateExtractor(i, { extract_type: v as "text" | "html" | "inner_html" | "attribute" })}
                  >
                    <SelectTrigger className="text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="text">Inner Text</SelectItem>
                      <SelectItem value="inner_html">Inner HTML</SelectItem>
                      <SelectItem value="html">Outer HTML</SelectItem>
                      <SelectItem value="attribute">Attribute Value</SelectItem>
                    </SelectContent>
                  </Select>
                  {extractor.extract_type === "attribute" && (
                    <Input
                      placeholder="Attribute name (e.g. href)"
                      value={extractor.attribute_name ?? ""}
                      onChange={(e) => updateExtractor(i, { attribute_name: e.target.value || null })}
                      className="text-sm font-mono col-span-2"
                    />
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeExtractor(i)}
                  className="text-gray-400 hover:text-red-500 mt-0.5"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Custom Search Rules */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              Custom Searches
            </CardTitle>
            <Button variant="outline" size="sm" onClick={addSearch} className="gap-1">
              <Plus className="h-3.5 w-3.5" />
              Add Search
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {localSearches.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No search rules configured. Add rules to find specific text or patterns in the raw HTML of each page.
            </p>
          ) : (
            localSearches.map((search, i) => (
              <div key={i} className="flex items-start gap-2 p-3 rounded-md border border-gray-200 bg-gray-50">
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <Input
                    placeholder="Search name (e.g. Google Analytics)"
                    value={search.name}
                    onChange={(e) => updateSearch(i, { name: e.target.value })}
                    className="text-sm"
                  />
                  <Input
                    placeholder={search.is_regex ? "Regex pattern (e.g. UA-\\d+)" : "Literal text (e.g. GTM-XXXXX)"}
                    value={search.pattern}
                    onChange={(e) => updateSearch(i, { pattern: e.target.value })}
                    className="text-sm font-mono"
                  />
                  <div className="col-span-2 flex items-center gap-4 text-sm mt-1">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={search.is_regex}
                        onChange={(e) => updateSearch(i, { is_regex: e.target.checked })}
                        className="rounded"
                      />
                      Regex
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={search.case_sensitive}
                        onChange={(e) => updateSearch(i, { case_sensitive: e.target.checked })}
                        className="rounded"
                      />
                      Case Sensitive
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer ml-auto">
                      <span>Flag if:</span>
                      <Select
                        value={search.contains ? "contains" : "does_not_contain"}
                        onValueChange={(v) => updateSearch(i, { contains: v === "contains" })}
                      >
                        <SelectTrigger className="h-8 w-36 text-xs bg-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="text-xs">
                          <SelectItem value="contains">Found</SelectItem>
                          <SelectItem value="does_not_contain">Not Found</SelectItem>
                        </SelectContent>
                      </Select>
                    </label>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeSearch(i)}
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
