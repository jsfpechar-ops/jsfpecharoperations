# 1370: Go port of the privacy request POST handlers

Status: review
Depends on: none | Base commit: a83df54 | Branch: task/1370-go-privacy-requests
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (the code is extracted by a command from the 1370a code file, never read or pasted by hand)

## 1. Objective

Port the two POST routes of `App/app/routes/privacy_requests.py` (create and update a data-subject request) to a new Go package `go/internal/web/privacy/`, with the `dsr.py` store functions, `db.audit` and `alerts.resolve` effects they use, plus a typed `ListForOwner` for the later GET page. The routes are registered in the Go binary but stay off: Caddy only sends paths listed in `UBYHOST_GO_PATHS` to Go, and nobody adds these here.

## 2. Context

Rules that apply (AGENTS.md): 1 filing correctness (not touched: no filing code); 2 no new personal-data field and no outbound request (fixtures use `@example.test` accounts, no names); 3 no guest data in the repo; 4 no new dependency (stdlib, pgx and repo packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python script uses only `db.execute`/`db.query` with `?`. No GET route and no HTML template here: the GET page comes in brief 1371 on the shared host layout (branch task/1380-go-host-layout).

What the Go code does, pinned by the golden (orchestrator and reviewer reference; the executor does not need to read further than this section and §4):

- Order is FastAPI's: the router's CSRF dependency (`hostweb.CSRF`) first, then (update only) the `{request_id}` int check (422 with FastAPI's exact JSON body), then `require_login` (`hostweb.Login`). Owner is `access.owner_id` = `h.Workspace.ID` (the admin's impersonation target, else the account; there is no team-member concept in Python), as `calendar/handler.go ownerID` does.
- `form_str`: Starlette `form.get` returns the **last** value of a repeated key, stripped (Python `str.strip`, which also strips U+001C..U+001F); a file part reads as "". `key in form` is key presence, empty value included.
- `received_at`: `YYYY-MM-DD` gets `T00:00:00+00:00`, empty is `db.utcnow()`, anything else is stored as typed. `due_at` is `one_month_later`, a port of `datetime.fromisoformat` + clamp-to-month-end + `isoformat()` for the extended ISO forms (date, `T` or space, `HH[:MM[:SS[.|,fraction]]]`, `Z` or `+-HH[:MM[:SS[.f]]]`). A string `fromisoformat` refuses makes Python raise ValueError before any write: **500 "Internal Server Error", nothing written, no audit**; Go does the same. Python additionally accepts basic (`20260131`), week (`2026-W05-1`) and any-character-separator forms: Go answers 500 for those (accepted divergence: the form field is `<input type="date">`).
- `guest_id`: an int only when all ASCII digits (Python `isdigit` also takes other Unicode digits: accepted divergence, as in `payments`). The guest is **not** owner-checked, as in Python. A guest id with no `guest` row breaks the FK: 500 in both, nothing written. On Postgres that failed INSERT still uses up an identity value (SQLite does not), so the golden puts that step last.
- Update: row missing or `owner_user_id` not the workspace: `flash.error.no_such_dsr`, no audit. A known status sets `status`; a closed one (`fulfilled`, `refused`, `withdrawn`) also sets `closed_at` and resolves alert `dsr_due:<id>`. `outcome_note` present sets it (stripped, "" allowed); `identity_checked` present sets `identity_checked_at`. Nothing to set: no UPDATE, but the `dsr_updated` audit row is still written. All timestamps in one request are one `Stamp(now)`.
- Audit rows: `actor` = account username, `owner_user_id` = workspace, `actor_user_id` = account, `impersonator_user_id` = account only while impersonating.
- Flash texts come from a package-local `i18n.json` generated from `host_i18n.py` (the hostweb catalog is empty and is read-only here). `App/scripts/go_host_i18n.py` only globs `go/internal/*/`, so `App/tests/test_go_privacy_requests.py` checks this catalog instead.
- `ListForOwner` returns `[]Request` with plain fields (NULL text is "", NULL id is 0) and an `Open()` method, so a template can print them directly.

Golden: `App/scripts/privacy_requests_golden.py` mounts the real router on a bare FastAPI app with a fixed clock (`db.utcnow` patched), the CSRF dependency overridden and `require_login` replaced by one that sets the actor and owner the way the real one does; it posts 19 steps (create valid, bad channel, bad subject in cs, empty received_at, digits guest + offset passthrough, non-digit guest + space separator, invalid received_at 500, repeated key last-wins + fraction, impersonating create, close resolves alert, note + identity + unknown status, extended keeps alert, nothing to set still audits, other owner, missing id in cs, `+5_2.00` path int, `abc` 422, impersonating close, missing guest 500) and records status, Location, body, and every `data_subject_request`, `audit` and `alert` row after each, plus 29 `one_month_later` cases and `list_for_owner` ids. The Go test seeds Postgres from the same file, signs in for real (session + CSRF token), posts the same bodies and compares everything.

**Verified by the brief writer** on a scratch copy of a83df54: every file below, generated golden sha256 `caa2d1d1775ada5dabd6ea7bcbd1095cc682c4553b4e3ed73bb7bda57bf6ab1c` (deterministic, also when rendered inside pytest), `gofmt -l .` empty, `go vet ./...` clean, `go test ./internal/web/privacy/ ./cmd/ubyhost-web/` ok **with a local PostgreSQL 16** (`--- PASS: TestPrivacyRequestsGolden` and `--- PASS: TestListForOwnerDatabase`, not skipped), the three pytest files green, and five deliberate mutations (first instead of last form value, impersonator flag inverted, only `fulfilled` closes, open-first sort dropped, date-only suffix without offset) each made a Go test fail.

Anchors that must exist verbatim (step 0): `func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {` in go/cmd/ubyhost-web/registry.go; `func Back(w http.ResponseWriter, r *http.Request, path string, msg, err Flash) {` and `func Lang(r *http.Request) string {` in go/internal/hostweb/hostweb.go; `func Login(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, error) {` and `func CSRF(w http.ResponseWriter, r *http.Request, getenv func(string) string, at time.Time) bool {` in go/internal/hostweb/gate.go; `def privacy_request_update(request_id: int, request: Request):` in App/app/routes/privacy_requests.py; `def one_month_later(iso: str) -> str:` in App/app/dsr.py; `def render(keys: list[str]) -> str:` in App/scripts/go_host_i18n.py.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/web/privacy/store.go | create | constants, `Request`, `ListForOwner`, `Get`, `Create`, `Update`, `Audit`, `ResolveAlert`, `Stamp`, `OneMonthLater` |
| go/internal/web/privacy/handler.go | create | `CreateHandler`, `UpdateHandler`, form helpers, embedded catalog |
| go/internal/web/privacy/store_test.go | create | golden loader, `OneMonthLater` vs Python, `ListForOwner` DB test, `testPool` |
| go/internal/web/privacy/handler_test.go | create | form/path unit tests, nil-pool CSRF test, golden replay on Postgres |
| go/internal/web/privacy/i18n_keys.txt | create | the four flash keys |
| go/internal/web/privacy/i18n.json | create | generated from host_i18n.py (step 1 extracts it; step 3 checks it) |
| go/internal/web/privacy/testdata/privacy_requests_golden.json | create | generated by the script in step 2, never by hand |
| go/cmd/ubyhost-web/register_web_privacy.go | create | `init()` registering only `POST /privacy-requests` and `POST /privacy-requests/{id}` with `m.wrap` |
| App/scripts/privacy_requests_golden.py | create | the golden generator |
| App/tests/test_go_privacy_requests.py | create | golden is current; the package catalog matches host_i18n |
| docs/tasks/1370-go-privacy-requests.md | edit | Status only |
| docs/tasks/1370a-go-privacy-requests-code.md | none | the code blocks (committed with this brief); never edit |
| docs/tasks/1370-report.md | create | report |

No other file may change.

## 4. Steps

0. From the repo root, on branch `task/1370-go-privacy-requests`: check the §2 anchors with one command, and that no §3 file exists yet:
   ```bash
   grep -cF 'func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {' go/cmd/ubyhost-web/registry.go; grep -cF 'func Back(w http.ResponseWriter, r *http.Request, path string, msg, err Flash) {' go/internal/hostweb/hostweb.go; grep -cF 'func Lang(r *http.Request) string {' go/internal/hostweb/hostweb.go; grep -cF 'func Login(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, error) {' go/internal/hostweb/gate.go; grep -cF 'func CSRF(w http.ResponseWriter, r *http.Request, getenv func(string) string, at time.Time) bool {' go/internal/hostweb/gate.go; grep -cF 'def privacy_request_update(request_id: int, request: Request):' App/app/routes/privacy_requests.py; grep -cF 'def one_month_later(iso: str) -> str:' App/app/dsr.py; grep -cF 'def render(keys: list[str]) -> str:' App/scripts/go_host_i18n.py; ls go/internal/web go/cmd/ubyhost-web/register_web_privacy.go App/scripts/privacy_requests_golden.py App/tests/test_go_privacy_requests.py 2>&1 | tail -30
   ```
   Expected: eight lines `1`, then four "No such file or directory". Anything else: STOP (§8).

1. Extract the nine files from [the code file](1370a-go-privacy-requests-code.md) (do not open it, do not retype anything), then check their hashes. From the repo root:
   ```bash
   python3 - <<'PY' 2>&1 | tail -30
   import pathlib, re
   text = pathlib.Path("docs/tasks/1370a-go-privacy-requests-code.md").read_text(encoding="utf-8")
   for m in re.finditer(r"^````[a-z]+ path=(\S+)\n(.*?)^````$", text, re.M | re.S):
       path = pathlib.Path(m[1])
       path.parent.mkdir(parents=True, exist_ok=True)
       path.write_text(m[2], encoding="utf-8")
       print("wrote", path)
   PY
   sha256sum go/internal/web/privacy/store.go go/internal/web/privacy/handler.go go/internal/web/privacy/store_test.go go/internal/web/privacy/handler_test.go go/internal/web/privacy/i18n_keys.txt go/internal/web/privacy/i18n.json go/cmd/ubyhost-web/register_web_privacy.go App/scripts/privacy_requests_golden.py App/tests/test_go_privacy_requests.py | tail -30
   ```
   Expected: nine `wrote` lines, then exactly these hashes:
   ```
   9f469e389b527d9ebfaa4eb945c62cf4496509b428aee95a59d31a734530d253  go/internal/web/privacy/store.go
   7a39677f9fa8ec450c13cb22ba60a536abd785910dab82f74bd6e01adc3e8ff2  go/internal/web/privacy/handler.go
   654fe3d871c010fe8cea3af17b045ffa62ed8eb90ccbd61693e3d666ab0b6d42  go/internal/web/privacy/store_test.go
   d5c26f8ba3261c736b10a11cb4329fe8b72221946401e2ed0013481b6510f5a7  go/internal/web/privacy/handler_test.go
   8a15c232a190aa2d37771b1057c30f36fa24310541a1b33317456145e7d01ea0  go/internal/web/privacy/i18n_keys.txt
   e47719b24e12e98b07359368ccdb29dcd800f6956e3a4c36b5c52200d8ec474e  go/internal/web/privacy/i18n.json
   af6708bf5d896248c2e6b0ac32fd6cd375ea3919fdd4ef5549bd4ceca9c34499  go/cmd/ubyhost-web/register_web_privacy.go
   0591fb34cb26c1cc251214d2682ee1f4280f18db0669ddf826677ea2b7f34c8e  App/scripts/privacy_requests_golden.py
   8c33a7cf2906b4faf9d01ec37d80be2a135b3f898d05b00ff9730a30ec2a708b  App/tests/test_go_privacy_requests.py
   ```
   A different hash: STOP (§8); never edit a file to make its hash match. Commit "1370 step 1" (the nine files).

2. Generate the golden. If `App/.venv` is missing, first from `App/`: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Then from `App/`:
   ```bash
   .venv/bin/python scripts/privacy_requests_golden.py 2>&1 | tail -3; sha256sum ../go/internal/web/privacy/testdata/privacy_requests_golden.json | tail -3
   ```
   Expected: `wrote .../go/internal/web/privacy/testdata/privacy_requests_golden.json` and `caa2d1d1775ada5dabd6ea7bcbd1095cc682c4553b4e3ed73bb7bda57bf6ab1c`. A different hash: STOP (§8); never edit the JSON. Commit "1370 step 2".

3. Run the §6 commands (Go, then Python, then the lint). Optional, if a local PostgreSQL 16 is at `/usr/lib/postgresql/16`: start one as the postgres user with its data dir outside `/tmp/claude-0` (for example `/var/tmp/pg1370`) and rerun the Go command with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/postgres` and `-v`; `--- PASS: TestPrivacyRequestsGolden` must appear. Without it write "DB tests: CI only" in the report. No commit unless something changed (nothing should).

4. Set this brief's `Status: review`, write `docs/tasks/1370-report.md` (§9), commit "1370 step 4". Do not push.

## 5. Do not touch

Read-only: go/internal/hostweb/, go/internal/session/, go/internal/jobs/, go/cmd/ubyhost-web/main.go, registry.go, register_web.go, App/tests/conftest.py, every file under App/app/, App/scripts/go_host_i18n.py, Caddy files and deploy/. Never edit docs/ENVIRONMENT.md, status.md, test-map.md, decisions.md, known-issues.md. No new Go or Python dependency (rule 4). No GET route, no template, never a bare `GET /`. No push, merge, secrets, servers or `.env`.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/web/privacy/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30` (expected `ok` twice; the DB tests skip without `UBYHOST_TEST_DATABASE_URL` and run in CI).
From `App/`: `.venv/bin/python -m pytest tests/test_go_privacy_requests.py tests/test_go_host_i18n.py tests/test_privacy_requests.py -q --tb=short -x 2>&1 | tail -30` (expected all passed).
Golden freshness: from `App/`, `.venv/bin/python scripts/privacy_requests_golden.py >/dev/null 2>&1; git status --short ../go | tail -30` prints nothing after step 2's commit.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` ends `context lint: OK`.

## 7. Acceptance

- [ ] Step 0: eight `1` lines and four missing paths.
- [ ] Step 1: the nine hashes match; step 2: the golden hash matches.
- [ ] From `go/`: gofmt empty, `go vet ./...` clean, both packages `ok`.
- [ ] DB tests: `--- PASS: TestPrivacyRequestsGolden` locally, or "CI only" in the report.
- [ ] The pytest command passes and the freshness command prints nothing.
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat a83df54..HEAD | tail -30` lists only the §3 paths.
- [ ] Commits "1370 step 1", "1370 step 2", "1370 step 4" on `task/1370-go-privacy-requests`; nothing pushed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an anchor in step 0 is not found, or a §3 file already exists;
- a hash in step 1 or 2 differs (never edit a file, the JSON, the Python or the Go to make it match);
- `TestPrivacyRequestsGolden` fails (any Go/Python mismatch is a question for the orchestrator), or any test fails twice;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, a PR, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1370-report.md` (600 tokens at most) and set `Status: review`. It has: 1. `git diff --stat a83df54..HEAD | tail -15`; 2. each §6 command (and the optional DB run) with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left (none expected: nothing is switched on).

## Risk list (for the reviewer)

Read `go/internal/web/privacy/handler.go` against App/app/routes/privacy_requests.py and admin_helpers.form_str (CSRF, then path int, then login; last form value; strip; `in form` presence; closed set; audit always on update; no audit on bad input), and `store.go` against App/app/dsr.py (insert columns, `IS NOT DISTINCT FROM`, sort), db.audit (db.py 2152) and alerts.resolve (alerts.py 535). Then check the golden test does not skip in CI (`--- PASS: TestPrivacyRequestsGolden` in the Go job log). Known and accepted divergences: received_at forms that only `fromisoformat` reads (basic, week date, odd separators, offset minutes over 59) are 500 in Go and stored in Python; non-ASCII digits in guest_id are NULL in Go; path ids pydantic reads that the regexp does not (none known) would 422; `guest_id` is not owner-checked in either (an existing Python gap, not fixed here); the Python dev bypass (no accounts outside production) is not ported; the golden runs Python on SQLite, the Go side on Postgres. Caddy's `@go path` matcher is method-blind: adding `/privacy-requests` to `UBYHOST_GO_PATHS` would also send the GET page to Go (404) until brief 1371 lands; `/privacy-requests/*` alone is safe (POST only in Python).

## Owner steps

None for this brief: the routes are registered but Caddy does not send them to Go. Do not add `/privacy-requests` to `UBYHOST_GO_PATHS` until the GET page (brief 1371) is merged.
