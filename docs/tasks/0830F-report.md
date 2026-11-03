# 0830F report: sub-pages (part F)

Status: blocked (checkpoint: test fixed and diagnosed; templates not started)

## Files changed
- `App/tests/test_0830_airbnb_pages_browser.py`: `test_0830_airbnb_page` takes `monkeypatch` and sets `config.BILLING_ENABLED = True` for `partF-subscription` only.
- No template changed. No `app2.css` change (the `0830F sub-pages` markers are still empty).

## Subscription 320/390/768 on /settings: cause
`/predplatne` (`App/app/routes/billing.py`, `plan_page`) redirects to `/settings` when `billing.enabled()` is false, which is `config.BILLING_ENABLED`. The test never enabled it, so it landed on `/settings`. Other billing tests set it the same way (`tests/test_0416_plan_page_browser.py:31`). This was a test problem; the page itself is fine.

## Test counts (`-k partF`, after the fix)
Command: `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0830_airbnb_pages_browser.py -k partF -q --tb=line -rs -p no:cacheprovider`
Result: 36 failed, 0 passed, 0 skipped (54 deselected).
- Before the fix, subscription passed at 1024, 1280 and 1440 only because it was the `/settings` page. Now all six subscription widths fail on the real `/predplatne` page.
- Sample reasons (partF-subscription-390): not on v2 shell; `.airbnb-back` missing; pills/tabs not right; h1 8 px from a neighbour; fine print of 107 characters outside a help body.

## Not done (left for the next run)
Templates, in this order (all still plain `host_page.html` without `{% set v2 = true %}` except billing/payments, which are not v2):
1. `guest_questions.html`, `guest_question.html`: set `v2 = true`, back header, index rows or cards for questions.
2. `leon_settings.html`, `leon_setup/_layout.html`, `cards.html`, `done.html`, `import.html`, `switch_on.html`, `try.html`.
3. `cleaning_settings.html`.
4. `billing_plan.html`, `payments.html`, `payments_share.html`, `payments_consent.html`: look only; POST targets and forms unchanged.
5. Port the old CSS these pages need into the `/* 0830F sub-pages */` block in `App/app/static/app2.css`.
6. Then run `-k partF` plus the old tests that touch these templates (`grep -l "guest_question\|leon\|cleaning/properties\|predplatne\|payments" App/tests/*.py`). Browser tests need 0 skipped.

Note: the `partials/settings_*.html` set exists (back header, index row, pills, value card, toggle row); reuse it.

## Deviations
Done: steps 1 (test fix and diagnosis). Left: templates and CSS (steps 2 to 6 above).
Owner steps left: none.
