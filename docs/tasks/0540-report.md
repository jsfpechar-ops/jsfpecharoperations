# 0540 report
Status: blocked
Done: steps 1 to 5. Left: step 6 (old host-page assertions). Stopped at brief section 8 and addendum: the addendum's expectation for `/cleaning` does not match the new table.

Commits: 97d8d65 (step 1), f9c1220 (step 2), f284668 (step 3), 9666920 (step 4), ca1bd61 (step 5). Step 6 is not committed.

Uncommitted (working tree): App/tests/test_cleaning.py, lines 223-229. The 001234, &lt;script&gt; and script-not-in checks moved to GET /cleaning/properties/{home}?lang=en (per addendum). The 11:00/15:00 check is still on /cleaning and fails.

Tests:
- Set 1 (after the edit): 1 failed, 59 passed. Failing: tests/test_cleaning.py::test_readable_list_and_settings_escape_host_text_and_show_leading_zero_code, line 224, `assert "11:00" in response.text and "15:00" in response.text` on /cleaning.
- Set 2 (-x): 1 failed at tests/test_cleaning_browser.py:90, `.cleaning-card` count 0 (expected 3) on /cleaning?lang=en, 360 px. Host-page assertions in section 6 not yet updated.
- design_lint: OK.
- context_lint: OK (warnings only, unrelated to this change).

Cause of the 11:00/15:00 failure: the new table time cell shows startTime-endTime or checkoutTime-checkinTime per event, and the arrival cell shows checkinTime. The 11:00/15:00 values come from the property `*_hour` fields via cleaning._hour(), which the table does not render. Question for the orchestrator: move the 11:00/15:00 check to the settings page, or drop it?

git diff --stat origin/main (committed state, excluding the uncommitted test edit):
 App/app/cleaning_i18n.py | 13 ++-
 App/app/host_vi_i18n.py | 11 +++
 App/app/routes/cleaning.py | 21 ++++-
 App/app/templates/_cleaning_screen.html | 4 +-
 App/app/templates/_cleaning_table.html | 24 +++++
 App/tests/test_0540_cleaning_tables.py | 113 ++++++++++++++++++++++++

Assertions changed: test_cleaning.py::test_readable_list_and_settings_escape_host_text_and_show_leading_zero_code. Host-page checks moved to the settings URL (001234, &lt;script&gt;, script not in). The 11:00/15:00 check is still on /cleaning and fails; not resolved.

Deviations: step 6 not finished. The browser set has host-page `.cleaning-card` assertions still to update (test_cleaning_browser.py lines 90, 119-130, 447-482; test_design_guardrails_browser.py 420-423). Shared-view lines were not touched. Commit trailer uses Claude Opus 5.5 as the run note asks.

Owner steps left: decide the 11:00/15:00 question, then the orchestrator or a new run finishes step 6. No push, no PR.
