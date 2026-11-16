# A1c report: critical alert after 3 definite UbyPort failures

Status: review

Done (feat/ubyport-three-failures-alert, PR draft):
- Steps 1 to 7: reporting.py streak, alert and resolve; effects.go transportStreak; submit.go streak, alert and resolve; i18n en, cs, vi; hostweb layout i18n.json regenerated (go_host_i18n.py --check exit 0).
- Step 9: four Python tests pass (tests/test_submission_mail.py -k a1c).
- Step 10: three Go tests pass (submit_test.go).
- Section 6: pytest 110 passed (8 files); go test ./internal/ubyport/... ./internal/hostweb/... ok; gofmt and go vet clean; context_lint OK.
- Postgres 5433 was down; started it. Tests run as role postgres (role pgtest does not exist).

Deviations:
- Step 2 fix: stored_params on a sqlite Row returns {} (no .get), so the streak read uses dict(previous).
- Step 9 fix: test seed tokens are mailnotifya1c1..4. The purge only removes permalink_token LIKE 'mailnotify%'; the a1c tokens left a legal_entity FK failure.
- Branch name is the owner's feat/ubyport-three-failures-alert, not the brief's task/a1c-...

Left:
- Step 8 registries: go/internal/calendar/testdata/filing_watchdog_golden.json:5736 and filing_watchdog_run_golden.json:3580 list submission_transport. No test named the new kind, so left unchanged.
- Help and guide: the PR template asks for it when host behaviour changes. The brief does not name it, so it is not done.

Owner steps: none until review. Merge with scripts/merge-pr-on-green.sh only after review.
