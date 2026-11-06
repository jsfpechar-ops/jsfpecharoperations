# 0965 report
Status: review

Files: App/app/host_i18n.py (stay_fees.guest_pay.qr_note, en/cs/vi), App/tests/test_stay_fee_guest_pay_0897.py (assertion updated to new en text), docs/tasks/0965-iban-note-all-countries.md (Status: review).

Commands (tail -5):
- pytest test_stay_fee_guest_pay_0897.py test_static_versions.py -rs: 50 passed, 0 skipped
- ruff check --select E9,F63,F7,F82,F401,F841: All checks passed!
- grep "Czech and Slovak" App/app/*.py templates: only the new en string remains; no other host copy found.
- context_lint.py: see commit output (LINT_EXIT above)

Checklist 7: tests pass, 0 skipped, lint clean. Done.

Deviations: steps 1 to 3 done in one commit (small brief). Commit trailer uses Co-Authored-By Claude Haiku 5.5 per session attribution instead of the brief's Sonnet 5.5 line. No PR opened (owner instruction).
Questions: none.
Owner steps left: review and merge the branch via scripts/merge-pr-on-green.sh or a PR, as they decide.
