# 1291 Report

Status: review

## 1. Files changed

```
 App/app/claim.py                           |  8 ++++----
 App/tests/test_host_guest_details_mail.py | 10 +++++-----
 2 files changed, 9 insertions(+), 9 deletions(-)
```

## 2. Commands

**pytest** (`App/`, last lines):

```
........................................................................ [ 97%]
....                                                                     [100%]
148 passed, 1 warning in 5.02s
```

**context lint** (repo root, last lines):

```
next free: task 1292 | migration 0046
context lint: OK
```

## 3. Acceptance

- [x] `cc_email=payload.get("reply_to"` in `maybe_notify_completion`
- [x] `host_url=` with `reservations/{id}` on completion composer
- [x] `test_the_receipt_is_copied_to_the_host_and_the_host_still_gets_details`
- [x] §6 pytest green (148 passed)
- [x] `host_guest_details` still called after enqueue

## 4. Deviations

None.

## 5. Questions

None.

## 6. Owner steps left

1. Merge with `scripts/merge-pr-on-green.sh <pr>`.
2. Deploy production.
3. Confirm next completed stay: host CC on guest receipt + `guest_details_host` still arrives.
4. No backfill for stay 198.
