# 1221: Go billing invoicer `go/internal/billingjob` (issue, supplementary, storno, send)

Status: todo
Depends on: 1220 (the `go/internal/pdf` package must exist on the branch; brief 1222 builds on this one) | Base commit: 85c355d | Branch: task/1221-go-billing-job
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the Go port of `App/app/billing_invoices.py`: `billingjob.Invoicer` issues UbyHost's own invoices to hosts (period invoice, supplementary invoice, storno) in one transaction with Python's numbering, snapshot, PDF, audit rows and error cases, and `Send` queues the `billing_invoice` mail. Nothing calls it yet: the job run (trial, roll, follow_apartments, dunning, registration) is brief 1222 and builds on this package. Python is untouched.

## 2. Context

- **API (exact):** `type Invoicer struct{ Pool *pgxpool.Pool }` with `IssueForPeriod(ctx, owner int64, periodFrom, periodTo string, today time.Time) (int64, error)`, `IssueSupplementary(ctx, owner int64, amountCZK int64, description, periodFrom, periodTo string, today time.Time) (int64, error)`, `Storno(ctx, invoiceID int64, reason string, today time.Time) (int64, error)`, `Send(ctx, invoiceID int64) error`. Also exported for 1222: `Recipient`, `MailEnabled`, `AppBaseURL`, `PublicBaseURL`, `OperatorEmail`, `DueDays`, `SupplementaryMinCZK`. Sentinel errors (`Error()` is Python's ValueError text): `ErrBuyerMissing` (`buyer_missing`), `ErrNoPlan`, `ErrBelowMinimum`, `ErrNotAnInvoice`, `ErrAlreadyVoided`, `ErrPaid`, `ErrWorkspaceDeleted`. `today` is used only for its calendar date; the caller passes the local date, as Python's `date.today()`.
- **What it does.** `issue` is one transaction: sequence upsert (`platform_invoice_sequence`), number `UBY-<year>-<seq:04d>`, variable symbol `<year><seq:04d>`, `snapshot_json` byte-identical to Python's `json.dumps(..., ensure_ascii=False, sort_keys=True)` (own writer in `items.go`; `encoding/json` would escape `<>&`), PDF from `pdf.Render(inv, rows, "cs", false, false)`, `pdf_sha256` of the stored bytes, storno voids the original, `IssueForPeriod` clears `carry_czk`. The audit row `platform_invoice_issued` (`<number> <kind>`, actor `system`) is written after the commit. Prices come from the existing `billing.Quote` (read-only).
- **Mail.** `Send` builds the Czech mail with the new `mail.BuildBillingInvoice` (same shell and blocks as the other Go mails, html `lang="cs"`), then `ubyport.EnqueueMail` (read-only reuse): kind `billing_invoice`, key `billing-invoice-<id>`, `owner_user_id` set, no cc, payload `{"text","html","lang":"cs","reply_to","platform_invoice_id","attachment_name":"<number>.pdf"}` written as Python's `json.dumps`. Nothing is queued when mail is off (`UBYHOST_MAIL_BACKEND` not `console`/`ses`), the invoice is missing or has no owner, or the recipient (`buyer_email`, else the login e-mail, stripped, normalised) is empty.
- **Golden.** `App/scripts/billing_invoice_golden.py` seeds a throwaway SQLite with six users and four old invoices, runs 35 steps (period invoice twice, supplementary incl. `below_minimum` at 49 and the boundary 50, every storno error, send incl. mail off and no recipient, a year rollover) through the real Python, and dumps the results plus the `platform_invoice`, sequence, carry, audit and `email_outbox` rows to `go/internal/billingjob/testdata/invoicer.golden.json`. `invoicer_test.go` replays the same steps on Postgres and compares everything (including the full mail payload) except `pdf_blob`/`pdf_sha256`; for those it checks that the stored hash matches the stored bytes and that they start `%PDF-`. It skips without `UBYHOST_TEST_DATABASE_URL`. `unit_test.go` (no database) checks the snapshot writer against a Python-written string, plus floor division, Czech plurals and date formats.
- All the code was written and dry-run by the brief writer (gofmt, vet, build, `go test ./internal/billingjob` with Postgres 16 green, the test fails when a description is changed, the golden script reproduces the file byte for byte). It is stored under `docs/tasks/1221-files/` with a sha256 each; you only copy and verify. Do not edit these files.
- **Known differences from Python (accepted, documented in `doc.go`):** (1) PDF bytes and `pdf_sha256` come from go/internal/pdf, not reportlab; (2) `Send` returns an error only, Python returned the mail id or `None`; (3) `EnqueueMail` failures return an error, Python logged and returned the existing id; (4) `buyer_name` blankness uses `strings.TrimSpace`, not Python `str.strip`; (5) operator and billing settings are read from the environment at each call, Python reads them once at import; (6) a plan name outside `standard`/`max` is an error from `billing.Quote`, Python raises `KeyError` (the database constrains it anyway).
- 1222 reads these hand-offs: `periodItems`/`account` stay unexported; it calls the four methods and the exported helpers above.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/billingjob/doc.go` | create | package comment with the API and differences |
| `go/internal/billingjob/invoicer.go` | create | sentinels, `Invoicer`, issue/supplementary/storno, transaction |
| `go/internal/billingjob/items.go` | create | account row, `periodItems`, dates, snapshot writer |
| `go/internal/billingjob/send.go` | create | `Send`, `Recipient`, mail and base-URL helpers |
| `go/internal/billingjob/unit_test.go` | create | snapshot, floor division, plurals, dates (no database) |
| `go/internal/billingjob/invoicer_test.go` | create | golden replay on Postgres |
| `go/internal/billingjob/testdata/invoicer.golden.json` | create | Python results and rows, written by the script |
| `go/internal/mail/billing_invoice.go` | create | `BuildBillingInvoice` (cs strings, shell, blocks) |
| `App/scripts/billing_invoice_golden.py` | create | the golden script |
| `docs/tasks/1221-files/*` | keep | the attachments (already committed by the brief writer; leave them) |
| `docs/tasks/1221-report.md` | create | the report |

No other file may change.

## 4. Steps

Attachment sha256 (first 12 hex characters shown; the full values are in step 0):

- `doc.go` 11073d383908
- `invoicer.go` 67f467431ec7
- `items.go` 86f0a85779c6
- `send.go` 5ad03bcad8a5
- `unit_test.go` 51bda39c0151
- `invoicer_test.go` 77323f3f8ab6
- `billing_invoice.go` 7ba81a62d5e6
- `billing_invoice_golden.py` 90b0746ba526
- `invoicer.golden.json` 362662715998

### Step 0: anchors

From the repo root:

```bash
git status --short | head -5; ls go/internal/pdf/invoice.go 2>&1 | tail -1; ls go/internal/billingjob 2>&1 | tail -1; ls docs/tasks/1221-files | wc -l; cd docs/tasks/1221-files && sha256sum -c <<'EOF2' 2>&1 | tail -12
7ba81a62d5e61fe256eb490691164eb0b2a0a5c1a618818673d6ba2e78a6d16c  billing_invoice.go
90b0746ba526539223f2d49e7e8a802cbb4475d75087e20f333d794d29f31f2b  billing_invoice_golden.py
11073d3839086fbbf3cd3f0c475cd5c0929072ad848d192fbfb79387b14cfb8d  doc.go
67f467431ec7763a149aa6cf771b0b55ab9fe7eeef87d3ac433c4f64d0b72dd9  invoicer.go
362662715998e0d5cff75fc07f2e9fddaa5e018a5b5904518debc811f52c7570  invoicer.golden.json
77323f3f8ab6b5f36d772cdeef12bcee95a4dffde41d3df06f976b597f8a79a9  invoicer_test.go
86f0a85779c6b56e44b609b9671660fad1f28a11c2d87442d0266639391a91c7  items.go
5ad03bcad8a5e1b4dab95325eff40867b017d3d69e615e03a8b4c22debf45bd7  send.go
51bda39c01516db05c1532055b54a97b6e19717c62d2c6d134e2a6483fd41721  unit_test.go
EOF2
```

Expected: empty status, `go/internal/pdf/invoice.go` listed (brief 1220 applied; if `ls: cannot access`, STOP: 1221 needs 1220), `ls: cannot access` for billingjob, `9`, nine lines ending `OK`. Anything else: STOP (§8).

### Step 1: the Go code

```bash
mkdir -p go/internal/billingjob/testdata
for f in doc.go invoicer.go items.go send.go unit_test.go invoicer_test.go; do cp docs/tasks/1221-files/$f go/internal/billingjob/$f; done
cp docs/tasks/1221-files/billing_invoice.go go/internal/mail/billing_invoice.go
cp docs/tasks/1221-files/invoicer.golden.json go/internal/billingjob/testdata/
cd go && test -z "$(gofmt -l internal/billingjob internal/mail)" && go vet ./internal/billingjob ./internal/mail 2>&1 | tail -10; go build ./... 2>&1 | tail -5; go test ./internal/billingjob -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL|panic)' | tail -10; git status --short go.mod go.sum | tail -3
```

Expected: gofmt and vet silent, build silent, `--- PASS` for `TestSnapshotJSONMatchesPython` and `TestHelpers`, `--- SKIP` for `TestInvoicerMatchesPython` (no database variable yet), `ok`, and no change to `go.mod` or `go.sum` (no new dependency; if either changes: STOP). Commit: `1221 step 1`.

### Step 2: the database test

Needs a Postgres. CI uses `postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test`; locally use any reachable Postgres 16 or 17 on which the user may create databases:

```bash
cd go && UBYHOST_TEST_DATABASE_URL="$UBYHOST_TEST_DATABASE_URL" go test ./internal/billingjob -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10
```

Expected: three `--- PASS` (including `TestInvoicerMatchesPython`) and `ok`. If no database is reachable, say so in the report and leave this step to CI (do not mark it done); the other steps still stand. A failing row diff: STOP (§8), do not edit the golden or the Go code.

### Step 3: the Python golden script, and proof that it reproduces the file

```bash
cp docs/tasks/1221-files/billing_invoice_golden.py App/scripts/billing_invoice_golden.py
cd App && (test -d .venv || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt)) 2>&1 | tail -3
.venv/bin/python scripts/billing_invoice_golden.py 2>&1 | tail -3; cd .. && git status --short go/internal/billingjob/testdata | tail -3; sha256sum go/internal/billingjob/testdata/invoicer.golden.json | cut -c1-12
```

Expected: `wrote .../invoicer.golden.json`, no change shown for the testdata file (the script reproduces the committed JSON byte for byte; otherwise STOP and report), checksum prefix `362662715998`. Commit: `1221 step 3`.

### Step 4: final check

Run the §6 commands, write the report, set `Status: review`. Push is NOT yours (§8).

## 5. Do not touch

Everything outside §3. In particular `go/internal/pdf`, `go/internal/billing`, `go/internal/ubyport`, `go/cmd/*` (no registration here: that is 1222), `App/app/*` (read-only), `docs/context/*`, `docs/ENVIRONMENT.md`. Hard rules: 2 (the golden holds invented data only; the new code reads personal data the invoice already holds and sends one mail kind the Python job already sends; no new outbound request), 4 (no dependency), 5 (SQL stays in the Go package, parameterised, Postgres only; no schema change).

## 6. Commands

```bash
cd go && test -z "$(gofmt -l internal/billingjob internal/mail)" && go vet ./internal/billingjob ./internal/mail && go build ./... 2>&1 | tail -5
cd go && go test ./internal/billingjob ./internal/mail -count=1 2>&1 | tail -10
cd go && UBYHOST_TEST_DATABASE_URL="$UBYHOST_TEST_DATABASE_URL" go test ./internal/billingjob -count=1 -v 2>&1 | grep -cE '^--- PASS'
python3 scripts/context_lint.py 2>&1 | tail -5
```

Expected: silent / `ok` twice / `3` (with a database; `2` plus one `SKIP` without) / lint clean.

## 7. Acceptance

- [ ] `TestInvoicerMatchesPython` passes against Postgres (results, invoices, sequence, carry, audit and mail rows equal Python's), or the report says no database was reachable.
- [ ] `go build ./...` and vet clean; gofmt silent; `go.mod`/`go.sum` unchanged.
- [ ] Every stored invoice has `has_pdf` true (hash matches bytes, starts `%PDF-`).
- [ ] `git diff --stat` lists only §3 files (plus `docs/tasks/1221-files` unchanged).
- [ ] The golden script reproduces the committed JSON byte for byte.

## 8. Stop and ask

Stop, and write the report, if: an anchor or checksum differs; `go/internal/pdf` is missing; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, `Done: steps 1 to k`); `go.mod` or `go.sum` change; a file outside §3 needs a change; a step is unclear; you need push, merge or deploy (hand that to the owner).

## 9. Report

`docs/tasks/1221-report.md` (600 tokens at most): files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`go/internal/billingjob/invoicer.go` (read against `App/app/billing_invoices.py` `issue`, `storno`, `issue_for_period`), `go/internal/billingjob/items.go` (`period_items`, snapshot writer), `go/internal/billingjob/send.go` and `go/internal/mail/billing_invoice.go` (against `mail_notify.build_billing_invoice` and `billing_invoice`).

## Owner steps

1. Merge when CI is green (the CI Postgres runs the golden replay). Nothing is switched on by this PR; the job registration is brief 1222.
