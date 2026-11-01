# 0722 report: compact phone Overview

Status: blocked (one test group still fails: 0710 overview at 320 and 390 px, `.card.need` height)

## Done
- `app2.css`: `body.v2 .ph-hide` (display none below 1024 px); phone-only rules for env banner, needs-you cards 3+, month line order; `.needs-you-actions .btn` min-height 44 px on phone. Key bumped to `20261101-0722c`, manifest written.
- `dashboard.html`: help `details`, quick links `p.ov-links`, onboarding banner and onboarding finish card hidden on phone (one-line finish strip kept). Needs-you shows 2 cards on phone, rest behind one "Show N more" toggle (CSS `nth-child`); desktop keeps 4. Problem line is bold, property and dates small.
- `_host_alerts.html`: PIN bubble hidden on the Overview at phone; stack hidden when only PIN lines remain.
- `_env_banner.html`: phone shows title only; explanation in a `details`.
- `needs_you.py` + `host_i18n.py` / `host_vi_i18n.py`: `needs_you.short.*` problem texts (en, cs, vi). The long explanations no longer show on the Overview (desktop too).
- `catalog.json`: new classes listed. design lint OK, context lint OK.
- Tests: `.needs-you` selector (never present in markup) replaced by `[data-needs-you-card]`; `.notification-stack:visible`; `.ui-btn` to `.btn`; copy keys in missing-banner test.

## Phone-only hides
help `details`; `p.ov-links` (Cleaning and Clear demo data); onboarding banner; onboarding finish card; PIN alert bubble; alert stack when only PIN; needs-you cards 3+ (toggle); env banner explanation.

## Test tail (last run: missing_banner, phone_browser, 0710)
```
.card.need height at 320 px: app=165.094px mockup=166.281px
.card.need height at 390 px: app=150px mockup=166.281px
2 failed, 26 passed in 35.93s
```
Earlier full run of the 14 listed files: 83 passed, 5 failed (all fixed above except 0710).

## Not done / left
- 0710 overview 390: card 16 px shorter than mockup (likely one line of the small text or the action row). 320: 1.2 px. Needs a design decision or a markup check.
- Screenshots in `docs/tasks/screenshots-0722/` not taken.
- Reachability not verified: Cleaning via Menu, onboarding via Menu.
- Other alert duplicates of needs-you not analysed (only PIN).
- Brief Status left at `todo`; no PR, no push.
