# 1420: Go invoice pages: package foundation, decimal maths, string catalog

Status: review
Depends on: none (the PDF library `go/internal/pdf/` and the billing job are merged) | Base commit: the working branch head (no fixed commit) | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch: never create a branch, never push, never open a PR. Commit `1420 step k` after each step that changes a file. The owner opens one pull request for all briefs.

## 1. Objective

Create the Go package `go/internal/web/invoices` with what every later brief of the invoice thread builds on: the route registry, the request entry that runs the Python dependencies in their order (CSRF, then login), the `{id}` 422 rule, the flash, redirect and audit helpers, the exact decimal maths of `App/app/invoices.py` (math/big, no dependency), the host string catalog for all eight briefs, and the empty registration file in `go/cmd/ubyhost-web`. No route is registered yet. This is brief 1 of 8 (1420 to 1427) that port the ten routes of `App/app/routes/invoices.py`; the send route is blocked (1429).

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 no new personal-data field and no new outbound request; 3 fixtures are made up (`@example.test`, no real names); 4 no new dependency (stdlib, pgx and packages already in go.mod); 5 plain PostgreSQL SQL, no schema change; 7 and 10 (screenshots, UX gate) do not apply yet: the pages are not served, no path is in `UBYHOST_GO_PATHS`, and the UX gate is the owner step at the switch (brief 1427, Owner steps).

**All code is pre-written, compiled and tested** by the brief writer in a scratch worktree, in brief order 1420 to 1427. Sidecars live under `docs/tasks/1420-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

| sha256 | file (repo path; sidecar = `docs/tasks/1420-files/<path>.txt`) |
|---|---|
| `eaba2dcc9f07239763a429cf384ca21046b57c8b30702e33f626df3f2e1fb732` | `go/internal/web/invoices/handlers.go` |
| `ee05e3387bcdb1ab60a83fec173a5168f83f094c9d0e8a3215e5b96625cba7c4` | `go/internal/web/invoices/dec.go` |
| `2e2cc74b92195c55e47b84339c6889b637aacffae3de6658f319df82622c5505` | `go/internal/web/invoices/i18n_keys.txt` |
| `56fd8075b9022239a9e36f789eb967994934e3c7eae1ec4f4d4df710fa7d83d2` | `go/internal/web/invoices/i18n.json` |
| `2cd3c2e04800522d03f663f20f1f7e46f7d361234dffa494f0749db9e87ab193` | `go/internal/web/invoices/dec_test.go` |
| `fc340b3d89dfd8e048ab004b5f84719c5d899a92f298190c7f101ec9039faf70` | `go/internal/web/invoices/handlers_test.go` |
| `95e54a49f6a1ffa5e7c0df7b19a9b08bafd0d1097d9c5d0295bd18ea6b16cf32` | `go/internal/web/invoices/i18n_test.go` |
| `1ba3b5a366e7c72b491540991805f12599d23400b1126b34dc7dc03f05107e0f` | `go/cmd/ubyhost-web/register_web_invoices.go` |

Anchors that must exist verbatim (step 0 prints 1 or more): `App/app/templating.py` `def _money_czk(`; `App/app/invoices.py` `def vat_parts(`; `go/internal/hostweb/gate.go` `func CSRF(w http.ResponseWriter` and `func Login(`.

**What the thread ports** (`App/app/routes/invoices.py`, 1,049 lines; Go in `go/internal/web/invoices/`):

| Route | Python function | Brief |
|---|---|---|
| GET /invoices | invoices_list (370-441) | 1423 |
| GET /invoices/{id} | invoice_detail (902-927) | 1423 |
| GET /invoices/{id}.pdf | invoice_pdf_download (883-899) | 1423 |
| POST /invoices/{id}/paid | invoice_mark_paid (930-940) | 1424 |
| POST /invoices/{id}/cancel | invoice_cancel (1004-1027) | 1424 |
| GET /invoice/d/{token} | invoice_download (1030-1049) | 1424 |
| GET /invoices/new | invoice_new (444-489) | 1425 |
| POST /invoices/preview | invoice_preview (790-811) | 1427 |
| POST /invoices | invoice_issue (814-880) | 1427 |
| POST /invoices/{id}/send | invoice_send (961-1001) | 1429, blocked |

Helpers in the same file that are not routes (`save_invoice_details`, `lookup_invoice_details`, `register_lookup`, `apply_account_payload` and the other 0075/0076 functions, lines 492-787) serve the business editor in `admin.py` and belong to the property-settings thread, not to this one.

**How the Go copies Python in this brief:**

- `deps.enter` (handlers.go) is `protect_host_post` (a POST needs a valid CSRF token; `hostweb.CSRF` answers the 403 or the redirect) then `auth.require_login` (`hostweb.Login`). `deps.enterID` is the same for a route with `invoice_id: int`: CSRF, then the id check (a non-number is FastAPI's 422 JSON `int_parsing` body, even for a signed-out visitor, as FastAPI validates before the handler runs), then login. A number too big for int64 is id 0 (no invoice).
- Flash and back: `c.flash(key, params)` is `admin_helpers.flash`, `c.back(path, msg, err)` is `admin_helpers.back` through `hostweb.Back`. `c.audit` is `db.audit`: actor = username, owner = workspace, impersonator when impersonating (as `go/internal/web/stayfees` does).
- `dec.go` is `_parse_decimal`, `_to_decimal`, `_to_int`, `_to_rate` and `vat_parts` (invoices.py 77-114) on `math/big.Rat`, half-up rounding away from zero as `Decimal.to_integral_value(ROUND_HALF_UP)`. `moneyCZK` is the `money_czk` filter (templating.py 60-65: no-break spaces between thousands, an ordinary space before Kč, a plain minus sign). Known differences: only ASCII digits are read (Python's Decimal also reads other Unicode digits), an exponent beyond plus or minus 400 is refused or read as zero. Values were checked against the Python functions (see `TestParseDecimal`, `TestVATParts`).
- `i18n_keys.txt` lists every host string the whole thread reads (220 keys after wildcards); `i18n.json` is its output (`python3 App/scripts/go_host_i18n.py` rewrites it; CI runs `--check`). `TestEveryKeyTheCodeReadsIsInTheCatalog` fails when a later brief names a key that is not listed.
- Registration: each later brief adds a file whose `init()` calls `addRoutes(func(deps) []Route)`; `invoices.Routes(pool, getenv, now)` returns them all and never touches the pool. `register_web_invoices.go` mounts them with `registerRoutes` and the metrics label. No later brief edits `handlers.go` or `register_web_invoices.go`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/handlers.go` | create | package doc, route registry, `enter`/`enterID`, 404/405/422/500 answers, flash, back, audit, form helpers |
| `go/internal/web/invoices/dec.go` | create | decimal maths and `moneyCZK` |
| `go/internal/web/invoices/i18n_keys.txt` | create | host string keys of the whole thread |
| `go/internal/web/invoices/i18n.json` | create | generated catalog (cs, en, vi) |
| `go/internal/web/invoices/dec_test.go` | create | decimal and money tests |
| `go/internal/web/invoices/handlers_test.go` | create | entry, id and static-answer tests; the test clock and environment |
| `go/internal/web/invoices/i18n_test.go` | create | every key the code reads is in the catalog |
| `go/cmd/ubyhost-web/register_web_invoices.go` | create | mounts `invoices.Routes` (owner of this file: the invoice thread) |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/invoices 2>&1 | tail -3` says "No such file"; `ls go/internal/pdf/invoice.go go/internal/billingjob/invoicer.go go/internal/web/stayfees/handlers.go | tail -3` lists all three; `grep -cF 'func CSRF(w http.ResponseWriter' go/internal/hostweb/gate.go` and `grep -cF 'func Login(' go/internal/hostweb/gate.go` each print 1 or more; `grep -cF 'def _money_czk(' App/app/templating.py` and `grep -cF 'def vat_parts(' App/app/invoices.py` each print 1 or more; `grep -c 'registerRoutes' go/cmd/ubyhost-web/registry.go` prints 1 or more; `find docs/tasks/1420-files -name '*.txt' | wc -l` prints `8`.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1420-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")"; cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/invoices/handlers.go go/internal/web/invoices/dec.go go/internal/web/invoices/i18n_keys.txt go/internal/web/invoices/i18n.json go/internal/web/invoices/dec_test.go go/internal/web/invoices/handlers_test.go go/internal/web/invoices/i18n_test.go go/cmd/ubyhost-web/register_web_invoices.go | tail -30
   ```

   All 8 hashes must equal §2. Commit "1420 step 1".

2. Build and test (repo root, one call per line; each ends with `2>&1 | tail -30`). No database is needed: this brief's tests do not use one.

   ```bash
   cd go && gofmt -l internal/web/invoices cmd/ubyhost-web 2>&1 | tail -30
   cd go && go build ./... 2>&1 | tail -30
   cd go && go vet ./internal/web/invoices/... ./cmd/... 2>&1 | tail -30
   cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: the first three print nothing; the last prints `ok  \tgithub.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices\t<time>` and `ok  \t...go/cmd/ubyhost-web\t<time>`. A `FAIL`, a `[build failed]` or a vet line: read the last 30 lines once, then STOP (§8).

3. Write the report (§9) and commit "1420 step 3".

## 5. Do not touch

Everything outside §3. In particular: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/internal/pdf/`, `go/internal/billingjob/`, `go/internal/mail/`, `App/tests/conftest.py`, every Python file under `App/app/`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`, `docs/ENVIRONMENT.md`. Never set `UBYHOST_GO_PATHS`, edit Caddy or compose, push, merge or deploy. Never edit a copied file to make a test pass: a failing sidecar test is a STOP (§8). Hard rules 2, 3, 4, 5 as in §2.

## 6. Commands

Step 3 only, plus from the repo root `python3 scripts/context_lint.py 2>&1 | tail -30` (prints `context lint: OK`). Never the full suite, never `pytest tests`.

## 7. Acceptance

- [ ] The 8 sha256 values match §2.
- [ ] `gofmt -l` prints nothing; `go build ./...` and `go vet` print nothing.
- [ ] `go test` prints `ok` for `internal/web/invoices` and `cmd/ubyhost-web`; with PostgreSQL there is no `--- SKIP` line in `go test -v` (without it the report says "CI only").
- [ ] `go test -count=1 -v -run 'TestParseDecimal|TestVATParts|TestMoneyCZK|TestEveryKey|TestBadID' ./internal/web/invoices/ 2>&1 | grep -c '^--- PASS'` (from `go/`) prints 5.
- [ ] `go list ./internal/web/invoices/ 2>&1 | tail -3` prints the package path (it compiles with no route).
- [ ] `git log --oneline --grep='^1420 step' | tail -5` shows the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1420 step') | tail -30` lists only §3 paths.
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

Write `docs/tasks/1420-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`dec.go` against invoices.py 77-114 and templating.py 60-65: every amount on every invoice goes through it (rounding half up away from zero, the 10,000,000 limit, "abc" reads as 0, an empty VAT rate reads as 0 % while an unknown one reads as 12 %). `handlers.go` `enter` and `enterID`: the order CSRF, id, login; `audit` (the actor and impersonator columns). `i18n_keys.txt` is data only; skim for a key that carries personal data (none should). Nothing here reads guest data.

## Owner steps

None: nothing is switched on. The pages stay dormant until the owner adds paths to `UBYHOST_GO_PATHS` (listed in brief 1427, Owner steps).
