# 1630: Stop the separate "guest details" mail to the host after completion — Report

## Files Changed

```
 App/app/claim.py                                | 11 -----------
 App/tests/test_host_guest_details_mail.py       |  5 ++---
 docs/tasks/1630-stop-host-guest-details-mail.md |  2 +-
 3 files changed, 3 insertions(+), 15 deletions(-)
```

## Command Outputs

### Step 3: Verify host_guest_details removed from claim.py

```
grep -n "host_guest_details" App/app/claim.py
(no output — correct)
```

### Step 4: Test file updated and test name changed

```
sed -n '175,200p' App/tests/test_host_guest_details_mail.py
def test_the_receipt_is_copied_to_the_host_and_no_separate_host_details_mail(monkeypatch):
    ...
    assert _rows(seed["stay"], "guest_details_host") == []
```

### Step 6: All tests pass

```
.venv/bin/python -m pytest tests/test_host_guest_details_mail.py tests/test_guest_mail.py tests/test_claim_mail.py tests/test_completion_fee_mail_1077.py tests/test_guest_receipt_sent_mail.py -q --tb=short -x 2>&1 | tail -5
-- Docs: https://docs.pytest.org/en/capture-warnings.html
154 passed, 1 warning in 4.27s
```

### Context lint pass

```
python3 scripts/context_lint.py 2>&1 | tail -1
context lint: OK
```

## Acceptance Checklist

- [x] `grep -n "host_guest_details" App/app/claim.py` prints nothing.
- [x] In `maybe_notify_completion`, `mail.enqueue(kind="completion", ... cc_email=payload.get("reply_to", "") ...)` is immediately followed by `db.execute(` for `completion_notified_at`.
- [x] `test_the_receipt_is_copied_to_the_host_and_no_separate_host_details_mail` exists, keeps the completion asserts, and asserts `_rows(seed["stay"], "guest_details_host") == []`.
- [x] The old test name no longer appears: `grep -rn "still_gets_details" App/tests` prints nothing.
- [x] The section 6 pytest command passes with 0 failed (154 passed, 1 warning).
- [x] `python3 scripts/context_lint.py` passes (context lint: OK).
- [x] `git diff --stat` touches only files from section 3 (claim.py, test_host_guest_details_mail.py, brief and report).
- [x] No template, CSS or guest-page change, so no screenshot is needed.

## Deviations

None. All steps followed exactly as specified.

## Questions

None.

## Owner Steps Left

1. Open the pull request for branch `cursor/1630-stop-host-guest-details-mail-4527` and wait until the checks are green.
2. Keep it a draft until you want it live, because green merges auto-deploy.
3. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
4. After the next stay completes, check the host inbox: only "You're all set" arrives, with no "Your guests have registered".
