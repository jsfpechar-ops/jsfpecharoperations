# 0411 report

Status: done

## Files changed

- App/app/routes/admin.py: `stay_claim` computed once; `last_sent_at` query removed; `CLAIM_RESEND_ERRORS` map and `CLAIM_RESEND_FAILED`; demo-stay guard on the POST route; computed flash key replaced; stale `#guests` comment removed.
- App/app/host_i18n.py: `claim_resend_failed` (en, cs); `resend_help` fixed (en, cs).
- App/app/host_vi_i18n.py: `claim_resend_failed`; `resend_help` fixed.
- App/tests/test_claim_host_resend.py: new key-map test (2 tests, both pass).

## Steps

Steps 1 to 7 applied as written. Each anchor matched exactly once. Greps in §7 print nothing. `python3 scripts/context_lint.py`: OK.

## Tests (brief §6)

Command run from App/ with `--tb=no -rf`, without `-x`:

```
FAILED tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects
FAILED tests/test_host_i18n.py::test_a_signed_in_dashboard_keeps_vietnamese
FAILED tests/test_host_i18n.py::test_language_endpoint_accepts_vietnamese
3 failed, 97 passed, 2 warnings
```

All three fail with `sqlite3.OperationalError: no such table: apartment`. The same three fail on the base commit (checked with `git stash`), so this is not caused by this change. The test DB seems not to be initialised in this sandbox.

## Deviations

- Acceptance in §7 is not met: 3 failures in test_host_i18n.py, pre-existing on base. Not fixed (outside the brief).
- Commit message follows §9 plus the two trailers from the owner's instruction. The Co-Authored-By trailer says Opus 5.5; the executor running this brief is Haiku 5.5.
- Committed once at the end, not per step as executor.md asks, per the owner's instruction.

## Questions

- Is the test DB init step missing from this sandbox, or does test_host_i18n need a migration run first? Owner or orchestrator to confirm.

## Owner steps left

None from this brief. Push and merge are not done here.
