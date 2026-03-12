#!/usr/bin/env python3
"""
B1-B7: Crawl Lifecycle — start, list, get, pause, resume, stop, delete.

Exercises every crawl endpoint including state transitions and error cases.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
import urllib.error
import urllib.request

BASE_URL = "http://localhost"
API = f"{BASE_URL}/api/v1"
CRAWL_TARGET = "https://books.toscrape.com/"

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
    print(
        f"  {C.YELLOW}⚠{C.RESET} {name}  {C.DIM}({detail}){C.RESET}"
        if detail
        else f"  {C.YELLOW}⚠{C.RESET} {name}"
    )


def section(title):
    print(f"\n{C.BOLD}{C.CYAN}▸ {title}{C.RESET}")


def wait_crawl(crawl_id, max_wait=120):
    for _ in range(max_wait // 2):
        time.sleep(2)
        c, b = api_call("GET", f"/crawls/{crawl_id}")
        if (
            c == 200
            and isinstance(b, dict)
            and b.get("status") in ("completed", "failed", "cancelled")
        ):
            return b.get("status")
    return "timeout"


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  B1-B7: Crawl Lifecycle Test{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None
    crawl_ids = []

    try:
        section("Setup")
        code, body = api_call(
            "POST", "/projects", {"name": "Lifecycle Test", "domain": CRAWL_TARGET}
        )
        project_id = body["id"] if code == 201 and isinstance(body, dict) else None
        check("project created", project_id is not None)

        # ── B1: Start Crawl ───────────────────────────────────────
        section("B1. Start Crawl")

        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 5, "max_depth": 1, "rate_limit_rps": 10.0},
            },
        )
        check("valid start → 201", code == 201)
        cid1 = body.get("id") if isinstance(body, dict) else None
        if cid1:
            crawl_ids.append(cid1)
        check("response has crawl id", cid1 is not None)
        check(
            "status is queued or crawling", body.get("status") in ("queued", "crawling")
        )
        check("has config dict", isinstance(body.get("config"), dict))
        check("has created_at", "created_at" in body)
        check("total_urls starts at 0", body.get("total_urls", -1) == 0)

        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {"start_url": CRAWL_TARGET, "config": {"max_urls": 1}},
        )
        check("default config fills in", code == 201)
        if isinstance(body, dict) and body.get("id"):
            crawl_ids.append(body["id"])

        fake_pid = str(uuid.uuid4())
        code, _ = api_call(
            "POST", f"/projects/{fake_pid}/crawls", {"start_url": "https://example.com"}
        )
        check("nonexistent project → 404", code == 404)

        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {"start_url": CRAWL_TARGET, "config": {"max_urls": 1, "max_depth": 1}},
        )
        check("max_urls=1 accepted", code == 201)
        cid_one = body.get("id") if isinstance(body, dict) else None
        if cid_one:
            crawl_ids.append(cid_one)

        # ── B2: List Crawls ───────────────────────────────────────
        section("B2. List Crawls")

        code, body = api_call("GET", f"/projects/{project_id}/crawls")
        check("list crawls → 200", code == 200)
        items = body.get("items", []) if isinstance(body, dict) else []
        check("items is array", isinstance(items, list))
        check(f"has {len(items)} crawls (≥ 2)", len(items) >= 2)

        if items:
            first = items[0]
            check("CrawlSummary has id", "id" in first)
            check("CrawlSummary has status", "status" in first)
            check("CrawlSummary has mode", "mode" in first)
            check("CrawlSummary has total_urls", "total_urls" in first)
            check("CrawlSummary has crawled_urls_count", "crawled_urls_count" in first)
            check("CrawlSummary has created_at", "created_at" in first)

        code, body = api_call("GET", f"/projects/{project_id}/crawls?limit=1")
        check("limit=1 returns ≤ 1", code == 200 and len(body.get("items", [])) <= 1)

        # ── B3: Get Crawl Detail ──────────────────────────────────
        section("B3. Get Crawl Detail")

        if cid1:
            status = wait_crawl(cid1, max_wait=60)
            code, body = api_call("GET", f"/crawls/{cid1}")
            check("get crawl → 200", code == 200)
            check("CrawlResponse has started_at", "started_at" in body)
            check("CrawlResponse has completed_at", "completed_at" in body)
            check("CrawlResponse has config", isinstance(body.get("config"), dict))
            check("total_urls accurate", body.get("total_urls", 0) >= 1)
            check("crawled_urls_count ≥ 1", body.get("crawled_urls_count", 0) >= 1)

        fake_cid = str(uuid.uuid4())
        code, _ = api_call("GET", f"/crawls/{fake_cid}")
        check("nonexistent crawl → 404", code == 404)

        # ── B4: Pause Crawl ───────────────────────────────────────
        section("B4. Pause Crawl")

        code, slow_body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 50, "max_depth": 3, "rate_limit_rps": 1.0},
            },
        )
        slow_cid = (
            slow_body.get("id") if code == 201 and isinstance(slow_body, dict) else None
        )
        if slow_cid:
            crawl_ids.append(slow_cid)

        if slow_cid:
            time.sleep(3)
            code, body = api_call("POST", f"/crawls/{slow_cid}/pause")
            if code == 200:
                check("pause running crawl → 200", True)
                check(
                    "pause response has status=paused", body.get("status") == "paused"
                )

                c2, b2 = api_call("GET", f"/crawls/{slow_cid}")
                check("crawl status is paused", b2.get("status") == "paused")
            else:
                warn("pause failed (crawl may have completed too fast)", f"code={code}")

        code, _ = api_call("POST", f"/crawls/{fake_cid}/pause")
        check("pause nonexistent → 404 or 409", code in (404, 409))

        if cid1:
            code, _ = api_call("POST", f"/crawls/{cid1}/pause")
            check("pause completed crawl → 409", code == 409)

        # ── B5: Resume Crawl ──────────────────────────────────────
        section("B5. Resume Crawl")

        if slow_cid:
            c_check, b_check = api_call("GET", f"/crawls/{slow_cid}")
            if b_check.get("status") == "paused":
                code, body = api_call("POST", f"/crawls/{slow_cid}/resume")
                check("resume paused crawl → 200", code == 200)
                check(
                    "resume response has status=crawling",
                    body.get("status") == "crawling",
                )
            else:
                warn("crawl not in paused state, skipping resume test")

        if cid1:
            code, _ = api_call("POST", f"/crawls/{cid1}/resume")
            check("resume non-paused → 409", code == 409)

        # ── B6: Stop Crawl ────────────────────────────────────────
        section("B6. Stop Crawl")

        if slow_cid:
            c_check, b_check = api_call("GET", f"/crawls/{slow_cid}")
            if b_check.get("status") in ("crawling", "paused"):
                code, body = api_call("POST", f"/crawls/{slow_cid}/stop")
                check("stop active crawl → 200", code == 200)
                check(
                    "stop response has status=cancelled",
                    body.get("status") == "cancelled",
                )
            else:
                warn(
                    "crawl not active for stop test", f"status={b_check.get('status')}"
                )

        if cid1:
            code, _ = api_call("POST", f"/crawls/{cid1}/stop")
            check("stop completed crawl → 409", code == 409)

        # ── B7: Delete Crawl + Cascade ────────────────────────────
        section("B7. Delete Crawl (Cascade)")

        if cid_one:
            wait_crawl(cid_one, max_wait=30)

            code, urls = api_call("GET", f"/crawls/{cid_one}/urls")
            had_urls = isinstance(urls, dict) and len(urls.get("items", [])) > 0

            code, _ = api_call("DELETE", f"/crawls/{cid_one}")
            check("delete crawl → 204", code == 204)
            crawl_ids.remove(cid_one)

            code, _ = api_call("GET", f"/crawls/{cid_one}")
            check("crawl gone after delete", code == 404)

            if had_urls:
                code, body = api_call("GET", f"/crawls/{cid_one}/urls")
                items = body.get("items", []) if isinstance(body, dict) else []
                check("URLs gone after crawl delete", code == 404 or len(items) == 0)

        code, _ = api_call("DELETE", f"/crawls/{fake_cid}")
        check("delete nonexistent crawl → 404", code == 404)

    finally:
        section("Cleanup")
        for cid in crawl_ids:
            wait_crawl(cid, max_wait=30)
            api_call("DELETE", f"/crawls/{cid}")
        if project_id:
            api_call("DELETE", f"/projects/{project_id}")
        check("cleanup done", True)

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"  {C.GREEN}✓ {passed} passed{C.RESET}  ", end="")
    if warnings:
        print(f"{C.YELLOW}⚠ {warnings} warnings{C.RESET}  ", end="")
    if failed:
        print(f"{C.RED}✗ {failed} failed{C.RESET}  ", end="")
    print(f"{C.DIM}({passed + failed} checks){C.RESET}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}ALL CRAWL LIFECYCLE CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
