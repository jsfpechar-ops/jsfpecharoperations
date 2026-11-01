# 0709 report

Status: blocked (steps 1 to 5 done, tests failing; owner or coordinator decision needed)

## Commits (branch task/0709-v2-cleanup, not pushed)
- 0709 step 1: drop the global restyle (restores, deletes, app2 literals, JS line, dashboard-quiet class removed)
- 0709 step 2: catalog and design lint skip v2 templates
- 0709 step 3 and fix: base.html versions back to origin/main, dashboard-calendar keys, static versions written
- 0709 step 4 and fix: phone CSS, Stav pill, app2.css key bumped to 20261101-0709b
- 0709 report (this file)

## Commands and tails
- `.venv/bin/python -m pytest <brief §6 list> -q --tb=line -rfE`: 18 failed, 66 passed, 57 skipped (skips are `browser not required` in test_onboarding_wizard_browser.py; browser-only tests ran).
- `python3 scripts/design_lint.py`: FAIL, `DESIGN App/app/templates/dashboard.html: T1 style attribute` (lines 19 to 84 use inline style=; the brief skips only T3).
- `python3 scripts/context_lint.py`: OK.
- Acceptance diff of the restore list vs origin/main: empty.

## Failing tests (18)
- test_signed_in_chrome.py (7): sidebar footer, support line, one-h1 and what-needs-you checks. The restored test expects the origin/main sidebar and footer; the HEAD v2 shell does not render them. Also `getComputedStyle` TypeError in helpers.
- test_design_guardrails_browser.py (2), test_0284_states_browser.py (2), test_shell_lane_browser.py (4): same root cause (restored origin/main expectations vs v2 shell).
- test_a11y_guard_browser.py (3): focus-not-visible on dashboard 1280 (27 findings, e.g. `a#:UbyHost`, `button#:More actions`); under-rail on `a.skip-link` at 320 and 640 px. These are the a11y findings on `/` the brief asks to report.

## Screenshots (docs/tasks/screenshots-0709/)
- overview-cs-1280.png: clean.
- overview-cs-390.png: the Dnes table shows Host and Stav only (phone hiding works), the calendar scrolls inside its card, no sideways page scroll (test_0709 passes). Two issues: the account card (`Quiet Dashboard Review`, 2 nemovitosti) still shows in the top bar, so my `body.v2 .side .me` selector does not match the real markup; and the Stav cell of the Review Flat row is empty.

## Deviations
- Coordinator decision applied: workflow.css restored fully, `class="quiet"` in dashboard.html, dashboard-quiet and dashboard-today removed from catalog.json.
- Phone CSS prefixed with `body.v2`; the Dnes table hiding is scoped to `body.v2 .card > table` so other pages are untouched.
- Commit attribution: harness line (Claude Haiku 5.5), per coordinator decision 3.
- Step 3 and 4 each needed a fix commit: static versions refused a changed file under an old key.

## Questions
1. Design lint T1 on dashboard.html: move the inline styles to app2.css, or skip T1 for the v2 templates too?
2. The 18 failing tests: update the restored origin/main expectations for the v2 shell, or keep the old tests and change the v2 shell? This is outside the brief.
3. Account card on the 390 px top bar: which selector is the card? I can fix it in one pass once the markup is known.

## Owner steps left
None until the questions are answered.
