# 0540 report
Status: blocked
Done: steps 1 to 5. Left: step 6 (old host-page assertions). Stopped at brief section 8: an existing test that is not on the step 6 list now fails.

Commits: 97d8d65 (step 1), f9c1220 (step 2), f284668 (step 3), 9666920 (step 4), ca1bd61 (step 5).

Files changed: App/app/routes/cleaning.py, App/app/templates/_cleaning_table.html (new), App/app/templates/_cleaning_screen.html, App/app/cleaning_i18n.py, App/app/host_vi_i18n.py, App/tests/test_0540_cleaning_tables.py (new).

Tests:
- tests/test_0540_cleaning_tables.py: 5 passed.
- Set 1 without -x: 1 failed, 59 passed. Failing: tests/test_cleaning.py::test_readable_list_and_settings_escape_host_text_and_show_leading_zero_code at line 224, assert "001234" in GET /cleaning?lang=en. The new host table has no manual code or instructions (brief columns: Property, Time/Day, Next arrival, Status). Later asserts in that test (escaped script text, 11:00 and 15:00) were not reached.
- Set 2 (browser tests) and the lint commands: not run, stopped per section 8.

Assertions changed: none.

Owner decision needed: either keep the code and instructions off the host list (then that test's host-page assertions change, which the brief does not list), or show the code in the table.

Deviations: index() also passes sections to the page. An unreachable for-else fallback in _cleaning_table.html. Commit trailer uses Claude Haiku 5.5 (per the attribution reminder), not Opus as the run notes said. No push, no PR.

git diff --stat origin/main:
 App/app/cleaning_i18n.py                        |  13 ++-
 App/app/host_vi_i18n.py                         |  11 +++
 App/app/routes/cleaning.py                      |  21 ++++-
 App/app/templates/_cleaning_screen.html         |   4 +-
 App/app/templates/_cleaning_table.html          |  24 +++++
 App/tests/test_0540_cleaning_tables.py          | 113 ++++++++++++++++++++++++
 docs/tasks/0540-cleaning-tables.md              |  39 ++++++++
 docs/tasks/0541-cleaning-header-and-calendar.md |  38 ++++++++
 8 files changed, 258 insertions(+), 5 deletions(-)
