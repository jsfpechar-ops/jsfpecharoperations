# 0858 report

Status: review

## Files changed
- App/tests/test_motion_browser.py (comment and path on the no-JS test; /stay-fees to /payments)

## Commands
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_motion_browser.py -q -rs --tb=short`
  - Before: 1 failed, 4 passed (`.ui-nav a[href="/reservations"]` timeout on /stay-fees)
  - After: 5 passed, 0 skipped

## Checks
- /payments extends host_page.html, which extends base.html and includes the old sidebar (.ui-nav) and renders details.ui-how. Stop condition not hit.
- No other /stay-fees references in the file.

## Deviations
- Not committed or pushed (per the owner's instruction for this run; the brief also says the orchestrator commits).

## Questions
- None.

## Owner steps left
- Orchestrator: review the diff, commit, and open the PR.
