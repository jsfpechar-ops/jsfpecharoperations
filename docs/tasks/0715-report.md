# 0715 report

Status: blocked

## Done
- Step 1 (commit 4c3353c): items 1, 2, 5. Header links in one flex row with no "·" separators; every Stav state is a pill (p-ok, p-warn, p-bad, p-n per the coordinator's mapping; p-n added to app2.css); month line items wrap as whole units.
- Step 2 (this commit): item 3 (`lang` argument on `_overview_calendar_rows`, fallback `calendar.kind_stay`); item 4 (.todo one column below 1024 px, check 8 updated); item 6 (reduced_motion="reduce" in both new_context calls in test_0710); removed the `main .pill` missing_ok entry in v2_mockup.py.
- Not done: step 3 (base.html key bump to 20261101-0715, static_versions --write, screenshots, PNG review, commit of screenshots).

## Test tails (3 files: test_0710, test_0520, test_dashboard_queue_copy; 0 skipped)
8 failed, 23 passed. Visible failures:
- test_0710 overview style: `main .pill color: app=rgb(138, 82, 0) mockup=rgb(22, 112, 68)` (also background-color and border-bottom-color). The first main .pill is now amber p-warn; the mockup's first pill is green. Unresolved.
- test_0710 overview at 320 px geometry: 7 findings, `past card edge by 3.0 px` on table, thead, tr, th, tbody, tr, td. Not investigated.
- test_0520 test_order_is_needs_you_month_calendar_today: `ValueError: substring not found` on `class="card cal"`. Also fails on base commit 51e193b (checked with git stash). Pre-existing.
- The other 4 failures were not captured; the budget ran out before I read the full list.

## Deviations
- not_registered (host.missing, a host action) is rendered as p-n, following "any state not listed → p-n". Owner should confirm; p-warn may be intended.
- Inner ui-badge sits inside the Stav pill; app2.css neutralises its background and border.
- v2_mockup.py has no browser context, so reduced_motion was added only in test_0710.
- Command budget reached at step 2; step 3 not started.

## Owner steps left
None. Orchestrator decides the pill-style mismatch (first main .pill) and the 320 px overflow before step 3.
