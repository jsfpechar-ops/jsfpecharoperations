# 1764: Go Settings: explain the passkey section as Face ID / Touch ID (device-specific wording)

Status: todo — scoped 2026-11-15 (Sonnet draft). Run only after its exact-diff pass (anchors, sha256 of edited files) per [workflow](../context/workflow.md#writing-briefs-for-haiku). BLOCKED until a Go Settings page with the passkey section exists (see §2 and step 0).
Depends on: 1762 (`authpage.DeviceKind`), 1760 (open draft PR #1029: Go passkey routes; wording only here, routes untouched), 1763 (same JS hooks; this brief must not change them) and 1704 (Go settings pages, open draft PR #1029; the security page there shows passkeys read only; not in the tree on 2026-11-15) | Base commit: current tip of the working branch | Branch: task/1764-go-settings-face-id-wording
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Next: 1765 (follow-up named in §2: server messages and Help & guide)
Tier: B (Sonnet writes; wording plus one small data field)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1764 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

Hosts do not know the word "passkey". On the Go Settings page the section is explained by the device that views it: iPhone, iPad, Mac "Face ID or Touch ID"; Android "fingerprint or face"; Windows "Windows Hello"; anything else "your device's screen lock". Section title, help, add button, count label, notes, remove confirm and error text lose the word "passkey". It appears once, in the help text, as a plain aside ("Also called a passkey.") so a host who sees the system sheet of Apple or Google can connect the two.

## 2. Context

Hard rules: 2 privacy (User-Agent read per request, never stored or logged; no new field, request or cookie); 6 light mode, removing an entry is a plain form POST that works without JavaScript; 9 copy (one explanation in one place; the button does not repeat the title); 11 Go first (all template and logic work in Go; only additive strings in two Python files).

- **Go Settings status:** on 2026-11-15 `go/internal/web/auth/` has no Settings template (`acct_templates/` and `account.go` hold only e-mail, setup and deletion pages) and `grep -rn 'passkeys.title' go` is empty. The Python original is `App/app/templates/settings.html` lines 115-140 (`#settings-passkeys`). This brief edits the Go copy of that section once it exists. If it does not exist, STOP (step 0).
- **Request access:** unknown until the Settings port exists. The page data struct (built in the Go handler that renders the Settings template) needs one field `DeviceKind string` set from `authpage.DeviceKind(r.Header.Get("User-Agent"))` (same as 1762 `Page.DeviceKind`). Executor names the struct and line in the report. If importing `authpage` creates an import cycle, STOP.
- **Why not "passkey" in rows:** the list shows entries made on OTHER devices too. Section title, help and add button speak for the viewing device; the count label and rows are device-neutral. Names stay as the host or the device stored them.
- **Catalogs:** `App/scripts/go_host_i18n.py` writes each Go `i18n.json` from that package's `i18n_keys.txt` plus strings in `App/app/host_i18n.py` (cs, en) and `App/app/host_vi_i18n.py` (vi). New keys are ADDED there (go-first exception 1). Existing `passkeys.*` keys are never edited or deleted: the Python Settings page uses them until cutover. Python templates are untouched.
- **Unchanged keys** (values contain no "passkey"; executor verifies with grep, STOP if one does): `passkeys.added_on`, `passkeys.last_used`, `passkeys.never_used`, `passkeys.remove`, `passkeys.rename`, `passkeys.name`, `passkeys.rename_action`.
- **Named follow-up 1765 (not here):** (a) server messages from the 1760 routes (`passkeys.error.login_failed`, `.signed_out`, `.unavailable`, `.too_many`, `.rate_limited`, `flash.passkeys.*`) still say "passkey"; (b) the Help & guide (`guide.settings.when`, `.login`, `.passkey_title`, `.passkey1-3`, `.wrong2`, `.wrong3` in `App/app/guide_i18n.py` and `host_vi_i18n.py`) still says "passkey", and the guide is Python-owned text read by Python tests (`test_guide_coverage.py`), so editing it is not additive. (c) the stored default name `passkeys.default_name` ("Passkey"). Say in the report that the PR template's guide-update box stays unticked and why.

**Exact new keys (add to `host_i18n.py` for cs and en, `host_vi_i18n.py` for vi):**

| Key | cs | en | vi |
|---|---|---|---|
| `settings.device_login.title.apple` | Přihlášení přes Face ID nebo Touch ID | Log in with Face ID or Touch ID | Đăng nhập bằng Face ID hoặc Touch ID |
| `settings.device_login.title.android` | Přihlášení otiskem prstu nebo obličejem | Log in with fingerprint or face | Đăng nhập bằng vân tay hoặc khuôn mặt |
| `settings.device_login.title.windows` | Přihlášení přes Windows Hello | Log in with Windows Hello | Đăng nhập bằng Windows Hello |
| `settings.device_login.title.other` | Přihlášení zámkem obrazovky zařízení | Log in with your device's screen lock | Đăng nhập bằng khóa màn hình của thiết bị |
| `settings.device_login.help` | Přihlaste se bez otvírání schránky. Odkaz e-mailem dál funguje, takže ztráta zařízení vás nikdy nezamkne. Říká se tomu také passkey. | Log in without opening your inbox. The e-mail link keeps working, so losing a device never locks you out. Also called a passkey. | Đăng nhập mà không cần mở hộp thư. Liên kết qua e-mail vẫn dùng được, nên mất thiết bị cũng không bị khóa tài khoản. Còn gọi là passkey. |
| `settings.device_login.add` | Zapnout na tomto zařízení | Turn on for this device | Bật trên thiết bị này |
| `settings.device_login.unsupported` | Tento prohlížeč to neumí. Zkuste telefon nebo aktuální Safari, Chrome, Edge či Firefox. | This browser cannot do this. Try your phone, or a current Safari, Chrome, Edge or Firefox. | Trình duyệt này không hỗ trợ. Hãy thử điện thoại, hoặc Safari, Chrome, Edge hay Firefox bản mới. |
| `settings.device_login.unavailable` | Vyžaduje vlastní https adresu webu. V této instalaci není k dispozici. | This needs the site's own https address. It is not available on this installation. | Cần địa chỉ https riêng của trang. Bản cài đặt này không có tính năng này. |
| `settings.device_login.error_failed` | Zapnutí se nepovedlo. Zkuste to prosím znovu. | Turning it on did not work. Please try again. | Không bật được. Vui lòng thử lại. |
| `settings.device_login.count_label` | Zařízení s přihlášením | Devices that can log in | Thiết bị có thể đăng nhập |
| `settings.device_login.remove_confirm` | Odebrat „%(name)s“? Toto zařízení se pak přihlásí odkazem z e-mailu. | Remove “%(name)s”? That device then logs in with the e-mail link. | Xóa “%(name)s”? Thiết bị đó sẽ đăng nhập bằng liên kết qua e-mail. |

- **Parity conflict:** 1704 holds `/settings/security` byte-equal to Python through `settings_menu_golden.json`. This brief breaks that on purpose. Run it only after the owner has cut Settings over to Go (Python page retired); then regenerate that golden only where the diff is exactly the new wording. If the Python page is still live, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| the Go Settings template with `id="settings-passkeys"` (path from step 0) | edit | replace `t "passkeys.title"`, `.help`, `.unavailable`, `.add`, `.unsupported`, `.error.failed`, `.count_label`, `.remove_confirm` with the new keys; title via `{{t (printf "settings.device_login.title.%s" .DeviceKind)}}` (else an `{{if eq}}` chain); keep every `data-passkey-*` attribute, the delete/rename form actions and `data-confirm` exactly |
| the Go Settings handler/data struct (step 0) | edit | add `DeviceKind`, set from `authpage.DeviceKind(r.UserAgent())` |
| its test file | edit | render test per device kind and per language; one test that the rendered HTML contains "passkey" exactly once (case-insensitive) in cs, en, vi when the page has one entry and an unsupported note |
| that package's `i18n_keys.txt` | edit | append the 11 `settings.device_login.*` keys (title counted four times) |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | add the keys above, nothing else |
| the generated `i18n.json` file(s) | regenerate | `cd App && python3 scripts/go_host_i18n.py` |
| `go/.../testdata/*` goldens | edit only if they break | only where the diff is exactly the new wording; list in report |
| `docs/tasks/1764-report.md` | create | the report (§9) |

## 4. Steps

0. Checks (repo root): `grep -rln 'settings-passkeys' go/internal | head -3` must print a Go template path, and `grep -rn 'data-passkey-add' go/internal | head -3` must print a hit in it; `ls go/internal/web/auth/authpage/device.go` must succeed (1762 done). Any check fails: STOP and report which. Note the template path, the data struct and its builder line.
1. Verify the seven unchanged keys contain no "passkey" in cs, en, vi (`grep -n '"passkeys.rename"' App/app/host_i18n.py App/app/host_vi_i18n.py | tail -10`, one per key).
2. Add keys to the two Python files and `i18n_keys.txt`; run the generator; `--check` exits 0.
3. Add `DeviceKind` to the struct and handler; edit the template; extend tests; fix goldens only for wording.
4. Run §6 and write the report.

## 5. Do not touch

The login page; `go/internal/web/auth/passkeys.go` and any 1760 route or message; `App/app/static/passkeys.js` and any `?v=` string; `App/app/templates/*`; existing i18n keys; `guide_i18n.py`; `UBYHOST_GO_PATHS`; filing code.

## 6. Commands

- `cd App && python3 scripts/go_host_i18n.py --check 2>&1 | tail -10` exits 0
- `cd go && gofmt -l . | tail -5` prints nothing; `go vet ./internal/web/... ./internal/hostweb/... 2>&1 | tail -20` silent
- `cd go && go test ./internal/web/auth/... ./internal/hostweb/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, none skipped
- `cd App && .venv/bin/python -m pytest tests/test_login_*.py tests/test_auth_*.py tests/test_passkeys.py -q --tb=short -x 2>&1 | tail -30` (test-map row "Login, 2FA, passkeys"; proves Python is unchanged)
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Rules 7 and 10 apply (host page template change): `cd App && .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_0786_settings_geometry_browser.py test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` green, 0 skipped (the host-pages row of the test-map; drop a file name only if it does not exist and say so); one 390, 768 and 1280 px screenshot of the Settings security section with the longest strings (Czech `other`, Vietnamese `other`, with an entry row and the unsupported note shown); write per page what you saw; tick the [design-system checklist](../design/design-system.md).

## 7. Acceptance

- Go Settings with an iPhone UA titles the section "Log in with Face ID or Touch ID" (en); Android, Windows and desktop Linux show their line.
- The rendered section contains "passkey" exactly once (the help aside) in cs, en and vi; the 11 new strings match §2 character for character.
- No User-Agent is stored or logged (grep the diff for `Printf` of the UA, `slog`, `db.`).
- Remove still posts to `/account/passkeys/{id}/delete` as a plain form; JavaScript off keeps the list and remove working.
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report when: step 0 fails; an import cycle; a template cannot call `t` with the new keys; a golden differs by more than the wording; a file outside §3 must change; a test needs a skip; the Settings section is not read per request (cached HTML would leak one device's label to another).

## 9. Report

`docs/tasks/1764-report.md`: commits, command outputs (last 30 lines), struct and line used for `DeviceKind`, screenshots with the per-page description, the follow-up 1765 list, what was left undone.

## Rollout and rollback

- **Rollout:** dormant until the Go Settings page is switched on; nothing is added to `UBYHOST_GO_PATHS` here.
- **Rollback:** revert the PR.

## Owner steps

None.
