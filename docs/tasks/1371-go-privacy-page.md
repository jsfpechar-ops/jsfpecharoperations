# 1371: Go privacy requests GET page, plus two 1370 review fixes

Status: todo
Depends on: #985 merged to main; executor first runs `git merge origin/main` on the branch. 1370 (#979, this branch). | Base commit: 3c30e5f | Branch: task/1370-go-privacy-requests
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (the code is extracted by a command from the 1371a code file, never read or pasted by hand)

## 1. Objective

Port `GET /privacy-requests` (App/app/templates/privacy_requests.html) to `go/internal/web/privacy/` on the shared host layout from #985, pinned by a Python golden of the rendered page content. Also fix two 1370 review findings: a path id beyond int64 gave a 500 in Go, and no golden step sent `_csrf` in the form body (the no-JS browser path).

## 2. Context

Rules that apply (AGENTS.md): 2 no new personal-data field, no outbound request; 3 fixtures use `@example.test` accounts, no names; 4 no new dependency (stdlib, pgx, repo packages); 5 plain SQL through pgxpool; 7 and 10 apply to a host page, see "Browser tests" below. Filing code is not touched.

What the code does (orchestrator and reviewer reference; the executor needs only §4):

- **Page.** `ListHandler`: `hostweb.Login` (no CSRF on GET, as FastAPI), `ListForOwner(workspace)`, then `layout.Render(..., layout.Page{Title: t("privacy_requests.title"), Nav: "privacy_requests", BodyKind: "list", V2: true}, pages, "privacy_requests", data)`. The template has an empty `privacy_requests.title` slot (Python empties `page_title`, so the shell header is skipped) and puts the settings back header (`/settings`, `common.back`, `arrow-left` 20) in the body, as `partials/settings_back_header.html` does. The form fields, the options from the 1370 constants, the labels, the `selected` status, `open` on the details element only when the list is empty, the guest id only when set, and the identity checkbox only when unchecked follow the Jinja line by line. `due_at` uses the layout's `datetime_local`; `received_at` uses `dateCZ`, a port of `validation.fmt_date` (strptime `%Y-%m-%d` on the first ten characters, else the value as stored), since the layout has no `date_cz` func. Only fixed paths go into `href`/`action`: `/settings`, `/privacy-requests`, `/privacy-requests/{{.ID}}` (an int64).
- **Page golden.** `App/scripts/privacy_requests_page_golden.py` mounts the real router with `require_login`/`owner_id` replaced (as the 1370 golden does), GETs the page for `owner_en`, `owner_cs` (six requests: every status, a NOTE with `<b>"'&+`, a Czech note, odd and invalid dates, a guest id, identity set and unset, plus one `owner_user_id NULL` row that must not show) and `empty_vi` (no requests: details open, empty text). It stores the status, `<title>` and the region from `<div class="ui-page"` up to the page skeleton, with `_csrf` values replaced by `CSRF`, plus 12 `fmt_date` cases. `page_test.go` seeds Postgres from the same file, signs in for real, renders the Go page, and compares the region item by item: every text run (unescaped, whitespace collapsed), every start tag with its sorted attributes, and every end tag (inside `<svg>` only the svg tag). Content parity, not bytes. The shell outside the region is #985's own golden.
- **Fix (b), beyond int64.** pydantic accepts `/privacy-requests/99999999999999999999` as an int. Python on PostgreSQL then gets no row from `dsr.get` (bigint = numeric; the brief writer checked this on PG 16 for +-99999999999999999999 and int64 max), so it answers `/login?next=...` signed out and `no_such_dsr` signed in. SQLite raises OverflowError instead, so the golden script wraps `dsr.get` to answer None beyond int64, as PostgreSQL does. Go keeps the 422 for non-ints, runs the login check, then answers `no_such_dsr` without a query. New steps: `update_beyond_int64_signed_out` (account 0 runs the real `require_login` with no session), `update_beyond_int64`, `update_below_int64_cs`, `update_int64_max`.
- **Fix (c), `_csrf` in the body.** A body containing `@CSRF@` goes through the real `protect_host_post` in Python (a second app with no override, a real token and the `ubyhost_csrf` cookie) and, in Go, gets the minted token in place of `@CSRF@` and no `x-csrf-token` header. Steps `update_csrf_in_body` and `create_csrf_in_body` (before the last step, which must stay last).
- **#986 (1382, hostweb fixes):** checked in the dry run. 1370's code and golden pass with it merged, and so does all of 1371. Its Starlette-style `Location` quoting does not change any Location in either golden, and its multipart CSRF does not touch these url-encoded posts. No dependency either way.
- **Browser tests (rules 7 and 10).** `App/tests` browser, geometry and layout-lint tests (`test_layout_lint_browser.py`, `test_0786_settings_geometry_browser.py`, which already covers `/privacy-requests`) start only the Python app. No fixture runs `ubyhost-web` or Caddy, so a Go page cannot be reached from them until it is switched on. The executor does not fake this: the 390/768/1280 screenshots and the layout lint of the Go page are an owner/coordinator step after the switch (owner steps below). Until then `/privacy-requests` keeps being served and browser-tested by Python.

**Verified by the brief writer** in a scratch worktree (origin/task/1380-go-host-layout 0bd8c2c merged with this branch at 3c30e5f; repeated with #986 513629d and origin/main 488a783 merged too): every hash below, `gofmt -l .` empty, `go vet ./...` clean, `go test ./internal/web/privacy/ ./cmd/ubyhost-web/ ./internal/hostweb/...` ok with PostgreSQL 16 (`--- PASS: TestPrivacyRequestsGolden`, `TestPrivacyRequestsPageGolden`, `TestListForOwnerDatabase`, not skipped), the pytest command green, both golden scripts deterministic, `go_host_i18n.py --check` clean. Mutations caught: 1370's old handler (500 on both beyond-int64 steps), and seven template edits (no `open`, no `selected`, empty note value, no guest id, raw `received_at`, wrong button class, raw `due_at`).

Anchors that must exist verbatim after the merge (step 0): `func MustParse(cat hostweb.Catalog, fsys fs.FS, patterns ...string) *Templates {` and `func Render(w http.ResponseWriter, r *http.Request, env Env, host *session.Host, p Page, tpl *Templates, name string, data any) error {` in go/internal/hostweb/layout/layout.go; `"datetime_local":        datetimeLocal,` in go/internal/hostweb/layout/funcs.go; `@router.get("/privacy-requests")` in App/app/routes/privacy_requests.py; `def fmt_date(value: Optional[str]) -> str:` in App/app/validation.py.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/web/privacy/handler.go | edit (whole file from 1371a) | beyond-int64 id is `no_such_dsr` after login |
| go/internal/web/privacy/handler_test.go | edit (whole file) | signed-out steps, `@CSRF@` body token |
| go/internal/web/privacy/page.go | create | `ListHandler`, `pageData`, `dateCZ`, `pages` |
| go/internal/web/privacy/templates/privacy_requests.tmpl | create | the page body |
| go/internal/web/privacy/page_test.go | create | `dateCZ` vs Python, extractor test, page golden on Postgres |
| go/internal/web/privacy/i18n_keys.txt | edit (whole file) | plus 34 `privacy_requests.*` keys |
| go/internal/web/privacy/i18n.json | edit (whole file) | generated from host_i18n.py |
| go/cmd/ubyhost-web/register_web_privacy.go | edit (whole file) | plus `GET /privacy-requests` |
| App/scripts/privacy_requests_golden.py | edit (whole file) | six steps, real login for account 0, real CSRF for `@CSRF@` |
| App/scripts/privacy_requests_page_golden.py | create | the page golden generator |
| App/tests/test_go_privacy_requests.py | edit (whole file) | plus the page golden freshness test |
| go/internal/web/privacy/testdata/privacy_requests_golden.json | regenerate | by step 2, never by hand |
| go/internal/web/privacy/testdata/privacy_requests_page_golden.json | create | by step 2, never by hand |
| docs/tasks/1371-go-privacy-page.md | edit | Status only |
| docs/tasks/1371a-go-privacy-page-code.md | none | the code blocks; never edit |
| docs/tasks/1371-report.md | create | report |

No other file may change (the files `git merge origin/main` brings in are not yours).

## 4. Steps

0. From the repo root, on branch `task/1370-go-privacy-requests` with a clean tree: merge main, then check the anchors, that the files 1371 replaces are still 1370's, and that the new ones do not exist:
   ```bash
   git fetch origin main 2>&1 | tail -2; git merge --no-edit origin/main 2>&1 | tail -3
   grep -cF 'func MustParse(cat hostweb.Catalog, fsys fs.FS, patterns ...string) *Templates {' go/internal/hostweb/layout/layout.go; grep -cF 'func Render(w http.ResponseWriter, r *http.Request, env Env, host *session.Host, p Page, tpl *Templates, name string, data any) error {' go/internal/hostweb/layout/layout.go; grep -cF '"datetime_local":        datetimeLocal,' go/internal/hostweb/layout/funcs.go; grep -cF '@router.get("/privacy-requests")' App/app/routes/privacy_requests.py; grep -cF 'def fmt_date(value: Optional[str]) -> str:' App/app/validation.py
   sha256sum go/internal/web/privacy/handler.go go/internal/web/privacy/handler_test.go go/internal/web/privacy/i18n_keys.txt go/internal/web/privacy/i18n.json go/cmd/ubyhost-web/register_web_privacy.go App/scripts/privacy_requests_golden.py App/tests/test_go_privacy_requests.py | tail -30
   ls go/internal/web/privacy/page.go go/internal/web/privacy/page_test.go go/internal/web/privacy/templates App/scripts/privacy_requests_page_golden.py 2>&1 | tail -30
   ```
   Expected: the merge succeeds without conflicts (a conflict, or `go/internal/hostweb/layout` missing, means #985 is not merged yet: STOP, §8); five lines `1`; these hashes:
   ```
   7a39677f9fa8ec450c13cb22ba60a536abd785910dab82f74bd6e01adc3e8ff2  go/internal/web/privacy/handler.go
   d5c26f8ba3261c736b10a11cb4329fe8b72221946401e2ed0013481b6510f5a7  go/internal/web/privacy/handler_test.go
   8a15c232a190aa2d37771b1057c30f36fa24310541a1b33317456145e7d01ea0  go/internal/web/privacy/i18n_keys.txt
   e47719b24e12e98b07359368ccdb29dcd800f6956e3a4c36b5c52200d8ec474e  go/internal/web/privacy/i18n.json
   af6708bf5d896248c2e6b0ac32fd6cd375ea3919fdd4ef5549bd4ceca9c34499  go/cmd/ubyhost-web/register_web_privacy.go
   0591fb34cb26c1cc251214d2682ee1f4280f18db0669ddf826677ea2b7f34c8e  App/scripts/privacy_requests_golden.py
   d1499ca8883cacfe1fb56bb35fec70cbde04ba220fdfc334ffa7cc491759d2cd  App/tests/test_go_privacy_requests.py
   ```
   then four "No such file or directory". Anything else: STOP (§8). The merge commit is the step 0 commit (no other commit).

1. Extract the eleven files from [the code file](1371a-go-privacy-page-code.md) (do not open it, do not retype anything; it overwrites the seven files above), then check their hashes. From the repo root:
   ```bash
   python3 - <<'PY' 2>&1 | tail -30
   import pathlib, re
   text = pathlib.Path("docs/tasks/1371a-go-privacy-page-code.md").read_text(encoding="utf-8")
   for m in re.finditer(r"^````[a-z]+ path=(\S+)\n(.*?)^````$", text, re.M | re.S):
       path = pathlib.Path(m[1])
       path.parent.mkdir(parents=True, exist_ok=True)
       path.write_text(m[2], encoding="utf-8")
       print("wrote", path)
   PY
   sha256sum go/internal/web/privacy/handler.go go/internal/web/privacy/handler_test.go go/internal/web/privacy/page.go go/internal/web/privacy/page_test.go go/internal/web/privacy/templates/privacy_requests.tmpl go/internal/web/privacy/i18n_keys.txt go/internal/web/privacy/i18n.json go/cmd/ubyhost-web/register_web_privacy.go App/scripts/privacy_requests_golden.py App/scripts/privacy_requests_page_golden.py App/tests/test_go_privacy_requests.py | tail -30
   ```
   Expected: eleven `wrote` lines, then exactly:
   ```
   6ac92fbc68bbb6cc837f35bae85bf23461ddf34ef73234a2543f2540ec785e4b  go/internal/web/privacy/handler.go
   63f8537f8dbfa5efc576464f560075fa3df361b2b670708af78ac5b8ee47069c  go/internal/web/privacy/handler_test.go
   11e4d333d723fbeeb6897823c50eb18f1229215400836b8d37ba18cfe7162ad7  go/internal/web/privacy/page.go
   692b904f74c5d983275cb21b00d1466c7703a80087aea9e7114b12ed5d9aee1c  go/internal/web/privacy/page_test.go
   26e3fb1d66ca8cc1c224a31beb6dea2e32236ed061bdd5708d001a6d4a5a51d5  go/internal/web/privacy/templates/privacy_requests.tmpl
   627ebf2490c4c0f2c008d2157600be768834ff7b658f0a9f5da94120cf2c4ae5  go/internal/web/privacy/i18n_keys.txt
   a756fe119f492b3c2441c8e4769f7066e8cc4aa441bd3943cd38df248c7be1ef  go/internal/web/privacy/i18n.json
   57e8c67e3fc4d066871ddbf68e056eb9253738fa13d0b059d10cf08cd9059b69  go/cmd/ubyhost-web/register_web_privacy.go
   98e257f718b955a77b50019cfe374fd0c125f024fec4226b3ebfb9b56e70152b  App/scripts/privacy_requests_golden.py
   5ee0218787420b26d7caebca4bf83022f343833805fcce17ef9fbdbf430f6ae8  App/scripts/privacy_requests_page_golden.py
   ad99f70c3e0932cdebefd38fd45a40eeffbe35fd1b0cbd48cb17e769fb6cce02  App/tests/test_go_privacy_requests.py
   ```
   A different hash: STOP (§8); never edit a file to make it match. Commit "1371 step 1" (the eleven files).

2. Generate both goldens and the catalog check. If `App/.venv` is missing, first from `App/`: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Then from `App/`:
   ```bash
   .venv/bin/python scripts/privacy_requests_golden.py 2>&1 | tail -2; .venv/bin/python scripts/privacy_requests_page_golden.py 2>&1 | tail -2; .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -3; sha256sum ../go/internal/web/privacy/testdata/*.json | tail -3
   ```
   Expected: two `wrote` lines, nothing from `--check`, and:
   ```
   140edee5cbe87ab410b8e556a0347c7bfca6d1bfe58debf07258cc907b1e5732  ../go/internal/web/privacy/testdata/privacy_requests_golden.json
   642ef7c399287d4a5558cf3e16d4695236ae21c0fe67b169a2a5fe2b7696d5da  ../go/internal/web/privacy/testdata/privacy_requests_page_golden.json
   ```
   A different hash: STOP (§8); never edit the JSON. (A change to host_i18n.py strings on main after 488a783 would change them: that is a STOP and a question, not a fix.) Commit "1371 step 2".

3. Run the §6 commands (Go, then Python, then the lint). Optional, if a local PostgreSQL 16 is at `/usr/lib/postgresql/16`: start one as the postgres user with its data dir outside `/tmp/claude-0` (for example `/var/tmp/pg1370`) and rerun the Go command with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/postgres` and `-v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`; `--- PASS: TestPrivacyRequestsGolden` and `--- PASS: TestPrivacyRequestsPageGolden` must appear. Without it write "DB tests: CI only" in the report. No commit unless something changed (nothing should).

4. Set this brief's `Status: review`, write `docs/tasks/1371-report.md` (§9), commit "1371 step 4". Do not push.

## 5. Do not touch

Read-only: go/internal/hostweb/ (including layout/), go/internal/session/, go/internal/jobs/, go/cmd/ubyhost-web/main.go, registry.go, register_web.go, App/tests/conftest.py, every file under App/app/, App/scripts/go_host_i18n.py, Caddy files, deploy/. Never edit docs/ENVIRONMENT.md, status.md, test-map.md, decisions.md, known-issues.md, or the 1370 brief and code file. No new Go or Python dependency (rule 4). Never a bare `GET /`. Until brief 1381 lands with its safeHref filter, no user-controlled URL goes into a layout macro's `href` argument; only fixed paths (`/settings`, `/privacy-requests`) are allowed (this template passes none to a macro). Never add `/privacy-requests` to `UBYHOST_GO_PATHS`. No push, merge to main, secrets, servers or `.env`.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/web/privacy/ ./cmd/ubyhost-web/ ./internal/hostweb/... -count=1 2>&1 | tail -30` (expected `ok` four times; the DB tests skip without `UBYHOST_TEST_DATABASE_URL` and run in CI).
From `App/`: `.venv/bin/python -m pytest tests/test_go_privacy_requests.py tests/test_go_host_i18n.py tests/test_privacy_requests.py tests/test_go_layout_golden.py -q --tb=short -x 2>&1 | tail -30` (expected all passed).
Golden freshness: from `App/`, `.venv/bin/python scripts/privacy_requests_golden.py >/dev/null 2>&1; .venv/bin/python scripts/privacy_requests_page_golden.py >/dev/null 2>&1; git status --short ../go | tail -30` prints nothing after step 2's commit.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` ends `context lint: OK`.

## 7. Acceptance

- [ ] Step 0: clean merge of origin/main, five `1` lines, the seven 1370 hashes, four missing paths.
- [ ] Step 1: the eleven hashes match; step 2: both golden hashes match and `--check` is silent.
- [ ] From `go/`: gofmt empty, `go vet ./...` clean, four packages `ok`.
- [ ] DB tests: `--- PASS: TestPrivacyRequestsGolden` and `--- PASS: TestPrivacyRequestsPageGolden` locally, or "CI only" in the report.
- [ ] The pytest command passes and the freshness command prints nothing.
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat origin/main..HEAD -- go App docs/tasks/1371* | tail -30` lists only §3 paths plus 1370's own files.
- [ ] Commits: the merge, "1371 step 1", "1371 step 2", "1371 step 4"; nothing pushed.
- [ ] No screenshots from the executor: the Go page is not reachable from the browser tests yet (§2). The report says so.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- the merge of origin/main conflicts, #985's layout package is missing, an anchor is not found, a step 0 hash differs, or a new §3 file already exists;
- a hash in step 1 or 2 differs (never edit a file, the JSON, the Python or the Go to make it match);
- `TestPrivacyRequestsGolden` or `TestPrivacyRequestsPageGolden` fails (any Go/Python mismatch is a question for the orchestrator), or any test fails twice;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a new dependency seems needed, a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, a PR, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1371-report.md` (600 tokens at most) and set `Status: review`. It has: 1. `git diff --stat origin/main..HEAD | tail -20`; 2. each §6 command (and the optional DB run) with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left (the browser check below).

## Risk list (for the reviewer)

Read `templates/privacy_requests.tmpl` side by side with App/app/templates/privacy_requests.html and partials/settings_back_header.html; `page.go` (`ListHandler` order: Login, ListForOwner(workspace), Render; `dateCZ` against validation.parse_iso_date); the `beyond` branch in `handler.go`; the `@CSRF@` and account-0 paths in `handler_test.go` and `privacy_requests_golden.py` (the `pg_get` wrapper is the only Python behaviour the golden emulates, and it is PostgreSQL's); `pageContent` in `page_test.go` (it must not drop text or attributes). Check in CI that `TestPrivacyRequestsPageGolden` runs, not skips. Accepted divergences: `dateCZ` reads ASCII digits only (strptime also takes other Unicode digits); `<title>` comes from #985's shell. Caddy's `@go path` matcher is method-blind, so `/privacy-requests` must go into `UBYHOST_GO_PATHS` only when GET and both POSTs are all served by Go, which is the case after this brief, and only after brief 1381 (host alerts, which carry filing warnings) is merged.

## Owner steps

None to merge this brief: nothing is switched on. Later, when the coordinator says 1381 is merged and the Go pages may go live:

1. On staging only, add `/privacy-requests` and `/privacy-requests/*` to `UBYHOST_GO_PATHS` and restart, as for the earlier Go paths.
2. The coordinator then has an orchestrator run the rule 7/10 check against staging: `test_layout_lint_browser.py` for `/privacy-requests`, and the 390/768/1280 screenshots, with what was seen written in the PR.
3. Only then add the same paths in production.
