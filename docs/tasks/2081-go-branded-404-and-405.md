# 2081: Restore branded guest 404 and HTML 405 pages

Status: todo
Depends on: 2080 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2081-go-branded-404-and-405
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Use the existing localized error views for browser 404 and 405 responses from the Go catch-all. Preserve status, method headers and guest privacy.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/main.py:264`

  ```text
  if exc.status_code not in (404, 405) or not _wants_html(request):
  ```
- `App/app/routes/guest.py:970`

  ```text
  def error_page(request: Request, kind: str, status_code: int):
  ```
- `go/cmd/ubyhost-web/main.go:131`

  ```text
  func notFound(mux *http.ServeMux) http.HandlerFunc {
  ```
- `go/internal/hostweb/notfound.go:32`

  ```text
  func NotFoundPage(w http.ResponseWriter, r *http.Request) {
  ```
- `go/internal/web/guest/pages.go:67`

  ```text
  func (g guestAccess) unavailable(w http.ResponseWriter, r *http.Request, lang, reason string, status int, token string, resID int64, extra map[string]string) {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/cmd/ubyhost-web/main.go` | edit | Select the HTML renderer without changing routing. |
| `go/cmd/ubyhost-web/main_test.go` | edit | Verify the normal mux path, format and Allow. |
| `go/internal/hostweb/notfound.go` | edit | Generalize the existing renderer to the supplied status. |
| `go/internal/web/guest/pages.go` | edit | Export an adapter to the existing guest unavailable view. |

The executor report and brief status follow section 9.

## 4. Steps

1. In `hostweb/notfound.go`, extract the body of `NotFoundPage` into a status-taking `NotFoundHTML` renderer and have `NotFoundPage` call it with 404 for its HTML case. Keep `BlockedPage` behavior and current content. In `guest/pages.go`, add a DB-free adapter to render the existing localized `bad_link` view for the supplied 404/405 status and Python's guest language and token fallback. Pass only escaped, scoped link pieces to the template.
2. In the Go mux catch-all, calculate status and Allow before rendering. Return the same numeric status and preserve Allow on 405. On HTML requests use the guest adapter for guest paths and the existing host renderer for host paths. Keep current non-HTML paths and never redirect on a wrong method. Leave the 500 wrapper in place.
3. Add `TestCatchAllBrandedErrors` with a synthetic guest path and a known path receiving a wrong method, host equivalents and non-HTML variants. Check 404/405, HTML, Allow, two guest languages and no data lookup on the error page. Run section 6. Capture the host and guest error pages as required.

## 5. Do not touch

Keep existing router patterns, redirects, 500 logic, language catalogs and payments gate. Limit implementation to the browser catch-all.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./cmd/ubyhost-web/ ./internal/hostweb/ ./internal/web/guest/ -run 'CatchAllBrandedErrors|NotFoundPage|BadLinkPage' -count=1 -v 2>&1 | tail -30
cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```

For each changed guest-facing response, include a 390 px screenshot from the Go flow with synthetic data. For host page changes apply the 390/768/1280 host UX gate and report what you saw at each width.

## 7. Acceptance

- [ ] Guest 404 and browser 405 use their localized templates and keep the right status.
- [ ] Host 405 keeps Allow and existing host copy. API and retired-path behavior are unchanged.
- [ ] Error rendering needs no database or provider call, and screenshots are attached.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2081-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/cmd/ubyhost-web/main.go`, `go/internal/hostweb/notfound.go`, `go/internal/web/guest/pages.go`

## Owner steps

1. Open after 2080 because both briefs edit the web entry point.
2. Review screenshots and the status and header results.
