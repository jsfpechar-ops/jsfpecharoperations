# 1704b report

Status: review
Branch: claude/beautiful-archimedes-lxhrit (not the brief's task/1704b-go-settings-pages). Step 1 commit: b7a8c45.

## 1. Files changed (step 1, sidecars copied and hash-checked)

- go/internal/retention/settings_view.go (new)
- go/internal/mail/console_view.go (new)
- go/internal/web/public/operator.go (new)
- go/internal/web/settings/ (settings.go, data.go, templates/settings.tmpl, templates/group_security.tmpl, templates/group_phone.tmpl, i18n_keys.txt, i18n.json, settings_test.go)
- go/cmd/ubyhost-web/register_web_settings.go (new)
- go/cmd/ubyhost-web/register_web_settings_test.go (new)
- docs/tasks/1704b-go-settings-pages.md and docs/tasks/1704-go-settings-menu-pages.md (Status only)

## 2. Commands

- Step 0 checks: all 14 anchors matched, 4 new paths absent, 13 sidecars present.
- Step 1 sha256sum -c: 13 of 13 `: OK`.
- Step 2 gofmt, go build, go vet: no output.
- Step 3 i18n check: CI only (no App/.venv).
- Step 4 PostgreSQL 16: existing cluster reused (`initdb` skipped, the data dir was not empty), started on port 55704, stopped at the end.
- Step 5 `go test` on the 5 packages: 5 of 5 `ok`.
- Step 5 named tests: 13 `--- PASS` in web/settings and 1 in cmd/ubyhost-web (`TestSettingsPageRoutesRegistered`), 14 of 14 named tests in total. SKIP count: 0.
- Context lint: `context lint: OK`.

## 3. Acceptance (§7)

- [x] sha256 13 of 13 OK
- [x] format, build and vet silent
- [ ] Step 3 i18n: CI only (no App/.venv)
- [x] Step 5: 5 `ok`, 14 PASS, SKIP 0
- [x] Only the §3 paths were committed; no push, no `main`, no `UBYHOST_GO_PATHS`, no Caddy, compose, env or Python change
- [ ] UI gate: pending (see 6)

## 4. Deviations

- Branch as above.
- Step 6 UX gate: no Python baseline (no App/.venv), no screenshots, no browser run. design-system section 5 is NOT ticked: its visual items cannot be checked without a browser.
- Done: steps 1 to 7. Left: none in code.

## 5. Questions

- Coordinator: add the Go test row (`go test ./internal/web/settings/... ./internal/retention/... ./internal/mail/...` on PostgreSQL) to test-map.

## 6. Owner steps left

- Screenshots at 390, 768 and 1280 of the five Go pages, with `test_layout_lint_browser.py` green on Go. Pending until brief 1705 switches the paths.
- known-issues (for the orchestrator to append):
  - "Settings > Data shows the time and dry/live state of the last retention run of any host (`retention_last_run` is one global setting row; Python the same; the counts are admin only)."
  - "`appVersion` in `go/internal/web/settings/data.go` mirrors `App/app/__init__.py`; the Go test breaks when Python's version is bumped alone."
