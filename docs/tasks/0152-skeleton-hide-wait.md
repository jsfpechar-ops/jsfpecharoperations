# 0152: skeleton test waits for the minimum-visible hide, then finish 0151

Status: todo
Depends on: 0151 steps 1-3 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

## 1. Objective

0151 stopped at step 4 on `tests/test_onboarding_wizard_browser.py:1518` (`assert skeleton.is_hidden()`), twice. Cause (orchestrator): `skeleton.js` line 43 keeps the skeleton up for `MIN_VISIBLE_MS` (400) after it shows, so `hide()` defers the hide by up to 400 ms and the test asserts at once. The test must wait for the hide, with a bound. The assertion (the skeleton does hide) stays.

## 2. Context

Anchor A, `App/tests/test_onboarding_wizard_browser.py` lines 1517-1518:
```
            page.evaluate("window.ubyhostSkeleton.hide()")
            assert skeleton.is_hidden()
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_onboarding_wizard_browser.py | edit | Anchor A |
| docs/tasks/0151-report.md | edit | final status |

## 4. Steps

1. Replace Anchor A with:
```
            page.evaluate("window.ubyhostSkeleton.hide()")
            skeleton.wait_for(state="hidden", timeout=2000)  # skeleton.js MIN_VISIBLE_MS defers the hide
            assert skeleton.is_hidden()
```
   Run from `App/`: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py -k phone_guest_sharing_and_clear_setup_actions -q --tb=short 2>&1 | tail -8`. Expected: pass. Ruff on the file with `--select E9,F63,F7,F82,F401,F841`. Commit `0152 step 1` with `git add App/tests/test_onboarding_wizard_browser.py`.
2. Do 0151 step 4 exactly as written in `docs/tasks/0151-guest-browser-ci-fix.md` (the eight-file run and its capture steps). Expected: fully green, 0 skipped. Restore tracked evidence folders with `git checkout -- <folder>` after captures.
3. Do 0151 step 5 exactly as written (by-eye review, known-issues row, report). In the known-issues row, note the skeleton race is fixed in the test by 0152. Set `docs/tasks/0151-report.md` Status to review or blocked. Commit `0151 report` with explicit `git add` of the files that step names.

## 5. Do not touch

Everything else. No push.

## 6. Commands

As in the steps. Known local failures you may ignore: test_host_i18n language endpoint run alone, test_property_navigation_browser.py, the test_host_properties_navigation fit test, test_host_fit_browser, test_host_invoice_items_browser, test_host_property_controls_browser, test_host_ux_acceptance rail-cards test, test_host_list_page_layout_browser properties [40,42].

## 7. Acceptance

- [ ] Step 2 passes with 0 skipped.
- [ ] Step 3 report written.

## 8. Stop and ask

Stop if a test fails twice. Report the assertion verbatim.

## 9. Report

As in step 3.
