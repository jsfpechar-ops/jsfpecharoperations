# 1124 report: CI fixes for PR 923

Status: review (executor: Haiku 5.5)

## Steps

- Step 1 (schema 44 pins in test_db_postgres.py): already done. grep found no `44` pin.
- Step 2 (other test files): already done. Only unrelated hits (test_0199_phone_geometry_browser.py:126, test_feed_dns_pinning.py:348, test_funnel_ads_geometry_browser.py:156). Left alone.
- Step 3 (test_db_postgres.py): all 55 skipped (no UBYHOST_DATABASE_URL). CI test-postgres is the truth.
- Step 4 (claim copy): already done. The old sentence is not asserted on the claim page; line 227 (privacy page) is correct.
- Step 5 (test_claim_mail.py, test_claim_copy.py): 55 passed.
- Step 6 (docs/SES.md item 7): done, with both commands and both checks. context_lint OK. Note: `ubyhost-tls-required` appears on 3 lines (90, 91, 94), not the 5 hits the brief expected; the brief text itself has 3 mentions in the item.
- Step 7 (UX gate): done, see below.
- Step 8 (commit and push): see commit line below.
- Step 9 (PR body): not done. This session does not edit PR 923 (no PR edits in this brief's scope). Owner line for the PR body:
  `OWNER BEFORE MERGE: set UBYHOST_LEGAL_EFFECTIVE_DATE=2026-11-11 in the server .env. SES required TLS: done 2026-11-11.`

## Files changed

- docs/SES.md (step 7)
- docs/tasks/1124-pr923-ci-fixes.md (Status line only)
- docs/tasks/1124-report.md (this file)

No test file changed. No App/app/ change.

## Environment

- Created App/.venv, installed requirements-dev.txt and requirements.txt, then playwright==1.63.0 and chromium (rules.md section on Playwright). Local setup only, nothing committed.

## Commands (last lines)

- `.venv/bin/python -m pytest tests/test_claim_mail.py tests/test_claim_copy.py -q --tb=short -x` : `55 passed, 1 warning in 4.02s`
- `.venv/bin/python -m pytest tests/test_db_postgres.py -q --tb=short -x -rs` : `55 skipped in 0.25s`
- `python3 scripts/context_lint.py` : `context lint: OK`
- `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs` (with UBYHOST_REQUIRE_BROWSER=1) : `4 passed in 255.68s (0:04:15)`, 0 skipped

## UX gate

Settings > Account (/settings/account, switch `settings-guest-details-mail`): the harness produced `settings-account-390/768/1280.png`, but all three show the Settings index (Account, Security, Phone app, ...), not the Account page. The guest-details switch is not visible in any of them, so the switch was NOT checked visually.
- 390: Settings index, single column, no overflow, bottom nav clear.
- 768: Settings index, single column, no overflow.
- 1280: Settings index with sidebar, no overflow.
Harness gap: App/tests/test_layout_lint_browser.py has no `/settings/account` entry (grep `account` returns only lines 101 and 358, both unrelated). Harness not changed. Owner-visible gap for the reviewer: add the Account page to the harness in a follow-up brief.

## Deviations

- Screenshots were written to the session scratchpad, not /tmp/shots (session rule for temp files).
- App/.venv was created (brief expects it to exist).
- Playwright was installed per rules.md.

## Questions

- Settings > Account has no harness entry (see UX gate). Reviewer: approve the follow-up brief?
- Commit trailer: the brief and the user asked for `Co-Authored-By: Claude Opus 5.5`; the executor model is Haiku 5.5. Trailer used as the user specified.

## Owner steps left

1. Open the server `.env` and set `UBYHOST_LEGAL_EFFECTIVE_DATE=2026-11-11` before merging PR 923.
2. SES required TLS is done (2026-11-11); nothing to do.
