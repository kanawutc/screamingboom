#!/usr/bin/env python3
"""
SEO Spider — Background Monitor Daemon
=======================================
Runs every 5 minutes. Checks server + client health, scans logs for errors,
auto-fixes common issues (container restarts, nginx 502, etc.).

Usage:
    python3 monitor_daemon.py              # foreground (Ctrl+C to stop)
    python3 monitor_daemon.py --once       # single check then exit
    python3 monitor_daemon.py --interval 60  # custom interval (seconds)

Logs to: logs/monitor.log + stdout
"""

import subprocess, json, time, sys, os, re, signal
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
INTERVAL = 300  # 5 minutes default
API_BASE = "http://localhost/api/v1"
FRONTEND_URL = "http://localhost/"
LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "monitor.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB rotation
TZ = timezone(timedelta(hours=7))  # GMT+7

CONTAINERS = [
    "screamingfrogclone-backend-1",
    "screamingfrogclone-worker-1",
    "screamingfrogclone-db-1",
    "screamingfrogclone-redis-1",
    "screamingfrogclone-nginx-1",
]

# Track state across checks
last_errors: dict[str, list[str]] = {}
consecutive_failures: dict[str, int] = {c: 0 for c in CONTAINERS}
consecutive_failures["api"] = 0
consecutive_failures["frontend"] = 0
check_count = 0
fix_count = 0
running = True

# ── Helpers ─────────────────────────────────────────────────────────


def now() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str, level: str = "INFO"):
    ts = now()
    line = f"[{ts}] [{level:7s}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(exist_ok=True)
        # Rotate if too large
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE:
            rotated = LOG_FILE.with_suffix(".log.1")
            if rotated.exists():
                rotated.unlink()
            LOG_FILE.rename(rotated)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run(cmd: str, timeout: int = 15) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)


def curl(url: str, timeout: int = 10) -> tuple[int, int, str]:
    """Returns (exit_code, http_status, body)"""
    tmp = Path("/tmp/_mon_body")
    code, out = run(
        f'curl -s -o /tmp/_mon_body -w "%{{http_code}}" --max-time {timeout} "{url}"'
    )
    if code != 0:
        tmp.unlink(missing_ok=True)
        return code, 0, out
    try:
        http_status = int(out.strip())
    except ValueError:
        http_status = 0
    try:
        body = tmp.read_text()[:2000]
    except Exception:
        body = ""
    finally:
        tmp.unlink(missing_ok=True)
    return 0, http_status, body


def signal_handler(sig, frame):
    global running
    log("Received shutdown signal. Stopping gracefully...", "WARN")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ── Checks ──────────────────────────────────────────────────────────


def check_containers() -> list[str]:
    """Check all Docker containers are running and healthy."""
    errors = []
    code, out = run(
        "docker compose ps --format json 2>/dev/null || docker compose ps 2>/dev/null"
    )
    if code != 0:
        errors.append(f"docker compose ps failed: {out[:200]}")
        return errors

    # Parse JSON lines output
    running_containers = {}
    for line in out.strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            c = json.loads(line)
            name = c.get("Name", "")
            status = c.get("Status", "").lower()
            health = c.get("Health", "").lower()
            state = c.get("State", "").lower()
            running_containers[name] = {
                "status": status,
                "health": health,
                "state": state,
            }
        except json.JSONDecodeError:
            continue

    for container in CONTAINERS:
        if container not in running_containers:
            errors.append(f"Container {container} is NOT running")
            consecutive_failures[container] = consecutive_failures.get(container, 0) + 1
        else:
            info = running_containers[container]
            state = info["state"]
            health = info["health"]
            if state != "running":
                errors.append(f"Container {container} state={state} (expected running)")
                consecutive_failures[container] = (
                    consecutive_failures.get(container, 0) + 1
                )
            elif health and health not in ("healthy", ""):
                errors.append(f"Container {container} health={health}")
                consecutive_failures[container] = (
                    consecutive_failures.get(container, 0) + 1
                )
            else:
                consecutive_failures[container] = 0

    return errors


def check_api_health() -> list[str]:
    """Check backend API /health endpoint."""
    errors = []
    exit_code, status, body = curl(f"{API_BASE.replace('/api/v1', '')}/api/v1/health")

    if exit_code != 0:
        errors.append(f"API health unreachable (curl exit={exit_code})")
        consecutive_failures["api"] = consecutive_failures.get("api", 0) + 1
        return errors

    if status != 200:
        errors.append(f"API health returned HTTP {status}")
        consecutive_failures["api"] = consecutive_failures.get("api", 0) + 1
        return errors

    try:
        data = json.loads(body)
        if data.get("status") != "healthy":
            errors.append(f"API status={data.get('status')} (expected healthy)")
        services = data.get("services", {})
        if services.get("database") != "ok":
            errors.append(f"Database status={services.get('database')} (expected ok)")
        if services.get("redis") != "ok":
            errors.append(f"Redis status={services.get('redis')} (expected ok)")
        if not errors:
            consecutive_failures["api"] = 0
    except json.JSONDecodeError:
        errors.append(f"API health returned invalid JSON: {body[:100]}")

    return errors


def check_frontend() -> list[str]:
    """Check frontend is serving pages."""
    errors = []
    exit_code, status, body = curl(FRONTEND_URL)

    if exit_code != 0:
        errors.append(f"Frontend unreachable (curl exit={exit_code})")
        consecutive_failures["frontend"] = consecutive_failures.get("frontend", 0) + 1
        return errors

    if status != 200:
        errors.append(f"Frontend returned HTTP {status}")
        consecutive_failures["frontend"] = consecutive_failures.get("frontend", 0) + 1
    elif "SEO Spider" not in body and "<html" not in body.lower():
        errors.append("Frontend returned 200 but doesn't look like our app")
        consecutive_failures["frontend"] = consecutive_failures.get("frontend", 0) + 1
    else:
        consecutive_failures["frontend"] = 0

    return errors


def check_api_endpoints() -> list[str]:
    """Spot-check key API endpoints."""
    errors = []
    endpoints = [
        ("GET", f"{API_BASE}/projects?limit=1", 200),
    ]
    for method, url, expected_status in endpoints:
        exit_code, status, body = curl(url)
        if exit_code != 0:
            errors.append(f"{method} {url} \u2014 unreachable")
        elif status != expected_status:
            errors.append(
                f"{method} {url} \u2014 HTTP {status} (expected {expected_status})"
            )
    return errors


def scan_container_logs(since_minutes: int = 6) -> list[str]:
    """Scan recent Docker logs for errors/exceptions."""
    errors = []
    error_patterns = [
        r"(?i)traceback",
        r"(?i)unhandled\s+exception",
        r"(?i)fatal\s+error",
        r"(?i)segmentation\s+fault",
        r"(?i)out\s+of\s+memory",
        r"(?i)connection\s+refused",
        r"(?i)cannot\s+allocate\s+memory",
    ]
    # Less noisy patterns we still want to count
    warn_patterns = [
        r"(?i)error",
        r"(?i)failed",
    ]
    # Patterns to IGNORE (normal operations)
    ignore_patterns = [
        r"error_page",
        r"proxy_next_upstream",
        r"error\.html",
        r"error_log",
        r"KeyboardInterrupt",
        r"rate.limit",
        r'"error":null',
        r"no error",
        r"error_count.*0",
    ]

    for container in CONTAINERS:
        code, out = run(
            f"docker logs --since {since_minutes}m {container} 2>&1 | tail -200",
            timeout=10,
        )
        if code != 0:
            continue

        lines = out.split("\n")
        critical_lines = []
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # Skip ignored patterns
            if any(re.search(p, line_stripped) for p in ignore_patterns):
                continue
            # Check critical patterns
            if any(re.search(p, line_stripped) for p in error_patterns):
                critical_lines.append(line_stripped[:200])

        if critical_lines:
            # Deduplicate similar lines
            unique = list(dict.fromkeys(critical_lines))[:5]
            short_name = container.replace("screamingfrogclone-", "").replace("-1", "")
            errors.append(
                f"[{short_name}] {len(critical_lines)} error(s) in last {since_minutes}min: {unique[0]}"
            )

    return errors


def check_disk_space() -> list[str]:
    """Check Docker volume / host disk usage."""
    errors = []
    code, out = run("df -h / | tail -1")
    if code == 0:
        parts = out.split()
        if len(parts) >= 5:
            usage_str = parts[4].replace("%", "")
            try:
                usage = int(usage_str)
                if usage > 90:
                    errors.append(f"Disk usage at {usage}% \u2014 critically low space")
                elif usage > 80:
                    errors.append(f"Disk usage at {usage}% \u2014 getting low")
            except ValueError:
                pass
    return errors


def check_active_crawls() -> list[str]:
    """Check for stuck crawls (running > 30 min without progress)."""
    errors = []
    exit_code, status, body = curl(f"{API_BASE}/projects?limit=100")
    if exit_code != 0 or status != 200:
        return errors

    try:
        projects = json.loads(body).get("items", [])
    except (json.JSONDecodeError, AttributeError):
        return errors

    for project in projects:
        pid = project.get("id")
        if not pid:
            continue
        exit_code2, status2, body2 = curl(f"{API_BASE}/projects/{pid}/crawls?limit=10")
        if exit_code2 != 0 or status2 != 200:
            continue
        try:
            crawls = json.loads(body2).get("items", [])
        except (json.JSONDecodeError, AttributeError):
            continue

        for crawl in crawls:
            cstatus = crawl.get("status", "")
            if cstatus in ("crawling", "queued"):
                created = crawl.get("created_at", "")
                if created:
                    try:
                        created_dt = datetime.fromisoformat(
                            created.replace("Z", "+00:00")
                        )
                        age = datetime.now(timezone.utc) - created_dt
                        if age > timedelta(minutes=30):
                            errors.append(
                                f"Crawl {crawl['id'][:8]}... stuck in '{cstatus}' for {int(age.total_seconds() // 60)}min"
                            )
                    except (ValueError, TypeError):
                        pass

    return errors


# ── Auto-Fix ────────────────────────────────────────────────────────


def auto_fix(all_errors: dict[str, list[str]]) -> list[str]:
    """Attempt automatic fixes for known issues. Returns list of actions taken."""
    global fix_count
    actions = []

    # Fix 1: Restart crashed containers (after 2 consecutive failures)
    for container in CONTAINERS:
        if consecutive_failures.get(container, 0) >= 2:
            short = container.replace("screamingfrogclone-", "").replace("-1", "")
            log(
                f"Auto-fix: restarting {short} (failed {consecutive_failures[container]}x)",
                "FIX",
            )
            code, out = run(
                f"docker compose restart {short.replace('-1', '')}", timeout=30
            )
            if code == 0:
                actions.append(f"Restarted {short}")
                consecutive_failures[container] = 0
                fix_count += 1
            else:
                actions.append(f"Failed to restart {short}: {out[:100]}")

    # Fix 2: Nginx 502 (backend IP changed) - restart nginx
    api_errors = all_errors.get("api", [])
    if any("502" in e or "unreachable" in e for e in api_errors):
        if consecutive_failures.get("api", 0) >= 2:
            log("Auto-fix: restarting nginx (possible backend IP mismatch)", "FIX")
            code, out = run("docker compose restart nginx", timeout=30)
            if code == 0:
                actions.append("Restarted nginx (502 fix)")
                consecutive_failures["api"] = 0
                fix_count += 1

    # Fix 3: Stuck crawl > 60 min - stop it
    crawl_errors = all_errors.get("crawls", [])
    for err in crawl_errors:
        match = re.search(r"Crawl ([a-f0-9]{8})\.\.\. stuck.*?(\d+)min", err)
        if match:
            crawl_prefix = match.group(1)
            minutes = int(match.group(2))
            if minutes > 60:
                log(
                    f"Auto-fix: stuck crawl {crawl_prefix} running >{minutes}min", "FIX"
                )
                # We'd need the full ID to stop it - log for manual intervention
                actions.append(
                    f"ALERT: Crawl {crawl_prefix}... stuck >{minutes}min - needs manual stop"
                )

    return actions


# ── Main Loop ───────────────────────────────────────────────────────


def run_check() -> dict:
    """Run all checks, return summary."""
    global check_count
    check_count += 1

    log(f"{'=' * 60}", "INFO")
    log(f"Health Check #{check_count}", "INFO")
    log(f"{'=' * 60}", "INFO")

    all_errors: dict[str, list[str]] = {}
    all_ok = True

    # 1. Container health
    errs = check_containers()
    if errs:
        all_errors["containers"] = errs
        all_ok = False
        for e in errs:
            log(e, "ERROR")
    else:
        log("Containers: all 5 running", "OK")

    # 2. API health
    errs = check_api_health()
    if errs:
        all_errors["api"] = errs
        all_ok = False
        for e in errs:
            log(e, "ERROR")
    else:
        log("API health: healthy (db=ok, redis=ok)", "OK")

    # 3. Frontend
    errs = check_frontend()
    if errs:
        all_errors["frontend"] = errs
        all_ok = False
        for e in errs:
            log(e, "ERROR")
    else:
        log("Frontend: serving (200)", "OK")

    # 4. API endpoints
    errs = check_api_endpoints()
    if errs:
        all_errors["endpoints"] = errs
        all_ok = False
        for e in errs:
            log(e, "WARN")
    else:
        log("API endpoints: all responding", "OK")

    # 5. Container logs
    errs = scan_container_logs(since_minutes=6)
    if errs:
        all_errors["logs"] = errs
        for e in errs:
            log(e, "WARN")
    else:
        log("Container logs: clean (no critical errors)", "OK")

    # 6. Disk space
    errs = check_disk_space()
    if errs:
        all_errors["disk"] = errs
        for e in errs:
            log(e, "WARN")
    else:
        log("Disk space: OK", "OK")

    # 7. Stuck crawls
    errs = check_active_crawls()
    if errs:
        all_errors["crawls"] = errs
        for e in errs:
            log(e, "WARN")
    else:
        log("Active crawls: none stuck", "OK")

    # Auto-fix
    if all_errors:
        actions = auto_fix(all_errors)
        if actions:
            log(f"Auto-fix actions: {actions}", "FIX")

    # Summary
    total_errors = sum(len(v) for v in all_errors.values())
    status = "HEALTHY" if all_ok else f"DEGRADED ({total_errors} issue(s))"
    log(
        f"Status: {status}  |  Checks: {check_count}  |  Fixes applied: {fix_count}",
        "INFO",
    )
    log("", "INFO")

    return {"ok": all_ok, "errors": all_errors, "total_errors": total_errors}


def main():
    global INTERVAL

    # Parse args
    once = "--once" in sys.argv
    for i, arg in enumerate(sys.argv):
        if arg == "--interval" and i + 1 < len(sys.argv):
            try:
                INTERVAL = int(sys.argv[i + 1])
            except ValueError:
                pass

    log(f"SEO Spider Monitor started (interval={INTERVAL}s, pid={os.getpid()})", "INFO")
    log(f"Log file: {LOG_FILE}", "INFO")

    if once:
        result = run_check()
        sys.exit(0 if result["ok"] else 1)

    # Continuous loop
    while running:
        try:
            run_check()
        except Exception as e:
            log(f"Monitor check failed: {e}", "ERROR")

        # Sleep in small increments so we can catch SIGTERM quickly
        for _ in range(INTERVAL):
            if not running:
                break
            time.sleep(1)

    log("Monitor daemon stopped.", "INFO")


if __name__ == "__main__":
    main()
