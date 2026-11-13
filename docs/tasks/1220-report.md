# 1220 report: Go invoice PDF package

Status: review

## Files changed (vs a83df54, excluding the brief commit)

- go/go.mod, go/go.sum (gopdf v0.38.4, gofpdi, pkg/errors; gopdf moved to direct by tidy)
- go/internal/pdf/: doc.go, metrics.go, spayd.go, labels.go, invoice.go, invoice_test.go
- go/internal/pdf/fonts/ (DejaVuSans.ttf, DejaVuSans-Bold.ttf, LICENSE-DejaVu.txt), assets/ubyhost-mark-192.png, testdata/invoice_pdf_golden.json
- App/scripts/invoice_pdf_golden.py
- docs/tasks/1220-report.md

## Commits

- 8541b84 1220 step 1 (dependency)
- b1d16ee 1220 step 2 (fonts, logo)
- 17e1832 1220 step 3 (Go code, go mod tidy)
- 66cd095 1220 step 4 (golden script)
- step 5: this report

## Commands (last lines)

- Step 0 checksums: nine lines `OK`.
- Step 3 `go test ./internal/pdf -count=1 -v`: PASS for TestLayoutMatchesPythonOps, TestRenderParsesAndIsDeterministic, TestMoneyAndWidths, TestPreviewWatermarkIsTransparent; `ok ... internal/pdf 0.341s`.
- Step 4: `wrote .../invoice_pdf_golden.json`; testdata unchanged; sha256 prefix `5f0306f83f92`.
- §6 `gofmt`, `go vet ./internal/pdf`, `go build ./...`: silent.
- §6 `go test ./internal/pdf -count=1`: `ok ... internal/pdf 0.372s`.
- §6 golden cases: `11`.
- §6 `context_lint.py`: `context lint: OK` (WARN lines are pre-existing, about other briefs and App/ commits, not this change).

## §7 acceptance

- [x] Eleven golden cases pass.
- [x] go build and go vet clean; gofmt silent.
- [x] Determinism and PDF parse tests pass (TestRenderParsesAndIsDeterministic).
- [x] git diff lists only §3 files.
- [x] Golden script reproduces the committed JSON.

## Deviations

- Not pushed and no PR opened, per the executor instructions ("Do not push").
- Step 0 `git status` showed untracked `.claude/worktrees/` (the other agent's worktree), so it was not empty. Not touched.
- Step 4 created App/.venv (git-ignored, not committed).

## Questions

None.

## Owner steps left

1. Coordinator adds the decision line for github.com/signintech/gopdf v0.38.4 before the PR is marked ready.
2. Push the branch and open the draft PR (not done by the executor).
