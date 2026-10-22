# 0271: Browser click-throughs follow the story order

Status: todo
Depends on: 0270 | Base commit: 48c21b3 + 0270 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

0270 reordered the wizard. Seven Playwright tests still click through the old order. Rewrite each click-through to the new order, keeping every assertion, check and screenshot; only the order of the blocks and the expected next URL change.

## 2. Context

New order (0270): property → calendar → police → automation → stay_fee → door_lock (skipped automatically when no lock is available) → guest_link → try_it → done. Skipping the test run (`try_it`) is the last answer, so it finishes setup and lands on `/setup/done`.

The helper `walk_to(client, apartment_id, target)` in `App/tests/wizard_walk.py` (from 0270) answers steps in order with the test client (police: wait, automation: manual, door lock: none). Use it wherever a test used client posts to reach a step.

Each test below is a sequence of blocks. A block starts at a `page.wait_for_url("**/setup/<step>**")` (or `page.goto(…/setup/<step>…)`) and ends at the click that leaves that step. Move whole blocks; do not rewrite their insides except the `wait_for_url` target after the click.

Run Playwright tests from `App/` with:
`UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pwb .venv/bin/python -m pytest <file>::<test> -q --tb=short -rs -x -p no:cacheprovider 2>&1 | tail -30` (0 skipped). Tests write screenshots to `docs/tasks/0102-evidence/`; restore them before each commit: `git checkout -- ../docs/tasks/0102-evidence && git clean -fdq ../docs/tasks/0102-evidence`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_onboarding_wizard_browser.py | edit | 6 click-throughs |
| App/tests/test_onboarding_followup_browser.py | edit | 3 marks |

No other file may change.

## 4. Steps

**Step 1. `test_wizard_journey_and_geometry`.** New block order after `page.goto(f"{base}/calendar?lang={lang}")` and its shot/assert:
1. calendar skip click → `wait_for_url("**/setup/police**")`; then the police block (shot `04-police`, wait-button assert, the five `page.fill`, the `police-form` click) → `wait_for_url("**/setup/automation**")`;
2. automation block (shot `06-automation`, `automation-form` click) → `wait_for_url("**/setup/stay_fee**")`;
3. stay fee block (shot `05-stay-fee`, skip click) → `wait_for_url("**/setup/door_lock**")`, then `page.locator('button[data-lock-choice="no"]').click()` → `wait_for_url("**/setup/guest_link**")`. If door_lock is not available in this test (the click times out), instead expect guest_link right after stay fee and say so in Deviations;
4. guest link block (shot `02-guest-link`, the two asserts, `button[value='done']` click) → `wait_for_url("**/setup/try_it**")`;
5. try_it block (shot `03-try-it`, skip click) → `wait_for_url("**/setup/done**")`, shot `07-done` and the done-title assert.

Run it. Commit `0271 step 1`.

**Step 2. `test_review_fixes_in_the_browser`.** Replace the three `client.post(base, …)` lines before the browser with:

```
    assert walk_to(client, flat["id"], "try_it") == "try_it"
    client.post(base, data={"step": "try_it", "action": "demo"}, follow_redirects=False)
```

In the browser: change `page.goto(f"{base_url}{base}/guest_link?lang=en")` to `page.goto(f"{base_url}{base}/police?lang=en")` (Back from police opens the calendar; the rest of that block stays). After the try_it shot `10-try-it-open-en-1280.png`, delete the skip click and its `page.wait_for_url("**/setup/police**")`, and put `page.goto(f"{base_url}{base}/police?lang=en")` in their place (skipping the test run would finish setup and the later Exit button needs an unfinished wizard). Everything after stays. Run, commit.

**Step 3. `test_full_wizard_clickthrough_keeps_police_and_guest_settings`.** Police is already stored. New sequence after `page.goto(f"{base}/calendar?lang=en")`: calendar skip → `**/setup/automation**`, `automation-form` click → `**/setup/stay_fee**`, stay fee skip → `**/setup/door_lock**`, lock "no" → `**/setup/guest_link**`, `button[value='done']` → `**/setup/try_it**`, try_it skip → `**/setup/done**`. Update the comment to `# Police details are already stored, so the wizard goes on to when to report.` and move it above the first wait. Same door-lock fallback as step 1. Run, commit.

**Step 4. `test_wizard_round_screenshots`.** Replace the two `host["client"].post(f"/apartments/{tried['id']}/setup", …)` calls with `walk_to(host["client"], tried["id"], "try_it")`. Change the `page.wait_for_url("**/setup/police**")` after the try_it skip to `page.wait_for_url("**/setup/done**")`. Run, commit.

**Step 5. `test_deferred_police_journey_without_javascript`.** New block order after the calendar goto, shot `18-calendar` and `check_controls()`:
1. calendar skip → `**/setup/police**`, then the police block exactly as it is (wait/save geometry asserts, notes assert, shot `20-police`), `wait.click()` → `**/setup/automation**`, `check_controls()`;
2. automation: `input[value="manual"]` check, `automation-form` click → `**/setup/stay_fee**`, `check_controls()`;
3. stay fee skip → `**/setup/guest_link**` (no lock in this test; if the page lands on door_lock instead, click `button[data-lock-choice="no"]` first and say so), `check_controls()`;
4. `button[value=done]` → `**/setup/try_it**`, `check_controls()`, shot `19-try-it`;
5. try_it skip (`.setup-wizard-skip button`) → `**/setup/done**`; the rest (reload, finished, waiting checklist, shot 21, police link) stays.

Run for one parameter first (`-k "390-en"`), then all. Commit.

**Step 6. `test_wizard_polish_and_overview_cards`.** After the calendar-platform part ends with the `calendar-add` click:
1. `page.wait_for_url("**/setup/police**")` and the feed label assert; `page.locator(".setup-wizard-wait").click()` → `**/setup/automation**`;
2. `input[value="manual"]` check, `automation-form` click → `**/setup/stay_fee**`; the fee typography block (assert + overflow + shot `24-fee-intro`); stay fee skip → `**/setup/guest_link**` (door-lock fallback as step 5);
3. `button[value=done]` → `**/setup/try_it**`; the whole demo walkthrough block (demo property asserts, shots 35, 34, 23, reload, skip/check-again asserts, `guest_page.close()`) unchanged;
4. try_it skip → `**/setup/done**`, then the done-page asserts unchanged (badge counts stay 4 done and 3 neutral).

Run one parameter, then all. Commit.

**Step 7. `test_phone_guest_sharing_and_clear_setup_actions`.** 0270 already replaced its calendar post with `walk_to(…, "guest_link")`. Just run it; if it still fails, read the failing line and fix only the step order there.

**Step 8. `tests/test_onboarding_followup_browser.py` `test_current_property_name_demo_label_and_distinct_setup_status`.** After the line `    property_setup.mark(apartment_id, "try_it", "skipped")` add:

```
    # 0270: steps before the guest link are answered too, so it can be opened.
    property_setup.mark(apartment_id, "automation", "done")
    property_setup.mark(apartment_id, "stay_fee", "skipped")
    property_setup.mark(apartment_id, "door_lock", "not_needed")
```

Run it, commit.

## 5. Do not touch

App code, templates, other tests, `wizard_walk.py`. Never delete, skip or loosen an assertion; never change a screenshot name. Never push.

## 6. Commands

From `App/`, at the end:

`UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pwb .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_onboarding_followup_browser.py tests/test_lock_question_0234.py -q --tb=line -rs -p no:cacheprovider 2>&1 | tail -30` → 0 failed, 0 skipped (it takes about 10 minutes; use a 900000 ms timeout). Then restore the evidence folder.

## 7. Acceptance

- [ ] All tests in the three files pass with 0 skipped.
- [ ] Every screenshot name and assertion kept.

## 8. Stop and ask

Per TEMPLATE. A test that fails twice for a reason other than step order: stop and report it.

## 9. Report

`docs/tasks/0271-report.md` (600 tokens max), `Status: review`, commits `0271 step k`. Do not push.
