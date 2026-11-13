# 1500: Go auth, rest of "Port login and accounts" (split plan)

Status: blocked — handover plan, not an executable brief. The brief writer stopped at the 60k-token checkpoint (AGENTS.md). Each row below gets its own brief-writer chat (Opus, tier A) that writes `NNNN-go-auth-<part>.md` plus a sidecar `NNNN-files/` (Go files stored as `*.go.txt`, as in 1321-files).
Depends on: none | Base commit: b5f353682 | Branch: none
Executor: none (do not run)

## 1. Objective

Port the 28 routes of `App/app/routes/admin_accounts.py`, `signup.py` and `passkeys.py` that have no Go handler yet ([remaining](../plans/go-full-move-remaining.md) §2a). The goal is that every path in this area can be switched to Go as a whole, closing the `/login/2fa` and `/admin/users` method gaps first.

## 2. Context (checked against the code at b5f353682)

- Go already serves the 18 routes of brief 1282 (`go/internal/web/auth/auth.go` `Routes`), including `GET /login/2fa` and `GET /admin/users`. These are live code: new files only, exact diffs for `auth.go` `Routes` (append rows, nothing else).
- Library code that exists and must be reused, not re-written: `session/loginlink.go` (issue, peek, consume, rate keys, 2FA lockout), `session/accounts.go` (create, email taken, set email), `session/issue.go` (session, device cookie, 2FA pending token), `session/totp.go`, `signup/` (Register, PendingAccount, Activate, rate limit), `mail.SendNow`, `mail/auth_signup.go` (the three sign-up mails).
- Missing in Go, needed first: a server-side Turnstile check (`App/app/turnstile.py`; Go has none, only the CSP in `main.go`); `_finish_login` and `_keep_login_language` (`admin_accounts.py` 30-58 and the `_finish_login` helper); the `link_mail` builder (`mail_notify.py` 2672-2701, kinds in `LINK_MAIL`), `email_changed` (2704-), `passkey_added`, `workspace_deletion` mails. The mail package belongs to the mail thread: new files only (`go/internal/mail/auth_link.go`), with golden output from Python like `auth_signup.go`.
- Templates to port (lines): login 95, login_sent 30, login_link 21, two_factor_login 41, account_accept 31, two_factor_setup 41, two_factor_recovery 23, account_email_confirm 20, signup 69, signup_sent 12, signup_verify 24, admin_operations 267. Rendering through `hostweb/layout.Render` (read-only); signed-out rendering with `host == nil` must be checked first.
- **go-webauthn is approved (decisions.md line 61) but is not in `go/go.mod` or `go/go.sum`.** Adding it pulls transitive modules (CBOR, JWT, TPM, x/crypto). The passkey briefs need the owner to confirm the approval covers them, and a session with network access to the Go proxy to write `go.sum`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/1500-go-auth-split.md` | create | this plan |

No other file may change.

## 4. Steps

None: this plan is not run. The split, one brief each, in this order:

| Brief | Routes | Python | Closes / switches | Notes |
|---|---|---|---|---|
| 1501 shared | none (helpers) | `turnstile.py`, `_finish_login`, `_keep_login_language`, `mail_notify.link_mail`, `email_changed` | nothing | Turnstile siteverify is a new outbound request (same host and reason as Python); mail builders in a new `mail/auth_link.go` with goldens |
| 1502 login | `GET`/`POST /login`, `GET`/`POST /login/link` | 60-267 | `/login`, `/login/link` fully Go | device cookie skip of Turnstile, rate limits 3/15 min, 10/day, 10 per IP, 20 bad links; `no-store` and `no-referrer` on the link page |
| 1503 2fa login | `POST /login/2fa` | 275-316 | `/login/2fa` (collision) | 429 locked, 401 invalid, audit `two_factor_failed` |
| 1504 admin users | `POST /admin/users`, `/admin/users/{id}/invite`, `/admin/users/{id}/email` | 731-853 | `/admin/users` (collision) | `mail.SendNow` after enqueue; own-account email change re-attaches the session |
| 1505 account setup | `GET`/`POST /account/accept`, `GET`/`POST /account/2fa/setup` | 420-540 | both paths | QR via `skip2/go-qrcode` (already in go.mod); 10-minute fresh-login rule |
| 1506 email change | `POST /account/email`, `GET`/`POST /account/email/confirm` | 612-725 | `/account/email*` | link to new address, notice to old |
| 1507 signup | `GET`/`POST /signup`, `GET`/`POST /signup/verify` | `signup.py` 66-176 | `/signup*` | 410 on expired verify |
| 1508 operations | `GET /admin/operations` | 929-950 | `/admin/operations` | 267-line template; may need two briefs |
| 1509 deletion | `POST /admin/users/{id}/schedule-deletion` | 1042- | with 1504 | `workspace_deletion` mail is shared with the retention job: coordinator names the owner |
| 1510 export | `POST /admin/users/{id}/export` | 1013-1041 | with 1504 | uses `workspace_export.build_workspace_zip`: exports thread first |
| 1511-1513 passkeys | the 6 `passkeys.py` JSON routes | 94-253 | `/account/passkeys*`, `/login/passkey*` | blocked until go-webauthn is in go.mod (see §2) |

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `App/`, `go/go.mod`, `go/go.sum` (until the owner confirms §2), `docs/context/`.

## 6. Commands

None.

## 7. Acceptance

- [ ] Each row in §4 has its own brief, or a `blocked` line naming why.

## 8. Stop and ask

Do not run this file. A brief writer who finds a row wrong stops and tells the orchestrator.

## 9. Report

No report: each follow-up brief writes its own.

## Risk list (for the reviewer)

None: this file changes no code.

## Owner steps

1. Confirm in chat whether the go-webauthn approval covers its transitive modules, so the passkey briefs can add it to `go/go.mod`.
