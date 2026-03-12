#!/usr/bin/env python3
"""
Performance Test
================
Measures API response times, crawl throughput, and concurrency handling.

Usage:
    python test_performance.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost"
API = f"{BASE_URL}/api/v1"
CRAWL_TARGET = "https://books.toscrape.com/"
MAX_CRAWL_WAIT = 300

passed = 0
failed = 0
warnings = 0


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    DIM = "\033[2m"
    CYAN = "\033[36m"


def api_call(method, path, body=None, timeout=10):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return 0, str(e)


def timed_api_call(method, path, body=None, timeout=10):
    """Like api_call but also returns elapsed_ms."""
    start = time.monotonic()
    code, body_resp = api_call(method, path, body, timeout)
    elapsed_ms = (time.monotonic() - start) * 1000
    return code, body_resp, elapsed_ms


def timed_http_get(url, timeout=10):
    start = time.monotonic()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read()
            return resp.status, (time.monotonic() - start) * 1000
    except urllib.error.HTTPError as e:
        return e.code, (time.monotonic() - start) * 1000
    except Exception:
        return 0, (time.monotonic() - start) * 1000


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  {C.GREEN}✓{C.RESET} {name}")
        return True
    else:
        failed += 1
        msg = f"  {C.RED}✗{C.RESET} {name}"
        if detail:
            msg += f"  {C.DIM}({detail}){C.RESET}"
        print(msg)
        return False


def warn(name, detail=""):
    global warnings
    warnings += 1
    msg = f"  {C.YELLOW}⚠{C.RESET} {name}"
    if detail:
        msg += f"  {C.DIM}({detail}){C.RESET}"
    print(msg)


def section(title):
    print(f"\n{C.BOLD}{C.CYAN}▸ {title}{C.RESET}")


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — Performance Test{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None
    crawl_id = None

    try:
        # ── Setup ─────────────────────────────────────────────────
        section("Setup")
        code, body = api_call(
            "POST", "/projects", {"name": "Perf Test", "domain": CRAWL_TARGET}
        )
        if code != 201:
            print(f"  {C.RED}ABORT: Cannot create project{C.RESET}")
            sys.exit(1)
        project_id = body["id"]

        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 50, "max_depth": 3, "rate_limit_rps": 10.0},
            },
        )
        if code != 201:
            print(f"  {C.RED}ABORT: Cannot start crawl{C.RESET}")
            sys.exit(1)
        crawl_id = body["id"]

        print(f"  {C.DIM}Waiting for crawl (50 URLs)...{C.RESET}", end="", flush=True)
        crawl_start = time.time()
        final = "unknown"
        while time.time() - crawl_start < MAX_CRAWL_WAIT:
            time.sleep(3)
            c, b = api_call("GET", f"/crawls/{crawl_id}")
            if c == 200 and isinstance(b, dict):
                final = b.get("status", "")
                if final in ("completed", "failed", "cancelled"):
                    break
            print(".", end="", flush=True)
        crawl_elapsed = time.time() - crawl_start
        print(f" {crawl_elapsed:.0f}s")
        check("crawl completed", final == "completed", f"got: {final}")

        # ── 1. Endpoint Latency ───────────────────────────────────
        section("1. Endpoint Latency")

        code, _, ms = timed_api_call("GET", "/health")
        check(f"GET /health < 200ms", code == 200 and ms < 200, f"{ms:.0f}ms")

        code, _, ms = timed_api_call("GET", "/projects?limit=50")
        check(f"GET /projects < 500ms", code == 200 and ms < 500, f"{ms:.0f}ms")

        code, _, ms = timed_api_call("GET", f"/crawls/{crawl_id}")
        check(f"GET /crawls/:id < 500ms", code == 200 and ms < 500, f"{ms:.0f}ms")

        code, _, ms = timed_api_call("GET", f"/crawls/{crawl_id}/urls?limit=50")
        check(
            f"GET /crawls/:id/urls (50) < 1s", code == 200 and ms < 1000, f"{ms:.0f}ms"
        )

        code, _, ms = timed_api_call("GET", f"/crawls/{crawl_id}/issues?limit=50")
        check(
            f"GET /crawls/:id/issues (50) < 1s",
            code == 200 and ms < 1000,
            f"{ms:.0f}ms",
        )

        code, _, ms = timed_api_call("GET", f"/crawls/{crawl_id}/issues/summary")
        check(
            f"GET /crawls/:id/issues/summary < 1s",
            code == 200 and ms < 1000,
            f"{ms:.0f}ms",
        )

        # URL detail with seo_data
        code, urls_body = api_call("GET", f"/crawls/{crawl_id}/urls?limit=1")
        if isinstance(urls_body, dict) and urls_body.get("items"):
            uid = urls_body["items"][0]["id"]
            code, _, ms = timed_api_call("GET", f"/crawls/{crawl_id}/urls/{uid}")
            check(f"GET URL detail < 500ms", code == 200 and ms < 500, f"{ms:.0f}ms")

        # ── 2. Pagination Efficiency ─────────────────────────────
        section("2. Pagination Efficiency")

        # Page 1
        code1, body1, ms1 = timed_api_call("GET", f"/crawls/{crawl_id}/issues?limit=10")
        cursor1 = body1.get("next_cursor") if isinstance(body1, dict) else None

        if cursor1:
            # Page 2
            code2, body2, ms2 = timed_api_call(
                "GET", f"/crawls/{crawl_id}/issues?limit=10&cursor={cursor1}"
            )
            cursor2 = body2.get("next_cursor") if isinstance(body2, dict) else None
            if cursor2:
                # Page 3
                _, _, ms3 = timed_api_call(
                    "GET", f"/crawls/{crawl_id}/issues?limit=10&cursor={cursor2}"
                )
                ratio = ms3 / max(ms1, 1)
                check(
                    f"page 3 vs page 1 latency ratio < 3x",
                    ratio < 3.0,
                    f"page1={ms1:.0f}ms, page3={ms3:.0f}ms, ratio={ratio:.1f}x",
                )
            else:
                warn("only 2 pages of issues, cannot test deeper pagination")
        else:
            warn("only 1 page of issues")

        # ── 3. Concurrent Requests ───────────────────────────────
        section("3. Concurrent Requests")

        endpoints = [
            ("GET", "/health"),
            ("GET", "/projects?limit=5"),
            ("GET", f"/crawls/{crawl_id}"),
            ("GET", f"/crawls/{crawl_id}/urls?limit=5"),
            ("GET", f"/crawls/{crawl_id}/issues?limit=5"),
            ("GET", f"/crawls/{crawl_id}/issues/summary"),
            ("GET", "/health"),
            ("GET", f"/crawls/{crawl_id}/urls?limit=10"),
            ("GET", f"/crawls/{crawl_id}/issues?limit=10"),
            ("GET", f"/crawls/{crawl_id}"),
        ]

        def do_request(method_path):
            method, path = method_path
            code, _, ms = timed_api_call(method, path)
            return code, ms

        start_concurrent = time.monotonic()
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(do_request, ep): ep for ep in endpoints}
            for future in as_completed(futures):
                results.append(future.result())
        concurrent_total = (time.monotonic() - start_concurrent) * 1000

        all_success = all(r[0] == 200 for r in results)
        check(
            f"10 concurrent requests all 200",
            all_success,
            f"results={[r[0] for r in results]}",
        )

        max_latency = max(r[1] for r in results)
        check(
            f"max concurrent latency < 3s",
            max_latency < 3000,
            f"max={max_latency:.0f}ms, total_wall={concurrent_total:.0f}ms",
        )

        # ── 4. Crawl Throughput ──────────────────────────────────
        section("4. Crawl Throughput")

        code, body = api_call("GET", f"/crawls/{crawl_id}")
        if isinstance(body, dict):
            urls_crawled = body.get("crawled_urls_count", 0)
            check(
                f"crawled {urls_crawled} URLs in {crawl_elapsed:.0f}s",
                crawl_elapsed < 180,
                f"target < 180s",
            )
            if crawl_elapsed > 0:
                rate = urls_crawled / crawl_elapsed
                check(f"crawl rate ≥ 0.2 URLs/s", rate >= 0.2, f"rate={rate:.2f}/s")

        # ── 5. Frontend Load Time ─────────────────────────────────
        section("5. Frontend Performance")

        code, ms = timed_http_get(BASE_URL)
        check(f"Frontend initial load < 3s", code == 200 and ms < 3000, f"{ms:.0f}ms")

        code, ms = timed_http_get(f"{BASE_URL}/crawls")
        check(f"Frontend /crawls < 3s", code == 200 and ms < 3000, f"{ms:.0f}ms")

    finally:
        section("Cleanup")
        if crawl_id:
            api_call("DELETE", f"/crawls/{crawl_id}")
        if project_id:
            code, _ = api_call("DELETE", f"/projects/{project_id}")
            check("delete project", code == 204)

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"  {C.GREEN}✓ {passed} passed{C.RESET}  ", end="")
    if warnings:
        print(f"{C.YELLOW}⚠ {warnings} warnings{C.RESET}  ", end="")
    if failed:
        print(f"{C.RED}✗ {failed} failed{C.RESET}  ", end="")
    print(f"{C.DIM}({passed + failed} checks){C.RESET}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}ALL PERFORMANCE CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
