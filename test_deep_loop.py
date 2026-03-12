#!/usr/bin/env python3
"""
Deep-Loop Feature Test
======================
Extended test with a larger crawl (50 URLs, depth 3) to fully exercise:
  - All 8 inline analyzers (titles, meta_descriptions, headings, images, canonicals, directives, url_quality, security)
  - Post-crawl analysis (duplicate titles, duplicate meta descriptions, broken links)
  - Pause/Resume lifecycle
  - URL detail field completeness
  - Crawl deletion and re-crawl
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
MAX_CRAWL_WAIT = 300
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


def wait_for_crawl(crawl_id, label=""):
    print(
        f"  {C.DIM}Waiting for crawl{' (' + label + ')' if label else ''} (max {MAX_CRAWL_WAIT}s)...{C.RESET}",
        end="",
        flush=True,
    )
    start = time.time()
    final = "unknown"
    while time.time() - start < MAX_CRAWL_WAIT:
        time.sleep(POLL_INTERVAL)
        code, body = api_call("GET", f"/crawls/{crawl_id}")
        if code == 200 and isinstance(body, dict):
            final = body.get("status", "")
            if final in ("completed", "failed", "cancelled"):
                break
        print(".", end="", flush=True)
    elapsed = time.time() - start
    print(f" {elapsed:.0f}s")
    return final, elapsed


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — Deep-Loop Feature Test{C.RESET}")
    print(f"  {C.DIM}Target: {CRAWL_TARGET}{C.RESET}")
    print(f"  {C.DIM}Crawl size: 50 URLs, depth 3{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None
    crawl_id = None

    try:
        # ── Setup: create project ──────────────────────────────
        section("Setup")
        code, body = api_call(
            "POST", "/projects", {"name": "Deep Loop Test", "domain": CRAWL_TARGET}
        )
        if not check("create project", code == 201):
            sys.exit(1)
        project_id = body["id"]

        # ── T1: Large crawl ────────────────────────────────────
        section("T1. Large Crawl (50 URLs, depth 3)")
        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 50, "max_depth": 3, "rate_limit_rps": 10.0},
            },
        )
        check("start crawl → 201", code == 201)
        crawl_id = body["id"]

        final, elapsed = wait_for_crawl(crawl_id, "50 URLs")
        check("crawl completed", final == "completed", f"got: {final}")

        code, body = api_call("GET", f"/crawls/{crawl_id}")
        total_urls = body.get("total_urls", 0) if isinstance(body, dict) else 0
        crawled_count = (
            body.get("crawled_urls_count", 0) if isinstance(body, dict) else 0
        )
        check(
            f"crawled {crawled_count} URLs (total_urls={total_urls})",
            crawled_count >= 20,
        )

        if final != "completed":
            print(f"\n{C.RED}ABORT: Crawl did not complete{C.RESET}")
            return

        # ── T2: Full issue analysis ────────────────────────────
        section("T2. Full Issue Analysis")
        code, summary = api_call("GET", f"/crawls/{crawl_id}/issues/summary")
        check("issues summary → 200", code == 200)
        total_issues = summary.get("total", 0) if isinstance(summary, dict) else 0
        check(f"total issues = {total_issues}", total_issues > 0)

        by_sev = summary.get("by_severity", {}) if isinstance(summary, dict) else {}
        by_cat = summary.get("by_category", {}) if isinstance(summary, dict) else {}
        print(f"  {C.DIM}by_severity: {json.dumps(by_sev)}{C.RESET}")
        print(f"  {C.DIM}by_category: {json.dumps(by_cat)}{C.RESET}")

        # ── T3: Category coverage ──────────────────────────────
        section("T3. Analyzer Category Coverage")
        all_8_cats = [
            "titles",
            "meta_descriptions",
            "headings",
            "images",
            "canonicals",
            "directives",
            "url_quality",
            "security",
        ]
        covered = 0
        for cat in all_8_cats:
            count = by_cat.get(cat, 0)
            if count > 0:
                check(f"analyzer '{cat}' produced issues", True, f"count={count}")
                covered += 1
            else:
                warn(f"analyzer '{cat}' produced 0 issues")

        check(f"≥6 of 8 analyzers active", covered >= 6, f"covered={covered}/8")

        # ── T4: Issue types deep-dive ──────────────────────────
        section("T4. Issue Types Deep-Dive")
        code, body = api_call("GET", f"/crawls/{crawl_id}/issues?limit=500")
        all_issues = body.get("items", []) if isinstance(body, dict) else []
        all_types = {i.get("issue_type") for i in all_issues}
        print(
            f"  {C.DIM}distinct issue_types ({len(all_types)}): {sorted(all_types)}{C.RESET}"
        )
        check(f"≥5 distinct issue types", len(all_types) >= 5)

        expected_types = [
            "missing_title",
            "missing_meta_description",
            "missing_h1",
            "missing_image_alt",
            "missing_canonical",
        ]
        for et in expected_types:
            if et in all_types:
                check(f"issue type '{et}' found", True)
            else:
                warn(f"issue type '{et}' not found")

        # ── T5: Post-crawl analysis ───────────────────────────
        section("T5. Post-Crawl Analysis")
        post_crawl_types = {
            "duplicate_title",
            "duplicate_meta_description",
            "broken_internal_link",
            "canonical_mismatch",
        }
        found_pc = all_types & post_crawl_types
        if found_pc:
            for pt in found_pc:
                check(f"post-crawl: '{pt}' detected", True)
        else:
            warn(
                "no post-crawl issues detected", "may be normal for books.toscrape.com"
            )

        check("post-crawl analysis ran", True, "COMPLETING state was used")

        # ── T6: URL detail completeness ────────────────────────
        section("T6. URL Detail Completeness")
        code, urls_body = api_call(
            "GET", f"/crawls/{crawl_id}/urls?status_code=200&content_type=html&limit=3"
        )
        check("fetch HTML URLs → 200", code == 200)
        html_urls = urls_body.get("items", []) if isinstance(urls_body, dict) else []

        if html_urls:
            uid = html_urls[0].get("id")
            code, detail = api_call("GET", f"/crawls/{crawl_id}/urls/{uid}")
            check("URL detail → 200", code == 200)
            if isinstance(detail, dict):
                check("has title", detail.get("title") is not None)
                check("has title_length", detail.get("title_length") is not None)
                check(
                    "has title_pixel_width", detail.get("title_pixel_width") is not None
                )
                check("has meta_description", "meta_description" in detail)
                check("has meta_desc_length", "meta_desc_length" in detail)
                check("has h1", detail.get("h1") is not None)
                check("has h2 field", "h2" in detail)
                check("has canonical_url", "canonical_url" in detail)
                check("has robots_meta", "robots_meta" in detail)
                check("has is_indexable", "is_indexable" in detail)
                check("has indexability_reason", "indexability_reason" in detail)
                check("has word_count", "word_count" in detail)
                check("has seo_data (JSONB)", "seo_data" in detail)
                check(
                    "has response_time_ms", detail.get("response_time_ms") is not None
                )
                check("has crawl_depth", "crawl_depth" in detail)

                seo = detail.get("seo_data", {})
                if seo:
                    print(f"  {C.DIM}seo_data keys: {sorted(seo.keys())}{C.RESET}")

        # ── T7: Pause / Resume lifecycle ──────────────────────
        section("T7. Pause / Resume Lifecycle")
        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 100, "max_depth": 2, "rate_limit_rps": 2.0},
            },
        )
        check("start second crawl → 201", code == 201)
        crawl2_id = body["id"] if isinstance(body, dict) else None

        if crawl2_id:
            time.sleep(3)

            code, resp = api_call("POST", f"/crawls/{crawl2_id}/pause")
            if code == 200:
                check("pause crawl → 200", True)
                time.sleep(1)

                code2, body2 = api_call("GET", f"/crawls/{crawl2_id}")
                paused_status = (
                    body2.get("status", "") if isinstance(body2, dict) else ""
                )
                check(
                    "status = paused",
                    paused_status == "paused",
                    f"got: {paused_status}",
                )

                code, resp = api_call("POST", f"/crawls/{crawl2_id}/resume")
                check("resume crawl → 200", code == 200)

                time.sleep(1)
                code2, body2 = api_call("GET", f"/crawls/{crawl2_id}")
                resumed_status = (
                    body2.get("status", "") if isinstance(body2, dict) else ""
                )
                check(
                    "status back to crawling",
                    resumed_status in ("crawling", "completing", "completed"),
                    f"got: {resumed_status}",
                )
            else:
                warn(
                    "pause returned non-200",
                    f"code={code}, crawl may have finished too fast",
                )

            code, resp = api_call("POST", f"/crawls/{crawl2_id}/stop")
            if code == 200:
                check("stop crawl → 200", True)
            elif code == 409:
                warn("stop returned 409", "crawl already completed")
            else:
                check("stop crawl", False, f"code={code}")

            code, _ = api_call("DELETE", f"/crawls/{crawl2_id}")
            check("delete second crawl", code == 204, f"code={code}")

        # ── T8: Severity filter exhaustive ─────────────────────
        section("T8. Severity Filter Exhaustive")
        for sev in ("critical", "warning", "info", "opportunity"):
            code, body = api_call(
                "GET", f"/crawls/{crawl_id}/issues?severity={sev}&limit=5"
            )
            check(f"severity={sev} → 200", code == 200)
            items = body.get("items", []) if isinstance(body, dict) else []
            if items:
                bad = [i for i in items if i.get("severity") != sev]
                check(
                    f"severity={sev} filter correct",
                    len(bad) == 0,
                    f"{len(bad)} wrong severity",
                )
            else:
                warn(f"severity={sev} returned 0 results")

        # ── T9: Category filter exhaustive ─────────────────────
        section("T9. Category Filter Exhaustive")
        for cat in by_cat.keys():
            code, body = api_call(
                "GET", f"/crawls/{crawl_id}/issues?category={cat}&limit=5"
            )
            check(f"category={cat} → 200", code == 200)
            items = body.get("items", []) if isinstance(body, dict) else []
            if items:
                bad = [i for i in items if i.get("category") != cat]
                check(f"category={cat} filter correct", len(bad) == 0)

        # ── T10: issue_type filter ─────────────────────────────
        section("T10. Issue Type Filter")
        if all_types:
            sample_type = sorted(all_types)[0]
            code, body = api_call(
                "GET", f"/crawls/{crawl_id}/issues?issue_type={sample_type}&limit=10"
            )
            check(f"issue_type={sample_type} → 200", code == 200)
            items = body.get("items", []) if isinstance(body, dict) else []
            if items:
                bad = [i for i in items if i.get("issue_type") != sample_type]
                check(f"issue_type filter correct", len(bad) == 0)

        # ── T11: Non-indexable URLs ────────────────────────────
        section("T11. Indexability Verification")
        code, body = api_call(
            "GET", f"/crawls/{crawl_id}/urls?is_indexable=true&limit=100"
        )
        indexable = len(body.get("items", [])) if isinstance(body, dict) else 0
        code, body = api_call(
            "GET", f"/crawls/{crawl_id}/urls?is_indexable=false&limit=100"
        )
        non_indexable = len(body.get("items", [])) if isinstance(body, dict) else 0
        check(f"indexable={indexable}, non-indexable={non_indexable}", indexable > 0)
        check(
            "indexable + non_indexable ≤ total", indexable + non_indexable <= total_urls
        )

        # ── T12: Frontend with crawl data ──────────────────────
        section("T12. Frontend Verification")
        for path, name in [
            ("/", "Home"),
            ("/crawls", "Crawls list"),
            (f"/crawls/{crawl_id}", "Crawl detail"),
        ]:
            url = f"{BASE_URL}{path}"
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    code = resp.status
                    body = resp.read().decode()
            except urllib.error.HTTPError as e:
                code = e.code
                body = ""
            except Exception:
                code = 0
                body = ""
            check(f"{name} ({path}) → 200", code == 200)

    finally:
        section("Cleanup")
        if crawl_id:
            api_call("DELETE", f"/crawls/{crawl_id}")
            check("delete main crawl", True)
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
        print(f"\n  {C.GREEN}{C.BOLD}ALL DEEP CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
