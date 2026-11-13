# 1363 report

Status: review
Start commit: d44f8bce08e0a55f9780e7b17ce2711075fe8e05 (HEAD before step 1; brief base a83df54 is older, 1360 and 1362 were already on the branch)

## 1. Files changed (`git diff --stat d44f8bc HEAD`)

```
go/cmd/ubyhost-web/register_web_customers.go |  22 +++
go/internal/web/customers/handlers.go        | 155 ++++++++++++++++++
go/internal/web/customers/handlers_test.go   | 237 +++++++++++++++++++++++++++
go/internal/web/customers/i18n.json          |  18 ++
4 files changed, 432 insertions(+)
```

Commits: 1799ab0 (step 2), 5804c64 (step 3), 9b2708b (step 4). Step 5 is this report.

sha256: i18n.json, handlers.go, register_web_customers.go and handlers_test.go all matched the brief on the first check.

## 2. Commands (last lines of output)

- Step 2 build: `cd go && go build ./internal/web/...` printed nothing, exit 0.
- Step 3 vet: `go vet ./cmd/...` printed nothing, exit 0.
- §6.2 gofmt, vet, test: `ok  	.../go/internal/web/customers	1.987s` and `ok  	.../go/cmd/ubyhost-web	0.007s`.
- §6.2 SKIP count: `0`.
- §6.3 `.venv/bin/python -m pytest tests/test_admin_customers_golden.py -q --tb=short`: `1 passed in 1.91s`.
- §6.4 `python3 scripts/context_lint.py`: `next free: task 1364 | migration 0046`, then `context lint: OK`. The WARN lines above it are about other briefs and an App/ commit after the last status update; not from this change.

## 3. §7 acceptance

- [x] 4 files exist with the sha256 values in §4.
- [x] customers and cmd/ubyhost-web tests pass; SKIP count 0.
- [x] `grep -c 'mux.Handle' go/cmd/ubyhost-web/register_web_customers.go` prints `2`.
- [x] Context lint OK.
- [x] `git diff --stat d44f8bc HEAD` lists only §3 paths.

## 4. Deviations

- Step 1 skipped: Postgres already accepted connections on 127.0.0.1:55436.
- No push and no PR opened: the owner instruction was "do not push".
- Docs/tasks/1363-report.md is this file; the brief's `Status:` line was set to `review`.

## 5. Questions

None.

## 6. Owner steps left

- Push branch `go-customer-admin` and open the draft PR for 1360 to 1363 (orchestrator step).
