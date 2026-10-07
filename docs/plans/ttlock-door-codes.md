# Door codes (TTLock): architecture

Status: planning (orchestrator, 2026-10-07). Inputs: an owner-supplied Gemini spec (rejected, see the end of this file), the repo, a 3-advisor council, the official `/v3/keyboardPwd/get` doc and owner decisions.

## 1. What the feature is

A property can opt in to door codes. Once every guest on a stay is registered, UbyHost picks a door code, shows it to the guest and mails it (host in CC). Close to check-in it puts the code on the property's TTLock lock. The code is valid only from the property's check-in hour on arrival day to its checkout hour on departure day. The guest sees it on the stay page and gets it by e-mail, with the host in CC. If the booking is cancelled or moved, the code is deleted or moved with it.

A property without a lock sees no difference. No code runs and no API call is made for it.

## 2. Owner decisions (2026-10-07)

1. Every pilot lock has a Wi-Fi gateway. Endpoints: `add` (custom code), `change` and `delete`, all with the gateway type (`2`). `get` is not used, because of its 24 h first-use rule.
2. Pilot on a few of the owner's apartments. Built per host and per property from day one, so other hosts only need the setting.
3. Guest mail carries the PIN, host in CC.
4. Trigger is registration complete (`reservation.registration_completed_at`), not police acceptance.
5. Check-in and checkout hours are set by the host per property.
6. The 30,000 calls a month are per developer app, so every UbyHost host shares them (owner, 2026-10-07). Calls are budgeted, see §7.
7. The guest sees the PIN the moment registration is complete, and the lock gets it close to check-in (owner wish, design in §6).

## 3. Verified facts (official TTLock docs, pasted by the owner)

`/v3/keyboardPwd/get`:

- Returns a 6 to 9 digit random code from a cloud algorithm. No gateway needed. Not customisable.
- Validity is accurate to the hour (19:20 becomes 19:00). Send whole hours.
- Type 3 (period) must be used at least once within 24 h after the start time, or it is invalidated.
- The code is a string and can start with 0. Store it as text.

`/v3/keyboardPwd/change`:

- With `changeType=2` it works remotely on a Wi-Fi lock or a lock with a gateway.
- One call can change the name, the validity window (`startDate` and `endDate` together) and the code itself (`newKeyboardPwd`).
- Parameters: `clientId`, `accessToken`, `lockId`, `keyboardPwdId`, optional `keyboardPwdName`, `newKeyboardPwd`, `startDate`, `endDate`, then `changeType`, `date`. Response `{"errcode": 0, "errmsg": "..."}`.

`/v3/keyboardPwd/delete`:

- With `deleteType=2` it deletes remotely on a Wi-Fi lock or a lock with a gateway. Works for random and custom codes.
- Parameters: `clientId`, `accessToken`, `lockId`, `keyboardPwdId`, `deleteType`, `date`. Response `{"errcode": 0, ...}`.

Still unverified until task 0008 writes `docs/TTLOCK.md`: token lifetime and error codes, `add` parameters and whether `add` honours a future start, whether an expired code still takes a slot on the lock, and how many slots a lock has.

## 4. How heavy is it

Small, and isolated behind one per-property switch.

| Piece | Size (estimate) |
|---|---|
| `App/app/ttlock.py` HTTP client, token refresh, call budget | about 250 lines |
| `App/app/door_codes.py` state machine and reconciler | about 250 lines |
| 1 migration (3 tables, 4 apartment columns) | about 50 lines |
| 1 scheduler job | about 20 lines |
| Host UI: one settings card, one property section, one stay line | 3 template blocks |
| Guest UI: one block on `guest/stay.html` | 1 template block |
| 1 mail kind | about 40 lines |
| New dependencies | none (`requests` and `zoneinfo` already used) |

Runtime cost when no property has a lock: one indexed SQL query a minute that returns nothing. UbyPort filing code is never imported or touched by these modules (rule 1). A global kill switch `UBYHOST_DOOR_CODES=0` stops every TTLock call.

Names are provider-neutral (`door_code`, `lock_account`, `lock_provider`), so another lock brand later is a new client module, not a schema change. No provider abstraction is built now.

## 5. Data model (migration `0007_door_codes.sql`)

### `lock_account`: one per host and provider

| Column | Note |
|---|---|
| `id` | PK |
| `owner_user_id` | FK `user_account`, UNIQUE with `provider` |
| `provider` | `'ttlock'` |
| `account_label_masked` | for example `jo•••@gmail.com`, for display only |
| `access_token_enc`, `refresh_token_enc` | `db.encrypt_field` |
| `token_expires_at` | UTC ISO |
| `token_version` | INTEGER, compare-and-swap on refresh |
| `status` | `ok`, `reauth_needed` |
| `locks_json` | cached lock list (id, name, has_gateway), refreshed only on demand |
| `locks_fetched_at`, `created_at`, `updated_at` | |

The host's TTLock password is used once to get tokens and is never stored or logged.

### `apartment`: 4 new columns

`lock_provider TEXT` (NULL = feature off), `lock_id TEXT`, `checkin_hour INTEGER` (default 15), `checkout_hour INTEGER` (default 11).

### `door_code`: one per reservation

| Column | Note |
|---|---|
| `id` | PK |
| `reservation_id` | UNIQUE, FK, ON DELETE CASCADE |
| `apartment_id`, `lock_id` | lock id copied at issue, so a later lock change can still delete the old code |
| `state` | see below |
| `pin_enc` | `db.encrypt_field`, NULL after expiry |
| `provider_code_id` | TTLock `keyboardPwdId`, NULL until the code is on the lock |
| `push_after` | UTC ISO, check-in minus 48 h (or now, if sooner) |
| `valid_from`, `valid_to` | UTC ISO, from Prague local hours |
| `source` | `auto` or `manual` (host typed it in) |
| `attempts`, `next_attempt_at`, `claimed_at` | retry and lease |
| `last_error` | short code only, never a response body |
| `notified_at`, `notified_window` | guest mail queued, and for which window |
| `issued_at`, `revoked_at`, `created_at`, `updated_at` | |

### `lock_api_usage`: the budget counter

`month TEXT`, `provider TEXT`, `calls INTEGER`, PK (`month`, `provider`). Incremented with `INSERT ... ON CONFLICT DO UPDATE SET calls = calls + 1`, which works on SQLite and Postgres.

### Retention (`App/app/retention.py`)

- `door_code.pin_enc`: NULL at `valid_to` + 1 day.
- `door_code` row: deleted with its reservation.
- `lock_account` tokens: deleted on disconnect or account deletion.

## 6. State machine

The key idea: with a custom code, UbyHost picks the PIN itself. So the guest can see and receive the PIN at once, with no API call, and the lock only needs it before check-in.

```
 registration complete
          |
          v
       chosen  ---- PIN picked locally, shown on the stay page, mail queued. 0 calls.
          |
          | push_after reached (check-in - 48 h)
          v
       pushing ---ok---> active ---checkout + 1 day---> expired (pin_enc NULL,
          |  ^             |                             slot kept for reuse)
     error|  |retry        | booking cancelled
          v  |             v
       retrying        revoke_pending ---ok---> revoked
          |
 5 tries  v
       failed ---host "Retry now" or "Enter a code yourself"---> active

 chosen + booking cancelled  -> cancelled (0 calls, nothing was on the lock)
 chosen + dates moved        -> stays chosen, new window, one new mail (0 calls)
 active + dates moved        -> one change call, stays active, one new mail
```

Rules:

- One row per reservation (`UNIQUE`), created with `INSERT ... ON CONFLICT DO NOTHING`.
- A worker claims a row with one conditional UPDATE (`WHERE id = ? AND state IN ('chosen','retrying') AND push_after <= ? AND next_attempt_at <= ? AND (claimed_at IS NULL OR claimed_at < lease_cutoff)`) and acts only if `db.execute_rowcount` returns 1. Two processes can never both push one code.
- **Slot reuse.** To push, the worker first looks for an `expired` row of ours on the same lock. If one exists, it calls `change` on that `keyboardPwdId` with the new PIN and window. Otherwise it calls `add`. A lock then holds at most as many of our codes as there are stays that overlap the 48 h push window, about 2 per property. Capacity stops mattering, and there is no delete call after each stay. Only codes named `UH-...` are ever reused. The host's own codes are never touched.
- **PIN choice.** 6 digits from `secrets`, no runs or repeats (`123456`, `111111`), not equal to any active or chosen code of ours on the same lock. If the lock still refuses it at push time as a clash with one of the host's own codes (rare), the worker picks a new PIN, pushes it, sends the guest a "your door code changed" mail and alerts the host.
- **Push failures are found early.** The 48 h window gives about 2 days of retries before arrival. Backoff 1, 5, 15, 60 and 240 minutes, then `failed`. If a code is still not `active` 6 h before check-in, the host gets an urgent alert.
- **Stay starts within 48 h.** `push_after` is now, so the push happens on the guest's own save (§9 step 2) and the code is on the lock within seconds.
- Registration cleared after the PIN was chosen: the code stays. The guest is still staying, and revoking it on a form edit could lock them out.
- Before a retry after a push timeout, the client lists the lock's codes and adopts one named `UH-<door_code.id>` if it exists. A timeout never creates a second code.

## 7. API call budget (30,000 a month, shared by all hosts)

The design spends calls only on events, never on polling.

| Event | Calls |
|---|---|
| Stay registered, PIN shown and mailed | 0 |
| Code put on the lock (`change` on a reused slot, or `add`) | 1 |
| Cancelled or moved before the push | 0 |
| Cancelled after the push | 1 (`delete`) |
| Moved after the push | 1 (`change`) |
| Stay over | 0 (the slot waits for reuse) |
| Retry after an error | 1 each, at most 5 |
| Timeout recovery (list codes) | 1 |
| Token refresh | 1, only near expiry or on an expired-token error |
| Host connects the account or taps "Refresh lock list" | 1 |
| Guest opens the stay page, host opens the stay | 0 (reads the DB) |

Expected a little over 1 call per stay. 30,000 calls cover roughly 25,000 stays a month across all hosts. The pilot will use a few hundred.

Guards in `ttlock.py`, which every call goes through:

- Below 80 % of the month: normal.
- 80 % to 95 %: only push, delete, change and refresh. Lock-list refresh is refused with a message. The owner gets one alert.
- Above 95 %: only pushes for stays starting within 24 h, plus delete. The owner gets an urgent alert.
- The counter shows on the admin operations page.

No unlock-record polling, no lock-status polling, no periodic token refresh.

## 8. Security

- **PIN at rest.** Encrypted with `db.encrypt_field`, decrypted only while rendering the page or delivering the mail, NULL after expiry.
- **PIN in mail.** New mail kind `door_code`. The stored body holds a `{{door_code}}` marker, and the encrypted PIN sits in the payload, the same pattern as `{{claim_secret}}` in `App/app/mail.py`. The outbox row and the console mail log never hold the digits. Idempotency key `door_code:<reservation_id>:<valid_from>`, so a moved stay sends one new mail and a resend sends none.
- **PIN on the guest page.** Shown only to a device that passed the existing claim and PIN gate for that reservation. No JavaScript. The page gets `Cache-Control: no-store`.
- **Who picks the PIN.** The server, see §6. 6 digits from `secrets`, no runs or repeats. The guest learns the PIN before it is on the lock, but it opens nothing outside its window, so that is no extra exposure.
- **Lock ownership.** A host can only pick a lock from their own account's cached list. The server checks that `lock_id` is in that list on save, so a hand-edited form cannot target another host's lock.
- **Tokens.** Encrypted, per host. Refresh with compare-and-swap on `token_version`. A failed refresh sets `reauth_needed` and alerts the host. No token ever goes in `app.config`, env or logs.
- **Data sent to TTLock.** Lock id, validity window, the PIN and the code name `UH-<id>`. No guest name, e-mail or reservation summary.
- **Logging.** Error code and door-code id only. A test asserts that no PIN or token reaches the log.
- **Audit.** One `audit` row per issue, change, revoke and manual code.
- **Fallback the host controls.** When a code fails, the host sees "Retry now" and "Enter a code yourself". A code the host made in the TTLock app is stored and mailed the same way (`source = manual`).
- **Privacy register.** TTLock (Sciener, Hangzhou) goes into the subprocessor register and the ROPA before the guest block ships. If data is stored outside the EU, the lawyer reviews the transfer basis first.

## 9. Flow

1. A guest saves the last missing form. The existing code sets `registration_completed_at`.
2. In the same request, after the save is committed, `door_codes.on_registration_complete(reservation_id)` runs. It creates the row in `chosen`, picks the PIN and queues the mail. No API call. The stay page shows the PIN on that very response. If the stay starts within 48 h, it also tries one push with a 5 s timeout. If that push fails, the guest still sees the PIN, and the worker retries.
3. The `door_codes` scheduler job (every minute, its own job id, so a TTLock outage never marks the mail job failed) runs `door_codes.reconcile()`. It creates rows for stays completed by a scheduler tick, pushes codes whose `push_after` has come, retries, handles cancellations and moves, and expires old PINs. It uses the same functions as step 2.
4. iCal sync never calls TTLock. It only changes `reservation`, and the reconciler sees the difference on its next run.

The UbyPort submit path is not changed in any step.

## 10. How it looks

All screens use existing components and house CSS, light mode, and work without JavaScript.

### Host: Settings → Smart locks (new card)

```
Smart locks
TTLock     Not connected
           [TTLock e-mail or phone] [Password]   (Connect)
           We use your password once to connect and never store it.

-- after connecting --
TTLock     Connected as jo•••@gmail.com · 4 locks
           (Refresh lock list)   (Disconnect)
```

### Host: Property → Door code (new `<details class="panel property-section" id="door-code">`)

Shown only when the host has a connected account. Otherwise it shows one line: "Connect a smart lock in Settings."

```
Door code
[x] Send guests a door code when registration is complete
Lock            [Front door (gateway online)  v]
Check-in from   [15:00 v]     Check-out until [11:00 v]
```

### Host: stay detail and Today

One line in the stay, with the PIN visible to the host:

- "Door code 482193 · valid 12 Oct 15:00 to 14 Oct 11:00"
- "Door code waits for registration"
- "Door code failed: gateway offline" with (Retry now) and (Enter a code yourself)

Today gets a "Needs you now" row only for `failed`, or for a stay starting within 6 h without a code.

### Guest: stay page block (under the "all done" card in `guest/stay.html`)

```
Your door code
  4 8 2 1 9 3
Works from Sat 12 Oct, 15:00 to Mon 14 Oct, 11:00.
Type the code on the keypad, then press the lock key.
We have sent it to j•••@gmail.com too.
```

Before registration is complete: "Your door code appears here once every guest is registered." While being prepared: "Your door code is being prepared. Reload this page in a minute." When it failed: "Your host will send you the door code." Plus the host contact.

### Mail (kind `door_code`)

Subject "Your door code for <property>". Body: the code, the validity window in Prague time, the lock instruction from the property's check-in info, the host contact. To the guest, CC the host.

## 11. Delivery sequence (one PR each)

| Task | What | Depends on |
|---|---|---|
| 0008 | Fact sheet `docs/TTLOCK.md` from the official docs. Owner tests a remote delete on one lock. No App change | none |
| 0009 | Foundation. Migration, `ttlock.py` (form POST, 5 s timeout, token CAS refresh, budget counter, kill switch), retention lines, ENVIRONMENT section. HTTP faked in tests, a fixture blocks real network calls | 0008 |
| 0010 | Host setup. Smart locks card (connect, disconnect, refresh list), property door-code section, lock-ownership check. Browser and geometry tests | 0009 |
| 0011 | Issuing. `door_codes.py` state machine, reconciler job, inline first try on the guest's save, retries, host alerts. Test proves no write to `submission` or filing tables | 0010 |
| 0012 | Delivery. Guest stay block, mail kind with `{{door_code}}` marker, host stay line, manual code, Today row. Screenshots at 360, 390 and 1280 px | 0011 |
| 0013 | Lifecycle. Cancel, date move, expiry purge, admin usage panel | 0012 |
| docs | Subprocessor register, ROPA, privacy copy. Lawyer review if needed | before the pilot goes live |

Briefs for 0009 and later are written after the 0008 report, because the endpoint facts change their code.

## 12. Pilot rollout (owner)

1. Merge 0009 to 0013. Deploy.
2. In Settings → Smart locks, connect the TTLock account.
3. On 2 or 3 properties, turn on door codes, pick the lock, set the hours.
4. Make a test stay for tomorrow, register as a guest, check the page, the mail, the CC and the keypad.
5. Cancel the test stay. Check that the code no longer opens the door.
6. Watch the call counter on the admin operations page for the first month.

## 13. Open questions (0008 answers them)

1. Expired-token and dead-refresh-token error codes. Token lifetime. Does refresh rotate the refresh token?
2. `add` via gateway: parameters, does it honour a future `startDate`, does the 24 h first-use rule apply, code length limits, the error code for a clash and for an offline gateway.
3. Does `change` on an expired code's `keyboardPwdId` bring it back with the new PIN and window? (Slot reuse depends on it. If not, the worker calls `delete` after checkout, at 1 more call per stay.)
4. Does an expired code still take a slot on the lock, and how many slots does a lock have?
5. Per-second or per-minute rate limits.
6. Is there an OAuth redirect flow, so the host never types their password into UbyHost?
7. Who runs `euapi.ttlock.com` and where the data is stored.

Answered: the 30,000 limit is per developer app (owner). `change` and `delete` work remotely via gateway (official docs, §3).

## 14. Why not the Gemini spec

| Gemini spec | Repo reality |
|---|---|
| Flask, SQLAlchemy, `current_app`, `flash()` | FastAPI, raw SQL through `App/app/db.py` |
| `POST /stay/<t>/submit` is the trigger | Guest URLs are `/l/{token}/{reservation_id}/...`. Completion is set by `reporting.refresh_registration_completed_at`, can fire from a scheduler tick and can be cleared again |
| Overwrites `guest/confirm.html` | That is the claim confirmation page |
| Bootstrap classes, inline SVG | House CSS, light mode, geometry tests |
| One account in env, refreshed token in `app.config` | Web and worker are separate processes, and a restart loses the token |
| `if not reservation.passcode` guard | Two processes both pass the check |
| Plaintext `passcode` on `reservation` | Privacy first. Encrypted, purged after checkout |
| Guest name sent to TTLock | New personal data to a third party, for no gain |
| `boto3` send inside the request | The outbox has retries and idempotency |
| No cancel or date-move handling | iCal sync cancels and moves stays |
| Type 3 `get` code | 24 h first-use rule locks out late guests |
