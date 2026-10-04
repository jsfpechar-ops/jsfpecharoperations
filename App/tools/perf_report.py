#!/usr/bin/env python3
"""Weekly performance numbers from the app log (WP13, review 7.3.4).

Reads the PII-free access lines (``ubyhost.access``) and the scheduler's job
lines (``ubyhost.scheduler: job run ...``) from a file or stdin and prints, for
the last 7 days by default:

* p50 and p99 response time per route group (host, guest, public, admin);
* queries per request (mean and p99) and DB time p99 per group;
* lock wait p99 per group;
* error rate (status >= 500) per group;
* per job: runs, failures, p50/p99 run time, and the iCal changed ratio
  (feeds whose calendar changed and was parsed again, over feeds synced;
  WP15 skips the others).

Only group names, job ids and numbers are printed. The access line already
carries the route template instead of the path, but the report still never
prints a route, so nothing token-shaped can reach its output.

Usage::

    docker compose logs --no-color app | python tools/perf_report.py
    python tools/perf_report.py /var/log/ubyhost/app.log --days 7
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, TextIO

GROUPS = ("host", "guest", "public", "admin", "other")

# Signed-out pages. "/" is counted as host: signed in it is the dashboard,
# which is where nearly all of its traffic comes from.
_PUBLIC_EXACT = {
    "/cenik", "/dpa", "/jak-to-funguje", "/legal", "/privacy", "/subprocessors",
    "/terms", "/login", "/login/2fa", "/robots.txt", "/sitemap.xml",
    "/sample-airbnb.ics", "/favicon.ico", "/healthz",
}
_PUBLIC_PREFIXES = ("/pruvodce/", "/invoice/d/")

_TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")
_PAIR_RE = re.compile(r"\b([a-z_]+)=(\S+)")


def route_group(route: str) -> str:
    """The group of a route template; never returns the route itself."""
    if not route or route.startswith("<"):
        return "other"
    if route.startswith("/l/") or route == "/l":
        return "guest"
    if route.startswith("/admin/") or route == "/admin":
        return "admin"
    if route in _PUBLIC_EXACT or route.startswith(_PUBLIC_PREFIXES):
        return "public"
    return "host"


def percentile(values: List[float], pct: float) -> float:
    """Nearest-rank percentile; 0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return float(ordered[min(rank, len(ordered)) - 1])


def _timestamp(line: str) -> Optional[datetime]:
    match = _TIMESTAMP_RE.search(line)
    if not match:
        return None
    try:
        return datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}")
    except ValueError:
        return None


def _int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def parse(lines: Iterable[str], since: Optional[datetime] = None) -> Dict[str, dict]:
    """Collect the numbers, keyed by group and by job id."""
    requests: Dict[str, dict] = defaultdict(
        lambda: {"ms": [], "q": [], "db_ms": [], "lock_ms": [], "errors": 0}
    )
    jobs: Dict[str, dict] = defaultdict(
        lambda: {"ms": [], "failed": 0, "items": defaultdict(int)}
    )
    for line in lines:
        is_access = "ubyhost.access" in line and "route=" in line
        is_job = "ubyhost.scheduler" in line and "job run " in line
        if not (is_access or is_job):
            continue
        if since is not None:
            stamp = _timestamp(line)
            if stamp is not None and stamp < since:
                continue
        pairs = dict(_PAIR_RE.findall(line))
        if is_access:
            bucket = requests[route_group(pairs.get("route", ""))]
            ms = _int(pairs.get("ms"))
            if ms is None:
                continue
            bucket["ms"].append(ms)
            for key in ("q", "db_ms", "lock_ms"):
                value = _int(pairs.get(key))
                if value is not None:
                    bucket[key].append(value)
            status = _int(pairs.get("status")) or 0
            if status >= 500:
                bucket["errors"] += 1
        else:
            job_id = pairs.get("job")
            if not job_id or not re.fullmatch(r"[a-z_]{1,40}", job_id):
                continue
            bucket = jobs[job_id]
            ms = _int(pairs.get("ms"))
            if ms is not None:
                bucket["ms"].append(ms)
            if pairs.get("ok") == "0":
                bucket["failed"] += 1
            for key, raw in pairs.items():
                if key in ("job", "ok", "ms"):
                    continue
                value = _int(raw)
                if value is not None:
                    bucket["items"][key] += value
    return {"requests": dict(requests), "jobs": dict(jobs)}


def render(data: Dict[str, dict], out: TextIO) -> None:
    requests = data["requests"]
    out.write("Requests by route group\n")
    out.write(
        f"{'group':<8}{'count':>8}{'p50 ms':>9}{'p99 ms':>9}{'q/req':>8}{'q p99':>8}"
        f"{'db p99':>8}{'lock p99':>10}{'err %':>8}\n"
    )
    for group in GROUPS:
        bucket = requests.get(group)
        if not bucket or not bucket["ms"]:
            continue
        count = len(bucket["ms"])
        mean_q = sum(bucket["q"]) / len(bucket["q"]) if bucket["q"] else 0.0
        out.write(
            f"{group:<8}{count:>8}{percentile(bucket['ms'], 50):>9.0f}"
            f"{percentile(bucket['ms'], 99):>9.0f}{mean_q:>8.1f}"
            f"{percentile(bucket['q'], 99):>8.0f}{percentile(bucket['db_ms'], 99):>8.0f}"
            f"{percentile(bucket['lock_ms'], 99):>10.0f}"
            f"{100.0 * bucket['errors'] / count:>8.2f}\n"
        )
    all_lock = [value for bucket in requests.values() for value in bucket["lock_ms"]]
    total = sum(len(bucket["ms"]) for bucket in requests.values())
    errors = sum(bucket["errors"] for bucket in requests.values())
    out.write(
        f"all     {total:>8}  lock wait p99 {percentile(all_lock, 99):.0f} ms, "
        f"error rate {100.0 * errors / total if total else 0.0:.2f} %\n"
    )

    jobs = data["jobs"]
    if jobs:
        out.write("\nScheduler jobs\n")
        out.write(f"{'job':<13}{'runs':>6}{'failed':>8}{'p50 ms':>9}{'p99 ms':>9}  items\n")
        for job_id in sorted(jobs):
            bucket = jobs[job_id]
            items = " ".join(f"{key}={value}" for key, value in sorted(bucket["items"].items()))
            out.write(
                f"{job_id:<13}{len(bucket['ms']):>6}{bucket['failed']:>8}"
                f"{percentile(bucket['ms'], 50):>9.0f}{percentile(bucket['ms'], 99):>9.0f}"
                f"  {items}\n"
            )
        ical = jobs.get("ical")
        if ical:
            feeds = ical["items"].get("feeds", 0)
            changed = ical["items"].get("changed", 0)
            ratio = 100.0 * changed / feeds if feeds else 0.0
            out.write(f"\niCal changed ratio: {changed}/{feeds} feed syncs ({ratio:.1f} %)\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("path", nargs="?", help="log file; stdin when omitted or '-'")
    parser.add_argument("--days", type=int, default=7, help="look back this many days (default 7)")
    parser.add_argument(
        "--now", help="end of the window, ISO date-time (default: now, local time of the log)"
    )
    args = parser.parse_args(argv)
    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    since = now - timedelta(days=args.days) if args.days > 0 else None
    if not args.path or args.path == "-":
        data = parse(sys.stdin, since)
    else:
        with open(args.path, encoding="utf-8", errors="replace") as handle:
            data = parse(handle, since)
    render(data, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
