# 0830F2 report: subscription, payments, share, consent (part F2)

Status: blocked (payments-consent: 6 reds need a test-side change; see Questions)

## Files changed
- `App/app/templates/billing_plan.html`: `v2 = true`, settings back header (`/settings`), `.settings-lane` wrapper, long sub-lines moved into help tips (`ui_tip`). Forms, POST targets, field names unchanged. Shell shim: the route passes an int in `apartments`, which the v2 shell reads with `| length` (500 without the shim). The page keeps the count in `apartment_count` and gives the shell a list. Python unchanged.
- `App/app/templates/payments.html`: v2, back header (`/settings`), lane, services empty line moved to a help tip. Flows, forms and JS hooks unchanged.
- `App/app/templates/payments_share.html`: v2, back header (`/payments`), lane, paid note moved to a help tip. The duplicate "back" text link is dropped (the header does that job).
- `App/app/templates/payments_consent.html`: v2, back header (`/payments`), lane. Legal copy stays visible.
- `App/app/static/app2.css`: block `/* 0830F2 (start) */ ... /* 0830F2 (end) */` placed before `/* 0830F sub-pages (end) */`. Covers service and step list cards, chip gaps, section spacing, 44 px radio and checkbox and help buttons below 1024 px.
- No test file changed. No commit. (A `git add -N` on billing_plan was reverted with `git reset`.)

## Test counts
Command: `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0830_airbnb_pages_browser.py -k "subscription or payments" -q --tb=short -rs -p no:cacheprovider`
- partF-subscription: 6 of 6 pass.
- partF-payments: 6 of 6 pass.
- partF-payments-consent: 0 of 6 pass. Skipped: 0.

## Old tests (16 files touching these templates or the shell)
Command: `... -m pytest <16 files> -q --tb=line -rfEs`. Result: 19 failed, 132 passed, 0 skipped.
- `test_design_shell_browser.py`: 5 failed. Includes `test_more_preserves_each_page_kind...[/payments?lang=en-390]` and `[-820]`, which use `/payments` as the old-shell page. They fail now that /payments is v2. Not rewritten. The other 3 are sidebar and tab-bar checks.
- `test_host_wide_geometry_browser.py` (6), `test_0705_v2_shell_browser.py` (1), `test_shell_lane_browser.py` (4), `test_design_guardrails_browser.py` (3): shell and sidebar checks. Not verified against a baseline (checkout is shared with the other parts, no stash used).

## Design lint
`python3 scripts/design_lint.py` (tail):
```
DESIGN App/app/templates/entities.html: T3 class not in catalog: settings-help-line
DESIGN App/app/templates/settings.html: T3 class not in catalog: settings-toggle-form
DESIGN App/app/templates/settings.html: T3 class not in catalog: settings-toggle-form
DESIGN App/app/templates/settings_archived.html: T3 class not in catalog: settings-help-line
DESIGN App/app/templates/guest_questions.html: T3 class not in catalog: f1-tip
design lint: FAIL
```

## Deviations
Done: templates, CSS block and both test runs above. Left: screenshots at 390 px (not taken), and the payments-consent reds.

## Questions
1. `/payments/consent` returns 404 unless `config.STRIPE_MODE` is `test` or `live` (`App/app/routes/payments.py`, `_off()`). The test sets neither, so the page is the generic 404 (no v2 shell). The test needs `monkeypatch.setattr(config, "STRIPE_MODE", "test")` for `partF-payments-consent`, the same way `partF-subscription` sets BILLING_ENABLED. Owner or the test owner decides; this executor does not edit the test file.
2. Optional cleanup: rename the route variable `apartments` to `apartment_count` in the billing route, then drop the shim in `billing_plan.html`. The shell's `apartments | length` check hits any page that passes an int under that name.

## Owner steps left
None.
