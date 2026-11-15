# 1762: Go login: device-specific passkey button label (no word "passkey" on the login page)

Status: todo — scoped 2026-11-15 (Sonnet draft). Run only after its exact-diff pass (anchors, sha256 of edited files) per [workflow](../context/workflow.md#writing-briefs-for-haiku).
Depends on: 1760 (open draft PR #1029: passkey routes in Go; this brief changes wording only and must not touch those routes) and 1502 (Go login page in `authpage`; already in the tree) | Base commit: current tip of the working branch | Branch: task/1762-go-login-face-id-label
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Next: 1763 (remembered-device auto-open)
Tier: B (Sonnet writes; wording and one small helper)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1762 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

Hosts do not know the word "passkey". On the Go login page the passkey button reads by device: iPhone, iPad, Mac "Log in with Face ID or Touch ID"; Android "Log in with fingerprint or face"; Windows "Log in with Windows Hello"; anything else "Log in with your device's screen lock". Settings wording is brief 1764. The one-time security prompt (`security_prompt`, shell dialog) loses the word "passkey" too.

## 2. Context

Hard rules: 2 privacy (User-Agent is read per request to pick a label, never stored or logged; no new field, no new outbound request); 6 light mode, forms work without JavaScript; 9 copy: the button text is the explanation, add no hint line; 11 Go first (all work below is Go; the label is rendered on the server, so no JavaScript change and no flash).

- Today `go/internal/web/auth/authpage/templates/login.html` lines 50-57 render `{{t "login.passkey"}}` inside `<div class="auth-passkey" data-passkey-login data-passkey-supported hidden>`. JavaScript only unhides it when WebAuthn exists. Keep that.
- `Page` in `go/internal/web/auth/authpage/authpage.go` (built in `Render`, about line 118) has no request data. Add one field `DeviceKind string` filled from `r.Header.Get("User-Agent")`.
- The one-time prompt already exists: `layout.security_prompt` in `go/internal/hostweb/layout/shell.html` (lines 521-545), keys `security_prompt.passkey` ("Add a passkey") and `security_prompt.passkey_help`. This is a wording change only. It gets the neutral "else" wording (the layout package has no request data; device-specific wording there is out of scope).
- Catalogs: `App/scripts/go_host_i18n.py` writes each `i18n.json` from the keys in `i18n_keys.txt` and the strings in `App/app/host_i18n.py` (cs, en) and `App/app/host_vi_i18n.py` (vi). Only cs, en, vi exist. Adding NEW keys to those two Python files is go-first exception 1 (port plumbing the Go catalog needs); Python templates never read the new keys, so Python behaviour is unchanged. Do NOT edit or reuse the existing `login.passkey`, `security_prompt.passkey` keys (Python still uses them until cutover).

**Exact new keys (add to `host_i18n.py` for cs and en, `host_vi_i18n.py` for vi):**

| Key | cs | en | vi |
|---|---|---|---|
| `login.device.apple` | Přihlásit se přes Face ID nebo Touch ID | Log in with Face ID or Touch ID | Đăng nhập bằng Face ID hoặc Touch ID |
| `login.device.android` | Přihlásit se otiskem prstu nebo obličejem | Log in with fingerprint or face | Đăng nhập bằng vân tay hoặc khuôn mặt |
| `login.device.windows` | Přihlásit se přes Windows Hello | Log in with Windows Hello | Đăng nhập bằng Windows Hello |
| `login.device.other` | Přihlásit se zámkem obrazovky zařízení | Log in with your device's screen lock | Đăng nhập bằng khóa màn hình của thiết bị |
| `security_prompt.device_login` | Přihlašovat se zámkem obrazovky zařízení | Log in with your device's screen lock | Đăng nhập bằng khóa màn hình của thiết bị |
| `security_prompt.device_login_help` | Face ID, otisk prstu nebo PIN zařízení. Bez e-mailu a bez kódu. | Face ID, a fingerprint or your device PIN. No inbox, no code. | Face ID, vân tay hoặc mã PIN của thiết bị. Không cần hộp thư, không cần mã. |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/authpage/device.go` | create | `DeviceKind(userAgent string) string` returning `apple`, `android`, `windows` or `other` |
| `go/internal/web/auth/authpage/device_test.go` | create | table test, 10+ real-looking UA strings, empty UA gives `other` |
| `go/internal/web/auth/authpage/authpage.go` | edit | `Page.DeviceKind`, set in `Render` |
| `go/internal/web/auth/authpage/templates/login.html` | edit | button text `{{t (printf "login.device.%s" .DeviceKind)}}`; fall back to `login.device.other` if the template engine cannot do `printf` keys (use `{{if eq .DeviceKind "apple"}}` chain) |
| `go/internal/web/auth/authpage/authpage_test.go` | edit | render test per device kind and per language |
| `go/internal/web/auth/authpage/i18n_keys.txt` | edit | append the four `login.device.*` keys |
| `go/internal/hostweb/layout/shell.html` | edit | prompt uses `security_prompt.device_login` and `_help` (lines 529-533 only) |
| `go/internal/hostweb/layout/i18n_keys.txt` | edit | append the two `security_prompt.device_login*` keys |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | add the six keys, nothing else |
| the two generated `i18n.json` files | regenerate | `cd App && python3 scripts/go_host_i18n.py` |
| `go/internal/hostweb/layout/testdata/*` | edit only if goldens break | regenerate with the package's existing golden flag, list in report |
| `docs/tasks/1762-report.md` | create | the report (§9) |

Detection rules (order matters): UA contains `iPhone`, `iPad`, `iPod` or `Macintosh` gives `apple` (iPadOS reports as Macintosh; both want Face ID or Touch ID); contains `Android` gives `android`; contains `Windows` gives `windows`; else `other`. No library.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/auth/authpage/device.go` must fail (file absent); `grep -cF '{{t "login.passkey"}}' go/internal/web/auth/authpage/templates/login.html` prints 1; `git log --oneline origin/docs/final-go-sqlite-briefs -3` readable. Else STOP.
1. Add keys to the two Python files and the two `i18n_keys.txt`; run the generator; `--check` exits 0.
2. Add `device.go`, `device_test.go`, edit `authpage.go`.
3. Edit `login.html` and `shell.html`; extend `authpage_test.go`; fix goldens only where the diff is exactly the new wording.
4. Run §6 and write the report.

## 5. Do not touch

Settings pages and their "passkey" wording; `go/internal/web/auth/passkeys.go` (brief 1760); `App/app/static/passkeys.js`; any `?v=` string; `App/app/templates/*`; existing i18n keys; `UBYHOST_GO_PATHS`; filing code.

## 6. Commands

- `cd App && python3 scripts/go_host_i18n.py --check 2>&1 | tail -10` exits 0
- `cd go && gofmt -l . | tail -5` prints nothing; `go vet ./internal/web/... ./internal/hostweb/... 2>&1 | tail -20` silent
- `cd go && go test ./internal/web/auth/... ./internal/hostweb/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, none skipped
- `cd App && .venv/bin/python -m pytest tests/test_login_*.py tests/test_auth_*.py tests/test_passkeys.py -q --tb=short -x 2>&1 | tail -30` (test-map row "Login, 2FA, passkeys"; proves Python is unchanged)
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Rules 7 and 10 apply (login and the prompt are template changes): `cd App && .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30` green, 0 skipped; plus the geometry test of the touched pages named in the test-map; one 390, 768 and 1280 px screenshot of the login page in each of the four label variants' longest text (Czech `other`, Vietnamese `other`): the button must not clip or wrap badly. Write per page what you saw in the report; tick the [design-system checklist](../design/design-system.md).

## 7. Acceptance

- Go login with an iPhone UA shows "Log in with Face ID or Touch ID" (en); Android, Windows and desktop Linux show their line; the word "passkey" is absent from the login page in cs, en and vi (grep the rendered HTML, case-insensitive).
- No User-Agent is stored or logged (grep the diff for `Printf`, `slog`, `db.`).
- Page still works with JavaScript off (the e-mail form is untouched; the button stays `hidden` until JS).
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report when: an anchor is missing; the layout package cannot call `t` with the new keys without a new loader; a golden differs by more than the wording; a file outside §3 must change; a test needs a skip.

## 9. Report

`docs/tasks/1762-report.md`: commits, command outputs (last 30 lines), screenshots with the per-page description, what was left undone.

## Rollout and rollback

- **Rollout:** dormant until brief 1761 switches Go login on; nothing is added to `UBYHOST_GO_PATHS` here.
- **Rollback:** revert the PR.

## Owner steps

None.
