# 0830A report: shared test and CSS markers (part A)

Status: review (part A done; not committed)

## Files
- `App/app/static/app2.css`: six empty marker pairs appended (shared, B, C, D, E, F).
- `App/tests/test_0830_airbnb_pages_browser.py`: new, 90 cases (15 pages x 6 widths 320, 390, 768, 1024, 1280, 1440).

## Run (final, clean: 81 failed, 9 passed, 0 errors, 0 skipped)
Command: `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0830_airbnb_pages_browser.py -q --tb=line -rfEs -p no:cacheprovider | tail -30`
Two earlier runs were made: the first showed a teardown FK error (my seeded invoice and submission blocked the rich host's cleanup; fixed), the second only added the id tally. Neither changed the failing set.

Failing ids by part (of 6 widths each):
- partB: 6 of 12 (overview fails 6; menu passes 6)
- partC: 12 of 12
- partD: 12 of 12
- partE: 18 of 18
- partF: 33 of 36 (subscription passes at 1024, 1280, 1440)

Failing by width: 320: 14, 390: 14, 768: 14, 1024: 13, 1280: 13, 1440: 13.

## Selecting parts
- `-k partB`, `-k partC`, `-k partD`, `-k partE`, `-k partF`
- one page: `-k partF-payments`, one case: `-k "partB-overview-390"`

## Deviations
- The brief names `test_0800_v2_remaining_pages_browser.py` as the seed model, but it is not on this branch. It exists in git history (commit 35f3fefe). I reused its pattern and the 0710 fixtures (`base`, `dashboard_rich_host`, `_open_app`, `_placeholders`).
- Seeds: the rich host's property and stay, plus one invoice and one submission (rows deleted in the fixture teardown).
- Routes not parametrised: Leon setup, single guest question, payment share (each needs a route or id this part did not check). Invoice stay picker is covered by `partE-invoice-form`. `partF-cleaning-settings` uses `/cleaning/properties/{first_property}`.
- Observed in run 1: `partF-subscription` at 320, 390, 768 landed on `/settings`, not `/predplatne`. Check the route before fixing that page.
- The card check uses the generic `.card` selector as well as `.settings-value-card`, so wrapper cards may be flagged.
- Screenshots not taken (UBYHOST_SHOTS_0830 not set). `design_lint.py` not run.

Owner steps left: none. Parts B to F run next, in parallel.
