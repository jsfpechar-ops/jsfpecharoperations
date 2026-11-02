# 0717: v2 Overview keeps every feature the old Overview had
Status: todo
Depends on: 0715 | Base commit: claude/project-thread-50hyv5 | Branch: task/0717-v2-overview-parity
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
The v2 Overview (`App/app/templates/dashboard.html`) dropped things the old one showed. Restore them in the mockup's quiet style, so these tests pass. Prefer restoring the feature over changing a test; change a test only where section 2 says.

## 2. Context and decisions (orchestrator, 2026-11-01)
Failing tests (local run of the non-browser suite):
- Alerts: `test_p1_review.py::test_A_job_failed_alert_is_visible_to_owner`, `::test_A_control_owned_alert_renders` (and the "deadline watch" text check in the same file). Brief 0714 hid the `_host_alerts.html` stack on v2 pages. These alerts must stay visible. Decision: on v2 pages render the alert stack again, but only for alerts that do NOT already have a todo card (the stay-covered ones stay hidden), styled as compact `.card` notes in app2.css above "Potřebuje vás". Find the 0714 guard in `base.html` (`hide_alert_stack or v2`) and replace it with that rule (the route or template can pass the set of covered reservation ids; `needs_you.build()` already knows them). Then re-run `test_needs_you_dashboard_0241.py` (no duplicate) and the p1 tests.
- Page help: `test_page_help_0277.py::test_every_main_page_has_one_closed_help[en,cs,vi]` needs exactly one `data-how=` closed help on `/`. Restore the old Overview's closed help (copy its markup from `git show origin/main:App/app/templates/dashboard.html`) as a quiet `<details data-how>` placed where the head's "How does this work?" link is; remove that link so the help lives in one place (rule 9).
- `test_onboarding.py::test_finished_onboarding_shows_guest_link_and_pin_handoff`: restore the old Overview's guest link + PIN handoff block (copy from origin/main dashboard.html) as one quiet card under the todo cards, shown under the same condition.
- `test_deadline_after_reporting.py` (2): a reported stay past its deadline shows no overdue; a stay filed late reads "late". Check the Stav mapping from brief 0715: filed state must win over overdue (order the checks: reported/filed first, then failed, then overdue). Keep the deadline_badge text.
- `test_0375_needs_you_and_open.py::test_needs_you_template_uses_icon_and_primary_only_on_first_line`: the first todo card's button is the primary coral `.btn`; the others are `.btn ghost sm`. Each card has the icon box. Fix the template if not so.
- `test_dashboard_missing_banner.py::test_lines_past_the_fifth_wait_behind_show_more`: the test expects items past the fifth behind "show more"; v2 shows 4 then `<details>`. Keep 4 (mockup) and update the test's number to 4, stating the 0706 reason in a comment.
- `test_design_dashboard.py` (2): `test_dashboard_with_a_property_has_the_v2_header_one_primary_and_refresh_hooks` and `test_no_raw_style_or_pill_in_the_dashboard_template`. Read both. Exactly one primary coral `.btn` on the page (todo first-card primary counts? if the test says one primary, make the head "Přidat pobyt" the only coral one and all todo buttons ghost, and update test_0375 accordingly—pick whichever the two tests agree on and say so). The "raw pill" rule: if it forbids literal `pill` classes in dashboard.html, move the Stav pill mapping into a macro in `_components.html` named `v2_status_pill(...)` and call it.
- `test_host_language.py::test_the_setup_steps_a_new_czech_host_reads_are_czech`: find which English string appears on the Czech `/` and translate it via the existing i18n keys.
- The Czech-language failure is "no onboarding banner on /": restore the old Overview's onboarding/setup banner (copy from origin/main dashboard.html) for hosts who have not finished setup, as one quiet card above the todo cards.
- `test_0252_touch_sweep_browser.py` fails for `/` at phone390 and ipad1024: run it, read the findings (tap targets/overlap) and fix in app2.css.
- `test_endtoend.py::test_08_dashboard_shows_the_stay_as_awaiting_the_guest`: the v2 Overview lists only today's stays; assert the stay on `/reservations` instead (keep the awaiting-guest check).
- `test_demo_seed.py::test_seed_imports_stays_without_fetching_the_calendar` and `test_reporting_help_0097.py::...geometry_and_tips_in_the_browser`: run each; if they also fail on `origin/main` (check in a temporary `git worktree add /tmp/wtmain origin/main`), note it and leave them; otherwise fix.
- Ignore other `test_endtoend.py` failures if they fail the same way on origin/main (environment); report them.
- Bump the app2.css key in `base.html` to `20261101-0717` only if you changed app2.css; then `--write` the manifest.

## 3. Files
`App/app/templates/dashboard.html`, `App/app/templates/base.html`, `App/app/templates/_components.html` (new macro only), `App/app/routes/admin.py` (covered-ids only), `App/app/static/app2.css`, `App/tests/static_versions.json`, the named tests (only where section 2 allows), report `docs/tasks/0717-report.md`.

## 4. Steps
Test by test; run only that file; commit every 2-3 fixes with explicit paths.

## 5. Do not touch
`_shell_v2.html` (brief 0716 runs in parallel), `app.js`, `_shell_sidebar.html`.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_p1_review.py tests/test_needs_you_dashboard_0241.py tests/test_page_help_0277.py tests/test_onboarding.py tests/test_deadline_after_reporting.py tests/test_0375_needs_you_and_open.py tests/test_dashboard_missing_banner.py tests/test_design_dashboard.py tests/test_host_language.py tests/test_0520_overview_today.py tests/test_dashboard_queue_copy.py tests/test_0252_touch_sweep_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped). Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All listed tests pass, 0 skipped; 0710 still green.

## 8. Stop and ask
Stop if an alert kind would end up shown nowhere, or if restoring a block needs more than ~20 lines in admin.py.

## 9. Report
`docs/tasks/0717-report.md`: status, test tails, change per test, deviations.
