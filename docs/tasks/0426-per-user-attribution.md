# 0426: Per-user attribution — host id on the access line, daily storage report

Status: todo
Depends on: 0425 | Base commit: 05a69e244bbf5a17478afb9cbe7a5c4a87159c9e | Branch: task/0426-per-user-attribution
Executor: GLM Flash (owner's choice for this task) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make the per-request access line carry the numeric host id, and add a daily worker job that logs one PII-free line about disk usage per host and for the whole volume. Together with Loki (brief 0425) this answers, from a browser: how much request volume, request time and storage each host causes.

## 2. Context

Owner decisions (chat 2026-10-27): the numeric host id is allowed on access lines (pseudonymous only — no e-mail, no name); Grafana Labs is a subprocessor for these logs (ROPA row in step 5).

Hard rule 2 applies: new personal-data usage gets a line in App/app/retention.py; the PR description states the reason for the outbound flow (operational monitoring; ids and byte counts only).

Excerpts (verbatim; if any is not found, STOP §8).

App/app/main.py — the logger:

    log = logging.getLogger("ubyhost")
    # OPS-3: one PII-free line per request, carrying the route template only.
    log_access = logging.getLogger("ubyhost.access")

App/app/main.py — the middleware call site:

    if config.ACCESS_LOG:
        _log_access(request, response.status_code, started, stats)
    return response

App/app/main.py — the whole _log_access:

    def _log_access(
        request: Request,
        status_code: int,
        started: float,
        stats: "db.RequestStats | None" = None,
    ) -> None:
        path = request.url.path
        if path.startswith("/static/") or path == "/healthz":
            return
        stats = stats or db.RequestStats()
        # q, db_ms and lock_ms are counts and durations only; they carry nothing
        # from the request, so the line stays as PII-free as the route template.
        log_access.info(
            "method=%s route=%s status=%s ms=%d q=%d db_ms=%d lock_ms=%d",
            request.method,
            _access_route(request),
            status_code,
            int((time.perf_counter() - started) * 1000),
            stats.queries,
            int(stats.db_seconds * 1000),
            int(stats.lock_seconds * 1000),
        )

App/app/scheduler.py — job levels (the dict continues; add one entry, do not reorder):

    _JOB_LEVELS = {
        "ical": "warning",
        "submit": "critical",
        "deadlines": "critical",
        "mail": "warning",
        "photo_sweep": "warning",
        "retention": "warning",

App/app/scheduler.py — the registration pattern:

        _scheduler.add_job(
            _job_guide_import, "interval", minutes=minutes["guide_import"],
            id="guide_import", max_instances=1, coalesce=True,
        )
        _scheduler.start()

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/main.py | edit | host=%d on the access line + _access_host_id helper |
| App/app/retention.py | edit | one line: access lines carry the numeric host id and where they are kept |
| App/app/scheduler.py | edit | _job_storage_report, cron registration, _JOB_LEVELS entry |
| docs/privacy/ROPA.md | edit | Grafana Labs subprocessor row, matching the file's table format |
| App/tests/ (the file grep finds) | edit or create | update the access-line format test, or add one |

No other file may change.

## 4. Steps

Step 1 — find the session-to-host helper routes already use:

    grep -n "^def " App/app/auth.py 2>&1 | head -50

There must be one existing helper that maps a request to the signed-in host (routes depend on it). Use exactly that helper; do not write a new DB query pattern. If none exists or the choice is ambiguous, STOP (§8).

Step 2 — App/app/main.py: change only the format string and add the last argument of _log_access:

        log_access.info(
            "method=%s route=%s status=%s ms=%d q=%d db_ms=%d lock_ms=%d host=%d",
            request.method,
            _access_route(request),
            status_code,
            int((time.perf_counter() - started) * 1000),
            stats.queries,
            int(stats.db_seconds * 1000),
            int(stats.lock_seconds * 1000),
            _access_host_id(request),
        )

and add this helper right after _access_route (same file; the helper call is the one found in step 1):

    def _access_host_id(request: Request) -> int:
        """Numeric host id for the access line; 0 when no host session exists.

        The number is the only identifier on the line (owner decision,
        2026-10-27): no e-mail, no name, and anonymous and guest requests
        without a session are 0. Access logging must never break a request.
        """
        try:
            host = <the auth helper from step 1>(request)
            return int(getattr(host, "id", 0) or 0)
        except Exception:
            return 0

Step 3 — App/app/retention.py: find where data kinds are listed:

    grep -n "^def \|^#\|^## " App/app/retention.py 2>&1 | head -50

Add one line in the file's own style:

    # Access log lines (ubyhost.access): carry the numeric host id only; kept
    # in container logs (json-file, 10 MB × 5) and in Grafana Cloud Loki for
    # the free-tier retention period; no guest data, e-mail or name.

If retention.py has no such list, STOP and report.

Step 4 — App/app/scheduler.py: first inspect the data layout (grep only, no whole-file reads):

    grep -rn "passport_photos" App/app/config.py App/app/passport_photos.py 2>&1 | head -50
    grep -rn "guide_photos" App/app/config.py App/app/guide_photos.py 2>&1 | head -50
    grep -rln "CREATE TABLE" App/app/migrations 2>&1 | head -10

Then add, after the existing _job_* functions, in the file's style:

    def _job_storage_report() -> None:
        """One PII-free line per day: disk usage per host and for the volume.

        Everything is a byte count or a numeric id, so the line can go to
        Grafana Cloud like the access lines (owner decision, 2026-10-27).
        """
        import json
        import os

        def _tree_bytes(path):
            total = 0
            try:
                for entry in os.scandir(path):
                    if entry.is_dir(follow_symlinks=False):
                        total += _tree_bytes(entry.path)
                    else:
                        total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                pass
            return total

        usage = os.statvfs(config.DATA_DIR)
        db_bytes = 0
        for name in ("ubyhost.db", "ubyhost.db-wal"):
            try:
                db_bytes += os.stat(config.DATA_DIR / name).st_size
            except OSError:
                pass
        per_host = db.query(
            # One row per host: the count of its photo files and the count of
            # its submissions, derived from the schema found above. Counts and
            # numeric ids only; no guest columns in the output.
            "<per-host count query you derive from the schema>"
        )
        log.info(
            "storage_report total_bytes=%d free_bytes=%d db_bytes=%d photos_bytes=%d hosts=%s",
            usage.f_blocks * usage.f_frsize,
            usage.f_bavail * usage.f_frsize,
            db_bytes,
            _tree_bytes(config.DATA_DIR / "passport_photos"),
            json.dumps([dict(row) for row in per_host], separators=(",", ":")),
        )

Register it next to the other add_job calls and add the level entry:

        "storage_report": "warning",

        _scheduler.add_job(
            _job_storage_report, "cron", hour=2, minute=41,
            id="storage_report", max_instances=1, coalesce=True,
        )

If photos are not separable per host on disk, hosts= carries counts only and photos stay aggregate — say so in the report; do not invent per-host bytes.

Step 5 — docs/privacy/ROPA.md: read the table format:

    grep -n "^|" docs/privacy/ROPA.md 2>&1 | head -30

Add one row in that format: processor Grafana Labs (Grafana Cloud, EU region); purpose: operational logs and metrics; data: pseudonymous numeric ids and byte counts, no guest content.

Step 6 — tests: find the access-line assertions:

    grep -rn "ubyhost.access\|db_ms=" App/tests 2>&1 | head -50

Update the assertions to the new format (host=%d present). If none exists, add one minimal test in the style of the neighbouring test files: an anonymous request logs host=0, and the route stays a template. Then run only the test-map rows for the changed files:

    grep -n "main\|scheduler\|retention" docs/context/test-map.md 2>&1 | head -30

## 5. Do not touch

deploy/ (compose, .env*, caddy/), Dockerfile, docs other than ROPA.md, .github/workflows. No new dependency. Never push, merge or deploy.

## 6. Commands

    cd App && .venv/bin/python -m pytest tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30

→ passes (hard rule 2 gate).

    cd App && .venv/bin/python -m pytest <the test-map rows for main/scheduler, and the new or updated access-line test> -q --tb=short -x 2>&1 | tail -30

→ passes.

    python3 scripts/context_lint.py 2>&1 | tail -30

→ passes.

## 7. Acceptance

- [ ] access line format: method, route template, status, ms, q, db_ms, lock_ms, host — non-zero for a signed-in host, 0 otherwise, and no other identifier
- [ ] _log_access cannot raise (helper wrapped; anonymous request covered by a test)
- [ ] storage_report registered at 02:41 UTC and emits one line: total/free/db/photos bytes + hosts JSON of numeric ids and counts
- [ ] retention.py line and ROPA row added in each file's own format
- [ ] git diff --stat lists only §3 files

## 8. Stop and ask

Standard template items, plus: no single-call session-to-host helper exists in auth.py; the schema does not allow a per-host count aggregation; retention.py or ROPA.md format is unclear.

## 9. Report

Write docs/tasks/0426-report.md (600 tokens at most), Status: review, per the template.

## Risk list (for the reviewer)

App/app/main.py (the privacy-relevant one-line change), App/app/scheduler.py, docs/privacy/ROPA.md, App/app/retention.py.

## Owner steps

1. Read the main.py diff: you are approving a deliberate, decided weakening of the OPS-3 "no identifiers" stance — numeric host id only.
2. Merge on green, deploy, then verify in Grafana → Explore → Loki: {container="ubyhost"} |= "method=" | logfmt returns lines, and host is 0 or a host id.
3. The next morning after 02:41 UTC, {container="worker"} |= "storage_report" shows the storage line.
4. Check which retention the Grafana Cloud free tier applies to logs today and note it in docs/OBSERVABILITY.md if it differs from what that file says.
