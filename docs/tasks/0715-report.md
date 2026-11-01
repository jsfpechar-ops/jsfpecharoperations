# 0715 report

Status: blocked

## Done
Nothing changed in App/. Stopped at brief section 8 before step 1 (items 1, 2, 5), because item 2 has a Stav state with no clear pill tone.

## Stop reason (brief section 8)
Brief item 2 maps only waiting/incomplete (p-warn), failed/overdue (p-bad), reported/not_required (p-ok). The Overview Stav cell (App/app/templates/dashboard.html, lines 107-112, using progress_pill from App/app/templates/_components.html lines 75-122) also renders these states, which the brief does not map:
- ready, awaiting_verification (macro tone blue; labels ready_immediate, ready_scheduled, ready_manual, awaiting_verification). app2.css has only p-ok, p-warn, p-bad; there is no blue pill class.
- awaiting_guest/incomplete when automation_mode is not immediate (macro teal/amber, not a pill).
- is_demo preview (status.demo_preview, grey).

Owner or orchestrator must decide the tone for these before step 1 can be applied. Options: (a) add a p-info (blue) class to app2.css and map ready states to it; (b) map them to p-ok; (c) leave them as ui-badge and map only the three listed states.

## Pre-check facts (for the next executor)
- Item 3 label key exists in all three languages: calendar.kind_stay (en "Stay" host_i18n.py:7795, cs "Pobyt" host_i18n.py:7878, vi "Lượt lưu trú" host_vi_i18n.py:3368). The label is built in App/app/routes/admin.py:569 inside _overview_calendar_rows, which has no lang argument; the caller (around line 527) would need to pass one.
- Item 1 anchors: dashboard.html lines 56-58 (ov-links block, "·" spans at 57 and 58). CSS .ov-links at app2.css:126.
- Item 5 anchor: dashboard.html line 79 (data-dashboard-month).
- Item 4 anchor: app2.css line 73 (.todo one column below 767px; the brief wants below 1024px, so the media query must change).
- Item 6 anchor: test_0710_v2_mockup_match_browser.py lines 40 and 54 (new_context calls); v2_mockup.py missing_ok "main .pill" at line 51-53.
- Key bump: base.html line 21 (app2.css?v=20261101-0714b).

## Test tails
Not run (no code change).

## Deviations
Stopped at section 8, not at a failing test. No commit of code. This report is committed only.

## Questions
Which tone rule for ready and awaiting_verification states (see options above)?

## Owner steps left
None until the question is answered.
