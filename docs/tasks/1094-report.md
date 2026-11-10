# 1094 H0 answers (read-only, head-count change)

Base: branch tip c07a0504. Lines are from this tree (grep-confirmed). `G` = `App/app/routes/guest.py`. No test or server was run.
Common to all guest routes in (a): `_open_link` + `_require_pin` (PIN cookie) run first. `_reservation_for_guest` loads the stay.

## (a) Lead changes after claim

Verdict: the claim check is a DEVICE cookie, not a lead check, and it is skipped when mail is off (`G:1244`) and for a logged-in host who owns the flat (`G:1246`). Nothing in guest.py checks "is lead" or "is member".
Verdict: edit, remove and add-person route through three different guards; the only audited ones are remove, save (new and edit alike, no field names) and the count (numbers only).

`_require_claim_session` (`G:1243-1257`): mail off: pass; host owns apartment: pass; else `claim.ensure_row`, `guest_access_open` (else 404 stay_gone), `_device_holds_claim` (`G:279-287`: signed cookie `CLAIM_COOKIE` holds the stay with generation equal to `token_version` of a CLAIMED row), failing that 303 to the stay page. A device holds the cookie only after `claim.confirm` with the e-mail secret (`G:1685`), so a member can pass only by being given the mail link. `_owned_ids` (`G:164-172`): signed cookie `OWNED_COOKIE` with the guest ids this browser saved (`_remember_owned`). Not a role.

| Route | Method | Function file:line | Fields written | Posted from template | Claim checked | Lead checked | Class | Old value read from | Audit event and detail keys | Brief |
|---|---|---|---|---|---|---|---|---|---|---|
| `/l/{token}/pin` | POST | verify_pin `G:1268` | PIN cookie, rate-limit counters, 3 lockout audits (`G:1309,1324,1344`) | guest pin page | no (it is the PIN) | no | other | n/a | lockout audit rows only | none |
| `/claim` | GET | claim_landing `G:1580` | `claim.ensure_row` INSERTs an empty reservation_claim row if none (`claim.py` ensure_row `db.insert`); no mail | link from stay page | no | no | other | n/a | none | none |
| `/claim/confirm` | POST | claim_confirm `G:1636` | `claim.confirm`: reservation_claim state=CLAIMED, secret cleared; applies pending count via `headcount.apply_declared_in` (`claim.py:710`); cookie | `guest/confirm.html` | by secret + rate limit 20 | no | first registration | reservation_claim.declared_guests (pending count) | `reservation_declared_guests_set` / `_refused`, `id= from= to= source=claim_confirm` (`headcount.py:84-106`) | H1 |
| `/party` branch 1: set count, mail OFF | POST | set_party_size `G:1687` (lines 1710-1730) | `reservation.declared_guests` via `headcount.set_declared_guests` | stay.html party form | NO (no guard at all) | no | lead change (count) | reservation.declared_guests | `reservation_declared_guests_set`/`_refused`, keys `id from to source=party` | H2a |
| `/party` branch 2: count, claimed, mail ON | POST | `G:1780-1800` | `reservation.declared_guests` | stay.html | yes (`G:1786`) | device only | lead change (count) | reservation.declared_guests | same, `source=party` | H2a |
| `/party` branch 3: start claim by e-mail (stay not claimed, or e-mail posted) | POST | `G:1733-1778` -> `claim.start_claim` (`claim.py:226`) | reservation_claim: email, masked, lang, token hash, hold, pending `declared_guests`; outbox mail | stay.html / claim.html | NO (anyone with link+PIN; Turnstile + 10/hour limit) | no | first registration | reservation_claim row | none from the route (mail outbox row only) | none (Q8) |
| `/party` branch 4: re-send on claimed stay | POST | same branch, `resend` | new secret and hash only; `declared_guests` set NULL (`claim.py:281-292`); same e-mail required else `already_claimed` | stay.html resend | no | no | other (no data changes) | n/a | none | none |
| `/another` | POST | add_another_person `G:1813` | `reservation.declared_guests` +1 via headcount (`G:1839`); no-op if host override | stay.html | yes (`G:1828`) | device only | lead change (add, count) | reservation.declared_guests | `reservation_declared_guests_set`, `source=another` | H2b |
| `/new` | GET | guest_form_new `G:2028` | none in the guest table. Claim row via ensure_row only; reads the draft | redirect after save / link | yes (`G:2041`) | device only | other | n/a | none | none |
| `/edit/{guest_id}` | GET | guest_form_edit `G:2079` | none (renders the form) | stay.html | yes (`G:2091`) | owned id (`G:2094`, 403 not_yours) | other | n/a | none | none |
| `/remove/{guest_id}` | GET | guest_remove_confirm `G:2162` via `_removal_guard` `G:2123` | none (existing "are you sure" page, no old/new values) | stay.html | yes | owned id | other | n/a | none | H2b |
| `/remove/{guest_id}` | POST | guest_remove `G:2183` | DELETE guest row; clears `signed_for_*` of children; deletes passport file | remove confirm page | yes | owned id | lead change (remove) | guest row (all columns, `*_enc` decrypted by `db._hydrate`) | `guest_removed_by_guest`, `guest=<id> reservation=<id>`, actor=guest (`G:2213`) | H2b |
| `/relang` | POST | guest_form_relang `G:2236` | none (redraws form, nothing stored) | form language menu | yes (`G:2258`) | owned id | other | n/a | none | none |
| `/save` new person | POST | guest_form_save `G:2312`, insert in tx `G:2573-2640` | guest row (all form fields, `signature_png_enc`, notice, filled_ip, submit_state); count via `apply_declared_in` only if no count exists | `guest/form.html` | yes (`G:2326`) | no. A posted `guest_id` that is not owned is silently treated as NEW (`G:2335-2338`) | first registration when no guest row exists (`is_first`), else lead change (add) | n/a | `guest_form_saved`, `guest=<id> reservation=<id>` (`G:2662`) | H2b |
| `/save` existing person | POST | same, `update_if` `G:2545-2561` | all form fields, signature, `filled_*`, `submit_state` reset to pending, `submit_attempts` 0, photo if posted | `guest/form.html` (`guest_id` hidden) | yes | owned id | lead change (edit) | guest row; photo flag `passport_photo_at` + encrypted file | same `guest_form_saved`, NO field names, same event as new | H2b |
| `/save` count write | POST | `G:2594` `apply_declared_in(party_size)` | `reservation.declared_guests` when count is None | form.html first form | yes | no | first registration | reservation.declared_guests | `reservation_declared_guests_set`, `source=first_form` (`G:2650`) | H1 |
| `/draft` | POST | guest_form_draft `G:2721` | `guest_draft` row: `DRAFT_FIELDS` text only (includes `doc_number`), 60 chars each, new person only (`guest_id` set -> 204, nothing stored) | form.html autosave | yes (403, `G:2737`) | device only | other | n/a | none | none |
| `/scan` | POST | guest_document_scan `G:2785` | none (OCR result returned as JSON, nothing stored) | form.html | yes (`G:2803`) | none: no owned check, no guest id | other | n/a | none | none |
| `/guide/leon` | POST | `guest_leon.py:70` | no stay or guest column (only reads, `db.query_one`) | guide page | not read | no | other | n/a | none | none |
| `/g/{token}/leon` | POST | `guest_leon.py:97` | same | guide page | not read | no | other | n/a | none | none |
| `/p/{slug}/b/{booking_id}/{token}/cancel` | POST | booking_manage_cancel `property_page.py:536` -> `booking_cancel.cancel` (`booking_cancel.py:86` sets reservation cancelled) | reservation.status, claim expiry | booking manage page | no: booking token | no (booker, not a claim lead) | other (stay cancel by booker) | reservation.status | not read | none |

mail_unsubscribe.py (`:55`): no stay or guest data; it flips a lifecycle-mail flag for a host account by signed token. privacy_requests.py (`:38`, `:71`): `auth.require_login`, host only. No guest GET route writes stay or guest data; the only GET write is the empty claim row from `ensure_row` and the draft read.

Remove paragraph: `_removal_guard` (`G:2123-2159`) calls `_require_claim_session` (so with mail off, or for a host view-as-guest, no claim is needed at all) and then `guest_id not in _owned_ids(request)` -> 403 not_yours. That is a device rule: the person must have been saved on this browser. A member can pass only if their device holds the claim cookie AND saved that person; with only link + PIN and mail on, a member is redirected. The lead cannot remove or edit a person another device added, and cannot touch a host-added row (test `test_guest_edit_until_filed.py:156`). `/save` on an existing row uses the same owned rule (but fails open to "new person", see table); `/scan` has no owned rule. Remove never lowers `declared_guests` (floor stays, headcount unchanged).
Old values for the confirm page: guest table, columns plain or `*_enc` (`doc_number_enc`, `visa_number_enc`, `signature_png_enc`, `birth_date_enc`, `res_street_enc`, `res_city_enc`; `db.py:1043,1097-1100`, decrypted by `db._hydrate`). Signature is an encrypted data URL (<=256 KB); passport photo is a file (not a column) with the flag `passport_photo_at`.
Lead changes with no audit row today: `/save` existing person (the event exists but is the same as for a new person and holds no field names); `/party` branch 2 and `/another` have the count audit only (numbers, no guest position); photo replace (flag only inside `/save`).

## (b) Count writers and readers

Verdict: `headcount.py` is the only guest writer of `reservation.declared_guests` in production code; the only bypass is demo seeding (`demo.py`, source demo). The reservation_claim count reaches `reservation.declared_guests` only in `claim.confirm` through `headcount.apply_declared_in` with the floor, so the "second hole through start_claim" is closed by 1092.
Verdict: H1 must change Python (reporting, stays_export, claim, admin SQL), Go (recover.go, progress.go) and two template prefills together; three Go files read the count, not two.

| Where file:line | Language | Table | Read or write | Via | Copies the rule | H1 must change |
|---|---|---|---|---|---|---|
| `headcount.py:75` update | Python | reservation.declared_guests | write | via headcount | no | no |
| `headcount.py:50-61` | Python | reservation | read (override refuses, floor) | headcount | partial (override truthy) | yes |
| `demo.py:307,349,388,423,464,479,526` | Python | reservation.declared_guests | write | bypass (demo source) | no | no |
| `demo.py:118` | Python | reservation.expected_guests_override | write (1) | host/demo | no | no |
| `routes/admin.py:3871, 4082-4086, 4158-4162` | Python | override | write | host | no | no |
| `routes/admin.py:4131-4133` | SQL | override, declared | write + read | host | yes, `COALESCE(NULLIF(override,0), declared)` | yes |
| `booking_direct.py:48` | SQL | override | write (insert, `booking["guests"]`) | direct booking | no | no |
| `booking_webhook.py:76` | SQL | override | write (insert) | webhook | no | no |
| `db.py:204,205` | SQL schema | reservation | schema | n/a | no | no |
| `db.py:376` | SQL schema | reservation_claim.declared_guests | schema | n/a | no | no |
| `claim.py:281` | Python | reservation_claim.declared_guests | write (pending count; NULL when CLAIMED) | claim | no | no |
| `claim.py:688-714` | Python | reservation_claim | read, then clear | claim.confirm -> `headcount.apply_declared_in` | no | no |
| `claim.py:363-366` `_declared_count` | Python | override, progress, claim | read | resend | yes, own variant (`override` else progress else claim else 1) | yes |
| `reporting.py:420-424` `expected_guest_count` | Python | reservation | read | n/a | THE rule (`if override` else declared) | yes |
| `reporting.py:477` `reservation_progress` | Python | reservation | read | calls the rule | no | via rule |
| `stays_export.py:56` | Python | reservation | read (CSV guest column) | n/a | yes (`override or declared`) | yes |
| `routes/guest.py:1495-1496` | Python | claim, reservation | read (claim form prefill) | n/a | no (claim count else declared) | yes (prefill) |
| `routes/guest.py:1552, 1831` | Python | override | read (`can_raise_party`, `/another` no-op) | n/a | partial | yes |
| `routes/guest.py:2411, 2594` | Python | reservation | read | calls the rule | no | via rule |
| `routes/dashboard_calendar.py:102` | Python | via progress | read | calls the rule | no | via rule |
| `go/internal/ubyport/recover.go:166-205` | Go | reservation | read | n/a | yes (override != 0 else declared) | yes |
| `go/internal/calendar/handler.go:173` | Go | reservation | read (SELECT only) | n/a | no | yes only if a column is added |
| `go/internal/calendar/progress.go:88-100` `expectedCount` | Go | reservation | read | n/a | yes (override != 0 else declared) | yes |
| `templates/guest/claim.html:36` | template | claim + reservation | read (input value) | n/a | no: `claim.declared_guests or override or 1` | yes |
| `templates/guest/assigned.html:33` | template | claim | read (hidden `party_size`) | n/a | no | check |
| `templates/reservation_detail.html:375` | template | via progress.expected | read (input value, min = live rows) | n/a | no | no |
| `templates/reservations.html:58`, `_dashboard_calendar.html:54` | template | override | write path: input `expected_guests` posts to `admin.py:3871` | host | no | no |

Go: no non-test Go code writes either column (writes exist only in `recover_test.go:173` and `handler_test.go:145-155`). Go rule and Python rule treat override 0 the same way (truthy test; admin SQL uses NULLIF 0; `stays_export` uses `or`). No other Go package counts expected guests (`grep` found only the three files above). H1 change list: `reporting.py`, `stays_export.py`, `claim.py:363`, `admin.py:4133`, `recover.go`, `progress.go`, templates `claim.html`, `assigned.html`.

## (c) Sync

Verdict: no sync or booking path writes, clears or re-writes `declared_guests` on UPDATE; only direct booking and webhook write `expected_guests_override` and only on INSERT.
Verdict: a lead's lowered count survives every sync update, but a direct booking's override (set to the booked guests) blocks any lowering (`headcount.py:61`).

| Path | Insert writes count | Update writes count | Evidence file:line | Effect on a lowered count |
|---|---|---|---|---|
| iCal sync | no | no | insert `icalsync.py:849-866`; update payload keys `:745-753`, `changed` diff `:786-790`; email `:848`; cancel `:524,937` | untouched; a date move re-fits unsent guest windows only |
| `booking_ical.py` | no | no | grep found no reservation write | n/a |
| Direct booking | override = booked guests | no | `booking_direct.py:47-53` | override wins; lead cannot lower |
| Webhook | override = booked guests | no | `booking_webhook.py:75-82` | same |
| Booking cancel | n/a | no (status only) | `booking_cancel.py:86` | untouched |

## (d) checkin_hour

Verdict: nullable INTEGER, no default ("the host sets the hours; there is no default", `migrations/0007_door_codes.sql:4-5,16`); setup field `property_setup.py:40`, saved via `admin.py:2333,2633,2778` (`_hour_or_none`).
Verdict: readers disagree on empty: door codes need it, the booking site uses 15, the calendar draws 12:00. Recommended fallback: 15.

| Reader file:line | Empty or NULL means | Default |
|---|---|---|
| `door_codes.py:113` | stay excluded from code issue | none |
| `door_codes.py:179,436,905` | `datetime(hour=None)` raises TypeError (guarded only by the `:113` query) | none |
| `claim.py:422` | mail shows the date only, no time | none |
| `booking_site.py:100` (`DEFAULT_CHECKIN_HOUR = 15`, `:31`) | invalid or NULL -> 15 | 15 |
| `routes/dashboard_calendar.py:33-47,99-101` | draws 12:00, sets `timingFallback` | 12:00, visual only |
| `go/internal/calendar/handler.go:173` | read as text for display; null handling not read | not read |
| `routes/admin.py:2553`, `:764` | setup incomplete / lock needs both hours | none |

Recommended fallback hour for the cut-off: 15 (15:00 Europe/Prague). Reason: the booking site already uses it for the same idea (refund and cancel deadline, `booking_site.py:100,219`). The calendar's 12:00 is a drawing position, not a promise.

## (e) Go

Verdict: owner Q12 (2026-11-10) allows a small Go change in the same PR. H1 changes two Go functions: `RefreshRegistrationCompletedAt` (`go/internal/ubyport/recover.go:166`, decides filing time: it stamps `registration_completed_at`) and `expectedCount` (`go/internal/calendar/progress.go:88`, display only). `handler.go:173` is only the SELECT and needs no change unless a column is added.
Verdict: the brief's expected two files are corrected to recover.go + progress.go.

| File | Function | Current rule | Columns Go reads | Test table |
|---|---|---|---|---|
| `go/internal/ubyport/recover.go:184-188` | RefreshRegistrationCompletedAt | `expected := declared; if override != nil && *override != 0 { expected = override }` | date_from, date_to, registration_completed_at, expected_guests_override, declared_guests | yes: `recover_test.go:180` `TestRefreshRegistrationCompletedAt`, cases struct has `declared` but NO override field; add one |
| `go/internal/calendar/progress.go:88-100` | expectedCount | non-zero override wins, else declared (nil stays nil) | via stayRow from `handler.go:173` | `handler_test.go:309` `TestDashboardCalendarProgressAndTone`; seeds `handler_test.go:145-155` insert `declared_guests` only; no `progress_test.go` |

## (f) Signature and passport photo in the lead edit form

Verdict: a stateless confirm works for text and for a signature (the signature is already a hidden field), but not for a photo (multipart file, never held between steps).
Verdict: recommended for H2b: text + signature stateless; photo via a token to a short-lived encrypted pending file (no preview).

| Item | Held in | Survives a stateless confirm | Evidence | Option |
|---|---|---|---|---|
| Text fields | form inputs; `/draft` stores a text subset (`DRAFT_FIELDS`, 60 chars, 7 days, 20 per stay, new person only) | yes, as hidden fields | `guest_draft.py:20-22,24-49`; `G:2721-2780` | hidden fields |
| Signature | hidden input `#signature`, prefilled with the stored signature on edit (`data-kept`); data URL, PNG or JPEG, <=256 KB | yes (already works this way); `/save` requires a valid one every time | `templates/guest/form.html:315-316`; `validation.py:801,862`; `test_guest_edit_until_filed.py:77` | hidden field, no change |
| Photo, posted | file input in the multipart form, not echoed on error | NO: a file input cannot be refilled | `form.html:283`; `G:2437-2462` | see recommendation |
| Photo, not posted on edit | file on disk, encrypted (`passport_photos.save_photo`), flag `passport_photo_at` | kept (`has_existing_photo`, `G:2443`); never cleared | `G:2443-2462,2583` | none |
| Photo format | uploads <=5 MB (PDF <=15 MB); images re-encoded to JPEG; purged 7 days after check-in or 30 days after upload | n/a | `passport_photos.py:22-23,128-151,266-275` | n/a |
| `/draft` and photo or signature | `DRAFT_FIELDS` has neither | n/a | `guest_draft.py:24-49` | n/a |

Recommendation for H2b: build the confirm page statelessly (hidden fields for text and signature). When a new photo is chosen, accept it at the Change step, re-encode it with `passport_photos.prepare_upload`, hold it as an encrypted pending file under a random token (hidden field), and show "New photo (replaces current)" with no preview. The existing sweep (`passport_photos.purge_stale`) removes pending files; the confirm copy must not say "nothing is saved" when a photo is pending. A guest row, its audit row and the host mail change only on Confirm.

## Tests per route

| Route | Test file | Test names |
|---|---|---|
| `/pin` | `test_security.py`, `test_guest_pin.py` | not read per name (grep hits only) |
| `/claim`, `/claim/confirm` | `test_party_count_1092.py`, `test_claim_mail.py`, `test_guest_csrf.py` | `test_an_unconfirmed_claim_does_not_touch_the_count_and_confirm_applies_it_once` (230), `test_confirm_keeps_the_old_count_when_the_typed_one_is_below_the_rows` (251) |
| `/party` | `test_party_count_1092.py`, `test_guest_csrf.py` | `..lower the count below the live rows` (125), `..lowered to the live rows and the audit holds numbers only` (137), `test_the_ceiling_is_sixty` (155), `test_with_mail_off_the_open_party_post_has_the_same_floor` (192), `test_on_a_claimed_stay_the_leads_address_alone_cannot_change_the_count` (277), `test_the_party_the_guest_declared_is_recorded_with_a_valid_token` (csrf:158) |
| `/another` | `test_party_count_1092.py`, `test_guest_navigation.py`, `test_guest_pin.py` | none by name in 1092 (grep hit only) |
| `/new`, `/edit` | `test_guest_form_draft_1082.py`, `test_guest_form_draft_1087.py`, `test_guest_navigation.py`, `test_guest_edit_until_filed.py` | `test_a_complete_signed_form_can_be_reopened_and_changed_before_filing` (59), `test_a_device_cannot_edit_or_remove_a_person_it_did_not_add` (156) |
| `/remove` | `test_guest_edit_until_filed.py`, `test_under15_signature_1089.py`, `test_guest_csrf.py` | `test_remove_asks_first_then_deletes_the_person_and_updates_the_headcount` (168), `test_a_filed_person_cannot_be_removed_even_after_the_confirmation_loaded` (193), `test_a_person_being_filed_right_now_is_not_removed` (204), `test_removing_one_of_two_people_keeps_the_other_and_says_so` (236) |
| `/relang` | `test_guest_form_draft_1087.py`, `test_under15_signature_1090.py` | not read per name |
| `/save` | `test_party_count_1092.py`, `test_guest_edit_until_filed.py` | `test_the_first_form_sets_the_count_with_one_audit_row` (421), `test_a_save_after_the_count_was_lowered_is_refused` (437), `test_two_phones_cannot_both_take_the_last_slot` (396), `test_an_edit_still_needs_a_valid_signature_and_the_legal_tick` (77), `test_an_edit_made_before_filing_is_what_gets_filed` (142) |
| `/draft` | `test_guest_form_draft_1082.py`, `test_guest_form_draft_1087.py` | not read per name |
| `/scan` | `test_doc_ocr.py` | not read per name |
| `/guide/leon`, `/g/{token}/leon` | `test_guest_leon_chat.py`, `test_leon.py` | not read per name |
| booker cancel | `test_booking_cancel.py` | not read per name |
| `reporting.expected_guest_count` | `test_deadline_cap_filing.py`, `test_wp28_geometry.py` | grep hit only |
| `headcount` writers | `test_party_count_1092.py` | `test_every_writer_takes_the_reservation_key` (450) |
| Go | `recover_test.go`, `handler_test.go` | `TestRefreshRegistrationCompletedAt`, `TestDashboardCalendarProgressAndTone` |

## Pointers for H3 and H4

- `db.py:2152 audit(action, detail, actor, owner_user_id)` | audit helper; table `audit` columns: id, at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id (`db.py:320-329`); detail is free text, `headcount.record` writes `id= from= to= source=` (`headcount.py:84-106`)
- `mail.py:244 enqueue(kind, idempotency_key, to_email, subject, payload, ...)` | the mail queue (kind must be in `mail.KINDS`); send is `mail.py:733 send_now`; the only limit seen is the claim resend cooldown, `claim.py:145` `RESEND_COOLDOWN_SECONDS = 60` (no "one mail per N minutes" for hosts found)
- `claim.py:854 sweep_reminders` | enqueues kind `reminder_guest`, key `reminder_guest:<reservation>:<date>` (`claim.py` ~917-921); template name not read
- `config.py:365` `DOOR_CODES_LIVE = os.environ.get("UBYHOST_DOOR_CODES_LIVE", "0") in ("1","true","yes")` | one feature flag example (read in `door_codes.py:117`)

## Needs a code change

- `G:1710-1730` | `/party` with mail off has no claim or lead check at all (any link+PIN holder can set the count) | H2a
- `G:2335-2338` | `/save` with a non-owned `guest_id` silently becomes a new person instead of 403 | H2b
- `G:2325-2327`, `G:1244` | `_require_claim_session` is skipped when mail is off; "lead" is a device cookie, not a role; `/scan` has no owned rule | H2b
- `G:2662` | `guest_form_saved` is one event for new and edit, no field names, no guest position; no audit for photo replace | H3 (needs H2b to add the row)
- `claim.py:363-366` | `_declared_count` is a count copy not in the plan's list | H1
- `go/internal/calendar/progress.go:88` | third Go count copy (plan names two) | H1
- `templates/guest/claim.html:36`, `assigned.html:33` | count prefill copies use a different order of precedence | H1
- `headcount.py:61` | a direct-booking or webhook stay has override = booked guests, so the lead can never lower it | H1 (owner call)
- `door_codes.py:179,436` | `checkin_hour` NULL raises TypeError if reached without the `:113` guard | H4 (fallback hour)
- `demo.py:307-526` | demo seeds write `declared_guests` directly (bypass, source demo only) | none
