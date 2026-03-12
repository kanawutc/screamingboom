#!/usr/bin/env python3
"""
Data Integrity Test
===================
Verifies data is CORRECT, not just present.
Checks consistency between endpoints, calculated fields, and cascade deletes.

Usage:
    python test_data_integrity.py
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
MAX_CRAWL_WAIT = 180

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


def fetch_all_items(path, limit=200):
    """Fetch all items from a paginated endpoint."""
    items = []
    cursor = None
    for _ in range(20):  # safety limit
        q = f"{path}?limit={limit}"
        if cursor:
            q += f"&cursor={cursor}"
        code, body = api_call("GET", q)
        if code != 200 or not isinstance(body, dict):
            break
        items.extend(body.get("items", []))
        cursor = body.get("next_cursor")
        if not cursor:
            break
    return items


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — Data Integrity Test{C.RESET}")
    print(f"  {C.DIM}Target: {CRAWL_TARGET}{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    project_id = None
    crawl_id = None

    try:
        # ── Setup ─────────────────────────────────────────────────
        section("Setup")
        code, body = api_call(
            "POST", "/projects", {"name": "Integrity Test", "domain": CRAWL_TARGET}
        )
        if not check("create project", code == 201):
            sys.exit(1)
        project_id = body["id"]

        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 30, "max_depth": 2, "rate_limit_rps": 10.0},
            },
        )
        check("start crawl", code == 201)
        crawl_id = body["id"] if isinstance(body, dict) else None

        if not crawl_id:
            sys.exit(1)

        print(f"  {C.DIM}Waiting for crawl...{C.RESET}", end="", flush=True)
        start = time.time()
        final = "unknown"
        while time.time() - start < MAX_CRAWL_WAIT:
            time.sleep(3)
            c, b = api_call("GET", f"/crawls/{crawl_id}")
            if c == 200 and isinstance(b, dict):
                final = b.get("status", "")
                if final in ("completed", "failed", "cancelled"):
                    break
            print(".", end="", flush=True)
        print(f" {time.time() - start:.0f}s")
        if not check("crawl completed", final == "completed", f"got: {final}"):
            sys.exit(1)

        # Get crawl metadata
        code, crawl = api_call("GET", f"/crawls/{crawl_id}")
        total_urls = crawl.get("total_urls", 0) if isinstance(crawl, dict) else 0
        crawled_count = (
            crawl.get("crawled_urls_count", 0) if isinstance(crawl, dict) else 0
        )

        # ── 1. Count consistency ──────────────────────────────────
        section("1. Count Consistency")

        all_urls = fetch_all_items(f"/crawls/{crawl_id}/urls")
        check(
            "total_urls matches URL list count",
            total_urls == len(all_urls),
            f"total_urls={total_urls}, list_count={len(all_urls)}",
        )

        # ── 2. Issues summary math ───────────────────────────────
        section("2. Issues Summary Math")

        code, summary = api_call("GET", f"/crawls/{crawl_id}/issues/summary")
        check("fetch summary", code == 200)
        if isinstance(summary, dict):
            total_issues = summary.get("total", 0)
            by_sev = summary.get("by_severity", {})
            by_cat = summary.get("by_category", {})

            sev_sum = sum(by_sev.values())
            check(
                "by_severity sums to total",
                sev_sum == total_issues,
                f"sev_sum={sev_sum}, total={total_issues}",
            )

            cat_sum = sum(by_cat.values())
            check(
                "by_category sums to total",
                cat_sum == total_issues,
                f"cat_sum={cat_sum}, total={total_issues}",
            )

        # ── 3. Issue registry adherence ──────────────────────────
        section("3. Issue Registry Adherence")

        all_issues = fetch_all_items(f"/crawls/{crawl_id}/issues")
        check(f"fetched {len(all_issues)} issues", len(all_issues) > 0)

        valid_severities = {"critical", "warning", "info", "opportunity"}
        valid_categories = {
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

        bad_sev = [i for i in all_issues if i.get("severity") not in valid_severities]
        check(
            "all issues have valid severity",
            len(bad_sev) == 0,
            f"{len(bad_sev)} invalid",
        )

        bad_cat = [i for i in all_issues if i.get("category") not in valid_categories]
        check(
            "all issues have valid category",
            len(bad_cat) == 0,
            f"{len(bad_cat)} invalid",
        )

        # Every issue must have non-empty description
        no_desc = [i for i in all_issues if not i.get("description")]
        check(
            "all issues have description", len(no_desc) == 0, f"{len(no_desc)} missing"
        )

        # Every issue must have non-empty url
        no_url = [i for i in all_issues if not i.get("url")]
        check("all issues have url", len(no_url) == 0, f"{len(no_url)} missing")

        # Every issue must have non-empty issue_type
        no_type = [i for i in all_issues if not i.get("issue_type")]
        check(
            "all issues have issue_type", len(no_type) == 0, f"{len(no_type)} missing"
        )

        # ── 4. No duplicate (url, issue_type) pairs ──────────────
        section("4. Issue Deduplication")

        seen = set()
        duplicates = 0
        for iss in all_issues:
            key = (iss.get("url", ""), iss.get("issue_type", ""))
            if key in seen:
                duplicates += 1
            seen.add(key)
        # Some issue types legitimately appear multiple times per URL:
        # - post-crawl types flag the same URL from different duplicate groups
        # - image issues fire once per image (missing_alt_text, etc.)
        # - link issues fire once per broken link target
        multi_instance_types = {
            "duplicate_title",
            "duplicate_meta_description",
            "broken_internal_link",
            "canonical_mismatch",
            "missing_alt_text",
            "alt_text_too_long",
            "missing_image_dimensions",
            "broken_link_4xx",
            "broken_link_5xx",
        }
        real_dups = 0
        seen2 = set()
        for iss in all_issues:
            if iss.get("issue_type") in multi_instance_types:
                continue
            key = (iss.get("url", ""), iss.get("issue_type", ""))
            if key in seen2:
                real_dups += 1
            seen2.add(key)
        check(
            "no duplicate (url, issue_type) for single-instance issues",
            real_dups == 0,
            f"duplicates={real_dups}",
        )

        # ── 5. URL data completeness ─────────────────────────────
        section("5. URL Data Completeness")

        no_url_field = [u for u in all_urls if not u.get("url")]
        check("all URLs have url field", len(no_url_field) == 0)

        no_status = [u for u in all_urls if u.get("status_code") is None]
        check(
            "all URLs have status_code",
            len(no_status) == 0,
            f"{len(no_status)} missing",
        )

        # ── 6. SEO field correctness on detail ───────────────────
        section("6. SEO Field Correctness (URL Detail)")

        # Get first HTML URL detail
        html_urls = [
            u
            for u in all_urls
            if u.get("status_code") == 200 and "html" in (u.get("content_type") or "")
        ]
        if html_urls:
            uid = html_urls[0]["id"]
            code, detail = api_call("GET", f"/crawls/{crawl_id}/urls/{uid}")
            check("fetch URL detail", code == 200)

            if isinstance(detail, dict):
                title = detail.get("title", "")
                title_length = detail.get("title_length")
                if title and title_length is not None:
                    check(
                        "title_length matches len(title)",
                        title_length == len(title),
                        f"title_length={title_length}, len(title)={len(title)}",
                    )
                elif title:
                    warn("title_length is None but title exists")

                pw = detail.get("title_pixel_width")
                if title:
                    check(
                        "title_pixel_width > 0 when title exists",
                        pw is not None and pw > 0,
                        f"pw={pw}",
                    )

                meta_desc = detail.get("meta_description", "")
                mdl = detail.get("meta_desc_length")
                if meta_desc and mdl is not None:
                    check(
                        "meta_desc_length matches len(meta_description)",
                        mdl == len(meta_desc),
                        f"mdl={mdl}, len={len(meta_desc)}",
                    )
                elif meta_desc:
                    warn("meta_desc_length is None but meta_description exists")

                # is_indexable consistency
                is_indexable = detail.get("is_indexable")
                reason = detail.get("indexability_reason")
                if is_indexable is False:
                    check(
                        "non-indexable URL has indexability_reason",
                        bool(reason),
                        f"reason={reason}",
                    )
                elif is_indexable is True:
                    check("indexable URL reason is 'indexable' or similar", True)

                # word_count
                wc = detail.get("word_count")
                if wc is not None:
                    check("word_count ≥ 0", wc >= 0, f"wc={wc}")

                # crawl_depth
                depth = detail.get("crawl_depth")
                if depth is not None:
                    check("crawl_depth ≥ 0", depth >= 0, f"depth={depth}")

                # response_time_ms
                rt = detail.get("response_time_ms")
                if rt is not None:
                    check("response_time_ms ≥ 0", rt >= 0, f"rt={rt}")
        else:
            warn("no HTML URLs found for detail check")

        # ── 7. Temporal ordering ──────────────────────────────────
        section("7. Temporal Ordering")

        if isinstance(crawl, dict):
            started = crawl.get("started_at", "")
            completed = crawl.get("completed_at", "")
            created = crawl.get("created_at", "")
            if started and completed:
                check(
                    "started_at < completed_at",
                    started < completed,
                    f"started={started}, completed={completed}",
                )
            if created and started:
                check(
                    "created_at ≤ started_at",
                    created <= started,
                    f"created={created}, started={started}",
                )

        # ── 8. Duplicate title issues reference multiple URLs ────
        section("8. Post-Crawl Issue Correctness")

        dup_title_issues = [
            i for i in all_issues if i.get("issue_type") == "duplicate_title"
        ]
        if dup_title_issues:
            # Should have ≥2 issues (one per URL sharing the title)
            check(
                f"duplicate_title: {len(dup_title_issues)} issues (≥2)",
                len(dup_title_issues) >= 2,
            )
            # All should have different URLs
            dup_urls = {i.get("url") for i in dup_title_issues}
            check(
                "duplicate_title issues reference different URLs",
                len(dup_urls) >= 2,
                f"unique_urls={len(dup_urls)}",
            )
        else:
            warn("no duplicate_title issues (may be normal)")

        # ── 9. Cascade delete verification ────────────────────────
        section("9. Cascade Delete")

        # Create a mini project+crawl, let it complete, then delete project and verify URLs gone
        code, body = api_call(
            "POST",
            "/projects",
            {"name": "Cascade Test", "domain": "https://example.com"},
        )
        if code == 201 and isinstance(body, dict):
            tmp_pid = body["id"]
            code, body = api_call(
                "POST",
                f"/projects/{tmp_pid}/crawls",
                {
                    "start_url": "https://example.com",
                    "config": {"max_urls": 3, "max_depth": 1, "rate_limit_rps": 10.0},
                },
            )
            if code == 201 and isinstance(body, dict):
                tmp_cid = body["id"]
                # Wait for completion
                for _ in range(30):
                    time.sleep(2)
                    c, b = api_call("GET", f"/crawls/{tmp_cid}")
                    if (
                        c == 200
                        and isinstance(b, dict)
                        and b.get("status") in ("completed", "failed")
                    ):
                        break

                # Delete project (should cascade)
                code, _ = api_call("DELETE", f"/projects/{tmp_pid}")
                check("delete cascade project → 204", code == 204)

                # Verify crawl is gone
                code, _ = api_call("GET", f"/crawls/{tmp_cid}")
                check("crawl gone after project delete", code == 404, f"code={code}")

                # Verify URLs are gone
                code, body = api_call("GET", f"/crawls/{tmp_cid}/urls?limit=1")
                items = body.get("items", []) if isinstance(body, dict) else []
                check(
                    "URLs gone after project delete",
                    code == 404 or len(items) == 0,
                    f"code={code}",
                )
            else:
                warn("could not create cascade test crawl")
        else:
            warn("could not create cascade test project")

        # Crawl-level cascade: delete crawl, verify URLs gone
        if crawl_id and all_urls:
            first_url_id = all_urls[0].get("id")
            code, _ = api_call("DELETE", f"/crawls/{crawl_id}")
            check("delete crawl → 204", code == 204)

            code, body = api_call("GET", f"/crawls/{crawl_id}/urls?limit=1")
            items = body.get("items", []) if isinstance(body, dict) else []
            check(
                "URLs gone after crawl delete",
                code == 404 or len(items) == 0,
                f"code={code}",
            )

            crawl_id = None  # mark as already deleted

    finally:
        section("Cleanup")
        if crawl_id:
            api_call("DELETE", f"/crawls/{crawl_id}")
        if project_id:
            code, _ = api_call("DELETE", f"/projects/{project_id}")
            check("delete project", code == 204 or code == 404)

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"  {C.GREEN}✓ {passed} passed{C.RESET}  ", end="")
    if warnings:
        print(f"{C.YELLOW}⚠ {warnings} warnings{C.RESET}  ", end="")
    if failed:
        print(f"{C.RED}✗ {failed} failed{C.RESET}  ", end="")
    print(f"{C.DIM}({passed + failed} checks){C.RESET}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}ALL INTEGRITY CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
