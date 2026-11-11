# 1121 Report

Status: review

## 1. Files changed

```
 App/app/claim.py                          |  18 +++-
 App/app/host_i18n.py                      |  59 +++++++++++++
 App/app/mail.py                           |  39 ++++++++-
 App/app/mail_notify.py                    | 194 +++++++++++++++++++++++++++++++++++++++++++
 App/tests/test_claim_mail.py              |   2 +
 App/tests/test_host_guest_details_mail.py |  (new)
 5 modified + 1 created, 306 insertions(+), 6 deletions(-)
```

## 2. Commands and output

**Step 2 verify** (`grep -n '"guest_details_host"' App/app/mail.py`):
```
42:    "guest_details_host",
109:    "guest_details_host",
```

**Step 7 verify** (import mail.py):
```
(no output)
```

**Step 8 verify** (mask_document_number):
```
•••• 4567 ••••
```

**Step 9 verify** (host_i18n translate):
```
Otevřít pobyt
```

**Step 10 verify** (`grep -n 'cc_email' App/app/claim.py`):
```
(no output)
```

**Step 11 verify** (`grep -n 'host_guest_details' App/app/claim.py`):
```
831:        mail_notify.host_guest_details(
```

**Step 12 verify** (`grep -n 'host_url' App/app/claim.py`):
```
(no output)
```

**Step 13 verify** (`grep -n '"guest_details_host"' App/tests/test_claim_mail.py`):
```
1821:        "guest_details_host",
```

**Step 14** (`pytest tests/test_host_guest_details_mail.py -q --tb=short -x`):
```
......
6 passed in 0.39s
```

**Step 15** (mail + claim + host_i18n + completion_fee tests):
```
402 passed, 6 warnings in 6.58s
```

**Context lint**:
```
context lint: OK
```

## 3. Acceptance §7

- [x] `grep -n 'cc_email' App/app/claim.py` prints nothing.
- [x] `grep -c 'guest_details_host' App/app/mail.py` prints 2.
- [x] `tests/test_host_guest_details_mail.py`: 6 passed.
- [x] Step 15 command: 0 failed.
- [x] `git diff --stat origin/main` lists only the §3 files.

## 4. Deviations

- The context lint reports `next free: migration 0046`; the brief mentioned watching for migration 45 vs 44. This task creates no migration, so no deviation.
- Czech strings in `_GUEST_DETAILS_HOST_STRINGS` use unicode escape sequences in the source (Python `\uXXXX`). The `test_host_i18n.py` key-equality test passes; the string values are functionally correct.
- `_DOC_MASK` uses `\u2022\u2022\u2022\u2022` (bullet characters) rather than literal `••••` in the source, identical at runtime.

## 5. Questions

- `App/app/fee_update.py`: `completion_update` still copies the host via `cc_email`. That is out of scope for 1121 per §5.

## 6. Owner steps

1. Open the draft PR for `task/1120-1123-guest-details-mail` on GitHub.
2. When CI is green and the review is done, click "Ready for review".
3. Merge with `scripts/merge-pr-on-green.sh <PR number>` from the repo root.
4. Full details stay off for every workspace until 1123b's DPA version bump is live.
