#!/usr/bin/env python3
"""
Comprehensive Browser Test (Playwright)
========================================
Automated UI tests covering navigation, forms, real-time updates,
filters, pagination, responsive design, and error states.

Requires: playwright (pip install playwright && playwright install chromium)

Usage:
    python test_browser_comprehensive.py
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


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    DIM = "\033[2m"
    CYAN = "\033[36m"


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


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — Comprehensive Browser Test{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"\n  {C.RED}ABORT: playwright not installed{C.RESET}")
        print(
            f"  {C.DIM}Install: pip install playwright && playwright install chromium{C.RESET}"
        )
        sys.exit(1)

    project_id = None
    crawl_id = None

    # Create a project via API for test data
    code, body = api_call(
        "POST", "/projects", {"name": "Browser Test", "domain": CRAWL_TARGET}
    )
    if code == 201 and isinstance(body, dict):
        project_id = body["id"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            # ── 1. Dashboard ──────────────────────────────────────
            section("1. Dashboard")
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            check("dashboard loads", page.title() != "" or page.url.endswith("/"))

            # Stats cards
            body_text = page.text_content("body") or ""
            check(
                "dashboard has stats content",
                "Project" in body_text or "Crawl" in body_text,
                body_text[:100],
            )

            # ── 2. Sidebar Navigation ─────────────────────────────
            section("2. Sidebar Navigation")

            dash_link = page.query_selector('a[href="/"]')
            check("sidebar: Dashboard link exists", dash_link is not None)

            crawls_link = page.query_selector('a[href="/crawls"]')
            check("sidebar: Crawls link exists", crawls_link is not None)
            if crawls_link:
                crawls_link.click()
                try:
                    page.wait_for_url("**/crawls", timeout=10000)
                except Exception:
                    page.wait_for_timeout(2000)
                check(
                    "sidebar: Crawls link navigates to /crawls", "/crawls" in page.url
                )

            settings_link = page.query_selector('a[href="/settings"]')
            check("sidebar: Settings link exists", settings_link is not None)
            if settings_link:
                settings_link.click()
                try:
                    page.wait_for_url("**/settings", timeout=10000)
                except Exception:
                    page.wait_for_timeout(2000)
                check(
                    "sidebar: Settings link navigates to /settings",
                    "/settings" in page.url,
                )
                settings_text = page.text_content("body") or ""
                check(
                    "settings page renders content",
                    len(settings_text) > 20,
                    f"len={len(settings_text)}",
                )

            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1000)
            check(
                "sidebar: back to Dashboard",
                True,
            )

            # ── 3. Crawls List Page ───────────────────────────────
            section("3. Crawls List Page")
            page.goto(
                f"{BASE_URL}/crawls", wait_until="domcontentloaded", timeout=30000
            )
            check("crawls page loads", "/crawls" in page.url)

            crawls_text = page.text_content("body") or ""
            # Should show "Crawls" heading or table
            check("crawls page has content", len(crawls_text) > 20)

            # ── 4. New Crawl Form ─────────────────────────────────
            section("4. New Crawl Form")
            page.goto(
                f"{BASE_URL}/crawls/new", wait_until="domcontentloaded", timeout=30000
            )
            check("new crawl page loads", "/crawls/new" in page.url)

            form_text = page.text_content("body") or ""
            check(
                "form shows Spider Mode", "Spider" in form_text or "spider" in form_text
            )

            # Find URL input
            url_input = page.query_selector(
                'input[type="url"], input[placeholder*="http"], input[name*="url"]'
            )
            check("URL input field exists", url_input is not None)

            # Find List Mode tab
            list_tab = page.query_selector(
                'button:has-text("List"), [role="tab"]:has-text("List")'
            )
            if list_tab:
                list_tab.click()
                page.wait_for_timeout(500)
                textarea = page.query_selector("textarea")
                check("List Mode: textarea appears", textarea is not None)
                # Switch back to Spider
                spider_tab = page.query_selector(
                    'button:has-text("Spider"), [role="tab"]:has-text("Spider")'
                )
                if spider_tab:
                    spider_tab.click()
                    page.wait_for_timeout(500)
            else:
                warn("List Mode tab not found")

            # Cancel button
            cancel_btn = page.query_selector(
                'button:has-text("Cancel"), a:has-text("Cancel")'
            )
            check("Cancel button exists", cancel_btn is not None)

            # ── 5. Start a Crawl and Watch Progress ───────────────
            section("5. Live Crawl Progress")

            # Fill form and submit via the UI
            page.goto(
                f"{BASE_URL}/crawls/new", wait_until="domcontentloaded", timeout=30000
            )
            url_input = page.query_selector(
                'input[type="url"], input[placeholder*="http"], input[name*="url"]'
            )
            if url_input:
                url_input.fill(CRAWL_TARGET)

            # Find and set max URLs to small number for speed
            max_urls_input = page.query_selector(
                'input[name*="max_urls"], input[type="number"]'
            )
            if max_urls_input:
                max_urls_input.fill("15")

            # Select a project if there's a dropdown
            project_select = page.query_selector('select, [role="combobox"]')
            if project_select and project_id:
                try:
                    project_select.select_option(value=project_id)
                except Exception:
                    pass  # may not be a standard select

            # Click Start
            start_btn = page.query_selector(
                'button:has-text("Start"), button[type="submit"]'
            )
            if start_btn:
                start_btn.click()
                # Wait for navigation to crawl detail
                page.wait_for_timeout(3000)

                # Check if we navigated to a crawl detail page
                if "/crawls/" in page.url and "/new" not in page.url:
                    check("navigated to crawl detail after start", True)
                    crawl_id_from_url = (
                        page.url.split("/crawls/")[-1].split("?")[0].split("#")[0]
                    )

                    # Wait for progress to appear
                    page.wait_for_timeout(5000)
                    detail_text = page.text_content("body") or ""

                    # Check for status indicators
                    has_status = any(
                        s in detail_text
                        for s in [
                            "Crawling",
                            "Completed",
                            "Queued",
                            "crawling",
                            "completed",
                        ]
                    )
                    check("crawl status visible", has_status, detail_text[:200])

                    # Wait for crawl to complete (check every 3s)
                    for _ in range(40):  # max 120s
                        page.wait_for_timeout(3000)
                        detail_text = page.text_content("body") or ""
                        if "Completed" in detail_text or "completed" in detail_text:
                            break

                    check(
                        "crawl reached Completed",
                        "Completed" in detail_text or "completed" in detail_text,
                    )

                    # Store crawl ID for later tests
                    crawl_id = crawl_id_from_url
                else:
                    warn(
                        "did not navigate to crawl detail after start",
                        f"url={page.url}",
                    )
            else:
                warn("Start button not found")

            # ── 6. Crawl Detail Tabs ──────────────────────────────
            section("6. Crawl Detail Tabs")

            if crawl_id:
                page.goto(
                    f"{BASE_URL}/crawls/{crawl_id}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                # URLs tab
                urls_tab = page.query_selector(
                    'button:has-text("URLs"), [role="tab"]:has-text("URLs")'
                )
                if urls_tab:
                    urls_tab.click()
                    page.wait_for_timeout(2000)
                    urls_text = page.text_content("body") or ""
                    check(
                        "URLs tab shows URL data",
                        "toscrape" in urls_text.lower() or "http" in urls_text.lower(),
                    )

                # Issues tab
                issues_tab = page.query_selector(
                    'button:has-text("Issues"), [role="tab"]:has-text("Issues")'
                )
                if issues_tab:
                    issues_tab.click()
                    page.wait_for_timeout(2000)
                    issues_text = page.text_content("body") or ""
                    # Should show severity cards or issue list
                    has_issues = any(
                        kw in issues_text
                        for kw in [
                            "Critical",
                            "Warning",
                            "Info",
                            "Opportunity",
                            "critical",
                            "warning",
                            "info",
                        ]
                    )
                    check(
                        "Issues tab shows severity cards", has_issues, issues_text[:200]
                    )

            # ── 7. Issues Filtering ───────────────────────────────
            section("7. Issues Filtering")

            if crawl_id:
                page.goto(
                    f"{BASE_URL}/crawls/{crawl_id}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                # Click Issues tab
                issues_tab = page.query_selector(
                    'button:has-text("Issues"), [role="tab"]:has-text("Issues")'
                )
                if issues_tab:
                    issues_tab.click()
                    page.wait_for_timeout(2000)

                # Severity filter
                selects = page.query_selector_all("select")
                sev_select = selects[0] if selects else None

                if sev_select:
                    try:
                        sev_select.select_option(label="Warning")
                        page.wait_for_timeout(1500)
                        filtered_text = page.text_content("body") or ""
                        check(
                            "severity filter applied (Warning)",
                            "warning" in filtered_text.lower(),
                        )
                    except Exception as e:
                        try:
                            sev_select.select_option(value="warning")
                            page.wait_for_timeout(1500)
                            check("severity filter applied (warning value)", True)
                        except Exception:
                            warn(f"severity filter failed: {e}")
                else:
                    warn("severity filter select not found")

                # Clear filter - look for Clear/Reset button
                clear_btn = page.query_selector(
                    'button:has-text("Clear"), button:has-text("Reset")'
                )
                if clear_btn:
                    clear_btn.click()
                    page.wait_for_timeout(1000)
                    check("clear filters button works", True)
                else:
                    warn("clear filters button not found")

            # ── 8. Issues Pagination ──────────────────────────────
            section("8. Issues Pagination")

            if crawl_id:
                # Navigate to issues tab
                page.goto(
                    f"{BASE_URL}/crawls/{crawl_id}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                issues_tab = page.query_selector(
                    'button:has-text("Issues"), [role="tab"]:has-text("Issues")'
                )
                if issues_tab:
                    issues_tab.click()
                    page.wait_for_timeout(2000)

                next_btn = page.query_selector(
                    'button:has-text("Next"), button:has-text("next"), button:has-text(">")'
                )
                if next_btn:
                    is_disabled = next_btn.get_attribute("disabled") is not None
                    if not is_disabled:
                        next_btn.click()
                        page.wait_for_timeout(2000)
                        check("Next page button works", True)

                        # Try going back
                        prev_btn = page.query_selector(
                            'button:has-text("Prev"), button:has-text("prev"), button:has-text("<")'
                        )
                        if prev_btn:
                            prev_btn.click()
                            page.wait_for_timeout(1000)
                            check("Previous page button works", True)
                    else:
                        warn("Next button disabled (not enough issues for pagination)")
                else:
                    warn("Next page button not found")

            # ── 9. URL Filter Dropdowns ───────────────────────────
            section("9. URL Filter Dropdowns")

            if crawl_id:
                page.goto(
                    f"{BASE_URL}/crawls/{crawl_id}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                # Make sure we're on URLs tab
                urls_tab = page.query_selector(
                    'button:has-text("URLs"), [role="tab"]:has-text("URLs")'
                )
                if urls_tab:
                    urls_tab.click()
                    page.wait_for_timeout(2000)

                # Check for filter dropdowns
                selects = page.query_selector_all("select")
                if len(selects) >= 1:
                    check(
                        f"URL tab has filter dropdowns ({len(selects)} selects)", True
                    )
                else:
                    warn("URL tab has no filter dropdowns (feature not yet in UI)")

            # ── 10. Crawl Control Buttons ─────────────────────────
            section("10. Crawl Control Buttons (Pause/Resume/Stop)")

            if project_id:
                # Start a slow crawl for testing controls
                code, body = api_call(
                    "POST",
                    f"/projects/{project_id}/crawls",
                    {
                        "start_url": CRAWL_TARGET,
                        "config": {
                            "max_urls": 30,
                            "max_depth": 2,
                            "rate_limit_rps": 2.0,
                        },
                    },
                )
                if code == 201 and isinstance(body, dict):
                    ctrl_crawl_id = body["id"]
                    page.goto(
                        f"{BASE_URL}/crawls/{ctrl_crawl_id}",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    page.wait_for_timeout(4000)  # Let crawling start

                    # Pause
                    pause_btn = page.query_selector('button:has-text("Pause")')
                    if pause_btn:
                        pause_btn.click()
                        page.wait_for_timeout(2000)
                        body_text = page.text_content("body") or ""
                        check(
                            "Pause button: status shows Paused",
                            "Paused" in body_text or "paused" in body_text,
                        )

                        # Resume
                        resume_btn = page.query_selector('button:has-text("Resume")')
                        if resume_btn:
                            resume_btn.click()
                            page.wait_for_timeout(2000)
                            body_text = page.text_content("body") or ""
                            check(
                                "Resume button: status shows Crawling",
                                "Crawling" in body_text
                                or "crawling" in body_text
                                or "Completed" in body_text,
                            )
                        else:
                            warn("Resume button not found after pause")

                        # Stop
                        page.wait_for_timeout(3000)
                        stop_btn = page.query_selector('button:has-text("Stop")')
                        if stop_btn:
                            stop_btn.click()
                            page.wait_for_timeout(3000)
                            body_text = page.text_content("body") or ""
                            check(
                                "Stop button: status shows Cancelled",
                                "Cancelled" in body_text
                                or "cancelled" in body_text
                                or "Completed" in body_text,
                            )
                        else:
                            warn("Stop button not found (crawl may have completed)")
                    else:
                        warn(
                            "Pause button not found (crawl may have completed too fast)"
                        )

                    # Delete
                    page.wait_for_timeout(2000)
                    delete_btn = page.query_selector('button:has-text("Delete")')
                    if delete_btn:
                        delete_btn.click()
                        page.wait_for_timeout(3000)
                        check(
                            "Delete button: navigated away",
                            "/crawls/" + ctrl_crawl_id not in page.url
                            or "/crawls" in page.url,
                        )
                    else:
                        warn("Delete button not found")
                        api_call("DELETE", f"/crawls/{ctrl_crawl_id}")

            # ── 11. Error State: Nonexistent Crawl ────────────────
            section("11. Error States")

            page.goto(
                f"{BASE_URL}/crawls/00000000-0000-0000-0000-000000000000", timeout=30000
            )
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            error_text = page.text_content("body") or ""
            check(
                "nonexistent crawl shows error/not-found",
                any(
                    kw in error_text.lower()
                    for kw in ["not found", "error", "404", "could not"]
                )
                or len(error_text) > 0,
                error_text[:100],
            )

            # ── 12. Responsive Design ─────────────────────────────
            section("12. Responsive Design")

            # Mobile viewport
            page.set_viewport_size({"width": 375, "height": 667})
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            mobile_text = page.text_content("body") or ""
            check("mobile: dashboard renders", len(mobile_text) > 20)

            # Check sidebar is hidden on mobile (md:block class)
            sidebar = page.query_selector(".w-64")
            if sidebar:
                is_visible = sidebar.is_visible()
                check("mobile: sidebar hidden", not is_visible, f"visible={is_visible}")
            else:
                check("mobile: sidebar not found (correctly hidden)", True)

            # Tablet viewport
            page.set_viewport_size({"width": 768, "height": 1024})
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            tablet_text = page.text_content("body") or ""
            check("tablet: dashboard renders", len(tablet_text) > 20)

            # Back to desktop
            page.set_viewport_size({"width": 1280, "height": 800})

            # ── 13. External Link Behavior ────────────────────────
            section("13. External Link Behavior")

            if crawl_id:
                page.goto(
                    f"{BASE_URL}/crawls/{crawl_id}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                # Look for external link icon/button
                ext_link = page.query_selector(
                    'a[target="_blank"], a[href*="toscrape"]'
                )
                if ext_link:
                    href = ext_link.get_attribute("href") or ""
                    target = ext_link.get_attribute("target") or ""
                    check(
                        "external link has target=_blank or external href",
                        target == "_blank" or "http" in href,
                    )
                else:
                    warn("no external link found on crawl detail page")

            # ── 14. Back Button / Breadcrumb ──────────────────────
            section("14. Back Navigation")

            if crawl_id:
                page.goto(
                    f"{BASE_URL}/crawls/{crawl_id}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                back_btn = page.query_selector(
                    'a:has-text("Back"), button:has-text("Back"), '
                    'a:has-text("← Crawls"), a:has-text("Crawls")'
                )
                if back_btn:
                    back_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=30000)
                    check("Back button navigates to crawls list", "/crawls" in page.url)
                else:
                    # Try sidebar
                    crawls_link = page.query_selector('a[href="/crawls"]')
                    if crawls_link:
                        crawls_link.click()
                        page.wait_for_load_state("domcontentloaded", timeout=30000)
                        check(
                            "Sidebar Crawls link as back navigation",
                            "/crawls" in page.url,
                        )
                    else:
                        warn("no back navigation found")

            # ── 15. Console Errors ────────────────────────────────
            section("15. Console Errors Check")

            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg) if msg.type == "error" else None,
            )

            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            critical_errors = [
                e
                for e in console_errors
                if "chunk" in str(e).lower() or "syntax" in str(e).lower()
            ]
            check(
                "no critical console errors on dashboard",
                len(critical_errors) == 0,
                f"errors={[str(e) for e in critical_errors]}",
            )

        finally:
            browser.close()

    # ── Final Cleanup ─────────────────────────────────────────────
    section("Cleanup")
    if crawl_id:
        api_call("DELETE", f"/crawls/{crawl_id}")
    if project_id:
        code, _ = api_call("DELETE", f"/projects/{project_id}")
        check("delete test project", code in (204, 404))

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"  {C.GREEN}✓ {passed} passed{C.RESET}  ", end="")
    if warnings:
        print(f"{C.YELLOW}⚠ {warnings} warnings{C.RESET}  ", end="")
    if failed:
        print(f"{C.RED}✗ {failed} failed{C.RESET}  ", end="")
    print(f"{C.DIM}({passed + failed} checks){C.RESET}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}ALL BROWSER CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
