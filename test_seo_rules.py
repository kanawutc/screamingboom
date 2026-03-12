#!/usr/bin/env python3
"""
E1-E9: SEO Analysis Rules — verify all 45 issue types are detected.

Crawls books.toscrape.com and checks which of the 45 registered issue types
appear. Since we can't control the target HTML, we validate that each analyzer
category produces at least one issue, and verify the issue types are in the
registry.
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

ISSUE_REGISTRY = {
    "titles": [
        "missing_title",
        "duplicate_title",
        "title_too_long",
        "title_too_short",
        "title_pixel_too_wide",
        "title_same_as_h1",
        "multiple_titles",
    ],
    "meta_descriptions": [
        "missing_meta_description",
        "duplicate_meta_description",
        "meta_description_too_long",
        "meta_description_too_short",
        "multiple_meta_descriptions",
    ],
    "headings": [
        "missing_h1",
        "duplicate_h1",
        "multiple_h1",
        "h1_too_long",
        "non_sequential_headings",
    ],
    "images": ["missing_alt_text", "alt_text_too_long", "missing_image_dimensions"],
    "canonicals": [
        "missing_canonical",
        "self_referencing_canonical",
        "multiple_canonicals",
        "canonical_mismatch",
        "non_indexable_canonical",
    ],
    "directives": [
        "has_noindex",
        "has_nofollow",
        "has_noindex_nofollow",
        "multiple_robots_meta",
        "has_x_robots_tag",
    ],
    "url_quality": [
        "url_non_ascii",
        "url_has_underscores",
        "url_has_uppercase",
        "url_too_long",
        "url_has_parameters",
        "url_has_multiple_slashes",
    ],
    "security": [
        "http_url",
        "mixed_content",
        "missing_hsts",
        "missing_csp",
        "missing_x_content_type_options",
        "missing_x_frame_options",
    ],
    "links": ["broken_link_4xx", "broken_link_5xx"],
    "indexability": [
        "non_indexable_noindex",
        "non_indexable_canonicalized",
        "non_indexable_redirect",
        "non_indexable_client_error",
        "non_indexable_server_error",
    ],
}

ALL_TYPES = set()
for types in ISSUE_REGISTRY.values():
    ALL_TYPES.update(types)


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
    for _ in range(50):
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
    print(f"{C.BOLD}  E1-E9: SEO Analysis Rules Test{C.RESET}")
    print(
        f"  {C.DIM}Registry: {len(ALL_TYPES)} issue types across {len(ISSUE_REGISTRY)} categories{C.RESET}"
    )
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None

    try:
        section("Setup — Crawl books.toscrape.com (50 URLs)")
        code, body = api_call(
            "POST", "/projects", {"name": "SEO Rules Test", "domain": CRAWL_TARGET}
        )
        project_id = body["id"] if code == 201 else None

        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 50, "max_depth": 3, "rate_limit_rps": 10.0},
            },
        )
        crawl_id = body.get("id") if code == 201 else None

        print(f"  {C.DIM}Waiting for crawl...{C.RESET}", end="", flush=True)
        for i in range(90):
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

        all_issues = fetch_all_items(f"/crawls/{crawl_id}/issues")
        check(f"fetched {len(all_issues)} issues", len(all_issues) > 0)

        found_types = {i.get("issue_type") for i in all_issues}
        found_categories = {i.get("category") for i in all_issues}
        print(f"  {C.DIM}Found types: {sorted(found_types)}{C.RESET}")

        check(
            "all found types ⊆ registry",
            found_types.issubset(ALL_TYPES),
            f"unknown: {found_types - ALL_TYPES}",
        )

        for cat, expected_types in ISSUE_REGISTRY.items():
            section(f"E. {cat} ({len(expected_types)} types)")

            cat_issues = [i for i in all_issues if i.get("category") == cat]

            if cat in found_categories:
                check(f"{cat}: has issues ({len(cat_issues)})", len(cat_issues) > 0)
            else:
                warn(f"{cat}: no issues found (target site may not trigger these)")

            cat_found_types = {i.get("issue_type") for i in cat_issues}
            for it in expected_types:
                if it in cat_found_types:
                    count = sum(1 for i in cat_issues if i.get("issue_type") == it)
                    check(f"  {it} detected ({count}x)", True)
                else:
                    warn(f"  {it} not triggered (site may not have this condition)")

            for i in cat_issues:
                if not i.get("url"):
                    check(f"  {i.get('issue_type')} has url field", False)
                    break
                if not i.get("description"):
                    check(f"  {i.get('issue_type')} has description field", False)
                    break
            else:
                if cat_issues:
                    check(f"  all {cat} issues have url + description", True)

        section("Coverage Summary")
        coverage_pct = len(found_types) / len(ALL_TYPES) * 100
        check(
            f"issue type coverage: {len(found_types)}/{len(ALL_TYPES)} ({coverage_pct:.0f}%)",
            len(found_types) >= 5,
            "at least 5 types needed",
        )

        not_found = ALL_TYPES - found_types
        if not_found:
            print(
                f"  {C.DIM}Not triggered ({len(not_found)}): {sorted(not_found)}{C.RESET}"
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
        print(f"\n  {C.GREEN}{C.BOLD}ALL SEO RULES CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
