# 1145: K-F19 guest writers that skip updated_at

Status: done — no change needed
Depends on: 1138 | Base commit: 28106c93 | Branch: none (no code change)
Executor: none

## 1. Objective

Check whether the two writers named in 1138 §2 point 3 can change a field the UbyPort payload reports without bumping `updated_at`. They cannot, so the 1138 claim re-check is not blind to any reported field written through them.

## 2. Context

- `App/app/routes/stay_fees.py:1164` (not `App/app/stay_fees.py`, which does not exist) writes `fee_host_decision`, `fee_host_reason`, `fee_host_reason_reference` and **does** set `"updated_at": db.utcnow()`. The 1138 note was wrong about this one.
- `App/app/passport_photos.py:299` (`purge_stale`) writes only `passport_photo_at: None` and does not bump `updated_at`.
- Payload field set, Python: `guest_payload` in `App/app/reporting.py:180-200` reads `stay_from`/`stay_to` (via `_stay_dates`), `surname`, `first_name`, `birth_date`, `nationality`, `doc_number`, `visa_number`, `res_street`, `res_city`, `res_country`, `purpose`, `note`. `FILED_FIELDS` (`reporting.py:~215-229`) lists the same set.
- Payload field set, Go: `go/internal/ubyport/request.go:209-214` builds `cSurN`, `cDocN`, ... from the collected guest; the SELECT is at `go/internal/ubyport/collect.go:423-425` (surname, first_name, res_country, purpose, note, doc_number, ...). No `passport_photo_at`, no `fee_host_*`, no `doc_type`.
- None of `passport_photo_at`, `fee_host_decision`, `fee_host_reason`, `fee_host_reason_reference` is in either list.

## 3. Files

None changed.

### Other writers checked (guest/reservation, no `updated_at`)

None touches a reported column:

- `reporting.py:2129, 2182, 2304, 2323`: `submission_id` (claim bookkeeping).
- `reporting.py:2559, 2599`: `submit_state`, `manual_*` (state, not payload).
- `retention.py:143`: `filled_ip`. `db.py:1125`: `doc_type` and `fee_host_*` (migration reset).
- `routes/guest.py:467, 2261`: `signed_for_*`.
- `filing_watchdog.py:271`: reservation `at_risk_mailed_at`.
- `icalsync.py:986`: reservation `guest_email` (not in payload). The other reservation writers (`icalsync.py:440, 932`, `routes/admin.py:4154, 4241`) all carry `updated_at`.

## 4. Steps

None. Decision:

No code change, no test. A pin test on the payload field set was not added: `FILED_FIELDS` and `guest_payload` already name the set, and a new writer of a reported column is a review item, not something a static test can catch cheaply. If a future writer must touch a reported column, it sets `"updated_at": db.utcnow()` like `routes/stay_fees.py:1164`.

Fix the 1138 §2 point 3 wording at the next edit of that file: the `stay_fees.py` path is `routes/stay_fees.py` and it does bump `updated_at`.

## 5. Do not touch

No executor run.

## 6. Commands

None.

## 7. Acceptance

Evidence in §2-§3.

## 8. Stop and ask

Not applicable.

## 9. Report

`docs/tasks/1145-report.md`.
