# 1704c report: Go settings security and phone pages

Status: review

## 1. Files changed (step commits 1 and 2)

- go/internal/web/settings/security.go, phone.go, security_phone_test.go (new)
- go/internal/web/settings/templates/group_security.tmpl, group_phone.tmpl (replaced 1704b stubs)
- go/internal/web/settings/i18n_keys.txt, i18n.json
- go/internal/web/settings/settings.go (four edits)
- go/cmd/ubyhost-web/register_web_settings_security.go, register_web_settings_security_test.go (new)
- docs/tasks/1704c-report.md, 1704c brief and 1704 index (Status only, step 8)

No file under App/ changed. No path was added to UBYHOST_GO_PATHS.

## 2. Commands (last lines of output)

- Step 0: all anchors `1`, all five 1704b hashes `: OK`, no 1704c file present, 9 sidecars.
- Step 1: 9 hashes `: OK`.
- Step 2: `settings.go` hash `: OK`.
- Step 3 (gofmt, go build, go vet): no output.
- Step 4: `Python checks: CI only (no App/.venv)`.
- Step 5: PostgreSQL 16 started on 55706 (`server started`), stopped at the end.
- Step 6: `ok .../go/internal/web/settings`, `ok .../go/cmd/ubyhost-web`. The 15 named tests all `--- PASS`. SKIP count: 0.
- Step 7: `UX baseline: CI only (no App/.venv)`. Context lint (repo root): `context lint: OK`.

## 3. Section 7 acceptance

- [x] Step 0 checks as stated.
- [x] Step 1 sidecar hashes and step 2 hash `: OK`.
- [x] Format, build and vet printed nothing.
- [ ] Step 4 i18n: CI only (no App/.venv).
- [x] Step 6: two `ok` lines, 15 tests PASS, SKIP 0.
- [x] Step commits list only the §3 paths.
- [x] No UBYHOST_GO_PATHS, Caddy, compose, env or Python change; nothing pushed.
- [ ] UX gate (390/768/1280 screenshots, layout lint on Go): pending until 1705.

Design checklist (design-system.md §5), not ticked: the screenshot items wait for the owner switch (1705). The Python-to-Go markup diff (`_csrf` only) is taken from the brief; not re-checked here.

## 4. Deviations

- The sidecars under docs/tasks/1704c-files were copied to their repo paths but not re-committed: they were already tracked and unchanged.
- Step 7 Python baseline and step 4 i18n check could not run (no App/.venv).

## 5. Questions

None.

## 6. Owner steps left

- Brief 1705 switches `/settings/security` and `/settings/phone` (add to UBYHOST_GO_PATHS, see the brief's Owner steps).
- For brief 1764: the page-data struct is `SecurityData` in go/internal/web/settings/security.go, built in `loadSecurity` (add `DeviceKind string` there). The passkeys section is the template `settings.passkeys` in go/internal/web/settings/templates/group_security.tmpl.
- For brief 1705: the routes are `GET /settings/security` and `GET /settings/phone`. Forms post to the existing `/account/*` routes; keep the Python ones until switched.
