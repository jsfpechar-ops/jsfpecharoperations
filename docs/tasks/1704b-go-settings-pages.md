# 1704b: Go Settings pages (GET /settings and /settings/{account,data,technical,help})

Status: done (2026-11-17; reviewed, Go tests green; Go UX gate pending at 1705)
Depends on: none (brief 1608 exports, 1609 purge route, 1380/1381 host layout, 1704a are on this branch; verified at ed12cdc) | Base commit: current tip of the working branch | Branch: task/1704b-go-settings-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 14)
Tier: B (Sonnet wrote the exact-diff pass; the orchestrator reads the diff of the risk-listed files). Part of [1704](1704-go-settings-menu-pages.md); 1704c (security, phone) plugs into it.

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1704b step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1704b step'`, never a fixed base commit.

## 1. Objective

Port `_settings_page` (`App/app/routes/admin.py` 5331-5440, template `App/app/templates/settings.html` with the partials `settings_back_header`, `settings_index_row`, `settings_toggle_row`, `settings_value_card`, `settings_pills` and the macros `settings_group`, `settings_heading`) for the index and four of the six groups to a new Go package `go/internal/web/settings`, and register `GET /settings`, `/settings/account`, `/settings/data`, `/settings/technical`, `/settings/help` in ubyhost-web. The routes are dormant: nothing is added to `UBYHOST_GO_PATHS` (brief 1705 switches). `/settings/security` and `/settings/phone` are brief 1704c; the shell leaves them an extension point (section 2). Every form keeps posting to its existing Python route (`/account/email`, `/account/onboarding-emails`, `/account/stay-fee-emails`, `/account/guest-details-mail`, `/settings/purge-expired`, `/settings/privacy/ad-consent`); the Go forms only add the `_csrf` hidden input.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (read-only page); 2 privacy: no new personal-data field, no retention line, no outbound request (the page shows the signed-in account's own e-mail and name, the workspace's own consents, audit rows and console mails, as Python does); 3 fixtures are made up; 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 light mode, every form works without JavaScript (the Go forms carry `<input type="hidden" name="_csrf" value="{{csrf}}">`, the only intended markup addition); 11 Go first: this brief is the Go port, and per the owner decision of 2026-11-17 its tests are Go only with hand-written expected strings (no Python golden script, no `App/` file).

**All code is pre-written, compiled and tested** (in a throwaway copy of this branch, with PostgreSQL 16). Sidecars: `docs/tasks/1704b-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Nothing in an existing file changes: every file is new.

| sha256 | file | action | lines |
|---|---|---|---|
| `f488cd438b912879f33458c685f7b878a00ecf65de19abf7c259affcd7157077` | `go/internal/retention/settings_view.go` | create | 42 |
| `07d47b030534584e5bb3c13568364ef875b66faa00204b3e7d68c2384345b7fc` | `go/internal/mail/console_view.go` | create | 73 |
| `0aa3f1ec3ae383a3de83d742848c240eaaf9a935372aba4584a5587c5cb92fd5` | `go/internal/web/public/operator.go` | create | 16 |
| `4b816f535c1ca7d3b13f47f3e35a4b8c3ee5a6c48003c86abe2cde653741f93a` | `go/internal/web/settings/settings.go` | create | 123 |
| `839721ac025ae4ef1c4ece216a7ca366876ecb4c196fe1ee67b45319727b3144` | `go/internal/web/settings/data.go` | create | 461 |
| `a440bd4716e5f801873e55e784a6cc1e57a753f0f16a40aad3b94a4209e0c278` | `go/internal/web/settings/templates/settings.tmpl` | create | 404 |
| `2165009745723bcc76f66ccb00e5ee16303500753fe8d0642d2e5c2fb6580cb8` | `go/internal/web/settings/templates/group_security.tmpl` | create | 4 |
| `57d45a03e25b3a595895c21f809d39305efd6beb3e96b9d0c5290f8fa0f518b4` | `go/internal/web/settings/templates/group_phone.tmpl` | create | 4 |
| `cfe0c9f4c02828594325c0779882ffb54ca0f4ebf08ec9123cc33f4241761fa1` | `go/internal/web/settings/i18n_keys.txt` | create | 22 |
| `3bbbd1a3191e5b17516ed2cbf532393d93d4c14a894f00aad7c87ea60c0cdfca` | `go/internal/web/settings/i18n.json` | create | 503 |
| `eebc4cdbc0119a7e4b62cd4a29b9ea1a0555750150a4e5b3a205811078a21b0f` | `go/internal/web/settings/settings_test.go` | create | 784 |
| `2efe43f2c479df816e6ee82bc194cc169a8883c4bc272c7fbf02074a573527c0` | `go/cmd/ubyhost-web/register_web_settings.go` | create | 30 |
| `2a18c382eafd91fb15c0e9eaf535db36748f35f85b85dc9d628e60b51e62fa93` | `go/cmd/ubyhost-web/register_web_settings_test.go` | create | 29 |

Full manifest: `docs/tasks/1704b-files/MANIFEST.sha256` (exact-diff backfill 2026-11-20 from commit `b7a8c45dd` / `1704b step 1`, before 1704c template replacements).

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- `settings/settings.go`: `Handler(pool, getenv, now, group)` is `require_login` (`hostweb.Login`, `Cache-Control: no-store, private`), then one loader per group, then `layout.Render` with nav `settings`, body kind `settings`, `V2`, `BodyAlerts` (the page draws the alert stack itself, as `_host_alerts.html` does in settings.html). `group == ""` is the index. A group without a loader answers 404 (so `Handler(..., "security")` is a 404 until 1704c). `Groups` is `SETTINGS_GROUPS` in Python's order (a test pins it). Unlike Python, which builds every value for every group, each loader reads only what its group shows.
- **Extension point for 1704c (the shell stays stable).** `pageData` has one field per group and a marker comment `// 1704c: add the fields Security *SecurityData and Phone *PhoneData here`; the map `loaders` has `// 1704c: add "security" and "phone" here`; `settings.tmpl` calls `{{template "settings.group.security" .}}` and `{{template "settings.group.phone" .}}` in Python's order between account and data, and `templates/group_security.tmpl` and `group_phone.tmpl` are stubs that define those two templates as empty. 1704c therefore (1) overwrites the two stub files with its real `{{define "settings.group.security"}}{{if eq .Group "security"}}{{with .Security}}...{{end}}{{end}}{{end}}` (and `.phone`), (2) adds the two fields at the first marker and the two loaders at the second, in new files of its own (`security.go`, `phone.go`; the `SecurityData` struct for 1764 lives there), (3) adds `register_web_settings_security.go` that mounts `settings.Handler(pool, os.Getenv, time.Now, "security")` for `GET /settings/security` and `"phone"` for `GET /settings/phone`, (4) re-runs `go_host_i18n.py` (`i18n_keys.txt` already lists `settings.*`; it adds `passkeys.*` and any other prefix it needs). The index already links both pages. The shell, the index and the other four groups do not change.
- `settings/data.go`: the four loaders. **Owner scoping:** every workspace query uses `h.Workspace.ID` (`owner_user_id IS NOT DISTINCT FROM $1` for `legal_entity`, `apartment`, `audit`, `data_subject_request`; `a.owner_user_id = $n` for the guest counts; `signup.ConsentsFor(workspace)`); the only reads keyed by the signed-in account are the account's own `user_account` row (name, e-mail, the three switches) and `FROM codelist` / `FROM settings` (global tables, as in Python). The three e-mail switches are shown only to a `host` account looking at its own workspace (no admin preview), the stay-fee one only with a property that has a fee, as `_onboarding_emails`, `_stay_fee_emails`, `_guest_details_mail`. Admin blocks (destination, mail backend line, codelists, users and incidents rows, backup marker, retention counts) key on `h.Account.Role == "admin"` as `current_user.role` does.
- `retention/settings_view.go` (new file, adds only): `HousebookCutoff`, `ExpiredGuestCount`, `DueGuestCount`, the numbers of `housebook.retention_cutoff`, `expired_guest_ids`, `due_guest_ids`, with a mandatory owner (never Python's `? IS NULL OR`, which would read every host). `mail/console_view.go` (new, adds only): `RecentConsole`, `mail.recent_console_messages` for one owner, claim secret put back best effort as `_reveal_claim_secret` does. `public/operator.go` (new, adds only): `OperatorFromEnv`, `operator.details()` on the same environment reading as the legal pages. Existing files of those packages do not change.
- `templates/settings.tmpl`: the Go twin of settings.html. The macros and partials are written out as their markup (the layout has no `{% call %}`). `help_tip`, `tip_label`, `settings_heading`, `icon`, `csrf`, `datetime_local`, `billing_on`, `t`, `tp`, `kv` come from the layout funcs.
- `i18n_keys.txt` / `i18n.json`: the page catalog, written by `App/scripts/go_host_i18n.py` (`settings.*` plus the `legal.*`, `nav.*`, `common.*` keys the page reads).
- `register_web_settings.go`: an `init()` that adds the five `GET` patterns through `registerRoutes`; the existing `GET /settings/archived`, `POST /settings/purge-expired` and `POST /settings/privacy/ad-consent` keep theirs (the test checks it).
- Tests (all Go, hand-written expected strings from the seed in `settings_test.go`, 14 tests): signed-out redirect for all five paths; index order and that no group body shows; account (Hana Host, one business opens its editor, host 3 with two businesses gets the list and falls back to the user name and "No login e-mail", the admin rows, the admin preview shows no switches, billing row only with billing on, 4 forms with 4 `_csrf`); data (host 2 and host 3 get their own counts, the last-run line, due, open requests, privacy banner, consents in Google-then-Meta order, 2 forms with 2 `_csrf`, admin counts and backup marker); the empty data page; technical (own audit rows only, newest first, `?audit=support`, NULL detail prints `None`, PIN line, empty log); technical as admin (destination for `test`, `prod`, `mock`, SES, an unknown backend, code lists, preview of a host workspace); console mail (claim secret put back, other host's mail never shown, no key keeps the marker, the block hides for a host without messages or on another backend); help; cs and vi; 404 for an unknown group; a test that `appVersion` equals `App/app/__init__.py`.

**Accepted differences (only reachable with hand-made data or settings):**

- html/template writes `+` in the stored time as `&#43;` and `'` as `&#39;`; the browser shows the same text.
- The last-run line, the guest PIN line and the PIN env are read as Python reads them; the data directory is `UBYHOST_DATA_DIR` with no Python default (`App/data`), so without it no backup row shows (production always sets it).
- "Today" for the retention numbers is the Prague date (as the purge button and the job use), Python's `date.today()` is the server date; they differ only in the hours around midnight and only the cutoff day (31 January) can move a number.
- An unknown `UBYHOST_UBYPORT_ENV` is a 500 on the technical page for an admin only (Python 500s every settings page).
- The console mail list is read only when the backend is `console` (Python reads it for every group and shows it only then).
- `HEAD` is served by the `GET` pattern.
- `retention_last_run` is one global setting row, so a host sees the time and dry/live state of the last run of any host (Python does the same; the counts are admin only). Goes to known-issues in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/retention/settings_view.go` | create | `HousebookCutoff`, `ExpiredGuestCount`, `DueGuestCount` |
| `go/internal/mail/console_view.go` | create | `RecentConsole` |
| `go/internal/web/public/operator.go` | create | `OperatorFromEnv` |
| `go/internal/web/settings/settings.go` | create | handler, page data, loader map, 1704c markers |
| `go/internal/web/settings/data.go` | create | the four group loaders |
| `go/internal/web/settings/templates/settings.tmpl` | create | shell, index, four groups |
| `go/internal/web/settings/templates/group_security.tmpl` | create | empty stub, 1704c overwrites |
| `go/internal/web/settings/templates/group_phone.tmpl` | create | empty stub, 1704c overwrites |
| `go/internal/web/settings/i18n_keys.txt` | create | page catalog keys |
| `go/internal/web/settings/i18n.json` | create | page catalog (generated, checked in step 3) |
| `go/internal/web/settings/settings_test.go` | create | Go tests with a seed and hand-written expectations |
| `go/cmd/ubyhost-web/register_web_settings.go` | create | registers the five `GET` routes |
| `go/cmd/ubyhost-web/register_web_settings_test.go` | create | route registration test |
| `docs/tasks/1704b-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1704b-report.md` | create | the report (§9) |

No other file may change (step 7 also edits the Status line of this brief and of the 1704 index row).

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF 'SETTINGS_GROUPS = ("account", "security", "phone", "data", "technical", "help")' App/app/routes/admin.py | tail -1` prints `1`.
   - `grep -cF '__version__ = "1.1.0"' App/app/__init__.py | tail -1` prints `1` (a test reads this line).
   - `grep -cF 'func housebookCutoff(today time.Time) time.Time {' go/internal/retention/retention.go | tail -1` prints `1`.
   - `grep -cF 'func isoDate(t time.Time) string { return t.Format("2006-01-02") }' go/internal/retention/retention.go | tail -1` prints `1`.
   - `grep -cF 'func (c Config) decrypt(token string) (string, error) {' go/internal/mail/outbox_markers.go | tail -1` prints `1`.
   - `grep -cF 'claimSecretKey    = "claim_secret_enc"' go/internal/mail/outbox_markers.go | tail -1` prints `1`.
   - `grep -cF 'func loadConfig(getenv func(string) string) config {' go/internal/web/public/public.go | tail -1` prints `1`.
   - `grep -cF 'func ConsentsFor(ctx context.Context, pool *pgxpool.Pool, userID int64) ([]Consent, error) {' go/internal/signup/register.go | tail -1` prints `1`.
   - `grep -cF 'func EndpointFor(getenv func(string) string) (string, error) {' go/internal/ubyport/sweep.go | tail -1` prints `1`.
   - `grep -cF 'func LoadDataKeys(getenv func(string) string) (*MultiFernet, error) {' go/internal/secure/datakeys.go | tail -1` prints `1`.
   - `grep -cF 'func MustParseFuncs(cat hostweb.Catalog, funcs template.FuncMap, fsys fs.FS, patterns ...string) *Templates {' go/internal/hostweb/layout/pagefuncs.go | tail -1` prints `1`.
   - `grep -cF 'BodyAlerts bool' go/internal/hostweb/layout/layout.go | tail -1` prints `1`.
   - `grep -cF '"settings_heading":      c.settingsHeading,' go/internal/hostweb/layout/funcs.go | tail -1` prints `1`.
   - `grep -cF 'func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {' go/cmd/ubyhost-web/registry.go | tail -1` prints `1`.
   - `grep -rcF '"GET /settings"' go/cmd/ubyhost-web | grep -v ':0$' | tail -3` prints nothing (the page routes are not registered yet).
   - `ls go/internal/web/settings go/internal/retention/settings_view.go go/internal/mail/console_view.go go/internal/web/public/operator.go 2>&1 | tail -4` says "No such file" four times (nothing of this brief exists yet).
   - `find docs/tasks/1704b-files -name '*.txt' | wc -l | tail -1` prints `13`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1704b-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF2' 2>&1 | tail -15
   f488cd438b912879f33458c685f7b878a00ecf65de19abf7c259affcd7157077  go/internal/retention/settings_view.go
   07d47b030534584e5bb3c13568364ef875b66faa00204b3e7d68c2384345b7fc  go/internal/mail/console_view.go
   0aa3f1ec3ae383a3de83d742848c240eaaf9a935372aba4584a5587c5cb92fd5  go/internal/web/public/operator.go
   4b816f535c1ca7d3b13f47f3e35a4b8c3ee5a6c48003c86abe2cde653741f93a  go/internal/web/settings/settings.go
   839721ac025ae4ef1c4ece216a7ca366876ecb4c196fe1ee67b45319727b3144  go/internal/web/settings/data.go
   a440bd4716e5f801873e55e784a6cc1e57a753f0f16a40aad3b94a4209e0c278  go/internal/web/settings/templates/settings.tmpl
   2165009745723bcc76f66ccb00e5ee16303500753fe8d0642d2e5c2fb6580cb8  go/internal/web/settings/templates/group_security.tmpl
   57d45a03e25b3a595895c21f809d39305efd6beb3e96b9d0c5290f8fa0f518b4  go/internal/web/settings/templates/group_phone.tmpl
   cfe0c9f4c02828594325c0779882ffb54ca0f4ebf08ec9123cc33f4241761fa1  go/internal/web/settings/i18n_keys.txt
   3bbbd1a3191e5b17516ed2cbf532393d93d4c14a894f00aad7c87ea60c0cdfca  go/internal/web/settings/i18n.json
   eebc4cdbc0119a7e4b62cd4a29b9ea1a0555750150a4e5b3a205811078a21b0f  go/internal/web/settings/settings_test.go
   2efe43f2c479df816e6ee82bc194cc169a8883c4bc272c7fbf02074a573527c0  go/cmd/ubyhost-web/register_web_settings.go
   2a18c382eafd91fb15c0e9eaf535db36748f35f85b85dc9d628e60b51e62fa93  go/cmd/ubyhost-web/register_web_settings_test.go
   EOF2
   ```

   Every line must end with `: OK` (13 lines). Then commit "1704b step 1" with only these paths: `git add go/internal/retention/settings_view.go go/internal/mail/console_view.go go/internal/web/public/operator.go go/internal/web/settings go/cmd/ubyhost-web/register_web_settings.go go/cmd/ubyhost-web/register_web_settings_test.go && git commit -m "1704b step 1" | tail -3`.

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/retention internal/mail internal/web/public internal/web/settings cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/retention/... ./internal/mail/... ./internal/web/public/... ./internal/web/settings/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. Catalog check (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else run (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=${PIPESTATUS[0]}"; .venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and a `passed` line with no `skipped`. Nothing changed, so no commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55704/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55704 && chown postgres /var/tmp/pg55704 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55704/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55704/data -o "-p 55704 -k /var/tmp/pg55704" -l /var/tmp/pg55704/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55704/postgres` in step 5. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Run the tests on PostgreSQL (one call, from the repo root):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55704/postgres go test ./internal/web/settings/... ./internal/retention/... ./internal/mail/... ./internal/web/public/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: five `ok` lines (`.../go/internal/web/settings`, `.../go/internal/retention`, `.../go/internal/mail`, `.../go/internal/web/public`, `.../go/cmd/ubyhost-web`). Then show the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55704/postgres go test ./internal/web/settings/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestGroupsOrderAndVersion$|^TestParseLastRunKeepsOrder$|^TestSettings|^TestSettingsPageRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 14 tests and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestGroupsOrderAndVersion
   --- PASS: TestParseLastRunKeepsOrder
   --- PASS: TestSettingsSignedOut
   --- PASS: TestSettingsUnknownGroup
   --- PASS: TestSettingsIndex
   --- PASS: TestSettingsAccount
   --- PASS: TestSettingsData
   --- PASS: TestSettingsDataNothingToPurge
   --- PASS: TestSettingsTechnical
   --- PASS: TestSettingsTechnicalAdmin
   --- PASS: TestSettingsTechnicalConsoleMail
   --- PASS: TestSettingsHelp
   --- PASS: TestSettingsLanguages
   --- PASS: TestSettingsPageRoutesRegistered

   Then the skip count of the settings package: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55704/postgres go test ./internal/web/settings/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

6. UX gate (AGENTS.md rule 10, [workflow](../context/workflow.md#ux-gate)). The pages are dormant: the Python browser tests and the shots tool cannot reach the Go service, so they cannot prove these pages yet. Do what can run now, and write the rest into the report as pending (owner item, as for 1704a):
   - Read `docs/design/pages/settings.md` and tick `docs/design/design-system.md` section 5 in the report (the template keeps Python's classes and markup; the diff to Python is `_csrf` only, plus the escapes named under accepted differences).
   - If `App/.venv/bin/python` exists, run the Python baseline, which draws the same pages from Jinja: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expected: a `passed` line, 0 skipped. Else write "UX baseline: CI only (no App/.venv or no playwright)".
   - **Pending until the paths are switched (1705):** `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` of the Go pages `/settings`, `/settings/account`, `/settings/data`, `/settings/technical`, `/settings/help`, opened and described per width ("390: ...; 768: ...; 1280: ..."), with `test_layout_lint_browser.py` green on Go. Nothing to commit here.

7. Write the report (§9), set `Status: review` in this file and in the 1704 index row of 1704b (`docs/tasks/1704-go-settings-menu-pages.md`), and commit "1704b step 7" with only those three paths.

## 5. Do not touch

`App/` (no Python file changes; Python still serves `/settings*`), `UBYHOST_GO_PATHS`, `docs/ENVIRONMENT.md`, Caddy and compose files, every server file, every other file under `go/`: in particular the existing files of `go/internal/retention/`, `go/internal/mail/` and `go/internal/web/public/` (the three new files only add), `go/internal/hostweb/` and its `i18n.json`, `go/internal/web/properties/i18n.json`, the exports, purge, ad-consent and account routes the forms post to. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the seed is made up; the claim secret in the test is a made-up string).

## 6. Commands

Exactly the commands of §4 (steps 2, 3, 5 and 6). Test-map row "Host pages, templates, CSS": `test_host_*.py` and `test_host_geometry.py` (0 skipped) run from CI for the Python side; the Go side has no row yet, the coordinator adds `go test ./internal/web/settings/... ./internal/retention/... ./internal/mail/...` (PostgreSQL) from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 13 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 3: `i18n rc=0` and a `passed` line, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: five `ok` lines, the 14 named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1704b step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1704b step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python file changed; nothing was pushed to `main`.
- [ ] UI: dormant pages. **The visual and UX gate (screenshots at 390, 768 and 1280 for the five pages, layout lint on Go) is pending** until the owner switches the paths (1705).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a file count of step 0 or step 1 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1704b-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left, and for known-issues: "Settings > Data shows the time and dry/live state of the last retention run of any host (`retention_last_run` is one global setting row; Python the same; the counts are admin only)", and "`appVersion` in `go/internal/web/settings/data.go` mirrors `App/app/__init__.py`; the Go test breaks when Python's version is bumped alone".

## Risk list (for the reviewer)

Read `data.go` (every workspace query keyed by `h.Workspace.ID`, the guest counts never take a nil owner, the account row keyed by the signed-in account only, the three e-mail switches shown only for a host in its own workspace, admin blocks keyed on the account role, the audit `LIMIT 500` and the support filter built from constants, no value from the request in SQL except the owner), `settings.tmpl` (every post form has `_csrf`; the forms post to the Python routes unchanged; values escaped by html/template; no `safe`; the console mail `srcdoc` is an escaped string), `console_view.go` (owner-scoped join on `email_outbox`; a key or payload that cannot be read leaves the marker, never fails the page) and `settings_view.go` (`a.owner_user_id = $3`).

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705 (after 1704c).
- **Rollback:** Revert the PR.

## Owner steps

None now: nothing is switched on. Later, after 1704c and the UX gate of §7 passed on Go (owner item), brief 1705 switches `/settings`, `/settings/account`, `/settings/data`, `/settings/technical`, `/settings/help` (and the two of 1704c) together: add the exact paths to the comma-separated `UBYHOST_GO_PATHS` (see docs/ENVIRONMENT.md), run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`, and open each page signed in at 390, 768 and 1280 px. Rollback: remove the paths again and repeat the last two commands.
