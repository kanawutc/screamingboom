#!/usr/bin/env python3
"""
API Edge Cases Test
===================
Tests every API endpoint with invalid, boundary, and edge-case inputs.
Ensures proper error codes (422, 404, 409) and no server crashes.

Usage:
    python test_api_edge_cases.py
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
    msg = f"  {C.YELLOW}⚠{C.RESET} {name}"
    if detail:
        msg += f"  {C.DIM}({detail}){C.RESET}"
    print(msg)


def section(title):
    print(f"\n{C.BOLD}{C.CYAN}▸ {title}{C.RESET}")


def wait_for_crawl(crawl_id, max_wait=180):
    start = time.time()
    while time.time() - start < max_wait:
        time.sleep(2)
        code, body = api_call("GET", f"/crawls/{crawl_id}")
        if code == 200 and isinstance(body, dict):
            status = body.get("status", "")
            if status in ("completed", "failed", "cancelled"):
                return status
    return "timeout"


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — API Edge Cases Test{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    fake_uuid = str(uuid.uuid4())
    project_id = None
    crawl_id = None

    try:
        # ── Setup: create a real project + crawl for later tests ───
        section("Setup")
        code, body = api_call(
            "POST", "/projects", {"name": "Edge Case Test", "domain": CRAWL_TARGET}
        )
        check("setup: create project", code == 201)
        project_id = body["id"] if isinstance(body, dict) else None

        if project_id:
            code, body = api_call(
                "POST",
                f"/projects/{project_id}/crawls",
                {
                    "start_url": CRAWL_TARGET,
                    "config": {"max_urls": 10, "max_depth": 1, "rate_limit_rps": 10.0},
                },
            )
            check("setup: start crawl", code == 201)
            crawl_id = body["id"] if isinstance(body, dict) else None

        if crawl_id:
            print(
                f"  {C.DIM}Waiting for crawl to complete...{C.RESET}",
                end="",
                flush=True,
            )
            status = wait_for_crawl(crawl_id, max_wait=180)
            print()
            check("setup: crawl completed", status == "completed", f"got: {status}")

        # ── 1. Project validation errors ──────────────────────────
        section("1. Project Validation Errors")

        code, _ = api_call("POST", "/projects", {})
        check("POST /projects empty body → 422", code == 422, f"code={code}")

        code, _ = api_call("POST", "/projects", {"name": ""})
        check("POST /projects empty name → 422", code == 422, f"code={code}")

        code, _ = api_call("POST", "/projects", {"domain": CRAWL_TARGET})
        check("POST /projects missing name → 422", code == 422, f"code={code}")

        code, _ = api_call("POST", "/projects", {"name": "Test"})
        check("POST /projects missing domain → 422", code == 422, f"code={code}")

        # ── 2. Project not found ──────────────────────────────────
        section("2. Project Not Found")

        code, _ = api_call("GET", f"/projects/{fake_uuid}")
        check("GET /projects/{nonexistent} → 404", code == 404, f"code={code}")

        code, _ = api_call("PUT", f"/projects/{fake_uuid}", {"name": "X"})
        check("PUT /projects/{nonexistent} → 404", code == 404, f"code={code}")

        code, _ = api_call("DELETE", f"/projects/{fake_uuid}")
        check("DELETE /projects/{nonexistent} → 404", code == 404, f"code={code}")

        code, _ = api_call("GET", "/projects/not-a-uuid")
        check("GET /projects/not-a-uuid → 422", code == 422, f"code={code}")

        # ── 3. Crawl creation validation ──────────────────────────
        section("3. Crawl Creation Validation")

        if project_id:
            code, _ = api_call("POST", f"/projects/{project_id}/crawls", {})
            check("POST crawl empty body → 422", code == 422, f"code={code}")

            code, resp = api_call(
                "POST", f"/projects/{project_id}/crawls", {"start_url": ""}
            )
            check(
                "POST crawl empty start_url → 201 or 422",
                code in (201, 422),
                f"code={code}",
            )
            if code == 201 and isinstance(resp, dict) and resp.get("id"):
                api_call("DELETE", f"/crawls/{resp['id']}")

            code, _ = api_call(
                "POST",
                f"/projects/{project_id}/crawls",
                {"start_url": CRAWL_TARGET, "config": {"max_urls": -1}},
            )
            check("POST crawl max_urls=-1 → 422", code == 422, f"code={code}")

            # max_urls=0 is now valid (means "unlimited")
            code, resp = api_call(
                "POST",
                f"/projects/{project_id}/crawls",
                {"start_url": CRAWL_TARGET, "config": {"max_urls": 0}},
            )
            check("POST crawl max_urls=0 → 201 (unlimited)", code == 201, f"code={code}")
            # Clean up the unlimited crawl immediately
            if code == 201 and isinstance(resp, dict) and resp.get("id"):
                api_call("POST", f"/crawls/{resp['id']}/stop")
                api_call("DELETE", f"/crawls/{resp['id']}")

        code, _ = api_call(
            "POST", f"/projects/{fake_uuid}/crawls", {"start_url": CRAWL_TARGET}
        )
        check("POST crawl on nonexistent project → 404", code == 404, f"code={code}")

        # ── 4. Crawl not found ────────────────────────────────────
        section("4. Crawl Not Found")

        code, _ = api_call("GET", f"/crawls/{fake_uuid}")
        check("GET /crawls/{nonexistent} → 404", code == 404, f"code={code}")

        code, _ = api_call("DELETE", f"/crawls/{fake_uuid}")
        check("DELETE /crawls/{nonexistent} → 404", code == 404, f"code={code}")

        # ── 5. Crawl lifecycle conflicts (409s) ──────────────────
        section("5. Crawl Lifecycle Conflicts")

        if crawl_id:
            # Crawl is completed — pause/resume/stop should 409
            code, _ = api_call("POST", f"/crawls/{crawl_id}/pause")
            check("pause completed crawl → 409", code == 409, f"code={code}")

            code, _ = api_call("POST", f"/crawls/{crawl_id}/resume")
            check("resume completed crawl → 409", code == 409, f"code={code}")

            code, _ = api_call("POST", f"/crawls/{crawl_id}/stop")
            check("stop completed crawl → 409", code == 409, f"code={code}")

        # pause/resume/stop nonexistent crawl
        code, _ = api_call("POST", f"/crawls/{fake_uuid}/pause")
        check(
            "pause nonexistent crawl → 404 or 409", code in (404, 409), f"code={code}"
        )

        code, _ = api_call("POST", f"/crawls/{fake_uuid}/resume")
        check(
            "resume nonexistent crawl → 404 or 409", code in (404, 409), f"code={code}"
        )

        code, _ = api_call("POST", f"/crawls/{fake_uuid}/stop")
        check("stop nonexistent crawl → 404 or 409", code in (404, 409), f"code={code}")

        # ── 6. Pagination boundaries ──────────────────────────────
        section("6. Pagination Boundaries")

        code, _ = api_call("GET", "/projects?limit=0")
        check("limit=0 → 422", code == 422, f"code={code}")

        code, _ = api_call("GET", "/projects?limit=501")
        check("limit=501 (over max) → 422", code == 422, f"code={code}")

        code, body = api_call("GET", "/projects?limit=1")
        check(
            "limit=1 → returns ≤1 item", code == 200 and len(body.get("items", [])) <= 1
        )

        code, body = api_call("GET", "/projects?cursor=zzzz_invalid")
        # Should either return empty or 422 — not crash
        check("invalid cursor → no crash", code in (200, 422), f"code={code}")

        # ── 7. Issues/URLs filter edge cases ─────────────────────
        section("7. Filter Edge Cases")

        if crawl_id:
            code, body = api_call(
                "GET", f"/crawls/{crawl_id}/issues?severity=nonexistent"
            )
            check(
                "severity=nonexistent → 200 empty",
                code == 200
                and isinstance(body, dict)
                and len(body.get("items", [])) == 0,
                f"code={code}, items={len(body.get('items', [])) if isinstance(body, dict) else '?'}",
            )

            code, body = api_call(
                "GET", f"/crawls/{crawl_id}/issues?category=nonexistent"
            )
            check(
                "category=nonexistent → 200 empty",
                code == 200
                and isinstance(body, dict)
                and len(body.get("items", [])) == 0,
            )

            code, body = api_call("GET", f"/crawls/{crawl_id}/urls?status_code=999")
            check(
                "status_code=999 → 200 empty",
                code == 200
                and isinstance(body, dict)
                and len(body.get("items", [])) == 0,
            )

            # Logical contradiction: indexable + 404
            code, body = api_call(
                "GET", f"/crawls/{crawl_id}/urls?is_indexable=true&status_code=404"
            )
            check(
                "is_indexable=true + status_code=404 → 200 (empty likely)",
                code == 200,
                f"code={code}",
            )

            # Issues for nonexistent crawl
            code, _ = api_call("GET", f"/crawls/{fake_uuid}/issues?limit=5")
            check(
                "issues on nonexistent crawl → 200 empty or 404",
                code in (200, 404),
                f"code={code}",
            )

            code, _ = api_call("GET", f"/crawls/{fake_uuid}/issues/summary")
            check(
                "summary on nonexistent crawl → 200 or 404",
                code in (200, 404),
                f"code={code}",
            )

        # ── 8. Double-delete ──────────────────────────────────────
        section("8. Double-Delete")

        # Create and delete a throwaway project
        code, body = api_call(
            "POST", "/projects", {"name": "Throwaway", "domain": "https://example.com"}
        )
        if code == 201 and isinstance(body, dict):
            tmp_id = body["id"]
            code1, _ = api_call("DELETE", f"/projects/{tmp_id}")
            check("first delete project → 204", code1 == 204)
            code2, _ = api_call("DELETE", f"/projects/{tmp_id}")
            check("second delete project → 404", code2 == 404, f"code={code2}")

        # ── 9. Crawl with unreachable URL ─────────────────────────
        section("9. Unreachable URL Crawl")

        if project_id:
            code, body = api_call(
                "POST",
                f"/projects/{project_id}/crawls",
                {
                    "start_url": "https://thisdomaindoesnotexist99999.com/",
                    "config": {"max_urls": 5, "max_depth": 1, "rate_limit_rps": 5.0},
                },
            )
            if code == 201 and isinstance(body, dict):
                bad_crawl_id = body["id"]
                check("start crawl with unreachable URL → 201", True)
                status = wait_for_crawl(bad_crawl_id, max_wait=90)
                check(
                    "unreachable crawl finishes gracefully",
                    status in ("completed", "failed"),
                    f"status={status}",
                )
                # Clean up
                api_call("DELETE", f"/crawls/{bad_crawl_id}")
            else:
                check(
                    "start crawl with unreachable URL → 201",
                    code == 201,
                    f"code={code}",
                )

    finally:
        # ── Cleanup ───────────────────────────────────────────────
        section("Cleanup")
        if crawl_id:
            code, _ = api_call("DELETE", f"/crawls/{crawl_id}")
            check("delete test crawl", code == 204, f"code={code}")
        if project_id:
            code, _ = api_call("DELETE", f"/projects/{project_id}")
            check("delete test project", code == 204, f"code={code}")

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"  {C.GREEN}✓ {passed} passed{C.RESET}  ", end="")
    if warnings:
        print(f"{C.YELLOW}⚠ {warnings} warnings{C.RESET}  ", end="")
    if failed:
        print(f"{C.RED}✗ {failed} failed{C.RESET}  ", end="")
    print(f"{C.DIM}({passed + failed} checks){C.RESET}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}ALL EDGE CASE CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
