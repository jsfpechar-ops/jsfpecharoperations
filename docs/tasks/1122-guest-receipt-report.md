# 1122 Report: "What you sent" block on the guest receipt

Status: review

## 1. Files changed (`git diff --stat HEAD`)

```
 App/app/claim.py         |  4 ++++
 App/app/guest_uk_i18n.py |  3 +++
 App/app/mail.py          | 35 +++++++++++++++++++++++++++----
 App/app/mail_notify.py   | 51 +++++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 89 insertions(+), 4 deletions(-)
```

New file: `App/tests/test_guest_receipt_sent_mail.py` (untracked at diff time; included in commit).

i18n.py and guest_uk_i18n.py: the 5 new keys (`mail_completion_sent_*`) were already committed to this branch by a prior agent (1123 commit f24192cd8). My script verified they were in place; no net change to i18n.py.

## 2. Commands and output (last 5 lines each)

**Step 2** – `grep -n 'RECEIPT_DETAILS_' App/app/mail.py | head -3`:
```
174:RECEIPT_DETAILS_MARKER = "{{receipt_details}}"
175:RECEIPT_DETAILS_KEY = "receipt_details_reservation_id"
```

**Step 3** – `grep -n 'def _with_receipt_details' App/app/mail.py | head -3`:
```
371:def _with_receipt_details(value: str, payload: Dict[str, Any], *, as_html: bool) -> str:
```

**Step 4** – `grep -c 'as_html=False' App/app/mail.py`:
```
2
```

**Step 5** – `python -c "import app.mail"`:
```
(no output)
```

**Step 6** – `grep -n 'sent_details: bool = False' App/app/mail_notify.py | head -3`:
```
1723:    sent_details: bool = False,
```

**Step 7** – `grep -n 'RECEIPT_DETAILS_MARKER' App/app/mail_notify.py | head -3`:
```
1782:        blocks.append(mail.RECEIPT_DETAILS_MARKER)
1783:        text_lines.extend(["", mail.RECEIPT_DETAILS_MARKER])
```

**Step 8** – `python -c "import app.mail_notify as m; print(callable(m.render_receipt_details))"`:
```
True
```

**Step 9** – `grep -n 'sent_details=True' App/app/claim.py | head -3`:
```
515:                sent_details=True,
```

**Step 10** – `grep -n 'RECEIPT_DETAILS_KEY' App/app/claim.py | head -3`:
```
819:        payload[mail.RECEIPT_DETAILS_KEY] = int(reservation["id"])
```

**Steps 11–15** – `grep -c '"mail_completion_sent_title"' App/app/i18n.py`:
```
5
```
(Keys already present from 1123 commit; script was a no-op.)

**Step 16** – `python -c "from app import i18n; print(all('mail_completion_sent_title' in i18n.STRINGS[l] for l in i18n.LANGUAGES))"`:
```
True
```

**Step 17** – new test file, 6 tests:
```
......                                                                   [100%]
6 passed in 0.31s
```

**Step 18** – full mail/claim test suite:
```
FAILED tests/test_claim_mail.py::test_claim_form_and_privacy_notice_disclose_email_and_cookies
1 failed, 448 passed, 5 warnings in 6.22s
```

**Context lint**:
```
context lint: OK
```

## 3. §7 Acceptance

- [x] `tests/test_guest_receipt_sent_mail.py`: 6 passed.
- [x] Step 18 command: 448 passed; 1 failure is pre-existing (see Deviations).
- [x] `grep -c '"mail_completion_sent_title"' App/app/i18n.py App/app/guest_uk_i18n.py` → 5 and 1.
- [x] `git diff --stat HEAD` lists only the §3 files (mail.py, mail_notify.py, claim.py, guest_uk_i18n.py, new test). i18n.py had no net diff (keys already present).

## 4. Deviations

**Pre-existing test failure in step 18.**
`test_claim_mail.py::test_claim_form_and_privacy_notice_disclose_email_and_cookies` asserts
`"a receipt (your host gets a copy)"` in the claim page. Commit `f24192cd8` (1123: guest details mail — legal copy) updated `claim_email_help` in English to drop "(your host gets a copy)" but did not update the test. Verified by running the test with a clean stash (no 1122 changes): still fails. My changes do not introduce or worsen this failure.

**i18n.py steps were no-ops.**
The 5 new i18n keys (`mail_completion_sent_title`, `mail_completion_sent_doc_label`, `mail_completion_sent_unnamed` for en/cs/de/es/fr) and the uk keys were already present in the branch HEAD before I ran the scripts. The scripts found the keys already in place and changed nothing. This is not a problem; the keys satisfy the brief's requirement.

## 5. Questions

None.

## 6. Owner steps

1. Fix the pre-existing failure in `test_claim_mail.py:219`: update the assertion to match the current (1121-era) copy, e.g. `"and a receipt. Shown"` or similar, then commit.
2. Open the draft PR for `task/1120-1123-guest-details-mail` on GitHub (or ensure it is already open).
3. When CI is green and review is done, click "Ready for review".
4. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
