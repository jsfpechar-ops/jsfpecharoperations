# Report 1425: Go invoice pages: the stay picker and the invoice form

Status: review. Executor: Haiku 5.5, one big PR mode (no branch, no push, no PR).

## Diff stat (step 1 commit 454cbc3e1)

8 files, 3567 insertions, all in §3:
go/internal/web/invoices/{countries.go, countries.json, guest.go, formctx.go, pages_new.go, new_test.go}, templates/{picker.tmpl, form.tmpl}.

## Commands (last lines)

- sha256sum of 8 files: all 8 match §2.
- `gofmt -l internal/web/invoices cmd/ubyhost-web`: no output.
- `go build ./...`: no output.
- `go vet ./internal/web/invoices/... ./cmd/...`: no output.
- `go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/...` (with UBYHOST_TEST_DATABASE_URL on PostgreSQL 16, port 5613): `ok` for both packages.
- `go test -v` on both packages: 115 `--- PASS`, 0 `--- FAIL`, 0 `--- SKIP`.
- `go test -v -run 'TestPicker|TestForm|TestBundled'`: 8 `--- PASS`.
- `python3 scripts/context_lint.py`: `context lint: OK` (only WARN lines about other open briefs).

## §7 acceptance

- [x] 8 sha256 values match
- [x] gofmt, build, vet silent
- [x] go test ok for both packages, no SKIP
- [x] 8 PASS for TestPicker/TestForm/TestBundled
- [x] step commits: `1425 step 1` (454cbc3e1); the report commit is `1425 step 3`
- [x] nothing pushed, no branch created

## Deviations

- Step 2: used port 5613 and data dir /var/tmp/pg1425 as the task message assigned, not the brief's 55432 and pg1420. Server stopped and directory deleted afterwards.
- Brief status line changed to `review`.

## Questions

None.

## Owner steps

None (nothing is switched on).
