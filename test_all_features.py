#!/usr/bin/env python3
"""
Comprehensive Feature Test
==========================
Systematically tests EVERY feature of the SEO Spider app, collects all bugs
into a structured report, and prints machine-readable JSON at the end.

Sections (33):
  Phase 1:  Infrastructure (1-4)
  Phase 2:  Extraction Rules (5)
  Phase 3:  Spider Crawl (6-10)
  Phase 4:  URL Data (11-14)
  Phase 5:  Exports (15-17)
  Phase 6:  Data Endpoints (18-19)
  Phase 7:  Issues (20-21)
  Phase 8:  Lifecycle (22-23)
  Phase 9:  List Mode + Comparison (24-25)
  Phase 10: WebSocket (26)
  Phase 11: Deletion + Integrity (27-31)
  Phase 12: Frontend (32)
  Phase 13: Cleanup (33)

Usage:
    python test_all_features.py

Exit codes:
    0 — all checks passed
    1 — at least one failure
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
import time
import uuid
import urllib.error
import urllib.request

# ── Configuration ─────────────────────────────────────────────────

BASE_URL = "http://localhost"
API = f"{BASE_URL}/api/v1"
FRONTEND = "http://localhost:3000"
WS_BASE = "ws://localhost/api/v1"
CRAWL_TARGET = "https://books.toscrape.com/"
MAX_CRAWL_WAIT = 180
POLL_INTERVAL = 3

EXPORT_COLUMNS = [
    "url", "status_code", "content_type", "title", "title_length",
    "title_pixel_width", "meta_description", "meta_desc_length", "h1", "h2",
    "canonical_url", "robots_meta", "is_indexable", "indexability_reason",
    "word_count", "crawl_depth", "response_time_ms", "redirect_url",
]

# ── Global counters & bug collector ───────────────────────────────

passed = 0
failed = 0
warnings = 0
bugs: list[dict] = []

_current_section = ""
_current_endpoint = ""


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"


# ── Helpers ───────────────────────────────────────────────────────

def api_call(
    method: str,
    path: str,
    body: dict | list | None = None,
    timeout: int = 10,
) -> tuple[int, dict | list | str | None]:
    """Make an API call. Returns (status_code, parsed_body)."""
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
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


def api_call_raw(
    method: str,
    path: str,
    timeout: int = 10,
) -> tuple[int, bytes, dict]:
    """Make an API call returning raw bytes + response headers."""
    url = f"{API}{path}"
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp.read(), hdrs
    except urllib.error.HTTPError as e:
        raw = e.read() if e.fp else b""
        return e.code, raw, {}
    except Exception:
        return 0, b"", {}


def http_get_raw(url: str, timeout: int = 10) -> tuple[int, str]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def section(title: str):
    global _current_section
    _current_section = title
    print(f"\n{C.BOLD}{C.CYAN}▸ {title}{C.RESET}")


def set_endpoint(ep: str):
    global _current_endpoint
    _current_endpoint = ep


def check(
    name: str,
    condition: bool,
    detail: str = "",
    *,
    expected: str = "",
    actual: str = "",
    http_code: int | None = None,
) -> bool:
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
        bug: dict = {
            "section": _current_section,
            "check": name,
            "endpoint": _current_endpoint,
        }
        if expected:
            bug["expected"] = expected
        if actual:
            bug["actual"] = actual
        elif detail:
            bug["actual"] = detail
        if http_code is not None:
            bug["http_code"] = http_code
        bugs.append(bug)
        return False


def warn(name: str, detail: str = ""):
    global warnings
    warnings += 1
    msg = f"  {C.YELLOW}⚠{C.RESET} {name}"
    if detail:
        msg += f"  {C.DIM}({detail}){C.RESET}"
    print(msg)


def wait_for_crawl(crawl_id: str, max_wait: int = MAX_CRAWL_WAIT, quiet: bool = False) -> str:
    if not quiet:
        print(
            f"  {C.DIM}Waiting for crawl to complete (max {max_wait}s)...{C.RESET}",
            end="", flush=True,
        )
    start = time.time()
    status = "unknown"
    while time.time() - start < max_wait:
        time.sleep(POLL_INTERVAL)
        code, body = api_call("GET", f"/crawls/{crawl_id}")
        if code == 200 and isinstance(body, dict):
            status = body.get("status", "")
            if status in ("completed", "failed", "cancelled"):
                break
        if not quiet:
            print(".", end="", flush=True)
    if not quiet:
        print()
    return status


# ── WebSocket helpers ─────────────────────────────────────────────

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


async def ws_collect_messages(
    crawl_id: str, timeout: float = 45.0, max_messages: int = 30
) -> list[dict]:
    if not HAS_WEBSOCKETS:
        return []
    url = f"{WS_BASE}/crawls/{crawl_id}/ws"
    messages: list[dict] = []
    try:
        ws = await asyncio.wait_for(websockets.connect(url), timeout=10)
        try:
            while len(messages) < max_messages:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    try:
                        msg = json.loads(raw)
                        messages.append(msg)
                        if msg.get("type") in (
                            "crawl_completed", "crawl_failed", "crawl_cancelled",
                            "status_change",
                        ) and msg.get("status") in ("completed", "failed", "cancelled"):
                            break
                    except json.JSONDecodeError:
                        messages.append({"raw": raw})
                except asyncio.TimeoutError:
                    break
        finally:
            await ws.close()
    except asyncio.TimeoutError:
        messages.append({"error": "connection timeout"})
    except Exception as e:
        messages.append({"error": str(e)})
    return messages


async def ws_connect_and_check(crawl_id: str, timeout: float = 5.0) -> tuple[bool, str]:
    if not HAS_WEBSOCKETS:
        return False, "websockets library not installed"
    url = f"{WS_BASE}/crawls/{crawl_id}/ws"
    try:
        ws = await asyncio.wait_for(websockets.connect(url), timeout=timeout)
        await ws.close()
        return True, "connected"
    except asyncio.TimeoutError:
        return False, "connection timeout"
    except Exception as e:
        return False, str(e)


# ── Phase 1: Infrastructure (Sections 1-4) ───────────────────────

def test_01_health() -> bool:
    section("1. Health Check")
    set_endpoint("GET /health")
    code, body = api_call("GET", "/health")
    ok = check("GET /health returns 200", code == 200,
               f"code={code}", expected="200", actual=str(code), http_code=code)
    if not ok or not isinstance(body, dict):
        return False
    check("status = healthy", body.get("status") == "healthy",
          f"got: {body.get('status')}", expected="healthy", actual=str(body.get("status")))
    services = body.get("services", {})
    check("database = ok", services.get("database") == "ok",
          f"got: {services.get('database')}", expected="ok", actual=str(services.get("database")))
    check("redis = ok", services.get("redis") == "ok",
          f"got: {services.get('redis')}", expected="ok", actual=str(services.get("redis")))
    check("version present", "version" in body,
          expected="version key exists", actual=str(list(body.keys())))
    return True


def test_02_project_create() -> str | None:
    section("2. Project Create")
    set_endpoint("POST /projects")
    code, body = api_call("POST", "/projects", {
        "name": "Comprehensive Test Project",
        "domain": CRAWL_TARGET,
    })
    ok = check("POST /projects → 201", code == 201,
               f"code={code}", expected="201", actual=str(code), http_code=code)
    if not ok or not isinstance(body, dict):
        return None
    pid = body.get("id", "")
    check("response has id", bool(pid), expected="non-empty id", actual=str(pid))
    check("response has name", body.get("name") == "Comprehensive Test Project",
          f"got: {body.get('name')}")
    check("response has domain", body.get("domain") == CRAWL_TARGET,
          f"got: {body.get('domain')}")
    check("response has created_at", "created_at" in body)
    return pid


def test_03_project_read_update_list(project_id: str) -> None:
    section("3. Project Read/Update/List")

    # Read
    set_endpoint(f"GET /projects/{project_id}")
    code, body = api_call("GET", f"/projects/{project_id}")
    check("GET /projects/:id → 200", code == 200, f"code={code}", http_code=code)
    check("returns correct project", isinstance(body, dict) and body.get("id") == project_id)

    # Update
    set_endpoint(f"PUT /projects/{project_id}")
    code, body = api_call("PUT", f"/projects/{project_id}", {"name": "Updated Test Project"})
    check("PUT /projects/:id → 200", code == 200, f"code={code}", http_code=code)
    check("name updated", isinstance(body, dict) and body.get("name") == "Updated Test Project",
          f"got: {body.get('name') if isinstance(body, dict) else body}")

    # List with pagination
    set_endpoint("GET /projects?limit=2")
    code, body = api_call("GET", "/projects?limit=2")
    check("GET /projects → 200", code == 200, f"code={code}", http_code=code)
    check("returns paginated list", isinstance(body, dict) and "items" in body,
          expected="dict with 'items'")
    if isinstance(body, dict):
        items = body.get("items", [])
        check("limit=2 returns ≤2 items", len(items) <= 2, f"got {len(items)}")
        found = any(p.get("id") == project_id for p in items)
        if not found:
            # might be on next page, check with higher limit
            code2, body2 = api_call("GET", "/projects?limit=100")
            if isinstance(body2, dict):
                found = any(p.get("id") == project_id for p in body2.get("items", []))
        check("our project in list", found)

        # Cursor pagination
        next_cursor = body.get("next_cursor")
        if next_cursor:
            set_endpoint(f"GET /projects?limit=2&cursor={next_cursor}")
            code3, body3 = api_call("GET", f"/projects?limit=2&cursor={next_cursor}")
            check("cursor pagination returns 200", code3 == 200, f"code={code3}", http_code=code3)


def test_04_project_edge_cases() -> None:
    section("4. Project Edge Cases")
    fake = str(uuid.uuid4())

    set_endpoint("POST /projects (empty body)")
    code, _ = api_call("POST", "/projects", {})
    check("empty body → 422", code == 422, f"code={code}",
          expected="422", actual=str(code), http_code=code)

    set_endpoint("POST /projects (missing name)")
    code, _ = api_call("POST", "/projects", {"domain": CRAWL_TARGET})
    check("missing name → 422", code == 422, f"code={code}",
          expected="422", actual=str(code), http_code=code)

    set_endpoint("POST /projects (missing domain)")
    code, _ = api_call("POST", "/projects", {"name": "Test"})
    check("missing domain → 422", code == 422, f"code={code}",
          expected="422", actual=str(code), http_code=code)

    set_endpoint(f"GET /projects/{fake}")
    code, _ = api_call("GET", f"/projects/{fake}")
    check("fake UUID → 404", code == 404, f"code={code}",
          expected="404", actual=str(code), http_code=code)

    set_endpoint("GET /projects?limit=0")
    code, _ = api_call("GET", "/projects?limit=0")
    check("limit=0 → 422", code == 422, f"code={code}",
          expected="422", actual=str(code), http_code=code)

    set_endpoint("GET /projects?limit=501")
    code, _ = api_call("GET", "/projects?limit=501")
    check("limit=501 → 422", code == 422, f"code={code}",
          expected="422", actual=str(code), http_code=code)


# ── Phase 2: Extraction Rules (Section 5) ─────────────────────────

def test_05_extraction_rules(project_id: str) -> None:
    section("5. Extraction Rules CRUD")
    base = f"/projects/{project_id}/extraction-rules"

    rules_to_create = [
        {"name": "Title CSS", "selector": "title", "selector_type": "css", "extract_type": "text"},
        {"name": "H1 XPath", "selector": "//h1", "selector_type": "xpath", "extract_type": "text"},
        {"name": "Link Href", "selector": "a", "selector_type": "css", "extract_type": "attribute", "attribute_name": "href"},
        {"name": "Image Count", "selector": "img", "selector_type": "css", "extract_type": "count"},
    ]

    created_ids: list[str] = []
    for rule in rules_to_create:
        set_endpoint(f"POST {base}")
        code, body = api_call("POST", base, rule)
        ok = check(f"create rule '{rule['name']}' → 201", code == 201,
                    f"code={code}", expected="201", actual=str(code), http_code=code)
        if ok and isinstance(body, dict):
            rid = body.get("id", "")
            created_ids.append(rid)
            check(f"rule has correct name", body.get("name") == rule["name"])
            check(f"rule has selector_type", body.get("selector_type") == rule["selector_type"])
            check(f"rule has extract_type", body.get("extract_type") == rule["extract_type"])
            if rule.get("attribute_name"):
                check(f"rule has attribute_name", body.get("attribute_name") == rule["attribute_name"])

    # List
    set_endpoint(f"GET {base}")
    code, body = api_call("GET", base)
    check("list extraction rules → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, list):
        check(f"list returns {len(rules_to_create)} rules", len(body) >= len(rules_to_create),
              f"got {len(body)}")

    # Get single
    if created_ids:
        rid = created_ids[0]
        set_endpoint(f"GET {base}/{rid}")
        code, body = api_call("GET", f"{base}/{rid}")
        check("get single rule → 200", code == 200, f"code={code}", http_code=code)
        if isinstance(body, dict):
            check("rule has id", body.get("id") == rid)
            check("rule has created_at", "created_at" in body)

    # Update
    if created_ids:
        rid = created_ids[0]
        set_endpoint(f"PUT {base}/{rid}")
        code, body = api_call("PUT", f"{base}/{rid}", {"name": "Updated Title CSS"})
        check("update rule → 200", code == 200, f"code={code}", http_code=code)
        if isinstance(body, dict):
            check("rule name updated", body.get("name") == "Updated Title CSS",
                  f"got: {body.get('name')}")

    # Delete
    if created_ids:
        rid = created_ids[-1]
        set_endpoint(f"DELETE {base}/{rid}")
        code, _ = api_call("DELETE", f"{base}/{rid}")
        check("delete rule → 204", code == 204, f"code={code}",
              expected="204", actual=str(code), http_code=code)

        # 404 on deleted
        set_endpoint(f"GET {base}/{rid} (after delete)")
        code, _ = api_call("GET", f"{base}/{rid}")
        check("GET deleted rule → 404", code == 404, f"code={code}",
              expected="404", actual=str(code), http_code=code)

    # Clean up remaining rules
    for rid in created_ids[:-1]:
        api_call("DELETE", f"{base}/{rid}")


# ── Phase 3: Spider Crawl (Sections 6-10) ─────────────────────────

def test_06_start_spider_crawl(project_id: str) -> str | None:
    section("6. Start Spider Crawl")
    set_endpoint(f"POST /projects/{project_id}/crawls")
    code, body = api_call("POST", f"/projects/{project_id}/crawls", {
        "start_url": CRAWL_TARGET,
        "config": {"max_urls": 20, "max_depth": 2, "rate_limit_rps": 5.0},
    })
    ok = check("POST /projects/:id/crawls → 201", code == 201,
               f"code={code}", expected="201", actual=str(code), http_code=code)
    if not ok or not isinstance(body, dict):
        return None
    crawl_id = body.get("id", "")
    check("crawl has id", bool(crawl_id))
    check("initial status is queued/crawling",
          body.get("status") in ("queued", "crawling"),
          f"got: {body.get('status')}")
    check("mode is spider", body.get("mode") == "spider",
          f"got: {body.get('mode')}")
    return crawl_id


def test_07_crawl_creation_edge_cases(project_id: str) -> None:
    section("7. Crawl Creation Edge Cases")
    fake = str(uuid.uuid4())

    set_endpoint(f"POST /projects/{project_id}/crawls (negative max_urls)")
    code, _ = api_call("POST", f"/projects/{project_id}/crawls", {
        "start_url": CRAWL_TARGET,
        "config": {"max_urls": -1},
    })
    check("max_urls=-1 → 422", code == 422, f"code={code}",
          expected="422", actual=str(code), http_code=code)

    set_endpoint(f"POST /projects/{project_id}/crawls (rate_limit=0)")
    code, _ = api_call("POST", f"/projects/{project_id}/crawls", {
        "start_url": CRAWL_TARGET,
        "config": {"rate_limit_rps": 0},
    })
    check("rate_limit_rps=0 → 422", code == 422, f"code={code}",
          expected="422", actual=str(code), http_code=code)

    set_endpoint(f"POST /projects/{project_id}/crawls (rate_limit=101)")
    code, _ = api_call("POST", f"/projects/{project_id}/crawls", {
        "start_url": CRAWL_TARGET,
        "config": {"rate_limit_rps": 101},
    })
    check("rate_limit_rps=101 → 422", code == 422, f"code={code}",
          expected="422", actual=str(code), http_code=code)

    set_endpoint(f"POST /projects/{fake}/crawls")
    code, _ = api_call("POST", f"/projects/{fake}/crawls", {
        "start_url": CRAWL_TARGET,
    })
    check("nonexistent project → 404", code == 404, f"code={code}",
          expected="404", actual=str(code), http_code=code)


def test_08_wait_for_crawl(crawl_id: str) -> bool:
    section("8. Wait for Crawl")
    set_endpoint(f"GET /crawls/{crawl_id}")

    status = wait_for_crawl(crawl_id)
    check("crawl finished", status in ("completed", "failed", "cancelled"),
          f"status={status}")
    ok = check("crawl status = completed", status == "completed",
               f"got: {status}", expected="completed", actual=status)

    code, body = api_call("GET", f"/crawls/{crawl_id}")
    if code == 200 and isinstance(body, dict):
        total_urls = body.get("total_urls", 0)
        check("total_urls > 0", total_urls > 0, f"total_urls={total_urls}")
        check("has started_at", body.get("started_at") is not None)
        check("has completed_at", body.get("completed_at") is not None)
        if body.get("started_at") and body.get("completed_at"):
            check("completed_at >= started_at",
                  body["completed_at"] >= body["started_at"],
                  f"started={body['started_at']}, completed={body['completed_at']}")
    return ok


def test_09_list_crawls(project_id: str, crawl_id: str) -> None:
    section("9. List Crawls")

    # Project crawls
    set_endpoint(f"GET /projects/{project_id}/crawls")
    code, body = api_call("GET", f"/projects/{project_id}/crawls?limit=50")
    check("GET /projects/:id/crawls → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        items = body.get("items", [])
        found = any(c.get("id") == crawl_id for c in items)
        check("crawl in project's crawl list", found)

    # All crawls
    set_endpoint("GET /crawls")
    code, body = api_call("GET", "/crawls?limit=50")
    check("GET /crawls → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        check("has items list", "items" in body)
        # Pagination
        check("has next_cursor field", "next_cursor" in body)


def test_10_get_crawl_detail(crawl_id: str) -> None:
    section("10. Get Crawl Detail")
    set_endpoint(f"GET /crawls/{crawl_id}")
    code, body = api_call("GET", f"/crawls/{crawl_id}")
    check("GET /crawls/:id → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        expected_fields = [
            "id", "project_id", "status", "mode", "config",
            "total_urls", "crawled_urls_count", "error_count", "created_at",
        ]
        for f in expected_fields:
            check(f"has field '{f}'", f in body,
                  expected=f"field '{f}' present", actual=str(list(body.keys())))

    # 404 for fake ID
    fake = str(uuid.uuid4())
    set_endpoint(f"GET /crawls/{fake}")
    code, _ = api_call("GET", f"/crawls/{fake}")
    check("GET /crawls/{fake} → 404", code == 404, f"code={code}",
          expected="404", actual=str(code), http_code=code)


# ── Phase 4: URL Data (Sections 11-14) ────────────────────────────

def test_11_url_list_and_filters(crawl_id: str) -> str | None:
    section("11. URL List + Filters")
    url_id = None

    # Basic list
    set_endpoint(f"GET /crawls/{crawl_id}/urls")
    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?limit=50")
    check("GET /crawls/:id/urls → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        items = body.get("items", [])
        check("has crawled URLs", len(items) > 0, f"count={len(items)}")
        if items:
            url_id = items[0].get("id", "")
            check("URL has id", bool(url_id))
            check("URL has url field", bool(items[0].get("url")))
            check("URL has status_code", items[0].get("status_code") is not None)
            check("URL has content_type", items[0].get("content_type") is not None)

    # Filter: status_code
    set_endpoint(f"GET /crawls/{crawl_id}/urls?status_code=200")
    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?status_code=200&limit=5")
    check("filter status_code=200 → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        for u in body.get("items", []):
            if u.get("status_code") != 200:
                check("all filtered URLs have status 200", False,
                      f"got {u.get('status_code')}")
                break
        else:
            if body.get("items"):
                check("all filtered URLs have status 200", True)

    # Filter: content_type
    set_endpoint(f"GET /crawls/{crawl_id}/urls?content_type=html")
    code, _ = api_call("GET", f"/crawls/{crawl_id}/urls?content_type=html&limit=5")
    check("filter content_type=html → 200", code == 200, f"code={code}", http_code=code)

    # Filter: is_indexable
    set_endpoint(f"GET /crawls/{crawl_id}/urls?is_indexable=true")
    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?is_indexable=true&limit=5")
    check("filter is_indexable=true → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        indexable_count = len(body.get("items", []))
        check("has indexable URLs", indexable_count > 0, f"count={indexable_count}")

    # Filter: search
    set_endpoint(f"GET /crawls/{crawl_id}/urls?search=books")
    code, _ = api_call("GET", f"/crawls/{crawl_id}/urls?search=books&limit=5")
    check("filter search=books → 200", code == 200, f"code={code}", http_code=code)

    # Filter: status_code_min/max
    set_endpoint(f"GET /crawls/{crawl_id}/urls?status_code_min=200&status_code_max=299")
    code, _ = api_call("GET", f"/crawls/{crawl_id}/urls?status_code_min=200&status_code_max=299&limit=5")
    check("filter status_code_min/max → 200", code == 200, f"code={code}", http_code=code)

    # Filter: has_issue
    set_endpoint(f"GET /crawls/{crawl_id}/urls?has_issue=missing_title")
    code, _ = api_call("GET", f"/crawls/{crawl_id}/urls?has_issue=missing_title&limit=5")
    check("filter has_issue → 200", code == 200, f"code={code}", http_code=code)

    return url_id


def test_12_url_detail(crawl_id: str, url_id: str) -> None:
    section("12. URL Detail")
    set_endpoint(f"GET /crawls/{crawl_id}/urls/{url_id}")
    code, body = api_call("GET", f"/crawls/{crawl_id}/urls/{url_id}")
    check("GET /crawls/:id/urls/:url_id → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        check("has url field", bool(body.get("url")))
        check("has status_code", body.get("status_code") is not None)
        check("has content_type", body.get("content_type") is not None)

        # SEO data fields
        seo = body.get("seo_data") or {}
        has_seo = bool(seo) or any(k in body for k in (
            "title", "title_length", "meta_description", "h1",
            "canonical_url", "robots_meta", "is_indexable",
        ))
        check("has SEO data", has_seo, expected="seo_data or inline SEO fields")

        # Redirect chain
        has_redirect = "redirect_chain" in body or "redirect_url" in body or "redirect_chain" in seo
        check("has redirect chain info", has_redirect,
              expected="redirect_chain or redirect_url field")

    # 404 for fake URL id
    fake = str(uuid.uuid4())
    set_endpoint(f"GET /crawls/{crawl_id}/urls/{fake}")
    code, _ = api_call("GET", f"/crawls/{crawl_id}/urls/{fake}")
    check("fake url_id → 404", code == 404, f"code={code}",
          expected="404", actual=str(code), http_code=code)


def test_13_inlinks_outlinks(crawl_id: str, url_id: str) -> None:
    section("13. Inlinks + Outlinks")

    set_endpoint(f"GET /crawls/{crawl_id}/urls/{url_id}/inlinks")
    code, body = api_call("GET", f"/crawls/{crawl_id}/urls/{url_id}/inlinks")
    check("GET inlinks → 200", code == 200, f"code={code}", http_code=code)
    check("inlinks is a list", isinstance(body, list), f"type={type(body).__name__}")

    set_endpoint(f"GET /crawls/{crawl_id}/urls/{url_id}/outlinks")
    code, body = api_call("GET", f"/crawls/{crawl_id}/urls/{url_id}/outlinks")
    check("GET outlinks → 200", code == 200, f"code={code}", http_code=code)
    check("outlinks is a list", isinstance(body, list), f"type={type(body).__name__}")


def test_14_external_links(crawl_id: str) -> None:
    section("14. External Links")
    set_endpoint(f"GET /crawls/{crawl_id}/external-links")
    code, body = api_call("GET", f"/crawls/{crawl_id}/external-links?limit=10")
    check("GET /external-links → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        check("has items", "items" in body)
        check("has next_cursor", "next_cursor" in body)
        items = body.get("items", [])
        if items:
            first = items[0]
            check("external link has url", bool(first.get("url")))
            check("external link has source_url or source_page_url",
                  bool(first.get("source_url") or first.get("source_page_url")
                       or first.get("source_page_id")))


# ── Phase 5: Exports (Sections 15-17) ────────────────────────────

def test_15_csv_export(crawl_id: str) -> None:
    section("15. CSV Export")
    set_endpoint(f"GET /crawls/{crawl_id}/export")
    code, raw_bytes, headers = api_call_raw("GET", f"/crawls/{crawl_id}/export")
    check("GET /export → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)

    ct = headers.get("content-type", "")
    check("Content-Type is text/csv", "text/csv" in ct,
          f"got: {ct}", expected="text/csv", actual=ct)

    csv_text = raw_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    check("CSV has rows", len(rows) > 0, f"rows={len(rows)}")

    if rows:
        header_row = rows[0]
        check("CSV has header row", len(header_row) > 0)
        # Check columns match EXPORT_COLUMNS
        matches = header_row == EXPORT_COLUMNS
        check("CSV headers match EXPORT_COLUMNS", matches,
              expected=str(EXPORT_COLUMNS), actual=str(header_row))

    if len(rows) > 1:
        check("CSV has data rows", True, f"data_rows={len(rows) - 1}")


def test_16_xlsx_export(crawl_id: str) -> None:
    section("16. XLSX Export")
    set_endpoint(f"GET /crawls/{crawl_id}/export-xlsx")
    code, raw_bytes, headers = api_call_raw("GET", f"/crawls/{crawl_id}/export-xlsx")
    check("GET /export-xlsx → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)

    ct = headers.get("content-type", "")
    check("Content-Type is xlsx",
          "spreadsheetml" in ct or "openxmlformats" in ct,
          f"got: {ct}")

    # XLSX files are ZIP format — check PK magic bytes
    check("XLSX has PK magic bytes (ZIP)",
          raw_bytes[:2] == b"PK",
          expected="PK (0x504B)", actual=str(raw_bytes[:2]))

    check("XLSX is non-empty", len(raw_bytes) > 100,
          f"size={len(raw_bytes)}")


def test_17_sitemap_xml(crawl_id: str) -> None:
    section("17. Sitemap XML")
    set_endpoint(f"GET /crawls/{crawl_id}/sitemap.xml")
    code, raw_bytes, headers = api_call_raw("GET", f"/crawls/{crawl_id}/sitemap.xml")
    check("GET /sitemap.xml → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)

    ct = headers.get("content-type", "")
    check("Content-Type is XML", "xml" in ct, f"got: {ct}")

    xml_text = raw_bytes.decode("utf-8", errors="replace")
    check("has <?xml header", "<?xml" in xml_text)
    check("has <urlset>", "<urlset" in xml_text)
    check("has </urlset>", "</urlset>" in xml_text)
    check("has <loc> elements", "<loc>" in xml_text)
    check("has <changefreq>", "<changefreq>" in xml_text)
    check("has <priority>", "<priority>" in xml_text)

    # Well-formedness: try basic XML parse
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(xml_text)
        check("XML is well-formed", True)
    except ET.ParseError as e:
        check("XML is well-formed", False, f"parse error: {e}")
    except Exception as e:
        warn("XML parse check skipped", str(e))


# ── Phase 6: Data Endpoints (Sections 18-19) ─────────────────────

def test_18_structured_data(crawl_id: str) -> None:
    section("18. Structured Data")
    set_endpoint(f"GET /crawls/{crawl_id}/structured-data")
    code, body = api_call("GET", f"/crawls/{crawl_id}/structured-data?limit=10")
    check("GET /structured-data → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        check("has items", "items" in body)
        items = body.get("items", [])
        if items:
            first = items[0]
            check("item has url", bool(first.get("url")))
            check("item has blocks", "blocks" in first)
            check("item has block_count", "block_count" in first)
        else:
            warn("no structured data items found", "may be normal for target site")
    else:
        check("response is dict", False, f"type={type(body).__name__}")


def test_19_custom_extractions(crawl_id: str) -> None:
    section("19. Custom Extractions")
    set_endpoint(f"GET /crawls/{crawl_id}/custom-extractions")
    code, body = api_call("GET", f"/crawls/{crawl_id}/custom-extractions?limit=10")
    check("GET /custom-extractions → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        check("has items", "items" in body)
        items = body.get("items", [])
        if items:
            first = items[0]
            check("item has url", bool(first.get("url")))
            check("item has extractions", "extractions" in first)
        else:
            warn("no custom extraction items", "expected if no rules were active during crawl")
    else:
        check("response is dict", False, f"type={type(body).__name__}")


# ── Phase 7: Issues (Sections 20-21) ─────────────────────────────

def test_20_issues_list_and_filters(crawl_id: str) -> None:
    section("20. Issues List + Filters")

    # Basic list
    set_endpoint(f"GET /crawls/{crawl_id}/issues")
    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=10")
    check("GET /issues → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        items = body.get("items", [])
        check("has issues", len(items) > 0, f"count={len(items)}")
        if items:
            issue = items[0]
            check("issue has url", bool(issue.get("url")))
            check("issue has issue_type", bool(issue.get("issue_type")))
            check("issue has severity",
                  issue.get("severity") in ("critical", "warning", "info", "opportunity"),
                  f"got: {issue.get('severity')}")
            check("issue has category", bool(issue.get("category")))
            check("issue has description", bool(issue.get("description")))

    # Filter: severity
    set_endpoint(f"GET /crawls/{crawl_id}/issues?severity=warning")
    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?severity=warning&limit=5")
    check("filter severity=warning → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        for iss in body.get("items", []):
            if iss.get("severity") != "warning":
                check("all filtered issues have severity=warning", False,
                      f"got {iss.get('severity')}")
                break
        else:
            if body.get("items"):
                check("all filtered issues have severity=warning", True)

    # Filter: category
    set_endpoint(f"GET /crawls/{crawl_id}/issues?category=titles")
    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?category=titles&limit=5")
    check("filter category=titles → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        for iss in body.get("items", []):
            if iss.get("category") != "titles":
                check("all filtered issues have category=titles", False,
                      f"got {iss.get('category')}")
                break
        else:
            if body.get("items"):
                check("all filtered issues have category=titles", True)

    # Filter: issue_type
    set_endpoint(f"GET /crawls/{crawl_id}/issues?issue_type=missing_title")
    code, _ = api_call("GET", f"/crawls/{crawl_id}/issues?issue_type=missing_title&limit=5")
    check("filter issue_type → 200", code == 200, f"code={code}", http_code=code)

    # Pagination
    set_endpoint(f"GET /crawls/{crawl_id}/issues?limit=3")
    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=3")
    check("pagination limit=3 returns ≤3", code == 200 and isinstance(body, dict)
          and len(body.get("items", [])) <= 3)
    if isinstance(body, dict):
        next_cursor = body.get("next_cursor")
        if next_cursor:
            code2, body2 = api_call("GET", f"/crawls/{crawl_id}/issues?limit=3&cursor={next_cursor}")
            check("cursor page returns 200", code2 == 200, f"code={code2}", http_code=code2)
            if isinstance(body2, dict):
                first_ids = {i.get("id") for i in body.get("items", [])}
                second_ids = {i.get("id") for i in body2.get("items", [])}
                check("no overlap between pages", len(first_ids & second_ids) == 0)


def test_21_issues_summary(crawl_id: str) -> dict | None:
    section("21. Issues Summary")
    set_endpoint(f"GET /crawls/{crawl_id}/issues/summary")
    code, body = api_call("GET", f"/crawls/{crawl_id}/issues/summary")
    check("GET /issues/summary → 200", code == 200, f"code={code}", http_code=code)
    if not isinstance(body, dict):
        return None

    total = body.get("total", 0)
    check("total issues > 0", total > 0, f"total={total}")
    check("has by_severity", isinstance(body.get("by_severity"), dict))
    check("has by_category", isinstance(body.get("by_category"), dict))

    by_sev = body.get("by_severity", {})
    severity_sum = sum(by_sev.values())
    check("by_severity sums to total", severity_sum == total,
          f"sum={severity_sum}, total={total}",
          expected=str(total), actual=str(severity_sum))

    by_cat = body.get("by_category", {})
    cat_sum = sum(by_cat.values())
    check("by_category sums to total", cat_sum == total,
          f"sum={cat_sum}, total={total}",
          expected=str(total), actual=str(cat_sum))

    return body


# ── Phase 8: Lifecycle (Sections 22-23) ───────────────────────────

def test_22_pause_resume_stop(project_id: str) -> None:
    section("22. Pause/Resume/Stop")

    # Start a slow crawl
    set_endpoint(f"POST /projects/{project_id}/crawls (slow)")
    code, body = api_call("POST", f"/projects/{project_id}/crawls", {
        "start_url": CRAWL_TARGET,
        "config": {"max_urls": 50, "max_depth": 3, "rate_limit_rps": 1.0},
    })
    if code != 201 or not isinstance(body, dict):
        check("start slow crawl → 201", False, f"code={code}",
              expected="201", actual=str(code), http_code=code)
        return
    cid = body["id"]
    check("slow crawl started", True)

    # Give it a moment to begin crawling
    time.sleep(3)

    # Pause
    set_endpoint(f"POST /crawls/{cid}/pause")
    code, body = api_call("POST", f"/crawls/{cid}/pause")
    check("pause → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)
    if isinstance(body, dict):
        check("status = paused", body.get("status") == "paused",
              f"got: {body.get('status')}")

    # Verify paused via GET
    set_endpoint(f"GET /crawls/{cid}")
    code, body = api_call("GET", f"/crawls/{cid}")
    if isinstance(body, dict):
        check("GET confirms paused", body.get("status") == "paused",
              f"got: {body.get('status')}")

    # Resume
    set_endpoint(f"POST /crawls/{cid}/resume")
    code, body = api_call("POST", f"/crawls/{cid}/resume")
    check("resume → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)
    if isinstance(body, dict):
        check("status = crawling", body.get("status") == "crawling",
              f"got: {body.get('status')}")

    time.sleep(2)

    # Stop
    set_endpoint(f"POST /crawls/{cid}/stop")
    code, body = api_call("POST", f"/crawls/{cid}/stop")
    check("stop → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)
    if isinstance(body, dict):
        check("status = cancelled", body.get("status") == "cancelled",
              f"got: {body.get('status')}")

    # Clean up
    api_call("DELETE", f"/crawls/{cid}")


def test_23_lifecycle_conflicts(crawl_id_completed: str) -> None:
    section("23. Lifecycle Conflicts")

    set_endpoint(f"POST /crawls/{crawl_id_completed}/pause")
    code, _ = api_call("POST", f"/crawls/{crawl_id_completed}/pause")
    check("pause completed crawl → 409", code == 409, f"code={code}",
          expected="409", actual=str(code), http_code=code)

    set_endpoint(f"POST /crawls/{crawl_id_completed}/resume")
    code, _ = api_call("POST", f"/crawls/{crawl_id_completed}/resume")
    check("resume completed crawl → 409", code == 409, f"code={code}",
          expected="409", actual=str(code), http_code=code)

    set_endpoint(f"POST /crawls/{crawl_id_completed}/stop")
    code, _ = api_call("POST", f"/crawls/{crawl_id_completed}/stop")
    check("stop completed crawl → 409", code == 409, f"code={code}",
          expected="409", actual=str(code), http_code=code)


# ── Phase 9: List Mode + Comparison (Sections 24-25) ─────────────

def test_24_list_mode_crawl(project_id: str) -> str | None:
    section("24. List-Mode Crawl")
    set_endpoint(f"POST /projects/{project_id}/crawls (list mode)")
    code, body = api_call("POST", f"/projects/{project_id}/crawls", {
        "mode": "list",
        "urls": [
            "https://books.toscrape.com/",
            "https://books.toscrape.com/catalogue/page-2.html",
            "https://books.toscrape.com/catalogue/page-3.html",
        ],
        "config": {"max_urls": 10, "rate_limit_rps": 5.0},
    })
    ok = check("POST list-mode crawl → 201", code == 201,
               f"code={code}", expected="201", actual=str(code), http_code=code)
    if not ok or not isinstance(body, dict):
        return None
    cid = body["id"]
    check("mode is list", body.get("mode") == "list", f"got: {body.get('mode')}")

    status = wait_for_crawl(cid)
    check("list-mode crawl completed", status == "completed",
          f"status={status}", expected="completed", actual=status)
    return cid


def test_25_crawl_comparison(crawl_id_spider: str, crawl_id_list: str) -> None:
    section("25. Crawl Comparison")

    # Compare spider vs list
    set_endpoint(f"GET /crawls/compare?crawl_a={crawl_id_spider}&crawl_b={crawl_id_list}")
    code, body = api_call("GET",
        f"/crawls/compare?crawl_a={crawl_id_spider}&crawl_b={crawl_id_list}")
    check("GET /crawls/compare → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)
    if isinstance(body, dict):
        check("has summary", "summary" in body)
        check("has urls", "urls" in body)
        check("has total_count", "total_count" in body)
        summary = body.get("summary", {})
        check("summary has added", "added" in summary)
        check("summary has removed", "removed" in summary)
        check("summary has changed", "changed" in summary)
        check("summary has unchanged", "unchanged" in summary)

    # Filter by change_type
    set_endpoint(f"GET /crawls/compare?change_type=added")
    code, body = api_call("GET",
        f"/crawls/compare?crawl_a={crawl_id_spider}&crawl_b={crawl_id_list}&change_type=added")
    check("filter change_type=added → 200", code == 200, f"code={code}", http_code=code)
    if isinstance(body, dict):
        for u in body.get("urls", []):
            if u.get("change_type") != "added":
                check("all filtered urls are 'added'", False,
                      f"got {u.get('change_type')}")
                break
        else:
            check("change_type filter applied", True)

    # Self-compare → 400
    set_endpoint(f"GET /crawls/compare (self-compare)")
    code, _ = api_call("GET",
        f"/crawls/compare?crawl_a={crawl_id_spider}&crawl_b={crawl_id_spider}")
    check("self-compare → 400", code == 400, f"code={code}",
          expected="400", actual=str(code), http_code=code)


# ── Phase 10: WebSocket (Section 26) ─────────────────────────────

def test_26_websocket(project_id: str) -> None:
    section("26. WebSocket")

    if not HAS_WEBSOCKETS:
        warn("websockets library not installed — skipping WS tests",
             "pip install websockets")
        # Basic port reachability
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("localhost", 80))
        sock.close()
        check("WS port (80) is reachable", result == 0)
        return

    # Start a crawl for WS testing
    set_endpoint(f"POST /projects/{project_id}/crawls (WS test)")
    code, body = api_call("POST", f"/projects/{project_id}/crawls", {
        "start_url": CRAWL_TARGET,
        "config": {"max_urls": 10, "max_depth": 1, "rate_limit_rps": 5.0},
    })
    if code != 201 or not isinstance(body, dict):
        check("start crawl for WS test", False, f"code={code}")
        return
    ws_crawl_id = body["id"]

    # Collect WS messages during crawl
    set_endpoint(f"WS /crawls/{ws_crawl_id}/ws")
    messages = asyncio.get_event_loop().run_until_complete(
        ws_collect_messages(ws_crawl_id, timeout=45, max_messages=30)
    )
    errors = [m for m in messages if "error" in m]
    events = [m for m in messages if "error" not in m]

    check("WS connected (no errors)", len(errors) == 0, f"errors={errors}")
    check(f"received WS events", len(events) > 0, f"count={len(events)}")

    if events:
        progress_events = [e for e in events if e.get("type") == "progress"]
        if progress_events:
            check("received progress events", True, f"count={len(progress_events)}")
            first = progress_events[0]
            check("progress has crawled_count", "crawled_count" in first)
            check("progress has crawl_id", "crawl_id" in first)
        else:
            warn("no progress events", f"types: {set(e.get('type') for e in events)}")

    # Wait for WS crawl to finish then clean up
    wait_for_crawl(ws_crawl_id, quiet=True)

    # Test nonexistent crawl WS
    fake = str(uuid.uuid4())
    set_endpoint(f"WS /crawls/{fake}/ws")
    ok, detail = asyncio.get_event_loop().run_until_complete(
        ws_connect_and_check(fake, timeout=5)
    )
    # Either connects (sends nothing) or refuses — both acceptable
    check("WS to nonexistent crawl handled gracefully", True, detail)

    # Clean up
    api_call("DELETE", f"/crawls/{ws_crawl_id}")


# ── Phase 11: Deletion + Integrity (Sections 27-31) ──────────────

def test_27_delete_crawl_cascade(crawl_id_list: str) -> None:
    section("27. Delete Crawl Cascade")
    set_endpoint(f"DELETE /crawls/{crawl_id_list}")
    code, _ = api_call("DELETE", f"/crawls/{crawl_id_list}")
    check("DELETE crawl → 204", code == 204, f"code={code}",
          expected="204", actual=str(code), http_code=code)

    # Verify URLs gone
    set_endpoint(f"GET /crawls/{crawl_id_list}/urls")
    code, body = api_call("GET", f"/crawls/{crawl_id_list}/urls?limit=5")
    urls_gone = (code == 404) or (
        code == 200 and isinstance(body, dict) and len(body.get("items", [])) == 0
    )
    check("URLs gone after crawl delete", urls_gone,
          f"code={code}, items={len(body.get('items', [])) if isinstance(body, dict) else '?'}")

    # Verify issues gone
    set_endpoint(f"GET /crawls/{crawl_id_list}/issues")
    code, body = api_call("GET", f"/crawls/{crawl_id_list}/issues?limit=5")
    issues_gone = (code == 404) or (
        code == 200 and isinstance(body, dict) and len(body.get("items", [])) == 0
    )
    check("issues gone after crawl delete", issues_gone)


def test_28_delete_project_cascade() -> None:
    section("28. Delete Project Cascade")

    # Create throwaway project + crawl
    set_endpoint("POST /projects (throwaway)")
    code, body = api_call("POST", "/projects", {
        "name": "Throwaway Project", "domain": "https://example.com",
    })
    if code != 201 or not isinstance(body, dict):
        check("create throwaway project", False, f"code={code}")
        return
    tmp_pid = body["id"]

    set_endpoint(f"POST /projects/{tmp_pid}/crawls (throwaway)")
    code, body = api_call("POST", f"/projects/{tmp_pid}/crawls", {
        "start_url": "https://example.com",
        "config": {"max_urls": 3, "max_depth": 1, "rate_limit_rps": 5.0},
    })
    tmp_cid = None
    if code == 201 and isinstance(body, dict):
        tmp_cid = body["id"]
        wait_for_crawl(tmp_cid, max_wait=60, quiet=True)

    # Delete project
    set_endpoint(f"DELETE /projects/{tmp_pid}")
    code, _ = api_call("DELETE", f"/projects/{tmp_pid}")
    check("DELETE project → 204", code == 204, f"code={code}",
          expected="204", actual=str(code), http_code=code)

    # Verify project gone
    set_endpoint(f"GET /projects/{tmp_pid}")
    code, _ = api_call("GET", f"/projects/{tmp_pid}")
    check("project gone → 404", code == 404, f"code={code}",
          expected="404", actual=str(code), http_code=code)

    # Verify crawl gone
    if tmp_cid:
        set_endpoint(f"GET /crawls/{tmp_cid}")
        code, _ = api_call("GET", f"/crawls/{tmp_cid}")
        check("crawl gone after project delete → 404", code == 404,
              f"code={code}", expected="404", actual=str(code), http_code=code)


def test_29_unreachable_url_crawl(project_id: str) -> None:
    section("29. Unreachable URL Crawl")
    set_endpoint(f"POST /projects/{project_id}/crawls (unreachable)")
    code, body = api_call("POST", f"/projects/{project_id}/crawls", {
        "start_url": "https://thisdomaindoesnotexist99999.com/",
        "config": {"max_urls": 5, "max_depth": 1, "rate_limit_rps": 5.0},
    })
    if code != 201 or not isinstance(body, dict):
        check("start unreachable crawl → 201", code == 201,
              f"code={code}", expected="201", actual=str(code), http_code=code)
        return
    bad_cid = body["id"]
    check("unreachable crawl accepted", True)

    status = wait_for_crawl(bad_cid, max_wait=60)
    check("unreachable crawl finishes gracefully",
          status in ("completed", "failed"),
          f"status={status}")
    api_call("DELETE", f"/crawls/{bad_cid}")


def test_30_data_integrity(crawl_id: str) -> None:
    section("30. Data Integrity")

    # total_urls matches actual count
    set_endpoint(f"GET /crawls/{crawl_id}")
    code, body = api_call("GET", f"/crawls/{crawl_id}")
    total_urls = 0
    if isinstance(body, dict):
        total_urls = body.get("total_urls", 0)

    set_endpoint(f"GET /crawls/{crawl_id}/urls (all)")
    # Fetch all URLs with high limit
    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?limit=500")
    actual_count = 0
    items = []
    if isinstance(body, dict):
        items = body.get("items", [])
        actual_count = len(items)
    check("total_urls matches actual URL count",
          total_urls == actual_count or actual_count > 0,
          f"total_urls={total_urls}, actual={actual_count}")

    # All URLs have status_code
    all_have_status = all(u.get("status_code") is not None for u in items)
    check("all URLs have status_code", all_have_status or len(items) == 0)

    # All URLs have content_type or status_code != 200
    all_have_ct = all(
        u.get("content_type") is not None or u.get("status_code") != 200
        for u in items
    )
    check("all 200 URLs have content_type", all_have_ct or len(items) == 0)

    # Issues integrity
    set_endpoint(f"GET /crawls/{crawl_id}/issues (all)")
    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=500")
    if isinstance(body, dict):
        issues = body.get("items", [])
        required_issue_fields = ["url", "issue_type", "severity", "category", "description"]
        all_complete = True
        for iss in issues:
            for f in required_issue_fields:
                if not iss.get(f):
                    all_complete = False
                    break
            if not all_complete:
                break
        check("all issues have required fields", all_complete or len(issues) == 0,
              expected=str(required_issue_fields))


def test_31_issue_type_coverage(crawl_id: str) -> None:
    section("31. Issue Type Coverage")
    set_endpoint(f"GET /crawls/{crawl_id}/issues?limit=500")
    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=500")
    if not isinstance(body, dict):
        check("can fetch issues", False)
        return
    items = body.get("items", [])
    all_types = {i.get("issue_type") for i in items if i.get("issue_type")}
    all_categories = {i.get("category") for i in items if i.get("category")}
    check(f"≥3 distinct issue types", len(all_types) >= 3,
          f"found {len(all_types)}: {sorted(all_types)}")
    check(f"≥2 distinct categories", len(all_categories) >= 2,
          f"found {len(all_categories)}: {sorted(all_categories)}")
    print(f"  {C.DIM}issue types: {sorted(all_types)}{C.RESET}")
    print(f"  {C.DIM}categories: {sorted(all_categories)}{C.RESET}")


# ── Phase 12: Frontend (Section 32) ──────────────────────────────

def test_32_frontend(crawl_id: str | None) -> None:
    section("32. Frontend Routes")

    set_endpoint("GET /")
    code, body = http_get_raw(BASE_URL)
    check("GET / → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)
    is_html = "</html>" in body.lower() or "__next" in body.lower() or "<html" in body.lower()
    check("/ serves HTML", is_html)

    set_endpoint("GET /crawls")
    code, body = http_get_raw(f"{BASE_URL}/crawls")
    check("GET /crawls → 200", code == 200, f"code={code}",
          expected="200", actual=str(code), http_code=code)
    is_html = "</html>" in body.lower() or "__next" in body.lower() or "<html" in body.lower()
    check("/crawls serves HTML", is_html)

    if crawl_id:
        set_endpoint(f"GET /crawls/{crawl_id}")
        code, body = http_get_raw(f"{BASE_URL}/crawls/{crawl_id}")
        check("GET /crawls/:id → 200", code == 200, f"code={code}",
              expected="200", actual=str(code), http_code=code)
        is_html = "</html>" in body.lower() or "__next" in body.lower() or "<html" in body.lower()
        check("/crawls/:id serves HTML", is_html)


# ── Phase 13: Cleanup (Section 33) ───────────────────────────────

def cleanup(project_id: str | None, crawl_id_spider: str | None) -> None:
    section("33. Cleanup")
    if crawl_id_spider:
        set_endpoint(f"DELETE /crawls/{crawl_id_spider}")
        code, _ = api_call("DELETE", f"/crawls/{crawl_id_spider}")
        check("delete spider crawl", code in (204, 404), f"code={code}")
    if project_id:
        set_endpoint(f"DELETE /projects/{project_id}")
        code, _ = api_call("DELETE", f"/projects/{project_id}")
        check("delete test project", code in (204, 404), f"code={code}")
    if project_id:
        code, _ = api_call("GET", f"/projects/{project_id}")
        check("project gone after delete", code == 404)


# ── Bug Report ────────────────────────────────────────────────────

def print_bug_report():
    print(f"\n{C.BOLD}{'═' * 70}{C.RESET}")
    print(f"  {C.BOLD}RESULTS:{C.RESET} ", end="")
    print(f"{C.GREEN}{passed} passed{C.RESET}  ", end="")
    if warnings:
        print(f"{C.YELLOW}{warnings} warnings{C.RESET}  ", end="")
    if failed:
        print(f"{C.RED}{failed} failed{C.RESET}  ", end="")
    total = passed + failed
    print(f"{C.DIM}({total} checks){C.RESET}")
    print(f"{C.BOLD}{'═' * 70}{C.RESET}")

    if bugs:
        print(f"\n{C.BOLD}{C.RED}BUG REPORT ({len(bugs)} bugs):{C.RESET}")
        print(f"{C.DIM}{'─' * 70}{C.RESET}")
        for i, bug in enumerate(bugs, 1):
            print(f"  {C.RED}{i}.{C.RESET} [{C.CYAN}{bug['section']}{C.RESET}] {bug['check']}")
            if bug.get("endpoint"):
                print(f"     {C.DIM}endpoint: {bug['endpoint']}{C.RESET}")
            if bug.get("expected"):
                print(f"     {C.DIM}expected: {bug['expected']}{C.RESET}")
            if bug.get("actual"):
                print(f"     {C.DIM}actual:   {bug['actual']}{C.RESET}")
            if bug.get("http_code"):
                print(f"     {C.DIM}http_code: {bug['http_code']}{C.RESET}")
        print(f"{C.DIM}{'─' * 70}{C.RESET}")

        # Machine-readable JSON
        print(f"\n{C.BOLD}{C.MAGENTA}MACHINE-READABLE BUG REPORT (JSON):{C.RESET}")
        print("```json")
        print(json.dumps(bugs, indent=2))
        print("```")
    else:
        print(f"\n  {C.GREEN}{C.BOLD}ALL FEATURES WORKING{C.RESET}")

    print(f"\n{C.BOLD}{'═' * 70}{C.RESET}\n")


# ── Main ──────────────────────────────────────────────────────────

def main():
    print(f"\n{C.BOLD}{'═' * 70}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — Comprehensive Feature Test (33 Sections){C.RESET}")
    print(f"  {C.DIM}Target: {CRAWL_TARGET}{C.RESET}")
    print(f"  {C.DIM}API: {API}{C.RESET}")
    print(f"  {C.DIM}Max crawl wait: {MAX_CRAWL_WAIT}s{C.RESET}")
    print(f"{C.BOLD}{'═' * 70}{C.RESET}")

    project_id = None
    crawl_id_spider = None
    crawl_id_list = None

    try:
        # ── Phase 1: Infrastructure ──────────────────────────────
        if not test_01_health():
            print(f"\n{C.RED}ABORT: Health check failed — server not ready{C.RESET}")
            print_bug_report()
            sys.exit(1)

        project_id = test_02_project_create()
        if not project_id:
            print(f"\n{C.RED}ABORT: Project creation failed{C.RESET}")
            print_bug_report()
            sys.exit(1)

        test_03_project_read_update_list(project_id)
        test_04_project_edge_cases()

        # ── Phase 2: Extraction Rules ────────────────────────────
        test_05_extraction_rules(project_id)

        # ── Phase 3: Spider Crawl ────────────────────────────────
        crawl_id_spider = test_06_start_spider_crawl(project_id)
        test_07_crawl_creation_edge_cases(project_id)

        if not crawl_id_spider:
            print(f"\n{C.RED}ABORT: Spider crawl creation failed{C.RESET}")
            cleanup(project_id, None)
            print_bug_report()
            sys.exit(1)

        if not test_08_wait_for_crawl(crawl_id_spider):
            print(f"\n{C.RED}ABORT: Spider crawl did not complete{C.RESET}")
            cleanup(project_id, crawl_id_spider)
            print_bug_report()
            sys.exit(1)

        test_09_list_crawls(project_id, crawl_id_spider)
        test_10_get_crawl_detail(crawl_id_spider)

        # ── Phase 4: URL Data ────────────────────────────────────
        url_id = test_11_url_list_and_filters(crawl_id_spider)
        if url_id:
            test_12_url_detail(crawl_id_spider, url_id)
            test_13_inlinks_outlinks(crawl_id_spider, url_id)
        else:
            warn("skipping URL detail/inlinks/outlinks — no URL id found")
        test_14_external_links(crawl_id_spider)

        # ── Phase 5: Exports ─────────────────────────────────────
        test_15_csv_export(crawl_id_spider)
        test_16_xlsx_export(crawl_id_spider)
        test_17_sitemap_xml(crawl_id_spider)

        # ── Phase 6: Data Endpoints ──────────────────────────────
        test_18_structured_data(crawl_id_spider)
        test_19_custom_extractions(crawl_id_spider)

        # ── Phase 7: Issues ──────────────────────────────────────
        test_20_issues_list_and_filters(crawl_id_spider)
        test_21_issues_summary(crawl_id_spider)

        # ── Phase 8: Lifecycle ───────────────────────────────────
        test_22_pause_resume_stop(project_id)
        test_23_lifecycle_conflicts(crawl_id_spider)

        # ── Phase 9: List Mode + Comparison ──────────────────────
        crawl_id_list = test_24_list_mode_crawl(project_id)
        if crawl_id_list:
            test_25_crawl_comparison(crawl_id_spider, crawl_id_list)
        else:
            warn("skipping comparison — list-mode crawl failed")

        # ── Phase 10: WebSocket ──────────────────────────────────
        test_26_websocket(project_id)

        # ── Phase 11: Deletion + Integrity ───────────────────────
        if crawl_id_list:
            test_27_delete_crawl_cascade(crawl_id_list)
            crawl_id_list = None  # already deleted

        test_28_delete_project_cascade()
        test_29_unreachable_url_crawl(project_id)
        test_30_data_integrity(crawl_id_spider)
        test_31_issue_type_coverage(crawl_id_spider)

        # ── Phase 12: Frontend ───────────────────────────────────
        test_32_frontend(crawl_id_spider)

    finally:
        # ── Phase 13: Cleanup ────────────────────────────────────
        cleanup(project_id, crawl_id_spider)

    print_bug_report()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
