# 1520: Go port of the alert dismiss, the smart-locks redirect and the phone menu

Status: review
Depends on: none | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** The owner wants one big pull request. You work on the current branch: commit `1520 step k` after each step that changes a file, never create a branch, never push, never open a PR. The orchestrator merges. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1520 step'` and `git show --stat` on those commits.

## 1. Objective

Port three routes of `App/app/routes/admin.py` to Go in `go/internal/web/properties/`: `POST /alerts/{id}/dismiss`, `GET /smart-locks` (the redirect only) and `GET /menu`. Same ownership check, status codes, redirects and rows as Python, proven by Go tests that name the Python lines they mirror.

## 2. Context

The files are written and were run green by the brief writer (sidecar `docs/tasks/1520-files/`). You do not write code: copy, check, test. **Do not open the sidecar files**; the reviewer reads them.

Python ported (read-only, for the reviewer), with the parity each Go test checks:

| Route | Python | Parity |
|---|---|---|
| `POST /alerts/{id}/dismiss` | `dismiss_alert` admin.py 5216-5254, `_redirect_path_from_referer` 357-372, `access.alert` access.py 136, `alerts.resolve_by_id` alerts.py 542, `reporting.apartment_in_doubt` reporting.py 1758 (Go: `ubyport.ApartmentInDoubt`) | another host's alert is 404 `No such alert.` (no Content-Type); `dates_changed_resign` is locked (303 with flash `flash.error.resign_card_locked`, or 409 for `X-Requested-With: fetch`); `submission_outcome_unknown` is locked while a guest points at an unknown batch; dismissing `guest_pin_rotated` also clears the host's other pin cards; fetch gets 204, others 303 to the Referer path when the Referer host equals the Host header, else `/`; row: `resolved_at`, `user_dismissed = 1` |
| `GET /smart-locks` | `smart_locks_page` 712-727, `_lock_tab_url` 185-193, `_lock_property_return` 210-220, `ttlock.enabled` ttlock.py 228, `ttlock.account_for` 250 | off unless `UBYHOST_DOOR_CODES` is exactly `1`, `true` or `yes` and both TTLock app keys are set (else 303 to `/apartments` with the error flash); `return_to` naming the host's own property goes to its lock section, else to the first active property's Door lock tab (`#smart-locks-list` with a lock account, else `#smart-locks-how`), else `/apartments` |
| `GET /menu` | `menu_view` 5257-5284, `reporting.month_summary` reporting.py 1017-1049, `templates/menu.html` | tiles count only this host's live (not archived), non-demo stays overlapping the Prague calendar month; the admin row shows for an admin (also inside a workspace) |

**Known deviation D1 (decision for the reviewer).** `menu_view` also calls `cleaning.schedule(owner, today, today)` for a badge. That range is empty, so the badge count is always 0 and the badge never shows; the call's only effect is `cleaning.reconcile(owner)`, which writes cleaning events. Go does not call it (`go/internal/web/cleaning` keeps `reconcile` private); the next cleaning page view does the same work. If the reviewer wants strict parity, the menu route stays blocked until `reconcile` is exported.

**Paths.** The exact paths `/menu`, `/smart-locks` (GET only in Python) and the one dismiss route under `/alerts/` become fully served by Go. `/smart-locks/setup`, `/smart-locks/refresh` and `/smart-locks/remove` are other paths; they stay on Python (brief 1526, blocked), so do not switch a `/smart-locks/*` prefix.

**Live on deploy.** The routes are registered the moment this deploys. Assumption: `UBYHOST_GO_PATHS` does not name `/menu`, `/smart-locks` or `/alerts/*` today (the server value cannot be read). If any is named, the route is live at once.

Rules that apply: AGENTS.md hard rules 2 (no new outbound request, no new personal-data field: none here), 5 (SQL is Postgres, no schema change), 6, 8. CSRF, path id and login run in the order FastAPI runs them (as `properties.go enter`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/misc.go` | create | the three handlers, `RegisterMisc`, `refererPath`, `doorCodesEnabled` |
| `go/internal/web/properties/templates/menu.tmpl` | create | port of `menu.html` |
| `go/internal/web/properties/misc_test.go` | create | tests with the Python line each case mirrors |
| `go/internal/web/properties/more_helpers_test.go` | create | test helpers reused by briefs 1521-1524 |
| `go/cmd/ubyhost-web/register_web_properties_misc.go` | create | `init()` calling `registerRoutes` |
| `go/internal/web/properties/i18n_keys.txt` | edit (append) | the keys this brief reads |
| `go/internal/web/properties/i18n.json` | edit (generated) | catalog regenerated from the keys file |
| `docs/tasks/1520-go-properties-misc.md` | edit | `Status:` line only |
| `docs/tasks/1520-report.md` | create | report |

No other file may change. **What changes for live traffic:** `i18n_keys.txt` and `i18n.json` only gain keys; `templates/menu.tmpl` joins the template set the live package parses at start (a parse error would stop the service, the tests parse it); no live handler changes.

## 4. Steps

1. Copy the five new files:

```bash
mkdir -p go/internal/web/properties && cp docs/tasks/1520-files/go/internal/web/properties/misc.go.txt go/internal/web/properties/misc.go
mkdir -p go/internal/web/properties/templates && cp docs/tasks/1520-files/go/internal/web/properties/templates/menu.tmpl.txt go/internal/web/properties/templates/menu.tmpl
mkdir -p go/internal/web/properties && cp docs/tasks/1520-files/go/internal/web/properties/misc_test.go.txt go/internal/web/properties/misc_test.go
mkdir -p go/internal/web/properties && cp docs/tasks/1520-files/go/internal/web/properties/more_helpers_test.go.txt go/internal/web/properties/more_helpers_test.go
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1520-files/go/cmd/ubyhost-web/register_web_properties_misc.go.txt go/cmd/ubyhost-web/register_web_properties_misc.go
```

2. Check them:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -12
35fb6837d7f195b9acdaf48c26c7130ae228fb77a861d49bc7e8680bfc102eb2  go/internal/web/properties/misc.go
b7ebc7539605331477cb1ea7a81e25743f33206b7719951953bb118cc8e7d1c3  go/internal/web/properties/templates/menu.tmpl
2cb505534bcdea0231e136e1fdf5513c7aee5cb569da0d47e7b98d0c548b8e7d  go/internal/web/properties/misc_test.go
19f2c51f66df015ef4688e580ea46b48d97d4117f02fd257e2d39223ba8b17d4  go/internal/web/properties/more_helpers_test.go
e18416986e2107465a7be185542fb359fe675849be7532d1706486f29ef5f579  go/cmd/ubyhost-web/register_web_properties_misc.go
SUMS
```

Expected: 5 lines ending `OK`.

3. Append the keys and regenerate the catalog (run from the repo root):

```bash
printf '\n' >> go/internal/web/properties/i18n_keys.txt
cat docs/tasks/1520-files/i18n_keys_append.txt >> go/internal/web/properties/i18n_keys.txt
cd App && .venv/bin/python -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
import go_host_i18n as g
d = Path('../go/internal/web/properties')
(d / 'i18n.json').write_text(g.render(g.read_keys(d / 'i18n_keys.txt')), encoding='utf-8')
" && cd .. && sha256sum go/internal/web/properties/i18n.json
```

Expected: `84b1e603ad739d46f929ac31615deab87b6f1a282b2f4943478d84d7212728b9  go/internal/web/properties/i18n.json`. A different sum: stop (§8). Then commit: `git add go && git commit -q -m "1520 step 3: files and catalog" && git show --stat HEAD | tail -12`.

4. Run the checks of §6, write the report, set `Status: review`, commit: `git add docs/tasks && git commit -q -m "1520 step 4: report"`.

## 5. Do not touch

- Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/cmd/ubyhost-web/registry.go`, `go/cmd/ubyhost-web/register_web.go`, `App/tests/conftest.py`, every file under `App/app/`, `App/scripts/`.
- `docs/ENVIRONMENT.md`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`.
- Nothing is added to `UBYHOST_GO_PATHS` anywhere (deploy files, env docs, tests). Do not edit the sidecar files, `go.mod` or `go.sum`; no `go get`, no `go mod tidy`.
- Hard rules 2, 3, 4, 5, 8 of AGENTS.md. Never push to `main`; never merge; no branch, no PR.

## 6. Commands

From the repo root. The Go tests need PostgreSQL: `export UBYHOST_TEST_DATABASE_URL=postgresql://...` as the owner's environment gives (unset means the database tests skip, which is a stop (§8), not a pass).

```bash
cd go && test -z "$(gofmt -l .)" && go build ./... && go vet ./internal/web/properties/... ./cmd/... 2>&1 | tail -5 && go test -count=1 -v ./internal/web/properties/ ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
```

Expected: no `SKIP`; `--- PASS` for `TestRefererPath`, `TestDoorCodesEnabled`, `TestPragueDay`, `TestMiscRegisterDoesNotTouchThePool`, `TestDismissAlert`, `TestDismissAlertInDoubt`, `TestSmartLocksRedirect`, `TestMenuPage`, and every older properties test; two `ok` lines.

```bash
python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -3
git log --oneline --grep='^1520 step' | tail -10
```

Expected: `context lint: OK`; one commit per step that changed a file.

## 7. Acceptance

- [ ] Step 2: 5 `OK`; step 3: the i18n sha256 given there.
- [ ] `gofmt -l .` empty, `go vet` clean, `go build ./...` OK.
- [ ] The tests named in §6 ran (not skipped) and passed, `./cmd/ubyhost-web` passes.
- [ ] `git log --oneline --grep='^1520 step'` lists the step commits; `git show --stat` of them touches only §3 paths.
- [ ] Screenshots (rule 7, UI): `/menu` is a new page; the executor cannot start the Go service here, so the reviewer takes the 390 px screenshot after the owner's staging deploy (owner step 2).

## 8. Stop and ask

Stop, and write the report, if: a sidecar `sha256sum` or `git apply --check` fails; an anchor is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1520-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git show --stat` of the `1520 step` commits), each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/properties/misc.go`: `dismissAlert` (the ownership query `alertOwnedSQL` must keep `owner_user_id IS NOT DISTINCT FROM`; both locked branches; the sibling-card update only touches `kind = 'guest_pin_rotated'`), `refererPath` (open-redirect guard: the Referer host must equal the Host header), `smartLocks`, `menu` (D1).
- No outbound request, nothing deletes. The alert update is the only write.

## Owner steps

1. Nothing to deploy yet: the paths are not switched.
2. When staging is up with `/menu` in `UBYHOST_GO_PATHS`, open `/menu` on a phone-sized window and check the tiles, the rows and the logout button against Python.
