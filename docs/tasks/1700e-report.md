# 1700e report: RÚIAN credit line on /legal

Status: review
Executor: Haiku 5.5, branch claude/beautiful-archimedes-lxhrit

## Files changed (git show --stat, steps 4 and 5)

- go/internal/web/public/page.go (import ruian, field Attribution, set for /legal)
- go/internal/web/public/templates/legal.tmpl (one credit panel before the disclaimer panel)
- go/internal/web/public/testdata/legal-cs.html, legal-en.html, legal-posthog.html, legal-no-dic-email.html (same panel, by sed)
- go/internal/web/public/legal_attribution_test.go (new, sidecar copy, sha256 OK)
- App/app/templates/legal.html (same panel)
- docs/tasks/1700e-ruian-attribution-line.md (Status line only)
- docs/tasks/1700e-report.md (this file)

## Commands (last lines)

- Step 0: all anchors and counts as stated (1, 1, 1, 1, 1 1 1 1, 0 0, 1).
- Step 1: `go/internal/web/public/legal_attribution_test.go: OK`
- Step 4: four lines, each `:1`.
- Step 6: gofmt, go build, go vet print nothing. `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public`. 0 FAIL, 0 SKIP. Named tests TestGoldenPages and TestLegalShowsRuianCreditOnce ran and passed. The PASS count across the wider -run was 82 (informational).
- Step 7: Python: CI (App/.venv does not exist).
- Step 8: no screenshot (see below). Non-visual check: /legal?lang=cs contains the credit once; the page has two quiet panels (credit, disclaimer).

## Section 7 acceptance

- [x] sha256sum of step 1: OK
- [x] gofmt, build, vet clean; Go tests ok, 0 FAIL, 0 SKIP
- [ ] Python tests: CI (no App/.venv)
- [x] Credit string count: legal-cs.html 1, legal.html 1; present only in the test file and the four goldens
- [x] Step commits: `1700e step 4` (342b6ce), `1700e step 5` (e3716b7); only §3 paths
- [ ] 390 px screenshot: not taken (see deviations)
- [x] Nothing pushed; no Caddy, compose, env or go/internal/ruian/ change

## Step 8 sentence

No browser screenshot: Playwright is not installed (no App/.venv, no Python playwright module). Non-visual check only: the credit line appears once on /legal?lang=cs, in its own quiet panel before the disclaimer panel. Visual check at 390 px is still open.

## Deviations

- Commit granularity: steps 2 and 3 have no separate commit; step 4 commits them together, as the brief's step 4 text says.
- Commit subjects are `1700e step k` with attribution trailers added.
- Screenshot not taken (Playwright unavailable); a new dependency to install it was not added.

## Questions

None.

## Owner steps left

- Reviewer or CI: run the Python parity test `App/tests/test_go_public_legal.py` (not run locally).
- Reviewer: take the 390 px screenshot of /legal?lang=cs once Playwright is available.
