# Report 1382: Go CSRF multipart and Back quoting

Status: review

## Files changed

- go/internal/hostweb/gate.go (edit): `mime` import, `csrfMaxMultipart`, `csrfMultipartMemory`, `formToken` used by `CSRF`
- go/internal/hostweb/hostweb.go (edit): `redirect`, `starletteQuote`, `quoteSafe` (shared with `pyQuote`)
- go/internal/hostweb/hostweb_test.go (edit): six TestBack rows
- go/internal/hostweb/csrf_test.go (new): TestCSRFFormBodies (5 cases) and the multipart file-readable subtest
- docs/tasks/1382-csrf-multipart.md (edit): Status line only
- docs/tasks/1382-report.md (new): this report

## Commands (last 5 lines)

`cd go && gofmt -l internal/hostweb && go vet ./internal/hostweb/ && go test ./internal/hostweb/`
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb	(cached)
```
Fresh run: `go test -count=1 -run TestCSRFFormBodies -v ./internal/hostweb/` shows all 6 subtests PASS, last line `ok  	.../go/internal/hostweb	0.103s`.

`go build ./... && go test ./internal/... 2>&1 | grep -v '^ok'`
```
?   	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries	[no test files]
```
No failures in any package.

`sha256sum` on the four files: all four match brief step 4.

`python3 scripts/context_lint.py 2>&1 | tail -5`
```
next free: task 1383 | migration 0046
context lint: OK
```

## Acceptance (§7)

- [x] `go test ./internal/hostweb/` passes, including TestCSRFFormBodies (6 subtests)
- [x] TestBack passes with the six new rows; `go test ./internal/...` all ok
- [x] All four sha256 values match
- [x] `git diff --stat` shows only the §3 files

## Deviations

- Diff applied with `git apply` from a file in the scratchpad (extracted from brief lines 55-195). No content changed.
- Committed as one commit with the owner's message, not one commit per step as executor.md suggests.

## Questions

None.

## Owner steps left

None for this brief. Merge via the normal draft-PR route.
