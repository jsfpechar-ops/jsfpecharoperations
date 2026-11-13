# 1301: Go port of property settings read-only pages

Status: review
Depends on: 1300 (PR #980), 1380 (PR #985) | Base commit: c540113 | Branch: task/1301-go-property-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Port two read-only host GET routes of `App/app/routes/admin.py` to Go in `go/internal/web/properties/`: `GET /guide` (the help page, rendered in the Go host layout of brief 1380) and `GET /guest-links` (a 303 redirect). Same status, `Location`, `<title>` and page content (every tag, attribute and text run inside `div.ui-page`) as Python, proven by a golden file the Python test writes and the Go test replays on Postgres; the routes stay switched off (nothing is added to `UBYHOST_GO_PATHS`).

## 2. Context

Every file was written and run green in a dry run by the brief writer; the finished files were a flat bundle, removed by brief 1410 (they live at the §3 paths on main). You do not write code: step 1 copies them, step 2 checks their sha256, steps 3-4 generate the two derived files, the rest are checks. **Do not open the bundle files**; the reviewer reads them.

Python sources ported (read-only, for the reviewer):

- `App/app/routes/admin.py` `guide_view` (~645): `demo_available = config.UBYPORT_ENV == "mock"`, `havel_on = ai.enabled_for(havel.FEATURE, current_user email)`; `guest_links` and `_property_hub_redirect` (~657-680).
- `App/app/templates/guide.html` (ported to `templates/guide.tmpl`; the `workflow_strip(none, heading=false)` macro of `_workflow.html` and `workflow.steps(None)` are inlined); `App/app/ai.py` `enabled`, `on_test_list`; `App/app/access.py` `apartments` (owner match `IS NOT DISTINCT FROM`, `archived_at IS NULL`, `ORDER BY internal_name`).

Left out on purpose (say so in the report, do not port): `GET /menu` needs `cleaning.schedule` and `reporting.month_summary` (cleaning and filing data, not this area); `GET /housebook` reads guest rows (`housebook.housebook_rows`, guest data, Tier A). Each gets its own brief.

Go code reused (read-only): `hostweb.Login`, `hostweb.Lang`, `layout.MustParse`, `layout.Render`, `layout.Page`, `layout.Env` (go/internal/hostweb/layout, brief 1380); from brief 1300's package: `catalog`, `server`, `Wrap`, `fail`, and in the test `testPool`, `seedWorld`, `readJSON`, `testEnv`, `testSecret`, `testNow`, `testClock`. Private copies in `pages.go` (commented with their source): `aiFeatureOn`, `aiOnTestList`, `listHas` (from `go/internal/palette/palette.go aiEnabledFor`). No user-controlled URL is passed to a layout macro (`help_tip` gets no `guide_href`).

The new keys are appended to `properties/i18n_keys.txt`, so the one `i18n.json` serves both the 1300 flashes and the guide; `App/tests/test_go_properties_actions.py::test_go_catalog_matches_host_i18n` and `go_host_i18n.py --check` cover it.

CI: the `go` job runs `go test ./... -count=1` with `UBYHOST_TEST_DATABASE_URL` set, so `TestPagesMatchPython` runs against Postgres; the Python test runs in the SQLite suite and in `test-postgres-full`. Both backends give the same golden (checked in the dry run).

Rules that apply: AGENTS.md hard rule 2 (no new outbound request, no new personal-data field: none here), rule 3 (seed holds only made-up names and `example.test` addresses), rule 4 (no new dependency), rule 5 (Postgres SQL in Go, no schema change), rule 7/10 do not apply yet: the pages are not served (no template change on the Python side, no browser test).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/pages.go` | create | `RegisterPages`, `/guide`, `/guest-links`, AI gate copies |
| `go/internal/web/properties/pages_test.go` | create | golden replay on Postgres, extraction self-test, register test |
| `go/internal/web/properties/templates/guide.tmpl` | create | guide.html as a Go template |
| `go/internal/web/properties/i18n_keys.txt` | replace | 1300's keys plus the guide keys (bundle copy) |
| `go/internal/web/properties/i18n.json` | regenerate (step 3) | catalog from `App/app/host_i18n.py` |
| `go/internal/web/properties/testdata/pages_cases.json` | create | seed rows and 10 cases |
| `go/internal/web/properties/testdata/pages_golden.json` | create (generated, step 4) | what Python rendered per case |
| `go/cmd/ubyhost-web/register_web_properties.go` | replace | one added line: `properties.RegisterPages(...)` |
| `App/tests/test_go_properties_pages.py` | create | Python render; writes and checks the golden |
| `docs/tasks/1301-go-property-pages.md` | edit | `Status:` line only |
| `docs/tasks/1301-report.md` | create | report |

No other file may change.

## 4. Steps

1. Check you are on the branch, then copy the seven bundle files (run from the repo root):

```bash
git branch --show-current
# Done in the original run. The bundle was removed by brief 1410; the files are at the §3 paths on main.
```

Expected first line: `task/1301-go-property-pages`. Anything else: stop (§8).

2. Check the copied files:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -10
3a24d7b7c0b26e779981e1d889c949de135f94419d8d31c8fceaedd36e8affd3  go/internal/web/properties/pages.go
f291ae6e245006d8ed9a552ca327c694ecf2cba4e05be9b20abffe3b128e0c71  go/internal/web/properties/pages_test.go
634ed7ed275c6a0468aa983b727126db3b6aff75b56e1514cfd80b8b20bacbab  go/internal/web/properties/templates/guide.tmpl
1e2c69061cfa4a69909111b22e8c4be6d9a30351f51410cd1827c789bb98a5ea  go/internal/web/properties/testdata/pages_cases.json
83c38d9cd00a5e34f7aca36f6c3ef54e4b8db5e4ff089840517e1c511f10a54e  go/internal/web/properties/i18n_keys.txt
294c4c83a95da338bdbca2b49228d78e9e3a64411b833f882c6c743baa127dbe  go/cmd/ubyhost-web/register_web_properties.go
50d195b27969e94e19dd41ae06cd7b7e653047180626df77b707abca7f8c062f  App/tests/test_go_properties_pages.py
SUMS
```

Expected: 7 lines ending `OK`. Any `FAILED`: stop (§8).

3. Regenerate the catalog:

```bash
cd App && .venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -3 && sha256sum ../go/internal/web/properties/i18n.json
```

Expected: `wrote .../go/internal/web/properties/i18n.json`, then `e72cb114d416734cd38cdd4009d416d701449c6b1604b49b61cfac1329fbac06  ../go/internal/web/properties/i18n.json`. Another `wrote` line for a different package: stop (§8).

4. Generate the golden (Python on the fixture database) and check it:

```bash
cd App && UBYHOST_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_go_properties_pages.py -q --tb=short -x 2>&1 | tail -5 && sha256sum ../go/internal/web/properties/testdata/pages_golden.json
```

Expected: `2 passed`, then `14a8bfa128dd543d1d53866f045192de35989a13bd480651bb2a2e3d2c63d169  ../go/internal/web/properties/testdata/pages_golden.json`. A different sum: stop (§8); never edit the golden by hand.

5. Run the checks in §6. Then commit:

```bash
git add go/internal/web/properties go/cmd/ubyhost-web/register_web_properties.go App/tests/test_go_properties_pages.py && git commit -q -m "1301: Go port of property settings read-only pages" && git show --stat HEAD | tail -15
```

6. Set `Status: review` in this brief, write `docs/tasks/1301-report.md` (§9), commit both.

## 5. Do not touch

- Read-only: `go/internal/hostweb/` (including `layout/`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/palette/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, 1300's files (`properties.go`, `localpath.go`, `slug.go`, `properties_test.go`, `testdata/actions_*`, `App/tests/test_go_properties_actions.py`), `App/tests/conftest.py`, every file under `App/app/` and `App/scripts/`.
- `docs/ENVIRONMENT.md`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`.
- Nothing is added to `UBYHOST_GO_PATHS` anywhere. No bare `GET /` route.
- Do not edit the copied files or the golden by hand. No new dependency, no `go get`, no `go mod tidy`.
- Hard rules 3, 4, 5, 8 of AGENTS.md. Never push to `main`; never merge.

## 6. Commands

From the repo root, with the test database the environment gives (`export UBYHOST_TEST_DATABASE_URL=postgresql://...`; unset means the Go replay skips, which is a stop (§8), not a pass):

```bash
cd go && test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -5 && go test -count=1 -v ./internal/web/properties/ ./internal/hostweb/... ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- (FAIL|SKIP)|ok|FAIL)|Pages|Extract' | tail -30 && go build -o /dev/null ./cmd/ubyhost-web && echo BUILD OK
```

Expected: no `SKIP` or `FAIL`; `--- PASS: TestPagesMatchPython`, `--- PASS: TestExtractItemsScope`, `--- PASS: TestPagesRegisterDoesNotTouchThePool`; `ok` for properties, hostweb, hostweb/layout and cmd/ubyhost-web; `BUILD OK`.

```bash
cd App && .venv/bin/python -m pytest tests/test_go_properties_pages.py tests/test_go_properties_actions.py -q --tb=short -x 2>&1 | tail -5
cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -3; echo "check exit $?"
python3 scripts/context_lint.py 2>&1 | tail -3
git status --short | tail -20
```

Expected: `4 passed`; no `stale:` line; `context lint: OK`; after the commit, a clean tree.

## 7. Acceptance

- [ ] Step 2: 7 `OK`; steps 3 and 4: the sha256 sums given there.
- [ ] `go vet ./...` clean, `gofmt -l .` empty, `go build ./cmd/ubyhost-web` OK.
- [ ] `TestPagesMatchPython` ran (not skipped) and passed; 1300's tests still pass.
- [ ] Python: 4 passed; `go_host_i18n.py --check` prints no `stale:`.
- [ ] `git diff --stat c540113..HEAD` lists only §3 paths and this brief.
- [ ] `grep -rn UBYHOST_GO_PATHS go/internal/web go/cmd/ubyhost-web/register_web_properties.go` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- you are not on `task/1301-go-property-pages`, a `cp` fails, or a sum in steps 2-4 differs;
- `TestPagesMatchPython` is skipped or a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, or `go` wants to change `go.mod`/`go.sum`;
- a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1301-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat c540113..HEAD`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left, and one line naming `/menu` and `/housebook` as left out (§2).

## Risk list (for the reviewer)

Read these against the Python sources in §2:

- `go/internal/web/properties/pages.go`: login first; havel gate reads the signed-in account's email (the admin while inside a workspace), only when the feature and key are set; `UBYHOST_UBYPORT_ENV` empty counts as `mock` (Python keeps an explicitly empty value, which never happens on a real box); `/guest-links` counts the workspace's non-archived properties (`LIMIT 2`) and builds `Location` from an integer id only.
- `templates/guide.tmpl`: same tags, attributes and text as guide.html in all branches (havel on/off, demo on/off); the golden covers en, cs, vi, admin inside a workspace and signed out.
- `pages_test.go` / `test_go_properties_pages.py`: the two `extract_items` must stay identical; the scope test pins both.

Known differences left on purpose: the shell around `div.ui-page` (nav, banners, alerts) is not compared here (layout's own test; host alerts arrive with 1381, and Go pages must not go live before it). `<title>` is translated by the page with `hostweb.Lang`, as the layout resolves it for a signed-in host.

## Owner steps

1. Wait for the draft PR's CI to go green (the `go` job runs the Postgres replay).
2. Nothing to deploy or configure: the routes stay off until a later brief adds them to `UBYHOST_GO_PATHS`, after 1381.
