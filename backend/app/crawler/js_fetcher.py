"""Playwright-based fetcher for JavaScript-rendered pages."""

import asyncio
import time
import structlog
from typing import Any

from app.crawler.fetcher import FetchResult

logger = structlog.get_logger(__name__)

class JsFetcherPool:
    """HTTP client pool using Playwright for JavaScript rendering.
    
    Acts as a drop-in replacement for FetcherPool when render_js is enabled.
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
        self._max_browsers = max_per_host if max_per_host > 0 else 2
        self._timeout_ms = request_timeout * 1000
        self._verify_ssl = verify_ssl
        self._pw = None
        self._browser = None
        self._context_pool: asyncio.Queue[Any] = asyncio.Queue()

    async def start(self) -> None:
        """Launch Playwright and pre-create browser contexts."""
        if self._browser:
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Please install with JS rendering support "
                "or disable render_js in crawl configuration."
            )

        self._pw_ctx = async_playwright()
        self._pw = await self._pw_ctx.__aenter__()
        
        # Launch Chromium headless
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        
        # Pre-create browser contexts for concurrency
        for _ in range(self._max_browsers):
            ctx = await self._browser.new_context(
                user_agent=self._user_agent,
                ignore_https_errors=not self._verify_ssl,
            )
            await self._context_pool.put(ctx)
            
        logger.info(
            "JS Fetcher pool started",
            user_agent=self._user_agent,
            max_browsers=self._max_browsers,
        )

    async def close(self) -> None:
        """Close all contexts and the browser."""
        while not self._context_pool.empty():
            ctx = self._context_pool.get_nowait()
            await ctx.close()
            
        if self._browser:
            await self._browser.close()
            
        if getattr(self, "_pw_ctx", None):
            await self._pw_ctx.__aexit__(None, None, None)
            
        logger.info("JS Fetcher pool closed")

    async def __aenter__(self) -> "JsFetcherPool":
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def fetch(self, url: str, max_retries: int = 3) -> FetchResult:
        """Fetch and render a URL using Playwright, with retry logic."""
        if not self._browser:
            raise RuntimeError("JsFetcherPool not started.")

        last_result: FetchResult | None = None

        for attempt in range(max_retries + 1):
            fetch_start = time.monotonic()
            
            # Borrow context
            ctx = await self._context_pool.get()
            
            try:
                page = await ctx.new_page()
                try:
                    # navigate Network idle to ensure JS has time to render
                    response = await page.goto(
                        url, 
                        timeout=self._timeout_ms,
                        wait_until="networkidle"
                    )
                    
                    if not response:
                        raise Exception("No response received from Playwright")
                    
                    body = await page.content()
                    status = response.status
                    headers = await response.all_headers()
                    final_url = page.url
                    content_type = headers.get("content-type", "text/html")
                    
                    result = FetchResult(
                        url=url,
                        final_url=final_url,
                        status_code=status,
                        headers=headers,
                        body=body.encode("utf-8"),
                        redirect_chain=[],  # Playwright handles redirects transparently
                        response_time_ms=int((time.monotonic() - fetch_start) * 1000),
                        content_type=content_type,
                        error=None,
                        is_redirect=(url != final_url)
                    )
                finally:
                    await page.close()
                    
            except Exception as e:
                # Provide a fallback error result
                err_msg = str(e)
                if "Timeout" in err_msg:
                    err_msg = "Request timeout"
                
                result = FetchResult(
                    url=url,
                    final_url=url,
                    status_code=0,
                    headers={},
                    body=b"",
                    redirect_chain=[],
                    response_time_ms=int((time.monotonic() - fetch_start) * 1000),
                    content_type="",
                    error=err_msg,
                    is_redirect=False,
                )
                
            finally:
                # Return context to pool
                await self._context_pool.put(ctx)

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

            if attempt >= max_retries:
                break

            delay = min(2**attempt, 60)
            if result.status_code == 429:
                delay = 30 * (2**attempt)
                
            logger.warning(
                "Retrying JS fetch",
                url=url,
                attempt=attempt + 1,
                status_code=result.status_code,
                error=result.error,
                delay=delay,
            )
            await asyncio.sleep(delay)

        assert last_result is not None
        if last_result.error is None:
            last_result.error = f"All {max_retries} retries exhausted (status {last_result.status_code})"
            
        return last_result
