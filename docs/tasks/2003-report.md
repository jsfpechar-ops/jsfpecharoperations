# Task 2003 Report: Host HTML branded NotFoundPage sweep

Status: review

## Changes

Replaced bare `http.NotFound` / plain `Not found.` on host HTML paths with `hostweb.NotFoundPage`. Added `TestHostPackagesNoBareNotFound` pin. Branched from 2002 tip (`db9987149`). On this tip the admin catalog file is `dev_ui.go` (not `dev_ui_page.go`).

```
go/internal/hostweb/notfound_host_pin_test.go | new
go/internal/web/{settings,properties,submissions,stays,staydetail,exports,public}/… | NotFoundPage
docs/tasks/2003-*.md | brief + report
docs/context/{status,decisions,known-issues}.md | orch notes (K-O07/08)
```

## Commands (last lines)

- `gofmt -l …` → empty
- `go test ./internal/hostweb/ -run TestHostPackagesNoBareNotFound` → PASS
- `go test ./internal/hostweb/ ./internal/web/{staydetail,stays,submissions,properties,exports,public}/` → all ok
- `go test ./internal/web/settings/` → FAIL without `UBYHOST_TEST_DATABASE_URL` (pre-existing; not caused by this change)
- `python3 scripts/context_lint.py` → OK

## Acceptance

- [x] Pin file list has no `http.NotFound(` / `[]byte("Not found.")`
- [x] `edit_posts.go` still returns JSON `{"ok":false}` for missing stay after valid id
- [x] Pin test PASS; package tests green (settings needs DB)
- [x] Left out: guest, booking, JSON APIs, misc alert, pages_render

## Deviations

- Pin lists `dev_ui.go` (2002 tip); brief originally said `dev_ui_page.go` (main rename).

## Owner steps

1. Merge #1256 (2002) then this PR with `scripts/merge-pr-on-green.sh` (or stack).
2. After deploy: missing apartment / `/settings/nope` → branded 404, not black text.
