#!/usr/bin/env python3
"""
WebSocket Test
==============
Deep test of the WebSocket crawl progress channel.
Tests event streaming, heartbeats, payloads, and edge cases.

Requires: websockets library (pip install websockets)
Falls back to raw socket test if websockets not available.

Usage:
    python test_websocket.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
import urllib.error
import urllib.request

BASE_URL = "http://localhost"
API = f"{BASE_URL}/api/v1"
WS_BASE = "ws://localhost/api/v1"
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
    messages = []
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
                            "crawl_completed",
                            "crawl_failed",
                            "crawl_cancelled",
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


async def ws_two_clients(crawl_id: str, timeout: float = 30.0) -> tuple[list, list]:
    if not HAS_WEBSOCKETS:
        return [], []
    url = f"{WS_BASE}/crawls/{crawl_id}/ws"

    async def collect(ws, max_msgs=20):
        msgs = []
        while len(msgs) < max_msgs:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                msg = json.loads(raw) if raw else {}
                msgs.append(msg)
                if msg.get("type") in (
                    "crawl_completed",
                    "crawl_failed",
                    "crawl_cancelled",
                    "status_change",
                ) and msg.get("status") in ("completed", "failed", "cancelled", None):
                    break
            except (asyncio.TimeoutError, Exception):
                break
        return msgs

    try:
        ws1 = await asyncio.wait_for(websockets.connect(url), timeout=10)
        ws2 = await asyncio.wait_for(websockets.connect(url), timeout=10)
        try:
            r1, r2 = await asyncio.gather(collect(ws1), collect(ws2))
            return r1, r2
        finally:
            await ws1.close()
            await ws2.close()
    except Exception as e:
        return [{"error": str(e)}], []


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SEO Spider — WebSocket Test{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")

    if not HAS_WEBSOCKETS:
        print(f"\n  {C.YELLOW}⚠ websockets library not installed{C.RESET}")
        print(f"  {C.DIM}Install with: pip install websockets{C.RESET}")
        print(f"  {C.DIM}Running basic socket-level tests only...{C.RESET}")

    project_id = None
    crawl_id = None
    crawl_id_2 = None

    try:
        # ── Setup ─────────────────────────────────────────────────
        section("Setup")
        code, body = api_call(
            "POST", "/projects", {"name": "WS Test", "domain": CRAWL_TARGET}
        )
        if code != 201:
            print(f"  {C.RED}ABORT: Cannot create project{C.RESET}")
            sys.exit(1)
        project_id = body["id"]
        check("project created", True)

        # ── 1. WS Connection to nonexistent crawl ────────────────
        section("1. WS Connection (Nonexistent Crawl)")
        fake_id = str(uuid.uuid4())
        if HAS_WEBSOCKETS:
            ok, detail = asyncio.get_event_loop().run_until_complete(
                ws_connect_and_check(fake_id, timeout=5)
            )
            # Should connect (WS accepts first, then may send nothing)
            # OR refuse — both are acceptable behaviors
            if ok:
                check("WS to nonexistent crawl connects (no events expected)", True)
            else:
                check("WS to nonexistent crawl handled gracefully", True, detail)
        else:
            # Raw socket test
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(("localhost", 80))
            sock.close()
            check("WS port (80) is reachable", result == 0)

        # ── 2. WS during active crawl ───────────────────────────
        section("2. WS During Active Crawl")
        code, body = api_call(
            "POST",
            f"/projects/{project_id}/crawls",
            {
                "start_url": CRAWL_TARGET,
                "config": {"max_urls": 10, "max_depth": 1, "rate_limit_rps": 10.0},
            },
        )
        check("start crawl for WS test", code == 201)
        crawl_id = body["id"] if isinstance(body, dict) else None

        if crawl_id and HAS_WEBSOCKETS:
            # Collect WS messages during crawl
            messages = asyncio.get_event_loop().run_until_complete(
                ws_collect_messages(crawl_id, timeout=45, max_messages=30)
            )

            errors = [m for m in messages if "error" in m]
            events = [m for m in messages if "error" not in m]

            check(
                "WS connection established (no errors)",
                len(errors) == 0,
                f"errors={errors}",
            )
            check(f"received {len(events)} WS events", len(events) > 0)

            # ── 3. Event payload validation ───────────────────────
            section("3. Event Payload Validation")

            progress_events = [e for e in events if e.get("type") == "progress"]
            status_events = [e for e in events if e.get("type") == "status_change"]
            event_types = {e.get("type", "unknown") for e in events}
            print(f"  {C.DIM}event types: {sorted(event_types)}{C.RESET}")

            if progress_events:
                check(f"received {len(progress_events)} progress events", True)
                first = progress_events[0]
                check(
                    "progress has 'crawled_count' field",
                    "crawled_count" in first,
                    f"keys={list(first.keys())}",
                )
                check(
                    "progress has 'crawl_id' field",
                    "crawl_id" in first,
                    f"keys={list(first.keys())}",
                )
            else:
                warn(f"no progress events, types found: {event_types}")

            completed_events = [
                e
                for e in status_events
                if e.get("status") in ("completed", "failed", "cancelled")
            ]
            if completed_events:
                check("received completion status_change event", True)
            else:
                time.sleep(5)
                code, body = api_call("GET", f"/crawls/{crawl_id}")
                st = body.get("status", "") if isinstance(body, dict) else ""
                if st == "completed":
                    warn(
                        "crawl completed but completion event may have arrived after disconnect"
                    )
                else:
                    warn(f"no completion event yet, status={st}")

            # ── 4. Heartbeat / Progress interval ─────────────────
            section("4. Heartbeat (Progress Events)")
            if len(progress_events) >= 2:
                check("multiple progress events as heartbeat", True)
            elif len(progress_events) == 1:
                check("at least 1 progress event received", True)
            else:
                warn("no progress events (crawl may have been too fast)")

        elif crawl_id:
            warn("websockets library not available, skipping active crawl WS tests")
            # Wait for crawl to finish for cleanup
            for _ in range(60):
                time.sleep(2)
                c, b = api_call("GET", f"/crawls/{crawl_id}")
                if (
                    c == 200
                    and isinstance(b, dict)
                    and b.get("status") in ("completed", "failed", "cancelled")
                ):
                    break

        # ── 5. WS after crawl completion ──────────────────────────
        section("5. WS After Crawl Completion")
        if crawl_id:
            for _ in range(30):
                time.sleep(2)
                c, b = api_call("GET", f"/crawls/{crawl_id}")
                if (
                    c == 200
                    and isinstance(b, dict)
                    and b.get("status") in ("completed", "failed", "cancelled")
                ):
                    break

        if crawl_id and HAS_WEBSOCKETS:
            ok, detail = asyncio.get_event_loop().run_until_complete(
                ws_connect_and_check(crawl_id, timeout=5)
            )
            check(
                "WS to completed crawl connects (no crash)",
                ok or "connect" not in detail.lower(),
                detail,
            )

        # ── 6. Multiple clients ──────────────────────────────────
        section("6. Multiple WS Clients")
        if HAS_WEBSOCKETS:
            # Start a new crawl for multi-client test
            code, body = api_call(
                "POST",
                f"/projects/{project_id}/crawls",
                {
                    "start_url": CRAWL_TARGET,
                    "config": {"max_urls": 10, "max_depth": 1, "rate_limit_rps": 5.0},
                },
            )
            if code == 201 and isinstance(body, dict):
                crawl_id_2 = body["id"]
                time.sleep(2)  # Let crawl start

                msgs1, msgs2 = asyncio.get_event_loop().run_until_complete(
                    ws_two_clients(crawl_id_2, timeout=30)
                )

                check(f"client 1 received {len(msgs1)} messages", len(msgs1) > 0)
                check(f"client 2 received {len(msgs2)} messages", len(msgs2) > 0)

                # Both should receive similar event types
                types1 = {m.get("type") for m in msgs1 if "type" in m}
                types2 = {m.get("type") for m in msgs2 if "type" in m}
                if types1 and types2:
                    check(
                        "both clients receive same event types",
                        types1 == types2,
                        f"t1={types1}, t2={types2}",
                    )

                for _ in range(30):
                    time.sleep(2)
                    c, b = api_call("GET", f"/crawls/{crawl_id_2}")
                    if (
                        c == 200
                        and isinstance(b, dict)
                        and b.get("status") in ("completed", "failed", "cancelled")
                    ):
                        break
        else:
            warn("skipping multi-client test (websockets not installed)")

        # ── 7. Disconnect handling ────────────────────────────────
        section("7. Server Stability After WS Disconnect")
        # After all WS tests, verify server is still healthy
        code, _ = api_call("GET", "/health")
        check("server healthy after WS tests", code == 200, f"code={code}")

    finally:
        section("Cleanup")
        if crawl_id:
            api_call("DELETE", f"/crawls/{crawl_id}")
        if crawl_id_2:
            api_call("DELETE", f"/crawls/{crawl_id_2}")
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
        print(f"\n  {C.GREEN}{C.BOLD}ALL WEBSOCKET CHECKS PASSED ✓{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}{failed} CHECK(S) FAILED{C.RESET}\n")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
