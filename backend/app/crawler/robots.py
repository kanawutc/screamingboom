"""Robots.txt Parser: per-domain fetch, parse, and cache.

Fetches and parses robots.txt for each domain encountered during a crawl,
caching results in Redis with per-crawl isolation.
"""

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import structlog

from app.crawler.fetcher import FetcherPool

logger = structlog.get_logger(__name__)

# Maximum robots.txt size we'll parse (500KB)
_MAX_ROBOTS_SIZE = 500 * 1024

# Redis cache TTL for parsed robots.txt results
_CACHE_TTL_SECONDS = 3600

# Timeout for fetching robots.txt (separate from regular page fetch timeout)
_ROBOTS_FETCH_TIMEOUT = 10


class RobotsChecker:
    """Manages robots.txt compliance checking with per-domain caching.

    Usage::

        checker = RobotsChecker(redis=redis_client, fetcher=fetcher_pool)
        allowed = await checker.can_fetch(crawl_id, url, user_agent)
        delay = await checker.get_crawl_delay(crawl_id, domain, user_agent)
        await checker.close()
    """

    def __init__(
        self,
        redis: object,  # redis.asyncio.Redis
        fetcher: FetcherPool,
        respect_robots: bool = True,
    ) -> None:
        self._redis = redis
        self._fetcher = fetcher
        self._respect_robots = respect_robots
        # In-memory cache of parsed RobotFileParser per domain (per crawl)
        self._parsers: dict[str, RobotFileParser] = {}

    async def can_fetch(
        self,
        crawl_id: str,
        url: str,
        user_agent: str = "*",
    ) -> bool:
        """Check if URL is allowed by robots.txt.

        Args:
            crawl_id: Current crawl ID (for cache isolation).
            url: URL to check.
            user_agent: User-agent string to check against.

        Returns:
            True if URL is allowed (or robots.txt mode is 'ignore').
        """
        if not self._respect_robots:
            return True

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        scheme = parsed.scheme.lower()

        parser = await self._get_parser(crawl_id, scheme, domain)
        if parser is None:
            # Failed to get parser — treat as "allow all"
            return True

        try:
            return parser.can_fetch(user_agent, url)
        except Exception:
            return True

    async def get_crawl_delay(
        self,
        crawl_id: str,
        domain: str,
        user_agent: str = "*",
        scheme: str = "https",
    ) -> float | None:
        """Extract Crawl-delay directive for a domain.

        Returns:
            Crawl-delay value in seconds, or None if not specified.
        """
        if not self._respect_robots:
            return None

        parser = await self._get_parser(crawl_id, scheme, domain)
        if parser is None:
            return None

        try:
            delay = parser.crawl_delay(user_agent)
            if delay is not None:
                return float(delay)
            return None
        except Exception:
            return None

    async def close(self) -> None:
        """Clear in-memory parser cache."""
        self._parsers.clear()

    # ------------------------------------------------------------------
    # Internal: fetch, parse, cache
    # ------------------------------------------------------------------

    async def _get_parser(
        self,
        crawl_id: str,
        scheme: str,
        domain: str,
    ) -> RobotFileParser | None:
        """Get or create a RobotFileParser for a domain.

        Checks in-memory cache → Redis cache → fetch from origin.
        """
        cache_key = f"{crawl_id}:{scheme}:{domain}"

        # 1. In-memory cache
        if cache_key in self._parsers:
            return self._parsers[cache_key]

        # 2. Redis cache
        redis_key = f"crawl:{crawl_id}:robots:{domain}"
        try:
            cached = await self._redis.get(redis_key)
            if cached is not None:
                parser = self._parse_robots_text(
                    f"{scheme}://{domain}/robots.txt",
                    cached.decode("utf-8") if isinstance(cached, bytes) else cached,
                )
                self._parsers[cache_key] = parser
                return parser
        except Exception as e:
            logger.debug("robots_redis_cache_miss", domain=domain, error=str(e))

        # 3. Fetch from origin
        robots_url = f"{scheme}://{domain}/robots.txt"
        robots_text = await self._fetch_robots(robots_url)

        # Cache in Redis
        try:
            await self._redis.set(redis_key, robots_text, ex=_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.debug("robots_redis_cache_set_failed", domain=domain, error=str(e))

        # Parse and cache in memory
        parser = self._parse_robots_text(robots_url, robots_text)
        self._parsers[cache_key] = parser
        return parser

    async def _fetch_robots(self, robots_url: str) -> str:
        """Fetch robots.txt content from origin.

        Returns:
            robots.txt content as string, or empty string on failure (allow all).
        """
        try:
            result = await asyncio.wait_for(
                self._fetcher.fetch(robots_url),
                timeout=_ROBOTS_FETCH_TIMEOUT,
            )

            # 404 or 5XX → treat as "allow all" (empty robots.txt)
            if result.status_code == 0 or result.status_code >= 400:
                logger.debug(
                    "robots_fetch_error_allow_all",
                    url=robots_url,
                    status=result.status_code,
                )
                return ""

            # Too large → ignore
            if len(result.body) > _MAX_ROBOTS_SIZE:
                logger.debug(
                    "robots_too_large_allow_all",
                    url=robots_url,
                    size=len(result.body),
                )
                return ""

            # Decode body
            try:
                return result.body.decode("utf-8", errors="replace")
            except Exception:
                return result.body.decode("latin-1", errors="replace")

        except asyncio.TimeoutError:
            logger.debug("robots_fetch_timeout_allow_all", url=robots_url)
            return ""
        except Exception as e:
            logger.debug("robots_fetch_exception_allow_all", url=robots_url, error=str(e))
            return ""

    def _parse_robots_text(self, url: str, content: str) -> RobotFileParser:
        """Parse robots.txt content into RobotFileParser."""
        parser = RobotFileParser()
        parser.set_url(url)

        if content:
            try:
                # RobotFileParser.parse() expects a list of lines
                lines = content.splitlines()
                parser.parse(lines)
            except Exception as e:
                logger.debug("robots_parse_error", url=url, error=str(e))
                # Return parser with no rules → allow all
                parser.parse([])
        else:
            # Empty content → allow all
            parser.parse([])

        return parser
