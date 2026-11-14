# Go full move: routes still without a Go handler

Status 2026-11-13, main at `930c1cea`. Companion to [go-full-move](go-full-move.md) section 7. Python has 341 routes in `App/app/routes/*.py` and `App/app/main.py`; Go has a handler for 97, so 244 are missing.

## 1. Method and blind spots

- Python side: an AST script read every `@router.<method>("...")` and `@app.<method>(...)` in `App/app/routes/*.py` and `main.py`, resolved `PAGE`-style constants and f-strings, and added the 6 `/settings/<group>` routes that `admin.py` adds in a loop (no `APIRouter(prefix=...)` is used). Run by code.
- Go side: a throwaway test in a temporary git worktree built the real mux with `newMux` and asked `mux.Handler(request)` which pattern serves each Python route (parameters replaced by `1`). Method-aware; a route counts as missing when only the `/` catch-all answers. Run by code, nothing in the repo changed.
- Blind spots: "has a handler" means a pattern is registered, not that the page is complete or matches Python. Registration that depends on env vars was seen with the test environment only. A Go wildcard such as `GET /p/{slug}/{file}` counts as a hit for every filename it would catch. The `UBYHOST_GO_PATHS` Caddy prefixes were not read.

## 2. Missing routes per thread

### 2a. First wave (all merged by PR #1003)

The `admin.py` mapping uses the section-7 prefixes. `GET /settings/<group>` is one loop in Python (6 routes: account, security, phone, data, technical, help); `admin.py` has 67 decorated routes plus those 6. Stays routes include `/reservations/{id}/guests*` (guest create), and the filing send handlers `POST /reservations/{id}/submit` and `POST /reservations/submit-ready`.

| Thread | Python file | Total | With Go | Missing: `METHOD /path` (Python function) |
|---|---|---|---|---|
| Public legal pages | `guest_guide_view.py` | 4 | 0 | `GET /l/{token}/{reservation_id}/guide` (stay_guide); `GET /l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}` (stay_guide_photo); `GET /g/{token}` (qr_guide); `GET /g/{token}/photos/{item_id}/{photo_id}` (qr_guide_photo) |
| Public legal pages | `legal.py` | 8 | 5 | `GET /jak-to-funguje` (product_details); `GET /cenik` (pricing); `GET /pruvodce/{slug}` (public_guide) |
| Public legal pages | `mail_unsubscribe.py` | 2 | 0 | `GET /mail/unsubscribe/{token}` (mail_unsubscribe_form); `POST /mail/unsubscribe/{token}` (mail_unsubscribe_submit) |
| Login and accounts | `admin_accounts.py` | 33 | 15 | `GET /login` (login_form); `POST /login` (login_submit); `GET /login/link` (login_link_form); `POST /login/link` (login_link_submit); `POST /login/2fa` (two_factor_login); `GET /account/accept` (account_accept_form); `POST /account/accept` (account_accept_submit); `GET /account/2fa/setup` (two_factor_setup_form); `POST /account/2fa/setup` (two_factor_setup_submit); `POST /account/email` (account_email_request); `GET /account/email/confirm` (account_email_confirm_form); `POST /account/email/confirm` (account_email_confirm_submit); `POST /admin/users` (user_create); `POST /admin/users/{user_id}/invite` (user_invite); `POST /admin/users/{user_id}/email` (user_email_set); `GET /admin/operations` (operations_admin); `POST /admin/users/{user_id}/export` (user_workspace_export); `POST /admin/users/{user_id}/schedule-deletion` (user_schedule_deletion) |
| Login and accounts | `passkeys.py` | 7 | 1 | `POST /account/passkeys/options` (passkey_register_options); `POST /account/passkeys` (passkey_register); `POST /account/passkeys/{passkey_id}/rename` (passkey_rename); `POST /account/passkeys/{passkey_id}/delete` (passkey_delete); `POST /login/passkey/options` (passkey_login_options); `POST /login/passkey` (passkey_login) |
| Login and accounts | `signup.py` | 7 | 3 | `GET /signup` (signup_form); `POST /signup` (signup_submit); `GET /signup/verify` (signup_verify_form); `POST /signup/verify` (signup_verify_submit) |
| Onboarding pages | `onboarding.py` | 7 | 4 | `POST /demo` (load_demo); `POST /demo/reset` (reset_demo); `GET /onboarding` (onboarding_view) |
| Onboarding pages | `onboarding_wizard.py` | 3 | 0 | `GET /apartments/{apartment_id}/setup` (setup_entry); `GET /apartments/{apartment_id}/setup/{step}` (setup_step); `POST /apartments/{apartment_id}/setup` (setup_action) |
| Property settings pages (`admin.py`) | `admin.py` | 41 | 12 | `GET /smart-locks` (smart_locks_page); `POST /smart-locks/setup` (smart_locks_setup); `POST /smart-locks/refresh` (smart_locks_refresh); `POST /smart-locks/remove` (smart_locks_remove); `POST /entities/{entity_id}/invoice` (entity_invoice_details); `POST /entities` (create_entity); `POST /entities/{entity_id}` (update_entity); `GET /apartments/ruian-suggest` (apartments_ruian_suggest); `GET /apartments/new` (apartment_new); `POST /apartments` (apartment_create); `GET /apartments/{apartment_id}` (apartment_detail); `POST /apartments/{apartment_id}/door-codes` (apartment_door_codes); `POST /apartments/{apartment_id}` (apartment_update); `POST /apartments/{apartment_id}/automation-timing` (automation_timing_save); `POST /apartments/{apartment_id}/feeds` (add_feed); `POST /sync` (sync_now); `POST /apartments/{apartment_id}/test-connection` (test_connection); `POST /apartments/{apartment_id}/police-letter` (police_letter_read); `POST /apartments/{apartment_id}/refresh-codelists` (refresh_codelists); `GET /housebook` (housebook_view); `POST /alerts/{alert_id}/dismiss` (dismiss_alert); `GET /menu` (menu_view); `GET /settings` (settings_view); `GET /settings/account` (_settings_group_view); `GET /settings/security` (_settings_group_view); `GET /settings/phone` (_settings_group_view); `GET /settings/data` (_settings_group_view); `GET /settings/technical` (_settings_group_view); `GET /settings/help` (_settings_group_view) |
| Cleaning pages | `cleaning.py` | 16 | 5 | `GET /cleaning` (index); `GET /cleaning/new` (new_event); `POST /cleaning/events` (create_event); `GET /cleaning/events/{event_id}/edit` (edit_event); `POST /cleaning/events/{event_id}` (update_event); `GET /cleaning/properties` (choose_property); `GET /cleaning/properties/{property_id}` (property_settings); `POST /cleaning/properties/{property_id}` (save_property); `POST /cleaning/properties/{property_id}/code/{action}` (code_action); `GET /cleaning/shares` (share_settings); `POST /cleaning/shares` (create_share) |
| Data exports | `exports.py` | 13 | 8 | `GET /guests/{guest_id}/form.pdf` (guest_form_pdf); `GET /housebook/pdfs.zip` (housebook_pdfs_download); `POST /settings/workspace-export` (settings_workspace_export); `GET /settings/archived` (settings_archived_view); `POST /settings/purge-expired` (purge_expired_records) |
| Stay fee pages | `stay_fees.py` | 16 | 8 | `POST /stay-fees/{apartment_id}/guest-pay-preview` (guest_pay_preview); `GET /stay-fees` (stay_fees_list); `GET /stay-fees/pdfs.zip` (stay_fee_pdfs_zip); `GET /stay-fees/{apartment_id}` (stay_fee_detail); `GET /stay-fees/{apartment_id}/pdf` (stay_fee_pdf_download); `POST /stay-fees/{apartment_id}/adjustment` (stay_fee_adjustment_add); `POST /stay-fees/confirm-ready` (stay_fee_confirm_ready); `POST /stay-fees/{apartment_id}/finalize` (stay_fee_finalize) |
| Subscription billing pages | `admin_billing.py` | 7 | 0 | `GET /admin/fakturace` (billing_admin_page); `POST /admin/fakturace/vypis` (billing_admin_statement); `POST /admin/fakturace/{invoice_id}/zaplaceno` (billing_admin_mark_paid); `POST /admin/fakturace/{invoice_id}/storno` (billing_admin_storno); `GET /admin/fakturace/{invoice_id}.pdf` (billing_admin_pdf); `GET /admin/fakturace/export-vse` (billing_admin_export_all); `GET /admin/fakturace/export` (billing_admin_export) |
| Subscription billing pages | `billing.py` | 6 | 0 | `GET /predplatne` (plan_page); `POST /predplatne` (plan_order); `POST /predplatne/zmena` (plan_change); `POST /predplatne/zrusit` (plan_cancel); `POST /predplatne/obnovit` (plan_resume); `GET /predplatne/faktury/{invoice_id}.pdf` (plan_invoice_pdf) |
| Payments and booking site | `payments.py` | 25 | 14 | `GET /apartments/{apartment_id}/page` (property_page_review); `POST /apartments/{apartment_id}/page` (property_page_save); `POST /apartments/{apartment_id}/page/photo-move` (property_page_photo_move); `POST /apartments/{apartment_id}/page/photo-delete` (property_page_photo_delete); `GET /booking-sites` (booking_sites); `GET /apartments/{apartment_id}/booking-site` (booking_site_setup); `POST /apartments/{apartment_id}/booking-site` (booking_site_save); `POST /apartments/{apartment_id}/booking-site/pay` (booking_site_pay); `POST /apartments/{apartment_id}/booking-site/confirm` (booking_site_confirm); `POST /apartments/{apartment_id}/booking-site/decline` (booking_site_decline); `POST /apartments/{apartment_id}/booking-site/cancel` (booking_site_cancel) |
| Payments and booking site | `property_page.py` | 12 | 4 | `GET /terms/booking` (booking_terms_page); `GET /p/{slug}` (property_page_view); `POST /p/{slug}/book` (property_page_book); `POST /p/{slug}/checkout` (property_page_checkout); `GET /p/{slug}/b/{booking_id}/{token}/invoice.pdf` (booking_invoice_pdf); `GET /p/{slug}/b/{booking_id}/{token}/correction.pdf` (booking_correction_pdf); `GET /p/{slug}/b/{booking_id}/{token}` (booking_manage_page); `POST /p/{slug}/b/{booking_id}/{token}/cancel` (booking_manage_cancel) |
| Payments and booking site | `stripe_connect.py` | 4 | 4 | none |
| Customer admin pages | `admin_customers.py` | 10 | 3 | `GET /admin` (admin_home); `POST /admin/customers/{user_id}/sleva` (customer_discount); `POST /admin/customers/{user_id}/plan` (customer_plan); `POST /admin/customers/{user_id}/priradit` (customer_assign_plan); `POST /admin/customers/{user_id}/prodlouzit` (customer_extend_trial); `POST /admin/customers/{user_id}/overit-znovu` (customer_resend_verification); `POST /admin/customers/{user_id}/stav` (customer_status) |
| Privacy request pages | `privacy_requests.py` | 3 | 2 | `GET /privacy-requests` (privacy_requests_list) |

### 2b. Threads that wait for a dependency (not started)

| Thread | Python file | Total | With Go | Missing: `METHOD /path` (Python function) |
|---|---|---|---|---|
| Invoice pages | `invoices.py` | 10 | 0 | `GET /invoices` (invoices_list); `GET /invoices/new` (invoice_new); `POST /invoices/preview` (invoice_preview); `POST /invoices` (invoice_issue); `GET /invoices/{invoice_id}.pdf` (invoice_pdf_download); `GET /invoices/{invoice_id:int}` (invoice_detail); `POST /invoices/{invoice_id}/paid` (invoice_mark_paid); `POST /invoices/{invoice_id}/send` (invoice_send); `POST /invoices/{invoice_id}/cancel` (invoice_cancel); `GET /invoice/d/{token}` (invoice_download) |
| AI assistant pages | `guest_guide.py` | 20 | 0 | `GET /apartments/{apartment_id}/guide` (guide_index); `POST /apartments/{apartment_id}/guide/cards` (guide_add); `GET /apartments/{apartment_id}/leon` (leon_page); `POST /apartments/{apartment_id}/leon` (leon_save); `POST /apartments/{apartment_id}/guide/import` (guide_import); `GET /apartments/{apartment_id}/guide/qr` (guide_qr); `GET /apartments/{apartment_id}/guide/qr.png` (guide_qr_png); `POST /apartments/{apartment_id}/guide/qr/rotate` (guide_qr_rotate); `GET /apartments/{apartment_id}/guide/quick` (guide_quick); `GET /apartments/{apartment_id}/guide/quick/done` (guide_quick_done); `GET /apartments/{apartment_id}/guide/quick/{step}` (guide_quick_step); `POST /apartments/{apartment_id}/guide/quick/{step}` (guide_quick_save); `GET /apartments/{apartment_id}/guide/{item_id}` (guide_card); `POST /apartments/{apartment_id}/guide/{item_id}` (guide_card_save); `POST /apartments/{apartment_id}/guide/{item_id}/discard` (guide_card_discard); `POST /apartments/{apartment_id}/guide/{item_id}/skip` (guide_card_skip); `POST /apartments/{apartment_id}/guide/{item_id}/delete` (guide_card_delete); `POST /apartments/{apartment_id}/guide/{item_id}/photos` (guide_photo_add); `GET /apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}` (guide_photo_file); `POST /apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}/delete` (guide_photo_delete) |
| AI assistant pages | `havel.py` | 4 | 0 | `GET /havel` (havel_page); `POST /havel` (havel_send); `POST /havel/support` (havel_support); `POST /havel/not-helped` (havel_not_helped) |
| AI assistant pages | `leon_setup.py` | 4 | 0 | `GET /apartments/{apartment_id}/leon/setup` (setup_entry); `GET /apartments/{apartment_id}/leon/setup/{step}` (setup_step_page); `POST /apartments/{apartment_id}/leon/setup` (setup_save); `POST /apartments/{apartment_id}/leon/setup/try` (setup_try) |
| Stays and submissions pages (`admin.py`) | `admin.py` | 20 | 0 | `GET /reservations` (reservations_list); `POST /reservations` (reservation_create); `POST /reservations/submit-ready` (reservations_submit_ready); `GET /reservations/{reservation_id}` (reservation_detail); `POST /reservations/{reservation_id}` (reservation_update); `POST /reservations/{reservation_id}/remove-empty-slot` (reservation_remove_empty_slot); `POST /reservations/{reservation_id}/quick-edit` (reservation_quick_edit); `POST /reservations/{reservation_id}/delete-demo` (reservation_delete_demo); `POST /reservations/{reservation_id}/archive` (reservation_archive); `POST /reservations/{reservation_id}/unarchive` (reservation_unarchive); `POST /reservations/{reservation_id}/reopen-guest` (reservation_reopen_guest); `POST /reservations/{reservation_id}/resend-claim` (reservation_resend_claim); `POST /reservations/{reservation_id}/release-claim` (reservation_release_claim); `POST /reservations/{reservation_id}/filed-by-hand` (reservation_filed_by_hand); `POST /reservations/{reservation_id}/filed-by-hand/undo` (reservation_filed_by_hand_undo); `POST /reservations/{reservation_id}/submit` (reservation_submit); `GET /reservations/{reservation_id}/guests/new` (guest_new); `POST /reservations/{reservation_id}/guests` (guest_create); `GET /submissions` (submissions_list); `GET /submissions/{submission_id}` (submission_detail) |
| Host guest editing (`admin.py`) | `admin.py` | 11 | 0 | `GET /guests/{guest_id}` (guest_edit); `POST /guests/{guest_id}` (guest_update); `POST /guests/{guest_id}/restrict` (guest_restrict); `POST /guests/{guest_id}/unrestrict` (guest_unrestrict); `POST /guests/{guest_id}/verify-identity` (guest_verify_identity); `GET /guests/{guest_id}/passport-photo` (guest_passport_photo); `POST /guests/{guest_id}/reveal-identity` (guest_reveal_identity); `POST /guests/{guest_id}/archive` (guest_archive); `POST /guests/{guest_id}/unarchive` (guest_unarchive); `POST /guests/{guest_id}/delete` (guest_delete); `POST /guests/{guest_id}/resend` (guest_resend) |
| Guest registration pages | `guest.py` | 19 | 0 | `POST /l/{token}/pin` (verify_pin); `GET /l/{token}/ruian-suggest` (ruian_suggest); `GET /l/{token}/privacy` (privacy_notice); `GET /l/{token}` (pick_stay); `GET /l/{token}/demo/{reservation_id}` (demo_pin_preview); `GET /l/{token}/{reservation_id}` (stay_overview); `GET /l/{token}/{reservation_id}/claim` (claim_landing); `POST /l/{token}/{reservation_id}/claim/confirm` (claim_confirm); `POST /l/{token}/{reservation_id}/party` (set_party_size); `POST /l/{token}/{reservation_id}/count` (lead_change_count); `POST /l/{token}/{reservation_id}/another` (add_another_person); `GET /l/{token}/{reservation_id}/new` (guest_form_new); `GET /l/{token}/{reservation_id}/edit/{guest_id}` (guest_form_edit); `GET /l/{token}/{reservation_id}/remove/{guest_id}` (guest_remove_confirm); `POST /l/{token}/{reservation_id}/remove/{guest_id}` (guest_remove); `POST /l/{token}/{reservation_id}/relang` (guest_form_relang); `POST /l/{token}/{reservation_id}/save` (guest_form_save); `POST /l/{token}/{reservation_id}/draft` (guest_form_draft); `POST /l/{token}/{reservation_id}/scan` (guest_document_scan) |
| Guest registration pages | `guest_leon.py` | 4 | 0 | `GET /l/{token}/{reservation_id}/guide/leon` (stay_leon_history); `POST /l/{token}/{reservation_id}/guide/leon` (stay_leon); `GET /g/{token}/leon` (qr_leon_history); `POST /g/{token}/leon` (qr_leon) |
| Guest registration pages | `guest_questions.py` | 5 | 0 | `GET /apartments/{apartment_id}/guide/questions` (questions_index); `GET /apartments/{apartment_id}/guide/questions/{question_id}` (question_page); `POST /apartments/{apartment_id}/guide/questions/{question_id}` (question_answer); `POST /apartments/{apartment_id}/guide/questions/{question_id}/dismiss` (question_dismiss); `POST /apartments/{apartment_id}/guide/questions/{question_id}/card` (question_card) |
| No thread (`admin.py`) | `admin.py` | 1 | 0 | `GET /` (dashboard) |
| No thread (other files) | `api.py` | 1 | 1 | none |
| No thread (other files) | `dashboard_calendar.py` | 1 | 1 | none |
| No thread (other files) | `dev_ui.py` | 1 | 0 | `GET /dev/ui` (dev_ui) |
| No thread (other files) | `main.py` | 11 | 2 | `GET /sample-airbnb.ics` (sample_airbnb_calendar); `GET /robots.txt` (robots); `GET /.well-known/tdmrep.json` (tdmrep); `GET /manifest.webmanifest` (web_manifest); `GET /sw.js` (service_worker); `GET /offline` (offline_page); `GET /sitemap.xml` (sitemap); `POST /language` (set_language); `GET /favicon.ico` (favicon) |
| No thread (other files) | `push.py` | 5 | 5 | none |

## 3. Threads merged but incomplete

None of these can be switched on as a whole by path prefix yet (missing / total).

| Thread | Missing | Note |
|---|---|---|
| Login and accounts | 28 / 47 | `/login` (GET and POST), `/signup`, login link, 2FA, account accept, email change, user create and invite, passkeys (6 of 7) still Python |
| Property settings pages | 29 / 41 | only the list, guide, archive and regenerate routes exist; `/apartments/{id}` detail, `/apartments/new`, `/settings*`, `/menu`, `/housebook`, `/smart-locks` missing |
| Payments and booking site | 19 / 41 | `/p/{slug}`, `/p/{slug}/book`, `/p/{slug}/checkout`, booking manage and PDFs missing; `stripe_connect` is complete (4 / 4) |
| Cleaning pages | 11 / 16 | |
| Subscription billing pages | 13 / 13 | package `go/internal/web/billing` exists, but no route is registered in any `register_web_*.go` |
| Public legal pages | 9 / 14 | `guest_guide_view` (4) and `mail_unsubscribe` (2) not registered at all |
| Stay fee pages | 8 / 16 | |
| Customer admin pages | 7 / 10 | |
| Onboarding pages | 6 / 10 | `onboarding_wizard` 0 / 3 |
| Data exports | 5 / 13 | |
| Privacy request pages | 1 / 3 | only `GET /privacy-requests` missing |

Not started (as expected): invoices 10, AI pages 28, stays and submissions 20, host guest editing 11, guest registration 28.

## 4. Path collisions

Caddy routes by path only. Each path below is served by Go for some methods and by Python for the rest, so moving it to Go breaks the missing method (checked by probing every method on every Python path).

| Path | Python methods | Go serves | Fails after switch |
|---|---|---|---|
| `/entities` | GET, POST | GET | `POST /entities` (create_entity). Still true from brief 1412 |
| `/apartments` | GET, POST | GET | `POST /apartments` (apartment_create). Still true |
| `/admin/users` | GET, POST | GET | POST (admin_accounts) |
| `/login/2fa` | GET, POST | GET | POST (login 2FA submit) |
| `/privacy-requests` | GET, POST | POST | `GET /privacy-requests` (list page) |
| `/p/{slug}/book` | POST | none (GET falls into Go `GET /p/{slug}/{file}`) | `POST` book |
| `/p/{slug}/checkout` | POST | none (same wildcard) | `POST` checkout |

Also: Go `GET /p/{slug}/{file}` is a wildcard under `/p/{slug}/`, so a prefix switch of `/p/*` sends `GET /p/{slug}` and the manage and PDF pages to Go, which has no handler for them (not verified what the catch-all answers).

## 5. Job kinds

Python `JOB_KINDS` in `App/app/scheduler.py` (15) against `registerJob` and the lane files in `go/cmd/ubyhost-web/` (register_jobs.go, register_filing.go, register_job_*.go). `go/internal/jobs/queue.go` holds the queue and alert names only, no handler map.

| Kind | Go handler | Where |
|---|---|---|
| ical | yes | register_jobs.go |
| submit | yes | register_filing.go (UbyPort sweep plus payments sweep); filing F1/F2 sign-off is a separate decision |
| deadlines | yes (Go only; Python entry is a stub) | register_jobs.go |
| mail | no | only a name in `queue.go`; mail job thread has no `register_job_mail.go` |
| photo_sweep | yes | register_job_photo_sweep.go |
| meta_capi | yes | register_jobs.go |
| retention | yes | register_job_retention.go |
| stay_fee_mail | yes | register_job_stay_fee_mail.go |
| stripe_sweep | yes | register_jobs.go |
| billing | yes | register_job_billing.go |
| billing_snapshot | yes | register_jobs.go |
| door_codes | no | only a name in `queue.go`; not in any section-7 thread (also runs cleaning events and cleaning codes) |
| posthog | yes | register_jobs.go |
| push | yes | register_jobs.go |
| guide_import | yes | register_job_guide_import.go |

13 of 15 have a Go handler; missing: `mail`, `door_codes`. Section 7 has no thread that owns `door_codes`.
