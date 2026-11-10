# 1080 report

Status: blocked
Branch: claude/ecstatic-feynman-6iy30u (brief's branch name ignored, per owner)

## Files changed (committed)
- App/app/auth.py: `device_cookie_valid(request)` added (step 1, commit 525ffa3).
- App/app/routes/admin_accounts.py: `skip_turnstile` in `_login_page_context`; forced `False` in `again` on `auth.error.turnstile` (step 2, commit 017e519).
- App/app/templates/login.html: e-mail widget and script conditions changed (step 3, commit aa57764).

## Uncommitted (left in working tree)
- App/tests/test_login_session_persistence.py: 4 new tests appended (step 4). Not committed: one fails.

## Commands (section 6)
- Import checks (step 1, 2): no output, exit 0.
- Cmd 1 (auth set, -x): last lines:
  `E   assert 'cf-turnstile' in '<!doctype html> ...'`
  `tests/test_login_session_persistence.py:196: in test_login_page_shows_the_widget_without_a_device_cookie`
  `1 failed, 13 passed in 6.60s`
- Cmd 2 (host tests): not run.
- Cmd 3 (UX gate): not run.
- Context lint: not run.

## Section 7 ticked
None. Not reached.

## Deviations
- Done: steps 1 to 3. Left: step 4 (fix one failing test, then the others), step 5 (decisions line), section 6 commands 1 to 3 and lint, screenshots, report PR text.
- Step 4 blocker: `App/app/templating.py` line 607 sets `turnstile_site_key` at import time from `config.TURNSTILE_ENABLED`, so `monkeypatch.setattr(config, "TURNSTILE_SITE_KEY", ...)` does not reach the page. The test must patch the template global instead (not yet found which name the env uses).
- Step 4 test 1 used a fresh client with the cookie, not a logout first (brief wording); equivalent for `/login`.
- Brief step 4 said the file already patches `TURNSTILE_SITE_KEY`; it does not.
- Security hook warned that the Turnstile `api.js` script tag has no SRI. Not changed: the brief says the tag stays as is, and Cloudflare's versioned api.js is not pinnable by hash. Reviewer to decide.
- Owner steps (Cloudflare dashboard) not done, as instructed.

## Questions
1. OK to patch the template global in the test (test-only change), or should the test read `config.TURNSTILE_ENABLED` at import differently?
2. Confirm SRI decision for the Turnstile script tag.

## Owner steps left
- Cloudflare dashboard steps in the brief (not done by executor).
