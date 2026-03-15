"use client";

import { useEffect, useRef, useCallback } from "react";
import { getCrawlWsUrl } from "@/lib/api-client";
import { useCrawlStore } from "@/stores/crawl-store";
import type { WsMessage, CrawlStatus } from "@/types";

const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

/**
 * Connects a WebSocket to /api/v1/crawls/{crawlId}/ws.
 * Automatically reconnects on disconnect (up to MAX_RECONNECT_ATTEMPTS).
 * Updates the Zustand store with progress/status events.
 *
 * Only connects when `enabled` is true (default: true).
 * Pass enabled=false for completed/failed/cancelled crawls.
 */
export function useCrawlWebSocket(
  crawlId: string | null,
  options: { enabled?: boolean } = {}
) {
  const { enabled = true } = options;
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { updateProgress, setLiveStatus, setWsConnected } = useCrawlStore();

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    setWsConnected(false);
  }, [setWsConnected]);

  const connect = useCallback(() => {
    if (!crawlId || !enabled) return;

    const url = getCrawlWsUrl(crawlId);
    if (!url) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        switch (msg.type) {
          case "progress":
            updateProgress(msg);
            break;
          case "status_change":
            setLiveStatus(msg.status as CrawlStatus);
            break;
          case "ping":
            // heartbeat — ignore
            break;
        }
      } catch {
        // Malformed message — ignore
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      // Auto-reconnect
      if (
        enabled &&
        reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS
      ) {
        reconnectAttempts.current++;
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      }
    };

    ws.onerror = () => {
      // Error will trigger onclose
    };
  }, [crawlId, enabled, updateProgress, setLiveStatus, setWsConnected]);

  // Reset reconnect counter when crawlId or enabled changes
  useEffect(() => {
    reconnectAttempts.current = 0;
  }, [crawlId, enabled]);

  useEffect(() => {
    if (!crawlId || !enabled) {
      cleanup();
      return;
    }
    connect();
    return cleanup;
  }, [crawlId, enabled, connect, cleanup]);

  return {
    isConnected: useCrawlStore((s) => s.wsConnected),
  };
}
