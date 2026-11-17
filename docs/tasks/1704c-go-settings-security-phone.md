# 1704c: Go Settings security and phone pages (GET /settings/security, /settings/phone)

Status: done (2026-11-17; reviewed, Go tests green; Go UX gate pending at 1705)
Depends on: 1704b (done, on this branch: `go/internal/web/settings/`, its stub templates and the `// 1704c:` markers; verified at 1318f4f), 1760 passkey and push routes (registered, read only here) | Base commit: current tip of the working branch | Branch: task/1704c-go-settings-security-phone
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 16)
Tier: B (Sonnet wrote the exact-diff pass; the orchestrator reads the diff of the risk-listed files, see the end). Part of [1704](1704-go-settings-menu-pages.md); brief 1764 builds on it.

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1704c step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR (the line `Branch:` above is the name the brief had when it was planned). Acceptance checks use `git log --oneline --grep='^1704c step'`, never a fixed base commit.

## 1. Objective

Fill in the two groups 1704b left empty: `GET /settings/security` (logout-all row, passkeys list, two-factor state) and `GET /settings/phone` (PWA install row, urgent alerts row with the push devices). This is the `group == 'security'` and `group == 'phone'` part of `App/app/templates/settings.html` (lines 105 to 247) and the values `_settings_page` builds for them in `App/app/routes/admin.py` (`passkeys`, `passkeys_available`, `push_available`, `push_key`, `push_devices`, and `current_user.totp_enabled`). Both pages are read only: adding, renaming and removing a passkey, removing a push device, logout-all and the two-factor forms post to the routes that already exist. The routes are dormant: nothing is added to `UBYHOST_GO_PATHS` (brief 1705 switches).

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched; 2 privacy: no new personal-data field, no retention line (the passkey name and the device name are already stored and listed by Python), no outbound request; 3 fixtures are made up; 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 light mode, every form works without JavaScript (the Go forms carry `<input type="hidden" name="_csrf" value="{{csrf}}">`; Python's `csrf.js` adds it in the browser, this is the only intended markup difference); 11 Go first: the tests are Go only with hand-written expected strings (no Python golden script, no `App/` file).

**All code is pre-written, compiled and tested** (in a throwaway copy of this branch, with PostgreSQL 16). Sidecars: `docs/tasks/1704c-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. One existing file, `settings.go`, gets four small edits (step 2).

| sha256 | file | action | lines |
|---|---|---|---|
| `572aa0b2c324c262ecfbe8d016071b06d3d7308e671356dafe9034931106aee0` | `go/internal/web/settings/security.go` | create | 69 |
| `42c4d918c5e03f983bab9ba5563f383061de869453beba57962c2808664f3aca` | `go/internal/web/settings/phone.go` | create | 79 |
| `4161b90e0fc75f302781aa08fd250aed7fd4bed88e0dd3e176b69d823811c880` | `go/internal/web/settings/security_phone_test.go` | create | 355 |
| `9dcbed660633d18e1f7027e9943dd1ee8803a0892fd624bfd29f3640ae9a43e9` | `go/internal/web/settings/templates/group_security.tmpl` | replace (1704b stub) | 109 |
| `2aeb79aec92f13c574e2e4ecb50d077d0e6547d6fe13f7977036cd5e2e4261e2` | `go/internal/web/settings/templates/group_phone.tmpl` | replace (1704b stub) | 59 |
| `a4599aea796d202c0aeac1b8d32ff11443da2d4913f788df702705c1b446ba60` | `go/internal/web/settings/i18n_keys.txt` | replace (adds 17 lines) | 39 |
| `5bd111150b5f1a06b544d6ef5753ee0efa1c9f276f8b1269e7bd9ca25e552593` | `go/internal/web/settings/i18n.json` | replace (generated) | 632 |
| `3a9ab15b2f5884523bc2ef6cfb128bac85626955f513b9b672bce4d4e5ce1ade` | `go/cmd/ubyhost-web/register_web_settings_security.go` | create | 28 |
| `2c62902933af8d601e85679e538b6615aa62d38cd4e2d6b88d7f7341368a41a5` | `go/cmd/ubyhost-web/register_web_settings_security_test.go` | create | 26 |
| `5bbd6f718143cf1ad606ec32eeaed17ce75bad2295cef439983ef4a4cd7e6c02` | `go/internal/web/settings/settings.go` | edit (step 2; hash after the edits) | 123 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- `security.go`: `SecurityData` (fields `TOTPEnabled`, `PasskeysAvailable`, `Passkeys []Passkey`) is the one page-data struct of the security page and `loadSecurity` the one function that builds it. **For brief 1764:** add `DeviceKind string` to `SecurityData` in `go/internal/web/settings/security.go` and set it in `loadSecurity`; edit the template `settings.passkeys` in `group_security.tmpl` (keeps `id="settings-passkeys"` inside `id="settings-security"` and the `passkeys.*` keys); do not touch the routes. Both queries are keyed by `h.Account.ID` (Python reads `auth.current_user`, so an admin previewing a host still sees the admin's own passkeys and two-factor state; a test pins it), like 1704b's account row. `authpage.PasskeysAvailable(getenv)` is the existing port of `passkeys.available()`.
- `phone.go`: `PhoneData` (`PasskeysAvailable`, `PushAvailable`, `PushKey`, `Devices []PushDevice`) and `loadPhone`. `PushAvailable` is Python's `_push_available`: web push on (`UBYHOST_WEB_PUSH` not 0, false or no) and `h.Workspace.ID == h.Account.ID` (no admin preview). Only then does it read `pushsend.Sender.PublicKey` (the existing port of `push.public_key()`; like Python it makes the VAPID key on first use) and the devices (`push.devices_for` order: `created_at, id`, keyed by `h.Account.ID`). `webPushOn` is a four-line copy of the unexported `push.enabled` ports in `pushweb` and `ubyport` (they cannot be imported; a table test pins it).
- `templates/group_security.tmpl`: `settings.group.security` is the `settings_group('security', ...)` wrapper and the logout-all row and the two-factor block; the passkeys list is its own template `settings.passkeys` (dot is `*SecurityData`), the section 1764 edits. The help text of the passkeys row is `passkeys.help`, plus a space and `passkeys.unavailable` when passkeys are not available, as Python builds it.
- `templates/group_phone.tmpl`: `settings.group.phone`. The install help is the escaped `pwa.install.help` followed by the markup `<p class="ui-sub" data-pwa-other>` (what Jinja's `~` with a `{% set %}` block produces; the Go template builds it with `safe` and `html`). All `data-*` hooks and ids keep Python's names (the static JS `pwa.js` and `push.js` drive them).
- `settings.go` edits: the two fields `Security` and `Phone` in `pageData`, the two entries in `loaders`, and two comments that said "empty until then". Nothing else of the shell changes.
- `i18n_keys.txt` / `i18n.json`: the 1704b keys plus `passkeys.*`, `pwa.install.*` and 15 `push.*` keys, written by `App/scripts/go_host_i18n.py` (verified with a stub for `fastapi`; the check in step 4 is the real one).
- `register_web_settings_security.go`: an `init()` that adds `GET /settings/security` and `GET /settings/phone` through `registerRoutes`, in a file of its own (1704b's `register_web_settings.go` is not edited).
- Tests (all Go, expected strings written by hand from the seed in `security_phone_test.go` on top of 1704b's `seed`): signed-out redirects for both pages; the full English security page for host 2 on an https installation (logout-all form, two passkeys in id order with Prague times, never-used text, the name with quotes and markup escaped in text, attribute and confirm message, 5 post forms all with `_csrf`, two-factor off shows only the setup link, host 3's key and the two-factor forms absent); the default http installation (no add button, unavailable text); host 3 with two-factor on (state card, move and disable forms) and only its own key; the admin with no passkey; an admin previewing host 2; cs and vi; the phone page (install row, escaped help plus paragraph, push key of 87 base64url characters that is stable across requests, devices in created order, the nameless one as "Device", 2 post forms with `_csrf`, host 3's device absent); no passkey hint on http; `UBYHOST_WEB_PUSH=0/false/no` removes the push row and the devices; host 3 sees only its device; an admin preview gets no push row; the index draws neither body; `webPushOn`; and the route test.

**Accepted differences (all intended):** the Go forms add `_csrf`; the page `<title>` is "Settings" on every group (the 1704b rule; Python's title is the same `nav.settings`); Python builds the passkey and push values for every group, Go reads them only for its own group; the Go `html/template` escapes `"` as `&#34;` (Jinja: `&#34;` as well) and `'` as `&#39;`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/settings/security.go` | create | `SecurityData`, `Passkey`, `loadSecurity` |
| `go/internal/web/settings/phone.go` | create | `PhoneData`, `PushDevice`, `loadPhone`, `webPushOn` |
| `go/internal/web/settings/security_phone_test.go` | create | Go tests with a seed and hand-written expectations |
| `go/internal/web/settings/templates/group_security.tmpl` | replace | the real security group (1704b stub) |
| `go/internal/web/settings/templates/group_phone.tmpl` | replace | the real phone group (1704b stub) |
| `go/internal/web/settings/i18n_keys.txt` | replace | adds the passkeys, pwa and push keys |
| `go/internal/web/settings/i18n.json` | replace | the generated catalog |
| `go/internal/web/settings/settings.go` | edit | two `pageData` fields, two `loaders` entries, two comments |
| `go/cmd/ubyhost-web/register_web_settings_security.go` | create | registers the two GET routes |
| `go/cmd/ubyhost-web/register_web_settings_security_test.go` | create | route registration test |
| `docs/tasks/1704c-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1704c-report.md` | create | the report (§9) |
| `docs/tasks/1704-go-settings-menu-pages.md`, this file | edit | Status only (step 8) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF "{% if group == 'security' %}{% call settings_group('security', t('settings.group.security')) %}" App/app/templates/settings.html | tail -1` prints `1`.
   - `grep -cF "{% if group == 'phone' %}{% call settings_group('phone', t('settings.group.phone')) %}" App/app/templates/settings.html | tail -1` prints `1`.
   - `grep -cF 'def _own_passkeys(request: Request):' App/app/routes/admin.py | tail -1` prints `1`.
   - `grep -cF 'func PasskeysAvailable(getenv func(string) string) bool {' go/internal/web/auth/authpage/authpage.go | tail -1` prints `1`.
   - `grep -cF 'func (s *Sender) PublicKey(ctx context.Context) (string, error) {' go/internal/pushsend/pushsend.go | tail -1` prints `1`.
   - `grep -cF 'POST /account/push/devices/{id}/delete' go/cmd/ubyhost-web/register_web.go | tail -1` prints `1`.
   - `grep -cF '{"POST /account/passkeys/{id}/delete", "/account/passkeys/{id}/delete", x.passkeyDelete},' go/internal/web/auth/passkeys.go | tail -1` prints `1`.
   - The four anchors of step 2, each printing `1`:
     - `grep -cF '// The groups security and phone are brief 1704c; their extension points are' go/internal/web/settings/settings.go | tail -1`
     - `grep -cF '// and group_phone.tmpl define the two groups of brief 1704c (empty until then).' go/internal/web/settings/settings.go | tail -1`
     - `grep -cF '// 1704c: add the fields' go/internal/web/settings/settings.go | tail -1`
     - `grep -cF '// 1704c: add "security" and "phone" here (loadSecurity, loadPhone).' go/internal/web/settings/settings.go | tail -1`
   - The 1704b files this brief replaces or edits are still the 1704b versions (one call, five `: OK` lines):

     ```bash
     sha256sum -c - <<'EOF2' 2>&1 | tail -6
     4b816f535c1ca7d3b13f47f3e35a4b8c3ee5a6c48003c86abe2cde653741f93a  go/internal/web/settings/settings.go
     2165009745723bcc76f66ccb00e5ee16303500753fe8d0642d2e5c2fb6580cb8  go/internal/web/settings/templates/group_security.tmpl
     57d45a03e25b3a595895c21f809d39305efd6beb3e96b9d0c5290f8fa0f518b4  go/internal/web/settings/templates/group_phone.tmpl
     cfe0c9f4c02828594325c0779882ffb54ca0f4ebf08ec9123cc33f4241761fa1  go/internal/web/settings/i18n_keys.txt
     3bbbd1a3191e5b17516ed2cbf532393d93d4c14a894f00aad7c87ea60c0cdfca  go/internal/web/settings/i18n.json
     EOF2
     ```
   - `grep -rcF '"GET /settings/security"' go/cmd/ubyhost-web | grep -v ':0$' | tail -3` prints nothing (the routes are not registered yet).
   - `ls go/internal/web/settings/security.go go/internal/web/settings/phone.go go/cmd/ubyhost-web/register_web_settings_security.go 2>&1 | tail -3` says "No such file" three times.
   - `find docs/tasks/1704c-files -name '*.txt' | wc -l | tail -1` prints `9`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1704c-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF2' 2>&1 | tail -10
   572aa0b2c324c262ecfbe8d016071b06d3d7308e671356dafe9034931106aee0  go/internal/web/settings/security.go
   42c4d918c5e03f983bab9ba5563f383061de869453beba57962c2808664f3aca  go/internal/web/settings/phone.go
   4161b90e0fc75f302781aa08fd250aed7fd4bed88e0dd3e176b69d823811c880  go/internal/web/settings/security_phone_test.go
   9dcbed660633d18e1f7027e9943dd1ee8803a0892fd624bfd29f3640ae9a43e9  go/internal/web/settings/templates/group_security.tmpl
   2aeb79aec92f13c574e2e4ecb50d077d0e6547d6fe13f7977036cd5e2e4261e2  go/internal/web/settings/templates/group_phone.tmpl
   a4599aea796d202c0aeac1b8d32ff11443da2d4913f788df702705c1b446ba60  go/internal/web/settings/i18n_keys.txt
   5bd111150b5f1a06b544d6ef5753ee0efa1c9f276f8b1269e7bd9ca25e552593  go/internal/web/settings/i18n.json
   3a9ab15b2f5884523bc2ef6cfb128bac85626955f513b9b672bce4d4e5ce1ade  go/cmd/ubyhost-web/register_web_settings_security.go
   2c62902933af8d601e85679e538b6615aa62d38cd4e2d6b88d7f7341368a41a5  go/cmd/ubyhost-web/register_web_settings_security_test.go
   EOF2
   ```

   Every line must end with `: OK` (9 lines). Then commit: `git add go/internal/web/settings go/cmd/ubyhost-web && git commit -m "1704c step 1" | tail -3` (the tree does not build yet; that is expected until step 2 is done).

2. Edit `go/internal/web/settings/settings.go`: four exact replacements, done by one script (repo root; each `old` must occur exactly once, else the script prints `ANCHOR` and changes nothing; `\t` is one tab). The file does not compile before all four are done.

   ```bash
   python3 - <<'PY'
   p = "go/internal/web/settings/settings.go"
   s = open(p, encoding="utf-8").read()
   edits = [
       ("// The groups security and phone are brief 1704c; their extension points are\n// marked \"1704c\" below. Nothing routes here until the owner adds the paths to\n// UBYHOST_GO_PATHS (brief 1705).\n",
        "// The groups security and phone are brief 1704c (security.go, phone.go).\n// Nothing routes here until the owner adds the paths to UBYHOST_GO_PATHS\n// (brief 1705).\n"),
       ("// and group_phone.tmpl define the two groups of brief 1704c (empty until then).\n",
        "// and group_phone.tmpl define the two groups of brief 1704c.\n"),
       ("\t// 1704c: add the fields `Security *SecurityData` and `Phone *PhoneData`\n\t// here (their types live in 1704c's own files).\n",
        "\tSecurity  *SecurityData // security.go (brief 1704c; 1764 adds DeviceKind there)\n\tPhone     *PhoneData    // phone.go (brief 1704c)\n"),
       ("\t// 1704c: add \"security\" and \"phone\" here (loadSecurity, loadPhone).\n",
        "\t\"security\":  loadSecurity,\n\t\"phone\":     loadPhone,\n"),
   ]
   for old, new in edits:
       if s.count(old) != 1:
           raise SystemExit("ANCHOR not found exactly once: " + old[:50])
       s = s.replace(old, new)
   open(p, "w", encoding="utf-8").write(s)
   print("settings.go edited")
   PY
   ```

   The heredoc lines are indented by three spaces in this file because they sit in a list; remove that indent when you paste (Python reads the script from the first column; the `PY` terminator must start in column 1 too). If you rather use the Edit tool, the four `old` and `new` texts are exactly the strings in the script.

   Then check (one call, repo root): `sha256sum -c - <<<'5bbd6f718143cf1ad606ec32eeaed17ce75bad2295cef439983ef4a4cd7e6c02  go/internal/web/settings/settings.go' 2>&1 | tail -2` prints `: OK`; a different hash means a replacement is off by a character: STOP (§8). Commit: `git add go/internal/web/settings/settings.go && git commit -m "1704c step 2" | tail -3`.

3. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/settings cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/settings/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

4. Catalog check (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 5. Else run (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=${PIPESTATUS[0]}"; .venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and a `passed` line with no `skipped`. Nothing changed, so no commit.

5. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else, if `pg_isready -h 127.0.0.1 -p 55706 | tail -1` says `accepting connections`, use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55706/postgres` and skip the start. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg55706 && chown postgres /var/tmp/pg55706 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55706/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55706/data -o "-p 55706 -k /var/tmp/pg55706" -l /var/tmp/pg55706/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. If `/var/tmp/pg55706/data` already exists and is not empty, skip `initdb` and only run `pg_ctl ... start`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 6. Stop the server again after step 6 (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55706/data stop' | tail -2`) if you started it.

6. Run the tests on PostgreSQL (one call, from the repo root):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55706/postgres go test ./internal/web/settings/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two `ok` lines (`.../go/internal/web/settings`, `.../go/cmd/ubyhost-web`). This runs the 14 tests of 1704b again; they must stay green. Then show the new named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55706/postgres go test ./internal/web/settings/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestSettingsSecurity|^TestSettingsPhone|^TestSettingsIndexHasNoSecurityBody$|^TestWebPushOn$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 15 tests and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestSettingsSecuritySignedOut
   --- PASS: TestSettingsSecurity
   --- PASS: TestSettingsSecurityNoHTTPS
   --- PASS: TestSettingsSecurityTwoFactorOn
   --- PASS: TestSettingsSecurityNoPasskeys
   --- PASS: TestSettingsSecurityAdminPreview
   --- PASS: TestSettingsSecurityLanguages
   --- PASS: TestSettingsPhone
   --- PASS: TestSettingsPhoneNoPasskeys
   --- PASS: TestSettingsPhonePushOff
   --- PASS: TestSettingsPhoneOwnerScope
   --- PASS: TestSettingsPhoneLanguages
   --- PASS: TestSettingsIndexHasNoSecurityBody
   --- PASS: TestWebPushOn
   --- PASS: TestSettingsSecurityPhoneRoutesRegistered

   Then the skip count of the settings package: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55706/postgres go test ./internal/web/settings/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

7. UX gate (AGENTS.md rule 10, [workflow](../context/workflow.md#ux-gate)). The pages are dormant: the Python browser tests and the shots tool cannot reach the Go service, so they cannot prove these pages yet. Do what can run now, and write the rest into the report as pending (owner item, as for 1704a and 1704b):
   - Read `docs/design/pages/settings.md` (section Settings) and tick `docs/design/design-system.md` section 5 in the report (the templates keep Python's classes and markup; the diff to Python is `_csrf` only).
   - If `App/.venv/bin/python` exists, run the Python baseline, which draws the same pages from Jinja: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expected: a `passed` line, 0 skipped. Else write "UX baseline: CI only (no App/.venv or no playwright)".
   - **Pending until the paths are switched (1705):** `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` of the Go pages `/settings/security` and `/settings/phone`, opened and described per width ("390: ...; 768: ...; 1280: ..."), with `test_layout_lint_browser.py` green on Go. Nothing to commit here.

8. Write the report (§9), set `Status: review` in this file and in the 1704 index row of 1704c (`docs/tasks/1704-go-settings-menu-pages.md`), and commit "1704c step 8" with only those three paths (`git add docs/tasks/1704c-report.md docs/tasks/1704c-go-settings-security-phone.md docs/tasks/1704-go-settings-menu-pages.md`).

## 5. Do not touch

`App/` (no Python file changes; Python still serves `/settings/security` and `/settings/phone`), `UBYHOST_GO_PATHS`, `docs/ENVIRONMENT.md`, Caddy and compose files, every server file, every other file under `go/`: in particular `settings.tmpl` and the other group templates of 1704b, `data.go`, `settings_test.go`, `register_web_settings.go` and its test, `go/internal/web/auth/` (the passkey, logout-all and two-factor routes the forms post to), `go/internal/pushweb/`, `go/internal/pushsend/`, `go/internal/hostweb/` and its `i18n.json`, `go/internal/web/properties/i18n.json`. Hard rules of AGENTS.md: no secret or personal datum in a file or a log (the seed is made up; the push key printed by a test is a throwaway key made in a throwaway database).

## 6. Commands

Exactly the commands of §4 (steps 3, 4, 6 and 7). Test-map row "Host pages, templates, CSS": `test_host_*.py` and `test_host_geometry.py` (0 skipped) run from CI for the Python side; the Go side has no row yet for settings, the coordinator adds `go test ./internal/web/settings/... ./cmd/ubyhost-web/...` (PostgreSQL) from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] Step 0: every check printed the stated result, including the five 1704b hashes.
- [ ] `sha256sum -c` of step 1 printed `: OK` for all 9 files, and step 2 printed `: OK` for `settings.go`.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 4: `i18n rc=0` and a `passed` line, or "CI only (no App/.venv)" in the report.
- [ ] Step 6: two `ok` lines, the 15 named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1704c step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1704c step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python file changed; nothing was pushed to `main`.
- [ ] UI: dormant pages. **The visual and UX gate (screenshots at 390, 768 and 1280 for `/settings/security` and `/settings/phone`, layout lint on Go) is pending** until the owner switches the paths (1705).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a file count of step 0, step 1 or step 2 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1704c-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left. State for brief 1764: the page-data struct is `SecurityData` in `go/internal/web/settings/security.go`, built in `loadSecurity` (add `DeviceKind string` there), and the passkeys section is the template `settings.passkeys` in `go/internal/web/settings/templates/group_security.tmpl`. State for brief 1705: the routes added are `GET /settings/security` and `GET /settings/phone`; the Go UX-gate pages are those two; the forms post to `/account/logout-all`, `/account/passkeys/{id}/{rename,delete}`, `/account/2fa/{move,disable}` and `/account/push/devices/{id}/delete` (Go twins are registered; keep the Python ones until their paths are switched), and the links go to `/account/2fa/setup`.

## Risk list (for the reviewer)

Read `security.go` and `phone.go` (every query keyed by the signed-in account, `h.Account.ID`, never by a request value; the push reads only run when `h.Workspace.ID == h.Account.ID`, so an admin previewing a host gets no push key and no devices; the key is only built when push is available), `group_security.tmpl` and `group_phone.tmpl` (every post form has `_csrf`; the forms post to the existing routes unchanged; names and device names escaped by html/template in text, attribute and confirm message, no `safe` on a stored value; `safe` is used once, for the install help, on text that comes only from the catalog, escaped with `html` first), and `settings.go` (the four edits only; `loaders` still 404s a group without a loader).

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705 (after 1704a and 1704b).
- **Rollback:** Revert the PR.

## Owner steps

None now: nothing is switched on. Later, after the UX gate of §7 passed on Go (owner item), brief 1705 switches `/settings/security` and `/settings/phone` together with the other `/settings*` paths: add the exact paths to the comma-separated `UBYHOST_GO_PATHS` (see docs/ENVIRONMENT.md), run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`, and open both pages signed in at 390, 768 and 1280 px. Rollback: remove the paths again and repeat the last two commands.
