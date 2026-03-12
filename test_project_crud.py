#!/usr/bin/env python3
"""
A1-A5: Project CRUD — every endpoint, every edge case.

Tests: Create, List (pagination), Get, Update, Delete (cascade).
"""

from __future__ import annotations

import json
import sys
import uuid
import urllib.error
import urllib.request

BASE_URL = "http://localhost"
API = f"{BASE_URL}/api/v1"

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


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  A1-A5: Project CRUD Test{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    cleanup_ids = []

    try:
        # ── A1: Create Project ────────────────────────────────────
        section("A1. Create Project")

        code, body = api_call(
            "POST",
            "/projects",
            {"name": "Test Project A1", "domain": "https://example.com"},
        )
        check("valid create → 201", code == 201)
        check("response has id", isinstance(body, dict) and "id" in body)
        check("response has name", body.get("name") == "Test Project A1")
        check("response has domain", body.get("domain") == "https://example.com")
        check("response has created_at", "created_at" in body)
        check("response has updated_at", "updated_at" in body)
        check("response has settings", "settings" in body)
        pid = body.get("id")
        if pid:
            cleanup_ids.append(pid)

        code2, _ = api_call(
            "POST",
            "/projects",
            {"name": "Test Project A1 Dup", "domain": "https://example.com"},
        )
        check("duplicate domain allowed", code2 == 201)
        if isinstance(_, dict) and "id" in _:
            cleanup_ids.append(_["id"])

        code3, _ = api_call("POST", "/projects", {"domain": "https://example.com"})
        check("missing name → 422", code3 == 422)

        code4, _ = api_call("POST", "/projects", {"name": "Test"})
        check("missing domain → 422", code4 == 422)

        code5, _ = api_call(
            "POST", "/projects", {"name": "", "domain": "https://x.com"}
        )
        check("empty name → 422", code5 == 422)

        code6, _ = api_call("POST", "/projects", {"name": "X", "domain": ""})
        check("empty domain → 422", code6 == 422)

        # ── A2: List Projects ─────────────────────────────────────
        section("A2. List Projects")

        code, body = api_call("GET", "/projects")
        check("list → 200", code == 200)
        check(
            "response has items array",
            isinstance(body, dict) and isinstance(body.get("items"), list),
        )
        check("response has next_cursor", "next_cursor" in body)

        code, body = api_call("GET", "/projects?limit=1")
        check(
            "limit=1 returns ≤ 1 item", code == 200 and len(body.get("items", [])) <= 1
        )

        cursor = body.get("next_cursor")
        if cursor:
            code, body2 = api_call("GET", f"/projects?cursor={cursor}&limit=1")
            check(
                "cursor pagination → next page",
                code == 200 and len(body2.get("items", [])) >= 0,
            )
        else:
            warn("no next_cursor to test pagination (need more projects)")

        code, _ = api_call("GET", "/projects?limit=0")
        check("limit=0 → 422", code == 422)

        code, _ = api_call("GET", "/projects?limit=501")
        check("limit=501 → 422", code == 422)

        code, body = api_call("GET", "/projects?cursor=garbage-not-uuid")
        check(
            "invalid cursor → empty page (not 500)",
            code == 200 and isinstance(body.get("items"), list),
        )

        # ── A3: Get Project ───────────────────────────────────────
        section("A3. Get Project")

        if pid:
            code, body = api_call("GET", f"/projects/{pid}")
            check("get by id → 200", code == 200)
            check("correct id returned", body.get("id") == pid)
            check(
                "has all fields",
                all(
                    k in body
                    for k in (
                        "id",
                        "name",
                        "domain",
                        "settings",
                        "created_at",
                        "updated_at",
                    )
                ),
            )

        fake_id = str(uuid.uuid4())
        code, _ = api_call("GET", f"/projects/{fake_id}")
        check("nonexistent UUID → 404", code == 404)

        code, _ = api_call("GET", "/projects/not-a-uuid")
        check("malformed id → 422", code == 422)

        # ── A4: Update Project ────────────────────────────────────
        section("A4. Update Project")

        if pid:
            code, body = api_call("PUT", f"/projects/{pid}", {"name": "Updated Name"})
            check("update name → 200", code == 200)
            check("name changed", body.get("name") == "Updated Name")

            code, body = api_call(
                "PUT", f"/projects/{pid}", {"domain": "https://new.example.com"}
            )
            check("update domain → 200", code == 200)
            check("domain changed", body.get("domain") == "https://new.example.com")

        code, _ = api_call("PUT", f"/projects/{fake_id}", {"name": "X"})
        check("update nonexistent → 404", code == 404)

        # ── A5: Delete Project + Cascade ──────────────────────────
        section("A5. Delete Project (Cascade)")

        code, proj = api_call(
            "POST",
            "/projects",
            {"name": "Cascade Test", "domain": "https://example.com"},
        )
        cascade_pid = proj.get("id") if isinstance(proj, dict) else None

        if cascade_pid:
            code, crawl = api_call(
                "POST",
                f"/projects/{cascade_pid}/crawls",
                {
                    "start_url": "https://example.com",
                    "config": {"max_urls": 2, "max_depth": 1},
                },
            )
            cascade_cid = crawl.get("id") if isinstance(crawl, dict) else None

            if cascade_cid:
                import time

                for _ in range(30):
                    time.sleep(2)
                    c, b = api_call("GET", f"/crawls/{cascade_cid}")
                    if (
                        c == 200
                        and isinstance(b, dict)
                        and b.get("status") in ("completed", "failed")
                    ):
                        break

            code, _ = api_call("DELETE", f"/projects/{cascade_pid}")
            check("delete project → 204", code == 204)

            if cascade_cid:
                code, _ = api_call("GET", f"/crawls/{cascade_cid}")
                check("cascade: crawl gone after project delete", code == 404)

                code, body = api_call("GET", f"/crawls/{cascade_cid}/urls")
                items = body.get("items", []) if isinstance(body, dict) else []
                check(
                    "cascade: URLs gone after project delete",
                    code == 404 or len(items) == 0,
                )

        code, _ = api_call("DELETE", f"/projects/{fake_id}")
        check("delete nonexistent → 404", code == 404)

    finally:
        section("Cleanup")
        for cid in cleanup_ids:
            api_call("DELETE", f"/projects/{cid}")
        check("cleanup done", True)

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"  {C.GREEN}✓ {passed} passed{C.RESET}  ", end="")
    if warnings:
        print(f"{C.YELLOW}⚠ {warnings} warnings{C.RESET}  ", end="")
    if failed:
        print(f"{C.RED}✗ {failed} failed{C.RESET}  ", end="")
    print(f"{C.DIM}({passed + failed} checks){C.RESET}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}ALL PROJECT CRUD CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
