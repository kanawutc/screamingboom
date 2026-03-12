#!/usr/bin/env python3
"""
C1-C2: URL Endpoints — list with filters + detail shape validation.

Requires a completed crawl to test against.
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


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  C1-C2: URL Endpoints Test{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None
    crawl_id = None

    try:
        section("Setup")
        code, body = api_call(
            "POST", "/projects", {"name": "URL Test", "domain": CRAWL_TARGET}
        )
        project_id = body["id"] if code == 201 else None
        check("project created", project_id is not None)

        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 20, "max_depth": 2, "rate_limit_rps": 10.0},
            },
        )
        crawl_id = body.get("id") if code == 201 else None
        check("crawl started", crawl_id is not None)

        print(f"  {C.DIM}Waiting for crawl...{C.RESET}", end="", flush=True)
        for i in range(60):
            time.sleep(2)
            c, b = api_call("GET", f"/crawls/{crawl_id}")
            if (
                c == 200
                and isinstance(b, dict)
                and b.get("status") in ("completed", "failed")
            ):
                break
            if i % 5 == 0:
                print(".", end="", flush=True)
        print()
        check("crawl completed", b.get("status") == "completed")

        # ── C1: List URLs with Filters ────────────────────────────
        section("C1. List URLs + Filters")

        code, body = api_call("GET", f"/crawls/{crawl_id}/urls")
        check("list urls → 200", code == 200)
        items = body.get("items", []) if isinstance(body, dict) else []
        check(f"has {len(items)} URLs", len(items) > 0)
        check("has next_cursor", "next_cursor" in body)

        if items:
            first = items[0]
            check("URL has id", "id" in first)
            check("URL has url", "url" in first)
            check("URL has status_code", "status_code" in first)
            check("URL has content_type", "content_type" in first)
            check("URL has crawl_depth", "crawl_depth" in first)
            check("URL has is_indexable", "is_indexable" in first)
            check("URL has crawled_at", "crawled_at" in first)

        code, body = api_call("GET", f"/crawls/{crawl_id}/urls?status_code=200")
        ok_items = body.get("items", []) if isinstance(body, dict) else []
        all_200 = all(u.get("status_code") == 200 for u in ok_items)
        check(
            f"filter status_code=200 → {len(ok_items)} results, all 200",
            code == 200 and all_200,
        )

        code, body = api_call("GET", f"/crawls/{crawl_id}/urls?content_type=text/html")
        html_items = body.get("items", []) if isinstance(body, dict) else []
        check(
            f"filter content_type=text/html → {len(html_items)} results",
            code == 200 and len(html_items) > 0,
        )

        code, body = api_call("GET", f"/crawls/{crawl_id}/urls?is_indexable=true")
        idx_items = body.get("items", []) if isinstance(body, dict) else []
        all_idx = all(u.get("is_indexable") is True for u in idx_items)
        check(
            f"filter is_indexable=true → {len(idx_items)} results",
            code == 200 and all_idx,
        )

        code, body = api_call("GET", f"/crawls/{crawl_id}/urls?is_indexable=false")
        non_idx_items = body.get("items", []) if isinstance(body, dict) else []
        all_non_idx = all(u.get("is_indexable") is False for u in non_idx_items)
        check(
            f"filter is_indexable=false → {len(non_idx_items)} results",
            code == 200 and all_non_idx,
        )

        code, body = api_call("GET", f"/crawls/{crawl_id}/urls?cursor=garbage")
        check(
            "invalid cursor → empty page",
            code == 200 and isinstance(body.get("items"), list),
        )

        # ── C2: URL Detail ────────────────────────────────────────
        section("C2. URL Detail")

        if items:
            url_id = items[0]["id"]
            code, detail = api_call("GET", f"/crawls/{crawl_id}/urls/{url_id}")
            check("get url detail → 200", code == 200)

            expected_fields = [
                "id",
                "crawl_id",
                "url",
                "status_code",
                "content_type",
                "title",
                "meta_description",
                "crawl_depth",
                "response_time_ms",
                "is_indexable",
                "crawled_at",
                "title_length",
                "title_pixel_width",
                "meta_desc_length",
                "h1",
                "h2",
                "canonical_url",
                "robots_meta",
                "indexability_reason",
                "word_count",
                "seo_data",
            ]
            missing = [f for f in expected_fields if f not in detail]
            check(
                f"detail has all {len(expected_fields)} fields",
                len(missing) == 0,
                f"missing: {missing}",
            )

            if detail.get("title"):
                check(
                    "title_length == len(title)",
                    detail.get("title_length") == len(detail["title"]),
                    f"title_length={detail.get('title_length')}, len={len(detail['title'])}",
                )
                check(
                    "title_pixel_width > 0", (detail.get("title_pixel_width") or 0) > 0
                )

            check("word_count ≥ 0", (detail.get("word_count") or 0) >= 0)
            check("crawl_depth ≥ 0", detail.get("crawl_depth", -1) >= 0)
            check("response_time_ms ≥ 0", (detail.get("response_time_ms") or 0) >= 0)

        fake_url_id = str(uuid.uuid4())
        code, _ = api_call("GET", f"/crawls/{crawl_id}/urls/{fake_url_id}")
        check("nonexistent url_id → 404", code == 404)

    finally:
        section("Cleanup")
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
        print(f"\n  {C.GREEN}{C.BOLD}ALL URL ENDPOINT CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
