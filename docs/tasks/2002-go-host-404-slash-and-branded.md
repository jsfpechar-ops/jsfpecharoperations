# 2002: Go host web answers a trailing-slash stay URL with a bare 404

Status: review
Depends on: none | Base commit: 6d8c1c4 | Branch: task/2002-go-host-404-slash-and-branded
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Three Go-only fixes in the host web, none of them touching Python:

1. `GET /reservations/252/` answers `404 page not found` from Go; Python answers `307` to `/reservations/252` (Starlette `redirect_slashes`). Every registered host route has the same gap, because the mux has an exact pattern and a `/` catch-all, with nothing in between.
2. A 404 on a host page renders Go's bare text `404 page not found` instead of the branded page the owner expects (Python renders `error.html` with `error_kind=not_found`). The owner saw this black page from an email link and reported it as a bug.
3. `staydetail`'s two not-found branches write no log line, so the one production 404 on a real stay (see §2) cannot be attributed to an id, a workspace or a method. Add exactly one line per not-found.

## 2. Context (verified 2026-11-22, read-only, on production and on `main`)

- Production runs the split Caddyfile: `@go path {$UBYHOST_GO_PATHS:/__go_off__}` → Go, default → Python. `.env` carried `/reservations/*[0-9]`; the owner removed it again (`.env` backup `~/ubyhost-env-backup-20261122T133030Z`, caddy recreated 13:30Z).
- Probes straight at the Go container (`ubyhost-go:8081` from the caddy container): `/reservations/252` → `303` (`/login` when anonymous), `/reservations/252/` → `404`, `/dev/ui` → `404`, `/healthz` → `200`. Against Python (`ubyhost:8080`): `/reservations/252/` → `307`.
- Go's own Prometheus counters (`/metrics`, container started 2026-11-20T12:11Z) show `route="/reservations/{reservation_id}"` with `code="200"` ×47, `code="303"` ×7, `code="404"` ×1, while the container log for the same span has **zero** `stay detail` lines. So the single 404 came from `http.NotFound` in `detailHandler` (parse or `!ok`), not from `serverError`.
- Ownership is **not** the difference: `App/app/access.py:94-106` scopes with `owner_id(request)` = `auth.workspace_user(request)["id"]`, and `go/internal/web/staydetail/load.go` `loadStaySQL` scopes with `a.owner_user_id IS NOT DISTINCT FROM $2` fed by `host.Workspace.ID` (`handlers.go:49`). Same account, same predicate.
- `git merge-base --is-ancestor 1737a58aa main` → **yes** (the box checkout is an ancestor), and `git diff 1737a58aa..main -- go/internal/web/staydetail` is **empty**, so this is not deploy drift: the gap is on `main`.
- Python's branded 404: `App/app/main.py:261-289` → `templating.render("error.html", {"error_kind": "not_found"}, status_code=404)` for HTML clients.
- Go's branded 404 already exists: `go/internal/hostweb/notfound.go` `BlockedPage` (branded HTML when `WantsHTML`, empty 404 body otherwise), used today only for the payments-hidden middleware at `go/cmd/ubyhost-web/main.go:64`.

Exact excerpts (verify verbatim; if any is not found, STOP §8):

- `go/cmd/ubyhost-web/main.go:126-128`:
  `func notFound(w http.ResponseWriter, _ *http.Request) {` / `http.NotFound(w, nil)` / `}`
- `go/cmd/ubyhost-web/main.go:229`: `mux.Handle("/", m.wrap("/", notFound))`
- `go/cmd/ubyhost-web/main.go:193`: `srv := &http.Server{Addr: addr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}`
- `go/internal/web/staydetail/handlers.go:44-47` (after `strconv.ParseInt`) and `:54-57` (after `!ok`): each is `http.NotFound(w, r)`
- `go/internal/hostweb/notfound.go:18-31`: `func BlockedPage(w http.ResponseWriter, r *http.Request) {` … `w.WriteHeader(http.StatusNotFound)`. `go/internal/hostweb/notfound.go:10-16` is `WantsHTML`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/hostweb/notfound.go` | edit | move the body into `NotFoundPage`; keep `BlockedPage` as a one-line call |
| `go/internal/hostweb/notfound_test.go` | edit | add `TestNotFoundPageHTML` / `TestNotFoundPageEmpty` |
| `go/internal/hostweb/slash.go` | new | `CanonicalSlash` wrapper (§4.2) |
| `go/internal/hostweb/slash_test.go` | new | table test (§4.5) |
| `go/cmd/ubyhost-web/main.go` | edit | wire `CanonicalSlash`, branded catch-all 404 |
| `go/internal/web/staydetail/handlers.go` | edit | branded 404 + one log line via a small `stayNotFound` helper |
| `go/internal/web/staydetail/handlers_test.go` | edit | `TestStayNotFound` (branded body, empty non-HTML body) |

No other file may change. No Python file, no Caddyfile, no `.env`, no deploy script.

## 4. Steps

1. **`hostweb.NotFoundPage`.** In `notfound.go`, rename the current `BlockedPage` body to `func NotFoundPage(w http.ResponseWriter, r *http.Request)` with a doc comment naming both callers (payments-hidden middleware and host-page 404s, `App/app/main.py:261-289`), then keep the old name for its existing call site:

   ```go
   // BlockedPage is the payments-hidden middleware's 404; NotFoundPage serves
   // every other host-page 404. One implementation, two names.
   func BlockedPage(w http.ResponseWriter, r *http.Request) { NotFoundPage(w, r) }
   ```

   Do not change the HTML, the copy helpers or the `WantsHTML` contract.

2. **New `go/internal/hostweb/slash.go`.** Starlette's `redirect_slashes`: a request whose path ends in `/` and whose path without the slash is served by a route gets a `307` to that path, query preserved; everything else falls through untouched. Use the mux itself as the oracle, and never redirect when the matching pattern is a subtree (ends in `/`) or missing, which is what keeps this from looping on the mux's own trailing-slash redirects:

   ```go
   // Router is the part of *http.ServeMux CanonicalSlash needs.
   type Router interface {
   	Handler(r *http.Request) (http.Handler, string)
   }

   // CanonicalSlash answers <path>/ with a 307 to <path> when a registered
   // route serves <path>, as Starlette's redirect_slashes does for the Python
   // app (305-style 307, method and body preserved). Routes registered as a
   // subtree ("/static/") and unknown paths are left to the mux.
   func CanonicalSlash(router Router, next http.Handler) http.Handler {
   	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
   		p := r.URL.Path
   		if len(p) > 1 && strings.HasSuffix(p, "/") {
   			if trimmed := strings.TrimRight(p, "/"); trimmed != "" {
   				probe := r.Clone(r.Context())
   				u := *r.URL
   				u.Path, u.RawPath = trimmed, ""
   				probe.URL = &u
   				if _, pattern := router.Handler(probe); pattern != "" && pattern != "/" && !strings.HasSuffix(pattern, "/") {
   					target := trimmed
   					if u.RawQuery != "" {
   						target += "?" + u.RawQuery
   					}
   					http.Redirect(w, r, target, http.StatusTemporaryRedirect)
   					return
   				}
   			}
   		}
   		next.ServeHTTP(w, r)
   	})
   }
   ```

3. **Wire it in `main.go`.** `srv := &http.Server{Addr: addr, Handler: hostweb.CanonicalSlash(mux, mux), ReadHeaderTimeout: 5 * time.Second}` and replace `notFound`'s body with `hostweb.NotFoundPage(w, r)` (keep the `mux.Handle("/", m.wrap("/", notFound))` line so the catch-all still counts in `ubyhost_go_http_requests_total`). `m.wrap` is unchanged.

4. **staydetail 404.** In `handlers.go` replace both `http.NotFound(w, r)` calls with one helper placed next to `serverError`:

   ```go
   // stayNotFound writes the branded host 404 and leaves one line for the next
   // production report: a stay that exists but is not the workspace's is a 404
   // by design (access.reservation parity), an unexplained one is not.
   func stayNotFound(w http.ResponseWriter, r *http.Request, id, workspaceID int64) {
   	log.Printf("stay detail: not found method=%s id=%d workspace=%d", r.Method, id, workspaceID)
   	hostweb.NotFoundPage(w, r)
   }
   ```

   Call it as `stayNotFound(w, r, 0, host.Workspace.ID)` on the parse branch and `stayNotFound(w, r, id, host.Workspace.ID)` on the `!ok` branch. The line carries request method and two database ids only, no name, no email, no token.

5. **Tests.** `slash_test.go`: a mux with `GET /reservations/{reservation_id}`, `GET /reservations`, `GET /static/` and a `/` catch-all, wrapped in `CanonicalSlash`; assert (a) `/reservations/7/` → 307 with `Location: /reservations/7`, (b) `/reservations/7/?return_to=%2F` → 307 with the query preserved, (c) `POST /reservations/7/` → 307 with the method kept, (d) `/` → the catch-all (200), (e) `/nope/` → the catch-all (404 via `NotFoundPage`), (f) `/static/app.css/` → untouched catch-all, no redirect. `notfound_test.go`: `NotFoundPage` branded HTML with `Accept: text/html`, empty body without it. `handlers_test.go`: `stayNotFound` — `strings.Contains(body, "Page not found")` with `Accept: text/html`, and a zero-length body for a request without it.

6. **Housekeeping.** `gofmt -l` clean, `go vet` clean, comment on the brief's §2 numbers where they are cited (do not copy the whole diagnostic into the code).

## 5. Do not touch

`App/` (any file), `deploy/` (Caddyfile, `.env`, scripts), `docs/context/*` other than nothing, other Go routes, the `wrap` metric keys, `hostweb.BlockedPage`'s HTML, the Caddy Go/Python path split, git history. No new dependency. Never push to `main`.

## 6. Commands

From `go/`: `gofmt -l ./internal/hostweb ./internal/web/staydetail ./cmd/ubyhost-web 2>&1 | tail -30`, `go vet ./internal/hostweb/... ./internal/web/staydetail/... ./cmd/ubyhost-web/... 2>&1 | tail -30`, `go test ./internal/hostweb/... ./internal/web/staydetail/... ./cmd/ubyhost-web/... 2>&1 | tail -30` (DB tests skip without `UBYHOST_TEST_DATABASE_URL`, per `docs/context/test-map.md` "Go filing alarms"). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -20`.

## 7. Acceptance

- [ ] `/reservations/7/` and `/reservations/7/?x=1` answer `307` to `/reservations/7` (query kept), `POST` included; `/`, unknown paths and subtree routes are unchanged.
- [ ] A host-page 404 with `Accept: text/html` renders the branded page; without it the body stays empty; the payments-hidden middleware still uses the same page.
- [ ] `staydetail` logs exactly one `stay detail: not found method=… id=… workspace=…` line per not-found and nothing else new.
- [ ] `gofmt`, `go vet`, the three package test suites and `scripts/context_lint.py` are green.
- [ ] PR body states what was NOT fixed: the one production 404 of 2026-11-22 is still unexplained; this brief only makes the next one diagnosable.

## 8. Stop and ask

Stop and write the report if: an excerpt in §2 is not found verbatim; a test fails twice; you reach 25 tool calls or ~50k tokens; a file outside §3 looks necessary; §5 would be touched; a step is unclear; you need push, merge, deploy or `.env` (owner).

## 9. Report

Write `docs/tasks/2002-report.md` (≤600 tokens), set `Status: review`, open one PR. Report: `git diff --stat`, each command with its last 5 lines, §7 ticked, deviations, and the answer to one question: does the trailing-slash redirect also cover the `#now` anchor link from the stay email (`https://app.ubyhost.com/reservations/252#now`), and if not, why not.

## Risk list (for the reviewer)

`go/cmd/ubyhost-web/main.go` (the handler chain every request passes through), `go/internal/hostweb/slash.go` (loop risk if the subtree guard is dropped), `go/internal/web/staydetail/handlers.go` (the stay page's 404 paths).

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh` once CI is green; staging ships automatically, production stays untouched.
2. When production is deployed again through the gated workflow (`workflow_dispatch`, ref `main`, `force_confirm=DEPLOY`), `/reservations/252/` redirects instead of 404ing, a not-found stay shows the branded page, and `docker logs ubyhost-ubyhost-go-1 | grep "stay detail: not found"` names the method, the stay id and the workspace id of any repeat.
