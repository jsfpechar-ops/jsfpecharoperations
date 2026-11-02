# 0680: Go command palette, guest link slug and missing tests
Status: review
Depends on: 0679 (commit 53440ff) | Base commit: task/0679-go-command-palette | Branch: task/0679-go-command-palette
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
## 1. Objective
Finish 0679 (read `docs/tasks/0679-report.md` first): port `guest_slug.ensure` so the Go palette creates a missing slug exactly as Python's `link_key` does, and add the tests 0679 left out. Production unchanged: Go container off.
## 2. Context
Python source of truth: `App/app/guest_slug.py` (all; grep `^def `, read `fold`, `readable_part`, `is_reserved`, `new_code`, `compose`, `_generated_readable`, `link_key`, `_insert_current`, `ensure` and the reserved-word list). The code alphabet and length come from `new_code`; use `crypto/rand`. Go: `go/internal/palette/` (0679 code). Folding must match Python for Czech names (`Chata Žluťoučký kůň` etc.): write a table test with 6 names whose expected `_generated_readable` outputs you get by running Python: `cd App && .venv/bin/python -c "from app import guest_slug; print([guest_slug._generated_readable(n) for n in [...]])"`. Insert with Postgres `$n`, inside a transaction, retry on a clash as `_insert_current` does.
## 3. Files
Edit/create only in `go/internal/palette/` (new `slug.go` + tests). Write `docs/tasks/0680-report.md`.
## 4. Steps
1. `slug.go`: `ensure` and helpers; `link_key` in the palette uses it.
2. Tests (DB, `UBYHOST_TEST_DATABASE_URL`): readable table test; property with token and no slug -> palette copy item has `/l/<readable>-<code>` and one `apartment_slug` row is written, second request reuses it; existing slug used as-is; two properties -> hub URLs `/apartments#property-summaries`; admin role adds the two admin items; 81 stays -> 80 stay items, archived and other owner's stays left out; 41 submissions -> 40; exact byte output for one small fixture (hardcoded expected JSON string).
3. Commit: `0680: Go command palette guest link slug and tests`.
## 5. Do not touch
Everything outside `go/internal/palette/` except the report and this Status line. No new dependency.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/t0679 go test ./internal/palette/ -count=1 2>&1 | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
palette tests pass, 0 skipped; vet/gofmt clean.
## 8. Stop and ask
Stop if `ensure` needs a schema change.
## 9. Report
`docs/tasks/0680-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
