# 1204: Operator customer POSTs get CSRF; Go remember-me lifetime matches Python

Status: todo
Depends on: none | Base commit: a4e20a22 | Branch: task/1204-operator-csrf-go-session
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

(a) The seven operator POST routes in `admin_customers.py` get the same host CSRF dependency every other host router has. (b) Go `session.Verify` enforces the same remember-me limits as Python (30 days since last signing, 90 days since login), instead of 400 days. Both close security-review findings; no new dependency, no schema change. The PR is a draft.

## 2. Context

Rules: AGENTS rule 4 (no dependency), 5 (no schema change), 8 (draft, never push to main). No template or CSS changes, so rules 7 and 10 do not apply.

**Finding 1, verified.** `App/app/routes/admin_customers.py` line 6 and 16:

```python
from fastapi import APIRouter, HTTPException, Request
...
router = APIRouter()
```

POST routes at lines 111, 135, 165, 184, 205, 228, 241 (`/sleva`, `/plan`, `/priradit`, `/prodlouzit`, `/aktivovat`, `/overit-znovu`, `/stav`). Mounted at `App/app/main.py:480` (`app.include_router(admin_customer_routes.router)`). Sibling pattern, `App/app/routes/admin_billing.py` lines 11, 15, 21:

```python
from fastapi import APIRouter, Depends, Request
from .. import analytics, ..., config, security, signup, validation
router = APIRouter(dependencies=[Depends(security.protect_host_post)])
```

All seven forms in `App/app/templates/admin_customer.html` (lines 92, 143, 154, 162, 176, 192, 198) already carry `<input type="hidden" name="_csrf" value="{{ csrf_token }}">`. No JS or fetch posts to `/admin/customers`. `admin_customers.html` only has a GET search form. **No template change is needed.**

Existing tests: `App/tests/conftest.py` fixture `csrf_proof_on_form_posts` (line 279) adds a valid `_csrf` automatically to every `TestClient` form POST that does not set its own. `test_admin_customers.py` has no `client.post(` at all. So **0 existing tests need the token added.** A test that wants a stale token passes `data={security.CSRF_FIELD: "not-a-token"}` (see `App/tests/test_admin_route_split.py` lines 144-157, the pattern to copy: expects 303 and `location` starting `/login?notice=form_expired`).

Other routers without the dependency (`admin_accounts`, `exports`, `onboarding`, `signup`, `passkeys`, `push` ...) are included inside `admin.router` (which has it) or are public/guest/webhook routes, so they are correct. Do not touch them.

**Finding 2, verified.** `go/internal/session/session.go`: line 26-27 `rememberMaxAge = 400 * 24 * time.Hour`; lines 114-130 `Verify` (shown below). Python `App/app/auth.py` lines 30-35 and 270-290:

```python
SESSION_MAX_AGE = 60 * 60 * 12
SESSION_REMEMBER_MAX_AGE = 60 * 60 * 24 * 30
SESSION_ABSOLUTE_MAX_AGE = 60 * 60 * 24 * 90
...
payload = _serializer().loads(token, max_age=SESSION_REMEMBER_MAX_AGE)
if payload.get("rm") and time.time() - int(payload.get("iat", 0)) > SESSION_ABSOLUTE_MAX_AGE:
    return None
if not payload.get("rm"):  # then loads(token, max_age=SESSION_MAX_AGE) must pass
```

Python semantics: the itsdangerous timestamp is the last signing time (30 days max for every token). Remember-me tokens also need `now - iat <= 90 days`; a missing `iat` counts as 0, so it is rejected. Non-remember tokens: 12 hours since signing. Go non-remember is already 12 hours, **identical**. Only the remember-me case differs (400 days vs 30 days, and no 90-day cap).

Current Go `Verify` (`session.go` lines 114-130):

```go
func Verify(secret, token string, now time.Time) (map[string]any, bool) {
	s := secure.NewTimedSerializer(secret, salt)
	var raw json.RawMessage
	if err := s.Loads(token, rememberMaxAge, now, &raw); err != nil {
		return nil, false
	}
	payload, ok := decodePayload(raw)
	if !ok {
		return nil, false
	}
	if !truthy(payload["rm"]) {
		if err := s.Loads(token, shortMaxAge, now, &raw); err != nil {
			return nil, false
		}
	}
	return payload, true
}
```

Go re-issue: Go calls `session.Sign` only once, in `go/internal/hostweb/gate.go:109` (impersonation expiry; payload has no `rm`, `iat` copied from the old token). Go never refreshes a remember-me cookie; only Python re-signs it. **User-visible effect:** a host whose remember-me cookie was last re-signed more than 30 days ago, or who logged in more than 90 days ago, is asked to log in again on Go-served routes. That is the same as on Python routes today. A host who is active on Python routes keeps being re-signed, so nothing changes for them.

Existing Go test `TestSessionAge` (`session_test.go` lines 114-131) signs a remember token **without `iat`** and expects it valid at 399 days. It must be rewritten (Step 4). Golden tokens in `testdata/tokens.json` have `iat` within seconds of the golden timestamp, so they stay valid. No other Go code uses `"rm"` tokens (`payments/connect_test.go:309` only calls `Verify` with its own token; run its package in §6).

`go/internal/session/session.go` Verify comment (line 112-113) and `docs/SECURITY.md` line 54 say 400 days; both are corrected.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin_customers.py` | edit | import `Depends`, `security`; router dependency |
| `App/tests/test_admin_customers.py` | edit | add 2 CSRF tests |
| `App/tests/test_admin_route_split.py` | edit | add 1 coverage test over every `/admin` POST |
| `go/internal/session/session.go` | edit | constants and `Verify` |
| `go/internal/session/session_test.go` | edit | rewrite `TestSessionAge`, add 3 tests |
| `docs/SECURITY.md` | edit | line 54 lifetime wording |

No other file may change.

## 4. Steps

1. `App/app/routes/admin_customers.py`: change line 8 to `from fastapi import APIRouter, Depends, HTTPException, Request`. Change line 10 to `from .. import admin_customers, admin_ops, billing, billing_analytics, billing_order, config, db, incidents, security, validation`. Change line 16 to `router = APIRouter(dependencies=[Depends(security.protect_host_post)])`. Run `grep -n 'security\|Depends' App/app/routes/admin_customers.py | tail -30` to check there is no name clash.

2. `App/tests/test_admin_customers.py`: add `security` to the `from app import ...` line (line 9). Append at the end of the file (use the `accounts` fixture as the existing tests do; read lines 43-52 first for how an admin client logs in with `login_as`, and copy that exact style):

```python
def _admin_and_customer(accounts):
    create, _prefix = accounts
    admin_id, admin_name = create(role="admin")
    customer_id, _customer_name = create()
    client = TestClient(app)
    assert login_as(client, admin_name, follow_redirects=False).status_code == 303
    return client, customer_id


def test_operator_customer_post_without_valid_csrf_is_rejected(accounts):
    client, customer_id = _admin_and_customer(accounts)
    response = client.post(
        f"/admin/customers/{customer_id}/stav",
        data={security.CSRF_FIELD: "not-a-token", "status": "paused"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?notice=form_expired")


def test_operator_customer_post_with_csrf_reaches_the_handler(accounts):
    client, customer_id = _admin_and_customer(accounts)
    response = client.post(
        f"/admin/customers/{customer_id}/overit-znovu", data={}, follow_redirects=False,
    )  # conftest adds a valid _csrf token
    assert response.status_code == 303
    assert not response.headers["location"].startswith("/login?notice=form_expired")
```

If `login_as` takes the password or other args differently in the neighbouring tests, copy the neighbours, not this sketch. If `overit-znovu` returns something other than 303 for a normal customer, read lines 228-240 of `admin_customers.py` and assert what it really returns, still asserting it is not the `form_expired` redirect. Run the two tests; they must fail before Step 1 and pass after. (Check the first by `git stash`-free reasoning only: do not stash; just run after Step 1.)

3. `App/tests/test_admin_route_split.py`: append at the end of the file (`security`, `app`, `TestClient` are already imported at lines 15-20):

```python
def test_every_admin_post_route_demands_csrf_proof():
    """Item 1204: a host router added without protect_host_post fails here.

    The OpenAPI schema lists every mounted route whatever router it came from.
    With no session and a wrong token, a protected route redirects to the
    form_expired notice before its own handler runs.
    """
    client = TestClient(app)
    paths = [
        path for path, item in app.openapi()["paths"].items()
        if path.startswith("/admin") and "post" in item
    ]
    assert "/admin/customers/{user_id}/stav" in paths
    unprotected = []
    for path in sorted(paths):
        url = path.replace("{user_id}", "1")
        url = __import__("re").sub(r"\{[^}]+\}", "1", url)
        response = client.post(
            url, data={security.CSRF_FIELD: "not-a-token"}, follow_redirects=False,
        )
        location = response.headers.get("location", "")
        if not (response.status_code in (303, 403) and (
                location.startswith("/login?notice=form_expired") or response.status_code == 403)):
            unprotected.append(path)
    assert unprotected == []
```

Replace the clumsy `__import__("re")` with a normal `import re` at the top of the file and delete the redundant `.replace("{user_id}", "1")` line. If a path legitimately is not host CSRF protected (the failure list names it), STOP (§8) and report it; do not add an allowlist silently. If `app.openapi()` hides a route (`include_in_schema=False`) that is acceptable.

4. `go/internal/session/session.go`: replace lines 26-27 with:

```go
	// rememberMaxAge is SESSION_REMEMBER_MAX_AGE (auth.py line 34): 30 days since the cookie was last signed.
	rememberMaxAge = 30 * 24 * time.Hour
	// absoluteMaxAge is SESSION_ABSOLUTE_MAX_AGE (auth.py line 35): 90 days since login ("iat") for remember-me.
	absoluteMaxAge = 90 * 24 * time.Hour
```

Update the `Verify` doc comment to: `30 days at most since signing, 90 days since "iat" when "rm" is truthy, and 12 hours unless the payload has a truthy "rm"`. In `Verify`, change the `if !truthy(payload["rm"]) {` block to:

```go
	if truthy(payload["rm"]) {
		// auth._session_payload: a missing "iat" counts as 0, so it is rejected.
		if now.Sub(time.Unix(iatSeconds(payload["iat"]), 0)) > absoluteMaxAge {
			return nil, false
		}
	} else {
		if err := s.Loads(token, shortMaxAge, now, &raw); err != nil {
			return nil, false
		}
	}
```

Add below `Verify`:

```go
// iatSeconds is int(payload.get("iat", 0)) in Python for the JSON values an iat can hold.
func iatSeconds(v any) int64 {
	switch x := v.(type) {
	case int64:
		return x
	case json.Number:
		f, _ := x.Float64()
		return int64(f)
	}
	return 0
}
```

(If `payload["iat"]` is a float, `convert` leaves it as `json.Number`; the case above covers it.) Then run `gofmt -l internal/session` from `go/`; it must print nothing.

5. `go/internal/session/session_test.go`: replace the `remember` half of `TestSessionAge` (the lines from `remember := Sign(...)` to the end of the function) with the three tests below. Keep the plain-token half untouched.

```go
func rememberToken(g golden, iatAgo time.Duration, signedAt time.Time) string {
	return Sign(g.Secret, map[string]any{
		"uid": int64(7), "sv": int64(3), "rm": int64(1),
		"iat": signedAt.Add(-iatAgo).Unix(),
	}, signedAt)
}

func TestRememberMeSinceReSign(t *testing.T) {
	g := loadGolden(t)
	base := time.Unix(g.Timestamp, 0)
	tok := rememberToken(g, 0, base)
	if _, ok := Verify(g.Secret, tok, base.Add(29*24*time.Hour)); !ok {
		t.Error("remember token rejected at 29 days since re-sign")
	}
	if _, ok := Verify(g.Secret, tok, base.Add(31*24*time.Hour)); ok {
		t.Error("remember token accepted at 31 days since re-sign")
	}
}

func TestRememberMeSinceLogin(t *testing.T) {
	g := loadGolden(t)
	base := time.Unix(g.Timestamp, 0)
	// Re-signed today, but the login was 91 days ago: rejected. 89 days ago: accepted.
	if _, ok := Verify(g.Secret, rememberToken(g, 91*24*time.Hour, base), base); ok {
		t.Error("remember token accepted 91 days after login")
	}
	if _, ok := Verify(g.Secret, rememberToken(g, 89*24*time.Hour, base), base); !ok {
		t.Error("remember token rejected 89 days after login")
	}
	// Missing iat counts as 0 and is rejected, as in Python.
	noIat := Sign(g.Secret, map[string]any{"uid": int64(7), "sv": int64(3), "rm": int64(1)}, base)
	if _, ok := Verify(g.Secret, noIat, base); ok {
		t.Error("remember token without iat accepted")
	}
}

func TestRememberMeInsideBothLimits(t *testing.T) {
	g := loadGolden(t)
	base := time.Unix(g.Timestamp, 0)
	tok := rememberToken(g, 60*24*time.Hour, base)
	if _, ok := Verify(g.Secret, tok, base.Add(29*24*time.Hour)); ok == false {
		t.Error("remember token rejected inside both limits (iat 60 days before signing, 29 days later = 89 days)")
	}
}
```

If the golden struct type is not named `golden`, use whatever `loadGolden` returns (`grep -n 'func loadGolden' go/internal/session/session_test.go`). Run `gofmt -l`.

6. `docs/SECURITY.md` line 54: in the "Stateless logout" row replace `signed-in host sessions last up to 400 days until logout` with `remember-me host sessions last up to 30 days since the cookie was last re-signed and 90 days since login (Python and Go enforce the same limits); other host sessions last 12 hours, until logout`. Leave the "Host CSRF" row (line 29) unchanged, its wording is still true.

## 5. Do not touch

Templates, JS, CSS, `go/internal/hostweb/*`, `App/app/auth.py`, `App/tests/conftest.py`, any other router, migrations, `requirements*`, `go.mod`. AGENTS rules 3, 4, 5, 8. Never push or merge.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_admin_customers.py tests/test_admin_route_split.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_login_*.py tests/test_auth_*.py tests/test_two_factor_*.py tests/test_passkeys.py tests/test_remember_me_reissue.py tests/test_security*.py -q --tb=short -x 2>&1 | tail -30
```

From `go/`:

```
gofmt -l internal/session 2>&1 | tail -30
go test ./internal/session/... 2>&1 | tail -30
go test ./internal/payments/... ./internal/hostweb/... 2>&1 | tail -30
```

Expected: all pass, `gofmt -l` prints nothing. From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` passes.

## 7. Acceptance

- [ ] `grep -n '^router' App/app/routes/admin_customers.py` shows `Depends(security.protect_host_post)`.
- [ ] Wrong-token POST to `/admin/customers/{id}/stav` redirects to `/login?notice=form_expired`; valid-token POST does not.
- [ ] The coverage test fails if the dependency is removed from `admin_customers.py` (check once by reading the result, not by editing and reverting).
- [ ] Go: remember token invalid after 31 days since signing and after 91 days since `iat`, valid inside both, invalid without `iat`; plain token still 12 hours.
- [ ] `grep -n '400' docs/SECURITY.md go/internal/session/session.go` shows no remaining session-lifetime 400.
- [ ] 0 existing tests needed the token added (state this in the report).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- the coverage test names an `/admin` POST route other than the customer ones as unprotected (report its path; the orchestrator decides);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1204-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/routes/admin_customers.py` (three lines).
- `go/internal/session/session.go` `Verify` and `iatSeconds`: compare against `App/app/auth.py` lines 270-290.
- The coverage test in `test_admin_route_split.py` (must not become an allowlist).

## Owner steps

1. Open the draft PR the orchestrator creates and wait for CI to turn green.
2. Mark it ready and merge it with `scripts/merge-pr-on-green.sh <PR number>`; green merges auto-deploy.
3. After deploy, hosts whose remember-me cookie is older than 30 days since last visit, or login older than 90 days, will see the login page once on Go-served pages (the same as on the Python pages today). No action needed.
