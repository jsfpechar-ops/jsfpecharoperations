# 1210: Go job kind `retention`, counting half (dry run, audit, setting, notices)

Status: review
Depends on: none (1200 register split merged) | Base commit: a83df54 | Branch: claude/1210-go-retention (work on the current branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (deletion, guest data) | Next: [1211](1211-go-retention-apply.md) adds the deleting half

## 1. Objective

Port `App/app/retention.py` `run()` to Go as job kind `retention` (package `go/internal/retention`), counting half: every step's dry-run count, the per-step `retention_delete` audit line, the `retention_run` audit line, the `retention_last_run` setting and the monthly `retention_due` alerts, byte-identical to Python on PostgreSQL. Go never deletes in this brief: with both apply switches on it fails closed. The kind stays on Python until the owner lists it in `UBYHOST_GO_JOB_KINDS` (not in this PR), so the owner can run Go in dry-run for 3 nights and compare (plan go-full-move J2).

## 2. Context

Rules: hard rule 2 (privacy; never log personal data: counts and ids only), 3 (fixture is synthetic, `example.test` addresses, `192.0.2.x` IPs), 4 (no dependency: only pgx, already in go.mod), 8 (never push to `main`). Plan `docs/plans/go-full-move.md` §2, §3 J2, §7.

Fixed decisions (orchestrator, do not change):

- **Switches.** `Config.DryRun` is false only when `UBYHOST_RETENTION_AUTOPURGE` (Python's switch, values `1`/`true`/`yes`, case-sensitive like `config.py`) **and** the new `UBYHOST_GO_RETENTION_APPLY` (same values) are both on. Default: dry run. In this brief `Run` returns `errApplyNotPorted` before any step when `DryRun` is false (nothing written); 1211 removes that guard.
- **Dry-run audit lines** are `db.audit_retention`'s exact JSON (`sort_keys=True`): `{"class": ..., "count": n, "cutoff": ..., "dry_run": true, "owner_user_id": null}`, actor `system`, action `retention_delete`. `retention_run` detail and `retention_last_run` value are `json.dumps(summary)` in insertion order (`dry_run`, `owner_user_id`, `counts` in STEPS order, then `at` for the setting). A failed step has no audit line and no key in `counts`; the first step error is returned after the summary, setting and notices, as Python re-raises it.
- **Registration** only through `go/cmd/ubyhost-web/register_job_retention.go` (`registerJob("retention", 24*60, retentionHandler)`; the factory does not touch the pool). `retention` is already in `jobNames` in `go/internal/jobs/queue.go`; level stays `warning` (Python `_JOB_LEVELS`). On a failed run the handler calls `jobs.RaiseFailed` at once (Python `_job_failed`) and returns the error.
- **Time.** `Run(ctx, pool, cfg, today, now, owner)` takes both explicitly. The handler passes `now.Local()` as today (Python `date.today()` is server-local; no container sets `TZ`, so UTC) and `now`. All "now" strings are formatted as Python formats them: `pyISO` (`db.utcnow`, `_days_ago_iso`, `login_link._iso`, `push._stamp`: seconds, `+00:00`) and `pyISOMicro` (`passkeys._iso` keeps microseconds). `rate_limit_event.at` is a float compared with `time.time()` minus the window.
- **PostgreSQL only.** Every date column the job compares is `text COLLATE "C"` in `App/migrations_pg/00001_baseline.sql`, as in Python's PG run; `db.sqlite_date_expr(x)` is the SQL function `ubyhost_sqlite_date(x)` from that baseline, used verbatim. `rate_limit_event.at` is `double precision`.
- **Parity proof.** `App/scripts/retention_golden.py` runs the real Python `run()` against `testdata/fixture.sql` on a throwaway PostgreSQL database at a frozen instant (2026-01-20T03:00:00.250000Z) for a global and an owner-1 dry run and records counts plus every touched table; `golden_test.go` replays both on Go and compares row by row. `App/tests/test_go_retention_parity.py` regenerates the golden in CI's PostgreSQL row and fails if Python changed without a new golden.

Python `App/app/retention.py` (read-only), behaviour mirrored: `STEPS` order `guests, invoices, platform_invoices, claim_emails, reservation_contacts, submitter_ips, empty_reservations, stay_fee_records, audit_rows, alerts, rate_limit_events, havel_gap, login_tokens, webauthn_challenges, door_code_pins, cleaning, push, guide_imports, guest_chats, legal_acceptance, workspaces`; `run()` writes the notices only on a global run; `_raise_due_notices` uses `housebook.due_guest_counts` and `alerts.raise_alert` with key `retention_due:<owner>:<YYYY-MM>` and params `{"count": n, "days": d}`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/retention/retention.go` | create | Config, Run, cutoffs, Python-format JSON/time helpers, audit, setting, due notices |
| `go/internal/retention/steps.go` | create | the 21 steps, counting half |
| `go/internal/retention/retention_test.go` | create | switches, step order, formats (no DB) |
| `go/internal/retention/golden_test.go` | create | replays golden.json on PostgreSQL; apply refused |
| `go/internal/retention/testdata/fixture.sql` | create | synthetic rows, due and not due, two owners |
| `go/internal/retention/testdata/golden.json` | create (generated) | written by the golden script |
| `go/cmd/ubyhost-web/register_job_retention.go` | create | `registerJob("retention", 24*60, ...)` |
| `App/scripts/retention_golden.py` | create | writes / checks golden.json from Python |
| `App/tests/test_go_retention_parity.py` | create | Python side: golden up to date (PostgreSQL only) |
| `docs/tasks/1210-report.md` | create | the report |
| `docs/tasks/1210-appendix/files.md` | delete (report step) | the file contents, committed with the brief |

No other file may change. Every file's content is in `docs/tasks/1210-appendix/files.md` (part of this brief, outside the lint cap); you copy it with the extractor, never by typing. The report step deletes that folder.

## 4. Steps

From the repo root. Do not read `docs/tasks/1210-appendix/files.md`: the extractor copies every file from it.

### Step 0: anchors and the extractor

```bash
git status --short | tail -5; ls go/internal/retention 2>&1 | tail -1; grep -c '"retention":' go/internal/jobs/queue.go; grep -c 'func registerJob(kind string, minutes int, h func(\*pgxpool.Pool) jobs.Handler)' go/cmd/ubyhost-web/registry.go
```

Expected: no `git status` line (the orchestrator committed this brief, 1211 and both `-appendix` folders), `ls: cannot access ...`, `1`, `1`. Anything else: STOP (§8).

Write the extractor (outside the repo; rewrite it if a new session finds it missing):

```bash
cat > /tmp/x1210.py <<'PY'
import hashlib, os, re, sys
brief = open(sys.argv[1], encoding="utf-8").read()
for path in sys.argv[2:]:
    found = re.findall(r"^<!-- file: " + re.escape(path) + r" -->\n````[a-z]*\n(.*?)\n````$", brief, re.S | re.M)
    if len(found) != 1:
        sys.exit(f"STOP: {len(found)} blocks for {path}")
    data = (found[0] + "\n").encode("utf-8")
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as out:
        out.write(data)
    print(hashlib.sha256(data).hexdigest() + "  " + path)
PY
python3 -c "import ast;ast.parse(open('/tmp/x1210.py').read());print('extractor ok')"
```

Expected: `extractor ok`.

### Step 1: the package

```bash
python3 /tmp/x1210.py docs/tasks/1210-appendix/files.md go/internal/retention/retention.go go/internal/retention/steps.go 2>&1 | tail -3
```

Expected exactly:

```text
550b821aca1756171fb4f04f54f90077460e39df523cb9b0309f9f0623b15e63  go/internal/retention/retention.go
c82210a6a1e6aa6cd39ce37280e2ce2bccb9bf0e336ac5fe2a4fa404a1e6bce5  go/internal/retention/steps.go
```

Commit `1210 step 1: retention package, counting half`.

### Step 2: unit tests

```bash
python3 /tmp/x1210.py docs/tasks/1210-appendix/files.md go/internal/retention/retention_test.go 2>&1 | tail -3; cd go && test -z "$(gofmt -l ./internal/retention)" && go vet ./internal/retention/ && go test ./internal/retention/ -count=1 2>&1 | tail -5
```

Expected: `2a4cd0618ded4e5d75efa084ff48f0f842d348b429f09e101b63320e19a97923  go/internal/retention/retention_test.go`, then `ok  	.../go/internal/retention`. Commit `1210 step 2: retention unit tests`.

### Step 3: register the job kind

```bash
python3 /tmp/x1210.py docs/tasks/1210-appendix/files.md go/cmd/ubyhost-web/register_job_retention.go 2>&1 | tail -3; cd go && test -z "$(gofmt -l ./cmd/ubyhost-web)" && go vet ./cmd/ubyhost-web/ && go test ./cmd/ubyhost-web/ -count=1 2>&1 | tail -5
```

Expected: `1da30a74bab1b16dbf4d19da915d7a3095f0b86b50bf9d4b2bf58b6507931a9b  go/cmd/ubyhost-web/register_job_retention.go`, then `ok`. Commit `1210 step 3: register job kind retention`.

### Step 4: fixture and golden test

```bash
python3 /tmp/x1210.py docs/tasks/1210-appendix/files.md go/internal/retention/testdata/fixture.sql go/internal/retention/golden_test.go 2>&1 | tail -3
```

Expected exactly:

```text
dc01acaf3653609c573f195dd5e57f784fca6754a38da21f105d42d7eb2f2603  go/internal/retention/testdata/fixture.sql
2dc07e83e11891681130d3a4363de773a0789bcdd98abd5604d462266b192989  go/internal/retention/golden_test.go
```

Commit `1210 step 4: retention fixture and golden test`.

### Step 5: Python golden script and parity test

```bash
python3 /tmp/x1210.py docs/tasks/1210-appendix/files.md App/scripts/retention_golden.py App/tests/test_go_retention_parity.py 2>&1 | tail -3
```

Expected exactly:

```text
25966764bf1848ae6e53415a65dcce2ed1e2e9c9925be4b83cb158f8ec97812c  App/scripts/retention_golden.py
fe3059ed30dcc4faf1fafcf40dd435d268bbadd08bdc9b9b4f537d2fc8239f03  App/tests/test_go_retention_parity.py
```

Commit `1210 step 5: retention golden script and parity test`.

### Step 6: generate golden.json on a local PostgreSQL

Start a throwaway server (PostgreSQL 16 binaries; if `/usr/lib/postgresql/16/bin/initdb` is missing: STOP, §8) and the venv:

```bash
mkdir -p /var/tmp/pg1210 && chown postgres /var/tmp/pg1210 && (test -d /var/tmp/pg1210/data || su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1210/data --no-locale -E UTF8 -A trust" >/dev/null) && su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1210/data -o '-p 5433 -k /var/tmp/pg1210' -l /var/tmp/pg1210/log start" 2>&1 | tail -1; test -x App/.venv/bin/python || (cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3)
```

Expected: `server started` (or `another server might be running`).

```bash
cd App && UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg1210&port=5433' .venv/bin/python scripts/retention_golden.py 2>&1 | tail -3; sha256sum ../go/internal/retention/testdata/golden.json | tail -1
```

Expected: `wrote .../golden.json`, then `6fbf48500afc798657fd7791710288fc470b1fae08a7c953db8a4aa46808785d  ../go/internal/retention/testdata/golden.json`. A different sha256: STOP (§8), do not edit the file. Commit `1210 step 6: retention golden.json`.

## 5. Do not touch

Everything in "READ-ONLY" of the orchestrator's list: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_jobs.go`, `App/tests/conftest.py`, every `App/app/*.py`, `go/internal/mail/`, `go/internal/photosweep/`, `go/go.mod`, `go/go.sum`, `docs/ENVIRONMENT.md`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`. Never set `UBYHOST_GO_JOB_KINDS`, `UBYHOST_RETENTION_AUTOPURGE` or `UBYHOST_GO_RETENTION_APPLY` anywhere: owner steps.

## 6. Commands

Test-map has no Go row; this is the check for the touched packages. With the server from step 6:

```bash
cd go && test -z "$(gofmt -l ./internal/retention ./cmd/ubyhost-web)" && go vet ./internal/retention/ ./cmd/ubyhost-web/ && UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg1210&port=5433' go test ./internal/retention/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)|^    --- ' | tail -30
```

Expected: `--- PASS` for `TestRunMatchesPythonGolden` (subtests `global_dry`, `owner1_dry`), `TestApplyIsRefusedUntil1211`, `TestConfigFromEnvSwitches`, `TestStepsOrderMatchesPython`, `TestFormats`, the existing cmd tests, two `ok` lines, no `SKIP`.

```bash
cd App && UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg1210&port=5433' .venv/bin/python -m pytest tests/test_go_retention_parity.py -q --tb=short -rs 2>&1 | tail -5; .venv/bin/ruff check scripts/retention_golden.py tests/test_go_retention_parity.py 2>&1 | tail -2
```

Expected: `2 passed`, `All checks passed!`. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` ends with `context lint: OK`.

## 7. Acceptance

- [ ] Every extractor sha256 and the golden.json sha256 matched.
- [ ] The §6 Go command: all named tests `--- PASS`, none skipped, two `ok`.
- [ ] The parity pytest: `2 passed`; ruff clean; context lint OK.
- [ ] `git diff --stat a83df54..HEAD | tail -15` lists only the §3 paths plus the briefs 1210 and 1211 and `docs/tasks/1211-appendix/files.md`.
- [ ] `grep -n 'slog\.' go/cmd/ubyhost-web/register_job_retention.go go/internal/retention/*.go | grep -v '_test' | tail -5` shows only the `retention run` counts line and the `job_failed alert not raised` line.
- [ ] Six commits `1210 step 1` to `1210 step 6`; nothing pushed.

## 8. Stop and ask

Stop, and write the report, if: an anchor in step 0 differs; the extractor prints `STOP` or a sha256 differs; `go vet` or a test fails twice (report the error, do not edit pasted code); PostgreSQL 16 is missing or does not start; you reach 25 tool calls or about 50k tokens (report `blocked`, executor.md); a file outside §3 would change, or §5 would be touched; you need push, merge, a PR, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1210-report.md` (600 tokens at most): 1. `git diff --stat a83df54..HEAD | tail -15`; 2. each §6 command with the last 5 lines; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left. Then `git rm -r -q docs/tasks/1210-appendix`. Set `Status: review`. Commit `1210 report`.

## Risk list (for the reviewer)

Read in full: `go/internal/retention/steps.go` (each count query against the Python function named in its comment), `retention.go` (`Run` order and failure handling, `cutoffs`, `summaryJSON`, `auditRetention`, `raiseDueNotices`/`raiseAlert`, the apply guard), `register_job_retention.go` (`now.Local()`, `RaiseFailed` on error, counts-only log), `App/scripts/retention_golden.py` (freezing: `db.datetime`, `retention.datetime`, `retention.time`, `login_link/passkeys/push._now`).

Known parity gaps (accepted; owner to know):

1. Retry: Python finishes the row and runs again tomorrow; Go's queue retries a failed run after 1, 5, 15 min and at the interval cap (5 attempts), so a failing night writes up to 5 sets of audit lines (counts only).
2. One instant: Python reads the clock per call (`_days_ago_iso`, `utcnow` per row, milliseconds apart); Go uses one `now` for the whole run, so every audit row of a run has the same `at`.
3. `retention_due` alerts are raised in owner-id order (Python: database group order); only alert ids differ.
4. Python's owner-scoped run from the Settings button audits with the signed-in host as `owner_user_id`/actor for `db.audit` rows; the Go job only runs globally, in the job context (no current owner), which is what Python's scheduler does.
5. A run with both apply switches on fails closed every night until 1211 merges (alert `job_failed:retention`).

## Owner steps

After merge and the auto-deploy, to run Go's counting for 3 nights. While Go owns the kind and `UBYHOST_GO_RETENTION_APPLY` is unset, nothing is deleted on those nights, even if `UBYHOST_RETENTION_AUTOPURGE=1`:

1. On the server, open `/opt/ubyhost/deploy/lightsail/.env` and add `retention` to both `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS` (comma lists). Do not add `UBYHOST_GO_RETENTION_APPLY`.
2. Deploy:

```bash
cd /opt/ubyhost/deploy/lightsail && ./scripts/deploy.sh
```

3. Each morning for 3 days, compare Go's run with Python's earlier nights:

```bash
cd /opt/ubyhost/deploy/lightsail && docker compose exec -T postgres psql -U ubyhost -d ubyhost -P pager=off -c "SELECT at, actor, left(detail, 300) FROM audit WHERE action = 'retention_run' ORDER BY id DESC LIMIT 6"
```

Expected: the newest rows say `"dry_run": true` with counts close to Python's earlier nights (they change only as rows age in or are deleted).
4. Roll back: remove `retention` from `UBYHOST_GO_JOB_KINDS` only and run step 2 again.

