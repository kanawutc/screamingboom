#!/usr/bin/env python3
"""
Full-Loop Feature Test
======================
End-to-end verification of every feature built in Sprint 1 + Sprint 2.

Tests:
  Sprint 1 — Foundation
    1. Health check (API + DB + Redis)
    2. Project CRUD (create, read, update, list, delete)
    3. Crawl lifecycle (start → wait for completion)
    4. Crawled URLs (list, detail, filters)
    5. WebSocket connectivity

  Sprint 2 — SEO Analysis
    6. Issues summary (severity/category counts)
    7. Issues list (pagination, filters: severity, category, issue_type)
    8. Issue type coverage (titles, meta_descriptions, headings, images, etc.)
    9. Post-crawl analysis (duplicate titles, duplicate descriptions)
   10. Indexability data on crawled URLs

  Client-Side
   11. Frontend serves HTML on /
   12. Frontend route /crawls loads
   13. Frontend route /crawls/<id> loads (crawl detail page)

Usage:
    python test_full_loop.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

BASE_URL = "http://localhost"
API = f"{BASE_URL}/api/v1"
CRAWL_TARGET = "https://books.toscrape.com/"
MAX_CRAWL_WAIT = 180
POLL_INTERVAL = 3

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


def api_call(
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = 10,
) -> tuple[int, dict | str | None]:
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
        except (json.JSONDecodeError, Exception):
            return e.code, raw
    except Exception as e:
        return 0, str(e)


def http_get_raw(url: str, timeout: int = 10) -> tuple[int, str]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def check(name: str, condition: bool, detail: str = "") -> bool:
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


def warn(name: str, detail: str = ""):
    global warnings
    warnings += 1
    msg = f"  {C.YELLOW}⚠{C.RESET} {name}"
    if detail:
        msg += f"  {C.DIM}({detail}){C.RESET}"
    print(msg)


def section(title: str):
    print(f"\n{C.BOLD}{C.CYAN}▸ {title}{C.RESET}")


# ─── Sprint 1: Foundation ─────────────────────────────────────────


def test_health() -> bool:
    section("1. Health Check")
    code, body = api_call("GET", "/health")
    ok = check("GET /health returns 200", code == 200)
    if not ok or not isinstance(body, dict):
        return False
    check("status = healthy", body.get("status") == "healthy")
    services = body.get("services", {})
    check("database = ok", services.get("database") == "ok")
    check("redis = ok", services.get("redis") == "ok")
    check("version present", "version" in body)
    return True


def test_project_crud() -> str | None:
    section("2. Project CRUD")

    code, body = api_call(
        "POST", "/projects", {"name": "Full Loop Test", "domain": CRAWL_TARGET}
    )
    ok = check("POST /projects → 201", code == 201)
    if not ok or not isinstance(body, dict):
        return None
    pid = body.get("id", "")
    check("project has id", bool(pid))
    check("project has name", body.get("name") == "Full Loop Test")
    check("project has domain", body.get("domain") == CRAWL_TARGET)
    check("project has created_at", "created_at" in body)

    code, body = api_call("GET", f"/projects/{pid}")
    check("GET /projects/:id → 200", code == 200)
    check("returns correct project", isinstance(body, dict) and body.get("id") == pid)

    code, body = api_call("PUT", f"/projects/{pid}", {"name": "Full Loop Test Updated"})
    check("PUT /projects/:id → 200", code == 200)
    check(
        "name updated",
        isinstance(body, dict) and body.get("name") == "Full Loop Test Updated",
    )

    code, body = api_call("GET", "/projects?limit=100")
    check("GET /projects → 200", code == 200)
    check("returns paginated list", isinstance(body, dict) and "items" in body)
    found = any(p.get("id") == pid for p in body.get("items", []))
    check("our project in list", found)

    return pid


def test_crawl_lifecycle(project_id: str) -> str | None:
    section("3. Crawl Lifecycle")

    code, body = api_call(
        "POST",
        f"/projects/{project_id}/crawls",
        {
            "start_url": CRAWL_TARGET,
            "config": {"max_urls": 20, "max_depth": 2, "rate_limit_rps": 5.0},
        },
    )
    ok = check("POST /projects/:id/crawls → 201", code == 201)
    if not ok or not isinstance(body, dict):
        return None
    crawl_id = body.get("id", "")
    check("crawl has id", bool(crawl_id))
    initial_status = body.get("status", "")
    check("initial status is queued/crawling", initial_status in ("queued", "crawling"))

    code, body = api_call("GET", f"/projects/{project_id}/crawls?limit=100")
    check("GET /projects/:id/crawls → 200", code == 200)
    check(
        "crawl in project's crawl list",
        any(c.get("id") == crawl_id for c in (body or {}).get("items", [])),
    )

    print(
        f"  {C.DIM}Waiting for crawl to complete (max {MAX_CRAWL_WAIT}s)...{C.RESET}",
        end="",
        flush=True,
    )
    start = time.time()
    final_status = initial_status
    while time.time() - start < MAX_CRAWL_WAIT:
        time.sleep(POLL_INTERVAL)
        c_code, c_body = api_call("GET", f"/crawls/{crawl_id}")
        if c_code == 200 and isinstance(c_body, dict):
            final_status = c_body.get("status", "")
            if final_status in ("completed", "failed", "cancelled"):
                break
        print(".", end="", flush=True)
    elapsed = time.time() - start
    print()

    check(
        f"crawl finished in {elapsed:.0f}s",
        final_status in ("completed", "failed", "cancelled"),
    )
    check(
        "crawl status = completed", final_status == "completed", f"got: {final_status}"
    )

    code, body = api_call("GET", f"/crawls/{crawl_id}")
    if code == 200 and isinstance(body, dict):
        total_urls = body.get("total_urls", 0)
        crawled_count = body.get("crawled_urls_count", 0)
        check("total_urls > 0", total_urls > 0, f"total_urls={total_urls}")
        check(
            "crawled_urls_count > 0",
            crawled_count > 0,
            f"crawled_urls_count={crawled_count}",
        )
        check("has started_at", body.get("started_at") is not None)
        check("has completed_at", body.get("completed_at") is not None)

    return crawl_id if final_status == "completed" else None


def test_crawled_urls(crawl_id: str) -> str | None:
    section("4. Crawled URLs")

    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?limit=50")
    ok = check("GET /crawls/:id/urls → 200", code == 200)
    if not ok or not isinstance(body, dict):
        return None

    items = body.get("items", [])
    check("has crawled URLs", len(items) > 0, f"count={len(items)}")

    first_url = items[0] if items else {}
    url_id = first_url.get("id", "")
    check("URL has id", bool(url_id))
    check("URL has url field", bool(first_url.get("url")))
    check("URL has status_code", first_url.get("status_code") is not None)
    check("URL has content_type", first_url.get("content_type") is not None)

    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?status_code=200&limit=5")
    check("filter by status_code=200 works", code == 200)
    if isinstance(body, dict):
        for u in body.get("items", []):
            if u.get("status_code") != 200:
                check(
                    "all filtered URLs have status 200",
                    False,
                    f"got {u.get('status_code')}",
                )
                break

    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?content_type=html&limit=5")
    check("filter by content_type=html works", code == 200)

    if url_id:
        code, body = api_call("GET", f"/crawls/{crawl_id}/urls/{url_id}")
        check("GET /crawls/:id/urls/:url_id → 200", code == 200)
        if isinstance(body, dict):
            has_detail = any(
                k in body
                for k in (
                    "seo_data",
                    "title",
                    "title_length",
                    "h1",
                    "canonical_url",
                    "robots_meta",
                )
            )
            check("URL detail has SEO fields", has_detail)

    return crawl_id


def test_websocket(crawl_id: str):
    section("5. WebSocket Endpoint")
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("localhost", 80))
        sock.close()
        if result == 0:
            check("WebSocket port reachable (port 80)", True)
        else:
            warn("WebSocket port not reachable", "port 80 closed")
    except Exception:
        warn("WebSocket check skipped", "socket test failed")

    code, _ = http_get_raw(f"{BASE_URL}/api/v1/crawls/{crawl_id}/ws")
    # WebSocket upgrade on regular HTTP gives 403 or connection error — that's expected
    warn(
        "WebSocket endpoint exists (HTTP probe)",
        f"code={code}, expected non-200 for non-WS request",
    )


# ─── Sprint 2: SEO Analysis ──────────────────────────────────────


def test_issues_summary(crawl_id: str) -> dict | None:
    section("6. Issues Summary")

    code, body = api_call("GET", f"/crawls/{crawl_id}/issues/summary")
    ok = check("GET /crawls/:id/issues/summary → 200", code == 200)
    if not ok or not isinstance(body, dict):
        return None

    total = body.get("total", 0)
    check("total issues > 0", total > 0, f"total={total}")
    check("has by_severity", isinstance(body.get("by_severity"), dict))
    check("has by_category", isinstance(body.get("by_category"), dict))

    by_sev = body.get("by_severity", {})
    severity_sum = sum(by_sev.values())
    check(
        "by_severity sums to total",
        severity_sum == total,
        f"sum={severity_sum}, total={total}",
    )

    by_cat = body.get("by_category", {})
    check(
        "has multiple categories", len(by_cat) >= 2, f"categories={list(by_cat.keys())}"
    )

    return body


def test_issues_list(crawl_id: str):
    section("7. Issues List & Filters")

    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=10")
    ok = check("GET /crawls/:id/issues → 200", code == 200)
    if not ok or not isinstance(body, dict):
        return

    items = body.get("items", [])
    check("has issues", len(items) > 0)

    if items:
        issue = items[0]
        check("issue has url", bool(issue.get("url")))
        check("issue has issue_type", bool(issue.get("issue_type")))
        check(
            "issue has severity",
            issue.get("severity") in ("critical", "warning", "info", "opportunity"),
        )
        check("issue has category", bool(issue.get("category")))
        check("issue has description", bool(issue.get("description")))

    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?severity=warning&limit=5")
    check("filter by severity=warning → 200", code == 200)
    if isinstance(body, dict):
        for iss in body.get("items", []):
            if iss.get("severity") != "warning":
                check(
                    "all filtered issues have severity=warning",
                    False,
                    f"got {iss.get('severity')}",
                )
                break
        else:
            if body.get("items"):
                check("all filtered issues have severity=warning", True)

    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?category=titles&limit=5")
    check("filter by category=titles → 200", code == 200)
    if isinstance(body, dict):
        for iss in body.get("items", []):
            if iss.get("category") != "titles":
                check(
                    "all filtered issues have category=titles",
                    False,
                    f"got {iss.get('category')}",
                )
                break
        else:
            if body.get("items"):
                check("all filtered issues have category=titles", True)

    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=3")
    check(
        "pagination: limit=3 returns ≤3",
        code == 200 and isinstance(body, dict) and len(body.get("items", [])) <= 3,
    )
    next_cursor = body.get("next_cursor") if isinstance(body, dict) else None
    if next_cursor:
        code2, body2 = api_call(
            "GET", f"/crawls/{crawl_id}/issues?limit=3&cursor={next_cursor}"
        )
        check("pagination: cursor page returns 200", code2 == 200)
        if isinstance(body2, dict) and isinstance(body, dict):
            first_ids = {i.get("id") for i in body.get("items", [])}
            second_ids = {i.get("id") for i in body2.get("items", [])}
            check(
                "pagination: no overlap between pages", len(first_ids & second_ids) == 0
            )


def test_issue_type_coverage(crawl_id: str, summary: dict | None):
    section("8. Issue Type Coverage")

    if not summary:
        warn("skipped — no summary data")
        return

    by_cat = summary.get("by_category", {})
    expected_categories = ["titles", "meta_descriptions", "headings", "images"]
    for cat in expected_categories:
        count = by_cat.get(cat, 0)
        if count > 0:
            check(f"category '{cat}' has issues", True, f"count={count}")
        else:
            warn(f"category '{cat}' has 0 issues", "may be expected for small crawls")

    optional_categories = ["canonicals", "directives", "url_quality", "security"]
    for cat in optional_categories:
        count = by_cat.get(cat, 0)
        if count > 0:
            check(f"category '{cat}' has issues", True, f"count={count}")
        else:
            warn(f"category '{cat}' has 0 issues", "optional for books.toscrape.com")

    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=200")
    if code == 200 and isinstance(body, dict):
        all_types = {i.get("issue_type") for i in body.get("items", [])}
        check(
            f"found {len(all_types)} distinct issue types",
            len(all_types) >= 3,
            f"types={all_types}",
        )


def test_post_crawl_analysis(crawl_id: str):
    section("9. Post-Crawl Analysis")

    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=200")
    if code != 200 or not isinstance(body, dict):
        check("can fetch issues for post-crawl check", False)
        return

    all_types = {i.get("issue_type") for i in body.get("items", [])}

    post_crawl_types = {
        "duplicate_title",
        "duplicate_meta_description",
        "broken_internal_link",
    }
    found_post_crawl = all_types & post_crawl_types
    if found_post_crawl:
        check(f"post-crawl issues detected", True, f"found: {found_post_crawl}")
    else:
        warn(
            "no post-crawl issues detected",
            "may be normal if no duplicates exist in target",
        )


def test_indexability(crawl_id: str):
    section("10. Indexability Data")

    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?is_indexable=true&limit=5")
    check("filter is_indexable=true → 200", code == 200)
    if isinstance(body, dict):
        indexable_count = len(body.get("items", []))
        check("has indexable URLs", indexable_count > 0, f"count={indexable_count}")

    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?limit=1")
    if code == 200 and isinstance(body, dict):
        items = body.get("items", [])
        if items:
            url_id = items[0].get("id", "")
            code2, detail = api_call("GET", f"/crawls/{crawl_id}/urls/{url_id}")
            if code2 == 200 and isinstance(detail, dict):
                seo = detail.get("seo_data") or {}
                has_indexability = "is_indexable" in detail or "is_indexable" in seo
                check("URL detail has indexability info", has_indexability)


# ─── Client-Side ─────────────────────────────────────────────────


def test_frontend(crawl_id: str | None):
    section("11-13. Frontend Routes")

    code, body = http_get_raw(BASE_URL)
    check("GET / → 200", code == 200)
    is_html = "</html>" in body.lower() or "__next" in body.lower()
    check("/ serves HTML (Next.js)", is_html)

    code, body = http_get_raw(f"{BASE_URL}/crawls")
    check("GET /crawls → 200", code == 200)

    if crawl_id:
        code, body = http_get_raw(f"{BASE_URL}/crawls/{crawl_id}")
        check("GET /crawls/:id → 200", code == 200)


# ─── Cleanup ─────────────────────────────────────────────────────


def cleanup(project_id: str | None, crawl_id: str | None):
    section("Cleanup")
    if crawl_id:
        code, _ = api_call("DELETE", f"/crawls/{crawl_id}")
        check("DELETE crawl", code == 204, f"code={code}")
    if project_id:
        code, _ = api_call("DELETE", f"/projects/{project_id}")
        check("DELETE project", code == 204, f"code={code}")

    if project_id:
        code, _ = api_call("GET", f"/projects/{project_id}")
        check("project gone after delete", code == 404)


# ─── Main ────────────────────────────────────────────────────────


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — Full-Loop Feature Test{C.RESET}")
    print(f"  {C.DIM}Target: {CRAWL_TARGET}{C.RESET}")
    print(f"  {C.DIM}Max crawl wait: {MAX_CRAWL_WAIT}s{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None
    crawl_id = None

    try:
        if not test_health():
            print(f"\n{C.RED}ABORT: Health check failed — server not ready{C.RESET}")
            sys.exit(1)

        project_id = test_project_crud()
        if not project_id:
            print(f"\n{C.RED}ABORT: Project creation failed{C.RESET}")
            sys.exit(1)

        crawl_id = test_crawl_lifecycle(project_id)
        if not crawl_id:
            print(f"\n{C.RED}ABORT: Crawl did not complete successfully{C.RESET}")
            cleanup(project_id, None)
            sys.exit(1)

        test_crawled_urls(crawl_id)
        test_websocket(crawl_id)

        summary = test_issues_summary(crawl_id)
        test_issues_list(crawl_id)
        test_issue_type_coverage(crawl_id, summary)
        test_post_crawl_analysis(crawl_id)
        test_indexability(crawl_id)
        test_frontend(crawl_id)

    finally:
        cleanup(project_id, crawl_id)

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"  {C.GREEN}✓ {passed} passed{C.RESET}  ", end="")
    if warnings:
        print(f"{C.YELLOW}⚠ {warnings} warnings{C.RESET}  ", end="")
    if failed:
        print(f"{C.RED}✗ {failed} failed{C.RESET}  ", end="")
    total = passed + failed
    print(f"{C.DIM}({total} checks){C.RESET}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}ALL FEATURES WORKING ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} FEATURE(S) NEED ATTENTION{C.RESET}\n")

    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
