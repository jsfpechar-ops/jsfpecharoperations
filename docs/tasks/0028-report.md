# 0028 report: guest door-code e-mail gets its deadline again

Status: review
Branch: `task/0024-door-code-immediate-handover` (base `06585a7`), PR #326.

## Steps

1. Done. `git pull` on the branch (already at `06585a7`, nothing new).
2. Done. Import in `App/tests/test_door_code_handover.py` now includes `mail`.
3. Done. Added `test_the_guest_door_code_mail_is_queued_with_the_deadline` at the end of that file.
4. Done. Ran before the fix: `1 failed, 7 passed`, failure `the guest door-code mail was not queued`, as the brief expects. Output below.
5. Done. `_send_code_mail` passes `first_use_by=shown["first_use_by"]`.
6. Skipped. `docs/tasks/0024-door-code-immediate-handover.md` is not on this branch (it lives on `claude/charming-feynman-k7oear`), so there was no status line to change.
7. Done. Ran §6, committed, pushed (see below).

## Root cause

`send_code_mail` catches every exception and logs `door_code_mail_failed`. The traceback in the log was:

```
TypeError: build_door_code() missing 1 required keyword-only argument: 'first_use_by'
```

No test ran the full path from a made code to a queued guest mail, so nothing failed.

## Commands

Before the fix, `.venv/bin/python -m pytest tests/test_door_code_handover.py -q`:

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_door_code_handover.py::test_the_guest_door_code_mail_is_queued_with_the_deadline
1 failed, 7 passed, 1 warning in 0.28s
```

After the fix, `.venv/bin/python -m pytest tests/test_door_code_handover.py tests/test_door_codes_safeguards.py tests/test_guest_mail.py -q`:

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
72 passed, 1 warning in 0.92s
```

`.venv/bin/python -m pytest tests -q` (last lines):

```
FAILED tests/test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses
FAILED tests/test_feed_url_ssrf.py::test_redirects_are_revalidated_not_followed_blindly
FAILED tests/test_feed_url_ssrf.py::test_a_redirect_that_drops_https_is_refused
FAILED tests/test_feed_url_ssrf.py::test_allows_public_https_calendar - app.f...
4 failed, 2934 passed, 7 warnings in 320.12s (0:05:20)
```

The four failures are the DNS tests from brief 0023 §2.

`python3 scripts/context_lint.py` (last line): `context lint: OK`

## Section 7

- [x] Step 4 output shows the new test failing before the fix.
- [x] §6 passes after it (72 targeted; full suite has only the four DNS failures).
- [x] `grep -n 'first_use_by=shown' App/app/door_codes.py` prints one line (line 221).
- [x] `git diff --stat 06585a7` lists only §3 files: `App/app/door_codes.py` and `App/tests/test_door_code_handover.py`, plus this report.

## Deviations

None, apart from step 6 (skipped, see above).

## Questions

None.

## Owner steps left

1. Open a PR for `task/0024-door-code-immediate-handover` into `main` on GitHub (PR #326 already exists for this branch; this push updates it). Wait for the checks to go green.
2. Tell the orchestrator. It re-checks, then merge with `scripts/merge-pr-on-green.sh 326`.
