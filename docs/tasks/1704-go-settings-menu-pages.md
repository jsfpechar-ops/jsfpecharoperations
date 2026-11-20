# 1704: Go property settings 5: settings, menu, guest links, guide and housebook pages

Status: review — index of 1704a/b/c (re-scoped 2026-11-17). Exact-diff sidecars for 1704a/b/c landed 2026-11-20 (`docs/tasks/1704{a,b,c}-files/`); wave P switch remains brief 1705.
Depends on: 1380/1381 host layout (done) | Base commit: current tip of the working branch | Branch: task/1704-go-settings-menu-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1704 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1704 step'`.

## 1. Objective

Port the two read-page areas Go does not have yet: `GET /housebook` and `GET /settings` with the six `GET /settings/<group>` pages (account, security, phone, data, technical, help). This brief is the **index and scope** of three runnable briefs (below). It is not run itself.

## 2. Context

**Re-scope 2026-11-17 (Sonnet).** Checked against the tree: `POST /alerts/{id}/dismiss`, `GET /menu`, `GET /guest-links` and `GET /guide` are already in Go (briefs 1301 and 1520: `go/internal/web/properties/misc.go`, `pages.go`). They leave this brief. `GET /housebook` and every `/settings*` page have no Go handler (`grep -rn '"GET /housebook\|"GET /settings' go` is empty); the CSV and ZIP exports (`go/internal/web/exports/housebook*.go`) are already ported and stay unchanged.

**Tests (owner 2026-11-17, [go-first](../context/go-first.md)):** Go only, with hand-written expected output (a fixed seed in the Go test, assertions on exact strings and ids). No Python golden script, no `App/` file, no `testdata/*_golden.json` from Python. The old plan with `App/scripts/go_settings_menu_golden.py` is void.

**Where the code goes:** `go/internal/web/hostweb` does not exist (`go/internal/hostweb` is the gate and layout). Put each page in its own new package next to its siblings: `go/internal/web/housebook/` (1704a) and `go/internal/web/settings/` (1704b, 1704c), the pattern of `go/internal/web/onboarding/` (handler through `hostweb.Login`, `layout.Render`, embedded `*.tmpl`, catalog from `i18n_keys.txt` written by `App/scripts/go_host_i18n.py`; this script is go-first exception 1 plumbing, no new Python file). Reuse, never copy: `hostweb.Login`, `hostweb.Back`, `session.Host.Workspace.ID` as the owner on every query (`owner_user_id IS NOT DISTINCT FROM $n`), the existing `exports` housebook SQL for rows, `safeLocalPath`, the `_csrf` hidden input (`{{csrf}}`) in every Go form so it works without JavaScript (rule 6).

**Python source of truth:** `App/app/routes/admin.py` 5228-5260 (housebook_view), 5304-5440 (`_settings_page`, `_settings_group_view`), `App/app/housebook.py` 36-210 (`period_presets`, `HOUSEBOOK_COLUMNS`, `housebook_rows`, `housebook_archived_rows`), `App/app/templates/housebook.html` (216 lines), `settings.html` (514 lines; groups: account 40, security 105, phone 197, data 249 and privacy 303, technical 357, help 478).

### The split (each fits one Haiku session; each gets its own exact-diff pass and sidecars before it runs)

| Brief | Scope | Depends on |
|---|---|---|
| 1704a | `GET /housebook` (filters apartment/from/to, rows, archived rows, period presets; links to the existing CSV and ZIP routes). **Exact-diff brief written: [1704a-go-housebook-page.md](1704a-go-housebook-page.md), Status: done (Go UX gate pending until the switch)** | none |
| 1704b | `GET /settings` and `/settings/{account,data,technical,help}`: the `settings_group` shell, tab strip, account, data and privacy, technical (destination, mail, codelists, UbyPort, audit with `?audit=support`), help (guide, legal, version); `SETTINGS_GROUPS` order as in Python. **Exact-diff brief written: [1704b-go-settings-pages.md](1704b-go-settings-pages.md), Status: review** | none; the shell is stable for 1704c (its extension point is described in the 1704b brief §2) |
| 1704c | `/settings/security` and `/settings/phone`: logout-all row, passkeys list (read only; add and remove stay on the 1760 routes), 2FA state, PWA install row, push devices (read only). **Exact-diff brief written: [1704c-go-settings-security-phone.md](1704c-go-settings-security-phone.md), Status: review** | 1704b (done) |

Order: 1704a and 1704b are independent; 1704c after 1704b. 1705 (switch) waits for all three.

### What 1764 needs (blocked on 1704c) and must stay stable

The passkey section in 1704c keeps the Python ids and keys exactly: `#settings-passkeys` inside `#settings-security`, the existing `passkeys.*` catalog keys, one page-data struct (`SecurityData`) built in one handler function so 1764 can add `DeviceKind string` there. 1764 edits the template section, not the handler routes. 1704c must not rename these; its report names the struct and file for 1764.

### Overlaps with other open briefs

`go/cmd/ubyhost-web/register_web_*.go` files are new per brief (no shared file). 1705 names all `/settings*` and `/housebook` paths in its collision test. 1764 edits the 1704c security template. The i18n catalogs are per new package (do not edit `go/internal/hostweb/i18n.json` or `properties/i18n.json`).

## 3. Files (index; each sub-brief lists its own)

| Path | Action | What |
|---|---|---|
| `docs/tasks/1704a-*.md`, `1704b-*.md`, `1704c-*.md` | create (exact-diff pass) | the runnable briefs, sidecars in `docs/tasks/1704{a,b,c}-files/` |

## 4. Steps (template for 1704a/b/c; each sub-brief writes them out as exact diffs)

0. Checks (repo root): `grep -cF` anchor lines for every file edited, `ls` proving the new files do not exist.
1. Copy the sidecars to their repo paths, `sha256sum -c` all OK, commit `1704x step 1`.
2. `gofmt -l`, `go build ./...`, `go vet` on the touched packages: silent.
3. Go tests with hand-written expected output (owner scoping: a second workspace's rows never appear; signed-out redirect to `/login?next=`; `_csrf` in every form; cs, en, vi titles). Database tests need `UBYHOST_TEST_DATABASE_URL` and are not skipped.
4. Register the routes in one new `go/cmd/ubyhost-web/register_web_*.go` (`registerRoutes`); dormant, nothing is added to `UBYHOST_GO_PATHS`.
5. UX gate (rule 10, [workflow](../context/workflow.md#ux-gate)): from `App/` with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots`, `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`, 0 skipped; open `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` per touched page; write "390: ...; 768: ...; 1280: ..." per page in the report; tick the [design-system checklist](../design/design-system.md). Read the page add-on in `docs/design/pages/` first.
6. Report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `go/internal/hostweb/i18n.json`, `properties/i18n.json` (new packages carry their own catalogs); `App/` (no Python golden, no `App/app/` change); the Go exports, passkey, push and 1760 routes (read only here); filing code.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go build ./... 2>&1 | tail -30` and `go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` are silent
- `cd go && go test ./internal/web/<package>/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, none skipped
- Test-map row "Host pages, templates, CSS": `test_host_*.py` and `test_host_geometry.py` (0 skipped) plus the UX gate above
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- Each route answers on Go in a test with the expected status, headers and body strings; a signed-out request redirects as Python does.
- Screenshots at 390/768/1280 per page, described in the report.
- `git log --oneline --grep='^1704'` shows one commit per step; `git diff --stat` lists only the sub-brief's section 3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1704-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705.
- **Rollback:** Revert the PR.

## Owner steps

None.
