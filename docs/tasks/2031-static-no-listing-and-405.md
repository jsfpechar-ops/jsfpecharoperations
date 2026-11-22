# 2031: No /static/ directory listing; wrong method on a known route gives 405 (D1, D3)

Status: todo
Depends on: none | Base commit: main | Branch: task/2031-static-no-listing-405
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`/static/` and any `/static/<dir>/` must answer 404, not an index of files. A POST to a path that exists for GET (for example `POST /cenik`) must answer 405 with `Allow`, as Python did, not 404.

## 2. Context

D1: `go/internal/web/staticfiles/static.go` lines 55-68 use `http.FileServer(http.Dir(root))`, which lists directories. Python's `StaticFiles` returned 404 for a directory.

D3: `go/cmd/ubyhost-web/main.go:249` registers `mux.Handle("/", m.wrap("/", notFound))`. Go's ServeMux only produces 405 when no pattern matches the path at all; the catch-all matches every method, so `POST /cenik` (only `GET /cenik` exists, `register_web_public.go:37`) falls through to the 404 page.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/web/staticfiles/static.go | edit | wrap the FS so directories (and paths ending `/`) are 404; use a `neuteredFS` whose `Open` returns `fs.ErrNotExist` for directories |
| go/internal/web/staticfiles/static_test.go | edit/add | `/static/`, `/static/platforms/` are 404; `/static/tokens.css` is 200 |
| go/cmd/ubyhost-web/main.go | edit | in `notFound`, if the path matches a registered pattern for another method answer 405 with `Allow` (use `mux.Handler(&http.Request{Method: m, URL: r.URL, Host: r.Host})` over GET, HEAD, POST and compare the returned pattern with `"/"`) |
| go/cmd/ubyhost-web/*_test.go | add | `POST /cenik` is 405 with `Allow: GET, HEAD`; `GET /nope` is still 404 |

No other file may change.

## 4. Steps

1. Read `static.go` lines 1-80 and `main.go` lines 120-140 and 240-255.
2. Implement the directory guard first; test; then the 405 logic; test.
3. `cd go && go test ./internal/web/staticfiles/... ./cmd/ubyhost-web/... 2>&1 | tail -30`.

## 5. Do not touch

Routes, Caddy, templates. POST routes that exist must keep working; the 405 probe must never call a handler.

## 6. Commands

From `go/`: `go test ./internal/web/staticfiles/... ./cmd/ubyhost-web/... 2>&1 | tail -30`. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Tests in §3 pass.
- [ ] `/static/favicon.png?v=1` still 200 with the same cache headers.

## 8. Stop and ask

As 2030 §8. Also stop if the 405 probe changes any existing route test.

## 9. Report

`docs/tasks/2031-report.md`, 600 tokens at most.
