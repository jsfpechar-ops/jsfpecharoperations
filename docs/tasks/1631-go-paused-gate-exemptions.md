# 1631: Go paused-plan exemptions live in hostweb.Login, with Python parity and PostgreSQL tests

Status: todo
Depends on: none (independent; run on go-wave3) | Base commit: none (one big PR mode, see below) | Branch: the orchestrator's current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now. Never create a branch, never push, never open a PR, use no `mcp__` tool. Commit after each step with the message `1631 step k` (k = the step number), and the report as `1631 report`. The orchestrator opens the one PR.

## 1. Objective

Python `require_login` lets a paused (read-only) workspace POST to a short list of paths; Go `hostweb.Login` redirects every POST of a paused workspace to `/predplatne?paused=1`, and two packages (`web/auth`, `web/billing`) work around that with request-method masks. This brief moves the exemption into `hostweb.Login` (one copy, checked against `auth.py` by a test), removes the two masks, and adds PostgreSQL tests of the rule.

## 2. Context

Tier A (sessions). Rules: 3 nothing real in the repo; 4 no new dependency. No file under `App/app/` changes. Dormant: nothing changes in production until a path is switched to Go.

**Python (the documented side), `App/app/auth.py`:**

```python
_READ_ONLY_OPEN_PREFIXES = ("/predplatne", "/logout", "/account", "/settings", "/exports")
_READ_ONLY_OPEN_PATHS = re.compile(
    r"^/(reservations/submit-ready|reservations/\d+/submit|guests/\d+/resend)$"
)
...
    if (
        getattr(request, "method", "GET") == "POST"
        and workspace is not None
        and not impersonating
        and not request.url.path.startswith(_READ_ONLY_OPEN_PREFIXES)
        and not _READ_ONLY_OPEN_PATHS.match(request.url.path)
    ):
        ...
            return RedirectResponse("/predplatne?paused=1", status_code=303)
```

**Go today, `go/internal/hostweb/gate.go` `Login`:**

```go
	if r.Method == http.MethodPost && !h.Impersonating && billingOn(getenv) {
		var status string
		err := pool.QueryRow(ctx, pausedSQL, h.Workspace.ID).Scan(&status)
```

no exemption list. Workarounds that this brief removes:

- `go/internal/web/auth/auth.go`: the vars `readOnlyOpenPrefixes`, `readOnlyOpenPaths`, func `readOnlyOpen`, const `openPost`, and in `login()` the block that copies the request and sets `req.Method = openPost`. The `bare` wrapper stays.
- `go/internal/web/billing/routes.go`: field `open bool` of `gate` and, in `login()`, the block `lr := r; if g.open && r.Method == http.MethodPost { lr = r.Clone(...); lr.Method = http.MethodGet }`. Callers `gate{open: true}` (in `plan_page.go`, `host_actions.go`, `routes.go`) become `gate{}`.

Other packages (`web/exports`, `web/privacy`, `web/properties`, ...) call `hostweb.Login` directly; after this brief a POST of theirs to an exempt path is exempt too, as in Python. `/logout` does not call `Login` (it uses `d.current`), so it never hit the paused check; it stays untouched.

**Behaviour check on removing the masks.** The billing mask turned a POST into a GET only for `Login`; `http.Redirect` on a GET writes a small HTML body, on a POST none, and Python's `RedirectResponse` writes none. So after the change an unauthenticated POST to `/predplatne/...` redirects to `/login` with no body (closer to Python). If any existing test fails because of this or any other difference, do not edit the test: keep the mask in that one package, say why in the report, and finish the rest (section 8).

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1 unless stated):

| File | Anchor |
|---|---|
| `App/app/auth.py` | `_READ_ONLY_OPEN_PREFIXES = ("/predplatne", "/logout", "/account", "/settings", "/exports")` |
| `go/internal/hostweb/gate.go` | `if r.Method == http.MethodPost && !h.Impersonating && billingOn(getenv) {` |
| `go/internal/web/auth/auth.go` | `readOnlyOpenPrefixes = []string{"/predplatne", "/logout", "/account", "/settings", "/exports"}` |
| `go/internal/web/auth/auth.go` | `req.Method = openPost` |
| `go/internal/web/billing/routes.go` | `if g.open && r.Method == http.MethodPost {` |
| `go/internal/web/billing/plan_page.go` | `gate{open: true}` |
| `go/internal/web/billing/routes_test.go` | `func TestPausedHostStillPostsToPlanPage(` |

`grep -rc 'gate{open: true}' go/internal/web/billing/*.go | grep -v ':0'` lists exactly `host_actions.go` (2), `plan_page.go` (1), `routes.go` (3). Anything else: STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/hostweb/gate.go` | edit | `ReadOnlyOpen` + the exemption in `Login` |
| `go/internal/hostweb/gate_paused_test.go` | create | parity test against `auth.py` (no database) |
| `go/internal/web/auth/auth.go` | edit | remove the mask and its vars |
| `go/internal/web/billing/routes.go`, `plan_page.go`, `host_actions.go` | edit | remove `open` |
| `go/internal/web/billing/paused_exempt_test.go` | create | PostgreSQL tests of `hostweb.Login` |
| `docs/tasks/1631-report.md` | create | the report |

No other file may change.

## 4. Steps

0. Checks (repo root, one call): `git status --short | tail -5` prints nothing; the section 2 anchors print `1`; the `gate{open: true}` listing matches. Any difference: STOP, no commit.

1. In `go/internal/hostweb/gate.go`: add `"regexp"` to the imports (after `"net/url"`), and above `// Login is require_login` insert:

```go
// readOnlyOpenPrefixes and readOnlyOpenPaths are auth.py
// _READ_ONLY_OPEN_PREFIXES and _READ_ONLY_OPEN_PATHS (0415): what a paused plan
// may still POST. gate_paused_test.go checks them against auth.py.
var (
	readOnlyOpenPrefixes = []string{"/predplatne", "/logout", "/account", "/settings", "/exports"}
	readOnlyOpenPaths    = regexp.MustCompile(`^/(reservations/submit-ready|reservations/\d+/submit|guests/\d+/resend)$`)
)

// ReadOnlyOpen reports whether a POST to path is allowed on a paused plan.
func ReadOnlyOpen(path string) bool {
	for _, p := range readOnlyOpenPrefixes {
		if strings.HasPrefix(path, p) {
			return true
		}
	}
	return readOnlyOpenPaths.MatchString(path)
}
```

   and change the condition to `if r.Method == http.MethodPost && !h.Impersonating && !ReadOnlyOpen(r.URL.Path) && billingOn(getenv) {`. Run `cd go && gofmt -l internal/hostweb; go build ./internal/hostweb/ 2>&1 | tail -5` (no output). Commit `1631 step 1`.

2. Create `go/internal/hostweb/gate_paused_test.go` (package `hostweb`): `TestReadOnlyOpenMatchesPython` reads `../../../App/app/auth.py` with `os.ReadFile` (fatal if missing), finds the tuple with the regexp `_READ_ONLY_OPEN_PREFIXES = \(([^)]*)\)` and the path regex with `_READ_ONLY_OPEN_PATHS = re\.compile\(\s*r"([^"]+)"`, and checks: the quoted strings of the tuple, in order, equal `readOnlyOpenPrefixes`; the Python regex string equals `readOnlyOpenPaths.String()`. Then a table test of `ReadOnlyOpen`: true for `/predplatne`, `/predplatne/obnovit`, `/logout`, `/account/logout-all`, `/settings/privacy/ad-consent`, `/exports/x`, `/reservations/submit-ready`, `/reservations/12/submit`, `/guests/7/resend`; false for `/reservations/12`, `/reservations/x/submit`, `/guests/7`, `/apartments`, `/admin/incidents`, `/`. Run `cd go && go test ./internal/hostweb/ -run 'ReadOnlyOpen' -count=1 -v 2>&1 | tail -15`: PASS. Commit `1631 step 2`.

3. Remove the web/auth mask. In `go/internal/web/auth/auth.go` delete the comment and `var (readOnlyOpenPrefixes ... readOnlyOpenPaths ...)` block, `func readOnlyOpen`, the `openPost` comment and const, and in `login()` replace the `req := r` ... `req.Method = openPost` ... `}` lines so the body is: `h, err := hostweb.Login(bare{w}, r, d.pool, d.getenv, at)` (keep the error handling and the return). Fix the doc comment of `login` to say `hostweb.Login exempts the read-only-open paths itself`. Remove imports left unused (`regexp`, maybe `strings`; check with the build). Run `cd go && gofmt -l internal/web/auth; go vet ./internal/web/auth/ 2>&1 | tail -5`. Commit `1631 step 3`.

4. Remove the web/billing mask. In `routes.go` delete the `open bool` field and its comment lines in `gate`, and in `login()` replace the `lr := r ... lr.Method = http.MethodGet ... }` block with a direct `h, err = hostweb.Login(w, r, d.pool, d.getenv, at)`; then `sed -i 's/gate{open: true}/gate{}/' go/internal/web/billing/{plan_page,host_actions,routes}.go`. Run `cd go && gofmt -l internal/web/billing; go vet ./internal/web/billing/ 2>&1 | tail -5`. Commit `1631 step 4`.

5. Create `go/internal/web/billing/paused_exempt_test.go` (package `billing`; reuse `testPool`, `seedUsers`, `seedAccount`, `sessionFor`, `csrfPair`, `testEnvMap`, `testNow`, `testSecret`; `go test` must not skip, so `UBYHOST_TEST_DATABASE_URL` is set). `TestLoginPausedExemptions`: pool, `seedUsers`, `seedAccount(t, pool, 1, "paused", "standard", "month")`; a handler `func(w, r)` that calls `hostweb.Login(w, r, pool, testEnvMap(nil), testNow)` and, when it returns a host, writes `204`. Table of `(who, method, path, want)` sent through `httptest` with the session cookie `sessionFor(who, testNow)` (no CSRF needed, `Login` does not check it):
   - `host1` POST `/account/logout-all`, `/settings/privacy/ad-consent`, `/predplatne/obnovit`, `/logout`, `/exports/x`, `/reservations/5/submit`, `/guests/5/resend`: `204`.
   - `host1` POST `/apartments`, `/reservations/5`: `303` with Location exactly `/predplatne?paused=1`.
   - `host1` GET `/apartments`: `204` (a paused plan only blocks POST).
   - `admin_imp` (admin impersonating host 1) POST `/apartments`: `204`.
   Then set the account `active` (`UPDATE billing_account SET status = 'active' WHERE owner_user_id = 1`) and check POST `/apartments` gives `204`. Each case is a `t.Run`. Run `cd go && UBYHOST_TEST_DATABASE_URL=$URL go test ./internal/web/billing/ -run 'TestLoginPausedExemptions|TestPausedHostStillPostsToPlanPage' -count=1 -v 2>&1 | tail -30`: all PASS. Commit `1631 step 5`.

6. Run section 6. Write the report (section 9), commit as `1631 report`. Do not push or open a PR.

## 5. Do not touch

`App/` (including `App/app/auth.py`), `go/internal/session/`, `go/go.mod`, `go/go.sum`, `go/internal/web/exports/`, `go/internal/web/privacy/`, `go/internal/web/properties/`, every existing test file, `docs/context/*`. No new dependency.

## 6. Commands

From the repo root. Start a PostgreSQL 16 on a unique port with data dir under `/var/tmp`, export `UBYHOST_TEST_DATABASE_URL` (a superuser URL; tests create and drop their own databases), and keep it set for all of:

- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/... ./cmd/... 2>&1 | tail -30` prints nothing.
- `cd go && go test ./internal/hostweb/... ./internal/web/... ./internal/session/... -count=1 -v 2>&1 | grep -c '^\s*--- SKIP'` prints `0` (no test skipped; report the number). Then the same command with `| grep -v '^\(=== \|\s*--- PASS\|PASS\|ok\)' | tail -30` shows no FAIL.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1631.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1631 step'` lists steps 1 to 5, and `--grep='^1631 report'` the report.
- [ ] `grep -rn 'openPost\|g\.open\|gate{open' go/internal | wc -l` prints `0` (or, if you kept a mask per section 2, the report says which and why).
- [ ] `grep -c '_READ_ONLY_OPEN' go/internal/hostweb/gate_paused_test.go` prints at least `2`.
- [ ] The tests of step 2 and 5 pass; the paused POST to `/apartments` is `303 /predplatne?paused=1`, to the five exempt paths `204`, impersonating admin `204`.
- [ ] Section 6 output as stated, 0 skipped.
- [ ] `git diff --stat <first 1631 commit>^..HEAD` lists only section 3 files.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; an existing test fails twice for a reason other than the body difference of section 2; you reach 25 tool calls or about 50k tokens (report `blocked`); a new dependency seems needed; a file outside section 3 needs a change; the paused redirect shows up for an exempt path in a package other than web/auth and web/billing (report the path); a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1631-report.md` (600 tokens at most), set `Status: review`: 1. files changed; 2. each command with the last 5 lines of output and the SKIP count; 3. section 7 ticked; 4. deviations (a kept mask); 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

`Login` is called by about 25 packages; the only change for them is that a POST whose path is in the Python list is no longer redirected when the plan is paused. Check the regexp in `gate.go` equals Python's, and that web/auth golden tests (`TestRoutesGoldenDatabase`) still pass without the mask.

## Owner steps

None. Dormant until a path is switched to Go. (The owner's report that Go redirects paused POSTs to `/logout`, `/account`, `/settings`, `/exports` was not reproduced in current code: those handlers already avoided the check; this brief makes that true by construction.)
