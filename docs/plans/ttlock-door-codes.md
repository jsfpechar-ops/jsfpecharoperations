# Door codes (TTLock): architecture

Status: planning (orchestrator, 2026-10-07). Inputs: an owner-supplied Gemini spec (rejected, §13), the repo, a 3-advisor council, official TTLock docs pasted by the owner, and owner decisions.

## 1. What the feature is

A property can opt in to door codes. When every guest on the stay is registered, UbyHost asks TTLock for a timed code. The code is valid from the property's check-in hour on arrival day to its checkout hour on departure day. The guest sees it on the stay page at once and gets it by e-mail, with the host in CC. If the booking is cancelled or moved, UbyHost deletes or moves the code.

Everything else (a late guest, a new code, a manual exception) the host does in their own TTLock app. UbyHost automates only the routine.

A property without a lock sees no difference. No code runs and no API call is made for it.

## 2. Owner decisions (2026-10-07)

1. Code type (owner, 2026-10-08, final): **timed random codes** (`/v3/keyboardPwd/get`, type 3). Creating one is a cloud-only call: no gateway, no Bluetooth, about a second, and it works while the property's Wi-Fi is down, because the lock checks the code by itself. The PIN shows on the same screen as the last form. Back-to-back stays have different windows, so each gets its own code and nothing is ever reused or overwritten. Custom codes (`add`) were considered and rejected: they would make every stay depend on the gateway being online, only to cover cancellations within 24 h of check-in, which the platforms' policies practically rule out (owner). The gateway is used only for `change` and `delete`.
2. Trigger: the whole party is registered (`reservation.registration_completed_at`). This keeps the code as the compliance lever (owner, 2026-10-07, reversing an earlier lead-guest-only answer).
3. The guest link goes out by automated message the day before check-in, so a code is normally created at most a day or two ahead.
4. Guest mail carries the PIN, host in CC.
5. **The host must set the check-in and check-out hour** for each property before door codes can be switched on. There is no default; the switch is refused until both are set (owner, 2026-10-08).
5a. **One hour of margin on each side** (owner, 2026-10-08): a code works from 1 h before check-in to 1 h after check-out (`config.DOOR_CODE_BUFFER_HOURS`). It absorbs lock clock drift and the open question whether the lock applies daylight saving time. The property section shows this as a warning, and warns again when the margin makes back-to-back codes overlap (§10).
5b. **Lock time** (owner, 2026-10-08): every lock must run on Prague time. The host sets the lock's time zone and calibrates its clock in the TTLock app at setup (§12). UbyHost checks it three ways: the lock picker warns when a lock's `timezoneRawOffset` is not 3,600,000 (Prague without summer time); a weekly `queryDate` per lock, with `updateDate` when the clock is more than 2 minutes off (task 0013); and the 1 h margin above.
6. A guest who arrives more than 24 h after check-in time: the code expires, and UbyHost does nothing. The guest page and mail say the code must be used for the first time within 24 h of check-in. No first-use check, no host mail, no fresh-code button. The host uses the TTLock app.
7. No "issue code anyway" button. The host uses the TTLock app.
8. The 30,000 calls a month are per developer app, shared by every UbyHost host.
9. Pilot on a few of the owner's properties. Built per host and per property, so other hosts only need the setting.
10. Taken period (owner, 2026-10-10): a type-3 `get` that returns `-1026` is not retried, and the window is not shifted. The worker creates a custom code (`keyboardPwd/add`, `addType=2`) for that stay only. This is the only use of `add`. It supersedes the rejection of custom codes in item 1 for that one case. The normal stay stays a type-3 `get`. `-2018` does not fall through to `add`. UbyHost never calls `keyboardPwd/change` on a type-3 code. Full rules: §6. Brief: [0037](../tasks/0037-door-code-taken-period.md).

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
| `username` | the TTLock account UbyHost uses for this host, for display |
| `access_token_enc`, `refresh_token_enc` | `db.encrypt_field` |
| `token_expires_at` | UTC ISO |
| `token_version` | INTEGER, compare-and-swap on refresh |
| `status` | `ok`, `reauth_needed` |
| `locks_json` | cached lock list (id, name), refreshed only on demand |
| `locks_fetched_at`, `created_at`, `updated_at` | |

The login of the account UbyHost uses (pilot: the owner's spare TTLock account) is typed in once, used for one token call and never stored. The refresh token lasts 10 years, so a re-login is needed only after `10011`.

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
   pending --claim--> issuing --ok--> issued --checkout--> expired (pin_enc NULL after 1 day)
                        |  ^             |
                   error|  |retry        +--cancelled--> revoke_pending --> revoked (best effort, see below)
                        v  |             |
                      retrying           +--dates or hours moved--> a new code (custom add if the period is taken)
                        |
              5 tries   v
                      failed  (host mail: "create a code in the TTLock app")
```

Rules:

- One row per reservation (`UNIQUE`), created with `INSERT ... ON CONFLICT DO NOTHING`.
- A process claims a row with one conditional UPDATE (`WHERE id = ? AND state IN ('pending','retrying') AND next_attempt_at <= ? AND (claimed_at IS NULL OR claimed_at < lease_cutoff)`) and calls TTLock only if the row count is 1. Two processes can never both create a code for one stay.
- Every code is new. Back-to-back stays (one leaves at 11:00, the next arrives at 15:00) have different windows, so their codes never meet. UbyHost never changes or deletes the code of a stay that is not cancelled or moved.
- A retry after a timeout first lists the lock's codes (`searchStr=UH-<door_code.id>`) and adopts the match, so a timeout never creates a second code.
- Registration cleared after the code exists (a form went missing): nothing changes. The code stays, because the guest is still staying.
- Backoff 1, 5, 15, 60 and 240 minutes, then `failed` and one host mail. `-1026` is not in this retry list.
- A free window gets one type-3 code (`keyboardPwd/get`). It expires by itself. UbyHost does not delete it at checkout and does not call `keyboardPwd/change`.
- `-1026` on that `get` means the period is already taken (staging, 2026-10-08; the number is not in TTLock's published list). Do not call `get` again for that window. Do not shift the check-in or check-out hour. Do not reuse a cancelled stay's PIN. The guest save does not call the gateway. The worker calls `keyboardPwd/add` with `addType=2`, a new 7-digit code (no leading zero), `keyboardPwdType=3`, and the same start and end. `door_code.code_kind` becomes `custom`. A custom code has no 24-hour first-use rule, so the guest page and the guest mail omit that sentence.
- If `add` fails because the gateway is offline or busy, retry with the backoff above and keep trying `add`, not `get`. If it fails for permission (`-2018`), storage, or a second duplicate PIN (`-3007`), stop and send one host mail. The guest stays on the waiting line.
- Dates or hours changed after a code exists: create a new type-3 code for the new window. If that returns `-1026`, use the same custom `add` in that worker run. Then one best-effort delete of the old code. The old code belongs to the same guest, so leaving it is harmless. `-2018` stops further tries on that stay and sends one host mail. It does not trigger `add`.
- Cancelled (rare: guests register at most a day ahead): one `delete` attempt through the gateway, and one host mail: "This stay was cancelled after its door code was sent. The code may keep working until its end date." The next guest for those dates gets their own code by the rule above, never this PIN.
- 24 h first-use rule: the guest page and mail say "Use the code for the first time before <code start + 24 h>", where the code start already includes the 1 h margin. A later arrival is handled by the host in the TTLock app (owner).

## 7. API call budget (30,000 a month, shared by all hosts)

Calls happen only on events, never on polling. There is **no** extra job that lists or re-fetches PINs to “make sure they are still right”: a type-3 random code is a cloud algorithm (the lock often does not know it until first use), and `listKeyboardPwd` returns the digits. Unlock-record callbacks stay off for the same reason (PIN + arrival times).

Operations → Background jobs gets **one** new row, in task 0012, not in 0008:

| JOB | RUNS EVERY |
|---|---|
| door codes | 1 min |

That job (`door_codes.reconcile`) retries issue, adopts a code by name after a timeout (`find_code_by_name`), expires local PIN state, and later (task 0015) checks **at most one lock clock per run**. Clock drift is the reliability spend; PIN polling is not. A TTLock outage of this job must not mark the mail job failed (own job id).

| Event | Calls |
|---|---|
| Registration complete, code created (`get`) | 1 |
| Same period already taken (`get` returns `-1026`, then one `add`) | 2 |
| Cancelled after the code was created | 1 |
| Dates or hours moved (`get`, or `get` plus `add`) | 1 or 2 |
| Stay over | 0 (the code expires by itself) |
| Lock clock check (`queryDate`), per lock per week | about 4 a month per lock |
| Retry after an error | 1 each, at most 5 |
| Timeout recovery (list codes) | 1 |
| Token refresh | 1, only near expiry or on an expired-token error |
| Host taps Set up (register the UbyHost user, get a token) | 2 |
| Host taps Check for locks | 1 |
| Host taps Remove (delete the UbyHost user) | 1 |
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

**Owner decision 2026-10-07: accepted for the pilot, no claim check yet.** Reasons: the pilot runs only on the owner's properties, Booking.com feeds carry no data to check, and the owner prefers to keep the property PIN as the only gate. What limits the risk meanwhile:

- The guest mail goes to the host in CC, with the guest names. A stranger's names are visible before check-in, and the host can delete the code in the TTLock app.
- The host can change the property PIN (existing feature). The door-code section on the property page says, once: "Anyone with this property's guest link and PIN can register for an upcoming stay and receive its door code. Change the PIN from time to time."
- The door-code terms (Guide) state this risk to every host who connects. The booking-code check (the guest types the booking confirmation number, compared with the code from the feed) is the parked design for when more hosts join (owner, 2026-10-08: no pilot list, the owner is the only host today).

### 8.2 The TTLock account (owner, 2026-10-08)

There is no pilot list and only one way to connect. Every host already has a TTLock account; they **share their locks with UbyHost** instead of giving UbyHost a login.

- On Properties → Property tools → Smart locks the host accepts the door-code terms and taps Set up. UbyHost creates a TTLock user for that host (User Register API, random name and password, password stored encrypted) and shows its name with a copy button.
- In the TTLock app, as the account that owns the lock, the host taps the lock, then Authorized Admin, then Create Admin, and sends a Permanent admin eKey to that name with "Manage their own users only" on. A plain eKey is not enough, and the screen has no Remote unlock switch (UbyHost never calls an unlock endpoint anyway). Then "Check for locks" lists the locks with name, ID (as in the TTLock app under Basic information) and battery.
- The host's TTLock password never reaches UbyHost. UbyHost's user holds rights only on the shared locks and cannot open a door remotely. One user per host, so a host's list can only ever contain locks that host shared; nobody can attach someone else's lock, and nobody types a lock ID.
- Remove deletes the TTLock user, which also deletes every eKey shared with it. A dead refresh token is recovered by logging in again with the stored password, with no host action.
- The steps for hosts live in one place: the Guide section "Door codes with TTLock" (task 0016). Pages link to it.
- `ttlock.py` calls only an allowlist of endpoints (`/oauth2/token`, `/v3/user/register`, `/v3/user/delete`, `/v3/key/list`, `/v3/lock/listKeyboardPwd`, `/v3/keyboardPwd/get`, `/add`, `/change`, `/delete`, `/v3/lock/queryDate`, `/v3/lock/updateDate`), and a test fails if any other path appears. `/add` is the taken-period fallback only (§6). Never called: `/v3/lock/detail` and `/v3/key/get` (super passcode in the response), `/v3/key/getUnlockLink` (remote unlock link), `/v3/key/send` and `/v3/key/authorize` (handing out access). `lockData` and passcode digits from list responses are dropped while parsing, and no raw response is ever logged ([TTLOCK](../TTLOCK.md#secrets-in-ttlock-responses-never-store-never-log)).
- **Pre-build check (owner, §12a):** the TTLock app's Send eKey screen must accept a prefixed API user name. The API documents it; the app screen is unconfirmed.

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
2. In the same request, after the save is committed and `registration_completed_at` is set, `door_codes.on_registration_complete(reservation_id)` creates the row and tries one `get` (cloud only, 5 s timeout). On success the stay page shows the PIN in that same response, and the guest mail is queued in the transaction that stores the PIN. On `-1026` the request stops there; the worker creates a custom code (§6). On any other failure the guest sees the waiting line and the worker retries `get`.
3. The `door_codes` scheduler job (every minute, its own job id, so a TTLock outage never marks the mail job failed) runs `door_codes.reconcile()`. It retries due rows, handles cancellations and moves, and expires old PINs. It also creates rows the request missed (for example a stay completed by a scheduler tick), so correctness never depends on step 2.
4. iCal sync never calls TTLock. It only changes `reservation`, and the reconciler sees the difference on its next run.

Gateway calls (`change`, `delete`, and the weekly lock-clock check) run only in the worker, one at a time, with a 35 s timeout, because TTLock allows one remote operation per lock at a time and waits up to 30 s itself ([TTLOCK](../TTLOCK.md#how-the-gateway-fits)).

The UbyPort submit path is not changed in any step.

## 10. How it looks

All screens use existing components and house CSS, light mode, and work without JavaScript.

### Host: Properties → Property tools → Smart locks (new page, `/smart-locks`)

Not in the main navigation and not in Settings: it sits next to Guest links and Automation, and only while the feature is on.

```
Smart locks
Optional. With a TTLock lock and gateway, guests get a timed door code once everyone is registered.

-- not set up --
[ ] I accept the door code terms. Read them          (Set up)
Step-by-step guide

-- set up, nothing shared yet --
Share your locks with UbyHost
In the TTLock app, open each rental lock, tap Send eKey and enter this account:
  abcd_uh3f9c2a71d04e8b5c   [copy]
Turn on Authorized admin, turn off Remote unlock, leave the end date empty.
(Check for locks)

-- locks found --
Front door · ID 532323 · battery 85 % · used by: Studio Karlín
Back door  · ID 532401 · battery 60 % · not used by a property yet · ! Time zone is not Prague
(Check for locks)  (Remove)
```

### Host: Property → Door code (new `<details class="panel property-section" id="door-code">`)

Shown on every existing property while the feature is on. Without a connection: one line and a "Set up smart locks" button that opens the Smart locks page and comes back here after "Check for locks". With a connection but no shared lock: one line and a link to the page.

```
Door code
[x] Send the guest a door code when every guest is registered
Lock            [Front door  v]          ! Lock time zone is not Prague. Fix it in the TTLock app.
Check-in from   [-- v]  (required)       Check-out until [-- v]  (required)

  Codes work from 1 hour before check-in to 1 hour after check-out,
  so a slightly wrong lock clock never locks a guest out.
  ! With these times the leaving guest's code still works when the next guest arrives.   (only if check-in - check-out < 2 h)

  Anyone with this property's guest link and PIN can register for an upcoming stay
  and receive its door code. Change the PIN from time to time.
```

Validation: both hours 0 to 23 and required when the box is ticked. The overlap warning shows when check-in hour minus check-out hour is less than 2 * `DOOR_CODE_BUFFER_HOURS`; it is a warning, not a refusal.

### Host: stay detail (read-only line)

- "Door code 4821936 · works 12 Oct 14:00 to 14 Oct 12:00" (the real window, margin included)
- "Door code waits for registration"
- "Door code could not be created. Create one in the TTLock app."

### Guest: stay page block (under the "all done" card in `guest/stay.html`)

```
Your door code
  4 8 2 1 9 3 6
Check-in from Sat 12 Oct, 15:00. Check-out by Mon 14 Oct, 11:00.
Use the code for the first time before Sun 13 Oct, 14:00, or it stops working.
We have sent it to j•••@gmail.com too.
```

While being prepared: "Your door code is being prepared. Reload this page in a minute." When it failed: "Your host will send you the door code." plus the host contact.

### Mails

- `door_code` (guest, host in CC): subject "Your door code for <property>". The code, the window and the first-use deadline in Prague time, the property's check-in info, the host contact.
- `door_code_notice` (host only): one of "could not be created", "could not be deleted after a cancellation". Each says what to do in the TTLock app.

## 11. Delivery sequence (one PR each, in order)

| Task | What | Visible change |
|---|---|---|
| [0008](../tasks/0008-door-codes-schema.md) | Schema, settings, PIN retention step | none |
| [0009](../tasks/0009-ttlock-client.md) | TTLock client: allowlist, timeouts, tokens, budget, get/change/delete, lock list | none |
| [0010](../tasks/0010-smart-locks-page.md) | Properties → Property tools → Smart locks: accept terms, Set up, share eKeys, check for locks, remove | every host, once the feature is on |
| [0011](../tasks/0011-property-door-code-section.md) | Property → Door code section (tick box, lock, required hours, warnings) | per property, off by default |
| [0012](../tasks/0012-door-codes-issuing.md) | Issuing: hook after the guest save, background job, retries, alerts, test mode (`UBYHOST_DOOR_CODES_LIVE`) | codes for manual stays |
| [0013](../tasks/0013-door-code-delivery.md) | Guest stay block, guest mail with host CC, host stay line | guest sees the code |
| [0014](../tasks/0014-door-code-cancel-and-move.md) | Cancellations, date and hour changes, host notice mails | |
| [0015](../tasks/0015-lock-clock-and-usage.md) | Weekly lock clock check, call counter, budget alerts | admin only |
| [0016](../tasks/0016-door-codes-guide-and-legal.md) | Guide "Door codes with TTLock", door-code terms, guest privacy paragraph, subprocessor row, ROPA | every host and guest of a door-code property |
| [0037](../tasks/0037-door-code-taken-period.md) | Taken period: custom `add` from the worker; no `change`; no retry of `-1026` | guest still sees a code when the same dates are booked again |
| legal | [DOOR_CODES_LEGAL](../privacy/DOOR_CODES_LEGAL.md): SCCs with TTLock before any other host uses door codes; TTLock into DPA §11 at the next revision | |

## 12a. Pre-build check (owner, before task 0009)

One check decides the account model, so it runs before any code is written. It takes about 10 minutes on a Mac, in Terminal. The client secret stays on your machine: never paste it into a chat.

1. Make a test TTLock user (replace the two placeholders):
   ```
   PW=$(openssl rand -hex 12)
   curl -s https://euapi.ttlock.com/v3/user/register \
     --data-urlencode "clientId=CLIENT_ID" --data-urlencode "clientSecret=CLIENT_SECRET" \
     --data-urlencode "username=uhtest1" --data-urlencode "password=$(md5 -q -s "$PW")" \
     --data-urlencode "date=$(($(date +%s)*1000))"
   ```
   The answer is like `{"username":"abcd_uhtest1"}`. Note that name.
2. In the TTLock app: open a lock, Send eKey, enter `abcd_uhtest1`, Authorized admin on, Remote unlock off, Send. Write down whether the app accepts it.
3. Delete the test user:
   ```
   curl -s https://euapi.ttlock.com/v3/user/delete \
     --data-urlencode "clientId=CLIENT_ID" --data-urlencode "clientSecret=CLIENT_SECRET" \
     --data-urlencode "username=abcd_uhtest1" --data-urlencode "date=$(($(date +%s)*1000))"
   ```
4. Tell the orchestrator whether step 2 worked. If it did not, the fallback is that each host makes a spare TTLock account, shares to it, and types that spare account's login once; tasks 0009 and 0010 change accordingly.

## 12. Production acceptance test (owner, before going live)

Everything below runs on the real server in **test mode**: only stays added by hand get a code, so no real guest is affected. Write pass or fail next to each check. Go live only when every check passes.

**Setup**

1. Deploy up to tasks 0015 and 0016. In the server `.env`: `UBYHOST_TTLOCK_CLIENT_ID`, `UBYHOST_TTLOCK_CLIENT_SECRET`, `UBYHOST_DOOR_CODES=1`. Leave `UBYHOST_DOOR_CODES_LIVE` unset. Restart.
2. TTLock app, for each pilot lock: set the time zone to Prague and calibrate the clock (lock, Settings, Lock Time).
3. Follow the Guide section "Door codes with TTLock" as a new host would: Properties → Property tools → Smart locks, accept the terms, Set up, send each pilot lock's eKey to the shown name, Check for locks. Every pilot lock is listed with its name, ID and battery, and no time-zone warning. Note anything in the Guide that was unclear.
4. Each pilot property → Door code: tick the box, pick the lock, set check-in 15:00 and check-out 11:00, save. The section shows the test-mode line.

**Checks**

| # | Do | Expect |
|---|---|---|
| 1 | Add a stay by hand for tomorrow, 1 guest. Open the guest link on your phone, claim it with your own e-mail, fill in the form. | The stay page shows the door code within seconds. A mail with the code arrives, with the host address in CC. The host stay page shows "Door code … works … 14:00 to … 12:00". |
| 2 | Arrival day, 13:55: type the code. Then at 14:05. | 13:55: does not open. 14:05: opens. It keeps opening after that. |
| 3 | Departure day, 12:05: type the code. | Does not open. |
| 4 | A real calendar stay on a pilot property completes its registration. | No code, no mail, nothing on its stay page (test mode). |
| 5 | Change the end date of a hand-added test stay by one day. | Within 2 minutes the guest gets one new mail with the new check-out; the code opens on the extra day. |
| 6 | Cancel (archive) a hand-added test stay that has a code. | You get "door code deleted after a cancellation". Typing the code does not open the door (this settles the open question from `docs/TTLOCK.md`). |
| 7 | Unplug the gateway. Register another hand-added test stay. Then cancel it while the gateway is still unplugged. Plug it back. | The code still appears at once (no gateway needed). After about 20 minutes (three tries) you get "delete a door code in the TTLock app". |
| 8 | Smart locks → Remove. Then Set up again and share one lock again. | After Remove: the eKeys are gone from the TTLock app and door codes on the properties are off. After setting up again: the lock is back after Check for locks. |
| 9 | Admin → Operations. | "TTLock calls this month" shows a small number and "Test mode". |
| 10 | On the server, search the app logs for one of the test PINs (the orchestrator gives the exact command for your setup). | 0 matches. |
| 11 | After the next daylight-saving change (25 Oct 2026), repeat check 2 on a new test stay. | Same result. |

**Go live**

1. Only after every check passed: set `UBYHOST_DOOR_CODES_LIVE=1` in `.env` and restart.
2. Watch the CC copy of the first real guest's mail.
3. Before any other host uses door codes: SCCs with TTLock signed ([DOOR_CODES_LEGAL](../privacy/DOOR_CODES_LEGAL.md) section 9).

**Switch off at any time**

- One property: untick its Door code box.
- Everything: set `UBYHOST_DOOR_CODES=0` and restart. No TTLock call is made after that, and codes already sent keep working until their end time.

## 13. Open questions

The unanswered TTLock facts are listed in [TTLOCK](../TTLOCK.md), section "Not stated in the supplied docs". Task 0008 answers them.

## 14. Why not the Gemini spec

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
