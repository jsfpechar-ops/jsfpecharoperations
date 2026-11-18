# 1704a report: Go house book page (GET /housebook)

Status: review (no PR opened: run rules forbid it; the owner or coordinator opens it). Dormant: `UBYHOST_GO_PATHS` not changed.

## 1. Files changed

Commit `571ff5f 1704a step 1` (sidecars copied and checksum-verified, then committed):
- `go/internal/web/exports/housebook_view.go`, `go/internal/web/exports/housebook_view_test.go`
- `go/internal/web/housebook/housebook.go`, `housebook_test.go`, `templates/housebook.tmpl`, `i18n_keys.txt`, `i18n.json`
- `go/cmd/ubyhost-web/register_web_housebook.go`, `register_web_housebook_test.go`

Step 7 (this commit): `docs/tasks/1704a-report.md` (new), `docs/tasks/1704a-go-housebook-page.md` (Status: review), `docs/tasks/1704-go-settings-menu-pages.md` (index row Status: review).

## 2. Commands (last lines of output)

- Step 0 anchors: all 15 checks as stated (9 greps print 1, the route grep prints nothing, the two `ls` say "No such file", 9 sidecars).
- Step 1 sha256: 9 lines, all `: OK`.
- Step 2 gofmt, build, vet: no output.
- Step 3 `go_host_i18n.py --check`: `i18n rc=0`; pytest `2 passed in 0.58s`, no skip.
- Step 4: skipped, `UBYHOST_TEST_DATABASE_URL` already set (PostgreSQL 16 on 55700).
- Step 5: `ok .../go/internal/web/housebook`, `ok .../go/internal/web/exports`, `ok .../go/cmd/ubyhost-web`. The 11 named tests: all `--- PASS`. SKIP count: `0`.
- Step 6 Python baseline: `ModuleNotFoundError: No module named 'playwright'` at collection of `tests/test_layout_lint_browser.py`. Not run.
- Context lint: `context lint: OK`, rc=0.

## 3. Brief section 7

- [x] sha256 `: OK` for all 9 files
- [x] format, build and vet printed nothing
- [x] Step 3: `i18n rc=0` and a `passed` line
- [x] Step 5: three `ok` lines, 11 tests PASS, SKIP 0
- [x] Commit list: `571ff5f 1704a step 1` (the only step commit with changes)
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env or Python change
- [ ] UI gate: pending (see Owner steps)

Design-system section 5 checklist: not ticked. Every item needs a rendered page, and the Go page cannot be rendered yet. Items already true for the template (same classes and markup as Python) are unverified until the screenshots exist.

## 4. Deviations

- Step 1 used explicit `git add <paths>` for the 9 files, not `git add go`.
- Step 4 skipped: the existing PostgreSQL server was used.
- Step 6 Python baseline did not run: `App/.venv` has no `playwright`. Installing it is a new dependency (rule 4), so I did not install it. The Go screenshots at 390, 768 and 1280 are pending the path switch, as the brief says.
- Step 7 edited two files outside brief §3 (the brief's own status line and the 1704 index row), because step 7 names both edits.
- Step 7 status is `review` without a PR, because the run rules forbid opening one.
- Known-issues item (for the coordinator): the house book shows a guest filed by hand as "Not yet sent" (Python quirk, `housebook.html` `reported_pill` tests only the exact `yes`). Kept on purpose; a test pins it.

## 5. Questions

- Should `playwright` be added to `App/.venv` for the local UX baseline, or does the UX baseline run only in CI? This needs an owner decision (rule 4).

## 6. Owner steps left

1. Open the PR for `claude/beautiful-archimedes-lxhrit` (not `main`) and let the UX gate run.
2. UX gate on Go: screenshots of `/housebook` at 390, 768 and 1280 px, layout lint on Go, then tick design-system section 5.
3. Path switch only after step 2 (brief section "Owner steps"): add `/housebook` to `UBYHOST_GO_PATHS`, run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
