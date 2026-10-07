# Door codes (TTLock): architecture

Status: planning (orchestrator, 2026-10-07). Inputs: an owner-supplied Gemini spec (rejected, §13), the repo, a 3-advisor council, official TTLock docs pasted by the owner, and owner decisions.

## 1. What the feature is

A property can opt in to door codes. When every guest on the stay is registered, UbyHost asks TTLock for a timed code. The code is valid from the property's check-in hour on arrival day to its checkout hour on departure day. The guest sees it on the stay page at once and gets it by e-mail, with the host in CC. If the booking is cancelled or moved, UbyHost deletes or moves the code.

Everything else (a late guest, a new code, a manual exception) the host does in their own TTLock app. UbyHost automates only the routine.

A property without a lock sees no difference. No code runs and no API call is made for it.

## 2. Owner decisions (2026-10-07)

1. Code type: timed random code, `/v3/keyboardPwd/get` with `keyboardPwdType=3`. The lock checks it by itself, so creating it does not need the gateway online, and the number of such codes is not limited (manuals.plus, not the official docs). Every pilot lock also has a Wi-Fi gateway, used for delete and change.
2. Trigger: the whole party is registered (`reservation.registration_completed_at`). This keeps the code as the compliance lever (owner, 2026-10-07, reversing an earlier lead-guest-only answer).
3. The guest link goes out by automated message the day before check-in, so a code is normally created at most a day or two ahead.
4. Guest mail carries the PIN, host in CC.
5. Check-in and checkout hours are set by the host per property.
6. A guest who arrives more than 24 h after check-in time: the code expires, and UbyHost does nothing. The guest page and mail say the code must be used for the first time within 24 h of check-in. No first-use check, no host mail, no fresh-code button. The host uses the TTLock app.
7. No "issue code anyway" button. The host uses the TTLock app.
8. The 30,000 calls a month are per developer app, shared by every UbyHost host.
9. Pilot on a few of the owner's properties. Built per host and per property, so other hosts only need the setting.

## 3. TTLock facts

All API facts, error codes and their UbyHost reactions live in [TTLOCK](../TTLOCK.md). Key points:

- `get` type 3 needs no gateway, is accurate to the hour, and must be used within 24 h of its start.
- `change` and `delete` work remotely through the gateway (type 2).
- Tokens last 90 days. A refresh returns a new pair. `10003`/`10004` mean refresh, `10011` means the host must reconnect.
- Every call's `date` must be within 5 minutes of TTLock's clock (`80000`).

## 4. How heavy is it

| Piece | Size (estimate) |
|---|---|
| `App/app/ttlock.py` HTTP client, token refresh, call budget | about 200 lines |
| `App/app/door_codes.py` states and reconciler | about 200 lines |
| 1 migration (3 tables, 4 apartment columns) | about 50 lines |
| 1 scheduler job | about 20 lines |
| Host UI: one settings card, one property section, one stay line (read-only) | 3 template blocks |
| Guest UI: one block on `guest/stay.html` | 1 template block |
| 2 mail kinds (guest code, host notice) | about 60 lines |
| New dependencies | none (`requests` and `zoneinfo` already used) |

When no property has a lock, the cost is one indexed SQL query a minute that returns nothing. The modules never import or touch UbyPort filing code (rule 1). A global kill switch `UBYHOST_DOOR_CODES=0` stops every TTLock call.

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
| `locks_json` | cached lock list (id, name), refreshed only on demand |
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
| `state` | §6 |
| `pin_enc` | `db.encrypt_field`, NULL after checkout |
| `provider_code_id` | TTLock `keyboardPwdId` |
| `valid_from`, `valid_to` | UTC ISO, from Prague local hours |
| `attempts`, `next_attempt_at`, `claimed_at` | retry and lease |
| `last_error` | short code only, never a response body |
| `issued_at`, `revoked_at`, `created_at`, `updated_at` | |

### `lock_api_usage`: the budget counter

`month TEXT`, `provider TEXT`, `calls INTEGER`, PK (`month`, `provider`). Incremented with `INSERT ... ON CONFLICT DO UPDATE SET calls = calls + 1`, which works on SQLite and Postgres.

### Retention (`App/app/retention.py`)

- `door_code.pin_enc`: NULL at `valid_to` + 1 day.
- `door_code` row: deleted with its reservation.
- `lock_account` tokens: deleted on disconnect or account deletion.

## 6. States

```
 registration complete, property has a lock, stay not over
                 |
                 v
   pending --claim--> issuing --ok--> issued
                        |  ^             |
                   error|  |retry        |
                        v  |             |
                      retrying           +--booking cancelled--> revoke_pending --ok--> revoked
                        |                |
              5 tries   v                +--dates moved--> change call, stays issued, new guest mail
                      failed  (host mail: "create a code in the TTLock app")
                                         |
                                  checkout + 1 day --> expired (pin_enc NULL)
```

Rules:

- One row per reservation (`UNIQUE`), created with `INSERT ... ON CONFLICT DO NOTHING`.
- A process claims a row with one conditional UPDATE (`WHERE id = ? AND state IN ('pending','retrying') AND next_attempt_at <= ? AND (claimed_at IS NULL OR claimed_at < lease_cutoff)`) and calls TTLock only if `db.execute_rowcount` returns 1. Two processes can never both create a code for one stay.
- Registration cleared after the code exists (a form went missing): nothing changes. The code stays, because the guest is still staying.
- A retry after a timeout first lists the lock's codes and adopts one named `UH-<door_code.id>`, so a timeout never creates a second code.
- Backoff 1, 5, 15, 60 and 240 minutes, then `failed` and one host mail.
- Dates moved: `change` with the new window. If 0008 finds that `change` does not work on a random code, then `delete` plus a new `get`, and the guest gets the new code by mail.
- A cancellation whose delete keeps failing (gateway offline): retries continue until the old `valid_to`, and the host gets one mail after 1 h saying "delete code 48•••93 in the TTLock app". A cancelled booking's code could otherwise open the door for the next guest.

## 7. API call budget (30,000 a month, shared by all hosts)

Calls happen only on events, never on polling.

| Event | Calls |
|---|---|
| Lead guest registered, code created | 1 |
| Cancelled after the code was created | 1 |
| Dates moved | 1 (or 2 if `change` cannot be used) |
| Retry after an error | 1 each, at most 5 |
| Timeout recovery (list codes) | 1 |
| Token refresh | 1, only near expiry or on an expired-token error |
| Host connects the account or taps "Refresh lock list" | 1 |
| Guest or host opens a page | 0 (reads the DB) |

Expected a little over 1 call per stay, so 30,000 calls cover about 25,000 stays a month across all hosts. The pilot will use a few hundred.

Guards in `ttlock.py`, which every call goes through:

- Below 80 % of the month: normal.
- 80 % to 95 %: no lock-list refresh. The owner gets one alert.
- Above 95 %: only create (for stays starting within 24 h) and delete. The owner gets an urgent alert.
- The counter shows on the admin operations page.

## 8. Security

### 8.1 Blocker: who gets the code

The door code is only as safe as the guest link. Today each property has one fixed link and one property PIN, shared with every guest. A claim proves that the claimer owns *some* e-mail address, not that they hold the booking. `reservation.phone_last4` is stored from the Airbnb feed but never checked. So a former guest who kept the link and PIN can pick a stay in the 2-day window, claim it, fill in made-up names and receive the next guest's door code. Door codes must not ship until this is closed.

Proposed fix (owner decision pending):

- **Airbnb stays** (feed has the phone's last 4 digits): the claim asks "Last 4 digits of the phone number on your booking". 3 wrong answers lock the stay and alert the host. A guess succeeds 3 times in 10,000.
- **Stays with no proof in the feed** (Booking.com, Agoda, manual stays): either the host releases the code with one tap after registration ("All guests registered for 12 to 14 Oct. Release the door code?"), or door codes are off for them. Default: host release.
- The check runs at claim time, so it also protects the guest data, not just the door.

### 8.2 The TTLock account

The access token can do anything the TTLock account can do on every lock in it. Proposed (owner decision pending): UbyHost creates a dedicated TTLock user per host with the User Register API, and the host shares only the rental locks with it as admin in the TTLock app. UbyHost never sees the host's own password, holds rights only on shared locks, and the host can cut it off with one tap. Whether a shared admin can call `get`, `change` and `delete` is checked in the 0008 owner test. Fallback: the host types their TTLock login once (§10), and the password is never stored.

### 8.3 Controls

- **PIN at rest.** Encrypted with `db.encrypt_field`, decrypted only while rendering the page or delivering the mail, NULL after checkout.
- **PIN in mail.** New mail kind `door_code`. The stored body holds a `{{door_code}}` marker, and the encrypted PIN sits in the payload, the same pattern as `{{claim_secret}}` in `App/app/mail.py`. The outbox row and the console mail log never hold the digits. Idempotency key `door_code:<reservation_id>:<valid_from>`, so a moved stay sends one new mail and nothing sends twice.
- **PIN on the guest page.** Shown only to a device that passed the existing claim and PIN gate for that reservation. No JavaScript. The response has `Cache-Control: no-store`.
- **Lock ownership.** A host can only pick a lock from their own account's cached list. The server checks on save that `lock_id` is in that list, so a hand-edited form cannot target another host's lock.
- **Tokens.** Encrypted, per host. Refresh with compare-and-swap on `token_version`. A failed refresh sets `reauth_needed` and mails the host. No token ever goes in `app.config`, env or logs.
- **Data sent to TTLock.** Lock id, validity window and the code name `UH-<id>`. No guest name, e-mail or reservation summary.
- **Logging.** Error code and door-code id only. A test asserts that no PIN or token reaches the log.
- **Audit.** One `audit` row per create, change and delete.
- **Privacy register.** TTLock (Sciener, Hangzhou) goes into the subprocessor register and the ROPA before the guest block ships. If data is stored outside the EU, the lawyer reviews the transfer basis first.

## 9. Flow

1. A guest saves the last missing form of the party.
2. In the same request, after the save is committed and `registration_completed_at` is set, `door_codes.on_registration_complete(reservation_id)` creates the row and tries one `get` with a 5 s timeout. On success the stay page shows the PIN in that same response, and the guest mail is queued in the transaction that stores the PIN. On failure the guest sees "Your door code is being prepared. Reload this page in a minute." and the worker retries.
3. The `door_codes` scheduler job (every minute, its own job id, so a TTLock outage never marks the mail job failed) runs `door_codes.reconcile()`. It retries due rows, handles cancellations and moves, and expires old PINs. It also creates rows the request missed (for example a stay completed by a scheduler tick), so correctness never depends on step 2.
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

Shown only when the host has a connected account. Otherwise one line: "Connect a smart lock in Settings."

```
Door code
[x] Send the guest a door code when every guest is registered
Lock            [Front door  v]
Check-in from   [15:00 v]     Check-out until [11:00 v]
```

### Host: stay detail (read-only line)

- "Door code 4821936 · valid 12 Oct 15:00 to 14 Oct 11:00"
- "Door code waits for registration"
- "Door code could not be created. Create one in the TTLock app."

### Guest: stay page block (under the "all done" card in `guest/stay.html`)

```
Your door code
  4 8 2 1 9 3 6
Works from Sat 12 Oct, 15:00 to Mon 14 Oct, 11:00.
Use it for the first time before Sun 13 Oct, 15:00.
We have sent it to j•••@gmail.com too.
```

While being prepared: "Your door code is being prepared. Reload this page in a minute." When it failed: "Your host will send you the door code." plus the host contact.

### Mails

- `door_code` (guest, host in CC): subject "Your door code for <property>". The code, the window and the first-use deadline in Prague time, the property's check-in info, the host contact.
- `door_code_notice` (host only): one of "could not be created", "could not be deleted after a cancellation". Each says what to do in the TTLock app.

## 11. Delivery sequence (one PR each)

| Task | What | Depends on |
|---|---|---|
| 0008 | Fill the gaps in `docs/TTLOCK.md` (lock list, passcode list, rate limits, processor). Owner tests admin sharing and a remote delete. No App change | none |
| 0009 | Foundation. Migration, `ttlock.py` (form POST, 5 s timeout, token CAS refresh, budget counter, kill switch), retention lines, ENVIRONMENT section. HTTP faked in tests, a fixture blocks real network calls | 0008 |
| 0010 | Host setup. Smart locks card, property door-code section, lock-ownership check. Browser and geometry tests | 0009 |
| 0011 | Issuing. `door_codes.py` states, reconciler job, first try on the save that completes registration, retries, failed notice. Test proves no write to `submission` or filing tables | 0010 |
| 0012 | Delivery. Guest stay block, `door_code` mail with marker, host stay line. Screenshots at 360, 390 and 1280 px | 0011 |
| 0013 | Lifecycle. Cancel, date move, PIN purge, admin usage panel | 0012 |
| docs | Subprocessor register, ROPA, privacy copy. Lawyer review if needed | before the pilot goes live |

Briefs for 0009 and later are written after the 0008 report.

## 12. Open questions

The unanswered TTLock facts are listed in [TTLOCK](../TTLOCK.md), section "Not stated in the supplied docs". Task 0008 answers them.

## 13. Why not the Gemini spec

| Gemini spec | Repo reality |
|---|---|
| Flask, SQLAlchemy, `current_app`, `flash()` | FastAPI, raw SQL through `App/app/db.py` |
| `POST /stay/<t>/submit` is the trigger | Guest URLs are `/l/{token}/{reservation_id}/...`, and stays complete in `reporting.refresh_registration_completed_at`, which a scheduler tick can also run |
| Overwrites `guest/confirm.html` | That is the claim confirmation page |
| Bootstrap classes, inline SVG | House CSS, light mode, geometry tests |
| One account in env, refreshed token in `app.config` | Web and worker are separate processes, and a restart loses the token |
| `if not reservation.passcode` guard | Two processes both pass the check |
| Plaintext `passcode` on `reservation` | Privacy first. Encrypted, purged after checkout |
| Guest name sent to TTLock | New personal data to a third party, for no gain |
| `boto3` send inside the request | The outbox has retries and idempotency |
| No cancel or date-move handling | iCal sync cancels and moves stays |
