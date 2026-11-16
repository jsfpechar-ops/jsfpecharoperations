# A1c report: critical alert after 3 definite UbyPort failures

Status: blocked

Done (committed on feat/ubyport-three-failures-alert):
- Steps 1 to 4: reporting.py constant, streak, submission_transport_repeated alert, resolve (commits A1c step 1 to 4).
- Step 5: effects.go transportStreak, plus encoding/json import (A1c step 5).
- Step 6: submit.go streak, repeated alert and resolve (A1c step 6). gofmt clean, go vet ./internal/ubyport/ clean.
- Step 7: host_i18n.py (en, cs), host_vi_i18n.py, regenerated go/internal/hostweb/layout/i18n.json. go_host_i18n.py --check exits 0 (A1c step 7).
- Step 9: four Python tests appended to App/tests/test_submission_mail.py (A1c step 9). Committed as a failing state, see below.

Left:
- Step 9 test `test_three_faults_in_a_row_raise_the_repeated_alert` fails: after 3 fault transport errors the repeated alert is not open (assert None is not None, line 761). Teardown also errors: sqlite3 FOREIGN KEY failure in _purge (test_submission_mail.py:70 via db.py:1962). Root cause not found. Suspects: the streak param not persisted on open-row refresh (alerts.raise_alert, alerts.py:470-485), or the teardown purge order with the new alert.
- Step 10: Go tests (submit_test.go) not written. Go test run not done.
- Section 6 commands not run in full. Step 8 registries: only hits are go/internal/calendar/testdata/filing_watchdog_golden.json:5736 and filing_watchdog_run_golden.json:3580 (not changed).

Deviations:
- Branch name is feat/ubyport-three-failures-alert as the owner's instruction says, not task/a1c-three-failures-alert from the brief.
- Commit messages follow the brief ("A1c step k").

Owner steps left: none yet. Merge only after the review is green, with scripts/merge-pr-on-green.sh.
