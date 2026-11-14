# 1423 report: Go invoice list, detail and PDF download

Status: review. One big PR mode: commits `1423 step 1` and `1423 step 3` on the current branch. Nothing pushed, no branch created, no PR opened.

## Files (diff stat: 9 files, 1160 insertions)

go/internal/web/invoices/: listfilter.go, pages_list.go, pages_detail.go, pdf_download.go, pages_test.go, pdf_download_test.go, templates/list.tmpl, templates/filter.tmpl, templates/detail.tmpl. All copied from the sidecars; no edits.

## Steps

- Step 0: reset to claude/happy-babbage-2zeeam; anchors and dependency check (`go/internal/web/invoices/store.go`) all matched.
- Step 1: 9 sha256 values matched §2.
- Step 2: disposable PostgreSQL 16 on port 5607, data under /var/tmp/pg1423. Stopped and removed afterwards.
- Step 3 commands, last lines:
  - `gofmt -l internal/web/invoices cmd/ubyhost-web`: no output.
  - `go build ./...`: no output.
  - `go vet ./internal/web/invoices/... ./cmd/...`: no output.
  - `go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/...`: `ok ...internal/web/invoices 16.326s`, `ok ...cmd/ubyhost-web 0.087s`.
  - `go test -v ... | grep -c -- '--- SKIP'`: 0.
  - `go test -v -run 'TestList|TestDetail|TestPDF|TestPyQuote' ... | grep -c '^--- PASS'`: 7.
  - `python3 scripts/context_lint.py`: `context lint: OK` (only the usual WARN lines about other briefs).

## Section 7

- [x] 9 sha256 values match
- [x] gofmt, build, vet silent
- [x] go test ok for both packages, 0 SKIP with PostgreSQL
- [x] 7 PASS lines for the named tests
- [x] UX gate: not applicable (pages not served)
- [x] step commits present, only §3 paths touched
- [x] nothing pushed, no branch created

## Deviations

- The PostgreSQL port was 5607 and the data directory /var/tmp/pg1423, per the task message (the brief's example used 55432 and pg1420).
- Ran as root; the server was started as user postgres, as the brief says.

## Questions

None.

## Owner steps left

None.
