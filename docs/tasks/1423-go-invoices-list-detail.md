# 1423: Go invoice pages: the list, the detail page and the PDF download

Status: review
Depends on: 1422 (merged or on this branch) | Base commit: the working branch head (no fixed commit) | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch: never create a branch, never push, never open a PR. Commit `1423 step k` after each step that changes a file. The owner opens one pull request for all briefs.

## 1. Objective

Add three routes to the Go invoice package, still switched off: `GET /invoices` (the filtered, paged list), `GET /invoices/{id}` (the detail page) and `GET /invoices/{id}.pdf` (the stored PDF). The Jinja templates `invoices.html`, `_list_filter.html` and `invoice_detail.html` become Go templates on the host layout shell; the list filter (`App/app/list_filter.py`) is ported.

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 no new personal-data field and no new outbound request; 3 fixtures are made up (`@example.test`, no real names); 4 no new dependency (stdlib, pgx and packages already in go.mod); 5 plain PostgreSQL SQL, no schema change; 7 and 10 (screenshots, UX gate) do not apply yet: the pages are not served, no path is in `UBYHOST_GO_PATHS`, and the UX gate is the owner step at the switch (brief 1427, Owner steps).

**All code is pre-written, compiled and tested** by the brief writer in a scratch worktree, in brief order 1420 to 1427. Sidecars live under `docs/tasks/1423-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

| sha256 | file (repo path; sidecar = `docs/tasks/1423-files/<path>.txt`) |
|---|---|
| `3e976c73b13f68730c4b8f8aac088c1615f0c85930f0b8374c2127db15db2242` | `go/internal/web/invoices/listfilter.go` |
| `4b0ae3b7c9d9b9523f09b994f87cf0980122271b971804410f6b0d1b5512e71d` | `go/internal/web/invoices/pages_list.go` |
| `29eaa9e0de3ccc63e6409b1dd12f0a68d2b1fbf53ddf571c4b139395ef4b510e` | `go/internal/web/invoices/pages_detail.go` |
| `f1a90a2365d61aa95924d53599150587c99db52058c1eba7890279426b1e6039` | `go/internal/web/invoices/pdf_download.go` |
| `3fdee89a11bb2014e795ccca58a712b57611b94131fe7a45c3ba4e6a1c22bffe` | `go/internal/web/invoices/templates/list.tmpl` |
| `0e3ce8517b4b9264422211ca7f4437e064651b98d1c192ba3f450b9466065a0c` | `go/internal/web/invoices/templates/filter.tmpl` |
| `e2deb7373e8c9a4ee425861c2ea6053d96cb7584fc40ebcab2ec045bca9f56fd` | `go/internal/web/invoices/templates/detail.tmpl` |
| `cc2beec271785c83cc015e7fd0765c6beac89068ffebb3a7013be41e2ffcfd82` | `go/internal/web/invoices/pages_test.go` |
| `43d7e24aeaead75611e0420615530ecfd056b6bb24719ecfacc8089fc5dcee5d` | `go/internal/web/invoices/pdf_download_test.go` |

**Parity (Python -> Go):**

| Route | Python | Go |
|---|---|---|
| GET /invoices | invoices_list, routes/invoices.py 370-441; list_filter.py `parse`, `query`, `context`; templates invoices.html, _list_filter.html | `listHandler`/`list` in pages_list.go, listfilter.go, templates/list.tmpl, filter.tmpl |
| GET /invoices/{id} | invoice_detail 902-927 (`{invoice_id:int}`), template invoice_detail.html | `invoiceGet`/`detail` in pages_detail.go, templates/detail.tmpl |
| GET /invoices/{id}.pdf | invoice_pdf_download 883-899 | `pdfDownload` in pdf_download.go |

**Why one handler for two Python routes:** `ServeMux` wildcards are whole segments, so `GET /invoices/{id}` receives `12`, `12.pdf` and `preview`. `invoiceGet` sends `<n>.pdf` to `pdfDownload`, answers `preview` with Starlette's 405 JSON (`Allow: POST`), a non-number with the 404 JSON `{"detail":"Not Found"}`, and a number to the detail page. `/invoices/abc.pdf` is FastAPI's 422 JSON (the id is validated before the login check).

**Behaviours the tests pin:** the list shows only the host's invoices (`owner_user_id IS NOT DISTINCT FROM`); state is `correction` for a storno or ODD, `paid` when `paid_on` or `marked_paid_at` is set, `cancelled` when a storno points at it, else `unpaid`; filters: month (from 2000-01 to this month, anything else is ignored), property (only the host's), status (only the three known), search (`strpos(lower(number))` or `strpos(lower(buyer_name))` with the query lower-cased by the application, as Python: PostgreSQL's `lower()` in the C collation changes ASCII only, so "Černý" never matches "černý"); 50 rows a page, `page` below 1 or not a number is 1, the pager links keep the filter; the detail page shows the state pill and note, mark-paid only for an unpaid invoice, send only with a buyer e-mail, cancel only for an invoice without a correction (a VAT payer is also asked for a correction date), VAT columns and totals for a payer; another host's invoice, or none, is a redirect to `/invoices` with the `flash.error.no_such_invoice` message; the PDF download is the stored bytes with `Content-Disposition: attachment; filename="faktura-<number>.pdf"` and `Cache-Control: no-store`.

Deviations: the `page_tabs()` loop of invoices.html (it only draws one link) is the single "Invoice settings" link (`access.invoice_details_url`: the business editor when the host has one business, else `/entities`); the state pill labels are HTML-escaped in Go (the Jinja pill is concatenated and marked safe); amounts and dates are formatted in Go (`moneyCZK`, `fmtDate`) instead of the `money_czk` and `date_cz` filters; a method the route does not list on `/invoices/new` and similar paths gets `ServeMux`'s own 405 text, not Starlette's JSON.

The inline filter script and CSS are the shared ones in `static/`; only markup is ported. The templates keep the `data-*` hooks the existing JavaScript reads.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/listfilter.go` | create | month/property/status/search filter (list_filter.py) |
| `go/internal/web/invoices/pages_list.go` | create | GET /invoices, template funcs, the parsed templates |
| `go/internal/web/invoices/pages_detail.go` | create | GET /invoices/{id} and the dispatch of `.pdf`, `preview`, non-numbers |
| `go/internal/web/invoices/pdf_download.go` | create | the stored PDF |
| `go/internal/web/invoices/templates/list.tmpl` | create | invoices.html |
| `go/internal/web/invoices/templates/filter.tmpl` | create | _list_filter.html (invoice list variant) |
| `go/internal/web/invoices/templates/detail.tmpl` | create | invoice_detail.html |
| `go/internal/web/invoices/pages_test.go` | create | list, filters, paging, detail, refusals |
| `go/internal/web/invoices/pdf_download_test.go` | create | PDF headers, owner scoping, 422, login redirect |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/invoices/store.go go/internal/web/invoices/testenv_test.go | tail -3` lists both; `ls go/internal/web/invoices/pages_list.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def invoices_list(request: Request):' App/app/routes/invoices.py` and `grep -cF 'def invoice_detail(invoice_id: int, request: Request):' App/app/routes/invoices.py` each print 1 or more; `grep -cF 'func MustParseFuncs(' go/internal/hostweb/layout/pagefuncs.go` prints 1 or more; `find docs/tasks/1423-files -name '*.txt' | wc -l` prints `9`.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1423-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")"; cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/invoices/listfilter.go go/internal/web/invoices/pages_list.go go/internal/web/invoices/pages_detail.go go/internal/web/invoices/pdf_download.go go/internal/web/invoices/templates/list.tmpl go/internal/web/invoices/templates/filter.tmpl go/internal/web/invoices/templates/detail.tmpl go/internal/web/invoices/pages_test.go go/internal/web/invoices/pdf_download_test.go | tail -30
   ```

   All 9 hashes must equal §2. Commit "1423 step 1".

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

4. Write the report (§9) and commit "1423 step 3".

## 5. Do not touch

Everything outside §3. In particular: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/internal/pdf/`, `go/internal/billingjob/`, `go/internal/mail/`, `App/tests/conftest.py`, every Python file under `App/app/`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`, `docs/ENVIRONMENT.md`. Never set `UBYHOST_GO_PATHS`, edit Caddy or compose, push, merge or deploy. Never edit a copied file to make a test pass: a failing sidecar test is a STOP (§8). Hard rules 2, 3, 4, 5 as in §2.

## 6. Commands

Step 3 only, plus from the repo root `python3 scripts/context_lint.py 2>&1 | tail -30` (prints `context lint: OK`). Never the full suite, never `pytest tests`.

## 7. Acceptance

- [ ] The 9 sha256 values match §2.
- [ ] `gofmt -l` prints nothing; `go build ./...` and `go vet` print nothing.
- [ ] `go test` prints `ok` for `internal/web/invoices` and `cmd/ubyhost-web`; with PostgreSQL there is no `--- SKIP` line in `go test -v` (without it the report says "CI only").
- [ ] `cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 -v -run 'TestList|TestDetail|TestPDF|TestPyQuote' ./internal/web/invoices/ 2>&1 | grep -c '^--- PASS'` prints 7.
- [ ] UX gate (rules 7, 10): not applicable, the pages are not served; it is run at the switch (brief 1427, Owner steps).
- [ ] `git log --oneline --grep='^1423 step' | tail -5` shows the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1423 step') | tail -30` lists only §3 paths.
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

Write `docs/tasks/1423-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`pages_list.go` `list`: the dynamic WHERE (parameter numbers via `next`, the owner clause first, the status SQL, the search needle passed twice). `pages_detail.go` `detail`/`invoiceGet`: `loadInvoice` (owner scope) before anything is shown, the amounts, the cancel and paid conditions. `pdf_download.go`: owner check before the bytes. Personal data on screen: buyer name, e-mail, address are shown only to the owner of the invoice (tests: another host gets the redirect). Templates are new markup on the host shell: skim `detail.tmpl` for `{{` in an attribute that could take unescaped input (all output is `html/template`-escaped).

## Owner steps

None: nothing is switched on. The pages stay dormant until the owner adds paths to `UBYHOST_GO_PATHS` (listed in brief 1427, Owner steps).
