"""URL Frontier: manages crawl URL queue with BFS ordering and Bloom filter dedup."""

import asyncio

import structlog
from pybloom_live import ScalableBloomFilter
from redis.asyncio import Redis

from app.crawler.utils import extract_domain, normalize_url, url_hash_hex

logger = structlog.get_logger(__name__)


class URLFrontier:
    """BFS-ordered URL frontier backed by Redis sorted sets and a Bloom filter.

    URLs are scored by crawl depth so ZPOPMIN always returns the shallowest
    (breadth-first) URL next.  Deduplication is handled by a ScalableBloomFilter
    in memory (no persistence — Sprint 1 guardrail).
    """

    def __init__(
        self,
        crawl_id: str,
        redis: Redis,
        max_urls: int = 10_000,
    ) -> None:
        self._crawl_id = crawl_id
        self._redis = redis
        self._max_urls = max_urls
        self._urls_added: int = 0

        # In-memory Bloom filter — not persisted (Sprint 1)
        self._bloom = ScalableBloomFilter(
            initial_capacity=1_000_000,
            error_rate=0.001,
        )

    # ------------------------------------------------------------------
    # Redis key helpers
    # ------------------------------------------------------------------

    @property
    def frontier_key(self) -> str:
        """Redis sorted-set key for the frontier queue."""
        return f"crawl:{self._crawl_id}:frontier"

    @property
    def urls_added(self) -> int:
        """Total number of unique URLs added to the frontier."""
        return self._urls_added

    def _cooldown_key(self, domain: str) -> str:
        return f"crawl:{self._crawl_id}:domain_cooldown:{domain}"

    # ------------------------------------------------------------------
    # Bloom filter pre-population (for continue-crawl)
    # ------------------------------------------------------------------

    def pre_populate_bloom(self, url_hex_hashes: list[str]) -> int:
        """Add URL hashes to the Bloom filter without incrementing the added counter.

        Used by continue-crawl to mark already-crawled URLs as "seen" so they
        are never re-added to the frontier.  Returns the number of hashes added.
        """
        count = 0
        for h in url_hex_hashes:
            if h not in self._bloom:
                self._bloom.add(h)
                count += 1
        return count

    # ------------------------------------------------------------------
    # Core frontier operations
    # ------------------------------------------------------------------

    async def add(
        self,
        url: str,
        depth: int,
        base_url: str | None = None,
    ) -> bool:
        """Add a URL to the frontier.

        Returns True if the URL was new and successfully added, False if
        rejected (bad scheme, duplicate, or limit reached).
        """
        normalized = normalize_url(url, base_url)
        if normalized is None:
            return False

        if self._max_urls > 0 and self._urls_added >= self._max_urls:
            return False

        # Bloom filter check
        url_hex = url_hash_hex(normalized)
        if url_hex in self._bloom:
            return False

        # Mark as seen
        self._bloom.add(url_hex)

        # ZADD NX — depth as score for BFS ordering
        added = await self._redis.zadd(
            self.frontier_key,
            {normalized: float(depth)},
            nx=True,
        )
        if added:
            self._urls_added += 1
            return True

        return False

    async def add_batch(
        self,
        urls_with_depths: list[tuple[str, int]],
        base_url: str | None = None,
    ) -> int:
        """Add multiple URLs to the frontier in a single Redis pipeline.

        Returns the number of URLs actually added (after dedup + limit).
        """
        to_add: dict[str, float] = {}

        for raw_url, depth in urls_with_depths:
            if self._max_urls > 0 and self._urls_added + len(to_add) >= self._max_urls:
                break

            normalized = normalize_url(raw_url, base_url)
            if normalized is None:
                continue

            url_hex = url_hash_hex(normalized)
            if url_hex in self._bloom:
                continue

            self._bloom.add(url_hex)
            to_add[normalized] = float(depth)

        if not to_add:
            return 0

        # Pipeline ZADD NX
        added = await self._redis.zadd(self.frontier_key, to_add, nx=True)
        count = int(added) if added else 0
        self._urls_added += count
        return count

    async def pop(self) -> tuple[str, int] | None:
        """Pop the next URL (lowest depth = BFS order).

        Returns (url, depth) or None if the frontier is empty.
        """
        results = await self._redis.zpopmin(self.frontier_key, count=1)
        if not results:
            return None

        raw_url, score = results[0]
        url = raw_url.decode("utf-8") if isinstance(raw_url, bytes) else str(raw_url)
        return (url, int(score))

    async def pop_batch(self, count: int = 10) -> list[tuple[str, int]]:
        """Pop up to `count` URLs from the frontier (BFS order).

        Returns list of (url, depth) tuples.
        """
        results = await self._redis.zpopmin(self.frontier_key, count=count)
        return [
            (raw.decode("utf-8") if isinstance(raw, bytes) else str(raw), int(score))
            for raw, score in results
        ]

    async def size(self) -> int:
        """Number of URLs waiting in the frontier."""
        return await self._redis.zcard(self.frontier_key)

    async def is_empty(self) -> bool:
        """Check if the frontier has no more URLs to process."""
        return (await self.size()) == 0

    async def clear(self) -> None:
        """Delete the frontier and all domain cooldown keys for this crawl."""
        await self._redis.delete(self.frontier_key)

        # Clean up domain cooldown keys
        pattern = f"crawl:{self._crawl_id}:domain_cooldown:*"
        cursor: int = 0
        while True:
            cursor, keys = await self._redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break

        logger.info(
            "Frontier cleared",
            crawl_id=self._crawl_id,
            urls_added=self._urls_added,
        )

    # ------------------------------------------------------------------
    # Per-domain rate limiting
    # ------------------------------------------------------------------

    async def can_fetch(self, domain: str, rate_limit_ms: int = 1000) -> bool:
        """Check if we can fetch from this domain right now.

        Uses a Redis key with PX (millisecond) expiry as a cooldown timer.
        Returns True if the domain is available (key was set), False if in cooldown.
        """
        key = self._cooldown_key(domain)
        result = await self._redis.set(key, "1", nx=True, px=rate_limit_ms)
        return result is not None

    async def wait_for_domain(
        self,
        domain: str,
        rate_limit_ms: int = 1000,
    ) -> None:
        """Wait until a domain is available, then set a new cooldown.

        Blocks until the domain's cooldown key expires, then atomically
        sets a fresh cooldown.
        """
        key = self._cooldown_key(domain)
        while True:
            result = await self._redis.set(key, "1", nx=True, px=rate_limit_ms)
            if result is not None:
                return  # Cooldown set — we own this slot

            # Check remaining TTL
            ttl_ms = await self._redis.pttl(key)
            if ttl_ms > 0:
                await asyncio.sleep(ttl_ms / 1000.0)
            else:
                # Key expired between check and sleep — retry immediately
                await asyncio.sleep(0.01)
