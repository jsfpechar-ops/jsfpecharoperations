# 1330: Go stay fee actions and CSV

Status: todo
Depends on: none | Base commit: a83df54 | Branch: claude/1330-go-stay-fees
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Port eight host routes of `App/app/routes/stay_fees.py` to Go in a new package `go/internal/web/stayfees`, registered in the Go web server but switched off: Caddy sends a path to Go only when `UBYHOST_GO_PATHS` names it, and this brief changes no env, Caddy file or doc. A golden file written by the real Python routes proves the Go handlers give the same status, redirect, flash text, CSV and database rows.

## 2. Context

All code is finished and dry-run. It waits in `/tmp/claude-0/brief1330/` under the same relative paths as in the repo. You copy each file into place, check its sha256, run the tests and commit. You write no code. If `/tmp/claude-0/brief1330/` is missing or a sha256 differs: STOP (§8).

Routes (Python function in `App/app/routes/stay_fees.py` -> Go handler in `handlers.go`):

| Route | Python | Go |
|---|---|---|
| POST /stay-fees/{apartment_id}/adjustment/{adjustment_id}/undo | stay_fee_adjustment_undo | UndoHandler |
| POST /stay-fees/guest-decision | stay_fee_guest_decision | GuestDecisionHandler |
| POST /stay-fees/{apartment_id}/scope-ruling | stay_fee_scope_ruling | ScopeRulingHandler |
| POST /stay-fees/{apartment_id}/copy-setup | stay_fee_copy_setup | CopySetupHandler |
| POST /stay-fees/{apartment_id}/paid | stay_fee_mark_paid | PaidHandler |
| POST /stay-fees/{apartment_id}/filings/{filing_id}/sent | stay_fee_mark_filing_sent | FilingSentHandler |
| POST /stay-fees/{apartment_id}/filings/{filing_id}/paid | stay_fee_mark_filing_paid | FilingPaidHandler |
| GET /stay-fees/{apartment_id}/csv | stay_fee_csv_download | CSVHandler |

Out of scope (stay on Python, not ported): adjustment add, finalize, confirm-ready, guest-pay-preview, the GET HTML pages, PDF, pdfs.zip.

How parity is kept:

- Order of checks as in Python: CSRF (`hostweb.CSRF`, = `security.protect_host_post`, POST only), then login (`hostweb.Login`, = `auth.require_login`), then the route body line by line. Redirects and flashes through `hostweb.Back` with the same flash keys; texts come from the package's own `i18n.json` (en, cs, vi), written from `host_i18n.STRINGS` by the golden script.
- Ownership as `App/app/access.py`: apartment by `owner_user_id` = workspace id; guest and reservation through the apartment owner join. `identity_visible` for the CSV (admin, or not inside another workspace).
- Audit rows: same action and detail strings; actor = username, `actor_user_id` = account, `impersonator_user_id` = account while impersonating, `owner_user_id` = workspace (as `db.audit`). Timestamps in `db.utcnow` format `YYYY-MM-DDTHH:MM:SS+00:00`.
- `guest.fee_host_reason` is written encrypted to `fee_host_reason_enc` and the plaintext column is set NULL (as `db._write_values`). The CSV body is `csv_enc` decrypted with `secure.LoadDataKeys` (as `db.decrypt_blob`).
- Small pure helpers (`parse_month`, `overlap_keys`, `is_active`, `_fold_place`, `fee_copy_source`, `fee_return_path`, `safe_local_path`, constants) are unexported copies in `helpers.go`, each with the comment "copy of App/app/<file>.py <func>; replace with go/internal/stayfee when it lands". Do not create `go/internal/stayfee/`: another thread owns it.
- `stayfees.Routes` builds without touching the pool (the registry and `TestRoutesNeedNoPool` pass nil). The register file wraps each route with `m.wrap`; it registers no bare "GET /".

Golden test: `App/scripts/stay_fee_actions_golden.py` seeds a throwaway SQLite, runs 88 cases through the Python app (frozen clock, CSRF dependency off, `acceptance.pending` off), and writes `testdata/actions_golden.json` (status, Location, CSV headers and body, every changed row, new audit rows) and `i18n.json`. `actions_test.go` seeds Postgres (`UBYHOST_TEST_DATABASE_URL`, skips when unset) from the same file, sends a valid CSRF token, replays every case and compares. `App/tests/test_go_stay_fee_actions_golden.py` (marked `sqlite_only`) fails when either JSON file is stale.

Deviations from Python (recorded in the code and in the PR):

1. `POST /stay-fees/{id}/paid` for a property that is not the host's (or does not exist): Python crashes with 500 (`apartment["id"]` on None). Go redirects to `/stay-fees` with `flash.error.no_such_apartment`, like the sibling routes. The Go test expects that for the two golden cases named `(python 500)`.
2. Month and id digits: Python `str.isdigit` also accepts non-ASCII digits (`２０２６-10` parses as a month; such an id crashes `int()` or the query with a 500). Go accepts only ASCII digits: a non-ASCII month falls back to the default month, a non-ASCII or overflowing id means "not found".
3. A non-numeric path id when signed out: FastAPI answers 422 before login; Go redirects to `/login` first (the 422 comes once signed in). Signed-in behaviour is the same.
4. The identity-hidden CSV branch cannot be reached by a real session today (only admins enter another workspace, and admins always see identity data). Both the golden script and the Go test force it with a stub to compare the redirect.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/web/stayfees/helpers.go | new | pure helper copies and constants |
| go/internal/web/stayfees/handlers.go | new | the eight handlers and `Routes` |
| go/internal/web/stayfees/i18n.json | new | flash texts (generated) |
| go/internal/web/stayfees/actions_test.go | new | golden replay on Postgres, CSRF test, nil-pool test |
| go/internal/web/stayfees/helpers_test.go | new | helper cases printed by the Python functions |
| go/internal/web/stayfees/testdata/actions_golden.json | new | golden file (generated) |
| go/cmd/ubyhost-web/register_web_stayfees.go | new | `init()` -> `registerRoutes`, `m.wrap` per route |
| App/scripts/stay_fee_actions_golden.py | new | writes the two generated JSON files |
| App/tests/test_go_stay_fee_actions_golden.py | new | fails when the JSON files are stale |
| docs/tasks/1330-report.md | new | your report |

No other file may change. This brief is already committed.

## 4. Steps

Run every command from the repo root unless it says `cd`.

1. Check the source files (the hash list is the one in §7):

```bash
cd /tmp/claude-0/brief1330 && sha256sum -c 2>&1 <<'EOF' | tail -30
182de0abb1e6d2922a84de0dd680681b5acc3a972e5ec5bad8ca756af4e804cb  go/internal/web/stayfees/helpers.go
a4cd7993732e3726f19899b547811149fa8b992cc93dd0299c77be7df3a33ac7  go/internal/web/stayfees/handlers.go
0c4912becafd50ff5df7ce853f6759dafc2af0480fb4910cfda85658853ab7e4  go/internal/web/stayfees/i18n.json
731646250ba74e2865ccf1e2d5e68a425e8a6ca432f6cbbe7412e4ad9f048166  go/internal/web/stayfees/actions_test.go
4d1ed4293d49cccf0e5df1781d2534e8d8e3fab286dc9ded431e3b88dd1593ab  go/internal/web/stayfees/helpers_test.go
95ed73c05bd7cd17b4c0b923f219f51e5e64dd9db4102fff52a2d443066e84ca  go/internal/web/stayfees/testdata/actions_golden.json
5ce6e5b2478720464276413259e8bd5e1ec678b73b277fefbce3c52380738672  go/cmd/ubyhost-web/register_web_stayfees.go
01301764e588fe58491b4b44ae62f2c98ea520fa65bcc848563db634717382ce  App/scripts/stay_fee_actions_golden.py
bc7a9d332fb6021b7f62ef20b40365b7f4e701ecb182aa949727181447d8a4b5  App/tests/test_go_stay_fee_actions_golden.py
EOF
```

   Every line must end `OK`. Otherwise STOP.
2. Copy the Go files into place:
   `mkdir -p go/internal/web/stayfees/testdata && for f in go/internal/web/stayfees/helpers.go go/internal/web/stayfees/handlers.go go/internal/web/stayfees/i18n.json go/internal/web/stayfees/actions_test.go go/internal/web/stayfees/helpers_test.go go/internal/web/stayfees/testdata/actions_golden.json go/cmd/ubyhost-web/register_web_stayfees.go; do cp /tmp/claude-0/brief1330/$f $f; done && git status --short 2>&1 | tail -30`
   Expect only `?? go/cmd/ubyhost-web/register_web_stayfees.go` and `?? go/internal/web/`. Run the Go commands of §6. Commit: `git add go/internal/web/stayfees go/cmd/ubyhost-web/register_web_stayfees.go && git commit -m "1330 step 2: Go stay fee actions and CSV" 2>&1 | tail -5`
3. Copy the Python files into place:
   `for f in App/scripts/stay_fee_actions_golden.py App/tests/test_go_stay_fee_actions_golden.py; do cp /tmp/claude-0/brief1330/$f $f; done && git status --short 2>&1 | tail -30`
   Expect only those two files as `??`. Run the Python commands of §6. Commit: `git add App/scripts/stay_fee_actions_golden.py App/tests/test_go_stay_fee_actions_golden.py && git commit -m "1330 step 3: stay fee actions golden script and staleness test" 2>&1 | tail -5`
4. Check the repo copies: run the step 1 block again without the `cd /tmp/claude-0/brief1330 &&` (from the repo root); every line must end `OK`. Then `python3 scripts/context_lint.py 2>&1 | tail -3` ends with `context lint: OK`.
5. Write the report (§9) and commit it as `1330 step 5: report`. Do not push: the orchestrator pushes and opens the draft PR. Put in the report, for the PR body: the four deviations of §2, and "No new outbound request. No new personal-data field. Routes are registered but off: Caddy routes only UBYHOST_GO_PATHS to Go."

## 5. Do not touch

Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/secure/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/cmd/ubyhost-web/registry.go`, `go/cmd/ubyhost-web/register_web.go`, `go/go.mod`, `go/go.sum`, `App/app/` (all of it), `App/tests/conftest.py`, every env file, Caddy file and doc. Never create `go/internal/stayfee/`. Never edit a copied file: if a test fails, STOP (§8). Hard rules 2 (no new outbound request, no new personal-data field), 3 (fixture values are synthetic), 5, 8.

## 6. Commands

Go needs Postgres. Start one if none is running (pg_ctl refuses root, so run it as `postgres`):

```bash
mkdir -p /var/tmp/pg1330 && chown postgres /var/tmp/pg1330 && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1330/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1330/data -o '-p 54330 -k /var/tmp/pg1330' -l /var/tmp/pg1330/log start" 2>&1 | tail -3
```

If `/var/tmp/pg1330/data` already exists, only run the `pg_ctl ... start` part (an "already running" message is fine).

Go (step 2):

- `cd go && gofmt -l internal/web/stayfees cmd/ubyhost-web && go vet ./internal/web/stayfees/ ./cmd/ubyhost-web/ 2>&1 | tail -30` -> no output.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54330/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)|SKIP' | tail -30` -> every line `--- PASS`, two `ok` lines, no `SKIP` and no `FAIL`. `TestActionsMatchPython` and `TestCSRFRequired` must say PASS (they skip without the URL; a skip is a failure here).

Python (step 3; needs `App/.venv`; if missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

- `cd App && .venv/bin/python scripts/stay_fee_actions_golden.py 2>&1 | tail -2 && cd .. && git status --short 2>&1 | tail -30` -> two `wrote ...` lines (logged tracebacks for `/stay-fees/20/paid` and `/stay-fees/999/paid` before them are expected: deviation 1), then no output from `git status` (the regenerated JSON files are byte-identical).
- `cd App && .venv/bin/python -m pytest tests/test_go_stay_fee_actions_golden.py -q --tb=short -x 2>&1 | tail -30` -> `1 passed`.

## 7. Acceptance

- [ ] sha256 of each file, in `/tmp/claude-0/brief1330/` and in the repo after step 4:

```
182de0abb1e6d2922a84de0dd680681b5acc3a972e5ec5bad8ca756af4e804cb  go/internal/web/stayfees/helpers.go
a4cd7993732e3726f19899b547811149fa8b992cc93dd0299c77be7df3a33ac7  go/internal/web/stayfees/handlers.go
0c4912becafd50ff5df7ce853f6759dafc2af0480fb4910cfda85658853ab7e4  go/internal/web/stayfees/i18n.json
731646250ba74e2865ccf1e2d5e68a425e8a6ca432f6cbbe7412e4ad9f048166  go/internal/web/stayfees/actions_test.go
4d1ed4293d49cccf0e5df1781d2534e8d8e3fab286dc9ded431e3b88dd1593ab  go/internal/web/stayfees/helpers_test.go
95ed73c05bd7cd17b4c0b923f219f51e5e64dd9db4102fff52a2d443066e84ca  go/internal/web/stayfees/testdata/actions_golden.json
5ce6e5b2478720464276413259e8bd5e1ec678b73b277fefbce3c52380738672  go/cmd/ubyhost-web/register_web_stayfees.go
01301764e588fe58491b4b44ae62f2c98ea520fa65bcc848563db634717382ce  App/scripts/stay_fee_actions_golden.py
bc7a9d332fb6021b7f62ef20b40365b7f4e701ecb182aa949727181447d8a4b5  App/tests/test_go_stay_fee_actions_golden.py
```

- [ ] gofmt and go vet print nothing.
- [ ] Go tests: all PASS, with `TestActionsMatchPython` and `TestCSRFRequired` run (not skipped).
- [ ] Golden script leaves `git status` clean; the pytest file passes.
- [ ] `git diff --stat a83df54..HEAD` lists only §3 paths and this brief.
- [ ] `python3 scripts/context_lint.py` ends `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if:

- `/tmp/claude-0/brief1330/` is missing or a sha256 differs;
- a test fails twice, or a DB test skips;
- the golden script changes a JSON file;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1330-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat a83df54..HEAD`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- go/internal/web/stayfees/handlers.go (ownership checks, audit rows, encrypted reason write, CSV decrypt)
- go/internal/web/stayfees/helpers.go (`safeLocalPath` / `feeReturnPath`: open-redirect guard)
- go/cmd/ubyhost-web/register_web_stayfees.go (patterns, `m.wrap`, no "GET /")
- App/scripts/stay_fee_actions_golden.py (cases cover success, wrong owner, bad input, idempotent sent/paid, sealed adjustment, exempt reasons incl. local_rule reference length, copy-setup refusals, CSV identity-hidden / not-saved / future-month redirect)

## Owner steps

1. Wait for CI to go green on the draft PR, then merge it with `scripts/merge-pr-on-green.sh`. Nothing is switched on by the merge.
2. Switching these paths to Go is a later, separate step (add them to `UBYHOST_GO_PATHS`); not part of this brief.
