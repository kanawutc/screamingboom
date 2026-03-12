#!/usr/bin/env python3
"""
SEO Spider — Server Monitor
============================
Comprehensive health check for all server-side and client-side components.

Usage:
    python monitor.py            # Full status report
    python monitor.py --json     # JSON output
    python monitor.py --watch    # Continuous monitoring (5s interval)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ─── Configuration ────────────────────────────────────────────────────

BASE_URL = "http://localhost"
API_URL = f"{BASE_URL}/api/v1"
COMPOSE_PROJECT = "screamingfrogclone"
REQUEST_TIMEOUT = 5

EXPECTED_CONTAINERS = ["db", "redis", "backend", "worker", "frontend", "nginx"]


# ─── Status Enum ──────────────────────────────────────────────────────


class Status(Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"
    UNKNOWN = "unknown"


# ─── Check Result ─────────────────────────────────────────────────────


@dataclass
class CheckResult:
    name: str
    status: Status
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    response_ms: float | None = None


# ─── ANSI Colors ──────────────────────────────────────────────────────


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"

    @staticmethod
    def status_color(s: Status) -> str:
        return {
            Status.OK: Color.GREEN,
            Status.WARN: Color.YELLOW,
            Status.ERROR: Color.RED,
            Status.UNKNOWN: Color.DIM,
        }[s]


def status_icon(s: Status) -> str:
    return {Status.OK: "✓", Status.WARN: "⚠", Status.ERROR: "✗", Status.UNKNOWN: "?"}[s]


# ─── HTTP Helper ──────────────────────────────────────────────────────


def http_get(url: str, timeout: int = REQUEST_TIMEOUT) -> tuple[int, dict | str, float]:
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = (time.monotonic() - start) * 1000
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body), elapsed
            except json.JSONDecodeError:
                return resp.status, body, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.monotonic() - start) * 1000
        return e.code, str(e.reason), elapsed
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return 0, str(e), elapsed


# ─── Docker Checks ────────────────────────────────────────────────────


def check_docker_running() -> CheckResult:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return CheckResult("Docker Engine", Status.OK, "Running")
        return CheckResult("Docker Engine", Status.ERROR, "Not responding")
    except FileNotFoundError:
        return CheckResult("Docker Engine", Status.ERROR, "Docker CLI not found")
    except subprocess.TimeoutExpired:
        return CheckResult("Docker Engine", Status.ERROR, "Timed out")


def check_containers() -> list[CheckResult]:
    results = []
    try:
        raw = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if raw.returncode != 0:
            return [CheckResult("Containers", Status.ERROR, "docker compose ps failed")]

        containers: list[dict] = []
        for line in raw.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        found_names: set[str] = set()
        for c in containers:
            name = c.get("Name", c.get("Service", "unknown"))
            service = c.get("Service", "")
            state = c.get("State", "unknown")
            health = c.get("Health", "")
            status_str = c.get("Status", "")

            found_names.add(service)

            if service == "migrate":
                continue

            if state == "running":
                if health == "healthy" or "healthy" in status_str.lower():
                    s = Status.OK
                    msg = "Running (healthy)"
                elif health == "unhealthy" or "unhealthy" in status_str.lower():
                    s = Status.WARN
                    msg = "Running (unhealthy)"
                else:
                    s = Status.OK
                    msg = f"Running — {status_str}" if status_str else "Running"
            elif state == "exited":
                exit_code = c.get("ExitCode", "?")
                if service == "migrate" and str(exit_code) == "0":
                    s = Status.OK
                    msg = "Completed successfully"
                else:
                    s = Status.ERROR
                    msg = f"Exited (code {exit_code})"
            else:
                s = Status.WARN
                msg = f"State: {state}"

            details = {}
            if c.get("Publishers"):
                seen_targets: set[int] = set()
                port_strs: list[str] = []
                for p in c["Publishers"]:
                    pub = p.get("PublishedPort")
                    tgt = p.get("TargetPort")
                    if pub and tgt and tgt not in seen_targets:
                        seen_targets.add(tgt)
                        port_strs.append(f"{pub}→{tgt}")
                if port_strs:
                    details["ports"] = ", ".join(port_strs)

            results.append(CheckResult(f"Container: {service}", s, msg, details))

        for expected in EXPECTED_CONTAINERS:
            if expected not in found_names:
                results.append(
                    CheckResult(f"Container: {expected}", Status.ERROR, "Not found")
                )

    except FileNotFoundError:
        results.append(
            CheckResult("Containers", Status.ERROR, "docker compose not found")
        )
    except subprocess.TimeoutExpired:
        results.append(CheckResult("Containers", Status.ERROR, "Timed out"))

    return results


def check_container_resources() -> list[CheckResult]:
    results = []
    try:
        raw = subprocess.run(
            [
                "docker",
                "compose",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if raw.returncode != 0:
            return []

        for line in raw.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            name, cpu, mem_usage, mem_pct = parts[0], parts[1], parts[2], parts[3]

            stripped = name.replace(f"{COMPOSE_PROJECT}-", "")
            short_name = (
                stripped.rsplit("-", 1)[0] if stripped[-1:].isdigit() else stripped
            )

            cpu_val = float(cpu.replace("%", "")) if "%" in cpu else 0
            mem_val = float(mem_pct.replace("%", "")) if "%" in mem_pct else 0

            if cpu_val > 90 or mem_val > 90:
                s = Status.WARN
            else:
                s = Status.OK

            results.append(
                CheckResult(
                    f"Resources: {short_name}",
                    s,
                    f"CPU {cpu} | Mem {mem_usage} ({mem_pct})",
                )
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return results


# ─── Server-Side Checks ──────────────────────────────────────────────


def check_backend_services() -> list[CheckResult]:
    """Single /health fetch → 3 CheckResults: Backend API, PostgreSQL, Redis."""
    code, body, ms = http_get(f"{API_URL}/health")

    if code != 200 or not isinstance(body, dict):
        err = f"HTTP {code}: {body}"
        return [
            CheckResult("Backend API", Status.ERROR, err, response_ms=ms),
            CheckResult("PostgreSQL", Status.UNKNOWN, "Cannot reach API"),
            CheckResult("Redis", Status.UNKNOWN, "Cannot reach API"),
        ]

    api_status = body.get("status", "unknown")
    services = body.get("services", {})
    version = body.get("version", "?")

    api_result = CheckResult(
        "Backend API",
        Status.OK if api_status == "healthy" else Status.WARN,
        f"{api_status.capitalize()} (v{version})",
        {"services": services},
        response_ms=ms,
    )

    db_status = services.get("database", "unknown")
    db_result = CheckResult(
        "PostgreSQL",
        Status.OK if db_status == "ok" else Status.ERROR,
        "Connected" if db_status == "ok" else f"Status: {db_status}",
        response_ms=ms,
    )

    redis_status = services.get("redis", "unknown")
    redis_result = CheckResult(
        "Redis",
        Status.OK if redis_status == "ok" else Status.ERROR,
        "Connected" if redis_status == "ok" else f"Status: {redis_status}",
        response_ms=ms,
    )

    return [api_result, db_result, redis_result]


def check_api_endpoints() -> list[CheckResult]:
    results = []
    endpoints = [
        ("GET /projects", f"{API_URL}/projects?limit=1"),
        ("GET /health", f"{API_URL}/health"),
    ]
    for name, url in endpoints:
        code, body, ms = http_get(url)
        if code == 200:
            results.append(
                CheckResult(f"Endpoint: {name}", Status.OK, f"200 OK", response_ms=ms)
            )
        else:
            results.append(
                CheckResult(
                    f"Endpoint: {name}", Status.ERROR, f"HTTP {code}", response_ms=ms
                )
            )
    return results


_WORKER_ERROR_MARKERS = ("Traceback", "Exception", "CRITICAL", "level=error")


def check_worker() -> CheckResult:
    try:
        raw = subprocess.run(
            ["docker", "compose", "logs", "--tail", "20", "worker"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        logs = raw.stdout + raw.stderr
        found = [m for m in _WORKER_ERROR_MARKERS if m in logs]
        if found:
            return CheckResult(
                "Worker",
                Status.WARN,
                f"Recent errors in logs (matched: {', '.join(found)})",
                {"tail": logs[-500:]},
            )
        if raw.returncode == 0 and logs.strip():
            return CheckResult("Worker", Status.OK, "Running (no recent errors)")
        return CheckResult("Worker", Status.UNKNOWN, "No recent log output")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return CheckResult("Worker", Status.UNKNOWN, "Cannot read worker logs")


# ─── Client-Side Checks ──────────────────────────────────────────────


def check_nginx() -> CheckResult:
    code, _, ms = http_get(BASE_URL)
    if code == 200:
        return CheckResult(
            "Nginx Proxy", Status.OK, "Serving on port 80", response_ms=ms
        )
    return CheckResult("Nginx Proxy", Status.ERROR, f"HTTP {code}", response_ms=ms)


def check_frontend() -> CheckResult:
    code, body, ms = http_get(BASE_URL)
    if code != 200:
        return CheckResult(
            "Frontend (Next.js)", Status.ERROR, f"HTTP {code}", response_ms=ms
        )
    is_html = isinstance(body, str) and (
        "</html>" in body.lower()
        or "<!doctype" in body.lower()
        or "__next" in body.lower()
    )
    if is_html:
        return CheckResult(
            "Frontend (Next.js)", Status.OK, "Serving HTML", response_ms=ms
        )
    # 200 but not HTML — likely JSON or empty; frontend not serving properly
    return CheckResult(
        "Frontend (Next.js)",
        Status.WARN,
        "200 OK but response is not HTML",
        response_ms=ms,
    )


def check_frontend_pages() -> list[CheckResult]:
    results = []
    pages = [
        ("Crawls /crawls", f"{BASE_URL}/crawls"),
    ]
    for name, url in pages:
        code, _, ms = http_get(url)
        if code == 200:
            results.append(
                CheckResult(f"Page: {name}", Status.OK, "200 OK", response_ms=ms)
            )
        else:
            results.append(
                CheckResult(
                    f"Page: {name}", Status.ERROR, f"HTTP {code}", response_ms=ms
                )
            )
    return results


# ─── Application State ────────────────────────────────────────────────


def check_crawl_state() -> list[CheckResult]:
    results = []
    code, body, ms = http_get(f"{API_URL}/projects?limit=100")
    if code != 200 or not isinstance(body, dict):
        return [
            CheckResult("Application State", Status.UNKNOWN, "Cannot fetch projects")
        ]

    projects = body.get("items", [])
    results.append(
        CheckResult(
            "Projects", Status.OK, f"{len(projects)} project(s)", response_ms=ms
        )
    )

    total_crawls = 0
    active_crawls = 0
    failed_crawls = 0
    completed_crawls = 0
    last_completed_id: str | None = None

    for proj in projects:
        pid = proj.get("id", "")
        c_code, c_body, _ = http_get(f"{API_URL}/projects/{pid}/crawls?limit=100")
        if c_code != 200 or not isinstance(c_body, dict):
            continue

        crawls = c_body.get("items", [])
        total_crawls += len(crawls)

        for crawl in crawls:
            status = crawl.get("status", "")
            if status in ("queued", "crawling", "paused", "completing"):
                active_crawls += 1
            elif status == "failed":
                failed_crawls += 1
            elif status == "completed":
                completed_crawls += 1
                if last_completed_id is None:
                    last_completed_id = crawl.get("id", "")

    crawl_status = Status.OK
    if failed_crawls > 0:
        crawl_status = Status.WARN

    results.append(
        CheckResult(
            "Crawls",
            crawl_status,
            f"{total_crawls} total, {active_crawls} active, "
            f"{completed_crawls} completed, {failed_crawls} failed",
        )
    )

    if last_completed_id:
        s_code, s_body, _ = http_get(
            f"{API_URL}/crawls/{last_completed_id}/issues/summary"
        )
        if s_code == 200 and isinstance(s_body, dict):
            total_issues = s_body.get("total", 0)
            if total_issues > 0:
                results.append(
                    CheckResult(
                        "SEO Issues",
                        Status.OK,
                        f"{total_issues} issues in latest completed crawl",
                    )
                )

    return results


# ─── Report ───────────────────────────────────────────────────────────


@dataclass
class MonitorReport:
    timestamp: str
    checks: list[CheckResult]

    @property
    def overall_status(self) -> Status:
        if any(c.status == Status.ERROR for c in self.checks):
            return Status.ERROR
        if any(c.status == Status.WARN for c in self.checks):
            return Status.WARN
        return Status.OK

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall_status.value,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    **({"details": c.details} if c.details else {}),
                    **(
                        {"response_ms": round(c.response_ms, 1)}
                        if c.response_ms
                        else {}
                    ),
                }
                for c in self.checks
            ],
        }


def run_all_checks() -> MonitorReport:
    checks: list[CheckResult] = []

    # 1. Docker engine
    checks.append(check_docker_running())
    if checks[-1].status == Status.ERROR:
        return MonitorReport(datetime.now(timezone.utc).isoformat(), checks)

    # 2. Container status
    checks.extend(check_containers())

    # 3. Resource usage
    checks.extend(check_container_resources())

    # 4. Server-side: API + DB + Redis (single /health fetch)
    checks.extend(check_backend_services())
    checks.append(check_worker())

    # 5. API endpoints
    checks.extend(check_api_endpoints())

    # 6. Client-side: Nginx + Frontend
    checks.append(check_nginx())
    checks.append(check_frontend())
    checks.extend(check_frontend_pages())

    # 7. Application state
    checks.extend(check_crawl_state())

    return MonitorReport(datetime.now(timezone.utc).isoformat(), checks)


# ─── Display ──────────────────────────────────────────────────────────


def print_report(report: MonitorReport) -> None:
    c = Color
    overall = report.overall_status
    oc = Color.status_color(overall)
    ts = report.timestamp[:19].replace("T", " ") + " UTC"

    print()
    print(f"{c.BOLD}{'═' * 60}{c.RESET}")
    print(f"{c.BOLD}  SEO Spider — Server Monitor{c.RESET}")
    print(f"  {c.DIM}{ts}{c.RESET}")
    print(
        f"  Overall: {oc}{c.BOLD}{status_icon(overall)} {overall.value.upper()}{c.RESET}"
    )
    print(f"{c.BOLD}{'═' * 60}{c.RESET}")
    print()

    section = ""
    for check in report.checks:
        name = check.name
        if ":" in name:
            prefix = name.split(":")[0]
        else:
            prefix = name

        if prefix != section:
            section = prefix
            if prefix in ("Container", "Endpoint", "Page"):
                print(f"  {c.BOLD}{c.CYAN}▸ {prefix}s{c.RESET}")
            elif prefix == "Resources":
                print(f"  {c.BOLD}{c.CYAN}▸ {prefix}{c.RESET}")
            else:
                print(f"  {c.BOLD}{c.CYAN}▸ {name}{c.RESET}")

        sc = Color.status_color(check.status)
        icon = status_icon(check.status)
        latency = (
            f" {c.DIM}({check.response_ms:.0f}ms){c.RESET}" if check.response_ms else ""
        )
        display_name = name.split(": ", 1)[1] if ": " in name else name

        if ":" in name:
            print(
                f"    {sc}{icon}{c.RESET} {display_name:<24} {check.message}{latency}"
            )
        else:
            print(f"    {sc}{icon}{c.RESET} {check.message}{latency}")

        if check.details:
            for k, v in check.details.items():
                print(f"      {c.DIM}{k}: {v}{c.RESET}")

    print()

    ok_count = sum(1 for ch in report.checks if ch.status == Status.OK)
    warn_count = sum(1 for ch in report.checks if ch.status == Status.WARN)
    err_count = sum(1 for ch in report.checks if ch.status == Status.ERROR)
    total = len(report.checks)

    print(f"  {c.GREEN}✓ {ok_count} passed{c.RESET}  ", end="")
    if warn_count:
        print(f"{c.YELLOW}⚠ {warn_count} warnings{c.RESET}  ", end="")
    if err_count:
        print(f"{c.RED}✗ {err_count} errors{c.RESET}  ", end="")
    print(f"{c.DIM}({total} checks){c.RESET}")
    print()


# ─── Main ─────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Spider Server Monitor")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--watch", action="store_true", help="Continuous monitoring (5s interval)"
    )
    parser.add_argument(
        "--interval", type=int, default=5, help="Watch interval in seconds"
    )
    args = parser.parse_args()

    report = run_all_checks()

    if args.watch:
        try:
            while True:
                if not args.json:
                    print("\033[2J\033[H", end="")
                if args.json:
                    print(json.dumps(report.to_dict(), indent=2))
                else:
                    print_report(report)
                    print(
                        f"  {Color.DIM}Refreshing in {args.interval}s... (Ctrl+C to stop){Color.RESET}"
                    )
                time.sleep(args.interval)
                report = run_all_checks()
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print_report(report)

    sys.exit(0 if report.overall_status == Status.OK else 1)


if __name__ == "__main__":
    main()
