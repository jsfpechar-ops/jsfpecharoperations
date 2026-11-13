# 1427: Go invoice pages: issue, preview and the route table

Status: todo
Depends on: 1425 and 1426 (both merged or on this branch) | Base commit: main (sidecars replayed in order on 0eaed0a78) | Branch: task/1427-go-invoices-issue-preview
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Add the last two routes of the thread, still switched off: `POST /invoices/preview` (the draft as a watermarked PDF, nothing saved) and `POST /invoices` (the fill buttons, validation with the 422 form, the issue transaction, the redirect with the invoice number). Add the route-table tests in the package and in `go/cmd/ubyhost-web`, and the owner's switch-on list.

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 no new personal-data field and no new outbound request; 3 fixtures are made up (`@example.test`, no real names); 4 no new dependency (stdlib, pgx and packages already in go.mod); 5 plain PostgreSQL SQL, no schema change; 7 and 10 (screenshots, UX gate) do not apply yet: the pages are not served, no path is in `UBYHOST_GO_PATHS`, and the UX gate is the owner step at the switch (brief 1427, Owner steps).

**All code is pre-written, compiled and tested** by the brief writer in a scratch worktree, in brief order 1420 to 1427. Sidecars live under `docs/tasks/1427-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

| sha256 | file (repo path; sidecar = `docs/tasks/1427-files/<path>.txt`) |
|---|---|
| `f7d4b6ae7b3fdb79258728b42c2496b815a7c4427e3b2d1f0c916e35215d18e9` | `go/internal/web/invoices/post_issue.go` |
| `7eee1645fe9d455b2b0ef8581bdb213c327e6ba9146b80a55617a53173a266fb` | `go/internal/web/invoices/post_test.go` |
| `1c29506a0233ee702bec26e9f125e79b9e6703b261a16709118267ac717585a2` | `go/internal/web/invoices/fill_register_test.go` |
| `724a1aec4a2510e8fa9f9f6c32ab4ad9d7afcbf685bbeefd2f49531bcba4cb7c` | `go/internal/web/invoices/routes_test.go` |
| `ca6d1296bafa74ad4d6275fc946899121449c1f42ca1e73ffee489052a5e01d4` | `go/cmd/ubyhost-web/register_web_invoices_test.go` |

**Parity (Python -> Go `post_issue.go`):**

| Route | Python | Go |
|---|---|---|
| POST /invoices/preview | invoice_preview, routes/invoices.py 790-811; `_preview_view` 312-367; `_draft` 304-309 | `previewHandler`, `previewInvoice`, `previewItems` |
| POST /invoices | invoice_issue 814-880 | `issueHandler`/`issue` |

**Order of checks in `invoice_issue` (the Go code follows it line by line):** CSRF, login; the stay (`reservation_id`) must be the host's, else back to `/invoices/new` with `invoice.err.no_stay`; `stay_problem` key as the flash; the operator for the stay (the property's operator, else the posted `legal_entity_id`, else `?entity=`, else the first), none: `invoice.err.no_entity`; then, in this order and each re-rendering the form with status 200 and everything the host typed: `fill_buyer_from_register` (company: the guest's suggestion is dropped first, then the register fills blanks, brief 1426), `fill_from_guest` (blank buyer fields only; with no usable guest the error `invoice.fill_guest.none`), any other key starting `fill_`; otherwise the draft is built and validated (`validate_for_issue`, then the one-page check `pdf.TooLong` giving `invoice.err.too_long`); issues re-render with status **422** and the translated list; a stay that already holds its invoice or its limit redirects (`/invoices/<live id>` with the key, or `/reservations/<id>`); success redirects to `/invoices/<new id>` with `invoice.issued_flash` carrying the number. The preview never validates (an invalid draft still previews), saves nothing and takes no number; its view prints the number and variable symbol as dashes and leaves the buyer's country name empty, as `_preview_view` does.

**Behaviours the tests pin:** a full issue (number `2026-0001`, VS, totals, items, PDF hash, audit line `invoice_issued id=.. number=.. entity=.. total=..`, owner and `issued_by` = workspace owner); VAT payer amounts (base 123457 + 15000, VAT 25926, the local stay fee outside VAT); the 422 form keeps every typed value, the chosen extra kind and a quantity of 0; a second issue for the stay goes to the live invoice; foreign, cancelled and missing stays go to `/invoices/new`; a forged `legal_entity_id` of another host is ignored; a POST without a CSRF token never issues; the guest-fill and company-fill flows (a typed value is never replaced; the register fills the rest; the typed country stays).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/post_issue.go` | create | POST /invoices/preview and POST /invoices |
| `go/internal/web/invoices/post_test.go` | create | issue, VAT payer, 422, refusals, preview |
| `go/internal/web/invoices/fill_register_test.go` | create | the company fill flow with a local register |
| `go/internal/web/invoices/routes_test.go` | create | the eight routes, no duplicate pattern, no send route |
| `go/cmd/ubyhost-web/register_web_invoices_test.go` | create | every route reaches its own pattern in the real mux |

No other file may change.

## 4. Steps

0. Checks (repo root): `git branch --show-current` prints `task/1427-go-invoices-issue-preview`; `ls go/internal/web/invoices/formctx.go go/internal/web/invoices/ares.go go/internal/web/invoices/public.go | tail -4` lists all three; `ls go/internal/web/invoices/post_issue.go 2>&1 | tail -2` says "No such file"; `grep -cF 'async def invoice_issue(request: Request):' App/app/routes/invoices.py` and `grep -cF 'async def invoice_preview(request: Request):' App/app/routes/invoices.py` each print 1 or more; `find docs/tasks/1427-files -name '*.txt' | wc -l` prints `5`.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1427-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")"; cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/invoices/post_issue.go go/internal/web/invoices/post_test.go go/internal/web/invoices/fill_register_test.go go/internal/web/invoices/routes_test.go go/cmd/ubyhost-web/register_web_invoices_test.go | tail -30
   ```

   All 5 hashes must equal §2. Commit "1427 step 1".

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

   Then the whole web side once, from `go/` (only to prove nothing else broke): `cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 ./cmd/... ./internal/web/... 2>&1 | tail -30` prints `ok` for every package.

4. Write the report (§9) and commit "1427 step 3".

## 5. Do not touch

Everything outside §3. In particular: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/internal/pdf/`, `go/internal/billingjob/`, `go/internal/mail/`, `App/tests/conftest.py`, every Python file under `App/app/`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`, `docs/ENVIRONMENT.md`. Never set `UBYHOST_GO_PATHS`, edit Caddy or compose, push, merge or deploy. Never edit a copied file to make a test pass: a failing sidecar test is a STOP (§8). Hard rules 2, 3, 4, 5 as in §2.

## 6. Commands

Step 3 only, plus from the repo root `python3 scripts/context_lint.py 2>&1 | tail -30` (prints `context lint: OK`). Never the full suite, never `pytest tests`.

## 7. Acceptance

- [ ] The 5 sha256 values match §2.
- [ ] `gofmt -l` prints nothing; `go build ./...` and `go vet` print nothing.
- [ ] `go test` prints `ok` for `internal/web/invoices` and `cmd/ubyhost-web`; with PostgreSQL there is no `--- SKIP` line in `go test -v` (without it the report says "CI only").
- [ ] `cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 -v -run 'TestIssue|TestPreview|TestFill|TestFormState|TestRoutes|TestSendRoute' ./internal/web/invoices/ 2>&1 | grep -c '^--- PASS'` prints 9.
- [ ] `cd go && go test -count=1 -run TestInvoiceRoutesRegistered ./cmd/ubyhost-web/ 2>&1 | tail -3` prints `ok`.
- [ ] `git diff --stat HEAD~2..HEAD | tail -15` lists only §3 paths.
- [ ] Commits "1427 step 1" and "1427 step 3"; nothing pushed.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or a check in step 0 is not as written;
- a sha256 in step 1 does not match;
- `gofmt -l` prints a file, `go build` or `go vet` prints anything, or a test fails twice (read the last 30 lines once; never edit a copied file);
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1427-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`post_issue.go` `issue`: the order of the early returns (stay and operator are checked before any fill flow), `buildDraft` input is `PostForm` only, `issueInvoice` (owner and `issued_by`), the 422 branch writes nothing. `previewHandler`: saves nothing. Together with 1422 this is the code that creates legal documents: compare the draft test cases (1421) and `TestIssuePayerAmounts`. The forged-operator test (`TestIssueRefusals`) is the permission check for the operator id.

## Owner steps

Nothing is switched on by this brief, and the thread is not complete until brief 1429 (the send route) is unblocked, because of the way Caddy matches paths (see 6). After the eight briefs 1420 to 1427 are merged, what the owner can add to `UBYHOST_GO_PATHS` (space-separated, double quotes, as in `docs/ENVIRONMENT.md`; ask the orchestrator to add the row there):

1. Safe to add one by one, in this order, each followed by the UX gate below and the rollback test (remove the path again, `docker compose up -d caddy`): `/invoice/d/*` (public download link, no page), `/invoices/*.pdf`, `/invoices/*/paid`, `/invoices/*/cancel`, `/invoices/preview`, then `/invoices/new` and `/invoices` (the last one moves the list **and** the issue POST at once, because both use the path `/invoices`; the form on `/invoices/new` posts to `/invoices`, so add `/invoices/new` and `/invoices` together).
2. Do **not** add `/invoices/*`: Caddy would then send `/invoices/<id>/send` to Go, which has no handler (404). The detail page `GET /invoices/<id>` has no path of its own (there is no Caddy matcher that picks `/invoices/12` but not `/invoices/12/send`), so it stays on Python until brief 1429 ports the send route. Until then the list links to detail pages Python serves; that works.
3. Where Python still serves another method on the same path: `/invoices` (Python also answers nothing else on it: both GET and POST are Go once added), `/invoices/new` (GET only; Python answers POST with 405 and so does Go), `/invoices/preview` (POST only, Python answers GET with 405). `/invoices/*/paid` and `/invoices/*/cancel` (POST only). No path is shared with a method Python alone serves, except `/invoices/<id>/send` (POST, Python) which the matchers in 1 do not touch.
4. UX gate (AGENTS.md rule 10, yours, not the owner's) before each of `/invoices`, `/invoices/new` goes live: run `test_layout_lint_browser.py` against a Go-served build, open the 390, 768 and 1280 px screenshots of the list, the picker, the form (one operator and two operators, a payer and a non-payer, the 422 state) and write what you saw per page in the PR; tick the design-system checklist.
5. Rollback: remove the path from `UBYHOST_GO_PATHS`, run `caddy-validate.sh`, `docker compose up -d caddy`. Python code is deleted only in a later PR after one clean production week.
6. Coordinator lines (send to the orchestrator; `status.md`, `test-map.md`, `decisions.md` are theirs): status "Port invoice pages: 1420-1427 merged, dormant; send route (1429) blocked on the mail builder"; test-map row for `go/internal/web/invoices/**` and `go/cmd/ubyhost-web/register_web_invoices*.go`: `go test ./internal/web/invoices/... ./cmd/ubyhost-web/...` (database tests need `UBYHOST_TEST_DATABASE_URL`) and from `App/` `pytest tests/test_go_invoices.py`; decisions: "ARES lookup now also made by the Go service (same request as Python)".
