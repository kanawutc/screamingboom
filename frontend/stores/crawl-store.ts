import { create } from "zustand";
import type { CrawlStatus, WsProgressMessage } from "@/types";

interface CrawlProgress {
  crawled_count: number;
  error_count: number;
  elapsed_seconds: number;
  paused: boolean;
}

interface CrawlStoreState {
  /** Currently viewed crawl ID (for WebSocket subscription) */
  activeCrawlId: string | null;
  /** Latest progress from WebSocket */
  progress: CrawlProgress | null;
  /** Latest status (from WS status_change events) */
  liveStatus: CrawlStatus | null;
  /** WebSocket connection state */
  wsConnected: boolean;
}

interface CrawlStoreActions {
  setActiveCrawl: (crawlId: string | null) => void;
  updateProgress: (msg: WsProgressMessage) => void;
  setLiveStatus: (status: CrawlStatus) => void;
  setWsConnected: (connected: boolean) => void;
  reset: () => void;
}

const initialState: CrawlStoreState = {
  activeCrawlId: null,
  progress: null,
  liveStatus: null,
  wsConnected: false,
};

export const useCrawlStore = create<CrawlStoreState & CrawlStoreActions>()(
  (set) => ({
    ...initialState,

    setActiveCrawl: (crawlId) =>
      set({ activeCrawlId: crawlId, progress: null, liveStatus: null, wsConnected: false }),

    updateProgress: (msg) =>
      set({
        progress: {
          crawled_count: msg.crawled_count,
          error_count: msg.error_count,
          elapsed_seconds: msg.elapsed_seconds,
          paused: msg.paused,
        },
      }),

    setLiveStatus: (status) => set({ liveStatus: status }),

    setWsConnected: (connected) => set({ wsConnected: connected }),

    reset: () => set(initialState),
  })
);
