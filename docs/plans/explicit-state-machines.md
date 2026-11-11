# Explicit state machines

Owner asked 2026-11-11: find the implicit state machines and plan making them explicit.

## Problem

Three machines have a transition table that code checks (`billing_account.status`, `payment_request.status`, `site_booking.status`). About twenty others exist only as scattered `UPDATE ... WHERE state = ...` statements, several written from both Python and Go. Nobody can read the legal moves in one place, and a new write can add an illegal move without any test failing.

## Round 1: declare and pin (this plan)

Goal: every machine below has one table in code, and CI fails when a write appears that the table does not list. **No runtime behaviour changes in round 1.**

Rules for every brief:

1. **Derive, never design.** The table lists exactly the moves the code makes today. If the code and a doc (for example [submit_state](../OPERATIONS.md#the-submit_state-state-machine)) disagree, the brief does not pick: it lists the disagreement under "Open questions" and pins what the code does.
2. **The table lives in the owning module**, next to the state constants, named `TRANSITIONS` (as in `App/app/billing.py`). No shared new module, so briefs do not overlap.
3. **One new test file per machine**: `App/tests/test_sm_<machine>.py`. It reads the source of every writer (Python and Go) as text, finds every statement that writes the column, and compares them with a pinned list of (file, from-states, to-state) entries. It fails when a write is added, removed or changed, and when a pinned move is not in `TRANSITIONS`.
4. **Writers are not edited.** The atomic `UPDATE ... WHERE state = ?` compare-and-swap stays as it is. No read-then-write is introduced. Go files are read by the test, never changed.
5. No migration, no new dependency, no template or copy change.
6. Each brief fits one executor session (30 tool calls) and names every file.

## Briefs

| Brief | Machine | Risk | Brief writer |
|---|---|---|---|
| 1103 | `site_booking.status`: pin the direct writers in `booking_direct.py`, `booking_webhook.py` against the existing table | payments | Sonnet |
| 1104 | `payment_request.status`: pin the Go writers against the existing Python table | payments | Sonnet |
| 1105 | `guest.submit_state` | HIGH RISK filing | Opus |
| 1106 | `submission.state` | HIGH RISK filing | Opus |
| 1107 | `door_code.state` | concurrency | Opus |
| 1108 | `cleaning_code.state` | concurrency | Sonnet |
| 1109 | `reservation_claim.state` | guest-data access | Opus |
| 1110 | Queues: `email_outbox.state`, `push_outbox.state`, `ad_click.send_state`, `guide_import.status` | low | Sonnet |
| 1111 | CHECK constraints for state columns that have none. Blocked until the owner runs the distinct-values query the brief gives | HIGH RISK migration | Sonnet |

Run order: 1105 before 1106 (both add a table to `App/app/reporting.py`, at different anchors). The others touch different files and run in any order. 1107 and 1109 both name `ensure_row`, but these are two functions (`door_codes.ensure_row`, `claim.ensure_row`), so the context-lint warning is expected. 1111 runs last.

The two existing tables keep their name `_TRANSITIONS` (`booking_site.py`, `payment_request.py`); 1103 and 1104 do not rename them.

1111 is Postgres only and, per its own text, the app does not start after its merge until the owner runs `pg_schema.py apply`. Merge it only when the owner is ready to run that command at once.

The orchestrator adds the [test-map](../context/test-map.md) rows at review, so no brief edits that file.

## Not in round 1

- Runtime enforcement (a guard inside the writers) and one shared lifecycle for `door_code` and `cleaning_code`: decide after round 1 shows the real tables.
- `stripe_account.onboarding_state` (mirrors Stripe), `data_subject_request.status`, `guide_item.state`, `guest_question.status`, `bank_payment.status` (all have a CHECK and one writer), `user_account.posthog_stage`, `lock_account.status`, `cleaning_event.state`, `reservation.status` (two values).
- The derived customer lifecycle in `App/app/admin_customers.py` and the computed reservation progress labels: no stored state to guard.
