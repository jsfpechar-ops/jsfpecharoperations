# 1220-fix-1 report

Status: review

## Files changed
- go/internal/pdf/doc.go (edit): stroke width kept for stroked rects; fixed CreationDate removed; `time` import removed (unused after); baseline comment replaced.
- go/internal/pdf/doc_test.go (new): TestStrokedSquareRectKeepsWidth.
- docs/tasks/1220-fix-1-report.md (new): this report.

## Commands
`cd go && gofmt -l internal/pdf && go vet ./internal/pdf && go test ./internal/pdf -count=1 2>&1 | tail -30`
Output:
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pdf	0.345s
```
(gofmt and go vet printed nothing.)

## Section 7
- [x] go test ./internal/pdf passes (includes TestLayoutMatchesPythonOps and the new test).
- [x] Diff against b9c5d85 limited to doc.go and doc_test.go (plus the brief and report).

## Deviations
- Steps 1 to 3 were committed together in one commit (ac0caa7, "1220-fix-1 step 1") instead of one commit per step.
- No PR opened and nothing pushed: the owner's instruction was not to push, and opening a PR needs a push.

## Questions
None.

## Owner steps left
- Push the branch and open the PR (`git push -u origin task/1220-go-invoice-pdf`), then review.
