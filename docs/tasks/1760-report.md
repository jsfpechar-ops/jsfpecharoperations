# 1760 report: Go passkeys (go-webauthn v0.18.0)

Built: six routes in `go/internal/web/auth/passkeys.go` and `passkeys_ceremony.go`, registered dormant in `go/cmd/ubyhost-web/register_web_auth_passkeys.go`. `POST /account/security-prompt/seen` was already on Go (brief 1282).

- `POST /account/passkeys/options`, `POST /account/passkeys`, `POST /account/passkeys/{id}/rename`, `POST /account/passkeys/{id}/delete`
- `POST /login/passkey/options`, `POST /login/passkey`

## Ceremony handling (same table, same rules as `App/app/passkeys.py`)

- Relying party is the host of `UBYHOST_PUBLIC_BASE_URL`; only the public and app origins are accepted; no IP hosts, no plain http except localhost.
- Challenge: SHA-256 only, 5 minutes, spent with one `UPDATE ... RETURNING` (a replay or a race matches no row). Registration needs the signed-in account's own challenge; login and registration challenges are not interchangeable.
- Registration needs a login no older than 10 minutes, acts on the real account (never an impersonated workspace), max 10 per account (checked inside the INSERT), duplicate credential ids refused, resident key and user verification required.
- Login: credential found by id, account must be active and hold a user handle, presented handle must match, counter must rise (0 and 0 allowed for synced passkeys); a regression refuses the login, leaves the row untouched and writes `passkey_clone_suspected`. The counter update carries the old value in its WHERE.
- Rate limits unchanged: 30 option requests and 20 failures per 15 minutes per address. Audit rows as in Python. CSRF header/form check runs first on every route.

## Accepted differences

- go-webauthn also checks that the backup-eligible flag does not change. The table stores only "backed up", so for a row stored as not backed up the flag is taken from the answer; a backed-up row must still present it.
- An account without a stored user handle cannot log in with a passkey (Python skipped the handle check then; such an account cannot own a passkey anyway).
- `name` and `next` in the JSON body are read only when they are strings.
- Option JSON comes from the Go library, so it has the same fields the browser needs but not Python's exact key order. Challenge timestamps are written with microseconds.

## Tests

- `go/internal/web/auth/passkeys_test.go` (registration, rename, delete) and `passkeys_login_test.go` (login, clone, replay, expiry, rate limits, wrong origin or rpId, wrong user handle, base URL checks): 36 passing tests, none skipped, on PostgreSQL 16.
- Cross-language: `testdata/passkeys_python.json` (made and verified by py_webauthn) registers and logs in on Go; `testdata/passkeys_go.json` (made by the Go software authenticator) verifies under py_webauthn in `App/tests/test_go_passkeys_golden.py`.
- Whole `go/internal/web/...`, `cmd/ubyhost-web`, `retention` packages green; `context_lint` clean.
- The existing Python parity goldens for login are unchanged (no Python file touched).

## Not done

- Browser checks (owner steps below). No screenshots: no template or CSS changed, the passkey UI is `static/passkeys.js` on the Python pages.
- The rendered Settings and login pages stay on Python until briefs 1762-1764 (PR 1033, held).
