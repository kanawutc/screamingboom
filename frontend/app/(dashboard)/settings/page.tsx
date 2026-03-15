"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useState, useEffect } from "react";
import { Settings, Globe, Bot, Shield, Check } from "lucide-react";

const STORAGE_KEY = "seo-spider-settings";

const USER_AGENT_PRESETS: Record<string, string> = {
  default: "SEOSpider/1.0",
  googlebot: "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
  bingbot: "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
  custom: "",
};

const DEFAULT_SETTINGS = {
  maxUrls: 10000,
  maxDepth: 10,
  concurrency: 5,
  rateLimitRps: 2,
  userAgent: "SEOSpider/1.0",
  respectRobots: true,
  userAgentPreset: "default",
};

export default function SettingsPage() {
  const [defaults, setDefaults] = useState(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) setDefaults({ ...DEFAULT_SETTINGS, ...JSON.parse(stored) });
    } catch { /* ignore corrupt data */ }
  }, []);

  const handleSave = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(defaults));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch { /* storage full — ignore */ }
  };

  const handlePresetChange = (preset: string) => {
    const ua = USER_AGENT_PRESETS[preset] ?? defaults.userAgent;
    setDefaults({ ...defaults, userAgentPreset: preset, userAgent: preset === "custom" ? defaults.userAgent : ua });
  };

  return (
    <div className="space-y-6 p-6 overflow-auto flex-1">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Settings</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Default Crawl Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium">Max URLs per Crawl</p>
              <Input
                id="maxUrls"
                type="number"
                value={defaults.maxUrls}
                onChange={(e) =>
                  setDefaults({ ...defaults, maxUrls: Number(e.target.value) })
                }
                min={0}
                max={100000000}
              />
              <p className="text-xs text-muted-foreground mt-1">0 = unlimited</p>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Max Crawl Depth</p>
              <Input
                id="maxDepth"
                type="number"
                value={defaults.maxDepth}
                onChange={(e) =>
                  setDefaults({ ...defaults, maxDepth: Number(e.target.value) })
                }
                min={1}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Concurrency (Threads)</p>
              <Input
                id="concurrency"
                type="number"
                value={defaults.concurrency}
                onChange={(e) =>
                  setDefaults({
                    ...defaults,
                    concurrency: Number(e.target.value),
                  })
                }
                min={1}
                max={50}
              />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Rate Limit (req/s)</p>
              <Input
                id="rateLimit"
                type="number"
                value={defaults.rateLimitRps}
                onChange={(e) =>
                  setDefaults({
                    ...defaults,
                    rateLimitRps: Number(e.target.value),
                  })
                }
                min={0.1}
                max={100}
                step={0.1}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            User Agent
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <p className="text-sm font-medium">User Agent Preset</p>
            <Select
              value={defaults.userAgentPreset}
              onValueChange={handlePresetChange}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">SEO Spider (Default)</SelectItem>
                <SelectItem value="googlebot">Googlebot</SelectItem>
                <SelectItem value="bingbot">Bingbot</SelectItem>
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium">User Agent String</p>
            <Input
              id="userAgentString"
              value={defaults.userAgent}
              onChange={(e) =>
                setDefaults({ ...defaults, userAgent: e.target.value })
              }
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Crawl Behavior
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Respect robots.txt</p>
              <p className="text-sm text-muted-foreground">
                Follow robots.txt directives when crawling
              </p>
            </div>
            <input
              type="checkbox"
              className="h-5 w-5 rounded border-gray-300"
              checked={defaults.respectRobots}
              onChange={(e) =>
                setDefaults({ ...defaults, respectRobots: e.target.checked })
              }
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button size="lg" onClick={handleSave}>
          {saved ? <Check className="h-4 w-4 mr-2" /> : <Settings className="h-4 w-4 mr-2" />}
          {saved ? "Saved!" : "Save Settings"}
        </Button>
      </div>
    </div>
  );
}
