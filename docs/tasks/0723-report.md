# 0723 report: Overview polish after 0722

Status: partial. One test still fails (see "Open").

## What changed in this session
- Phone gaps (`App/app/static/app2.css`, one rule inside `@media (max-width:1023px)` scoped to `body.v2`): `.ov-head` margin-bottom set to -22px, so the date line sits about 28 px above "What needs you" (was about 55 px). `details.needs-you-more.ov-section` margin-bottom set to 0 on phone.
- Asset key bumped to `20261101-0723c` in `App/app/templates/base.html`; manifest rewritten with `tests/test_static_versions.py --write`.
- `App/tests/test_dashboard_calendar_browser.py`: when `.ov-cal-more` is hidden (height 0), the gap check runs from the stats block bottom to the calendar top (0..44 px) and the alignment loop skips the zero-height box.
- `App/tests/test_needs_you_0240.py`: old-text asserts repointed to the short lines ("Police report failed", "Chybí údaje pro policii", "Guests not registered", "Police overdue"). The setup/paste test now patches `app.demo.is_demo_apartment` so it runs without a database.
- Screenshots: `docs/tasks/screenshots-0723/overview-390.png`, `overview-768.png`, `overview-1280.png` regenerated. Unrelated tracked PNGs restored; generated untracked PNGs removed.

## Earlier commits (brief steps 1-3, not re-verified in this session)
- Clear demo data hidden on phone (`ph-hide`), desktop quiet links in one flex row.
- Dead i18n keys removed: needs_you.stay.failed / overdue / ready / no_form / forms_missing, needs_you.setup, needs_you.paste.

## Gap measurements at 390 px
- Date line to first section heading: about 55 px before, about 28 px after.
- "Show 3 more" to "Today" heading: about 100 px before, about 60 px after (not at the 28 px target). The remaining space is not explained yet; the DOM shows the details margin is now 0 but the heading still lands about 30 px lower than expected. Needs another measurement pass.

## Test tails
- Set run (9 files): `86 passed, 1 failed`.
- `ruff check --select E9,F63,F7,F82,F401,F841`: All checks passed.
- `design_lint.py`: OK. `context_lint.py`: OK.

## Open
- `test_calendar_geometry_locales_and_screenshots` fails at `test_dashboard_calendar_browser.py:354`: `.cal-day-number` width 43 px, asserted >= 43.9 at phone widths. It also fails at HEAD, but at HEAD it stops earlier at the `.ov-cal-more` assert (the CI failure). This is a separate pre-existing issue from 0722, not changed here.
- `.ov-head` negative margin is a workaround that keeps the mockup-match test on `h2.sec margin-top: 28px` passing. The brief's intended approach (margin-top 0 on the first `h2.sec`) fails `test_0710_v2_mockup_match_browser` on the style-match check, so the mockup test would need a decision.
