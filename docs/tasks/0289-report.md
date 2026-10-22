# 0289 report

Status: review

## Files changed
- App/app/static/host2.css: min-width rule for td.col-name moved from the 950px block to a new 1100px @container block at the end of the file.
- App/app/templates/base.html: host2.css key 20261022-0288 to 20261022-0289.
- App/tests/static_versions.json: regenerated with --write (35 files).

## Commits (local, wip-0284, not pushed)
- 0d1c25c 0289 step 1
- 9ccb082 0289 step 2

## Commands
- pytest tests/test_design_guardrails_browser.py tests/test_0285_rows_browser.py tests/test_static_versions.py -rs: `15 passed, 1 warning in 89.70s`, no skips.
- python3 scripts/design_lint.py: `design lint: OK`.

## Acceptance (section 7)
- [x] Layout guard and test_0285 pass, 0 skipped.
- [x] host2.css key 20261022-0289; static_versions.json regenerated; design lint clean.

## Deviations
- No 390 px screenshot was taken for the changed host page (AGENTS rule 7). The brief does not name the page.

## Questions
- Which host page(s) should get the 390 px screenshot for rule 7?

## Owner steps left
- Push and open the PR when ready (not done here, per instructions).
