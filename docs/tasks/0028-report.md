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

## Second run of this brief: stopped at step 2

The brief was run again on the same branch. §8 stop condition hit at step 2: anchor E2 is not found exactly once. The import it names is already in the file, because the first run applied step 2 in `76cef9f`. Anchor E1 is also already replaced (the `first_use_by=shown["first_use_by"]` line is at `App/app/door_codes.py:221`). No code was changed in this run.

Steps:

1. Done. Fetched the brief from `origin/claude/charming-feynman-k7oear` and checked it out. Compared it with the copy I ran before: identical. `git pull` on `task/0024-door-code-immediate-handover`: already up to date at `76cef9f`.
2. Stopped (§8). Anchor E2 (`from app import config, db, door_codes, mail_notify, ttlock`) found 0 times in `App/tests/test_door_code_handover.py`. The applied form (with `mail`) is present once.
3. Skipped (not reached, stop at step 2). The test in this step is already at the end of the file from the first run.
4. Skipped (not reached). The pre-fix run cannot be repeated on the fixed code. The pre-fix output is recorded above.
5. Skipped (not reached). Anchor E1 is already replaced, so the same edit is in place.
6. Skipped (not reached). The 0024 brief is not on this branch.
7. Skipped (not reached). §6 was already run in the first pass (72 passed, full suite 2934 passed with the four DNS failures) and is still valid for this code. No new commit from this run.

Section 7 for this run: not applicable (the run stopped before its checks). The first run's ticks stand.

Nothing for the owner to do beyond what the first run's owner steps already list.
