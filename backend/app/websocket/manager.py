"""WebSocket manager: CrawlBroadcaster with Redis pub/sub → client fan-out.

Architecture:
- ONE Redis subscription per crawl_id (not per WebSocket client)
- Fan-out to N asyncio.Queue instances — one per connected client
- Backpressure: drop oldest message on QueueFull
- Auto-cancel Redis listener when no clients remain
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class CrawlBroadcaster:
    """Manages Redis pub/sub subscriptions and fans out messages to WebSocket clients.

    Usage:
        broadcaster = CrawlBroadcaster(redis)
        queue = asyncio.Queue(maxsize=100)
        await broadcaster.subscribe(crawl_id, queue)
        # ... read from queue, send to WebSocket ...
        await broadcaster.unsubscribe(crawl_id, queue)
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        # crawl_id → set of asyncio.Queue
        self._clients: dict[str, set[asyncio.Queue]] = defaultdict(set)
        # crawl_id → asyncio.Task (listener)
        self._listeners: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, crawl_id: str, queue: asyncio.Queue) -> None:
        """Register a client queue for a crawl's events."""
        async with self._lock:
            self._clients[crawl_id].add(queue)
            # Start listener if this is the first client for this crawl
            if crawl_id not in self._listeners:
                task = asyncio.create_task(self._listen(crawl_id))
                self._listeners[crawl_id] = task
                logger.info("broadcaster_listener_started", crawl_id=crawl_id)

    async def unsubscribe(self, crawl_id: str, queue: asyncio.Queue) -> None:
        """Remove a client queue. Cancels listener if no clients remain."""
        async with self._lock:
            self._clients[crawl_id].discard(queue)
            if not self._clients[crawl_id]:
                # No more clients — cancel the listener
                del self._clients[crawl_id]
                task = self._listeners.pop(crawl_id, None)
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    logger.info("broadcaster_listener_stopped", crawl_id=crawl_id)

    async def shutdown(self) -> None:
        """Cancel all listeners. Called on app shutdown."""
        async with self._lock:
            for crawl_id, task in list(self._listeners.items()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._listeners.clear()
            self._clients.clear()

    async def _listen(self, crawl_id: str) -> None:
        """Subscribe to Redis channel and fan-out messages to client queues."""
        channel = f"crawl:{crawl_id}:events"
        # Create a separate pub/sub connection
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                # Fan-out to all registered queues
                async with self._lock:
                    queues = self._clients.get(crawl_id, set()).copy()

                for queue in queues:
                    try:
                        queue.put_nowait(data)
                    except asyncio.QueueFull:
                        # Backpressure: drop oldest, add newest
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            queue.put_nowait(data)
                        except asyncio.QueueFull:
                            pass  # Queue still full — skip message

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("broadcaster_listener_error", crawl_id=crawl_id, error=str(e))
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            # Remove dead listener from dict so subscribe() can create a new one
            async with self._lock:
                self._listeners.pop(crawl_id, None)


# Module-level singleton (initialized in lifespan)
_broadcaster: CrawlBroadcaster | None = None


def get_broadcaster() -> CrawlBroadcaster:
    """Return the global CrawlBroadcaster instance."""
    if _broadcaster is None:
        raise RuntimeError("CrawlBroadcaster not initialized.")
    return _broadcaster


def init_broadcaster(redis: Redis) -> CrawlBroadcaster:
    """Initialize the global broadcaster. Called during app lifespan startup."""
    global _broadcaster
    _broadcaster = CrawlBroadcaster(redis)
    return _broadcaster


async def shutdown_broadcaster() -> None:
    """Shutdown the global broadcaster. Called during app lifespan shutdown."""
    global _broadcaster
    if _broadcaster:
        await _broadcaster.shutdown()
        _broadcaster = None
