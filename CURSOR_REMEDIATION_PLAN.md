# UbyHost — remediation plan

Companion to `UBYHOST_CODE_AUDIT.md`. That document says what is wrong; this one
says what to do, in what order, and how to know each piece is finished. Written
to be handed to an AI agent with repo access.

Finding numbers in brackets — e.g. `[F2]` — refer to the audit's numbered
findings.

---

## Rules for the executing agent

Read these before touching anything.

1. **Read `AGENTS.md` and `docs/DESIGN.md` first.** Repo policy: no dark mode,
   no `prefers-color-scheme` dark styling. Run tests from `App/` with
   `.venv/bin/python -m pytest tests -q`. Do **not** set `PYTHONPATH=App` —
   `AGENTS.md` explains why it breaks collection on macOS.
2. **One phase per branch, one branch per PR.** Do not combine phases. Phase 1
   must be reviewable on its own because it is the part that fixes missed
   filings.
3. **No opportunistic refactoring.** If you notice something outside the work
   item you are on, add it to a `FOLLOWUPS.md` at the repo root and move on. The
   dead-code and duplication work has its own phase and its own review.
4. **Every work item ships with its test.** A behaviour change with no test that
   would have caught the old behaviour is not finished. Several items below exist
   *because* the behaviour was untested.
5. **Never break EN/CS key parity.** `host_i18n.STRINGS`, `_INTERFACE_STRINGS`
   and `i18n.STRINGS` are currently at exact parity (674/674, 398/398, 216/216).
   Every new user-facing string needs both languages in the same commit.
6. **Do not weaken an existing control to make a test pass.** If a test fails
   because you tightened something, fix the test.
7. **Migrations are append-only.** New columns go in *both* the `SCHEMA` literal
   and the `ADDED_COLUMNS` tuple in `App/app/db.py`, at the end, never reordered.
   `NOT NULL` needs a `DEFAULT`. This mechanism cannot rename, drop, or
   transform data — anything that needs a data migration needs a script (see
   Phase 2).
8. **Stop and ask before implementing anything in "Decisions needed" below.**
   Four items are product or legal calls, not engineering calls. Guessing them
   wrong is worse than leaving them.

---

## Decisions needed from the owner before coding starts

These block specific work items. Everything else can proceed without them.

| # | Question | Blocks | Why it can't be guessed |
| --- | --- | --- | --- |
| D1 | When a feed moves a booking's dates, should an already-collected signature be **kept** (it signed the old dates) or **wiped** (it no longer describes the stay)? | W1.1 | Current code wipes silently. Wiping is legally defensible — the form the guest signed states the dates. Keeping is friendlier. The fix differs: "keep + alert" vs "wipe + alert + re-invite". |
| D2 | What does UbyPort error **112 (reported late)** mean for the register — does it hold the record or refuse it? | W4.2 | Decides whether `blocked` + "Rejected" is right, or whether a late-but-accepted filing needs its own terminal state. This is a question for the Foreign Police, not for the code. |
| D3 | Is the 3-working-day window counted **from** the arrival day or from the day after? | W1.4 | `add_working_days` currently does not count the arrival day, so a Monday check-in yields Thursday 23:59:59. The stricter reading of §100(c) of Act 326/1999 gives Wednesday. Not a legal opinion — needs counsel or a citation. |
| D4 | Should the guest link keep reaching **old incomplete reservations** indefinitely? | W3.5 | `tests/test_claim_mail.py:401` asserts it does, so it looks deliberate. If intended, it needs a time bound; if not, it is an access-control bug. |

---

## Phase 1 — Stop silent missed filings

**Why first:** these are the five independent paths by which a legally-deadlined
report never goes out, with the host never told. Everything else in this repo is
recoverable; these are not.

**Branch:** `fix/missed-filing-paths`

### W1.1 — Calendar date change must not silently destroy a signature `[F2]` — Critical

**Files:** `App/app/icalsync.py:300-316`, `App/app/alerts.py`, `App/app/host_i18n.py`, `App/app/claim.py`

Depends on **D1**.

If D1 = *wipe*: keep the existing `UPDATE`, and add, in the same block:
- `alerts.raise_alert("critical", "dates_changed_resign", ..., dedupe_key=f"dates_changed_resign:{existing['id']}", apartment_id=..., reservation_id=...)`, with the message and detail taken from `host_i18n` (see W5.4 — do not add another English f-string).
- A re-invite through the existing outbox (`claim.py`), gated on the reservation having a claimed e-mail, using an idempotency key that includes the new dates so a second date change sends a second invite but a re-sync does not.
- Resolve the alert when the guest re-signs (in the guest `/save` path).

If D1 = *keep*: drop `signature_png = NULL, signed_at = NULL` from the `UPDATE`,
keep the `stay_from`/`stay_to` update, and still raise the alert — the host needs
to know the filed dates moved.

Either way, **narrow the `WHERE`**: the current statement flattens *every*
non-`sent` guest on the reservation to the feed's range, destroying per-guest
stay windows that legitimately differ (a guest leaving early). Only touch guests
whose `stay_from`/`stay_to` still equal the reservation's **old** values.

**Tests:** `App/tests/test_icalsync.py`
- Dates change → alert exists with the expected kind and dedupe key.
- Dates change → a guest whose `stay_from` differed from the reservation keeps their own dates.
- Guest re-signs → alert resolves.
- Assert the chosen D1 behaviour explicitly, so the decision is recorded in a test.

**Done when:** a date change on a stay with a signed, complete guest produces a
host-visible alert, and no state change is discoverable only from the log.

### W1.2 — The iCal poll job must actually run `[F1]` — Critical

**File:** `App/app/scheduler.py:66-104`

- Remove `next_run_time=None` from the `ical` job registration; give it
  `next_run_time=_soon()` like `photo_sweep` already has.
- Delete the `if db.query_one("SELECT 1 ... FROM ical_feed WHERE active = 1")`
  conditional un-pause at `:92-93` — it is the whole bug. A sync with no feeds
  is a no-op and costs nothing.
- Make `_soon()` timezone-aware: `datetime.now(ZoneInfo(config.TIMEZONE)) + timedelta(seconds=20)`.
  The scheduler runs in `Europe/Prague` and is currently handed a naive
  `datetime.now()`.

**Tests:** new `App/tests/test_scheduler.py` — the first scheduler test in the
repo. `conftest.py:32` disables the scheduler globally, so this file must
construct one directly rather than relying on app startup.
- After `start()`, `get_job("ical").next_run_time` is not `None`.
- Same with zero `ical_feed` rows present.

**Done when:** a fresh install that adds its first calendar polls on the normal
interval without a restart.

### W1.3 — A dying background job must be visible `[F: scheduler.py:14-63]` — High

**File:** `App/app/scheduler.py:14-63`

Each of the five job bodies currently ends `except Exception: log.exception(...)`.
Add an alert raise in each handler, kind `job_failed`, dedupe key
`job_failed:{job_id}`, level `critical` for `deadlines` and `submit` (losing
those loses compliance monitoring) and `warning` for the rest. Resolve the alert
at the top of the next successful run.

**Tests:** `App/tests/test_scheduler.py` — monkeypatch a job's callee to raise,
run the job function directly, assert the alert; then let it succeed and assert
the alert resolves.

**Done when:** the deadline watch cannot die silently.

### W1.4 — Anchor the deadline on the date that actually gets filed `[F39]` — High

**Files:** `App/app/deadlines.py`, `App/app/reporting.py:963-1016`, `App/app/routes/admin.py:140,154,1271`, `App/app/templating.py:92`

Also confirm **D3** before changing `add_working_days`; the anchor fix below is
independent of D3 and should ship regardless.

The deadline currently runs from `reservation["date_from"]` while the record
filed with the police carries `guest["stay_from"]` (`reporting._stay_dates:62-69`).
`housebook.py:99-104` already does the right thing with `COALESCE`.

- Add a helper — `reporting.reservation_deadline_anchor(reservation)` — returning
  the **earliest** `stay_from` among that reservation's non-archived guests,
  falling back to `reservation["date_from"]` when none is set. Earliest, because
  the statutory clock starts at the first arrival.
- Route all five call sites through it.
- Keep `deadlines.reporting_deadline(check_in)` as the pure function; only its
  input changes.

**Tests:** `App/tests/test_deadlines.py`
- A guest whose `stay_from` is two days before `reservation.date_from` produces a deadline two days earlier, and `urgency` flips accordingly.
- A reservation with no guest dates is unchanged.
- Multiple guests with different `stay_from` → earliest wins.

**Done when:** the dashboard's deadline and the filed `cFrom` cannot disagree.

### W1.5 — Guests must not be able to suppress the automatic filing `[F22]` — High

**Files:** `App/app/routes/guest.py:852-977`, `App/app/reporting.py:426-470`

A link holder can raise `declared_guests` to 60; `refresh_registration_completed_at`
then never fires because `filled >= expected` is never true, so immediate-mode
automation is suppressed indefinitely with no alert.

Pick one (prefer the first, it is smaller and closes the hole completely):
- **Cap the increase.** Allow a guest to *set* `declared_guests` once when it is
  `NULL`, and to lower it; reject an increase from a guest-authenticated request.
  Host override (`expected_guests_override`) keeps working as today.
- **Or** decouple the gate: set `registration_completed_at` when every *existing*
  guest form is complete and no form has been added for N hours, and raise a
  `headcount_mismatch` warning when `filled < expected`.

Either way, add a `headcount_mismatch` warning when a reservation sits with
`filled < expected` past its deadline anchor — otherwise "waiting for guest" is
indistinguishable from "suppressed".

**Tests:** `App/tests/test_guest_navigation.py`
- A guest raising `declared_guests` is rejected (or does not prevent completion, per the chosen option).
- Completion still fires on the normal path — regression guard.

### W1.6 — One bad feed must not stop every apartment `[F8]` — High

**File:** `App/app/icalsync.py:236-254`, `:402-411`

- Wrap `sync_feed(feed)` in `sync_all`'s loop in `try/except Exception`, count it
  into `totals["errors"]`, record it on the feed row, and continue to the next
  feed.
- Widen `sync_feed`'s own `except (FeedError, ValueError)` to also catch
  `Exception`, recording `last_status='error'` and raising `feed_error` as it
  already does for the narrow cases. Keep the narrow branch for its specific
  message if you like, but nothing may escape.
- Ensure `db.set_setting("last_ical_sync", ...)` at `:410` runs even when feeds
  errored.

**Tests:** `App/tests/test_icalsync.py` — three feeds, the middle one raising
`AttributeError`; assert feeds one and three are reconciled, the middle feed's
row records the error, and `last_ical_sync` advanced.

### W1.7 — Make the partial-feed guard proportional `[F3]` — High

**File:** `App/app/icalsync.py:340-376`

`if candidates and not seen_uids` protects only the *fully* empty response. A
feed that returns 1 of 10 events cancels the other nine.

- Replace with a ratio guard: if `len(seen_uids)` is below a threshold fraction
  of `len(candidates)` (start at 50%, make it a module constant, not an env var
  — see W5.3 on knobs nobody sets), retain **all** stays, mark the feed
  `last_status='suspect'`, and raise a `feed_incomplete` warning.
- Keep the existing per-stay cancellation path for the normal case.
- While in this function: `date.today()` at `:342` and `:201` must become
  `deadlines.local_now().date()` `[F10]`.

**Tests:** `App/tests/test_icalsync.py`
- 10 stays stored, feed returns 1 → nothing cancelled, alert raised, status `suspect`.
- 10 stored, feed returns 9 → the missing one is cancelled as today.
- Fully empty feed → existing retention behaviour preserved.

**Phase 1 exit criteria:** every path in §5 of the audit ("Can a report be …
never sent?") either cannot happen or raises a host-visible alert. All new tests
green. No new untranslated user-facing string.

---

## Phase 2 — Guest passport data at rest

**Why second:** the highest-severity finding in the audit, but it needs a real
data migration, so it wants its own PR and its own careful review rather than
riding along with Phase 1.

**Branch:** `fix/pii-at-rest`

### W2.1 — Give the submission XML a deletion path `[F35]` — Critical

**Files:** `App/app/housebook.py:685-699`, `App/app/db.py`, `App/app/routes/admin.py:2303`, `App/app/scheduler.py`

There is no `DELETE FROM submission` anywhere in the codebase. The request
envelope holds every reported guest's passport number and outlives the six-year
purge of the guest row.

- Add `reporting.purge_submission_payloads(owner_user_id=None, days=90)`: set
  `request_xml = NULL, response_xml = NULL` on submissions older than `days`
  whose state is terminal. Keep `receipt_pdf` and `pseudo_stamp` — those are the
  evidence the host must be able to produce.
- Extend `housebook.purge_expired` to delete `submission` rows that have no
  surviving `guest` rows after the guest purge.
- Call the payload purge from the existing `photo_sweep` job (it already runs
  every 12 h and already handles retention) and from the Settings purge button.
- `docs/OPERATIONS.md` already documents this gap — update that section to
  describe the new behaviour in the same commit.

**Tests:** `App/tests/test_retention.py`
- A submission older than the window has its XML nulled and its receipt kept.
- A recent submission is untouched.
- A submission whose guests were all purged is deleted.
- Cross-owner isolation: owner A's purge does not touch owner B's rows.

### W2.2 — Encrypt the travel-document fields `[F48]` — Critical

**Files:** `App/app/db.py`, `App/app/routes/guest.py`, `App/app/routes/admin.py`, `App/app/reporting.py`, `App/app/housebook.py`, new `App/scripts/migrate_encrypt_doc_fields.py`

Scope it to `doc_number` and `visa_number` first. Names and birth dates are a
larger surface (they appear in search, sort and PDF paths); do those in a
follow-up if the owner wants them.

This cannot use `ADDED_COLUMNS` — that mechanism adds columns, it does not
transform data. Sequence:

1. Add `doc_number_enc`, `visa_number_enc` (TEXT) to `SCHEMA` **and** the end of
   `ADDED_COLUMNS`.
2. Add `db.encrypt_field`/`db.decrypt_field` wrapping the existing Fernet
   helpers, with `decrypt_field` falling back to the plaintext column while both
   exist.
3. Write through both columns; read through the helper.
4. Ship a one-shot backfill script (`App/scripts/`) that encrypts existing rows
   and blanks the plaintext columns, idempotent and re-runnable, with a dry-run
   flag. Run it as a deploy step, not at import.
5. **Only in a later release**, once production is confirmed backfilled, stop
   writing the plaintext columns.

**Hard requirement:** `db.decrypt_secret` currently returns `""` on
`InvalidToken` `[F50]`. Do **not** reuse that behaviour here. A guest passport
number that fails to decrypt must raise, not silently become empty — an empty
`cDocN` filed with the police is worse than an error.

**Tests:** new `App/tests/test_pii_encryption.py`
- Round-trip through the guest save path.
- Stored value in the DB file is not the plaintext (assert the raw column does not contain the number).
- The backfill script is idempotent.
- A wrong key raises on read rather than returning empty.
- `reporting.guest_payload` still produces the correct `cDocN`.

### W2.3 — Archiving a guest must delete their passport scan `[F28]` — High

**File:** `App/app/routes/admin.py:1752-1754`

Add the `passport_photos.delete_photo(guest_id)` call that `guest_delete:1805`
already has. One line plus a test.

**Tests:** `App/tests/test_passport_photos.py` — archive a guest with a photo on
disk, assert the file is gone.

### W2.4 — Stop storing working claim links in cleartext `[F29]` — High

**Files:** `App/app/claim.py:242-257`, `App/app/mail.py:172-193`, `:305-316`

The claim secret is hashed in `reservation_claim` and then stored in plaintext in
`email_outbox.payload` and `console_mail_log.body_text` for 14 days, and shown
to hosts via `recent_console_messages`.

- Store a **placeholder** in the outbox payload and substitute the secret at send
  time from a short-lived in-memory value, or drop the retention to hours rather
  than days for rows whose `kind` carries a secret.
- Redact the `#c=` fragment in `console_mail_log.body_text`.
- `tests/test_claim_mail.py:296-318` currently asserts the cleartext behaviour as
  intended — that test must be rewritten, not deleted.

---

## Phase 3 — Guest access control

**Branch:** `fix/guest-access-control`

### W3.1 — CSRF on guest POSTs, and stop disabling it outside production `[F17, F18]` — High

**Files:** `App/app/routes/guest.py:30`, `App/app/templating.py` (`render_guest`), `App/app/security.py:173-184`, every `App/app/templates/guest/*.html` with a form, `App/app/static/csrf.js:13`

- Put `csrf_token` into the `render_guest` context.
- Add the `_csrf` hidden field to every guest form template.
- Remove the `/l/` exclusion from `csrf.js:13`.
- Attach a CSRF dependency to the guest router — either reuse
  `security.protect_host_post` or add a `protect_guest_post` that shares the
  token machinery.
- Delete the `if config.DEPLOYMENT != "production": return` early-out at
  `security.py:177-178`. Enforce everywhere.
- Expect test churn: existing tests POST without tokens. Fix the tests (add a
  conftest helper that fetches a page and extracts the token) — do **not** keep
  the production-only escape hatch to avoid the churn.

**Tests:** new `App/tests/test_guest_csrf.py`
- Each guest POST without a token → rejected.
- With a valid token → succeeds.
- Cross-site `Origin` → 403.

### W3.2 — Bound guest-supplied stay dates `[F19]` — High

**Files:** `App/app/routes/guest.py:1188-1189`, `App/app/validation.py`

`stay_from`/`stay_to` are hidden fields taken verbatim, land in the police record
as `cFrom`/`cUntil`, and drive photo retention via
`COALESCE(g.stay_to, r.date_to)`.

- Validate both against the reservation's range server-side. Reject outside it
  with a translated field error rather than silently clamping — a guest who
  genuinely arrives early should be told to ask the host, not have their date
  rewritten.
- Allow an explicit tolerance only if the product wants it, as a named constant.

**Tests:** `App/tests/test_host_guest_form.py` — a POST with `stay_from` a year
before the booking is rejected; the in-range case is unchanged.

### W3.3 — Validate the signature properly `[F20]` — High

**Files:** `App/app/routes/guest.py:1190-1192`, `:1209-1210`, `App/app/routes/admin.py:1502-1509`, `App/app/validation.py`, `deploy/lightsail/caddy/Caddyfile*`

`startswith("data:image/")` is the entire check. `passport_photos.py:64-84`
already shows the right shape for this repo.

- Add `validation.parse_signature_data_url(value)`: MIME allow-list
  (`image/png`, `image/jpeg`), base64 decode, byte-length cap (start at 256 KB),
  magic-byte check. Reject `image/svg+xml`.
- Use it in both the guest and host save paths — and put it in **one** place;
  the two paths currently duplicate this logic.
- Add `max_request_body` to the Caddyfiles.
- Guard the re-render at `templates/guest/form.html:235` the way
  `guest_form_admin.html:209` already does `[F33]`.

**Tests:** `App/tests/test_validation.py` and `test_host_guest_form.py`
- `data:image/svg+xml,...` rejected.
- `data:image/png;base64,<not-a-png>` rejected.
- Oversized payload rejected.
- A valid canvas PNG accepted, and `guest_has_signature` agrees.
- A rejected signature does **not** unlock the form (`guest_form_locked`).

### W3.4 — Make the claim secret single-use `[F21]` — High

**File:** `App/app/claim.py:310-333`

`confirm()` leaves `token_hash` intact and accepts `state IN (PROVISIONAL, CLAIMED)`,
so an e-mailed secret works forever, unlimited times.

- On successful confirm, clear `token_hash` (the `ubyhost_claim` cookie carries
  access from then on) or rotate it and bump `token_version`.
- Check `token_version` in `confirm()` — it is incremented at `:218` and never
  read.
- Restrict the `UPDATE` to `state = PROVISIONAL`.

**Tests:** `App/tests/test_claim_mail.py`
- A second `confirm()` with the same secret fails.
- An old secret fails after the host re-issues.
- The happy path still sets the cookie and grants access.

### W3.5 — Bound reservation reachability from a link `[F23]` — High

**File:** `App/app/routes/guest.py:334-348`

Depends on **D4**. If bounded: restrict to reservations whose `date_to` is within
N days of today (reuse `apartment.permalink_window_days`, which already exists
for exactly this purpose). Return the same `unavailable.html` for
out-of-window and non-existent IDs so the 404/200 difference stops disclosing
which IDs belong to the apartment.

**Tests:** an in-window incomplete reservation is reachable; a two-year-old one
is not, and the response is indistinguishable from a nonexistent ID.

### W3.6 — Secure flag on guest cookies `[F25]` — High

**File:** `App/app/routes/guest.py:156`, `:181`, `:192`

Replace the `PUBLIC_BASE_URL.startswith("https://")` test with
`auth._secure_cookies()`, which also honours `DEPLOYMENT == "production"`.
Promote that helper out of the underscore namespace while you are there.

**Tests:** `App/tests/test_security.py` — with `DEPLOYMENT=production` and an
`http://` base URL, all three cookies still carry `Secure`.

### W3.7 — PIN hardening `[F26]` — High

**Files:** `App/app/auth.py:416-426`, `App/app/rate_limit.py:9,12`, `App/app/templates/guest/pin.html:11`

- Stop accepting 4-digit PINs in `normalise_permalink_pin`; tighten the input
  `pattern`. `tests/test_guest_pin.py:128-167` asserts 4-digit acceptance as a
  requirement — that test encodes the weakness and must be updated.
- Add an escalating lockout on top of the sliding window: after N windows of
  failures, require a longer cool-off keyed on the token alone (not IP+token, so
  it is not trivially parallelised across IPs).
- Consider rotating the PIN automatically after a `guest_pin_abuse` alert.

### W3.8 — Turnstile must not be able to block registration outright `[F27]` — High

**File:** `App/app/turnstile.py:27-40`

A Cloudflare outage currently makes guest registration impossible with no alert.
Distinguish "challenge failed" (reject) from "verification unreachable"
(fail-open for a bounded number of attempts, and raise a `turnstile_unavailable`
warning). The statutory deadline does not pause for a CDN outage.

**Tests:** `App/tests/test_security_hardening.py` — a `requests` exception does
not reject the guest, and raises the alert.

### W3.9 — Rate-limit the unprotected guest POSTs `[F32]` — Medium

**Files:** `App/app/routes/guest.py:852-977`, `:1129`, `App/app/rate_limit.py:40-43`

`/save`, `/party` (no-mail path) and `/another` have no limit at all. Add one.
Also fix `blocked()` returning `False` on a falsy key and the `"unknown"`
fallback bucket.

---

## Phase 4 — Evidence trail and UbyPort semantics

**Branch:** `fix/evidence-trail`

### W4.1 — Distinguish "duplicate-derived sent" from "accepted with a receipt" `[F37, F44]` — High

**Files:** `App/app/reporting.py:769-832`, `App/app/db.py` (schema), `App/app/templates/submissions.html`, `submission_detail.html`

A 150 response currently produces `submission.state = "ok"` with
`receipt_pdf = NULL` — a successful filing with no Doručenka behind it.

- Add a distinct submission state (`ok_duplicate`) and a distinct guest-level
  marker so the UI can say "already in the register — receipt is on submission
  #N" and link to it.
- When a batch is accepted with no `pseudo_stamp` and no receipt, raise a
  `receipt_missing` warning. The product's third promise is that it keeps the
  confirmation; nothing currently notices when it does not.
- `tests/test_duplicate_guard.py:229-254` asserts the current behaviour — rewrite it.

### W4.2 — Decide what a 112 does `[F36]` — High

**Files:** `App/app/ubyport/errors.py:85`, `App/app/reporting.py:786`

Depends on **D2**. If a late filing is held by the register, 112 needs a terminal
state that reads as "filed, late" rather than "Rejected", and the record should
not sit in `blocked` alongside genuinely refused records.

Independent of D2, in the same pass: **delete `REJECTED_MARKERS`**
(`errors.py:32`) — it is defined, never consulted, and looks like a safety check
`[F45]`. And add a comment recording that classification depends on substring
matching the Czech code book, so a police-side wording change silently
reclassifies records.

### W4.3 — Resolve the phantom actor parameter `[F38, F40]` — High

**Files:** `App/app/reporting.py:501-508`, `:569-601`, `:690-943`, `App/app/routes/admin.py:1208`, `:1452`, `:1710`, `:1851`

- `submit_batch(verified_by_user_id=...)` is never read. Either use it (call
  `record_host_identity_confirmation(..., on_send=True)` for each accepted
  reportable guest, which is what the comment at `:582-584` claims already
  happens) or delete the parameter and the three routes' plumbing and `:928`.
  Decide, do not leave both.
- Delete `maybe_submit_after_verify` (`:506-508`, body `return None`) and its
  call site at `admin.py:1710`.
- Collapse `maybe_submit_after_host_save` → `try_immediate_submit` →
  `maybe_submit_after_completion` into one function with an honest name. The
  middle hop spends a `SELECT * FROM guest` to read `reservation_id`.

**Tests:** `App/tests/test_duplicate_guard.py` / `test_send_controls.py` — assert
whichever actor behaviour you chose, explicitly.

### W4.4 — One representation of the receipt↔stay link `[F46]` — Medium

**Files:** `App/app/db.py:145`, `:158`, `App/app/reporting.py:718`, `:780`, `App/app/routes/admin.py:1256-1261`, `:1267-1274`

`guest.submission_id` and `submission.guest_ids` JSON are two hand-synchronised
representations of the edge that ties a Doručenka to a stay. Pick one — prefer
`guest.submission_id`, it is queryable and indexable — and derive the other for
display. Add the missing test that `guest.submission_id` is set to the right
submission.

### W4.5 — Timezone-correct calendar dates `[F4]` — High

**File:** `App/app/icalsync.py:103-108`

`_as_date` takes `.date()` off a `datetime` with no timezone conversion, so a
UTC-stamped `DTSTART` stores the previous calendar day. Convert to
`config.TIMEZONE` first when the value is aware; leave naive and `date` values
alone (both already yield the correct local date).

**Tests:** `App/tests/test_icalsync.py` — **the suite currently has no timezone
coverage at all.** Add fixtures for: `DTSTART:20260910T230000Z`,
`DTSTART;TZID=Europe/Prague:20260910T140000`, a floating
`DTSTART:20260910T140000`, and an all-day `VALUE=DATE` regression case.

### W4.6 — Fix the remaining UID and lifecycle holes `[F5, F6, F7, F12, F13]` — High/Medium

**File:** `App/app/icalsync.py:260-338`, `:157-159`, `:294-295`

- Duplicate UID within one feed: detect the second occurrence and raise a
  warning rather than silently overwriting `[F6]`.
- Synthetic UID: drop the dates from the key (use a hash of `SUMMARY` +
  `DESCRIPTION` + sequence) so moving a UID-less event updates rather than
  cancel-and-recreate `[F7]`.
- A cancelled-then-rebooked UID is revived to `active` but nothing undoes
  `claim.expire_on_cancel` — the stay reappears with a dead guest link. Reopen
  guest access on revival `[F7]`.
- Already-`sent` guests keep stale `stay_from`/`stay_to` when the reservation
  moves — raise the `cancelled_after_report` equivalent for a *moved* reported
  stay `[F5]`.
- `is_block` matching free-text `SUMMARY` can delete a real stay. Require the
  match at first sight only; never let a summary change auto-cancel an existing
  active stay `[F13]`.
- `RRULE`/`EXDATE` are never expanded `[F12]` — decide whether to support
  recurring bookings or to detect and warn. Warning is acceptable; silently
  importing only the first occurrence is not.

### W4.7 — Serialise the DNS-pinning patch `[F9]` — High

**File:** `App/app/feed_fetch.py:46-70`, `:77-89`

`_connect_only_to` mutates the process-global
`urllib3.util.connection.create_connection` with no lock, while the scheduler
thread and Starlette's threadpool both fetch. Clicking "Sync now" during a poll
can cross pinned IPs or permanently restore the wrong original.

Prefer removing the monkeypatch: pass the pinned IP as the connection target and
carry the hostname in the `Host` header and TLS SNI, via a custom
`HTTPAdapter`/`PoolManager`. If the patch must stay, guard it with a module-level
`threading.Lock` held for the whole request *including the body read*.

**Tests:** `App/tests/test_feed_dns_pinning.py` currently covers one scenario and
stubs the pinned connector. Add: two concurrent fetches to different hosts both
resolve correctly; the 5 MiB cap; the redirect chain and `MAX_REDIRECTS`; an
https→http redirect downgrade rejected `[F16]`; a host resolving to mixed
public/private addresses.

---

## Phase 5 — Clean, efficient, meaningful

**Why last:** none of it can cause a wrong filing, and several items touch files
Phases 1–4 also touch. Doing it first would create conflicts for no safety gain.

**Branch:** `chore/cleanup` — but split into the five commits below so the dead-code
deletion is reviewable separately from the behaviour-preserving refactors.

### W5.1 — Delete dead code

Remove, having re-verified each with a repo-wide grep at the time of deletion
(the audit's list was accurate on 22 Sep 2026; re-check, do not trust it blindly):

`alerts.resolve_kind`, `alerts.count_critical`, `auth.is_logged_in`,
`auth.clear_pin_session`, `claim.secret_matches`, `env_guard.format_warnings`,
`housebook.sample_housebook_csv`, `housebook.iter_housebook_csv`,
`housebook.housebook_pdfs_zip`, `housebook.retention_expiry`,
`rate_limit._BLOCK_SECONDS`, `stays_import.sample_csv`,
`stays_import.iter_export_csv`, `stays_import.export_csv`,
`ubyport/soap.NS_ARRAYS`, `validation.ascii_fold`, `validation.age_on`,
`SubmissionResult.accepted`, `config.SES_FEEDBACK_QUEUE_URL`.

Also:
- `tools/design_matrix.py` — does not parse (`IndentationError` at line 75). Fix or delete.
- `tools/walkthrough.py`, `tools/feature_smoke.py`, `tools/pin_gate_check.py` — unreferenced; `feature_smoke` overlaps `smoke.py`, `pin_gate_check` duplicates `tests/test_guest_pin.py`.
- `static/ubyhost-logo.jpg`, `static/guide/housebook-filters.png`, `static/guide/help-link.png` — unreferenced.
- `reporting.status_label` — production-dead, called only from a test. Either wire it into the template that currently gets the raw `STATUS_LABELS` dict, or delete both and use the i18n labels (see W5.4).
- `auth.session_max_age` — used only by tests while `auth.py:304` re-implements it inline. Make `:304` call the helper.
- `want_pdf` — a three-layer parameter with one possible value, gating the legally-required receipt. Remove the parameter and always request the PDF.

**Owner decision inside this item:** `stays_import.import_csv` and
`housebook.import_csv` are ~90 lines each with no route and no test, and
`docs/TECHNICAL_COMPLIANCE_AUDIT.md:67` reasons about imported records as a
product feature (citing a symbol, `import_housebook_rows`, that does not exist).
**Either** wire them up — handling the `UNIQUE (apartment_id, uid)` collision,
which today would raise an uncaught `IntegrityError` mid-import and leave a
partial result — **or** delete them and correct that doc. Do not leave them.

**Done when:** `ruff check app tests tools --select F401,F841` is clean and CI
lints `tools/` too (W6.1).

### W5.2 — Collapse the duplication that can cause divergent filings

In priority order, because the first two decide whether a record gets filed:

1. **One guest-record extraction.** `routes/admin.py:1479-1499` and
   `routes/guest.py:1167-1178` maintain the same 11 field names independently.
   Move `GUEST_TEXT_FIELDS` and `_guest_payload` to a shared module and use it
   from both. Same for `_guest_signature_from_form` (`admin.py:1502-1509` vs
   `guest.py:1190-1192`).
2. **One completeness predicate.** `reporting.guest_issues:177-191` and
   `routes/guest.py:1199-1207` both re-run `validate_guest` and each appends its
   own signature issue — one English, one translated. Keep `reporting`'s as the
   single source and have the guest route call it with a translator.
3. **One naive-timestamp convention.** `reporting.py:536-543` treats
   `registration_completed_at` as UTC; `deadlines.local_now:91-96` treats naive
   as Prague civil. Pick one, document it in a module docstring, and make both
   obey it.
4. **One `_fmt_date`.** Byte-identical in `templating.py:31-33` and
   `alerts.py:21-23`; the `%d.%m.%Y` literal is hard-coded again at
   `reporting.py:992`, `:994` and in two templates.
5. **Route apartment lookups through `access.py`** for the two that are inside
   request handlers (`admin.py:145`, `:1194`). Leave `reporting.py`'s five —
   they have no request in scope.
6. **Pull the eight escaped ownership joins back into `access.py`**
   (`admin.py:249`, `:1039`, `:1113`, `:1894`, `:1946`, `:1960`,
   `alerts.py:151`, `reporting.py:974`). `access.py`'s docstring says the point
   is to make an omitted check conspicuous; that only works if the joins live
   there. While doing this, settle whether `owner_user_id IS ?` should be
   `= ?` — see the open question in W6.3.
7. **One bulk-zip helper** for `admin.py:1885-1937` and `:2103-2141`.

### W5.3 — Efficiency

1. **Move `_add_missing_columns` out of `connect()`** (`db.py:294`). It issues 23
   `PRAGMA table_info` calls per connection, every connection, and every query
   opens one — 96% of statements executed are schema-check overhead, roughly
   4,000 pragmas per dashboard load. `init_db` (`main.py:25`) already calls it at
   startup. Also fix the loop to pragma each *table* once rather than each
   *column*.
2. **Narrow `submissions_list`** (`admin.py:1946`): `SELECT s.*` over 200 rows
   pulls base64 receipts and full SOAP envelopes to render a list. Select the six
   columns the template uses plus `(s.receipt_pdf IS NOT NULL) AS has_receipt`.
   Same at `:1894` (receipts zip touches four columns) and `:1256-1261`.
3. **Add the missing indexes** (`db.py:203-209`): `submission(apartment_id)` —
   five join sites currently full-scan the widest table; `audit(owner_user_id, id)`;
   `email_outbox(state, next_attempt_at)`. Drop `idx_guest_state` — no query
   filters on `submit_state` in SQL, so it is maintained on every write and never
   read.
4. **`collect_sendable`** (`reporting.py:638`): the main query already joins
   `reservation`; select `r.*` and delete the per-guest `SELECT * FROM reservation`.
   This is in the send path.
5. **`count_sendable_stays`** (`reporting.py:511`, called `admin.py:1082`):
   delete it. The caller already has `controls` for every row —
   `sum(1 for i in rows if i["controls"].get("send_enabled"))`.
   `queue_counts:319-332` in the same file already shows the right shape.
6. **`reservation_progress`** (`reporting.py:222`, `:227`): stop running
   `validate_guest` twice per guest. Compute `complete` once and derive
   `incomplete` as the complement.
7. **`is_demo_apartment`** (`demo.py:32-34`): stop querying `legal_entity` per
   dashboard row on every deployment for a feature gated to `UBYPORT_ENV == "mock"`.
   Short-circuit on the env check, or add a column.
8. **Import-time side effects** (`config.py:11-15`, `:49`): importing the module
   creates directories and writes a secret to disk, or raises before logging is
   configured. Move both behind an explicit `init()` called from `main.py`.
   `ubyport/client.py:18` reads `UBYHOST_SOAP_WSA_HEADER` at import for the same
   reason — make it a runtime read.

Each of these is behaviour-preserving. If a test changes behaviour, you have
found a bug — stop and report it rather than adjusting the test.

### W5.4 — Translate the Python-generated text

The pattern today: templates are translated, Python-generated strings are not.
`routes/guest.py` has zero untranslated flash messages; `routes/admin.py` has 99,
plus 5 in `admin_accounts.py`, plus every alert title in `reporting.py` and
`icalsync.py`, plus `reporting.STATUS_LABELS`.

- Move `STATUS_LABELS` and the `status_label` wording into `host_i18n` and have
  the template use the i18n labels (this also resolves the dead
  `status_label` in W5.1).
- Move every alert title and detail into `host_i18n` with parameters, starting
  with `icalsync.py:211-212`, `:249`, `:367-368` and `reporting.py:494`, `:751`,
  `:859`, `:863-864`, `:912`. *"A stay from … was cancelled in the calendar after
  it had already been reported to the police"* is one of the most consequential
  messages the product emits and a Czech host reads it in English.
- `reporting.py:184-186` is a validation error **a guest** sees, in English — it
  must go through the guest catalog.
- Delete the English deadline prose at `reporting.py:997-1003`: `alerts.present`
  discards it and rebuilds from `host_i18n`, so it is dead work.
- Convert the `admin.py` flash messages in batches by section; they are
  mechanical but there are 99 of them.
- Give the two translation engines one implementation (`i18n.normalise_language`
  / `host_i18n.normalise_language` are identical; the lookup functions differ
  only in that **the guest-facing one lacks the interpolation guard**, so a
  malformed key raises on the guest form). Resolve the conflicting defaults —
  `i18n.DEFAULT_LANGUAGE = "en"` vs `host_i18n.PUBLIC_DEFAULT_LANGUAGE = "cs"`
  means a Czech guest with no `?lang=` gets English.

### W5.5 — Split `routes/admin.py`

2,321 lines, navigable by banner comment but fusing eight responsibilities. Move,
in this order, each as its own commit with no behaviour change:

1. `dashboard_rows` (`:121-164`) → `reporting.py`, beside `reservation_progress`.
   Its absence from there is why `count_sendable_stays` existed.
2. Exports (CSV, per-guest PDF, receipts zip, house-book CSV/PDF, retention
   purge, archive browser) → `routes/exports.py`.
3. Command-palette JSON API (`:196-261`) → `routes/api.py`.
4. Demo/onboarding/celebrations → `routes/onboarding.py`.

What should remain in `admin.py`: legal entities, apartments and feeds,
reservations and guests, and the send actions.

Also rename `stays_import.py` — after W5.1 it is export-only.

---

## Phase 6 — CI, tests and the remaining unknowns

**Branch:** `chore/ci-and-coverage`

### W6.1 — Make CI catch what it currently misses

`.github/workflows/ci.yml`:
- Extend the ruff selection beyond `E9,F63,F7,F82` to include at least `F401`
  and `F841` — the reason 20 dead definitions survived.
- Add `tools` to the lint path. It is excluded today, which is why a file that
  raises `IndentationError` is committed.
- Either enforce coverage (`--cov-fail-under`, set at the current measured level
  as a ratchet) or stop generating the XML — today it is computed and discarded.
- Either make `mypy` gate on a narrow module set or label it clearly as
  non-gating. With `continue-on-error: true` and `--follow-imports=skip` it
  reports almost nothing and blocks nothing.

`.github/workflows/deploy-production.yml`:
- **Deploy the commit CI validated**, not `origin/main`'s tip. The remote script
  does `git fetch origin main && git reset --hard origin/main` (`:76-77`), so if
  two commits land while CI runs on the first, a green run of commit A deploys
  commit B unvalidated.
- Close the `workflow_dispatch` bypass (`:21`) or require an explicit
  force-confirm input.
- Add a post-deploy public smoke check and a documented rollback step.

### W6.2 — Fix the tests that cannot fail

- `test_deadlines.py:131-148` — asserts on the **SQL string** while stubbing
  `db.query` to return `[]`, so the loop body of `check_deadlines` (every alert
  decision) is never entered. Rewrite it against real rows. The name promises the
  strongest claim in the product and the test cannot observe it.
- `test_deadlines.py:81-116`, `:119-128`, `:70-72` — re-implements the template
  helper's plural-key construction inside the test; asserts
  `describe_time_left(...)` equals a string built from its own inputs; sorts by
  `URGENCY_ORDER` then asserts the result is `URGENCY_ORDER`'s key order. Point
  them at the real helpers or delete them.
- `test_calendar_sync_ui.py:33-47` — stubs `icalsync.sync_all` entirely, so it
  asserts nothing about what the host is told when a feed fails. Assert the flash
  and the alert.
- `test_ubyport_sample_pdf.py:148` — `importorskip("pdfplumber")` on a dependency
  that *is* pinned in `requirements-dev.txt`, so it runs in CI and silently skips
  locally. Pick one.

### W6.3 — Answer the remaining open questions

From the audit's §7, in the order they block work:

- **`owner_user_id IS ?` vs `= ?`** (`access.py:21-79`): run
  `SELECT COUNT(*) FROM apartment WHERE owner_user_id IS NULL` (and the same for
  `legal_entity`) against production. If zero, switch to `= ?` and add a `NOT NULL`
  constraint path. Blocks part of W5.2.6.
- **Failed-submission retry**: confirm whether anything retries a stay in `error`
  other than the 10-minute sweep, which requires `registration_completed_at`. If
  a cleared timestamp can strand a record, that is a Phase 1-class bug found late
  — treat it as such.
- **Reconcile the docs' verified counts**: `SECURITY_REVIEW_2026-09-15.md:95`
  says 328 tests passed, `NEXT_MAIL_RELEASE.md:25` says 436, the repo has ~400
  test functions. Re-run and record the real number with the command that
  produced it.
- **Re-date the two audit docs.** Both are scoped "as of 15 September 2026" and
  predate the 1.1.0 / SES-live release of 21 September, so their mail rows
  describe the pre-flip state. Also fix the two items the code contradicts
  (`TECHNICAL_COMPLIANCE_AUDIT.md:78` and `:79` — see the audit's closing
  section) and the citation of the non-existent `import_housebook_rows` at `:67`.

---

## Sequencing summary

| Phase | Branch | Items | Blocked by |
| --- | --- | --- | --- |
| 1 — missed filings | `fix/missed-filing-paths` | W1.1–W1.7 | D1; D3 for part of W1.4 |
| 2 — PII at rest | `fix/pii-at-rest` | W2.1–W2.4 | — |
| 3 — guest access control | `fix/guest-access-control` | W3.1–W3.9 | D4 for W3.5 |
| 4 — evidence trail | `fix/evidence-trail` | W4.1–W4.7 | D2 for W4.2 |
| 5 — cleanup | `chore/cleanup` (5 commits) | W5.1–W5.5 | Phases 1–4 merged, to avoid conflicts |
| 6 — CI and unknowns | `chore/ci-and-coverage` | W6.1–W6.3 | W6.3's first item blocks W5.2.6 |

Phases 2, 3 and 4 are independent of each other and can run in parallel if more
than one agent is working. Phase 5 must come after them. Phase 1 should be merged
and deployed before the others start — it is the only phase whose findings are
actively costing filings today.

**Documentation duty, every phase:** `docs/OPERATIONS.md` and
`docs/ENVIRONMENT.md` were written from the current code. Any phase that changes
scheduler behaviour, `submit_state` transitions, alert kinds, retention or
environment variables updates them in the same PR. A doc that drifts is how this
codebase got a config comment promising a runtime batch-size refresh that does
not exist.
