# 2081 report: Restore branded guest 404 and HTML 405 pages

Status: review

## Files changed (commits f86aaf8, 0469faf, 600d64d)

- `go/cmd/ubyhost-web/main.go` (+25/-6): catch-all computes status and Allow before rendering; HTML requests use the guest adapter or the host renderer.
- `go/cmd/ubyhost-web/main_test.go` (+56): `TestCatchAllBrandedErrors`.
- `go/internal/hostweb/notfound.go` (+9/-1): `NotFoundHTML` takes a status.
- `go/internal/web/guest/pages.go` (+8): DB-free adapter to the localized `bad_link` view.

## Command results

- `go build ./...` (from `go/`): clean.
- `go test ./cmd/ubyhost-web/... ./internal/hostweb/... ./internal/web/guest/... -count=1`: ok for cmd/ubyhost-web, hostweb, hostweb/layout, web/guest. No FAIL lines.
- `UBYHOST_REQUIRE_BROWSER=1 App/.venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q --tb=short -x -rs` (main checkout venv): 6 passed, 0 skipped, 72 s.

## Screenshots (390 px)

Saved in `/tmp/claude-0/-home-user-jsfpecharoperations/fddd852d-eb27-56de-8c5b-4ff23a59b41e/scratchpad/2081-shots/`:

- `host-404-390.png`: unknown host path `/no-such-page`, status 404. Shows "Page not found", "The link is wrong or the page no longer exists.", and a "Home" link, in light mode.
- `host-405-390.png`: HTML 405 from `POST /payments` with `Accept: text/html`. Status 405 and `Allow: GET, HEAD` confirmed. The screenshot shows the same branded body, since it was rendered from the response HTML.

No guest 404/405 screenshot was taken in this step; the guest catch-all is only reachable outside `/l/` (see Finding).

## Finding

`/l/` paths go to the guest picker, which has its own branded bad-link page. The guest catch-all branch is therefore only reachable outside `/l/`.

## Deviations

- The brief file `docs/tasks/2081-go-branded-404-and-405.md` status line was not changed.
- Trailer on commits follows the task instruction (Opus 5.5). The session's own attribution reminder names Haiku 5.5.
- The server was started on 127.0.0.1:18081 against guest_test and stopped afterwards.

## Owner steps

1. Review the screenshots and the 405 status and Allow results.
2. Decide whether the `/l/` finding needs a follow-up brief.
