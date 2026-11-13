# 1421: Go invoice pages: the invoice draft, parity-checked against Python

Status: todo
Depends on: 1420 (merged or on this branch) | Base commit: main (sidecars replayed in order on 0eaed0a78) | Branch: task/1421-go-invoices-draft
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Port the pure invoice-building logic of `App/app/invoices.py` to Go (`draft.go`): the stay line, the extra lines, the seller snapshot, the due date and tax point, the totals, the validation caps and the stay rules, and compare 47 form cases and 10 stay cases with the output of the real Python (`App/scripts/invoices_golden.py` writes the golden). Nothing reads the database; no route yet.

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 no new personal-data field and no new outbound request; 3 fixtures are made up (`@example.test`, no real names); 4 no new dependency (stdlib, pgx and packages already in go.mod); 5 plain PostgreSQL SQL, no schema change; 7 and 10 (screenshots, UX gate) do not apply yet: the pages are not served, no path is in `UBYHOST_GO_PATHS`, and the UX gate is the owner step at the switch (brief 1427, Owner steps).

**All code is pre-written, compiled and tested** by the brief writer in a scratch worktree, in brief order 1420 to 1427. Sidecars live under `docs/tasks/1421-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

| sha256 | file (repo path; sidecar = `docs/tasks/1421-files/<path>.txt`) |
|---|---|
| `f59123e17939c8208e9f2f82a8ea974263d91e787151170a42f5397f017a6939` | `go/internal/web/invoices/draft.go` |
| `f7fde7a626a67488198f1222d61c39c6714668787cb7cfdc93018af0573da5fe` | `go/internal/web/invoices/draft_test.go` |
| `0ff7f1f79da40ea6563d688ad583da5342cb675dd820a5b5ae17a19103d88746` | `go/internal/web/invoices/testdata/draft_golden.json` |
| `d9e3e5c7b27a354d36c2b1e66b11f94e30e2b85ff53ec203708db631f5d23f4d` | `App/scripts/invoices_golden.py` |
| `d84a67fff35b7aa227a3917385c58d6ddcd64c4ff6a78cddb7a6a41822b1245d` | `App/tests/test_go_invoices.py` |

Anchors that must exist verbatim (step 0 prints 1 or more): `App/app/invoices.py` `def build_draft(` and `def validate_for_issue(`.

**Parity (Python `App/app/invoices.py` -> Go `draft.go`):**

| Python | Go | Lines |
|---|---|---|
| build_draft (stay path) | buildDraft | 362-436 |
| _stay_item, _extras_from_form | stayItem, extrasFromForm | 285-359 |
| seller_snapshot (with payments.normalise_account) | sellerSnapshot, normaliseAccount | 157-206 |
| stay_problem, stay_nights, stay_label, _nights_text | stayProblem, stayNights, stayLabel, nightsText | 237-278 |
| validate_for_issue, _stay_issues | validateForIssue, stayIssues | 450-500 |
| custom_paid_via_label | customPaidViaLabel | 439-447 |

Not ported: `_items_from_form` (117-154) and the free-form path of `build_draft`: every route passes a stay, so nothing reaches them.

**Behaviours the golden pins** (read the cases in `App/scripts/invoices_golden.py`): Czech and plain decimals, a price that is not a number is flagged (`price_invalid`) and counts as 0; VAT payer: stay rate default 12, extras default rate 0 for a blank rate, `stay_fee` always 0 %; a forged `item_kind=stay` is turned into `invalid` and refused; at most one "other" line, 60 characters; extras together at most the stay line's gross; "other" at most 30 % of it (exactly 30 % passes, integer maths `other*100 > stay*30`); quantity 1 to 99; four lines at most; unpaid invoices get the due date `today + invoice_due_days` (0 days allowed); the tax point is the check-out day, never in the future; `seller_*` fields a form carries replace the stored seller (blank included), a posted `seller_bank_account` is normalised (Czech account to IBAN, mod 11, IBAN checksum) or, when invalid, the stored account stays; the last value of a repeated form key wins.

**Golden:** `App/scripts/invoices_golden.py` imports the real `app.invoices`, builds each case and writes `go/internal/web/invoices/testdata/draft_golden.json` (no database, no network; `--check` exits 1 when stale). `draft_test.go` builds the same drafts in Go and compares every field. `App/tests/test_go_invoices.py` checks the catalog against `go_host_i18n.py` and runs the golden `--check`.

**Verified by the brief writer:** with 1420 and these files: gofmt empty, vet clean, 47 draft cases and 10 stay cases PASS. The golden script was run with the database and PDF modules stubbed (the functions it calls are pure); it was **not** run with the real application imports (no `fastapi` here), and `test_go_invoices.py` was not run under pytest: its two assertions were run as plain Python (catalog identical, golden `--check` exit 0).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/draft.go` | create | draft types, form parsing, seller snapshot, validation |
| `go/internal/web/invoices/draft_test.go` | create | compares 47 form cases and 10 stay cases with the Python golden |
| `go/internal/web/invoices/testdata/draft_golden.json` | create | generated by the script below (deterministic) |
| `App/scripts/invoices_golden.py` | create | golden writer, runs the real `app.invoices` |
| `App/tests/test_go_invoices.py` | create | catalog and golden freshness |

No other file may change.

## 4. Steps

0. Checks (repo root): `git branch --show-current` prints `task/1421-go-invoices-draft`; `ls go/internal/web/invoices/handlers.go go/internal/web/invoices/dec.go | tail -3` lists both (brief 1420); `ls go/internal/web/invoices/draft.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def build_draft(' App/app/invoices.py` and `grep -cF 'def validate_for_issue(' App/app/invoices.py` each print 1 or more; `find docs/tasks/1421-files -name '*.txt' | wc -l` prints `5`.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1421-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")"; cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/invoices/draft.go go/internal/web/invoices/draft_test.go go/internal/web/invoices/testdata/draft_golden.json App/scripts/invoices_golden.py App/tests/test_go_invoices.py | tail -30
   ```

   All 5 hashes must equal §2. Commit "1421 step 1".

2. Build and test (repo root, one call per line; each ends with `2>&1 | tail -30`). No database is needed: this brief's tests do not use one.

   ```bash
   cd go && gofmt -l internal/web/invoices cmd/ubyhost-web 2>&1 | tail -30
   cd go && go build ./... 2>&1 | tail -30
   cd go && go vet ./internal/web/invoices/... ./cmd/... 2>&1 | tail -30
   cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: the first three print nothing; the last prints `ok  \tgithub.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices\t<time>` and `ok  \t...go/cmd/ubyhost-web\t<time>`. A `FAIL`, a `[build failed]` or a vet line: read the last 30 lines once, then STOP (§8).

   Then, from `App/` (skip a command whose `.venv` is missing and write "CI only" in the report):

   ```bash
   cd App && .venv/bin/python scripts/invoices_golden.py --check 2>&1 | tail -5
   cd App && .venv/bin/python -m pytest tests/test_go_invoices.py -q --tb=short -x 2>&1 | tail -30
   cd go && git status --short . | tail -5
   ```

   Expected: the first prints nothing (a `stale:` line: STOP, Python moved; never edit the JSON, Python or Go to match), the second prints `2 passed`, the third prints nothing.

3. Write the report (§9) and commit "1421 step 3".

## 5. Do not touch

Everything outside §3. In particular: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/internal/pdf/`, `go/internal/billingjob/`, `go/internal/mail/`, `App/tests/conftest.py`, every Python file under `App/app/`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`, `docs/ENVIRONMENT.md`. Never set `UBYHOST_GO_PATHS`, edit Caddy or compose, push, merge or deploy. Never edit a copied file to make a test pass: a failing sidecar test is a STOP (§8). Hard rules 2, 3, 4, 5 as in §2.

## 6. Commands

Step 3 only, plus from the repo root `python3 scripts/context_lint.py 2>&1 | tail -30` (prints `context lint: OK`). Never the full suite, never `pytest tests`.

## 7. Acceptance

- [ ] The 5 sha256 values match §2.
- [ ] `gofmt -l` prints nothing; `go build ./...` and `go vet` print nothing.
- [ ] `go test` prints `ok` for `internal/web/invoices` and `cmd/ubyhost-web`; with PostgreSQL there is no `--- SKIP` line in `go test -v` (without it the report says "CI only").
- [ ] `cd go && go test -count=1 -v -run 'TestBuildDraftMatchesPython|TestStayProblemMatchesPython' ./internal/web/invoices/ 2>&1 | grep -c '^    --- PASS'` prints 57.
- [ ] Golden `--check` clean and pytest `2 passed`, or "CI only" with the reason.
- [ ] `git diff --stat HEAD~2..HEAD | tail -15` lists only §3 paths.
- [ ] Commits "1421 step 1" and "1421 step 3"; nothing pushed.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or a check in step 0 is not as written;
- a sha256 in step 1 does not match;
- `gofmt -l` prints a file, `go build` or `go vet` prints anything, or a test fails twice (read the last 30 lines once; never edit a copied file);
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1421-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`draft.go` against invoices.py 157-206 and 285-500: every amount (`vatParts`, `grossNoVAT`, the cap comparisons), the issue list and its order, `stayProblem` date limits (400 days back, 365 forward), the due-date and tax-point rules. `normaliseAccount` against payments.py 109-125 (a wrong IBAN on an invoice is money). The golden cases are the evidence: read the case list for a rule the Python has that no case covers.

## Owner steps

None: nothing is switched on. The pages stay dormant until the owner adds paths to `UBYHOST_GO_PATHS` (listed in brief 1427, Owner steps).
