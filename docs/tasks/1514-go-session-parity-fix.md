# 1514: Go session parity: the two hostweb gaps of 1282 are closed; drop the test waiver that still hides them

Status: review
Depends on: none (independent of 1501) | Base commit: none (one big PR mode, see below) | Branch: the orchestrator's current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now. Never create a branch, never push, never open a PR. Commit after each step with the message `1514 step k` (k = the step number), and the report as `1514 report`. The orchestrator opens the one PR.

## 1. Objective

Brief 1282 recorded two gaps in the live Go session code: `hostweb.endExpired` signed the stop cookie without `rf` and with SameSite=Strict, and `csrfMaxAge` was 400 days against Python's 30. Both are already fixed (brief 1382, commit `8a1241966`, merged to main), so no live code changes here; this brief removes the `knownGaps` waiver in `go/internal/web/auth/routes_test.go` that still deletes `rf` and copies the cookie attributes before comparing, so the Python golden proves the fix from now on.

## 2. Context

Tier A (sessions). Rules: 3 nothing real in the repo; 4 no new dependency. No file under `App/app/` or `go/internal/hostweb/` changes.

**Claim 1, stop cookie (refuted: already fixed).** Python `App/app/auth.py` `end_expired_impersonation` ends with `attach_session(response, issue_session(account["id"], account["session_version"], issued_at=session_issued_at(request)))`: `issue_session` writes `{"uid", "sv", "iat", "rf"}` and `attach_session` sets `samesite="lax"`, 12 hours without remember. docs/SECURITY.md (Host sessions, 0911): the session cookie is "signed, HttpOnly, Secure on HTTPS and SameSite=Lax". Python is the documented side. Go `go/internal/hostweb/gate.go` `endExpired` now signs `"rf":  at.Unix(),` and sets `SameSite: http.SameSiteLaxMode,` with `MaxAge: sessionMaxAge` (12 hours): equal to Python.

**Claim 2, CSRF max age (refuted: already fixed).** Python `App/app/security.py`: `CSRF_MAX_AGE = auth.SESSION_REMEMBER_MAX_AGE` (30 days), used for the token check and the CSRF cookie. Go: `go/internal/hostweb/gate.go` `const csrfMaxAge = 30 * 24 * time.Hour` and `go/internal/hostweb/layout/layout.go` `csrfMaxAge = 30 * 24 * 60 * 60 // auth.SESSION_REMEMBER_MAX_AGE`; `TestCSRFMaxAge` in `go/internal/hostweb/csrf_test.go` checks 29 days pass and 31 days fail. The CSRF cookie stays SameSite=Strict on both sides, as SECURITY.md says.

**What is left.** `go/internal/web/auth/routes_test.go` still has

```go
var knownGaps = map[string]string{
	// hostweb.endExpired signs {uid, sv, iat} with SameSite=Strict; Python's
	// end_expired_impersonation goes through issue_session (adds rf) and
	// attach_session (SameSite=Lax). Reported for the hostweb owner.
	"stop_expired": "rf",
}
```

and `TestRoutesGoldenDatabase` deletes `rf` from both payloads and copies Go's attributes over Python's for `stop_expired`, so a regression of claim 1 would pass. The patch in `docs/tasks/1514-files/routes_test.go.patch` empties the map (the loop that reads it stays). Verified by the brief writer with PostgreSQL 16: `TestRoutesGoldenDatabase/stop_expired` passes with the patch; with the patch and `"rf"` removed from `endExpired`, or with `SameSiteStrictMode` put back, it fails (both passed before the patch).

**What a signed-in user notices when this deploys: nothing.** Only a test file changes. When 1382 itself went live: an admin whose workspace preview expired gets a Lax session cookie with `rf` (no visible change), and a host form whose CSRF token is older than 30 days (a tab left open for a month) is refused with the usual "try again" redirect instead of being accepted, exactly as Python does. Sessions and logins were not affected. No rollout steps are needed.

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `go/internal/web/auth/routes_test.go` | `"stop_expired": "rf",` |
| `go/internal/hostweb/gate.go` | `"rf":  at.Unix(),` |
| `go/internal/hostweb/gate.go` | `SameSite: http.SameSiteLaxMode,` |
| `go/internal/hostweb/gate.go` | `const csrfMaxAge = 30 * 24 * time.Hour` |
| `go/internal/hostweb/layout/layout.go` | `csrfMaxAge = 30 * 24 * 60 * 60 // auth.SESSION_REMEMBER_MAX_AGE` |
| `App/app/security.py` | `CSRF_MAX_AGE = auth.SESSION_REMEMBER_MAX_AGE` |

If one of the `gate.go`, `layout.go` or `security.py` anchors prints 0, a gap is back: STOP and report which (section 8); do not edit `hostweb`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/routes_test.go` | edit (patch) | `knownGaps` emptied, comment says why |
| `docs/tasks/1514-report.md` | create | the report |

`docs/tasks/1514-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call): `git status --short | tail -5` prints nothing; the six anchors of section 2 each print `1`; then

```bash
sha256sum docs/tasks/1514-files/routes_test.go.patch | tail -1; git apply --check docs/tasks/1514-files/routes_test.go.patch 2>&1 | tail -3
```

   Expected: `c36000154d089b01841c2809f531355eeebb5b8bc6ea4642cc276896686303db  docs/tasks/1514-files/routes_test.go.patch` and no output from `git apply --check`. Anything else: STOP. No commit for step 0.

1. Apply the patch (from the repo root):

```bash
git apply docs/tasks/1514-files/routes_test.go.patch && git diff --stat | tail -3
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go vet ./internal/web/auth/ 2>&1 | tail -5; go test -count=1 ./internal/web/auth/ 2>&1 | tail -5
```

   Expected: `go/internal/web/auth/routes_test.go | 9 +++------`, `1 file changed, 3 insertions(+), 6 deletions(-)`, no gofmt or vet output, `ok`. Commit `1514 step 1`.

2. Run section 6. Write the report (section 9) and commit it as `1514 report`. Do not push or open a PR.

## 5. Do not touch

`go/internal/hostweb/` (both claims are already fixed there; nothing is authorised), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, the rest of `go/internal/web/auth/` (including `testdata/routes.json`), `go/go.mod`, `go/go.sum`, `App/` (including `App/tests/conftest.py`), `docs/context/*` (`status.md`, `test-map.md`, `decisions.md` are read-only), `docs/tasks/1514-files/`.

## 6. Commands

From the repo root:

- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/... ./cmd/... 2>&1 | tail -30` prints nothing.
- `cd go && go test ./internal/web/auth/... ./internal/session/... ./internal/hostweb/... -count=1 2>&1 | tail -30` prints only `ok` lines. `TestRoutesGoldenDatabase` needs `UBYHOST_TEST_DATABASE_URL` (it skips without it; CI runs it). If it is set, `TestRoutesGoldenDatabase/stop_expired` must PASS.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1514.

Test-map: no row covers Go packages; the commands above are this brief's tests.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1514 step'` lists step 1, and `git log --oneline --grep='^1514 report'` the report.
- [ ] `for c in $(git log --format=%h --grep='^1514 '); do git show --name-only --format= $c; done | sort -u` lists `go/internal/web/auth/routes_test.go`, `docs/tasks/1514-report.md` and `docs/tasks/1514-go-session-parity-fix.md` (the Status line), nothing else.
- [ ] `grep -c 'stop_expired' go/internal/web/auth/routes_test.go` prints `0` and `grep -c 'var knownGaps = map\[string\]string{}' go/internal/web/auth/routes_test.go` prints `1`.
- [ ] Section 6 output exactly as stated.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found (a hostweb anchor missing means a gap is back: say which), the sha256 differs, or `git apply --check` fails;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1514-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of `go/internal/web/auth/routes_test.go`: only the `knownGaps` map and its comment change; the comparison loop is untouched, so `stop_expired` is now compared in full (payload including `rf`, cookie attributes including SameSite).

## Owner steps

None. Nothing changes in production.
