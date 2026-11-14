# 1424: Go invoice pages: mark paid, cancel and the public download link

Status: todo
Depends on: 1423 (merged or on this branch) | Base commit: the working branch head (no fixed commit) | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch: never create a branch, never push, never open a PR. Commit `1424 step k` after each step that changes a file. The owner opens one pull request for all briefs.

## 1. Objective

Add three routes to the Go invoice package, still switched off: `POST /invoices/{id}/paid`, `POST /invoices/{id}/cancel` and the public `GET /invoice/d/{token}` that the e-mailed link opens (signed, 30 days, 30 requests an hour per visitor).

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 no new personal-data field and no new outbound request; 3 fixtures are made up (`@example.test`, no real names); 4 no new dependency (stdlib, pgx and packages already in go.mod); 5 plain PostgreSQL SQL, no schema change; 7 and 10 (screenshots, UX gate) do not apply yet: the pages are not served, no path is in `UBYHOST_GO_PATHS`, and the UX gate is the owner step at the switch (brief 1427, Owner steps).

**All code is pre-written, compiled and tested** by the brief writer in a scratch worktree, in brief order 1420 to 1427. Sidecars live under `docs/tasks/1424-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

| sha256 | file (repo path; sidecar = `docs/tasks/1424-files/<path>.txt`) |
|---|---|
| `bbf7fac011a8b4ef3fcf81f14baabac8d61b3d4c2e34600b0c07d3847b99a6a4` | `go/internal/web/invoices/actions.go` |
| `6812121e9aa5d784441e4b511da01a768fe79c0096fba2d0db6258a744fdf4e8` | `go/internal/web/invoices/public.go` |
| `c016e6416160389889c1d61381360910d4cd57e0f4d7cadfecf6dfa91c51d79c` | `go/internal/web/invoices/actions_test.go` |

**Parity (Python -> Go):**

| Route | Python | Go |
|---|---|---|
| POST /invoices/{id}/paid | invoice_mark_paid, routes/invoices.py 930-940 | `markPaid` in actions.go |
| POST /invoices/{id}/cancel | invoice_cancel 1004-1027 (calls invoices.cancel) | `cancel` in actions.go, `cancelInvoice` (brief 1422) |
| GET /invoice/d/{token} | invoice_download 1030-1049; invoice_links.py (`download_token`, `read_download_token`); rate_limit.py `blocked`/`record`/`client_key` | `publicDownload`, `readDownloadToken`, `downloadTokenFor`, `throttled`, `peer` in public.go |

**Behaviours the tests pin:** mark paid sets `marked_paid_at` to the UTC time, writes the audit line `invoice_marked_paid id=<id>` (actor = username, owner = workspace) and goes back to `/invoices/<id>` with the `invoice.marked_paid_flash` message; another host's invoice or none is the redirect to `/invoices` with the error flash and changes nothing; a POST without a valid CSRF token never acts (checked before the id); cancel passes the trimmed reason and the optional correction date to `invoices.cancel`; a refusal goes back to the *same* invoice with a plain error text (`invoice.err.reason_required` for a short reason, `invoice.err.not_cancellable` for every other refusal, and these are translated texts, not flash keys), success goes to the *new* storno or ODD with `invoice.cancelled_flash`.

**The public link:** the token is `URLSafeTimedSerializer(secret_key, salt="ubyhost-invoice-download")` of `{"i": id, "h": first 16 characters of the stored PDF hash}`, valid 30 days; `go/internal/secure` already reproduces itsdangerous (a Python-made token reads in Go and the reverse: the salt, key order and payload are the Python ones). A bad, expired, stale (hash changed) or unknown token is a 404 with the text `Not found`; the rate limit is `rate_limit_event` scope `invoice_download`, key `<visitor ip>:invoice_download`, 30 events an hour, 429 `Too many requests`; every attempt counts, a bad token too; the visitor IP is `CF-Connecting-IP` (Caddy overwrites it), else the peer address. Headers: `Content-Disposition: attachment`, `Cache-Control: no-store`, `X-Robots-Tag: noindex`; the body is the stored PDF. Starlette's plain `Response("...")` sets no content type; neither does Go here.

No new outbound request. The route needs no login: a guest has no account.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/actions.go` | create | mark paid and cancel |
| `go/internal/web/invoices/public.go` | create | token, rate limit and the public download |
| `go/internal/web/invoices/actions_test.go` | create | mark paid, cancel, public link, rate limit |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/invoices/pages_detail.go go/internal/web/invoices/pdf_download.go | tail -3` lists both; `ls go/internal/web/invoices/actions.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def invoice_mark_paid' App/app/routes/invoices.py` and `grep -cF 'def read_download_token(' App/app/invoice_links.py` each print 1 or more; `grep -cF 'func (s *TimedSerializer) Loads(' go/internal/secure/signer.go` prints 1 or more; `find docs/tasks/1424-files -name '*.txt' | wc -l` prints `3`.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1424-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")"; cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/invoices/actions.go go/internal/web/invoices/public.go go/internal/web/invoices/actions_test.go | tail -30
   ```

   All 3 hashes must equal §2. Commit "1424 step 1".

2. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip to step 3. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1420 && chown postgres /var/tmp/pg1420 && su postgres -c 'cd /tmp && /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1420/data -A trust -U postgres >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1420/data -o "-p 55432 -k /var/tmp/pg1420" -l /var/tmp/pg1420/log start' 2>&1 | tail -3
   ```

   Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in step 3. A server on that port already (another brief's): use it. No PostgreSQL 16 binaries at that path: write "CI only (no PostgreSQL)" in the report and run step 3 without the variable; the database tests then SKIP, which is expected and not a pass.

3. Build and test (repo root, one call per line; each ends with `2>&1 | tail -30`):

   ```bash
   cd go && gofmt -l internal/web/invoices cmd/ubyhost-web 2>&1 | tail -30
   cd go && go build ./... 2>&1 | tail -30
   cd go && go vet ./internal/web/invoices/... ./cmd/... 2>&1 | tail -30
   cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: the first three print nothing; the last prints `ok  \tgithub.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices\t<time>` and `ok  \t...go/cmd/ubyhost-web\t<time>`. A `FAIL`, a `[build failed]` or a vet line: read the last 30 lines once, then STOP (§8).

4. Write the report (§9) and commit "1424 step 3".

## 5. Do not touch

Everything outside §3. In particular: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/internal/pdf/`, `go/internal/billingjob/`, `go/internal/mail/`, `App/tests/conftest.py`, every Python file under `App/app/`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`, `docs/ENVIRONMENT.md`. Never set `UBYHOST_GO_PATHS`, edit Caddy or compose, push, merge or deploy. Never edit a copied file to make a test pass: a failing sidecar test is a STOP (§8). Hard rules 2, 3, 4, 5 as in §2.

## 6. Commands

Step 3 only, plus from the repo root `python3 scripts/context_lint.py 2>&1 | tail -30` (prints `context lint: OK`). Never the full suite, never `pytest tests`.

## 7. Acceptance

- [ ] The 3 sha256 values match §2.
- [ ] `gofmt -l` prints nothing; `go build ./...` and `go vet` print nothing.
- [ ] `go test` prints `ok` for `internal/web/invoices` and `cmd/ubyhost-web`; with PostgreSQL there is no `--- SKIP` line in `go test -v` (without it the report says "CI only").
- [ ] `cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 -v -run 'TestMarkPaid|TestCancelAction|TestPublic' ./internal/web/invoices/ 2>&1 | grep -c '^--- PASS'` prints 4.
- [ ] `git log --oneline --grep='^1424 step' | tail -5` shows the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1424 step') | tail -30` lists only §3 paths.
- [ ] Nothing pushed, no branch created.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or a check in step 0 is not as written;
- a sha256 in step 1 does not match;
- `gofmt -l` prints a file, `go build` or `go vet` prints anything, or a test fails twice (read the last 30 lines once; never edit a copied file);
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1424-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`public.go`: this is the only route in the thread without a login. `readDownloadToken` (signature, 30-day age, hash prefix, id lookup), `publicDownload` (rate limit before the token check, the 404 and 429 answers, the three headers), `peer` (which header names the visitor). `actions.go`: `loadInvoice` owner scope before the write; `cancel` maps the refusals exactly as the Python (which message, which redirect). Audit lines carry ids and the reason text only.

## Owner steps

None: nothing is switched on. The pages stay dormant until the owner adds paths to `UBYHOST_GO_PATHS` (listed in brief 1427, Owner steps).
