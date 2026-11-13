# 1353: Go host payments pages (switched off)

Status: todo
Depends on: 1380 (draft PR #985, branch task/1380-go-host-layout) | Base commit: fe42cc4 | Branch: task/1353-go-payments-host-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (host payments pages, privacy-relevant links) | Review: Opus reads the diff of the risk-listed files

## 1. Objective

Port the host payments pages of `App/app/routes/payments.py` to a new Go package `go/internal/payments/pages` (GET /payments, GET /payments/new, POST /payments/services, POST /payments/services/{id}/delete, GET /payments/requests/{id}/share, GET and POST /payments/consent) on the shared Go layout of 1380. Nothing goes live: Caddy sends a path to Go only after the owner adds it to `UBYHOST_GO_PATHS`, so Python keeps serving every page until then.

## 2. Context

All code in the bundle (§4 step 1) is pre-written and was dry-run green on the base commit: `go build ./...`, `go vet ./...`, `gofmt -l`, `go test` of `./internal/payments/...`, `./internal/payments/pages/`, `./cmd/ubyhost-web/`, `./internal/hostweb/...` against Postgres 16 (the golden test runs 28 page cases and 17 writes, all equal to Python), the golden script `--check`, `go_host_i18n.py --check`, and `pytest tests/test_payments*.py tests/test_go_payments_pages_golden.py`. You copy it in with one command (§4 step 1), generate two files with the repo's own scripts, and verify. Do not edit any file.

What the code does (for the reviewer; you need not read the code):

- **API used (1380, `go/internal/hostweb/layout`):** `layout.MustParse(cat, files, "templates/*.tmpl")` once, then `layout.Render(w, r, layout.Env{Pool, Getenv, Now}, host, layout.Page{Title, Nav, BodyKind, V2, HowKey}, pages, "<name>", data)` after `hostweb.Login`. A page defines `{{define "<name>"}}`; `payments`, `payments_new` and `payments_consent` define an empty `"<name>.title"` because their Python `page_title` block is empty (the h1 is in the body). `payments_share` keeps the default h1 (Page.Title). The page is buffered, so a failed render is a clean 500.
- **Python logic matched:** `_connect_state` (stripe_account row for `UBYHOST_STRIPE_MODE`), `_setup` (consent audit row `payments_terms_accepted` / `version=2026-11-01`, first non-archived legal_entity by id, the four steps and the next button), `payment_request.for_owner` (100 newest), `_stays`/`_stay_label`, `payment_request.has_bank_account`, `payment_services.list_for/get/add/remove` (JSON in `settings` key `payment_services:<owner>`, rewritten byte for byte as Python's `json.dumps(..., ensure_ascii=False)` with every item's keys kept in order: `pyjson.go`), `payments_consent.accepted/record` (audit row with actor = account username, actor_user_id, impersonator_user_id when impersonating), the `date_cz` filter, flashes through `hostweb.Back` in the host's language, `fix=stripe` on not_ready. POSTs run `hostweb.CSRF` first, then `hostweb.Login`, as `security.protect_host_post` then `auth.require_login`. Form fields and query values use the last value, as Starlette's `.get`.
- **Share page:** calls the existing `payments.LinkSender` (`payments.NewStripeOnboarder(...).SendPaymentLink`, read-only use of `go/internal/payments`). `payments.ErrStripeOff` gives `payments.err.stripe_off`, `""` gives `payments.err.not_ready` with `fix=stripe`.
- **Coordinator rule (layout thread, until 1381 adds safeHref):** no user-controlled or DB-stored URL goes into a layout macro's `href`. The share page's mailto and WhatsApp buttons are plain `<a href="{{.MailtoURL}}">` / `<a href="{{.WhatsAppURL}}">` in the package's own template (html/template checks the scheme; the values have a fixed `mailto:` / `https://wa.me/` prefix and a percent-encoded rest, as Python's `quote`). The payment link itself is only an `<input value>`. `TestShareNeverLinksJavascript` stores `javascript:alert(1)` as guest e-mail and `javascript:alert(1)//` as the link and checks that no `href` starts with `javascript:`. Macro hrefs used: only constants and `/entities?edit=<integer id>`.
- **Routes:** `go/cmd/ubyhost-web/register_web_payments_pages.go` registers 7 patterns through `registerRoutes` (registry.go). The route function builds handlers only; nothing touches the pool while building. No pattern overlaps `register_web.go`: `GET /payments/requests/{id}/share` differs from the existing POST `.../link` and `.../send` by path or method.
- **Gaps (stay on Python, listed for a later brief):** `GET /payments/qr/{id}` (host QR preview) and `GET /pay/{id}/{token}` (guest bank-transfer page) extend `base.html` directly with `show_nav = False` and no host_page frame. Layout 1380 always wraps the body in the host_page frame (`<div class="ui-page">`), so it does not offer `base.html` for these two. Also, their paths are the same mux patterns as the PNG routes already in `register_web.go` (`GET /payments/qr/{file}`, `GET /pay/{id}/{file}`); Go's ServeMux panics on a second registration, so a later brief must either edit those two lines in `register_web.go` to a dispatcher (`<digits>.png` to the unchanged PNG handler, anything else to the HTML page) or have Caddy keep the HTML paths on Python (`/payments/qr/*.png` is already the documented `UBYHOST_GO_PATHS` form).
- **Where Go may differ from Python (all edge cases, none reachable from the real forms):** a non-integer `{id}` on the share page is 404 (FastAPI 422); only ASCII digits count as digits (Python's `isdigit` also takes other Unicode digits, and `int()` then may 500); an amount too large for int64 is "services.err" (Python: the same flash); a hand-edited services setting holding NaN/Infinity is "no services" (Python loads it), a lone surrogate becomes U+FFFD, and a list/dict as a service name prints as JSON (Python prints its repr); the overview does not run Python's unused `_stays` and `prefill` reads (no visible effect).
- **Tests:** `App/scripts/payments_pages_golden.py` seeds a fixture (5 hosts: Stripe off / none / pending / complete / rejected / action-free with a live-mode-only row, services empty / 2 with an extra key and junk entries / 20 full / bad JSON, consent given / old version / not given, cs and en) into a throwaway SQLite DB, runs the real FastAPI routes with the TestClient (`payment_links.send` replaced by fixed answers, no network) and writes `testdata/golden.json`: status, Location, `<title>`, and for each page the visible text, the form fields and the links of the body region (from `<div class="ui-page"` to `<div class="page-skeleton"`; the shell is 1380's golden), plus after each write the `payment_services:*` settings and the consent audit rows. `TestGoldenMatchesPython` seeds the same fixture into Postgres and compares with the same `summarise`. `App/tests/test_go_payments_pages_golden.py` fails when golden.json is stale.
- **Rules 7 and 10 (pre-switch, not now):** 1380 has no Go layout-lint harness. Before the owner adds any of these paths to `UBYHOST_GO_PATHS`, a later brief must run `test_layout_lint_browser.py` and the payments browser tests against the Go pages with 0 skipped and take the 390/768/1280 screenshots. Also 1381 (host alerts) must have landed (layout.go says Go pages must not go live before it).

## 3. Files

| Path | Action | sha256 | What |
|---|---|---|---|
| go/internal/payments/pages/pages.go | create (844 lines) | 05d75bb9bc67df32d0bcc236be819bb1715b614644df5b55b6310321a7cab095 | handlers, reads and writes |
| go/internal/payments/pages/pyjson.go | create (312 lines) | 24c1fbd5c834dfb1b0b2d85101ab342d855279181a033eb8087d97b567572485 | ordered JSON load/dump as Python's json |
| go/internal/payments/pages/pages_test.go | create (546 lines) | 62dfb90145a9e49c1ca68ea051b72a0dc2417d530b1dff847e17278c300e65b7 | golden, javascript-href, refusal and unit tests |
| go/internal/payments/pages/templates/payments.tmpl | create (101 lines) | 357e919a3e3d9f2b9e12f5ba200e328c226eb753bb39d33b0beeff413ee98e04 | payments.html |
| go/internal/payments/pages/templates/payments_new.tmpl | create (40 lines) | eb6f44e42fc8f2268a040a15bda41409cc24dbf1458011651208b828dda0bb07 | payments_new.html |
| go/internal/payments/pages/templates/payments_share.tmpl | create (20 lines) | 20cfa1a8af853fab250e662a2af4780f330f1da848e462663b4696d610f4e19b | payments_share.html |
| go/internal/payments/pages/templates/payments_consent.tmpl | create (22 lines) | 380492d411b30e5c26992c766bd71a171627f47eb9655a5e20e671107755c9fa | payments_consent.html |
| go/internal/payments/pages/i18n_keys.txt | create (137 lines) | 0af371ac4dd841b571395f92c0b1778545446fd8cc0b7a7e4c901c2318564e45 | catalog keys |
| go/cmd/ubyhost-web/register_web_payments_pages.go | create (30 lines) | 2bc543833e5e832d6d2236fee69e773518e2a13c5e0b3e47a28faf8a2a12650c | registerRoutes, 7 patterns |
| App/scripts/payments_pages_golden.py | create (335 lines) | 1e5a58ec3b52704d2e6eae0ed5c14a9a071b6c5f5f531b1e1bcd5d370e362b30 | writes testdata/golden.json |
| App/tests/test_go_payments_pages_golden.py | create (17 lines) | ef346de4efa7973f11805a34c62d78e8bff2dc073be408d9d304fe35c573da3f | golden.json is current |
| go/internal/payments/pages/i18n.json | create | ea154757da377ae80df20608865faae4b199981088f0524f9648cda8a5a850a5 | generated by go_host_i18n.py (step 2) |
| go/internal/payments/pages/testdata/golden.json | create | d1dcd98f5994eec08014edf6cd51e52e7c7d4e6594a889b7e75241b67d25b734 | generated by payments_pages_golden.py (step 3) |
| docs/tasks/1353-go-payments-host-pages.md | edit | (this file) | Status only |
| docs/tasks/1353-go-payments-host-pages.files.txt | delete (step 1) | n/a | the code bundle |
| docs/tasks/1353-report.md | create | n/a | your report |

No other file may change. `App/.venv/` is git-ignored; leave it untracked.

## 4. Steps

Run everything from the repo root unless a step says `cd App`.

1. Extract the files from the bundle `docs/tasks/1353-go-payments-host-pages.files.txt` (one command; never open the bundle: it is ~2400 lines of code; the command prints the first 12 hex of each sha256), then delete the bundle:

   ```bash
   python3 - <<'EOF' 2>&1 | tail -30
   import hashlib, pathlib, re
   brief = pathlib.Path("docs/tasks/1353-go-payments-host-pages.files.txt").read_text(encoding="utf-8")
   blocks = re.findall(r"<!-- file: (\S+) -->\n~~~~[a-z]*\n(.*?)\n~~~~\n", brief, re.S)
   for path, body in blocks:
       p = pathlib.Path(path)
       p.parent.mkdir(parents=True, exist_ok=True)
       p.write_text(body + "\n", encoding="utf-8")
       print(hashlib.sha256(p.read_bytes()).hexdigest()[:12], path)
   print(len(blocks), "files")
   EOF
   ```

   Expect `11 files` and each prefix equal to the §3 sha256. A mismatch: STOP (§8). Then `git rm -q docs/tasks/1353-go-payments-host-pages.files.txt` and commit `1353 step 1`.

2. Python venv (skip the install when `App/.venv/bin/python` exists), then generate the catalog:

   ```bash
   cd App && (test -x .venv/bin/python || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt)) 2>&1 | tail -5
   cd App && .venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -5
   sha256sum go/internal/payments/pages/i18n.json
   ```

   Expect `wrote .../go/internal/payments/pages/i18n.json` (only that file) and the §3 sha256. Commit `1353 step 2`.

3. Generate the golden file:

   ```bash
   cd App && .venv/bin/python scripts/payments_pages_golden.py 2>&1 | tail -1
   sha256sum go/internal/payments/pages/testdata/golden.json
   ```

   Expect `wrote go/internal/payments/pages/testdata/golden.json: 28 cases, 17 writes` and the §3 sha256. A different sha256: STOP (§8), do not commit the file. Commit `1353 step 3`.

4. Start a throwaway Postgres 16 for the Go DB tests (skip if `pg_isready -h 127.0.0.1 -p 55453` already says accepting):

   ```bash
   mkdir -p /var/tmp/pg1353 && chown postgres /var/tmp/pg1353 && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1353 -A trust" 2>&1 | tail -2
   su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1353 -o '-p 55453 -k /tmp' -l /var/tmp/pg1353.log start" 2>&1 | tail -2
   ```

5. Run every command of §6 in order. Then write the report (§9).

## 5. Do not touch

- `go/internal/payments/*.go` (another brief changes that package in parallel; this brief only imports it), `go/internal/hostweb/**` (1380/1381), `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, `go/internal/jobs/`, `go/internal/mail/`, `App/app/**`, `App/tests/conftest.py`, `docs/ENVIRONMENT.md`, `docs/context/*`.
- No new dependency (rule 4): the code uses the standard library, pgx and the repo's own packages only.
- Never register a bare `"GET /"`; never add any path to `UBYHOST_GO_PATHS` (owner only).
- Rule 2: no new outbound request. The share page reuses the existing Stripe Payment Link call (`SendPaymentLink`, the same request Python's `payment_links.send` makes: to create or reuse the guest's card payment link); the tests replace it with a fake.
- Rule 3: the fixture holds only made-up names and `example.test` addresses.

## 6. Commands

```bash
cd go && go build ./... 2>&1 | tail -30
cd go && go vet ./... 2>&1 | tail -30
cd go && gofmt -l . 2>&1 | tail -30
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55453/postgres go test -count=1 ./internal/payments/... ./cmd/ubyhost-web/... ./internal/hostweb/... 2>&1 | tail -30
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55453/postgres go test -count=1 -v -run 'TestGoldenMatchesPython|TestShareNeverLinksJavascript|TestRefusals' ./internal/payments/pages/ 2>&1 | grep -c -- '--- PASS'
cd App && .venv/bin/python scripts/payments_pages_golden.py --check >/dev/null 2>&1; echo "golden rc=$?"
cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -3
cd App && .venv/bin/python -m pytest tests/test_payments*.py tests/test_go_payments_pages_golden.py -q -x -rs 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -5
```

Expected: build, vet and gofmt print nothing; `go test` prints `ok` for every package (none FAIL; `internal/payments/pages` must not say `no tests to run` or skip: the DB URL must be set); the PASS count is `48` (3 top tests + 45 golden subtests); golden check prints `golden rc=0`; i18n check prints nothing; pytest ends `33 passed, 5 skipped` (the 5 skips are the payments browser tests without playwright: `could not import 'playwright.sync_api'`; anything else skipped or failed: STOP); context lint ends `context lint: OK`.

## 7. Acceptance

- [ ] `git diff --stat fe42cc4` lists exactly the 13 created files of §3 plus this brief and the report (the bundle is added and deleted on this branch, so it is not listed).
- [ ] Each created file's sha256 equals §3.
- [ ] Every §6 command gives the expected output.
- [ ] `grep -c 'mux.Handle' go/cmd/ubyhost-web/register_web_payments_pages.go` prints `7`.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found or a sha256 differs;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1353-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat fe42cc4`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/payments/pages/pages.go`: the SQL (owner scoping on every read and write), CSRF before Login on the three POSTs, the consent audit row, the services rewrite.
- `go/internal/payments/pages/pyjson.go`: the byte-for-byte `json.dumps` of the services setting.
- `go/internal/payments/pages/templates/payments_share.tmpl`: the mailto/WhatsApp hrefs (plain `<a>`, no macro).
- `go/cmd/ubyhost-web/register_web_payments_pages.go`: the 7 patterns, no overlap with `register_web.go`.

## Owner steps

None for this PR: it adds code that nothing routes to. Later, after 1381 and the pre-switch browser checks (§2), the owner adds the paths to `UBYHOST_GO_PATHS`; a later brief will give those steps.
