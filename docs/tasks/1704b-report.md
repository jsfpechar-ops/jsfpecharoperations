# 1704b report

Status: review  
Branch: `cursor/1704b-go-settings-pages-dff7`  
Go implementation on `main` (#1081 `cc0c7c4ff`); this branch adds executor step 7 docs only.

## 1. Files changed (§3)

On `main` already: `go/internal/retention/settings_view.go`, `go/internal/mail/console_view.go`, `go/internal/web/public/operator.go`, `go/internal/web/settings/**` (shell + four groups), `go/cmd/ubyhost-web/register_web_settings*.go`, sidecars under `docs/tasks/1704b-files/`. Step 7: `docs/tasks/1704b-report.md`, `docs/tasks/1704b-go-settings-pages.md`, `docs/tasks/1704-go-settings-menu-pages.md`.

## 2. Commands (last lines)

- Step 2 gofmt/build/vet: no output.
- Step 3 `go_host_i18n.py --check`: `i18n rc=0`; `2 passed`.
- Step 4 PostgreSQL 16: **CI only** (no `postgres` user / binaries in this environment).
- Step 5 Go tests: **not run here** (§8 STOP before step 5 without PG); prior report had 5× `ok`, 14 PASS, SKIP 0 on port 55704.
- Step 6 Jinja baseline: `4 passed in 231.22s`. Go screenshots / layout lint on Go paths: **pending** until 1705.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## 3. Acceptance (§7)

- [x] Sidecars in repo; sha256 on main matches 8/13 1704b-only files (5 differ after 1704c on `settings.go`, stub templates, i18n — expected on integrated `main`).
- [x] format, build, vet silent
- [x] Step 3 i18n rc=0 and pytest passed
- [ ] Step 5 in this env: CI only (PostgreSQL)
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env, or Python route change on this branch
- [ ] UI gate on Go: pending until 1705 (Jinja baseline green)

## 4. Deviations

- Step 0 failed as written (files and routes already exist on `main`); step 1 not re-run (would revert 1704c).
- design-system §5: template parity / `_csrf` only; visual checklist items for Go service not ticked (dormant routes).

## 5. Questions

None.

## 6. Owner steps left

- Go UX gate at 390/768/1280 after 1705 path switch.
- known-issues: retention last-run global row (same as Python); `appVersion` tied to `App/app/__init__.py`.