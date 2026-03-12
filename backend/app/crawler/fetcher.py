"""HTTP Fetcher Pool: manages async HTTP requests with redirect tracking and retry."""

import asyncio
import dataclasses
import time
from urllib.parse import urljoin

import aiohttp
import structlog

logger = structlog.get_logger(__name__)

# Status codes that trigger retry
_RETRYABLE_5XX = frozenset(range(500, 600)) - {501}  # 5XX except 501
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECT_HOPS = 10


@dataclasses.dataclass
class FetchResult:
    """Result of an HTTP fetch operation."""

    url: str  # Original requested URL
    final_url: str  # URL after all redirects
    status_code: int  # HTTP status (0 if connection error)
    headers: dict[str, str]  # Response headers
    body: bytes  # Response body
    redirect_chain: list[dict[str, object]]  # [{"url": str, "status_code": int}, ...]
    response_time_ms: int  # Total response time in milliseconds
    content_type: str  # Content-Type header value
    error: str | None = None  # Error message if failed
    is_redirect: bool = False  # Whether the URL was redirected


class FetcherPool:
    """HTTP client pool using aiohttp with manual redirect following,
    exponential backoff retry, and connection pooling.

    Usage::

        async with FetcherPool(user_agent="MyBot/1.0") as fetcher:
            result = await fetcher.fetch("https://example.com")
    """

    def __init__(
        self,
        user_agent: str = "SEOSpider/1.0",
        max_connections: int = 0,
        max_per_host: int = 2,
        request_timeout: int = 30,
        verify_ssl: bool = True,
    ) -> None:
        self._user_agent = user_agent
        self._max_connections = max_connections
        self._max_per_host = max_per_host
        self._request_timeout = request_timeout
        self._verify_ssl = verify_ssl
        self._session: aiohttp.ClientSession | None = None
        self._connector: aiohttp.TCPConnector | None = None

    async def start(self) -> None:
        """Create the aiohttp session and connector."""
        if self._session and not self._session.closed:
            return

        self._connector = aiohttp.TCPConnector(
            limit=self._max_connections,
            limit_per_host=self._max_per_host,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(
            total=self._request_timeout,
            connect=10,
            sock_read=20,
        )
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout,
            headers={"User-Agent": self._user_agent},
        )
        logger.info(
            "Fetcher pool started",
            user_agent=self._user_agent,
            max_connections=self._max_connections,
            max_per_host=self._max_per_host,
        )

    async def close(self) -> None:
        """Close the aiohttp session cleanly."""
        if self._session and not self._session.closed:
            await self._session.close()
        # Give connector time to close lingering connections
        await asyncio.sleep(0.25)
        logger.info("Fetcher pool closed")

    async def __aenter__(self) -> "FetcherPool":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch(self, url: str, max_retries: int = 3) -> FetchResult:
        """Fetch a URL with automatic retry and redirect following.

        Returns a FetchResult with all metadata regardless of success/failure.
        """
        if self._session is None or self._session.closed:
            raise RuntimeError("FetcherPool not started. Call start() or use as context manager.")

        start = time.monotonic()
        result = await self._fetch_with_retry(url, max_retries)
        result.response_time_ms = int((time.monotonic() - start) * 1000)
        return result

    # ------------------------------------------------------------------
    # Internal: retry loop
    # ------------------------------------------------------------------

    async def _fetch_with_retry(self, url: str, max_retries: int) -> FetchResult:
        """Retry wrapper with exponential backoff."""
        last_result: FetchResult | None = None

        for attempt in range(max_retries + 1):
            result = await self._fetch_once(url)
            last_result = result

            # Success or non-retryable status
            if result.error is None and result.status_code < 500:
                return result

            # 501 Not Implemented — don't retry
            if result.status_code == 501:
                return result

            # 4XX — don't retry (except 429)
            if 400 <= result.status_code < 500 and result.status_code != 429:
                return result

            # Last attempt — return as-is
            if attempt >= max_retries:
                break

            # Calculate backoff delay
            if result.status_code == 429:
                # HTTP 429: domain-specific backoff 30s, 60s, 120s
                delay = 30 * (2**attempt)
            else:
                # Connection error / timeout / 5XX: exponential 1, 2, 4, 8...
                delay = min(2**attempt, 60)

            logger.warning(
                "Retrying fetch",
                url=url,
                attempt=attempt + 1,
                max_retries=max_retries,
                status_code=result.status_code,
                error=result.error,
                delay_s=delay,
            )
            await asyncio.sleep(delay)

        # All retries exhausted
        assert last_result is not None
        if last_result.error is None:
            last_result.error = (
                f"All {max_retries} retries exhausted (status {last_result.status_code})"
            )
        return last_result

    # ------------------------------------------------------------------
    # Internal: single fetch with manual redirect following
    # ------------------------------------------------------------------

    async def _fetch_once(self, url: str) -> FetchResult:
        """Execute a single fetch with manual redirect following."""
        redirect_chain: list[dict[str, object]] = []
        current_url = url
        seen_urls: set[str] = {url}
        body = b""
        headers: dict[str, str] = {}
        status_code = 0
        content_type = ""

        try:
            for _hop in range(_MAX_REDIRECT_HOPS):
                assert self._session is not None
                async with self._session.get(
                    current_url,
                    allow_redirects=False,
                    ssl=self._verify_ssl if self._verify_ssl else False,
                ) as response:
                    # ALWAYS consume body to prevent connection leaks
                    body = await response.read()
                    status_code = response.status
                    headers = {k: v for k, v in response.headers.items()}
                    content_type = response.headers.get("Content-Type", "")

                    if status_code in _REDIRECT_CODES:
                        location = response.headers.get("Location")
                        if not location:
                            # Malformed redirect — no Location header
                            break

                        # Resolve relative redirects
                        next_url = urljoin(current_url, location)

                        redirect_chain.append(
                            {
                                "url": current_url,
                                "status_code": status_code,
                            }
                        )

                        # Redirect loop detection
                        if next_url in seen_urls:
                            return FetchResult(
                                url=url,
                                final_url=current_url,
                                status_code=status_code,
                                headers=headers,
                                body=body,
                                redirect_chain=redirect_chain,
                                response_time_ms=0,
                                content_type=content_type,
                                error=f"Redirect loop detected: {next_url}",
                                is_redirect=True,
                            )

                        seen_urls.add(next_url)
                        current_url = next_url
                        continue
                    else:
                        # Non-redirect response — we're done
                        break

            return FetchResult(
                url=url,
                final_url=current_url,
                status_code=status_code,
                headers=headers,
                body=body,
                redirect_chain=redirect_chain,
                response_time_ms=0,
                content_type=content_type,
                error=None,
                is_redirect=len(redirect_chain) > 0,
            )

        except aiohttp.ClientConnectorError as e:
            logger.error("Connection error", url=url, error=str(e))
            return self._error_result(url, current_url, redirect_chain, f"Connection error: {e}")

        except aiohttp.ClientResponseError as e:
            logger.error("Response error", url=url, status=e.status, error=str(e))
            return FetchResult(
                url=url,
                final_url=current_url,
                status_code=e.status,
                headers={},
                body=b"",
                redirect_chain=redirect_chain,
                response_time_ms=0,
                content_type="",
                error=f"Response error: {e}",
                is_redirect=len(redirect_chain) > 0,
            )

        except asyncio.TimeoutError:
            logger.error("Request timeout", url=url)
            return self._error_result(url, current_url, redirect_chain, "Request timeout")

        except Exception as e:
            logger.error("Unexpected fetch error", url=url, error=str(e))
            return self._error_result(url, current_url, redirect_chain, f"Unexpected error: {e}")

    @staticmethod
    def _error_result(
        url: str,
        final_url: str,
        redirect_chain: list[dict[str, object]],
        error: str,
    ) -> FetchResult:
        """Build a FetchResult for error cases."""
        return FetchResult(
            url=url,
            final_url=final_url,
            status_code=0,
            headers={},
            body=b"",
            redirect_chain=redirect_chain,
            response_time_ms=0,
            content_type="",
            error=error,
            is_redirect=len(redirect_chain) > 0,
        )
