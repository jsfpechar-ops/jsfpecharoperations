# TTLock door codes: plan

Status: planning (orchestrator, 2026-10-07). Source: an owner-supplied Gemini spec, checked against the repo and a 3-advisor council (Contrarian, First Principles, Executor).

## Goal

A guest gets the door PIN only after their registration is complete. The PIN shows on the guest stay page and arrives by e-mail. The host sees it in the host app. A TTLock outage never touches UbyPort filing (rule 1).

## What the Gemini spec gets wrong

| Gemini spec | Repo reality | Plan |
|---|---|---|
| Flask, SQLAlchemy, `current_app`, `flash()`, `db.session` | FastAPI, raw SQL through `App/app/db.py` | Use `db.query_one`, `db.execute_rowcount`, `db.insert` |
| `POST /stay/<t>/submit` is the trigger | Guest URLs are `/l/{token}/{reservation_id}/...`. Completion is `reporting.refresh_registration_completed_at`. It can fire from a scheduler tick and can be cleared again | A worker job checks state on each run. The request never calls TTLock |
| Overwrite `guest/confirm.html` | `confirm.html` is the claim confirmation page | New block in `guest/stay.html`, no JS, house CSS |
| Bootstrap classes, inline SVG | Light-mode house design, geometry tests | Existing components only |
| One TTLock account in env vars, refreshed token kept in `app.config` | Web and worker are separate processes. A restart loses the token. TTLock may rotate the refresh token (unverified) | Token pair stored encrypted in the DB. Refresh uses compare-and-swap |
| `if not reservation.passcode` guard | Two processes can both pass the check | `UNIQUE(reservation_id)` plus a conditional UPDATE claim. Only the worker issues codes |
| Plaintext `passcode VARCHAR(20)` on `reservation` | Privacy first, public repo | `door_code.pin_enc` via `db.encrypt_field`, nulled after checkout (retention line) |
| Guest name in `keyboardPwdName` | New personal data sent to a third party | Send `UH-<door_code.id>` |
| `boto3` send inside the request | `mail.enqueue` outbox with retries and an idempotency key | New mail kind using the `{{claim_secret}}` marker pattern. The PIN is never stored in plaintext in the outbox or the console log |
| PIN in the host CC copy | Host owns the lock and sees it in the host app | Owner decision 2026-10-07: one mail to the guest with the host in CC, PIN included. The PIN still goes through the marker pattern, so it is never plaintext in the outbox |
| Global 15:00 / 11:00 env | Each apartment has its own times | `apartment.checkin_hour`, `apartment.checkout_hour`, defaults 15 and 11 |
| No cancel or date-change handling | iCal sync cancels and moves stays | Reconciler revokes or moves the code |
| 10003/10004 = expired token | Unverified (TTLock docs blocked from the orchestrator sandbox) | Task 0008 verifies |
| Type 3 "valid from check-in to checkout" is all you need | Verified (official `/v3/keyboardPwd/get` doc, pasted by the owner 2026-10-07): a period code "must be used at least once within 24 Hours after the Start Time, Or it will be invalidated" | A guest who first types the code more than 24 h after check-in time is locked out. Late-arrival path is required, not optional |

## Verified facts (official `/v3/keyboardPwd/get` doc, pasted by the owner 2026-10-07)

- `get` returns a 6 to 9 digit random code made by a cloud algorithm. No gateway is needed. The code cannot be chosen.
- Validity is accurate to the hour. 19:20 becomes 19:00, so send whole hours.
- Type 3 (period) must be used at least once within 24 h after the start time, or it is invalidated.
- Request: form-encoded POST with `clientId`, `accessToken`, `lockId`, `keyboardPwdType`, optional `keyboardPwdName`, `startDate`, `endDate`, `date` (ms). Response: `{"keyboardPwd": "0563456", "keyboardPwdId": 10236}`. The code is a string and can start with 0, so store it as text.

Inferred, not verified: the lock learns about a random code only when someone first types it. If so, a cloud delete without a gateway cannot reach the lock, and a cancelled booking's code works until its end date. Task 0008 checks this.

## Open facts (task 0008 settles them, nobody guesses)

1. Error codes for an expired token and a dead refresh token. Token lifetime. Does refresh rotate the refresh token?
2. Random period code: settled above (24 h first-use rule confirmed).
3. Can such a code be deleted or moved remotely? Does that need a gateway? Without one, a cancelled booking's code stays valid until its end date.
4. Custom code (`/v3/keyboardPwd/add`, gateway). Does it avoid the 24 h rule and allow delete and change?
5. Do the owner's locks have a G2 gateway (or Wi-Fi)?
6. OAuth for a host account (password grant, md5 password). Where the EU API is hosted and who the processor is.

Facts 2 to 5 pick the endpoint. With a gateway, the plan uses `add` (no 24 h rule, revocable). Without one, it uses `get` and the guest page offers "get a new code" (rate-limited) for a late arrival.

## Data shape (migration 0007)

- `apartment`: `lock_provider TEXT` (`'ttlock'` or NULL), `lock_id TEXT`, `checkin_hour INTEGER`, `checkout_hour INTEGER`.
- `door_code`: `id`, `reservation_id` UNIQUE, `apartment_id`, `state`, `attempts`, `next_attempt_at`, `claimed_at`, `provider_code_id TEXT`, `pin_enc TEXT`, `valid_from`, `valid_to` (UTC ISO), `last_error` (short code only), `issued_at`, `revoked_at`, `created_at`, `updated_at`.
- States: `pending` -> `issuing` -> `issued`; `issuing` -> `retrying` -> `failed` (host alert); `issued` -> `revoke_pending` -> `revoked`; `issued` -> `expired` (`pin_enc` nulled).
- Tokens, phase 1: one owner account in `settings` (`ttlock_access_token_enc`, `ttlock_refresh_token_enc`, `ttlock_token_expires_at`, `ttlock_token_version`). Seeded once from env. Per-host accounts are a later phase and need an owner decision.

## Trigger

New scheduler job `door_codes` (its own job, so a TTLock outage never marks the mail job failed). Each run compares wanted against actual state:

- Wanted: reservation `active`, `registration_completed_at` set, apartment has `lock_id`, stay not over. Ensure a row, issue the code.
- Cancelled, or dates changed: revoke, or move the window.
- Registration cleared after a code was issued: keep the code. The guest is still staying, and revoking it on a form edit could lock them out.
- A guest save may set `next_attempt_at = now` to speed things up. Correctness never depends on it.

## Delivery sequence (one PR each)

| Task | What | Depends on |
|---|---|---|
| 0008 | Spike: verify the open facts against the official docs and one real lock. Write `docs/TTLOCK.md`. No App change | none |
| 0009 | Migration 0007, `App/app/ttlock.py` client (requests, 5 s timeout, faked in tests), encrypted token store with CAS refresh, config, retention lines, ENVIRONMENT section | 0008 |
| 0010 | `door_codes` reconciler job: issue, retry with backoff, failed alert. Proves it never writes to submission or filing tables | 0009 |
| 0011 | Guest stay-page block, mail kind with `{{door_code}}` marker, host reservation line. Browser and geometry tests, screenshots | 0010 |
| 0012 | Cancel and date-change handling, apartment form fields (lock id, hours 0-23), late-arrival path chosen in 0008 | 0011 |

The briefs for 0009 and later are written after the 0008 report, because the endpoint choice changes them.

## Owner decisions (2026-10-07)

1. Gateway: every lock has a Wi-Fi gateway. The plan uses `/v3/keyboardPwd/add` (custom code, via gateway), if 0008 confirms it skips the 24 h first-use rule and supports remote delete and change. `get` stays the fallback.
2. Scope: a pilot on a few of the owner's apartments, one TTLock account.
3. Mail: the guest gets the PIN by e-mail with the host in CC. The PIN is valid only from check-in hour to checkout hour, which the host sets per apartment.
4. Trigger: the code is issued when all guest forms are complete (`registration_completed_at`), not when the police accept the filing. A filing can wait up to `submit_after_hours`, and the guest must not wait for it.

## Still open

1. Subprocessor: TTLock (Sciener) goes into the subprocessor register and ROPA before 0011 ships. A lawyer note is needed if hosting is outside the EU.
