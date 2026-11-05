# 0964 report (B06, connection states)

Status: blocked

Reason: the executor tool-call budget (25, brief section 8) was reached before the remaining checks ran and before any screenshot was opened. Test rows 2 to 6 and the context lint were not run. No screenshot was inspected, so no PASS/FAIL was given.

## Commits (branch codex/0964-b06-connection-states, base 7b0355c)

- 1106e97a 0964 step 1: templates, app2.css 0964 block, app2.css version key in base.html
- da7f3cf7 0964 step 2: four browser tests
- fd94de4e 0964 step 3: static_versions.json (app2.css entry only)
- 8a78b72f 0964 step 2 fix: test-only wait before an `is_visible` check in the calendar test

## Files changed (vs base)

- App/app/static/app2.css (+8)
- App/app/templates/_property_editor.html (+12)
- App/app/templates/_property_calendars.html (+7, -1)
- App/app/templates/base.html (version key)
- App/tests/test_host_property_controls_browser.py (+164)
- App/tests/static_versions.json (2 lines)

## Test results

- Row 1, `-k 0964` (new tests): first run failed in `test_0964_calendar_rows_keep_state_and_actions_with_a_long_url` at the `#feed-url-1` visibility check right after clicking the summary. The failing width varied between runs (768, 1280). Diagnostics after the failure showed the details open and the span with a non-empty box, so the cause was a timing race in the test, not the markup. Fix: wait for the span to be visible before the check (test only). Re-run: 4 passed, 0 skipped.
- Rows 2 to 6 (host row, smart-lock row, calendar row, static/design row, context lint): not run.

## Screenshots

Written to /tmp/ubyhost-b06 (untracked, nothing under docs/tasks changed): 0964-lock-off, lock-on, lock-unavailable, calendars-collapsed, calendars-open at 390, 768 and 1280 (15 files). None opened or described yet.

## Acceptance (section 7)

- Verified: the four new 0964 tests pass with 0 skipped.
- Not verified: the rest of section 7, the existing-test rows, the design-system checklist, and the screenshot review.

## Deviations and questions

- Test fix in section 3 file (one added line) after a timing failure; no product or markup change.
- Commit trailers: the Codex trailer requested for this batch plus the Claude attribution lines.

## Owner steps

None. Next executor session: run test rows 2 to 6 on this branch (with UBYHOST_DB unique per run), inspect the 15 screenshots, then set the status.
