# 1763: Go login: open the device prompt automatically on remembered devices

Status: todo — scoped 2026-11-15 (Sonnet draft). Run only after its exact-diff pass per [workflow](../context/workflow.md#writing-briefs-for-haiku).
Depends on: 1760 (passkey routes in Go, open draft PR #1029), 1762 (device labels) | Base commit: current tip of the working branch | Branch: task/1763-go-login-autoopen
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (small client-side change plus tests; the JavaScript is the only non-Go code and cannot be avoided)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1763 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

After a successful passkey login or passkey add on a device, `passkeys.js` stores the flag `localStorage["ubyhost.deviceLogin"] = "1"`. On the next visit to the Go login page with the flag, the device prompt opens by itself. If the browser refuses (Safari wants a tap) or the person cancels, the normal form with the big button stays, with no error shown for the automatic attempt. Devices without the flag never auto-open.

## 2. Context

Hard rule 2: the flag is a `localStorage` entry, not a cookie, never sent to the server, holds no personal data (the constant `"1"`). State exactly this in the report; no `retention.py` line is needed because nothing reaches the server. No new request: the auto attempt calls the same `/login/passkey/options` and `/login/passkey` as the button.

`App/app/static/passkeys.js` (308 lines) is the one script both stacks load. Go has no static file server of its own in the tree (grep found none), so the file is served from `App/app/static/`; the executor confirms with `grep -rn "static" go/cmd/ubyhost-web/*.go | head` and STOPS if Go serves a copy elsewhere. Python must stay unbroken and gain nothing: the new behaviour runs only when the login button wrapper carries the attribute `data-passkey-autostart`, which only the Go template emits. Without it the script behaves as today. Writing the flag happens on any page after a success (harmless for Python).

Relevant code: `loginWithButton` (about line 261), `finishLogin` (217), `addPasskey` (190, success branch redirects), `init` (285-300). `showError` already ignores `NotAllowedError` and `AbortError`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/passkeys.js` | edit | helpers `rememberDevice()`, `forgetDevice()`, `deviceRemembered()` wrapped in try/catch (storage can throw); set flag in `finishLogin` success and `addPasskey` success; in `init`, if `data-passkey-autostart` and flag set, call a quiet variant of `loginWithButton`; clear flag on server error whose HTTP status is 400 or 404 (no credential), keep it on cancel |
| `go/internal/web/auth/authpage/templates/login.html` | edit | add `data-passkey-autostart` to the `data-passkey-login` div; bump `?v=` on the passkeys.js script line (new value `20261115-auto1`) |
| `go/internal/hostweb/layout/shell.html` | edit | bump only the `?v=` on line 54 to `20261115-auto1` |
| `go/internal/web/auth/authpage/authpage_test.go` | edit | assert the attribute and the new `?v=` in the rendered login page |
| `App/tests/passkeys_client_cases.js`, `App/tests/test_passkeys_client.cjs` | edit | cases: flag set after login success; auto attempt with flag; no auto attempt without flag; `NotAllowedError` on auto attempt shows no error and keeps the button; storage throwing does not break the page |
| `App/tests/test_passkeys_client_browser.py` | edit | one browser case: flag preset, auto attempt rejected with NotAllowedError, big button visible and enabled at 390 px |
| `docs/tasks/1763-report.md` | create | the report (§9) |

Do NOT bump `?v=` in `App/app/templates/login.html` or `base.html` (Python stays as is). Clearing the flag when the last passkey is removed in Settings is OUT OF SCOPE (it needs the Settings page JS); the "no credential" clear covers a stale flag.

## 4. Steps

0. Checks: `grep -cF 'data-passkey-login-button' App/app/static/passkeys.js` prints 2; `grep -cF '20261102-0789a' go/internal/web/auth/authpage/templates/login.html` prints 1; else STOP.
1. Edit `passkeys.js` and add the node test cases; run the node test.
2. Edit the two Go templates and `authpage_test.go`.
3. Add the browser case.
4. Run §6 and write the report.

## 5. Do not touch

Python templates; `passkeys.py`; Settings pages; the Go passkey routes (1760); rate limits; any new dependency; cookies.

## 6. Commands

- `node --test App/tests/test_passkeys_client.cjs 2>&1 | tail -30` passes
- `cd App && .venv/bin/python -m pytest tests/test_passkeys_client_browser.py tests/test_passkeys.py -q --tb=short -x 2>&1 | tail -30` passes, 0 skipped
- `cd go && gofmt -l . | tail -5` empty; `go test ./internal/web/auth/... ./internal/hostweb/... -count=1 2>&1 | tail -30` passes
- `cd App && .venv/bin/python -m pytest tests/test_login_*.py tests/test_auth_*.py -q --tb=short -x 2>&1 | tail -30` (Python login unchanged)
- Rules 7 and 10: `tests/test_layout_lint_browser.py` green, 0 skipped; 390, 768 and 1280 px screenshots of the login page, with and without the flag; write per page what you saw; tick the [design-system checklist](../design/design-system.md).
- `python3 scripts/context_lint.py 2>&1 | tail -10` clean

## 7. Acceptance

- With the flag preset and a fake authenticator, the prompt starts without a click on the Go login page; without the flag it does not.
- A rejected auto attempt leaves no error text and the button works on tap.
- No cookie is set; the only storage key is `ubyhost.deviceLogin`.
- Python login page behaves as before (no `data-passkey-autostart` there).
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop when: Go serves its own copy of the script; the auto attempt would need a new endpoint; conditional-mediation autofill breaks (existing node cases fail); a skip is needed.

## 9. Report

`docs/tasks/1763-report.md`: commits, outputs (last 30 lines), screenshots, the privacy statement for the flag, what was left undone (Settings-page flag clearing).

## Rollout and rollback

- **Rollout:** dormant on Go until 1761; the script change is live for Python but inert there.
- **Rollback:** revert the PR.

## Owner steps

None.
