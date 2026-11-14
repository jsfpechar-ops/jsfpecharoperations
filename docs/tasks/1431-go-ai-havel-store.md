# 1431: Go port of Havel's limits, stats and gap log (rate-limit events, plan multiplier, AI switches)

Status: review
Depends on: 1430 | Base commit: the current head of the working branch | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy-relevant outbound request: the assistant's model calls)

**One big PR mode.** Work on the current branch. After each step that changes a file, commit it as `1431 step k` (k is the step number). Never create a branch, never push, never open a PR. Acceptance checks below use `git log --oneline --grep='^1431 step'` and `git show --stat`, not a fixed base commit.

## 1. Objective

Add the database side of Havel to `go/internal/web/ai`: the per-host message limits (burst, week, month, refusals, support), the daily stats, the redacted gap log, the plan multiplier and the AI feature switch with the test-email list, tested on PostgreSQL. No route yet.

## 2. Context

Rules (AGENTS.md): 2 privacy first (the gap log stores only the redacted question, day-precision, no user and no property, as Python does; no new field, no new table; `App/app/retention.py` already covers `havel_gap`, `havel_stats` and `rate_limit_event`); 4 no new dependency; 5 plain PostgreSQL, the same statements as Python's `db` helpers, `$n` placeholders.

**All code is pre-written, compiled and tested** over 1430. Sidecars: `docs/tasks/1431-files/<repo path>.txt`.

**What this ports** (Python mirror): `App/app/havel.py` 316-381 (`_since_week_start`, `_since_month_start`, `plan_multiplier`, `limit_state`, `record_message`, `record_refusal`, `support_blocked`, `record_stat`) and 571-583 (`record_gap`); `App/app/rate_limit.py` 28-63 (`_prune`, `_count`, `record`, `blocked`); `App/app/billing.py` 112-157 (`entitlements(...).ai_multiplier`: billing off or no account row 1, paused 0, trial 1, Max 5, else 1); `App/app/ai.py` 78-100 (`enabled`, `on_test_list`, `enabled_for`).

**Parity notes:** (1) Windows: Python subtracts aware datetimes of one zone by their wall clock, so the daylight-saving change adds no hour; `HavelSinceWeekStart` and `HavelSinceMonthStart` do the same and the test pins six values written by Python (e.g. Sunday 2026-03-29 12:00 Prague gives 561601 and 2462401). (2) `LimitState` runs refuse, burst (5 in 600 s), week (`UBYHOST_HAVEL_WEEKLY` default 8, times the plan multiplier) and month (`UBYHOST_HAVEL_MONTHLY` default 15) in this order and stops at the first hit; each check deletes its older events first, as `_count` does. A paused account has multiplier 0, so its week check blocks at once. (3) Rate-limit and gap rows use the request's clock (`at`), Python uses `time.time()` and `db.utcnow()`. (4) The gap row's `created_at` is the day at `T00:00:00+00:00`, `lang` cut to 5 characters, `page` stored only when it is a known page id.


## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/havel_store.go` | create | limits, rate-limit events, stats, gap log, plan multiplier, AI switches |
| `go/internal/web/ai/havel_store_test.go` | create | tests: windows, gates, limits, records, stats and gap log on PostgreSQL |
| `go/internal/web/ai/havel_testdb_test.go` | create | throwaway PostgreSQL database for the ai tests |
| `docs/tasks/1431-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1431-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `git log --oneline --grep='^1430 step 1' | wc -l` prints at least `1` (1430 is on this branch); `ls go/internal/web/ai/havel_engine.go` exists; `ls go/internal/web/ai/havel_store.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def limit_state(user_id: int, now: Optional[datetime] = None) -> Optional[str]:' App/app/havel.py` prints `1`; `grep -cF 'def record_gap(lang: str, page: str, kind: str, question: str) -> None:' App/app/havel.py` prints `1`; `find docs/tasks/1431-files -type f | wc -l` prints `3`. Anything else: STOP (§8).

1. Copy the files (one call, repo root). Run exactly:

   ```bash
   mkdir -p go/internal/web/ai && cp docs/tasks/1431-files/go/internal/web/ai/havel_store.go.txt go/internal/web/ai/havel_store.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1431-files/go/internal/web/ai/havel_store_test.go.txt go/internal/web/ai/havel_store_test.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1431-files/go/internal/web/ai/havel_testdb_test.go.txt go/internal/web/ai/havel_testdb_test.go
   ```

   Then check them: `sha256sum go/internal/web/ai/havel_store.go go/internal/web/ai/havel_store_test.go go/internal/web/ai/havel_testdb_test.go | tail -30`. Every hash must equal this table:

| sha256 | file (sidecar = `docs/tasks/1431-files/<path>.txt`) |
|---|---|
| `99764d8b0e020255f119e8c751201f38bd09a509b736400179e0288306940ca9` | `go/internal/web/ai/havel_store.go` |
| `2bbe75ae287e75651e9058ea31b067d8ae44fcd7602234a4966b4a39cdf182b8` | `go/internal/web/ai/havel_store_test.go` |
| `0197a83089563c5a76dad879742b75627d78a468da7e3e25d28fd6199e0685a4` | `go/internal/web/ai/havel_testdb_test.go` |

   Commit "1431 step 1".

2. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip to step 3. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pgai && chown postgres /var/tmp/pgai && su postgres -c '[ -d /var/tmp/pgai/data/base ] || /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pgai/data -A trust >/dev/null; /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data -o "-p 55432 -k /var/tmp/pgai" -l /var/tmp/pgai/log -w start' 2>&1 | tail -3
   ```

   Expected: `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in the later steps (if the server already runs from an earlier brief, `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data status' | tail -1` says `server is running`; use it). If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip this step. No PostgreSQL 16 binaries: write "DB tests not run (CI only)" in the report and run the Go commands without the variable (the DB tests then SKIP; name each skipped test in the report).

3. Go (from `go/`): `test -z "$(gofmt -l ./internal/web/ai)" && go build ./... 2>&1 | tail -30 && go vet ./internal/web/ai/ 2>&1 | tail -30 && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40`. Expected: no output from gofmt, build or vet, then `--- PASS:` for the eleven 1430 tests and TestHavelWindowsAreWallClockSeconds, TestHavelGates, TestHavelLimitsOnPostgres, TestHavelRecordsAndSupportCap, TestHavelStatsAndGapLog and one `ok`. A `--- SKIP` of an OnPostgres test means the URL was not seen. A FAIL: read the last 30 lines, STOP and paste them. Write the report (§9) and commit "1431 step 3".

## 5. Do not touch

`App/app/` and every other Python file (new files under `App/scripts/` and `App/tests/` named in §3 only), `App/migrations_pg/`, `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go` and every other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues, workflow), and every file in `go/internal/web/ai/` that is not named in §3 (the guide-editor thread owns the `guide*.go` files there). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1 to 5, 8 and 9 of AGENTS.md.

## 6. Commands

Step 3 above (Go). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Never `go test ./...`, never the full pytest suite.

## 7. Acceptance

- [ ] The 3 sha256 values match §4 step 1.
- [ ] gofmt, build and vet print nothing; the five new tests PASS (none skipped, or the skip named with its reason) and the 1430 tests still PASS.
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1431 step') | grep '|' | tail -40` lists only §3 paths.
- [ ] Commits "1431 step 1" and "1431 step 3", nothing pushed.

## 8. Stop and ask

As brief 1430 §8 (stop and write the report if an anchor is missing, a sha256 differs, a test fails twice, you reach 25 tool calls or about 50k tokens, a dependency seems needed, a file outside §3 needs a change, §5 would be touched, or a step is unclear). A golden `--check` that prints `stale:` is a STOP: never edit a sidecar, a Python file or a golden to match.

## 9. Report

Write `docs/tasks/1431-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`go/internal/web/ai/havel_store.go`: **`LimitState` and `Blocked`** (the spend and message caps per host; against havel.py 335-349 and rate_limit.py 28-63: order, thresholds, windows, the empty-key fail-closed rule, the plan multiplier); **`HavelAIOn` and `HavelOnTestList`** (the `UBYHOST_AI_FEATURES` switch, the key check per provider and the `UBYHOST_AI_TEST_EMAILS` list; against ai.py 78-100); `Multiplier` (billing.py 112-157); `RecordGap` (what is stored from a host's question: redacted, day-precision, no user, no property). The model spend caps themselves live in `go/internal/anthropic` (read-only, untouched).

## Owner steps

None: nothing is switched on.
