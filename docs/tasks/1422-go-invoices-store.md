# 1422: Go invoice pages: lookups, number allocation, issue and cancel transactions

Status: review
Depends on: 1421 (merged or on this branch) | Base commit: the working branch head (no fixed commit) | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch: never create a branch, never push, never open a PR. Commit `1422 step k` after each step that changes a file. The owner opens one pull request for all briefs.

## 1. Objective

Port the database side of the invoice pages to Go (`store.go`): the owner-scoped lookups, the invoice number and variable symbol allocation, the issue transaction (invoice, items, stored PDF with its hash, in one transaction), the per-stay limit, the storno or corrective (ODD) written by cancel, and the PDF read. Tests run on PostgreSQL with real invoices and real PDFs from `go/internal/pdf`.

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 no new personal-data field and no new outbound request; 3 fixtures are made up (`@example.test`, no real names); 4 no new dependency (stdlib, pgx and packages already in go.mod); 5 plain PostgreSQL SQL, no schema change; 7 and 10 (screenshots, UX gate) do not apply yet: the pages are not served, no path is in `UBYHOST_GO_PATHS`, and the UX gate is the owner step at the switch (brief 1427, Owner steps).

**All code is pre-written, compiled and tested** by the brief writer in a scratch worktree, in brief order 1420 to 1427. Sidecars live under `docs/tasks/1422-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

| sha256 | file (repo path; sidecar = `docs/tasks/1422-files/<path>.txt`) |
|---|---|
| `1f7a24c2e0461f1ad907fad860d2aedbe9918501b56c84f51d7cf92bef60bda2` | `go/internal/web/invoices/store.go` |
| `3ced8dc70307d54b8900e52dba290574b0eabce5ae0851b312f749f841acd04a` | `go/internal/web/invoices/testenv_test.go` |
| `71dfbca629a74c1338ff4e7649609cddd9f96bd8ec9229a07abacf2b379079cc` | `go/internal/web/invoices/store_test.go` |

Anchors that must exist verbatim (step 0 prints 1 or more): `App/app/invoices.py` `def _write_issued(` and `def allocate_number(`; `go/internal/pdf/invoice.go` `func Render(in Invoice`.

**Parity (Python -> Go `store.go`):**

| Python | Go | Lines |
|---|---|---|
| _load_invoice (every column but `pdf_blob`) | loadInvoice, invoiceColumns | invoices.py routes 50-61 |
| _entities, _chosen_entity, _entity_for_stay | entities, chosenEntity, entityForStay | routes 64-122 |
| _stay_for (access.reservation) | stayFor | routes 100-113, access.py 94-106 |
| _stay_options, _quick_stays | stayOptions, quickStays | routes 125-146, 192-202 |
| _last_stay_price_hint, _remember_paid_via | lastStayPriceHint, rememberedPaidVia | routes 205-241 |
| preview_number, allocate_number | previewNumber, allocateNumber, formatNumber | invoices.py 503-539 |
| _invoice_columns, pdf_view_row | writeIssued, pdfView | 542-612 |
| StayLimit, _check_stay_limit, active_invoice_for_stay | stayLimit, checkStayLimit, activeInvoiceForStay | 615-646 |
| _write_issued, issue | writeIssued, issueInvoice | 649-704 |
| _draft_from_original, cancel | draftFromOriginal, cancelInvoice | 707-783 |
| download_pdf | downloadPDF | 889-900 |

**Behaviours the tests pin:** numbers `<prefix><year>-<seq, 4 digits or more>` and variable symbol `<year><seq>`; `invoice_next_number` is used once, only when its year is the issue year, then cleared; the advisory lock is `pg_advisory_xact_lock(hashtext('invoice_sequence'), entity id)`, the one `db.lock_key` takes, so a Python and a Go writer of one operator queue up; a stay holds one live invoice, three issued in total (`invoice.err.stay_has_invoice` names the live one, `invoice.err.stay_limit` has none); `issued_by` is the workspace owner id (Python passes `access.owner_id`, not the account id); the PDF is rendered by `pdf.Render` inside the transaction and stored with its SHA-256; PostgreSQL triggers make an issued invoice immutable (tested); a non-payer cancel is a `storno`, a payer's is a `corrective` with the typed correction date (default today), all lines negated, `paid_on` copied as today when the original was paid; cancel needs a reason of 5 characters or more, refuses an invoice that already has a correction and refuses a storno; every owner lookup uses `owner_user_id IS NOT DISTINCT FROM`.

Deviations: `preview_number` uses `date.today().year` in Python (container local time); Go uses the UTC year (differs only in the first hour of 1 January). `correct_partial` (invoices.py 786-834, used by the booking webhook) is not ported here: it is not a route. `purge_expired` and `expired_ids` belong to the retention job (already Go).

**Test environment (`testenv_test.go`):** `UBYHOST_TEST_DATABASE_URL` points at a server you may create databases on; each test makes and drops a database and applies `App/migrations_pg/*.sql`. Two hosts, three businesses (one VAT payer), four stays, made-up names. Tests SKIP without the variable.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/store.go` | create | SQL, number allocation, issue and cancel transactions, PDF read |
| `go/internal/web/invoices/testenv_test.go` | create | PostgreSQL test environment, two hosts, `issueFor` |
| `go/internal/web/invoices/store_test.go` | create | numbering, stay limit, storno and ODD, hash check, immutability, owner scoping |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/invoices/draft.go go/internal/web/invoices/dec.go | tail -3` lists both; `ls go/internal/web/invoices/store.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def _write_issued(' App/app/invoices.py` and `grep -cF 'def allocate_number(' App/app/invoices.py` each print 1 or more; `grep -cF 'func Render(in Invoice' go/internal/pdf/invoice.go` prints 1 or more; `find docs/tasks/1422-files -name '*.txt' | wc -l` prints `3`.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1422-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")"; cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/invoices/store.go go/internal/web/invoices/testenv_test.go go/internal/web/invoices/store_test.go | tail -30
   ```

   All 3 hashes must equal §2. Commit "1422 step 1".

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

4. Write the report (§9) and commit "1422 step 3".

## 5. Do not touch

Everything outside §3. In particular: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/internal/pdf/`, `go/internal/billingjob/`, `go/internal/mail/`, `App/tests/conftest.py`, every Python file under `App/app/`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`, `docs/ENVIRONMENT.md`. Never set `UBYHOST_GO_PATHS`, edit Caddy or compose, push, merge or deploy. Never edit a copied file to make a test pass: a failing sidecar test is a STOP (§8). Hard rules 2, 3, 4, 5 as in §2.

## 6. Commands

Step 3 only, plus from the repo root `python3 scripts/context_lint.py 2>&1 | tail -30` (prints `context lint: OK`). Never the full suite, never `pytest tests`.

## 7. Acceptance

- [ ] The 3 sha256 values match §2.
- [ ] `gofmt -l` prints nothing; `go build ./...` and `go vet` print nothing.
- [ ] `go test` prints `ok` for `internal/web/invoices` and `cmd/ubyhost-web`; with PostgreSQL there is no `--- SKIP` line in `go test -v` (without it the report says "CI only").
- [ ] `cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 -v -run 'TestIssue|TestNumbering|TestStayLimit|TestCancel|TestDownload|TestHelpers' ./internal/web/invoices/ 2>&1 | grep -c '^--- PASS'` prints 8.
- [ ] `git log --oneline --grep='^1422 step' | tail -5` shows the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1422 step') | tail -30` lists only §3 paths.
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

Write `docs/tasks/1422-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`store.go` is the money and the numbering. Read `writeIssued` and `allocateNumber` against invoices.py 516-704 (the advisory-lock key, the order lock, entity read, stay limit, allocate, insert, items, render, hash, update, commit), `checkStayLimit`, `draftFromOriginal` and `cancelInvoice` (negated amounts, the kind, the correction date, who may cancel). Every query that takes an owner: `ownerArg` and `IS NOT DISTINCT FROM $n::bigint`. `issued_by` (owner id, not account id). `downloadPDF` (never re-renders).

## Owner steps

None: nothing is switched on. The pages stay dormant until the owner adds paths to `UBYHOST_GO_PATHS` (listed in brief 1427, Owner steps).
