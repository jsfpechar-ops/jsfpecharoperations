# 0373 report (executor: Haiku 5.5)

Status: blocked

## Commits (branch task/0373-havel-corner, not pushed)
- e1673e6 0373 step 6: havel.intro greeting, dedupe server intro
- 0f8c155 0373 step 6b: drop expand icon and havel.open_page keys
- 812f2da 0373 step 7: MASTER 7.15 Havel panel
- step 9 (tests, screenshots): committed with this report

## Files changed
- App/app/templates/_havel_topics.html: greeting uses `t('havel.intro')`
- App/app/templates/_havel_thread.html: `data-havel-greeting` on the intro item; no-JS /havel skips the thread intro when topics are shown
- App/app/static/havel.js: swap() drops incoming `[data-havel-greeting]` in append mode when the thread already has one
- App/app/templates/_havel_panel.html: expand icon removed
- App/app/host_i18n.py, App/app/host_vi_i18n.py: `havel.open_page` removed
- docs/design/MASTER.md: 7.15 text
- App/tests/test_havel_panel.py, App/tests/test_havel_browser.py: new launcher, modeless, greeting, phone sheet and cs greeting tests
- docs/tasks/screenshots-0373/: fab-dashboard-390.png, panel-open-390.png, panel-open-cs-390.png, panel-open-1280.png (not viewed), panel-topic-1280.png, panel-answer-1280.png

## Test results
- Brief set, run 1: 213 passed, 3 failed (computer test: fab visible check raced the async close event; greeting test: composer missing; fixed with `expect(...).to_be_visible()` and 390 px width).
- Brief set, run 2 (last): 214 passed, 2 failed, 0 skipped reported.
  - `test_havel_page.py::test_the_seventh_message_starts_a_fresh_conversation`: "Let's start a fresh conversation." missing from the non-fragment POST page. Not diagnosed. Possibly caused by the thread template change (step 6), not confirmed.
  - `test_havel_browser.py::test_greeting_shows_once_after_a_reply`: passes alone (7 of 7 in panel+browser files), fails in the full run: `#havel-message` never appears. Suspect shared per-user Havel state from earlier tests in the same DB (limit state hides the form). Not confirmed.
- ruff (E9,F63,F7,F82,F401,F841): All checks passed
- design_lint: OK. context_lint: OK

## Deviations
- Step 9 browser test for the greeting was moved to 390 px: on 1280 the composer appears only after a topic, and the test needs it on the home screen.
- Screenshots of the other 0322/0332 folders were restored with git checkout.

## Owner steps left
- None. Next: fix the two failing tests above (question for the owner: is the 7th-message failure expected from the step 6 template change?).
