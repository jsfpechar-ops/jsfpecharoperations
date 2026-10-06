# UbyHost — independent code audit

**Repo:** `jsfpechar-ops/jsfpecharoperations` (private) · app version `1.1.0`
**Scope:** `App/` — 30,402 lines of Python across 103 files, 49 templates, 48 test files
**Date:** 22 September 2026
**Nature:** read-only. No application code was modified. Documentation was updated separately (listed at the end).

---

## 1. Executive summary

The code does implement the three-step concept, and it implements it with more
care than most codebases of this size: the UbyPort module cites the operating
rules it honours, the duplicate guard is real and well tested, the statutory
three-working-day deadline is computed correctly including Czech public holidays
and DST, and a network failure leaves the queue intact rather than losing it.
The submission path — the part where being wrong is a compliance failure — is
the best part of the repo.

The divergences from the product's mental model are concentrated in two places.
First, **the pipeline has silent failure modes at both ends**: the calendar
poller is registered in a paused state and only wakes at boot if a feed already
exists; a later calendar change nulls a guest's already-collected signature with
nothing but a log line; a partially-truncated feed mass-cancels stays; and a
background job that raises is logged and forgotten with no alert. In each case
the host's only signal is a timestamp on the dashboard with no staleness
threshold behind it, so "less nagging, more certainty" degrades to *no* nagging
and false certainty.

Second, **the promise to store the confirmation receipt is not quite what the
data model does.** A duplicate response is recorded as a successful filing with
no Doručenka behind it, and a code 112 (reported late) parks the record in a
state the UI calls "Rejected" forever. Meanwhile every reported guest's passport
number is kept in cleartext twice — once on the guest row, once inside
`submission.request_xml` — and there is no `DELETE FROM submission` anywhere in
the codebase, so the second copy outlives the six-year purge of the first.

On code quality: it is clean by the ordinary measures — zero TODO/FIXME markers,
zero commented-out blocks, no unreferenced templates, honest domain-named
modules, and an end-to-end test that reads like the product. The redundancy that
exists is of a specific kind: **~20 unused functions, ~2,300 lines outside the
three product steps, three separate vocabularies for one status enum, two
independent implementations of "is this guest record complete", and a database
layer that executes 23 schema-check pragmas on every single query.**

**The single biggest risk** is the combination at the top of §5: a guest's
passport number exists in an unencrypted column *and* in an XML blob that
nothing ever deletes, on a host machine whose backups the supplied scripts do
not encrypt. Everything else on this list is recoverable; that one is a
notification-grade personal-data exposure if the box or a backup is ever lost.

---

## 2. Architecture overview

Descriptive, not critical.

A single FastAPI process, served by uvicorn behind Caddy on AWS Lightsail
(production, `ubyhost.com`) with a Render deployment pinned to the mock UbyPort
for staging. One SQLite file in WAL mode is the whole datastore. APScheduler
runs five background jobs inside the same web process. No queue, no cache, no
second service. For a single-operator product this is a defensible choice and
the code does not pretend otherwise.

| Concern | Where it lives |
| --- | --- |
| **Step 1 — calendar sync** | `feed_url.py` (URL/SSRF validation) → `feed_fetch.py` (pinned-DNS fetch) → `icalsync.py` (parse + reconcile into `reservation`) |
| **Step 2 — guest form** | `routes/guest.py` (1,343 lines) with `claim.py` (e-mail claim + tokens), `auth.py` (permalink token + PIN), `validation.py`, `passport_photos.py`, `turnstile.py`, `rate_limit.py` |
| **Step 3 — UbyPort submission** | `reporting.py` (1,042 lines — eligibility, claim lease, state transitions, alerts) → `ubyport/client.py` (NTLM/HTTP) → `ubyport/soap.py` (envelope + parse) with `ubyport/errors.py` (code classification) |
| Cross-cutting | `db.py` (SQLite + Fernet for secrets), `access.py` (ownership-scoped lookups), `security.py` (CSRF, headers), `deadlines.py` (Czech holidays + statutory window), `alerts.py`, `scheduler.py`, `mail.py` (SES/console outbox), `housebook.py` (domovní kniha + retention) |
| Host UI | `routes/admin.py` (2,321 lines), `routes/admin_accounts.py`, `templating.py`, 49 Jinja templates |
| i18n | 7 modules: `i18n.py` (guest) + `host_i18n.py` (host) + 5 pure-data legal catalogs merged into `host_i18n` at import |
| Test doubles | `mock_ubyport/` — a real SOAP stand-in, spawned as a subprocess by the end-to-end test and by CI, and running on the staging deployment |

`access.py` centralises the ownership joins that keep one host's data away from
another's, and it is the right idea. Eight further copies of the same join
pattern have since been written inline elsewhere (§4).

---

## 3. Flow-by-flow findings

### 3.1 Calendar sync

| # | Location | Sev | Finding | Why it matters here |
| --- | --- | --- | --- | --- |
| 1 | `App/app/scheduler.py:71-74`, `:92-93` | **Critical** | The `ical` job is added with `next_run_time=None`, which in APScheduler 3.x creates it **paused**. The only un-pause is at boot, gated on an active feed already existing. | A host who installs, then adds their first calendar, gets one inline sync and then no polling until the process restarts. Every later booking is invisible and its deadline expires unnoticed. |
| 2 | `App/app/icalsync.py:300-316` | **Critical** | When feed dates change, every non-`sent` guest on that stay has `signature_png` and `signed_at` set to `NULL`. The only notification is `log.warning` — no alert, no re-invite, no flag. | A ready-to-file stay silently becomes unfilable (`guest_issues` adds a hard signature error) while the statutory clock keeps running. This is the most consequential silent state change in the app. |
| 3 | `App/app/icalsync.py:348` | **High** | The mass-cancel guard is `if candidates and not seen_uids` — it protects only the *fully* empty feed. A truncated or partially-generated export takes the `else` branch and cancels every other future stay. | Cancelled stays drop out of `check_deadlines`, so the host loses the reporting obligation for guests who are actually arriving, with no visible error. `claim.expire_on_cancel` also destroys their guest links. |
| 4 | `App/app/icalsync.py:103-108`, called at `:140-142` | **High** | `_as_date` takes `datetime.date()` with **no timezone conversion**. A UTC-stamped `DTSTART:...T230000Z` stores the previous calendar day. | `reservation.date_from` is both the date filed as `cFrom` and the anchor for the deadline. An off-by-one here is a wrong filing *and* a deadline computed a day early or late. No test covers a non-`VALUE=DATE` DTSTART. |
| 5 | `App/app/icalsync.py:304` | **High** | The guest UPDATE is `WHERE ... submit_state != 'sent'`, so already-reported guests keep their old `stay_from`/`stay_to` while the reservation's dates move. `_stay_dates` prefers the guest values. | The filed record permanently disagrees with the calendar and nothing re-files the correction. The `cancelled_after_report` alert covers a *removed* stay but not a *moved* one. |
| 6 | `App/app/icalsync.py:260-338` | **High** | Two `VEVENT`s sharing a UID (recurrence override, or an OTA re-issuing a modified booking) collapse into one reservation — the second iteration overwrites the first. No counter, no log, no alert. | One real stay disappears and is never filed. |
| 7 | `App/app/icalsync.py:157-159` | **High** | The synthetic fallback UID embeds the dates. Moving a UID-less event changes its key, so the old row is cancelled and a new empty one inserted. | Guest data already collected stays attached to the cancelled row. |
| 8 | `App/app/icalsync.py:240` + `:402-411` | **High** | The except clause is only `(FeedError, ValueError)`, and `sync_all` does not wrap `sync_feed` at all. | Any other exception aborts the loop: one bad feed stops ingestion for every other apartment on the instance, and `last_ical_sync` is never updated. |
| 9 | `App/app/feed_fetch.py:46-70` | **High** | `_connect_only_to` mutates the **process-global** `urllib3.util.connection.create_connection` with no lock, while the scheduler thread and Starlette's threadpool both call it. | Clicking "Sync now" during a poll can cross pinned IPs between fetches, or leave the wrong `original` restored — the DNS-rebinding defence failing under ordinary use. |
| 10 | `App/app/icalsync.py:342`, `:201` | Medium | `date.today()` is process-local, while the rest of the app deliberately uses `deadlines.local_now()` with `Europe/Prague`. | On a UTC-clocked host, between midnight and 02:00 Prague the future/past cutoff is a day out — and that cutoff decides eligibility for auto-cancellation. |
| 11 | `App/app/icalsync.py:342-354`, `:378-382` | Medium | An empty-but-valid feed is retained (correct) but the feed is then marked `last_status='ok'` and the `feed_error` alert resolved. | A feed silently degraded to returning nothing shows a green pill. |
| 12 | `App/app/icalsync.py:139` | Medium | `walk("VEVENT")` never expands `RRULE`/`EXDATE`. | A recurring booking is imported as its first occurrence only; later occurrences are never ingested or filed. |
| 13 | `App/app/icalsync.py:261-263` + `:50-64` | Medium | `BLOCK_PATTERNS` matches free-text `SUMMARY`. A real booking whose summary later contains "blocked"/"maintenance" is skipped, drops out of `seen_uids`, and is auto-cancelled at `:375`. | A real guest stay deleted by a string match. |
| 14 | `App/app/feed_fetch.py:143-147` | Medium | The only content check is the substring `BEGIN:VCALENDAR`; `Content-Type` is never validated. | An HTML login wall containing that string parses as a calendar with zero bookings — which then routes into finding 3 or 11. |
| 15 | `App/app/feed_fetch.py:16`, `:80` | Medium | `FETCH_TIMEOUT = 45` is per-socket-operation, not a whole-transfer deadline, and `sync_all` iterates feeds sequentially with `max_instances=1`. | One slow-drip feed stalls calendar ingestion for the entire instance. |
| 16 | `App/app/feed_url.py:155-157` | Low | A redirect may downgrade `https` → `http`. | The feed URL is itself a bearer secret for Airbnb/Booking exports. |

**Well done here, for the record:** the SSRF work is thorough — scheme
allow-list, credential rejection, octal/hex IPv4 literal rejection, resolved-IP
checks against loopback/private/link-local/CGNAT/metadata, DNS pinned once and
re-validated per redirect hop, 3-hop cap, 5 MiB cap on both `Content-Length` and
the streamed body, and `ICAL_ALLOW_PRIVATE` neutralised in production. Finding 9
is a concurrency flaw in an otherwise strong control.

### 3.2 Guest link, form and signature

**Mechanics, verified:** `permalink_token` is 20 characters from a 33-symbol
alphabet via `secrets.choice` (≈100 bits) — ample. `permalink_pin` is 6 digits,
compared via HMAC fingerprint. The claim secret is `secrets.token_urlsafe(24)`
(192 bits) stored as SHA-256; unsalted is fine at that entropy and is not a
finding. The permalink token is stored in plaintext and never expires; the PIN
is per-apartment, static, and shared by every guest of every stay.

| # | Location | Sev | Finding | Why it matters here |
| --- | --- | --- | --- | --- |
| 17 | `App/app/routes/guest.py:30` vs `routes/admin.py:41` | **High** | The guest router is a bare `APIRouter()` — **no CSRF dependency and no same-site check on any guest POST.** `render_guest` never emits a `csrf_token`, and `static/csrf.js:13` explicitly skips paths starting with `/l/`. | Any page that learns a link can cross-site POST `/party` (claim with an attacker's e-mail), `/another` (inflate the headcount), `/save`, `/claim/confirm`. Each has a filing consequence. |
| 18 | `App/app/security.py:177-178` | **High** | `protect_host_post` returns early whenever `DEPLOYMENT != "production"`, so host CSRF is off on staging and local — and the same-site check, which is only reachable from this function, is off with it. | Staging holds real-shaped data and is the environment most often driven by a browser with other tabs open. |
| 19 | `App/app/routes/guest.py:1188-1189` + `templates/guest/form.html:50-53` | **High** | `stay_from`/`stay_to` are hidden form fields taken verbatim from the guest; the only server check is `stay_to > stay_from`. They become `cFrom`/`cUntil` on the police record. | A guest — or anyone with the link — can file arrival/departure dates unrelated to the booking. The same field drives photo retention (`COALESCE(g.stay_to, r.date_to)`), so a far-future value keeps the passport scan on disk indefinitely. |
| 20 | `App/app/routes/guest.py:1190-1192`, `:1209-1210` | **High** | `signature_png` validation is only `startswith("data:image/")` — no length cap, no base64 decode, no MIME allow-list, no image probe (contrast `passport_photos.py:64-84`, which does all of this properly). No request-body limit exists in the app or in the Caddyfile. | Two consequences: an unbounded blob into a `TEXT` column on a single-file SQLite DB; and `data:image/anything,<junk>` satisfies every downstream "signed" check, unlocks the form, and renders as *"(signature could not be rendered)"* in the statutory house-book PDF — a legally required signature that does not exist. |
| 21 | `App/app/claim.py:310-333` | **High** | `confirm()` never clears or rotates `token_hash`, and the SQL accepts `state IN (PROVISIONAL, CLAIMED)`. `token_version` is incremented but never checked here. The 30-minute expiry only applies while `PROVISIONAL`. | Once claimed, the e-mailed secret is valid forever and unlimited times. A forwarded claim e-mail is permanent unauthenticated write access to that reservation. |
| 22 | `App/app/routes/guest.py:852-977` + `reporting.py:436-440`, `:463-470` | **High** | Any link+PIN holder can set or raise `declared_guests` (1–60) on a reservation with no host override. `refresh_registration_completed_at` requires `filled >= expected`. | Inflating the headcount permanently prevents `registration_completed_at` from being set, so `maybe_submit_after_completion` never fires — indefinite suppression of the automatic filing, with no alert tied to it. |
| 23 | `App/app/routes/guest.py:334-348` | **High** | A stay link keeps every incomplete, unlocked **past** reservation of that apartment reachable with no time bound, and `reservation_id` is a global auto-increment. The 404-vs-200 difference discloses which IDs belong to the apartment. | One leaked link enumerates the apartment's reservation history and reopens years-old registrations for writing. (`tests/test_claim_mail.py:401` asserts this reachability as intended — worth confirming that is still the intent.) |
| 24 | `App/app/routes/guest.py:888-935` + `claim.py:193-204` | **High** | Claim-jacking: whoever claims first binds the reservation to their e-mail; the real guest then gets `assigned.html` and cannot reach the form, and a 30-minute provisional hold blocks a different address. | The legitimate guest is locked out of registration entirely, and the attacker receives the completion receipt. |
| 25 | `App/app/routes/guest.py:156`, `:181`, `:192` | **High** | `ubyhost_owned`, `ubyhost_claim` and `ubyhost_lang` set `secure=` from `PUBLIC_BASE_URL` alone, not `auth._secure_cookies()` (which also honours `DEPLOYMENT == "production"`). | These cookies are the only thing separating one party member's passport data from another's. A misconfigured base URL on production ships them over plaintext HTTP. |
| 26 | `App/app/auth.py:421-426` + `rate_limit.py:9`, `:12` + `templates/guest/pin.html:11` | **High** | 4-digit legacy PINs are still accepted (10⁴ space). The only defence is 10 failures / 15 min / (IP+token), no lockout, ≤2 s delay — ≈960 attempts/day/IP, parallelisable. Turnstile after 3 failures is inert unless `DEPLOYMENT=production` **and** all three `TURNSTILE_*` vars are set. | With `MAIL_BACKEND=disabled` the claim gate is also skipped, leaving token+PIN as the only boundary on the whole registration flow. |
| 27 | `App/app/turnstile.py:27-40` | **High** | `verify()` returns `False` on any requests exception or non-JSON response, and it gates PIN entry after 3 failures and every claim start. | A Cloudflare outage or egress block makes guest registration impossible, with no bypass and no alert — guests cannot register before the statutory deadline. |
| 28 | `App/app/routes/admin.py:1752-1754` vs `:1805` | **High** | `guest_archive` sets `archived_at` but never calls `passport_photos.delete_photo`; `guest_delete` does. | The passport scan of a guest the host believes they removed stays readable on disk until the 30-day sweep — and never, if `stay_to` was pushed out per finding 19. |
| 29 | `App/app/claim.py:242-257` + `mail.py:172-193`, `:305-316` | **High** | The claim secret is hashed in `reservation_claim` but stored **in cleartext** in `email_outbox.payload` (the body contains the full `#c=` URL) and again in `console_mail_log.body_text`, retained 14 days and surfaced to hosts via `recent_console_messages`. | A database read yields working claim links for every recent reservation, defeating the point of hashing the token. `tests/test_claim_mail.py:296-318` asserts this as intended. |
| 30 | `App/app/routes/guest.py:291-305` | Medium | `_visible_reservations` filters on `guest_access_locked_at IS NULL` but not on whether another e-mail already claimed the stay. | Any link holder sees the apartment's upcoming occupancy (dates, nights, progress) plus a masked claim e-mail. |
| 31 | `App/app/routes/guest.py:1284` | Medium | `filled_ip` (the guest's raw IP) is retained for the life of the six-year house-book record; the privacy notice mentions IP only in a bot-check context. | Undisclosed long retention of a network identifier attached to a passport record. |
| 32 | `App/app/rate_limit.py:40-43`, `:71-73` | Medium | `blocked()` short-circuits to `False` on a falsy key, and `client_key` falls back to the literal `"unknown"` when `request.client` is absent. `/save`, `/party` (no-mail path) and `/another` have no rate limit at all. | Combined with an unset `TRUSTED_PROXY_CIDRS`, all visitors behind the proxy share one bucket. |
| 33 | `App/app/templates/guest/form.html:235` | Medium | Re-renders `guest.signature_png` into a hidden input with no `data:image/` guard (the host template at `guest_form_admin.html:209` does guard it). | Not XSS — Jinja autoescape is on and there is no `\|safe`/`Markup` anywhere in `App/app/` — but CSP still carries `script-src 'unsafe-inline'`, so autoescape is the only remaining defence. |
| 34 | `App/app/main.py:71-74` | Medium | Only `ExpiredFormError` has a handler, and `/l/{token}/{reservation_id}` declares `reservation_id: int`, so `/l/{token}/foo` returns FastAPI's default 422 JSON echoing the path segment. | A machine-readable probe oracle on an otherwise guest-facing surface. |

**Well done here:** cross-guest PII reads are actually prevented — `_person_row`
gates name and summary on the signed `ubyhost_owned` cookie, `stay.html` renders
unowned people as a bare index, `/edit/{guest_id}` requires the ID be in the
cookie, and `/save` drops an unowned `guest_id`. Cross-apartment access is
blocked by `apartment_id = ?` on every reservation lookup. There is no PII in
any log line — every `log.*` call across `App/app/` was grepped; `db.audit`
carries IDs only and `mail._send_console` masks recipients.

### 3.3 UbyPort submission

| # | Location | Sev | Finding | Why it matters here |
| --- | --- | --- | --- | --- |
| 35 | `App/app/db.py:151-167` + `reporting.py:827-830` | **Critical** | `submission.request_xml`/`response_xml` hold the full envelope — surname, birth date, `cDocN` passport number, address — in cleartext, and **there is no `DELETE FROM submission` anywhere in the codebase** (verified by grep across `App/app/`). `housebook.purge_expired` deletes only `guest` rows and photos. | Passport numbers survive the six-year purge of the record they belong to, indefinitely, and remain readable from the submission pages. |
| 36 | `App/app/ubyport/errors.py:85` + `reporting.py:786` | **High** | Code 112 ("reported late") is classified `not_correctable` → `submit_state = blocked` → status label "Rejected", excluded from every future automatic send. But 112 does not necessarily mean the register refused the data. | The host's record of a filing that may well have landed reads as a permanent rejection, and nothing distinguishes "the register has it, late" from "the register does not have it". Flagging rather than asserting: this may be deliberate, but the code carries no comment saying so. |
| 37 | `App/app/reporting.py:788-807` + `db.py:151-167` | **High** | A duplicate (150) rewrites the state to `sent` and the submission row is stored `state="ok"` with `receipt_pdf = NULL`. | Sound as a recovery path for a lost response, but rule 10.5(3) wants the outcome on the stored record, and here the outcome is recorded as clean when it was a rejection interpreted as proof. The evidence trail shows a successful filing with no Doručenka behind it. `tests/test_duplicate_guard.py:229-254` locks this in as correct. |
| 38 | `App/app/reporting.py:696` (param), `:928`, `routes/admin.py:1208`, `:1452`, `:1851` | **High** | `submit_batch(verified_by_user_id=...)` is **never read in the body** — grepped. Three routes thread `access.owner_id(request)` into it; `reporting.py:928` exists solely to compute the value. | The send path records no actor on the guest record and never sets `identity_verified_at`, contradicting the comment at `reporting.py:582-584` ("Most hosts verify by sending"). `record_host_identity_confirmation` is only reached from the explicit Verify route; its `on_send=True` branch is exercised only by a test. |
| 39 | `App/app/deadlines.py:86-88`, called with `reservation["date_from"]` at `reporting.py:980`, `routes/admin.py:140`, `:154`, `:1271`, `templating.py:92` | **High** | The deadline is anchored on the **reservation's** `date_from`, while the date actually filed is the **guest's** `stay_from` (`reporting._stay_dates:62-69`, and `housebook.py:99-104` uses `COALESCE`). | If a guest's `stay_from` is earlier than the booking's, the dashboard shows a later deadline than the statutory one and `check_deadlines` never raises in time — the exact failure the module exists to prevent. Per finding 19 a guest can set `stay_from` themselves. No test covers the two differing. |
| 40 | `App/app/reporting.py:506-508` | Medium | `maybe_submit_after_verify` has body `return None` and is called for real from the Verify-identity POST at `routes/admin.py:1710`. | A reader of that route sees "verify then maybe submit"; nothing happens. In the module that decides whether a police filing goes out, a name that overstates is a correctness hazard for the next reader. |
| 41 | `App/app/config.py:66` vs `reporting.py:929` | Medium | The comment promises the batch ceiling is "refreshed at runtime via `MaximalniDelkaSeznamu`". It is not: `client.max_batch_size()` is called only from the Test-connection button and its value is displayed, never stored. | If the police lower the ceiling, the app keeps sending 32 per call. (Documented in the new `docs/ENVIRONMENT.md`; the stale code comment remains, since this audit does not edit code.) |
| 42 | `App/app/reporting.py:40`, `:664-687`, `:942-943` | Medium | The `submission_claim` lease has a 5-minute TTL and is released in a `finally`. A batch of 32 guests at a 60-second timeout can exceed that. | A concurrent sweep could re-claim a guest mid-flight. Mitigated by the 150-duplicate handling, so the outcome is a spurious duplicate against the host rather than a double filing. |
| 43 | `App/app/config.py:151-152` | Medium | `endpoint_for()` falls back to the **mock** endpoint for any unrecognised env string. | `env_guard` rejects invalid values at startup, so this is not reachable today — but it is a fail-*open*-to-fake default sitting behind a single validation, and the `env=` parameter is threaded through `submit_batch` from callers. |
| 44 | `App/app/ubyport/soap.py:199-205` + `reporting.py:769-783` | Medium | Acceptance is never gated on having received a `pseudo_stamp` or a receipt. A clean response with no receipt marks the guest `sent`. | The product's third promise is that it stores the actual confirmation. Nothing alerts when a filing is accepted with no evidence attached. |
| 45 | `App/app/ubyport/errors.py:29-32` | Medium | Classification depends on **substring matching the Czech code book text** (`duplic`, `pozd`, `late`). `REJECTED_MARKERS` is defined and never consulted (grepped). | A wording change on the police side silently reclassifies records between "fix and resend" and "permanently parked". And a tuple that looks like a safety check is not one. |
| 46 | `App/app/db.py:145` vs `:158` | Medium | The receipt↔stay edge is stored twice — `guest.submission_id` and `submission.guest_ids` JSON — kept in sync by hand in `submit_batch`. The reservation-detail page reads the first, submission-detail the second. | This is the link that ties a Doručenka to a stay, so divergence is an evidence-trail problem. Tests assert `guest_ids`; nothing asserts `guest.submission_id` was set. |
| 47 | `App/app/reporting.py:770` | Low | `per_record[index] if index < len(per_record) else ""` would treat a missing outcome as acceptance — but `client.py:167-171` already refuses a length mismatch as a transport error. | Correct today; the defensive branch is unreachable and reads as if it were the guard. |

**Well done here:** the `submission` row is written *before* the call, so a
crash mid-flight leaves a `running` record rather than nothing. Transport
failures leave guests `pending` and raise a **critical** alert, and the
end-to-end test proves the whole cycle including the alert clearing. The
`submission_claim` table is a genuine cross-process lease with a real
concurrency test behind it. `client.py:167` refuses a response whose record
count does not match the request. `deadlines.py` is the most carefully written
module in the repo — 13 statutory holidays, correct Anonymous Gregorian Easter,
Good Friday only from 2016, and a DST-crossing test.

### 3.4 Cross-cutting: auth and data at rest

| # | Location | Sev | Finding | Why it matters here |
| --- | --- | --- | --- | --- |
| 48 | `App/app/db.py:121-148`, `:437-450` | **Critical** | Guest PII — `surname`, `first_name`, `birth_date`, `doc_number`, `visa_number`, `res_*`, `note`, `signature_png`, `filled_ip` — is **plaintext**. `encrypt_secret`/`decrypt_secret` are used only for UbyPort passwords and TOTP secrets, never for guest data. Combined with finding 35 and unencrypted backups, one passport number exists in cleartext in at least two places with no deletion path for one of them. | This is the biggest single risk in the audit. Loss of the box or a backup is a notification-grade personal-data exposure. |
| 49 | `App/app/access.py:21-79` | Medium | Every ownership predicate is `owner_user_id IS ?` rather than `= ?`. If `owner_id(request)` returns `None`, these match rows whose owner is NULL. | `owner_user_id` is nullable and was added by migration, so NULL-owner rows can exist in an upgraded database. Worth confirming no such rows remain in production; the `IS` is presumably deliberate for the single-user case but it is an unlabelled latent cross-account path. |
| 50 | `App/app/db.py:443-450` | Medium | A wrong or rotated `SECRET_KEY` makes `decrypt_secret` return `""` instead of raising, which fails `validate_apartment` and returns `not_configured`. | Reporting stops. An `apartment_setup` warning is raised, so not fully silent — but the failure presents as a configuration problem rather than "your key changed". Now documented in `docs/OPERATIONS.md`. |
| 51 | `App/app/main.py:83-94` | Low | No `Strict-Transport-Security` from the app and none in the Caddyfiles; `script-src 'unsafe-inline'` on every response including guest pages. | HSTS depends entirely on Caddy defaults. |

---

## 4. Code quality findings

The headline: this is clean code with a specific, narrow kind of accumulation.
**Zero** TODO/FIXME/XXX/HACK markers. **Zero** commented-out code blocks. Zero
unreferenced templates (all 36 render). Every route is reachable. Perfect EN/CS
key parity across all three string catalogs (674/674, 398/398, 216/216) with no
collisions — someone maintains that carefully.

### Dead and vestigial code

~20 module-level definitions have exactly one reference in the repo (their own
definition). Low severity individually; listed because the owner asked for the
sweep.

`alerts.resolve_kind:197`, `alerts.count_critical:220`, `auth.is_logged_in:270`,
`auth.clear_pin_session:493`, `claim.secret_matches:336`,
`env_guard.format_warnings:157`, `housebook.sample_housebook_csv:416`,
`housebook.iter_housebook_csv:437`, `housebook.housebook_pdfs_zip:503`,
`housebook.retention_expiry:653`, `rate_limit._BLOCK_SECONDS:13`,
`stays_import.sample_csv:40`, `stays_import.iter_export_csv:192`,
`stays_import.export_csv:203`, `ubyport/errors.REJECTED_MARKERS:32`,
`ubyport/soap.NS_ARRAYS:19`, `validation.ascii_fold:193`, `validation.age_on:284`,
`SubmissionResult.accepted` (`client.py:44-49`), `config.SES_FEEDBACK_QUEUE_URL:128`.

Worth more than "unused":

- **`stays_import.import_csv:48` — ~90 lines, Medium.** The entire CSV
  stay-import half of a module *named* `stays_import` is unreachable: no route,
  no template, no test. `housebook.import_csv:202` is likewise route-less.
  `tests/test_endtoend.py:540-542` confirms `POST /reservations/import` returns
  ≥400 and `POST /housebook/import` returns 404. Two consequences: the
  documented migration path for a host bringing an existing paper house book
  does not exist, and `docs/TECHNICAL_COMPLIANCE_AUDIT.md:67` reasons about
  "imported records" as a product feature (and cites a symbol,
  `import_housebook_rows`, that does not exist anywhere).
- **`reporting.status_label:346` — Medium.** 13 lines of automation-aware status
  wording, called only from `tests/test_send_controls.py:141`. `templating.py:98`
  exposes the raw `STATUS_LABELS` dict to Jinja instead, so
  "Complete — sending automatically" and "Ready — send manually" never reach a
  user.
- **`auth.session_max_age:210` — Medium.** `auth.py:304` re-implements the same
  `remember ? REMEMBER : MAX` choice inline. Two sources of truth for session
  lifetime, one of them existing only for the test to assert against.
- **`tools/design_matrix.py` — Medium.** Does not parse: `IndentationError` at
  line 75. A committed file that cannot run is proof nothing checks `tools/` —
  and indeed CI lints `app tests` but not `tools`.
- **`tools/walkthrough.py`, `tools/feature_smoke.py`, `tools/pin_gate_check.py`** —
  unreferenced scaffolding; `feature_smoke` overlaps `smoke.py`, and
  `pin_gate_check` duplicates `tests/test_guest_pin.py`.
- **Three unreferenced static files:** `static/ubyhost-logo.jpg` (duplicate of
  the `.png` that *is* used), `static/guide/housebook-filters.png`,
  `static/guide/help-link.png`.

### No-op wrappers and phantom parameters

- `reporting.maybe_submit_after_verify:506` → `return None`, called from a live
  route (finding 40).
- `reporting.maybe_submit_after_host_save:501` → `try_immediate_submit:419` →
  `maybe_submit_after_completion:463`. **Three names for one hop**, and the
  middle one spends a `SELECT * FROM guest` purely to read `reservation_id`.
  Its own comment calls it a "compatibility wrapper" for callers that no longer
  exist.
- `submit_batch(verified_by_user_id=...)` — dead parameter threaded from three
  routes (finding 38).
- `want_pdf` — plumbed through three layers (`reporting.py:694` →
  `client.py:153` → `soap.py:87`) and **no caller ever passes anything but
  `True`**. Since the Doručenka is legally the thing the host must be able to
  save, it should be unconditional rather than a knob.
- 11 env vars are read at import with no value set in `deploy/`, `render.yaml`,
  `Dockerfile`, CI or docs. Two are load-bearing if ever wrong:
  `UBYHOST_MAX_BATCH` (finding 41) and `UBYHOST_SOAP_WSA_HEADER`
  (`client.py:18` — flips WS-Addressing headers on every envelope sent to the
  police, entirely untested, and until this audit documented nowhere).

### Duplication

The pairs worth fixing, in order of consequence:

1. **Two independent guest-record extractions.** `routes/admin.py:1479-1499`
   (`GUEST_TEXT_FIELDS` + `_guest_payload`) vs `routes/guest.py:1167-1178`,
   which writes the same 11 field names out by hand as an inline dict. Add a
   field to one and the other silently drops it from the police record.
   `_guest_signature_from_form` (`admin.py:1502-1509`) is likewise re-inlined at
   `guest.py:1190-1192`.
2. **Two independent completeness checks.** `reporting.guest_issues:177-191` vs
   `routes/guest.py:1199-1207` — both re-run `validate_guest` and each appends
   its own signature-missing issue, one in hard-coded English and one
   translated. These two predicates decide whether a record gets filed; if one
   gains a rule the other silently disagrees.
3. **Three vocabularies for one status enum.** `reporting.STATUS_LABELS:264-272`
   (7 English strings, exposed to Jinja) vs `reporting.status_label:346-358`
   (5 more, production-dead) vs the actually-rendered i18n labels in
   `host_i18n.py` used by `_components.html:173`.
4. **Two conventions for "what does a naive timestamp mean."**
   `reporting.py:536-543` treats `registration_completed_at` as UTC;
   `deadlines.local_now:91-96` treats naive as Prague civil. Both live in the
   reporting path. This is the split that produces an off-by-one on the
   automation delay around midnight.
5. **Two translation engines.** `i18n.normalise_language:907` and
   `host_i18n.normalise_language:2699` are identical; `i18n.translator:912` and
   `host_i18n.translate:2742` are the same lookup-with-EN-fallback-then-`%`,
   except the host one wraps interpolation in try/except and **the guest-facing
   one does not** — so a malformed key raises on the guest form and degrades
   gracefully on a host page. They also disagree on default language
   (`i18n.DEFAULT_LANGUAGE = "en"` vs `host_i18n.PUBLIC_DEFAULT_LANGUAGE = "cs"`).
6. **`_fmt_date`** — byte-identical three-line function in `templating.py:31-33`
   and `alerts.py:21-23`; the same `%d.%m.%Y` literal hard-coded again at
   `reporting.py:992`, `:994` and in two templates.
7. **13 inline `SELECT * FROM apartment WHERE id = ?`**, 12 of them
   ownership-blind: `reporting.py:160`, `:465`, `:515`, `:619`, `:896`;
   `routes/admin.py:57`, `:145`, `:1194`; `routes/guest.py:249`; `demo.py:190`,
   `:349`, `:540`. The `reporting.py` five are defensible (no request in scope);
   `admin.py:145` and `:1194` are inside request handlers that already have
   `access.apartment` available.
8. **Eight escaped ownership joins.** `access.py`'s docstring says keeping these
   in one module "makes an omitted ownership check conspicuous". The same join
   shape is now written inline at `routes/admin.py:249`, `:1039`, `:1113`,
   `:1894`, `:1946`, `:1960`, `alerts.py:151`, `reporting.py:974`.
9. **Two identical bulk-zip download routes** — `routes/admin.py:1885-1937`
   (receipts) and `:2103-2141` (house-book PDFs), same 20-line shape down to the
   function-local imports.

### Naming and structure

Module naming is a real strength: `reporting`, `deadlines`, `housebook`,
`icalsync`, `claim`, `passport_photos`, `ubyport/` all name the domain rather
than the technology. The outliers are `access.py` (the concept is "workspace"),
`templating.py`, `admin_helpers.py` ("helpers" is not a concept), and
`stays_import.py`, which after the dead-code sweep is an **export**-only module.

Where naming stops being honest is inside `reporting.py`:
`maybe_submit_after_verify` (does nothing), `try_immediate_submit` (does not
submit immediately), `maybe_submit_after_host_save` (forwards) — three names
describing a control flow that no longer exists, in the module that decides
whether a police filing goes out.

**`routes/admin.py` (2,321 lines)** *is* navigable — eleven banner comments mark
the sections. But those banners are the seam lines of at least eight distinct
responsibilities: dashboard/work-queue assembly (including the `dashboard_rows`
query engine at `:121-164`), the command-palette JSON API, demo load/reset,
onboarding and celebrations, legal-entity CRUD, apartment/feed/credential CRUD,
reservation and guest CRUD plus the send actions (the legally significant part),
and eight export/retention/archive endpoints. `dashboard_rows` in particular is
domain logic that belongs beside `reporting.reservation_progress` — and its
absence from `reporting.py` is *why* `count_sendable_stays` exists as a second,
redundant traversal.

**i18n is structural in its data, bolted on in its machinery.** The five
satellite modules (`landing`, `terms`, `privacy_policy`, `dpa`, `subprocessors`)
are pure data merged into `host_i18n` by a loop at `:2675-2696` — a sound split
that keeps long legal prose out of the UI catalog. Two engines and two delivery
paths for one concept is the bolted-on part (duplication item 5), plus:
`templating.py` wires only `host_i18n` into Jinja globals, so guest templates
receive their `t` per-route as a context value instead.

**Hard-coded English in Python-generated text.** The pattern is stark:
templates are translated, Python-generated strings are not. `routes/guest.py`
has **zero** untranslated flash messages; `routes/admin.py` has **99**
(`err="..."`/`msg="..."`), plus 5 in `admin_accounts.py`. Every alert title and
detail in `reporting.py` (`:494`, `:751`, `:859`, `:863-864`, `:912`) and
`icalsync.py` (`:211-212`, `:249`, `:367-368`) is an f-string in English —
including *"A stay from … was cancelled in the calendar after it had already
been reported to the police"*, one of the most consequential messages the
product can emit, read by a Czech host in English. `reporting.py:184-186` is a
validation error **a guest** can see, in English. And `reporting.py:997-1003`
builds English deadline prose that is then **discarded**, because
`alerts.present:83-122` rebuilds `deadline` messages from `host_i18n`.

### Efficiency

| # | Location | Sev | Finding |
| --- | --- | --- | --- |
| 52 | `App/app/db.py:283-295`, `:316-347` | **High** | `connect()` calls `_add_missing_columns()`, which issues **one `PRAGMA table_info` per entry in the 23-entry `ADDED_COLUMNS` tuple** — re-pragmaing `apartment`, `guest` and `legal_entity` four times each, because the loop is over columns not tables. Every `query()`/`query_one()`/`execute()`/`cursor()` opens a fresh connection. So **one logical query = 1 file open + 1 `chmod` + 2 pragmas + 23 `PRAGMA table_info` + the actual SQL — 26 statements, 25 of them overhead (96%).** `init_db` already calls the same function at startup. The comment justifying it describes a file-replaced-under-a-running-server scenario that does not occur in the Docker deployment. |
| 53 | `App/app/routes/admin.py:1946-1948` | **High** | `submissions_list` does `SELECT s.*` over 200 rows. That table holds `receipt_pdf`, `error_pdf`, `request_xml` and `response_xml`. The page needs id, created_at, state, internal_name and `bool(receipt_pdf)`. At a plausible ~60 KB receipt + ~15 KB XML per row that is **~15 MB of blobs materialised to render a list**. Same problem, smaller, at `:1894` (receipts zip, which touches four columns) and `:1256-1261` (reservation detail). |
| 54 | `App/app/reporting.py:638` | Medium | `collect_sendable`'s main query already joins `reservation` and selects `r.id AS res_id`, then the loop throws that away and issues `SELECT * FROM reservation WHERE id = ?` **per guest**. This is in the send path. |
| 55 | `App/app/reporting.py:511-521`, called at `routes/admin.py:1082` | Medium | `count_sendable_stays` is called **immediately after** the loop at `:1067-1080` has already computed `progress` and `controls` for exactly those rows — and then re-derives the number with 3 queries per reservation (apartment + guests + `is_demo_apartment`). At a page size of 50 that is ~150 wasted queries for a number available as `sum(1 for i in rows if i["controls"]["send_enabled"])`. `queue_counts:319-332`, two hundred lines away, takes the already-computed groups — the right shape already exists in the same file. |
| 56 | `App/app/reporting.py:222`, `:227` | Medium | `reservation_progress` calls `guest_is_complete` — a full `validate_guest` — on **every guest twice**, to build `complete` and then `incomplete`, when `incomplete` is exactly `guests - complete`. The function itself is N+1 across `dashboard_rows`, `reservations_list`, `count_sendable_stays`, `check_deadlines`, `refresh_registration_completed_at` and `alerts.present` (once per rendered stay alert on *every* page). |
| 57 | `App/app/reporting.py:363`, `:374`, `:900-903` + `demo.py:32-34` | Medium | `is_demo_apartment` runs a `legal_entity` query on **every dashboard row and every reservations-list row, on every deployment**, even though `demo.seed` refuses to run unless `UBYPORT_ENV == "mock"`. A preview feature paying rent in the reporting hot path. |
| 58 | `App/app/db.py:203-209` | Medium | Missing indexes for queries that actually run: **`submission(apartment_id)`** — five call sites join on it, so every submissions page and receipts zip full-scans the widest table in the schema (compounding finding 53); `audit(owner_user_id, id)` — full scan + sort of the fastest-growing table; `email_outbox(state, next_attempt_at)` — the scheduler's outbox poll, every 5 minutes. Inversely, `idx_guest_state` exists but **no query filters on `guest.submit_state` in SQL** — every such test is in Python. An index maintained on every write and never read. |
| 59 | `App/app/config.py:11-15`, `:49` | Medium | Importing `app.config` creates directories, `chmod`s them, and **generates and writes a 48-byte secret to disk** if absent — or raises `RuntimeError` before logging is configured if `UBYHOST_SECRET_KEY` is too short. Any `import app.config` from a test or a `tools/` script mutates the filesystem, and import order silently decides whether stored credentials stay decryptable. |

Combined estimate for one dashboard load (3 apartments, 50 in-window
reservations, counted from call sites — not instrumented, since the audit
environment has no FastAPI installed): **≈174 SQLite connections, ≈174 `chmod`
syscalls, and ~4,000 `PRAGMA table_info` executions.** The reservations list
adds ~150 more connections via finding 55. It works at this scale; it is the
kind of thing that stops working exactly when a host has enough bookings to
need the tool.

### Tests

**48 files, ~400 `def test_` functions.** Coverage of the three product steps is
genuinely good, and the prioritisation is correct — the compliance-critical path
is the best-tested part.

Verified present and real:

- **"A guest is never submitted twice" — tested four ways**, including
  `test_endtoend.py:381-388` (a full `sweep()` creates zero new submissions
  after acceptance) and `test_duplicate_guard.py:182`
  (`test_concurrent_sends_claim_each_guest_once` — a real concurrency test
  against the `submission_claim` lease, not a mock).
- **Transport-error behaviour — tested properly.**
  `test_endtoend.py:728-767` raises `UbyportTransportError`, asserts the guest
  stays `pending`, the submission row is `transport_error`, and a *critical*
  unresolved alert exists; then removes the patch and asserts the record goes
  out and the alert clears.
- **The statutory deadline — thoroughly tested.** `test_deadlines.py` covers
  Easter for three years, the holiday set, Good Friday's 2016 start,
  weekend and holiday skipping (17 Nov 2026 falls on a Tuesday), all five
  urgency buckets, Czech plural forms, and a DST crossing (check-in 26 Mar 2026,
  deadline 31 Mar, asserting either side of the 22:00 UTC boundary).
- `test_endtoend.py` is ordered and stateful (`test_01`…`test_29`) and reads as
  a narrative of the actual product; `test_28` asserts the audit trail.

Gaps and weak tests:

| Location | Sev | Finding |
| --- | --- | --- |
| — | **High** | **No test covers a guest whose `stay_from` differs from the reservation's `date_from`** — the input to finding 39, the one finding here that can cause a *missed* filing. |
| — | **High** | **No timezone coverage in the iCal suite at all.** Every fixture in `test_icalsync.py` uses `VALUE=DATE`. No `DTSTART...Z`, no `TZID=`, no floating datetime, no `VTIMEZONE` — so finding 4 is entirely untested. |
| — | High | **Partial feeds are untested.** Only the *fully* empty calendar is covered (`test_icalsync.py:144-192`); the mass-cancel branch at `icalsync.py:355-376` (finding 3) has no test. Nor does duplicate-UID-within-one-feed, cancelled-then-rebooked, `status='ignored'` persistence, or `is_block` auto-cancellation. |
| — | High | **No test that the signature is validated server-side** — no size cap, no "non-image `data:image/` payload is rejected", no test that a bogus signature fails to unlock the form (finding 20). |
| — | High | **No CSRF test for any guest POST** (`test_security.py:39-94` covers host routes only), no test that the claim secret is single-use or expires after `confirm()`, no test that `submission.request_xml` is ever purged (`test_retention.py` covers the guest row and the photo only), and no test that `guest_archive` removes the passport photo. |
| — | Medium | **No scheduler tests exist at all** — no test references `scheduler.start`, so finding 1 has no regression guard (`conftest.py:32` disables the scheduler globally). |
| `test_deadlines.py:131-148` | Medium | `test_deadline_watch_uses_czech_time_and_keeps_old_compliance_debt` monkeypatches `db.query` to return `[]` and asserts on the **SQL string** (`"date_from >= ?" not in captured["sql"]`). The loop body of `check_deadlines` — every alert decision — is never entered. Renaming a column breaks it; a logic inversion passes. The name promises the strongest claim in the product and the test cannot observe it. |
| `test_duplicate_guard.py:229-254` | Medium | Asserts `state == "ok"` for a duplicate with no receipt — locking in finding 37 as correct rather than flagging it. |
| `test_deadlines.py:81-116`, `:119-128`, `:70-72` | Low | Re-implements the plural-key construction from `templating.py:70-76` inside the test and asserts against the catalog (so dropping the `.few` branch in the helper still passes); asserts `describe_time_left(...)` equals a string built from its own inputs; and sorts by `URGENCY_ORDER` then asserts the result is `URGENCY_ORDER`'s key order. |
| `test_calendar_sync_ui.py:33-47` | Low | Stubs `icalsync.sync_all` entirely, so the "UI" coverage asserts nothing about what the host is told when feeds fail. |
| `feed_fetch.py` | Medium | Almost untested: `test_feed_dns_pinning.py` covers one scenario and stubs the pinned connector. Nothing exercises the 5 MiB cap, the redirect chain, a non-200, the "not an iCal" guard, an https→http redirect downgrade, a mixed public/private DNS result, or concurrent fetches against the global patch (finding 9). |
| `reporting.client_for:552` | Medium | Never exercised against anything but the mock — NTLM domain assembly, TLS verify and `use_ntlm=(env != "mock")` have no test. Reasonable, but worth knowing the real transport configuration is unverified. |

### CI

- **Lint is deliberately minimal and does gate:**
  `ruff check app tests --select E9,F63,F7,F82` — the "will it crash" subset. It
  excludes `F401`/`F841`, which is why the 20 dead definitions survive, and it
  **excludes `tools/`**, which is why a file that raises `IndentationError` is
  still committed.
- **Types do not gate.** `mypy app` runs with `continue-on-error: true` plus
  `--follow-imports=skip` (so it does no cross-module analysis) and six
  permissive flags. Honestly labelled "baseline", but it is decoration.
- **Tests gate**, with the mock UbyPort spawned for real, and a smoke job after
  them.
- **Coverage is measured and not enforced** — no `--cov-fail-under`, no upload;
  the XML is generated and discarded.
- **`deploy-production.yml` has two gaps, Medium.** `workflow_dispatch` bypasses
  the CI gate entirely, and the remote script does
  `git fetch origin main && git reset --hard origin/main` — it deploys **the
  current tip of `main`, not the commit CI validated**. If two commits land
  while CI runs on the first, the successful run of commit A deploys commit B
  unvalidated. For an app that files to a police register, that is the gap I
  would close first. There is no post-deploy production smoke check and no
  rollback step.

---

## 5. Domain-risk findings

Restated deliberately, because these carry outsized severity.

**Can a guest's passport data be exposed?** Not to another guest, and not to
another host — that part is genuinely well built (see the note after §3.2). The
exposure is at rest: **plaintext `doc_number` on the guest row (48), a second
cleartext copy inside `submission.request_xml` that no code path ever deletes
(35), and backup scripts that do not encrypt (documented in the new
`docs/OPERATIONS.md`).** Secondary paths: an archived guest's passport scan
stays on disk (28), a guest-controlled `stay_to` can keep it there indefinitely
(19), and working claim links sit in cleartext in `email_outbox.payload` for 14
days (29).

**Can a report be sent twice, or never sent?**

*Twice* — well defended. The `submission_claim` lease is a real cross-process
lock with a real concurrency test, `collect_sendable` refuses `sent` and
duplicate-`blocked` records even under `allow_resend`, and a 150 response is
correctly read as "the register already has it". The residual is finding 42: a
batch that outlives the 5-minute lease could be re-claimed, producing a spurious
duplicate against the host rather than a double filing.

*Never* — this is where the risk actually lives, and there are five independent
paths to it:

1. The paused `ical` job (1) — the booking never enters the system, so
   `check_deadlines` never sees it.
2. The signature wipe on a date change (2) — the record becomes incomplete and
   the sweep stops picking it up, with no alert.
3. The partial-feed mass-cancel (3) — cancelled stays drop out of the deadline
   query.
4. Guest-controlled `declared_guests` inflation (22) — `registration_completed_at`
   is never set, so immediate-mode automation never fires.
5. A Turnstile outage (27) — the guest cannot register at all, fail-closed, no
   alert.

And a background job that dies takes the deadline watch with it, silently
(`scheduler.py:31-37`) — so the alerting that would catch paths 1–4 is itself
unmonitored.

**Is the legal deadline computed timezone-safely?** The computation is correct —
Czech holidays, working days, `Europe/Prague`, DST, all tested. **The anchor is
wrong** (39): the deadline runs from `reservation.date_from` while the filing
uses `guest.stay_from`, and per finding 19 the guest supplies the latter. Two
supporting inconsistencies: `icalsync.py` uses process-local `date.today()` for
its future/past cutoff (10), and `reporting.py:536-543` treats a naive
`registration_completed_at` as UTC while `deadlines.local_now` treats naive as
Prague civil (duplication item 4).

**What if UbyPort is down, slow, or changes shape?** Down or slow is handled
properly — critical alert, queue preserved, retried, tested end to end. A shape
change is handled better than most: `client.py:167` refuses a response whose
record count does not match the request, and unreadable XML becomes a transport
error. The soft spot is semantic, not structural: classification leans on
substring-matching the Czech code book (45), so a police-side wording change can
silently move records between "fix and resend" and "permanently parked" with no
error anywhere.

---

## 6. Prioritized punch list

Critical and High only.

1. **Stop deleting collected signatures on a calendar date change**
   (`icalsync.py:300-316`) — or if wiping is the intended policy, raise an alert
   and re-invite the guest, because today the host is never told.
2. **Add a deletion path for `submission.request_xml`/`response_xml`**, and
   include them in the retention purge. Keeping the Doručenka has an evidential
   basis; keeping the request envelope's passport numbers forever does not.
3. **Fix the paused `ical` job** (`scheduler.py:71-74`) — register it with a
   normal first run, or re-arm it when a feed is added rather than only at boot.
4. **Encrypt `guest.doc_number` (and consider `birth_date`) at rest**, or
   document the decision not to. The Fernet machinery already exists in
   `db.py:432-450`; it is simply not pointed at guest data.
5. **Anchor the deadline on the same date that gets filed** — `guest.stay_from`
   with a fallback to `reservation.date_from`, matching `_stay_dates` and
   `housebook.py:99-104`. Add the test for the two differing.
6. **Bound `stay_from`/`stay_to` server-side to the reservation** — they are
   guest-supplied hidden fields that land in the police record and control photo
   retention.
7. **Add CSRF (or at minimum the same-site check) to the guest router**, and
   stop disabling `protect_host_post` outside production.
8. **Validate `signature_png` properly** — length cap, base64 decode, MIME
   allow-list, real-image probe. `passport_photos.py:64-84` already shows how;
   and add a request-body limit in Caddy while you are there.
9. **Rotate or clear the claim `token_hash` on `confirm()`** and check
   `token_version`, so a forwarded claim e-mail is not permanent access.
10. **Convert `datetime` DTSTART/DTEND to `Europe/Prague` before taking
    `.date()`** (`icalsync.py:103-108`), and add the missing timezone fixtures.
11. **Make the partial-feed guard proportional** — treat a feed returning
    dramatically fewer events than the stored set as suspect, not as authority
    to cancel.
12. **Tighten the sync exception boundary** — wrap `sync_feed` in `sync_all`, and
    widen `icalsync.py:240` beyond `(FeedError, ValueError)`, so one bad feed
    cannot stop every apartment.
13. **Raise an alert when a background job raises** (`scheduler.py:14-63`) — the
    deadline watch dying is the one failure that must not be silent.
14. **Serialise or remove the global `create_connection` patch**
    (`feed_fetch.py:46-70`) — as written, a concurrent "Sync now" can defeat the
    DNS-pinning defence.
15. **Reject a guest-supplied `declared_guests` increase**, or exclude
    guest-declared counts from the `registration_completed_at` gate.
16. **Give `guest_archive` the same photo deletion as `guest_delete`**
    (`admin.py:1752` vs `:1805`).
17. **Use `auth._secure_cookies()` for the guest cookies** (`guest.py:156`,
    `:181`, `:192`) so `DEPLOYMENT=production` alone guarantees `Secure`.
18. **Stop accepting 4-digit PINs**, and add an escalating lockout — 10 failures
    per 15 minutes with no lockout is ~960 attempts/day/IP against a 10⁴ space.
19. **Give Turnstile a fail-open or an alert** (`turnstile.py:27-40`) — a
    Cloudflare outage currently blocks guest registration outright.
20. **Either read `verified_by_user_id` in `submit_batch` or delete it**
    (`reporting.py:696`) — today the send path records no actor, and the comment
    at `:582-584` describes behaviour that no longer exists.
21. **Distinguish "duplicate-derived `sent`" from "accepted with a Doručenka"**
    in the stored submission state (`reporting.py:788-807`), and decide what a
    112 should actually mean for `submit_state` (`errors.py:85`).
22. **Narrow `submissions_list` to the columns it renders** (`admin.py:1946`) and
    add an index on `submission(apartment_id)`.
23. **Move `_add_missing_columns` out of `connect()`** (`db.py:294`) — it is a
    startup concern sitting in the innermost loop, and `init_db` already calls
    it.
24. **Deploy the commit CI validated**, not `origin/main`'s tip, and close the
    `workflow_dispatch` bypass (`deploy-production.yml:21`, `:76-77`).

---

## 7. Open questions

Things that could not be settled from the code alone. Listed rather than guessed.

1. **Is the `reservation_id` enumeration at `guest.py:334-348` intentional?**
   `tests/test_claim_mail.py:401` asserts that a link reaches old incomplete
   reservations, which reads as a deliberate "let a guest finish an old form"
   affordance. If so, it wants a time bound; if not, it is an access-control
   bug.
2. **What is a code 112 supposed to mean operationally?** Does the register hold
   a late-filed record or refuse it? The answer decides whether `blocked` +
   "Rejected" is right, or whether such a record needs its own terminal state.
   This is a question for the Foreign Police, not for the code.
3. **Is the 3-working-day window counted from the arrival day or the day after?**
   `add_working_days` does not count the arrival day, so a Monday check-in
   yields Thursday 23:59:59. The stricter reading of §100(c) of Act 326/1999
   would give Wednesday. The code picks the more generous reading with no comment
   saying so. Worth one line of citation either way. *[Not a legal opinion.]*
4. **Are there any `apartment`/`legal_entity` rows with `owner_user_id IS NULL`
   in production?** `access.py` uses `IS ?` throughout, which matches NULL-owner
   rows when no workspace user resolves. A single query settles whether finding
   49 is latent or live.
5. **Was CSRF on guest routes a considered decision?** `static/csrf.js:13`
   explicitly skips `/l/` paths, which suggests it was — but the reasoning is
   not recorded anywhere, and `docs/SECURITY.md:45` discloses the gap without
   justifying it.
6. **Does anything retry a failed UbyPort submission other than the 10-minute
   sweep?** The sweep only picks up stays that `due_for_automatic_send` accepts,
   which requires `registration_completed_at` — so a stay in `error` whose
   completion timestamp was cleared may depend entirely on the host noticing the
   alert. This could not be ruled out by reading.
7. **Is `stays_import.import_csv` (and `housebook.import_csv`) intended to ship?**
   ~90 lines each, no route, no test, and `docs/TECHNICAL_COMPLIANCE_AUDIT.md`
   reasons about imported records as if hosts could reach them. Either wire them
   up with the `UNIQUE (apartment_id, uid)` collision handled, or delete them and
   correct the doc.
8. **Is the `mail` scheduler job's absence from `env_guard`'s warning list
   deliberate?** With the scheduler off, no guest e-mail is sent at all, and
   neither `env_guard.py:116-120` nor the docs mentioned it before this audit.
9. **Should `demo.is_demo_apartment` be in the reporting hot path?** It costs a
   query per dashboard row on every deployment, for a feature gated to
   `UBYPORT_ENV == "mock"`. A cheap `apartment` column or an in-process cache
   would remove it, but whether demo apartments can be created outside mock by
   another route is not clear from the code.
10. **Verified counts in the existing docs do not reconcile.**
    `docs/SECURITY_REVIEW_2026-09-15.md:95` says "328 passed",
    `docs/NEXT_MAIL_RELEASE.md:25` says "436 passed", and the repo has ~400 test
    functions. Neither figure is reproducible from the docs as written. Also,
    `docs/TECHNICAL_COMPLIANCE_AUDIT.md` is dated 15 September 2026 but verifies
    legal text "dated 19 September 2026" — it claims to have checked text
    effective four days after its own review date.

### Two corrections to the existing audit docs

While cross-checking, two items those documents mark as open turned out to be
contradicted by the code, which is worth knowing before they drive work:

- **`TECHNICAL_COMPLIANCE_AUDIT.md:79`** says no per-record demo prohibition was
  identified at the UbyPort client boundary. One exists:
  `reporting.py:900-903` short-circuits any send for a demo apartment,
  `:374` excludes demo rows from collection, and `demo.py:450` refuses to seed
  outside mock.
- **`TECHNICAL_COMPLIANCE_AUDIT.md:78`** says there is no staging→prod
  prohibition. There are four: `env_guard.py:93-103` (fatal for `prod` without
  `DEPLOYMENT=production`, and for `prod` on Render), run by
  `docker-entrypoint.sh:10`; `render_start.sh:31-35`; and
  `deploy/lightsail/scripts/preflight.sh:37-50`. What is genuinely missing is
  only a guard on `staging → test`, since `env_guard` permits `test` anywhere.
  The finding should be narrowed to that.

---

## Appendix — documentation changes made

Code was not modified. These documentation files were, in the repo clone:

| File | Change |
| --- | --- |
| `docs/ENVIRONMENT.md` | **New.** Complete reference for ~40 environment variables read by the app and the deploy/backup scripts, with defaults and failure modes. 16 of them were documented nowhere before, including `UBYHOST_TRUSTED_PROXY_CIDRS` (a security control), `UBYHOST_SOAP_WSA_HEADER` (the police-integration escape hatch) and the three legal-version overrides. |
| `docs/OPERATIONS.md` | **New.** Runbook for the things missing from the docs: the five scheduled jobs and their two surprising behaviours; the `submit_state` state machine and every transition; what codes 112 and 150 actually do; all ten alert kinds with levels and clearing conditions; the `ADDED_COLUMNS` migration mechanism and its rules; a secret-key loss/rotation recovery procedure; what retention actually deletes and what it never deletes; and the gaps in backup/restore. |
| `README.md` | Rewritten — was a 5-line stub titled with the repo slug. Now names the product and indexes every doc, grouped by purpose, with the two audit docs marked as predating the 1.1.0 release. |
| `App/README.md` | Corrected the claim that losing `UBYHOST_SECRET_KEY` costs only the UbyPort password (it also invalidates all sessions and cookies, breaks TOTP, and silently stops reporting); noted that the key also encrypts TOTP secrets; noted that the 7-variable config table is not the whole surface; noted that house-book retention expiry is a manual button, not a scheduled job. |
| `docs/PRODUCTION_CHECKLIST.md` | Fixed the UbyPort error table: duplicates become `sent`, not `not_correctable`, and that submission carries no Doručenka. |
| `docs/LIGHTSAIL.md` | Added the missing `mail` job (5 min) to the scheduler table; noted that the scheduler being off stops all guest e-mail; added the paused-`ical`-job and silent-job-failure caveats. |

Not changed, and flagged instead: the stale comment at `App/app/config.py:66`
promising a runtime batch-size refresh that does not happen (finding 41), and
the stale comment at `App/app/reporting.py:582-584` describing verification on
send that no longer occurs (finding 38). Both are code.
