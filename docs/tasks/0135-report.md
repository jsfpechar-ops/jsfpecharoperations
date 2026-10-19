# 0135 report

Status: blocked

## Files changed
- App/app/templates/reservation_detail.html (steps 1 and 2)
- App/app/static/host.css (step 3: four dead .stay-jump rules removed)
- docs/design/catalog.json (step 3: template enforced; legacy list from lint, 47 tokens)
- App/tests/test_send_controls.py, test_wp28_ui_sweep.py, test_onboarding_followup_browser.py, test_wp28_geometry.py, test_design_stay_detail.py (step 4)

## Commits
- 6cb1a78 0135 step 1: head and CTA
- 23151f7 0135 step 2: mechanical class and role replacements
- 70afe21 0135 step 3: catalog enforces the detail template; drop stay-jump rules
- 0135 step 4: tests to v2 markup; new stay detail test

## Commands
- Step 1 compile: `ok` / `compiled`
- Step 2: `ok`
- Step 3: `python3 scripts/design_lint.py | tail -3` gives `design lint: OK`
- Step 4 pytest (8 files, no -x): `2 failed, 130 passed, 1 warning in 7.03s`

## Section 7
- [ ] not ticked: browser tests and screenshots (step 5) not run, blocked.
- [x] lint passes with reservation_detail.html enforced; host.css has no stay-jump rule.

## Deviations
- test_design_stay_detail.py: the page-level check for class="btn" and class="pill" is scoped to the `<main>` element. base.html's shared confirm and unsaved dialogs (after `</main>`) carry class="btn" and are not this page's markup. The template-level check is unchanged.
- test_wp28_ui_sweep.py line 143: `<details class="panel" id="file-by-hand">` changed to `class="ui-section"`, because step 2 renamed that element's class. The assertion is kept.
- Done: steps 1 to 4 (commits above). Left: step 4 fix in tests/test_overhaul.py, step 5, step 6.

## Blocked
- tests/test_overhaul.py:450 asserts `'class="panel stay-settings" id="stay-quick-edit"'`. Step 2 changed that element to `class="ui-section stay-settings"`. The file is not in brief section 3, so I stopped (section 8).
- tests/test_overhaul.py `test_demo_reset_removes_only_named_mock_data` fails with `sqlite3.IntegrityError: FOREIGN KEY constraint failed` at App/app/db.py:1375. Not in the brief's known-failure list. I did not check whether it predates this branch.

## Questions
- Owner: add tests/test_overhaul.py to section 3 for the one-line markup update, and say whether the demo-reset failure is known.

## Owner steps left
- None until the questions above are answered.
