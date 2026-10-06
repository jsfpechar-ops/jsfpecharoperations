# WP27: Privacy first (data minimisation audit and brand)

Commit `dfc30c8` on branch `wp27`, based on `golive` (ae9a430). Patch: `round3/WP27-privacy-first.patch`. Standalone, not stacked on another round-3 WP.

## Summary

Part 1 audits every table, cookie, storage key, log field and outbound request (below). The code at this commit is already lean: the main personal data is guest-book and stay-fee data required by law, and the extra fields (claim e-mail, phone fragment, submitter IP, passport photos, UbyPort XML) already have purge steps. One real gap was fixed: the house book wrote a localStorage key (`ubyhost_housebook_legal_v1`) that was missing from the published cookie and storage table, and the inventory test did not scan templates. Nothing else was removed. Every other "not needed" item would need a schema migration or changes the evidence the host relies on, so those are listed as recommendations.

Part 2 adds the "Privacy first" principle to AGENTS.md and docs/DESIGN.md, a "Privacy first" block (4 points, EN and CS, link to /privacy) on the landing, product and pricing pages, one line on the public privacy page and in the guest footer, and a test that crawls host, guest and public pages and fails if any cookie other than the documented strictly necessary set is set.

## Files changed

- `AGENTS.md`: new "Privacy first" section with the agent rules.
- `docs/DESIGN.md`: new "Privacy first" section (rules plus "how we say it"), and the locked public-site section now names the approved block.
- `App/app/cookie_inventory.py`: row for `ubyhost_housebook_legal_v1`; `STRICTLY_NECESSARY_COOKIES` (first-party cookie rows).
- `App/app/landing_i18n.py`: `privacy_first.*` strings, EN and CS.
- `App/app/i18n.py`: `privacy_first_line` for the guest footer, EN and CS.
- `App/app/templates/_privacy_first.html`: new partial, reuses `landing-section benefits` and `benefit-list`; no CSS, no images.
- `App/app/templates/landing.html`, `pricing.html`, `product.html`: include the partial before the final call to action.
- `App/app/templates/privacy.html`: privacy-first line under the page header.
- `App/app/templates/guest/base.html`: privacy-first line in the guest footer (`g-foot`). No CSS or JS touched, so no `?v=` bump.
- `App/tests/test_cookie_inventory.py`: storage-key scan now covers templates too.
- `App/tests/test_privacy_first.py`: new.

## Tests added

`tests/test_privacy_first.py`:
- `test_a_full_crawl_sets_exactly_the_strictly_necessary_cookies`: GETs every parameter-free GET route (43, found by walking the router) plus both public guides in EN and CS, anonymously, as a host and as a platform admin (sign-in with "remember me", language switch, logout), plus host reservation and apartment pages; then a guest flow with the PIN gate on (picker, PIN, stay page, claim, form save, guest privacy page). Asserts the set of Set-Cookie names equals `STRICTLY_NECESSARY_COOKIES`, with a message naming unexpected and unreached names. Checked by mutation: adding a `_ga` cookie to `remember_language` makes it fail with "Unexpected: ['_ga']".
- `test_the_strictly_necessary_set_is_the_first_party_cookie_inventory`: pins the 7 names.
- `test_the_privacy_first_section_is_on_the_marketing_pages`: title, 4 points and /privacy link on /, /cenik, /jak-to-funguje in EN and CS.
- `test_the_privacy_first_line_is_on_the_privacy_and_guest_pages`: public /privacy, a guest stay page and the guest privacy notice, EN and CS.
- `test_the_claims_never_say_no_cookies_in_absolute_terms`: the new copy never says "no cookies", "žádné cookies" or "bez cookies".

`tests/test_cookie_inventory.py::test_every_local_storage_key_is_declared` now also scans `templates/**/*.html` and asserts it found the house book key.

## Test commands and results

All from `/tmp/wp/wp27/App` with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu /tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider`:
- `tests/test_privacy_first.py tests/test_cookie_inventory.py`: 10 passed.
- Related copy, landing, legal, i18n, Umami guard (18 files): 201 passed.
- `UBYHOST_REQUIRE_BROWSER=1 ... tests/test_guest_browser_e2e.py -rs`: 4 passed, 0 skipped.
- `UBYHOST_REQUIRE_BROWSER=1 ... tests/test_host_geometry.py`: 2 passed.
- Full suite in chunks: `test_[a-f]*` (without browser e2e) 676 passed, 2 skipped; `test_[g-h]*` (without browser e2e) 365 passed; `test_[i-q]*` 679 passed; `test_[r-s]*` 434 passed, 1 failed; `test_[t-z]*` 219 passed.
- The one failure, `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`, is order-dependent and already on `golive`: it fails the same way in the `[r-s]` chunk with this WP stashed, and passes alone (1 passed).
- Ruff (`E9,F63,F7,F82,F401,F841`): all checks passed.
- Screenshots: `round3/shots/WP27-*.png` (landing EN, pricing CS, desktop 1280 and mobile 375, privacy page, and the block in context on pricing and product). The block lines up with the sections around it.

## Part 1: audit

Retention sources: `retention.py` STEPS (dry-run until `UBYHOST_RETENTION_AUTOPURGE=1`), `passport_photos.purge_stale` and `reporting.purge_submission_payloads` (12-hourly photo sweep, always on), `mail.purge_old` (mail job, always on), `housebook.purge_orphan_submissions`.

Verdict codes: **LAW** = required by law (§ 102 zákon 326/1999 Sb. guest-book fields, § 3g zákon 565/1990 Sb. stay-fee fields, § 35 zákon 235/2004 Sb. invoices); **FEAT** = needed for a feature; **NO** = not needed.

### Tables and personal-data columns

| Table / columns | Purpose | Basis / feature | Retention | Verdict |
|---|---|---|---|---|
| guest: surname, first_name, birth_date, nationality, doc_type, doc_number_enc, visa_number_enc, res_street, res_city, res_country, purpose, stay_from, stay_to | Guest book, UbyPort report, stay-fee book | § 102 326/1999; § 3g(2) 565/1990 (name, address, document type and number, stay dates) | 6 years after stay end, 31 Jan rule (`guests` step) | LAW |
| guest.note | Parent's document number for a child on a parent's passport | UbyPort record field | With the guest row | LAW (UbyPort) |
| guest.fee_host_decision, fee_host_reason_enc, fee_host_reason_reference | Stay-fee exemption and its reason | § 3g(2) 565/1990 (reason for exemption) | With the guest row | LAW |
| guest.signature_png_enc, signed_at | Guest's signature on the registration form | Signed form replacing the book (§ 101(4) 326/1999); host's choice | With the guest row | FEAT (legal form) |
| guest.notice_version, notice_lang, notice_ack_at | Proof the guest saw the privacy notice | Art. 13 GDPR evidence | With the guest row | FEAT |
| guest.filled_at, entered_by | Who entered the record and when | Audit of the book | With the guest row | FEAT |
| guest.filled_ip | Submitter IP for disputes | Owner decision G-D6, counsel to confirm | Nulled 90 days after stay end (`submitter_ips`) | FEAT, keep under review |
| guest.passport_photo_at (+ file on disk) | Optional document photo for host check | Property setting, off by default | Deleted on verify, 7 days after check-in, 30 days after upload at most (photo sweep) | FEAT |
| guest.identity_verified_at/_by, restricted_at/_reason, submit_*, submission_id, receipt_submission_id, manual_* , archived_at, is_lead, last_errors | Workflow state | Reporting workflow | With the guest row | FEAT (no extra personal data) |
| guest.doc_number, visa_number, signature_png, fee_host_reason (plaintext) | Legacy columns; writes go to the `_enc` twin and blank these (`db.ENCRYPTED_GUEST_COLUMNS`) | none | Always blank for new rows | NO, see recommendation 1 |
| reservation: date_from, date_to, source, uid, declared_guests, status | The stay | Core feature | Deleted with guests, or at 6 years if empty (`empty_reservations`) | FEAT |
| reservation.summary | Calendar title from iCal (can hold a guest name) | Shown to host to recognise the booking | With the reservation (6 years) | FEAT, see recommendation 3 |
| reservation.reservation_url | Link back to the booking platform | Host convenience | With the reservation | FEAT |
| reservation.guest_email, phone_last4 | Contact and claim matching | Claim link, reminders | Nulled 30 days after stay end (`reservation_contacts`) | FEAT |
| reservation.host_note | Host's own note | Host feature | With the reservation | FEAT |
| reservation_claim.email | Where the private link is sent | Claim link (required field on the guest claim form) | Nulled 30 days after stay end (`claim_emails`) | FEAT |
| reservation_claim.email_masked | Masked address shown on the assigned screen | Claim UI | Not nulled by `claim_emails` | FEAT, see recommendation 2 |
| reservation_claim.token_hash, lang, declared_guests, state fields | Claim mechanics | Feature | With the reservation | FEAT |
| submission: guest_ids, state, pseudo_stamp, receipt_pdf, error_pdf, errors | Proof of reporting | Host's evidence | Lives as long as the guests it proves | FEAT |
| submission.request_xml, response_xml | Raw UbyPort envelope (passport numbers) | Debugging | Blanked 90 days after settling (`purge_submission_payloads`) | FEAT, short-lived |
| stay_fee_filing: pdf_enc, csv_enc, payload_enc, totals | Sealed stay-fee period | § 3g 565/1990 | 6 years (`stay_fee_records`) | LAW |
| stay_fee_adjustment: people_count, nights, reason_enc | Manual stay-fee correction | § 3g 565/1990 | 6 years (`stay_fee_records`) | LAW |
| invoice, invoice_item: buyer_*, seller_*, pdf_blob | Invoices the host issues | § 35 235/2004 | 10 years from year end (`invoices`) | LAW |
| legal_entity: name, seat, ico, dic, contact_email, contact_phone, bank, signature_png_enc | Host's business identity on invoices, UbyPort and stay-fee reports | Feature, mostly business data | With the workspace (`workspaces`) | FEAT |
| apartment: address, uby_* (incl. uby_ws_password_enc), stay_fee_* , permalink_pin, notes, guest_message | Property and UbyPort credentials | Feature | With the workspace | FEAT |
| ical_feed.url | Secret calendar URL | Calendar sync | With the workspace | FEAT |
| user_account: username, display_name, password_hash, totp_secret_enc, recovery_codes_hash, last_login_at | Host sign-in | Contract, security | Until workspace deletion (`workspaces`) | FEAT, see recommendation 5 |
| legal_acceptance: ip, user_agent | Proof of acceptance of terms and DPA | Art. 7(1) GDPR evidence | Deleted 3 years after an inactive account's last login (`legal_acceptance`) | FEAT, see recommendation 4 |
| audit: actor, detail, ids | Security and access audit | Art. 32 GDPR | 3 years (`audit_rows`), except acceptance rows | FEAT |
| alert: message, detail, params | Host alerts | Feature | 365 days after resolved (`alerts`) | FEAT |
| rate_limit_event.key | Raw client IP (plus suffix) for login/PIN/claim throttling | Security | 24 hours (`rate_limit_events`) | FEAT |
| email_outbox: to_email, cc_email, subject, payload | Queued mail | Mail delivery | Deleted 14 days after sent/failed (`mail.purge_old`); with the workspace | FEAT |
| console_mail_log | Copy of mail in the console backend (dev/demo only) | Development | 14 days (`mail.purge_old`) | FEAT (non-production) |
| data_subject_request: subject ids, notes | GDPR request log | Art. 12 and 30 GDPR | Only with the workspace | FEAT, see recommendation 6 |
| security_incident | Breach register | Art. 33(5) GDPR | No purge step | FEAT, see recommendation 6 |
| codelist, settings, invoice_sequence, submission_claim | Reference data and locks | Feature | n/a | no personal data |

### Cookies (all first party, all strictly necessary)

| Name | Purpose | Lifetime | Flags |
|---|---|---|---|
| ubyhost_session | Sign-in session | 12 hours, 30 days with "remember me" | HttpOnly, SameSite=Strict |
| ubyhost_csrf | CSRF protection for forms | Matches session, up to 30 days | HttpOnly, SameSite=Strict |
| ubyhost_lang | Language the visitor chose (switcher or a `?lang=` link) | 180 days | SameSite=Lax |
| ubyhost_pin | Guest passed the property PIN | 7 days | HttpOnly, SameSite=Lax |
| ubyhost_claim | Guest's claimed stay on this device | 60 days | HttpOnly, SameSite=Lax |
| ubyhost_owned | Guest forms this device submitted (ids only, signed) | 60 days | HttpOnly, SameSite=Lax |
| ubyhost_guest_lang | Guest language | 60 days | SameSite=Lax |

Cloudflare edge cookies `__cf_bm` and `cf_clearance` (bot protection, set only by the edge when it challenges) are listed on the privacy page. Umami sets no cookie. The crawl test confirms the app sets exactly the 7 names above.

### localStorage (host app and public pages, never sent to the server)

`ubyhost-sidebar-collapsed`, `ubyhost-command-recents` (up to 8 recent palette item URLs), `ubyhost-saved-stay-views` (up to 5 saved list URLs and labels), `ubyhost_housebook_legal_v1` (new row, value "1"), `umami.disabled` (only after opt-out).

### Logs

uvicorn access log is off (`--no-access-log` in Dockerfile and render_start.sh). App log lines carry ids, counts, states and endpoints only (for example `ubyport_submission_rejected apartment_id=… submission_id=… state=…`); no names, e-mails, IPs or document numbers found. `run.sh` (local only) keeps uvicorn's default access log.

### Outbound requests

| Request | Code | Sends | Why |
|---|---|---|---|
| UbyPort SOAP | `ubyport/client.py` | Guest-book fields of foreign guests, host's UbyPort login | Statutory report (host's duty) |
| iCal feeds | `feed_fetch.py` | GET of the host's own calendar URL | Calendar sync |
| Amazon SES | `mail.py` (boto3) | Recipient address and mail content | Claim links, receipts, host notices |
| Cloudflare Turnstile siteverify | `turnstile.py` | Token, and the client IP | Bot check on sign-in and guest PIN/claim, production only when enabled |
| Heartbeat pings | `scheduler.py` | GET to the configured URL, no data | Monitoring, only if `UBYHOST_HEARTBEAT_*` set |
| Browser: Turnstile script | `login.html`, `guest/pin.html`, `guest/claim.html`, `guest/assigned.html` | Loaded from challenges.cloudflare.com | Only when a Turnstile site key is set |
| Browser: Umami | `_umami.html` | Page view, referrer, device class | Public marketing and legal pages only, when configured |

## Deviations from the spec and why

- **Footer line wording.** The owner's line "UbyHost collects only what Czech law requires and does not use tracking cookies" is not quite true: the guest claim form requires an e-mail address for the private link, and host accounts need sign-in data. Used instead: guest footer "UbyHost collects only what Czech law and your registration need, and does not use tracking cookies." / "UbyHost shromažďuje jen to, co vyžaduje český zákon a vaše registrace, a nepoužívá sledovací cookies."; privacy page "…what Czech law and the service itself need…" / "…co vyžaduje český zákon a samotná služba…".
- **No "data stored in the EU" point.** The Lightsail region is still unverified (04_legal_positions.md open item 2), and Cloudflare is a US company. The four points are: only the fields Czech law asks for (plus the e-mail for the private link); no tracking cookies; no ad or analytics scripts in the app or on guest pages (website statistics on public pages only); passport photos optional, deleted on verification or automatically 7 days after check-in. The photo sweep runs every 12 hours, so "7 days" can mean up to half a day later.
- **"No third-party scripts in the app or guest pages"** is stated with its one real exception: Cloudflare Turnstile on sign-in and guest PIN/claim pages when configured. Removing Turnstile is out of scope.
- **No automatic-deletion claim for guest records**: `retention.run` is dry-run until `UBYHOST_RETENTION_AUTOPURGE=1`. DESIGN.md says not to claim it until then.
- **Spec references § 102 for the guest-book fields**: kept. The retention rule is § 101(4), as 04_legal_positions.md says.
- The public site is "locked" in DESIGN.md. The block reuses the existing benefit list, and the task counts as the owner's go-ahead; DESIGN.md now names it as approved.

## What Cursor must verify or adapt when applying on the real main

- If another WP added guest languages to `i18n.py`, add `privacy_first_line` to each one (or let the fallback show English) and check the parity test.
- If another WP adds a cookie (for example a consent or ads cookie), `test_privacy_first.py` will fail on purpose. Only a strictly necessary cookie may be added to `cookie_inventory.py`. A consent-gated click id must be stored server-side, not in a cookie, or the "no tracking cookies" claim and the test must be revisited with the owner.
- The crawl uses `TestClient.event_hooks`; if the httpx/Starlette upgrade removes it, record the cookies with a small ASGI wrapper instead.
- `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown` fails in the `[r-s]` chunk on `golive` as well; this WP did not cause it.

## Manual steps for the owner

- Confirm the Lightsail region (eu-central-1) before any "data stored in the EU" claim is added.
- Decide when to turn on `UBYHOST_RETENTION_AUTOPURGE=1`. After that, a "guest records deleted after the legal 6 years" point can be added.

## Recommendations (not done, need a migration or a decision)

1. Drop the always-blank plaintext columns `guest.doc_number`, `visa_number`, `signature_png`, `fee_host_reason` after a one-off check that no row still holds a value (`SELECT COUNT(*) … WHERE doc_number IS NOT NULL AND doc_number <> ''`). SQLite needs a table rebuild, so do it as its own migration WP.
2. Null `reservation_claim.email_masked` in the `claim_emails` step together with `email` (one-line change, but it changes what an old assigned screen shows, so it needs a test and a decision).
3. Consider nulling or replacing `reservation.summary` once guests are registered: Booking.com and manual summaries can hold a guest name, which then lives 6 years next to the guest book that already has the name.
4. `legal_acceptance.user_agent` (300 chars) is weak evidence. Keeping only the version, time and method (IP optional) would be enough. Ask counsel.
5. Host account data has no "3 years after closure" anonymisation step yet (04_legal_positions.md section 4); only deletion via `deletion_due_at`.
6. `data_subject_request` and `security_incident` have no purge step. Add a retention line (for example 5 years after closure) in `retention.py`.
7. `ubyhost_guest_lang` is set on every guest page render, not only when the guest picks a language. Low risk (value "en" or "cs"), but setting it only on an explicit `?lang=` choice would match the host-side rule.
8. `ubyhost-saved-stay-views` stores list URLs, which can include a search term (possibly a guest name) in the host's browser. Consider stripping `q=` before saving.
