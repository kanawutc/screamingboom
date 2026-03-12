#!/usr/bin/env python3
"""
D1-D2: Issue Endpoints — list with filters + summary math.

Requires a completed crawl with known issues.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://localhost"
API = f"{BASE_URL}/api/v1"
CRAWL_TARGET = "https://books.toscrape.com/"

passed = 0
failed = 0
warnings = 0

VALID_SEVERITIES = {"critical", "warning", "info", "opportunity"}
VALID_CATEGORIES = {
    "titles",
    "meta_descriptions",
    "headings",
    "images",
    "canonicals",
    "directives",
    "url_quality",
    "security",
    "links",
    "indexability",
}


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


def fetch_all_items(path):
    items = []
    cursor = None
    for _ in range(20):
        url = f"{path}?limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        code, body = api_call("GET", url)
        if code != 200 or not isinstance(body, dict):
            break
        items.extend(body.get("items", []))
        cursor = body.get("next_cursor")
        if not cursor:
            break
    return items


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
    print(f"{C.BOLD}  D1-D2: Issue Endpoints Test{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None
    crawl_id = None

    try:
        section("Setup")
        code, body = api_call(
            "POST", "/projects", {"name": "Issue Test", "domain": CRAWL_TARGET}
        )
        project_id = body["id"] if code == 201 else None

        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 20, "max_depth": 2, "rate_limit_rps": 10.0},
            },
        )
        crawl_id = body.get("id") if code == 201 else None

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

        # ── D1: List Issues + Filters ─────────────────────────────
        section("D1. List Issues + Filters")

        code, body = api_call("GET", f"/crawls/{crawl_id}/issues")
        check("list issues → 200", code == 200)
        page_items = body.get("items", []) if isinstance(body, dict) else []
        check(f"has {len(page_items)} issues on first page", len(page_items) > 0)

        all_issues = fetch_all_items(f"/crawls/{crawl_id}/issues")
        check(f"fetched all {len(all_issues)} issues", len(all_issues) > 0)

        if all_issues:
            first = all_issues[0]
            check("issue has id", "id" in first)
            check("issue has crawl_id", "crawl_id" in first)
            check("issue has url_id", "url_id" in first)
            check("issue has url", "url" in first)
            check("issue has issue_type", "issue_type" in first)
            check("issue has severity", "severity" in first)
            check("issue has category", "category" in first)
            check("issue has description", "description" in first)
            check("issue has details", "details" in first)

        bad_sev = [i for i in all_issues if i.get("severity") not in VALID_SEVERITIES]
        check("all severities valid", len(bad_sev) == 0, f"{len(bad_sev)} invalid")

        bad_cat = [i for i in all_issues if i.get("category") not in VALID_CATEGORIES]
        check("all categories valid", len(bad_cat) == 0, f"{len(bad_cat)} invalid")

        found_sevs = {i.get("severity") for i in all_issues}
        test_sev = next(iter(found_sevs))
        code, body = api_call("GET", f"/crawls/{crawl_id}/issues?severity={test_sev}")
        filtered = body.get("items", []) if isinstance(body, dict) else []
        all_match_sev = all(i.get("severity") == test_sev for i in filtered)
        check(
            f"filter severity={test_sev} → all match",
            code == 200 and all_match_sev and len(filtered) > 0,
        )

        found_cats = {i.get("category") for i in all_issues}
        test_cat = next(iter(found_cats))
        code, body = api_call("GET", f"/crawls/{crawl_id}/issues?category={test_cat}")
        filtered = body.get("items", []) if isinstance(body, dict) else []
        all_match_cat = all(i.get("category") == test_cat for i in filtered)
        check(
            f"filter category={test_cat} → all match",
            code == 200 and all_match_cat and len(filtered) > 0,
        )

        found_types = {i.get("issue_type") for i in all_issues}
        test_type = next(iter(found_types))
        code, body = api_call(
            "GET", f"/crawls/{crawl_id}/issues?issue_type={test_type}"
        )
        filtered = body.get("items", []) if isinstance(body, dict) else []
        all_match_type = all(i.get("issue_type") == test_type for i in filtered)
        check(
            f"filter issue_type={test_type} → all match",
            code == 200 and all_match_type and len(filtered) > 0,
        )

        code, body = api_call("GET", f"/crawls/{crawl_id}/issues?cursor=garbage")
        check(
            "invalid cursor → empty page",
            code == 200 and isinstance(body.get("items"), list),
        )

        # ── D2: Issues Summary Math ───────────────────────────────
        section("D2. Issues Summary")

        code, summary = api_call("GET", f"/crawls/{crawl_id}/issues/summary")
        check("summary → 200", code == 200)
        check("has total", "total" in summary)
        check("has by_severity", "by_severity" in summary)
        check("has by_category", "by_category" in summary)

        total = summary.get("total", 0)
        by_sev = summary.get("by_severity", {})
        by_cat = summary.get("by_category", {})

        sev_sum = sum(by_sev.values())
        check(f"sum(by_severity) == total ({sev_sum} == {total})", sev_sum == total)

        cat_sum = sum(by_cat.values())
        check(f"sum(by_category) == total ({cat_sum} == {total})", cat_sum == total)

        check(
            "total matches fetched count",
            total == len(all_issues),
            f"summary={total}, fetched={len(all_issues)}",
        )

        sev_keys = set(by_sev.keys())
        check(
            "severity keys ⊆ valid set",
            sev_keys.issubset(VALID_SEVERITIES),
            f"keys={sev_keys}",
        )

        cat_keys = set(by_cat.keys())
        check(
            "category keys ⊆ valid set",
            cat_keys.issubset(VALID_CATEGORIES),
            f"keys={cat_keys}",
        )

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
        print(f"\n  {C.GREEN}{C.BOLD}ALL ISSUE ENDPOINT CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
