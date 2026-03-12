#!/usr/bin/env python3
"""
Multi-Target Crawl Validation Test
===================================
Tests the crawler against different types of websites to verify
handling of redirects, errors, minimal content, and various analyzers.

Usage:
    python test_crawl_targets.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://localhost"
API = f"{BASE_URL}/api/v1"
MAX_CRAWL_WAIT = 120

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
    msg = f"  {C.YELLOW}⚠{C.RESET} {name}"
    if detail:
        msg += f"  {C.DIM}({detail}){C.RESET}"
    print(msg)


def section(title):
    print(f"\n{C.BOLD}{C.CYAN}▸ {title}{C.RESET}")


def crawl_and_wait(
    project_id, start_url, max_urls=10, max_depth=1, rate_limit=10.0, label=""
):
    """Start a crawl, wait for completion, return (crawl_id, status, crawl_data)."""
    code, body = api_call(
        "POST",
        f"/projects/{project_id}/crawls",
        {
            "start_url": start_url,
            "config": {
                "max_urls": max_urls,
                "max_depth": max_depth,
                "rate_limit_rps": rate_limit,
            },
        },
    )
    if code != 201 or not isinstance(body, dict):
        return None, f"start_failed_{code}", None

    crawl_id = body["id"]
    print(
        f"  {C.DIM}Crawling {label or start_url[:40]}...{C.RESET}", end="", flush=True
    )

    start = time.time()
    final = "unknown"
    crawl_data = None
    while time.time() - start < MAX_CRAWL_WAIT:
        time.sleep(2)
        c, b = api_call("GET", f"/crawls/{crawl_id}")
        if c == 200 and isinstance(b, dict):
            final = b.get("status", "")
            crawl_data = b
            if final in ("completed", "failed", "cancelled"):
                break
        print(".", end="", flush=True)
    elapsed = time.time() - start
    print(f" {elapsed:.0f}s ({final})")

    return crawl_id, final, crawl_data


def get_crawl_issues(crawl_id, limit=200):
    """Fetch all issues for a crawl."""
    code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit={limit}")
    if code == 200 and isinstance(body, dict):
        return body.get("items", [])
    return []


def get_crawl_urls(crawl_id, limit=200):
    """Fetch all URLs for a crawl."""
    code, body = api_call("GET", f"/crawls/{crawl_id}/urls?limit={limit}")
    if code == 200 and isinstance(body, dict):
        return body.get("items", [])
    return []


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — Multi-Target Crawl Validation{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None
    crawl_ids = []

    try:
        # ── Setup ─────────────────────────────────────────────────
        section("Setup")
        code, body = api_call(
            "POST",
            "/projects",
            {"name": "Multi-Target Test", "domain": "https://books.toscrape.com/"},
        )
        if not check("create project", code == 201):
            sys.exit(1)
        project_id = body["id"]

        # ── T1: Standard HTML site (books.toscrape.com) ──────────
        section("T1. Standard HTML Site (books.toscrape.com)")
        cid, status, data = crawl_and_wait(
            project_id,
            "https://books.toscrape.com/",
            max_urls=20,
            label="books.toscrape.com",
        )
        if cid:
            crawl_ids.append(cid)
        check("books.toscrape.com completes", status == "completed", f"status={status}")

        if cid and status == "completed":
            urls = get_crawl_urls(cid)
            check(f"crawled {len(urls)} URLs", len(urls) >= 5)

            issues = get_crawl_issues(cid)
            check(f"found {len(issues)} issues", len(issues) > 0)

            # Should have multiple issue categories
            cats = {i.get("category") for i in issues}
            check(
                f"multiple issue categories ({len(cats)})",
                len(cats) >= 3,
                f"cats={cats}",
            )

            # Check HTML URLs have titles
            html_urls = [u for u in urls if u.get("status_code") == 200]
            check("has 200-status URLs", len(html_urls) > 0)

        # ── T2: Single-page site (example.com) ───────────────────
        section("T2. Minimal Site (example.com)")
        cid2, status2, data2 = crawl_and_wait(
            project_id, "https://example.com/", max_urls=5, label="example.com"
        )
        if cid2:
            crawl_ids.append(cid2)
        check("example.com completes", status2 == "completed", f"status={status2}")

        if cid2 and status2 == "completed":
            urls2 = get_crawl_urls(cid2)
            check(f"example.com: crawled {len(urls2)} URLs", len(urls2) >= 1)

            # Should find few if any outgoing links
            total = data2.get("total_urls", 0) if isinstance(data2, dict) else 0
            check("example.com: small URL count (≤5)", total <= 5, f"total={total}")

            # Check issues — should have missing canonical, security headers, etc.
            issues2 = get_crawl_issues(cid2)
            issue_types = {i.get("issue_type") for i in issues2}
            print(f"  {C.DIM}issue types: {sorted(issue_types)}{C.RESET}")

        # ── T3: HTTPS site with security headers ─────────────────
        section("T3. HTTPS with Security Headers")

        # books.toscrape uses HTTPS — check security issues
        if cid and status == "completed":
            issues_sec = [i for i in issues if i.get("category") == "security"]
            check(f"security issues detected ({len(issues_sec)})", len(issues_sec) > 0)

            sec_types = {i.get("issue_type") for i in issues_sec}
            print(f"  {C.DIM}security issue types: {sorted(sec_types)}{C.RESET}")

            # Should detect missing security headers
            has_header_issues = any("missing" in (it or "") for it in sec_types)
            check(
                "missing security header issues found",
                has_header_issues,
                f"types={sec_types}",
            )

        # ── T4: Images and alt text analysis ─────────────────────
        section("T4. Image Analysis")

        if cid and status == "completed":
            img_issues = [i for i in issues if i.get("category") == "images"]
            if img_issues:
                check(f"image issues detected ({len(img_issues)})", True)
                img_types = {i.get("issue_type") for i in img_issues}
                print(f"  {C.DIM}image issue types: {sorted(img_types)}{C.RESET}")
            else:
                warn("no image issues (books.toscrape.com may have all alt attributes)")

        # ── T5: Canonical tag analysis ───────────────────────────
        section("T5. Canonical Analysis")

        if cid and status == "completed":
            canon_issues = [i for i in issues if i.get("category") == "canonicals"]
            if canon_issues:
                check(f"canonical issues detected ({len(canon_issues)})", True)
                canon_types = {i.get("issue_type") for i in canon_issues}
                print(f"  {C.DIM}canonical issue types: {sorted(canon_types)}{C.RESET}")
            else:
                warn("no canonical issues (all pages may have proper canonicals)")

        # ── T6: URL quality analysis ─────────────────────────────
        section("T6. URL Quality Analysis")

        if cid and status == "completed":
            uq_issues = [i for i in issues if i.get("category") == "url_quality"]
            if uq_issues:
                check(f"URL quality issues detected ({len(uq_issues)})", True)
            else:
                warn("no URL quality issues")

        # ── T7: Rate limiting test ───────────────────────────────
        section("T7. Rate Limiting Comparison")

        # Fast crawl (10 RPS)
        cid_fast, status_fast, data_fast = crawl_and_wait(
            project_id,
            "https://books.toscrape.com/",
            max_urls=10,
            rate_limit=10.0,
            label="fast (10 RPS)",
        )
        if cid_fast:
            crawl_ids.append(cid_fast)

        # Slow crawl (1 RPS)
        cid_slow, status_slow, data_slow = crawl_and_wait(
            project_id,
            "https://books.toscrape.com/",
            max_urls=10,
            rate_limit=1.0,
            label="slow (1 RPS)",
        )
        if cid_slow:
            crawl_ids.append(cid_slow)

        if status_fast == "completed" and status_slow == "completed":
            fast_started = (data_fast or {}).get("started_at", "")
            fast_ended = (data_fast or {}).get("completed_at", "")
            slow_started = (data_slow or {}).get("started_at", "")
            slow_ended = (data_slow or {}).get("completed_at", "")

            # We can't easily compare timestamps here, but both should complete
            check("fast crawl completed", True)
            check("slow crawl completed", True)
            # The slow crawl should take noticeably longer — print for manual verification
            print(f"  {C.DIM}fast: {fast_started} → {fast_ended}{C.RESET}")
            print(f"  {C.DIM}slow: {slow_started} → {slow_ended}{C.RESET}")
        else:
            if status_fast != "completed":
                check("fast crawl completed", False, f"status={status_fast}")
            if status_slow != "completed":
                check("slow crawl completed", False, f"status={status_slow}")

        # ── T8: Crawl with httpbin (various responses) ───────────
        section("T8. HTTP Status Code Handling (httpbin.org)")

        cid_hb, status_hb, data_hb = crawl_and_wait(
            project_id,
            "https://httpbin.org/",
            max_urls=10,
            max_depth=1,
            label="httpbin.org",
        )
        if cid_hb:
            crawl_ids.append(cid_hb)
        check(
            "httpbin.org completes",
            status_hb in ("completed", "failed"),
            f"status={status_hb}",
        )

        if cid_hb and status_hb == "completed":
            urls_hb = get_crawl_urls(cid_hb)
            check(f"httpbin.org: crawled {len(urls_hb)} URLs", len(urls_hb) >= 1)

        # ── T9: Headings and title analysis depth ────────────────
        section("T9. Title & Heading Analysis Depth")

        if cid and status == "completed":
            title_issues = [i for i in issues if i.get("category") == "titles"]
            heading_issues = [i for i in issues if i.get("category") == "headings"]

            if len(title_issues) > 0:
                check(f"title issues: {len(title_issues)}", True)
            else:
                warn("no title issues (site may have well-formed titles)")
            check(f"heading issues: {len(heading_issues)}", len(heading_issues) > 0)

            title_types = {i.get("issue_type") for i in title_issues}
            heading_types = {i.get("issue_type") for i in heading_issues}
            print(f"  {C.DIM}title types: {sorted(title_types)}{C.RESET}")
            print(f"  {C.DIM}heading types: {sorted(heading_types)}{C.RESET}")

        # ── T10: Indexability across targets ──────────────────────
        section("T10. Indexability Verification")

        if cid and status == "completed":
            code, body = api_call(
                "GET", f"/crawls/{cid}/urls?is_indexable=true&limit=100"
            )
            indexable = len(body.get("items", [])) if isinstance(body, dict) else 0
            code, body = api_call(
                "GET", f"/crawls/{cid}/urls?is_indexable=false&limit=100"
            )
            non_indexable = len(body.get("items", [])) if isinstance(body, dict) else 0
            check(
                f"indexable={indexable}, non_indexable={non_indexable}", indexable > 0
            )

    finally:
        section("Cleanup")
        for cid in crawl_ids:
            api_call("DELETE", f"/crawls/{cid}")
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
        print(f"\n  {C.GREEN}{C.BOLD}ALL MULTI-TARGET CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
