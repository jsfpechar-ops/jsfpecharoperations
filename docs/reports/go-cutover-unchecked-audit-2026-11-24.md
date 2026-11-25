# UbyHost Python-to-Go cutover audit 2067

24 November 2026 · `claude/nice-hawking-fw98ct` · `2fa369c575f0c00ebcb283ae9948197737ff50ff`

**Cutover decision: HOLD.** The checked branch has source-confirmed differences in filing, registration and handling of guest data. Evidence refers to the published commit in a separate checkout. The production settings and historic state counts came from the audit brief. Runtime claims below are limited to the cases actually run.

Verdicts refer to individual checks. **SAME** means the listed behavior matched in the stated scope. **DIFFERENT** means both paths exist with different behavior. **MISSING** means the checked Go path omits a Python behavior. **UNVERIFIED** identifies a check that lacks enough evidence. The previously passed pixel, DOM, route and job-existence gates were taken as background. Known 2065/2066 and headcount audit-row differences were excluded from new findings.

## Critical before deploy

| Verdict | Impact | Python | Go |
|---|---|---|---|
| MISSING | Guest form save can skip the email-claim session check that Python requires when mail is on. The PIN check remains. Go uses the claim gate on the form-rendering path. The separate save handler proceeds to writes without it. | `App/app/routes/guest.py:1242–1255,2371–2381` | `go/internal/web/guest/form_save.go:96–116,134–181,404–411`; `go/internal/web/guest/form_pages.go:835–859` |
| DIFFERENT | Host guest create/edit writes sensitive information into plaintext columns. A pre-existing encrypted value can also continue to take precedence over the newly saved value, including when filing. | `App/app/routes/admin.py:4680,4808–4815`; `App/app/db.py:2017–2027,2166–2182,2432–2444` | `go/internal/web/stays/guest_edit.go:243–280,628–635,665–709` |
| MISSING | Go records acceptance of the guest notice without enforcing the required acknowledgement on the server. | `App/app/routes/guest.py:2480–2481,2569–2575` | `go/internal/web/guest/form_save.go:134–156,211–219`; `go/internal/web/guest/templates/form_content.tmpl:372` |
| MISSING | Where an apartment requires a foreign passport photo, Go guest save omits required-photo validation and upload persistence. | `App/app/reporting.py:409–427`; `App/app/routes/guest.py:2483–2516,2709–2715` | `go/internal/web/guest/form_save.go:134–181,211–219` |
| MISSING | The under-15 signer relationship is not stored, linked after an adult signature, or cleared when the child's age is corrected. | `App/app/routes/guest.py:2475–2479,2590–2603,2717–2724` | `go/internal/web/guest/form_save.go:134–181,211–236` |
| DIFFERENT | A guest correcting a filing error does not reset the attempts. A corrected record blocked as a duplicate can stay blocked, because Go checks error wording without comparing the corrected police fields. | `App/app/routes/guest.py:2605–2619`; `App/app/reporting.py:1320–1351` | `go/internal/web/guest/form_save.go:226–236` |
| MISSING | The first guest form does not validate or save the declared party size when the stay lacks an expected count. Go also carries the originally read count into the reservation-locked admission check. | `App/app/routes/guest.py:2459–2463,2654–2672` | `go/internal/web/guest/form_save.go:112–156,298–314,404–411` |
| DIFFERENT | Removing a guest leaves the separate passport scan for the later orphan sweep and skips the immediate filing check. The removal audit row is attributed to the apartment ID instead of its owner. | `App/app/routes/guest.py:2258–2272` | `go/internal/web/guest/form_pages.go:362–370,942–946` |
| DIFFERENT | Guest save and host guest edit enqueue a general submission sweep. Python immediately checks and files the completed stay and can surface its filing outcome in the form flow. This is distinct from the completion hooks in 2065. | `App/app/reporting.py:1162–1197`; `App/app/routes/guest.py:2733–2765` | `go/internal/web/guest/form_save.go:586–591`; `go/internal/web/stays/guest_edit.go:721–731` |
| DIFFERENT | Claim and resend emails contain a bare link in both parts. Localized instructions and the host Reply-To are absent. Guest-triggered resend also uses the first-email kind and subject. The token is encrypted in the queue. | `App/app/claim.py:342–373` | `go/internal/web/guest/party.go:487`; `go/internal/web/stays/claim_seed.go:127–128,172,328–365`; `go/internal/web/stays/claim_ops.go:783–811` |
| MISSING | The save handler omits the guest-link reachback cutoff and completed-stay device check. It also excludes demo stays even for their signed-in host. | `App/app/routes/guest.py:804–849` | `go/internal/web/guest/form_save.go:397–419` |
| DIFFERENT (cutover guidance) | The branch says week-one autopurge should be off. In production, Go deletes when the existing autopurge flag is on even with the separate Go flag absent. This matches the Python steady state and conflicts with the week-one instruction and the Go flag's documentation. | `App/app/config.py:447–451`; `App/app/scheduler.py:483–497` | `go/internal/retention/retention.go:54–81`; `docs/context/status.md:5–6`; `docs/ENVIRONMENT.md:62–63` |

## Should fix

| Verdict | Impact | Python | Go |
|---|---|---|---|
| DIFFERENT | **Health check** reports the data volume as writable without checking it, so an unwritable photo or attachment volume can appear healthy. Both check the database. | `App/app/main.py:601–615` | `go/cmd/ubyhost-web/main.go:110–125` |
| MISSING | The monthly operator email at 80% of an AI budget is replaced by a process log. The spending limits remain enforced. | `App/app/ai.py:307–315`; `App/app/mail_notify.py:3057–3065` | `go/internal/anthropic/ai.go:329–351` |
| DIFFERENT | Python renders a branded guest 404 and a branded HTML 405 with the Allow header. Go's catch-all emits plain guest 404 and empty 405; explicit handler errors can follow other paths. | `App/app/main.py:261–274` | `go/cmd/ubyhost-web/main.go:128–144`; `go/internal/web/auth/authpage/errorpage.go:19–48` |

## New features

The brief excludes typed garage, gate and building-entry codes and a guide link in guest emails from the regression count. The checked branch already registers Go-only host access-code settings and writes encrypted typed codes (`go/internal/web/ai/guide_access.go:25–32,335–337`). Go also contains mail marker handling for extra codes (`go/internal/mail/outbox_markers.go:199`). Guest delivery end to end is unverified. The guest-mail guide link remains an excluded feature per the brief.

## 1. POST and form behavior

Appendix A maps all 188 Python POST routes to Go source. It found zero Python PUT, DELETE or PATCH routes in scope. Most routes have an UNVERIFIED behavior verdict. See the critical table for verified guest and host guest write paths. **SAME**, scoped samples: normal stay edit matches editable fields, count range, flash and top-level follow-ups (`App/app/routes/admin.py:4176–4219`; `go/internal/web/staydetail/post.go:46–143`). The door-code toggle matches owner, lock and time checks, the checked writes and audit (`App/app/routes/admin.py:2500–2532`; `go/internal/web/properties/apartment_door_codes.go:44–129`). Also, the privacy-request update checks the workspace before writing (`App/app/routes/privacy_requests.py:72–94`; `go/internal/web/privacy/handler.go:220–265`). Recent fixes and known 2065/2066 were not counted again.

## 2. UbyPort filing

Immediate filing trigger differences are in the critical table.

| Verdict | Checked filing behavior | Python | Go |
|---|---|---|---|
| SAME | **Byte-for-byte synthetic XML test.** Python regenerated the six existing oracle files without changing their bytes. The existing Go test passed all six cases covering an EU guest, non-EU visa, escaping, fallback dates, a multi-guest batch and addressing headers. Go compiled the unchanged request sources using a scratch module. | `App/scripts/ubyport_golden.py:27–43` | `go/internal/ubyport/request_test.go:49–69` |
| SAME | **Historical states, source.** Transport retry reads the most recent 500 submissions per apartment, excluding authentication failures from the retry chain. Unknown outcomes are recognized and retried after 30 minutes, two hours, six hours and 12 hours with a five-attempt cap. Partial outcomes keep accepted guest states and receipt references. | `App/app/reporting.py:1992–2022,2220–2258,2277–2354` | `go/internal/ubyport/backoff.go:41–123`; `go/internal/ubyport/sweep.go:455–511,522–526,561–649`; `go/internal/ubyport/outcome.go:146`; `go/internal/ubyport/store.go:141–166` |
| SAME | **Deadline, source.** The third weekday counts the arrival day inclusively and ends at 23:59:59. The send gate uses the earliest active guest arrival or the reservation date. The six-hour deadline margin allows filing incomplete groups. | `App/app/deadlines.py:19–43`; `App/app/reporting.py:1205–1253,2861–2886` | `go/internal/deadlines/deadlines.go:44–74`; `go/internal/ubyport/collect.go:307–383` |
| SAME | **Receipt and failure writes, source.** Batch storage records guest IDs, error lists, receipt and error PDFs and encrypted XML. Police rejection or a partial response raises an alert and queues problem email and push. | `App/app/reporting.py:1784–1825,1992–2022,2083–2112` | `go/internal/ubyport/store.go:80–87,141–166`; `go/internal/ubyport/submit.go:166–192` |
| UNVERIFIED | **End to end.** Actual 30 transport-error, one partial and one unknown-outcome records were outside the offline audit. Full response classification and submit-state transitions, real delivery, fault injection and test coverage outside the XML builder were not verified. | `docs/OPERATIONS.md:74`; `App/app/reporting.py:1784–1825` | `go/internal/ubyport/outcome_test.go:34`; `go/internal/ubyport/sweep.go:452–649` |

## 3. Mail

Claim and resend body and Reply-To, and AI-budget notice differences are listed above. Appendix C inventories 38 registered mail kinds and lists the known goldens. **SAME — isolated Go content goldens passed** for completion, door codes and notices, fee updates, and both guest and host reminders. Other goldens remain **UNVERIFIED** because the full mail-package run stopped during offline dependency resolution.

## 4. Background jobs

**SAME**, scoped configuration check: Python and Go run retention daily and apply the supplied steady-state production autopurge setting (`App/app/scheduler.py:483–497`; `go/cmd/ubyhost-web/register_job_retention.go:18–35`; `go/internal/retention/retention.go:54–81`). Appendix C compares the 15 job schedules and their execution paths. Python checks for jobs left unclaimed past twice their interval and raises the job alert. Go shows missed schedules on Operations and alerts on terminal handler failures. The static Go worker search found no equivalent unclaimed-queue alert (`App/app/jobqueue.py:144–187,208–211`; `go/internal/jobs/queue.go:181–230`; `go/internal/web/customers/ops.go:136`).

## 5. Auth and security

- **SAME — sample of existing session rules.** The active-account lookup compares the session version and the host cookie keeps the corresponding sliding and absolute ages (`App/app/auth.py:29–43,311–334,620–650`; `go/internal/session/session.go:194–231`; `go/internal/session/issue.go:21–31,107–129,153–165`). This was a source comparison.
- **SAME — sampled owner filters.** Stay detail and update, guest edit and photo/identity lookup, invoice lookup, guest JSON export and submission downloads constrain the object to the current workspace. Privacy-request update checks the loaded row's workspace before mutating it. Go anchors are `go/internal/web/staydetail/load.go:28`, `go/internal/web/staydetail/post.go:153`, `go/internal/web/stays/guest_edit.go:214,249`, `go/internal/web/stays/guest_privacy.go:143`, `go/internal/web/invoices/store.go:359–362`, `go/internal/web/exports/guest_json.go:28`, `go/internal/web/exports/submissions.go:24–28`, and `go/internal/web/privacy/handler.go:246–254`. Python counterparts include `App/app/routes/admin.py:4069,4176,4696,4890`, `App/app/routes/invoices.py:884,903`, `App/app/routes/exports.py:117,222–253`, and `App/app/routes/privacy_requests.py:72–78`.
- **DIFFERENT — guest form claim.** See the critical table. Guest save checks token, PIN and rate limits before write. Other Go form handlers use a separate claim gate.
- **UNVERIFIED — exhaustive auth and ownership coverage.** Code entry points were found for login, signup, Passkeys, CSRF, Turnstile, guest PIN and admin actions (`go/internal/web/auth/login.go:219–221`, `signup_pages.go:214–261`, `passkeys.go:219–222,267–275,428–470` in the same package, and `go/internal/hostweb/gate.go:155–174`). Full runtime parity, every write's CSRF and no-JavaScript behavior, every owner filter and the admin route matrix are unverified. No finding of cross-workspace access is established by the sampled query checks.

## 6. Privacy

- **SAME — PostHog configuration and page grouping, source only.** Python's nine analytics templates are public marketing, guide and legal pages (`App/app/analytics.py:25–37`). The Go legal and public page renderers use the corresponding analytics component (`go/internal/web/public/render.go:16–21,66–74`; `go/internal/web/public/pages_render.go:14–24,40–55`; `go/internal/web/public/pages_data.go:97–105`). Python and both Go snippets declare cookieless, memory-only analytics and disable recording (`App/app/templates/_posthog.html:66–74`; `go/internal/web/public/templates/posthog.tmpl:62–70`; `go/internal/web/public/templates/pages/posthog.tmpl:62–70`).
- **DIFFERENT — personal data and deletion.** Host guest edit/create encryption and individual passport-scan cleanup differ as described above.
- **SAME — sampled data rights controls.** Request updates enforce workspace ownership in both languages. Workspace export uses a fresh-login gate and owner scope in each implementation (`App/app/routes/exports.py:417–444`; `go/internal/web/exports/workspace.go:400–430`). Monthly retention policy, holds, full workspace erasure and cleanup outcomes require a row-by-row comparison (`App/app/retention.py:339–430`; `go/internal/retention/workspace_delete.go:84–119`).
- **UNVERIFIED — privacy response gate.** All live response cookies, public pages without cookies, encrypted columns outside the reviewed paths, and workspace export/erasure on existing production-style data. Python test rules at `App/tests/test_privacy_first.py` were used as context. Live Go responses were not synthesized for the full matrix.

## 7. Downloads and feeds

**SAME — valid stored receipt and error PDFs, source.** The single receipt/error paths require login and workspace ownership, serve application/pdf with matching filename conventions and audit the export. A stay with one receipt returns the PDF. Multiple receipts yield a ZIP and consider both current and original submission references (`App/app/routes/exports.py:222–253,273–326`; `go/internal/web/exports/submissions.go:23–36,85–122,284–350`; `go/internal/web/exports/exports.go:254–264`).

**UNVERIFIED — seeded bytes/text and headers.** The side-by-side PDF/CSV/ZIP/ICS render and diff covering receipt, errors, invoices, forms, house book and stay fees was not completed. Authorization beyond the sampled controls and filenames or media type beyond the stored PDF paths remain unverified.

## 8. Integrations

| Verdict | Compared behavior | Python | Go |
|---|---|---|---|
| SAME | Source inspection confirms iCal platform and block recognition, synthetic identifiers and candidate processing for moved or cancelled stays. The parser has Python-derived fixtures. | `App/app/icalsync.py:81–90,219–228,237–264,303–369,647–722` | `go/internal/ical/parse.go:83–199,247–275`; `go/internal/ical/syncfeed.go:329–343,509–594` |
| SAME | Source has TTLock period creation, lookup/list, deletion and time operations in both implementations. | `App/app/ttlock.py:396,511,650–714` | `go/internal/ttlock/api.go:267,412,453,510–541` |
| SAME | Apify request builders and model feature/budget gate exist. Havel checks the test-list membership in its feature gate. | `App/app/guest_guide_import.py:310–359`; `App/app/ai.py:77–115,189–212` | `go/internal/guideimport/apify.go:73–132`; `go/internal/anthropic/ai.go:132–156,268–315`; `go/internal/web/ai/havel_store.go:53–68` |
| DIFFERENT | The AI 80% operator mail is missing from the Go budget warning path. | `App/app/ai.py:307–315` | `go/internal/anthropic/ai.go:329–351` |
| UNVERIFIED | End-to-end iCal dedupe on all four platforms, complete TTLock request payloads and callback coverage, Apify fallbacks, Leon/Havel/guide import prompt and request equivalence, and full owner test-list routing. | `App/app/icalsync.py:854`; `App/app/ttlock.py:396`; `App/app/guest_guide_import.py:333`; `App/app/ai.py:320` | `go/internal/ical/syncfeed.go`; `go/internal/ttlock/client.go:315`; `go/internal/guideimport/apify.go:90`; `go/internal/anthropic/ai.go:373` |

The SAME rows above cover the named source mechanisms. They do not extend to external calls, rate quotas, model prompts or confirmed delivery.

## 9. Languages

**SAME — catalog values.** For German, Spanish, French and Ukrainian, 355 keys per language matched the resolved Python catalogues exactly. All 13,187 shared host catalog entries checked across Czech, English and Vietnamese matched. See Appendix B. **UNVERIFIED** for rendered text, interpolation, literal strings outside the catalogs and screen layout.

## 10. Edge states

- **SAME — sampled status gates.** Removing a filed, restricted or actively claimed guest is stopped by corresponding conditions (`App/app/routes/guest.py:2250–2257`; `go/internal/web/guest/form_pages.go:349–360`). Both implement Prague-aware door times and deadline clocks in source (`App/app/door_codes.py:206–213`; `App/app/deadlines.py:47–52`; `go/internal/doorcodes/helpers.go:16,61–70`; `go/internal/deadlines/deadlines.go:17–36`).
- **UNVERIFIED — scenario coverage.** Past/cancelled/archived and post-filing stays beyond the listed guards, multi-apartment and multi-entity workflows, long and non-Latin input, empty states, list pagination, Prague midnight and both DST transitions were not exercised end to end.

## 11. Errors

**DIFFERENT**, source: branded 404/405 behavior and health reporting are in Should fix. Both frameworks contain HTML 500 rendering, but the Python exception handler catches unhandled errors and Go's wrapper handles returned 500 statuses (`App/app/main.py:293–306`; `go/internal/web/auth/authpage/errorpage.go:19–48`). **UNVERIFIED** for runtime 500/DB down, expired/revoked links end to end, and user-visible UbyPort, SES, or TTLock outage cases.

## 12. Deploy and runtime

- **Required cutover config.** The script requires `UBYHOST_SCHEDULER=go`. When active, Go startup requires all scheduled job kinds in both lists and rejects mismatched sets. The actual production lists are unverified. The mixed-stack ownership described in branch status still assigns mail and door codes to Python, so keeping those settings would fail the Go-only configuration checks (`deploy/lightsail/scripts/deploy.sh:15–25`; `go/cmd/ubyhost-web/job_config.go:24–72`; `go/internal/scheduler/scheduler.go:149–174`). The Go database URL is required and is passed by Compose (`go/cmd/ubyhost-web/main.go:187–205`; `deploy/lightsail/docker-compose.yml:120`).
- **SAME — wiring present, source only.** Both Caddy variants route to both Go slots with a health probe and block public metrics (`deploy/lightsail/caddy/Caddyfile.acme:14–17,37–45`; `deploy/lightsail/caddy/Caddyfile.cloudflare:60–65,87–95`). Alloy scrapes both slots and sends to Grafana; cAdvisor provides container metrics (`deploy/lightsail/monitoring/config.alloy:59–85`). Go calls the submit, iCal, mail and filing watchdog heartbeat paths (`go/cmd/ubyhost-web/register_filing.go:39`; `register_jobs.go:62`; `register_job_mail.go:141` in that package, and `go/internal/calendar/filing_watchdog.go:293–310`). Source paths do not demonstrate that the alerts received a live ping.
- **SAME — backup path present, source only.** Backup code can select an active app service and stream encrypted PostgreSQL dumps. WAL-G still has base-backup and retention commands (`deploy/lightsail/scripts/backup.sh:30–48,63–105`; `deploy/lightsail/scripts/walg-backup.sh:18–25`).
- **DIFFERENT — optional app dashboard URL.** `POSTHOG_APP_URL` is customizable in Python and read by Go, but has no pass-through in the Go Compose environment. A nondefault configured URL would fall back to the default on that stack (`App/app/config.py:529`; `go/internal/web/billing/admin_page.go:131`; `deploy/lightsail/docker-compose.yml:110–228`). The brief does not establish a nondefault value.
- **UNVERIFIED — operational checks.** Live Compose/Caddy, actual environment values, health under a read-only volume, heartbeat delivery, backup restore, WAL archives, and measured memory with two slots. Default memory is 128 MiB per slot (`deploy/lightsail/docker-compose.yml:246,258–264`). Migration 00023 adds a table. Migration 00024 replaces two check constraints and can scan existing rows (`App/migrations_pg/00023_apartment_entry_code.sql:1–32`; `App/migrations_pg/00024_guide_import_public_url.sql:1–7`). Production-sized lock and runtime costs were not measured. The week-one retention conflict is in the critical table.

## Completion and coverage

The full behavioral matrix remains open for most write routes, individual mail and job cases, exhaustive access control, seeded export renders, and the live operations listed above. The report is saved outside the source checkout. The checkout was used for reads and the narrow fixture test. No source edits, commits, pushes, PRs or production changes were made.

## Appendix A. All Python write routes

## Python write-route inventory

Source inventory covers FastAPI POST, PUT, DELETE and PATCH decorators and constant method registrations under App/app/routes and App/app/main.py. Go entries are source anchors for literal registrations, method tables and guide action dispatch, with placeholder names normalized for lookup. Generic dispatch and aliases can implement routes without a literal match. UNVERIFIED means behavior was not compared. The previous route-existence check was left alone.

| Method and path | Python entry point | Go source candidate | Verdict |
|---|---|---|---|
| `POST /language` | `App/app/main.py:576` `set_language` | `go/internal/web/public/utility.go:64` | UNVERIFIED |
| `POST /smart-locks/setup` | `App/app/routes/admin.py:730` `smart_locks_setup` | `go/internal/web/properties/smart_locks.go:37` | UNVERIFIED |
| `POST /smart-locks/refresh` | `App/app/routes/admin.py:777` `smart_locks_refresh` | `go/internal/web/properties/smart_locks.go:38` | UNVERIFIED |
| `POST /smart-locks/remove` | `App/app/routes/admin.py:821` `smart_locks_remove` | `go/internal/web/properties/smart_locks.go:39` | UNVERIFIED |
| `POST /entities/{entity_id}/invoice` | `App/app/routes/admin.py:967` `entity_invoice_details` | `go/internal/web/properties/invoice_details.go:21` | UNVERIFIED |
| `POST /entities` | `App/app/routes/admin.py:1196` `create_entity` | `go/internal/web/properties/entities.go:36` | UNVERIFIED |
| `POST /entities/{entity_id}` | `App/app/routes/admin.py:1231` `update_entity` | `go/internal/web/properties/entities.go:37` | UNVERIFIED |
| `POST /entities/{entity_id}/archive` | `App/app/routes/admin.py:1262` `archive_entity` | `go/internal/web/properties/properties.go:43` | UNVERIFIED |
| `POST /entities/{entity_id}/unarchive` | `App/app/routes/admin.py:1287` `unarchive_entity` | `go/internal/web/properties/properties.go:44` | UNVERIFIED |
| `POST /entities/{entity_id}/delete` | `App/app/routes/admin.py:1304` `delete_entity` | `go/internal/web/properties/properties.go:45` | UNVERIFIED |
| `POST /apartments` | `App/app/routes/admin.py:1802` `apartment_create` | `go/internal/web/properties/apartment_create.go:94` | UNVERIFIED |
| `POST /apartments/{apartment_id}/door-codes` | `App/app/routes/admin.py:2500` `apartment_door_codes` | `go/internal/web/properties/apartment_door_codes.go:36` | SAME (source-confirmed toggle happy path and normal validation) |
| `POST /apartments/{apartment_id}` | `App/app/routes/admin.py:2535` `apartment_update` | `go/internal/web/properties/apartment_update.go:84` | UNVERIFIED |
| `POST /apartments/{apartment_id}/regenerate-pin` | `App/app/routes/admin.py:3050` `regenerate_pin` | `go/internal/web/properties/properties.go:48` | UNVERIFIED |
| `POST /apartments/{apartment_id}/automation-timing` | `App/app/routes/admin.py:3079` `automation_timing_save` | `go/internal/web/properties/apartment_small_posts.go:52` | UNVERIFIED |
| `POST /apartments/{apartment_id}/regenerate-link` | `App/app/routes/admin.py:3141` `regenerate_link` | `go/internal/web/properties/properties.go:49` | UNVERIFIED |
| `POST /apartments/{apartment_id}/archive` | `App/app/routes/admin.py:3186` `archive_apartment` | `go/internal/web/properties/properties.go:46` | UNVERIFIED |
| `POST /apartments/{apartment_id}/unarchive` | `App/app/routes/admin.py:3207` `unarchive_apartment` | `go/internal/web/properties/properties.go:47` | UNVERIFIED |
| `POST /apartments/{apartment_id}/feeds` | `App/app/routes/admin.py:3328` `add_feed` | `go/internal/web/properties/apartment_small_posts.go:53` | UNVERIFIED |
| `POST /feeds/{feed_id}/delete` | `App/app/routes/admin.py:3404` `delete_feed` | `go/internal/web/properties/properties.go:50` | UNVERIFIED |
| `POST /sync` | `App/app/routes/admin.py:3419` `sync_now` | `go/internal/web/properties/sync.go:23` | UNVERIFIED |
| `POST /apartments/{apartment_id}/test-connection` | `App/app/routes/admin.py:3448` `test_connection` | `go/internal/web/properties/apartment_small_posts.go:56` | UNVERIFIED |
| `POST /apartments/{apartment_id}/police-letter` | `App/app/routes/admin.py:3552` `police_letter_read` | `go/internal/web/properties/apartment_small_posts.go:57` | UNVERIFIED |
| `POST /apartments/{apartment_id}/refresh-codelists` | `App/app/routes/admin.py:3652` `refresh_codelists` | `go/internal/web/properties/apartment_small_posts.go:58` | UNVERIFIED |
| `POST /reservations` | `App/app/routes/admin.py:3879` `reservation_create` | `go/internal/web/stays/handlers.go:193` | UNVERIFIED |
| `POST /reservations/submit-ready` | `App/app/routes/admin.py:4005` `reservations_submit_ready` | `go/internal/web/stays/submit.go:37` | UNVERIFIED |
| `POST /reservations/{reservation_id}` | `App/app/routes/admin.py:4176` `reservation_update` | `go/internal/web/staydetail/handlers.go:95` | SAME (source-confirmed field save and top-level side-effect calls on normal path) |
| `POST /reservations/{reservation_id}/remove-empty-slot` | `App/app/routes/admin.py:4223` `reservation_remove_empty_slot` | `go/internal/web/stays/edit_posts.go:47` | UNVERIFIED |
| `POST /reservations/{reservation_id}/quick-edit` | `App/app/routes/admin.py:4270` `reservation_quick_edit` | `go/internal/web/stays/edit_posts.go:46` | UNVERIFIED |
| `POST /reservations/{reservation_id}/delete-demo` | `App/app/routes/admin.py:4301` `reservation_delete_demo` | `go/internal/web/stays/edit_posts.go:50` | UNVERIFIED |
| `POST /reservations/{reservation_id}/archive` | `App/app/routes/admin.py:4315` `reservation_archive` | `go/internal/web/stays/edit_posts.go:48` | UNVERIFIED |
| `POST /reservations/{reservation_id}/unarchive` | `App/app/routes/admin.py:4335` `reservation_unarchive` | `go/internal/web/stays/edit_posts.go:49` | UNVERIFIED |
| `POST /reservations/{reservation_id}/reopen-guest` | `App/app/routes/admin.py:4352` `reservation_reopen_guest` | `go/internal/web/stays/claim_ops.go:175` | UNVERIFIED |
| `POST /reservations/{reservation_id}/resend-claim` | `App/app/routes/admin.py:4376` `reservation_resend_claim` | `go/internal/web/stays/claim_ops.go:176` | UNVERIFIED |
| `POST /reservations/{reservation_id}/release-claim` | `App/app/routes/admin.py:4403` `reservation_release_claim` | `go/internal/web/stays/claim_ops.go:177` | UNVERIFIED |
| `POST /reservations/{reservation_id}/filed-by-hand` | `App/app/routes/admin.py:4416` `reservation_filed_by_hand` | `go/internal/web/stays/claim_ops.go:178` | UNVERIFIED |
| `POST /reservations/{reservation_id}/filed-by-hand/undo` | `App/app/routes/admin.py:4448` `reservation_filed_by_hand_undo` | `go/internal/web/stays/claim_ops.go:179` | UNVERIFIED |
| `POST /reservations/{reservation_id}/submit` | `App/app/routes/admin.py:4465` `reservation_submit` | `go/internal/web/stays/submit.go:38` | UNVERIFIED |
| `POST /reservations/{reservation_id}/guests` | `App/app/routes/admin.py:4638` `guest_create` | `go/internal/web/stays/guest_edit.go:112` | DIFFERENT (see host guest encryption finding) |
| `POST /guests/{guest_id}` | `App/app/routes/admin.py:4717` `guest_update` | `go/internal/web/stays/guest_edit.go:114` | DIFFERENT (see host guest encryption finding) |
| `POST /guests/{guest_id}/restrict` | `App/app/routes/admin.py:4844` `guest_restrict` | `go/internal/web/stays/guest_privacy.go:177` | UNVERIFIED |
| `POST /guests/{guest_id}/unrestrict` | `App/app/routes/admin.py:4870` `guest_unrestrict` | `go/internal/web/stays/guest_privacy.go:178` | UNVERIFIED |
| `POST /guests/{guest_id}/verify-identity` | `App/app/routes/admin.py:4889` `guest_verify_identity` | `go/internal/web/stays/guest_privacy.go:179` | UNVERIFIED |
| `POST /guests/{guest_id}/reveal-identity` | `App/app/routes/admin.py:4958` `guest_reveal_identity` | `go/internal/web/stays/guest_privacy.go:181` | UNVERIFIED |
| `POST /guests/{guest_id}/archive` | `App/app/routes/admin.py:5000` `guest_archive` | `go/internal/web/stays/guest_lifecycle.go:44` | UNVERIFIED |
| `POST /guests/{guest_id}/unarchive` | `App/app/routes/admin.py:5036` `guest_unarchive` | `go/internal/web/stays/guest_lifecycle.go:45` | UNVERIFIED |
| `POST /guests/{guest_id}/delete` | `App/app/routes/admin.py:5063` `guest_delete` | `go/internal/web/stays/guest_lifecycle.go:46` | UNVERIFIED |
| `POST /guests/{guest_id}/resend` | `App/app/routes/admin.py:5090` `guest_resend` | `go/internal/web/stays/guest_lifecycle.go:47` | UNVERIFIED |
| `POST /alerts/{alert_id}/dismiss` | `App/app/routes/admin.py:5263` `dismiss_alert` | `go/internal/web/properties/misc.go:30` | UNVERIFIED |
| `POST /login` | `App/app/routes/admin_accounts.py:116` `login_submit` | `go/internal/web/auth/auth.go:66` | UNVERIFIED |
| `POST /login/link` | `App/app/routes/admin_accounts.py:228` `login_link_submit` | `go/internal/web/auth/auth.go:68` | UNVERIFIED |
| `POST /login/2fa` | `App/app/routes/admin_accounts.py:275` `two_factor_login` | `go/internal/web/auth/auth.go:69` | UNVERIFIED |
| `POST /logout` | `App/app/routes/admin_accounts.py:318` `logout` | `go/internal/web/auth/auth.go:47` | UNVERIFIED |
| `POST /account/logout-all` | `App/app/routes/admin_accounts.py:330` `logout_all` | `go/internal/web/auth/auth.go:48` | UNVERIFIED |
| `POST /account/onboarding-emails` | `App/app/routes/admin_accounts.py:350` `onboarding_emails_submit` | `go/internal/web/auth/auth.go:49` | UNVERIFIED |
| `POST /account/stay-fee-emails` | `App/app/routes/admin_accounts.py:374` `stay_fee_emails_submit` | `go/internal/web/auth/auth.go:50` | UNVERIFIED |
| `POST /account/guest-details-mail` | `App/app/routes/admin_accounts.py:393` `guest_details_mail_submit` | `go/internal/web/auth/auth.go:51` | UNVERIFIED |
| `POST /account/accept` | `App/app/routes/admin_accounts.py:437` `account_accept_submit` | `go/internal/web/auth/auth.go:74` | UNVERIFIED |
| `POST /account/2fa/setup` | `App/app/routes/admin_accounts.py:493` `two_factor_setup_submit` | `go/internal/web/auth/auth.go:76` | UNVERIFIED |
| `POST /account/2fa/move` | `App/app/routes/admin_accounts.py:541` `two_factor_move` | `go/internal/web/auth/auth.go:52` | UNVERIFIED |
| `POST /account/2fa/disable` | `App/app/routes/admin_accounts.py:578` `two_factor_disable` | `go/internal/web/auth/auth.go:53` | UNVERIFIED |
| `POST /account/email` | `App/app/routes/admin_accounts.py:612` `account_email_request` | `go/internal/web/auth/auth.go:77` | UNVERIFIED |
| `POST /account/email/confirm` | `App/app/routes/admin_accounts.py:672` `account_email_confirm_submit` | `go/internal/web/auth/auth.go:79` | UNVERIFIED |
| `POST /admin/users` | `App/app/routes/admin_accounts.py:745` `user_create` | `go/internal/web/auth/auth.go:70` | UNVERIFIED |
| `POST /admin/users/{user_id}/invite` | `App/app/routes/admin_accounts.py:774` `user_invite` | `go/internal/web/auth/auth.go:71` | UNVERIFIED |
| `POST /admin/users/{user_id}/email` | `App/app/routes/admin_accounts.py:788` `user_email_set` | `go/internal/web/auth/auth.go:72` | UNVERIFIED |
| `POST /admin/users/{user_id}/impersonate` | `App/app/routes/admin_accounts.py:854` `user_impersonate` | `go/internal/web/auth/auth.go:57` | UNVERIFIED |
| `POST /admin/stop-impersonating` | `App/app/routes/admin_accounts.py:883` `stop_impersonating` | `go/internal/web/auth/auth.go:58` | UNVERIFIED |
| `POST /admin/incidents` | `App/app/routes/admin_accounts.py:973` `incident_create` | `go/internal/web/auth/auth.go:60` | UNVERIFIED |
| `POST /admin/incidents/{incident_id}` | `App/app/routes/admin_accounts.py:997` `incident_update` | `go/internal/web/auth/auth.go:61` | UNVERIFIED |
| `POST /admin/users/{user_id}/export` | `App/app/routes/admin_accounts.py:1026` `user_workspace_export` | `go/internal/web/auth/auth.go:80` | UNVERIFIED |
| `POST /admin/users/{user_id}/schedule-deletion` | `App/app/routes/admin_accounts.py:1055` `user_schedule_deletion` | `go/internal/web/auth/auth.go:87` | UNVERIFIED |
| `POST /admin/fakturace/vypis` | `App/app/routes/admin_billing.py:66` `billing_admin_statement` | `go/internal/web/billing/table.go:40` | UNVERIFIED |
| `POST /admin/fakturace/{invoice_id}/zaplaceno` | `App/app/routes/admin_billing.py:84` `billing_admin_mark_paid` | `go/internal/web/billing/table.go:41` | UNVERIFIED |
| `POST /admin/fakturace/{invoice_id}/storno` | `App/app/routes/admin_billing.py:99` `billing_admin_storno` | `go/internal/web/billing/table.go:42` | UNVERIFIED |
| `POST /admin/customers/{user_id}/sleva` | `App/app/routes/admin_customers.py:111` `customer_discount` | `go/cmd/ubyhost-web/register_web_customers.go:28` | UNVERIFIED |
| `POST /admin/customers/{user_id}/plan` | `App/app/routes/admin_customers.py:135` `customer_plan` | `go/cmd/ubyhost-web/register_web_customers.go:29` | UNVERIFIED |
| `POST /admin/customers/{user_id}/priradit` | `App/app/routes/admin_customers.py:165` `customer_assign_plan` | `go/cmd/ubyhost-web/register_web_customers.go:30` | UNVERIFIED |
| `POST /admin/customers/{user_id}/prodlouzit` | `App/app/routes/admin_customers.py:184` `customer_extend_trial` | `go/cmd/ubyhost-web/register_web_customers.go:26` | UNVERIFIED |
| `POST /admin/customers/{user_id}/aktivovat` | `App/app/routes/admin_customers.py:205` `customer_toggle_active` | `go/cmd/ubyhost-web/register_web_customers.go:23` | UNVERIFIED |
| `POST /admin/customers/{user_id}/overit-znovu` | `App/app/routes/admin_customers.py:228` `customer_resend_verification` | `go/cmd/ubyhost-web/register_web_customers.go:27` | UNVERIFIED |
| `POST /admin/customers/{user_id}/stav` | `App/app/routes/admin_customers.py:241` `customer_status` | `go/cmd/ubyhost-web/register_web_customers.go:25` | UNVERIFIED |
| `POST /predplatne` | `App/app/routes/billing.py:86` `plan_order` | `go/internal/web/billing/table.go:38` | UNVERIFIED |
| `POST /predplatne/zmena` | `App/app/routes/billing.py:128` `plan_change` | `go/internal/web/billing/table.go:39` | UNVERIFIED |
| `POST /predplatne/zrusit` | `App/app/routes/billing.py:153` `plan_cancel` | `go/internal/web/billing/table.go:34` | UNVERIFIED |
| `POST /predplatne/obnovit` | `App/app/routes/billing.py:164` `plan_resume` | `go/internal/web/billing/table.go:35` | UNVERIFIED |
| `POST /cleaning/events` | `App/app/routes/cleaning.py:176` `create_event` | `go/internal/web/cleaning/host_events.go:181` | UNVERIFIED |
| `POST /cleaning/events/{event_id}` | `App/app/routes/cleaning.py:216` `update_event` | `go/internal/web/cleaning/host_events.go:252` | UNVERIFIED |
| `POST /cleaning/events/{event_id}/delete` | `App/app/routes/cleaning.py:237` `delete_event` | `go/cmd/ubyhost-web/register_web_cleaning.go:23` | UNVERIFIED |
| `POST /cleaning/properties/{property_id}` | `App/app/routes/cleaning.py:282` `save_property` | `go/internal/web/cleaning/host_settings.go:98` | UNVERIFIED |
| `POST /cleaning/properties/{property_id}/code/{action}` | `App/app/routes/cleaning.py:297` `code_action` | `go/internal/web/cleaning/host_codes.go:43` | UNVERIFIED |
| `POST /cleaning/shares` | `App/app/routes/cleaning.py:338` `create_share` | `go/internal/web/cleaning/host_shares.go:149` | UNVERIFIED |
| `POST /cleaning/shares/{share_id}/revoke` | `App/app/routes/cleaning.py:354` `revoke_share` | `go/cmd/ubyhost-web/register_web_cleaning.go:24` | UNVERIFIED |
| `POST /settings/workspace-export` | `App/app/routes/exports.py:416` `settings_workspace_export` | `go/internal/web/exports/routes.go:38` | UNVERIFIED |
| `POST /settings/purge-expired` | `App/app/routes/exports.py:537` `purge_expired_records` | `go/internal/web/exports/routes.go:42` | UNVERIFIED |
| `POST /l/{token}/pin` | `App/app/routes/guest.py:1267` `verify_pin` | `go/internal/web/guest/shell.go:521` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/claim/confirm` | `App/app/routes/guest.py:1643` `claim_confirm` | `go/internal/web/guest/stay_claim.go:89` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/party` | `App/app/routes/guest.py:1694` `set_party_size` | `go/internal/web/guest/party.go:55` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/count` | `App/app/routes/guest.py:1820` `lead_change_count` | `go/internal/web/guest/party.go:56` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/another` | `App/app/routes/guest.py:1865` `add_another_person` | `go/internal/web/guest/party.go:57` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/remove/{guest_id}` | `App/app/routes/guest.py:2235` `guest_remove` | `go/internal/web/guest/form_pages.go:66` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/relang` | `App/app/routes/guest.py:2288` `guest_form_relang` | `go/internal/web/guest/form_pages.go:67` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/save` | `App/app/routes/guest.py:2362` `guest_form_save` | `go/internal/web/guest/form_save.go:35` | DIFFERENT (see guest-save findings) |
| `POST /l/{token}/{reservation_id}/draft` | `App/app/routes/guest.py:2784` `guest_form_draft` | `go/internal/web/guest/draft_scan.go:61` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/scan` | `App/app/routes/guest.py:2848` `guest_document_scan` | `go/internal/web/guest/draft_scan.go:62` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/cards` | `App/app/routes/guest_guide.py:99` `guide_add` | `go/internal/web/ai/guide_cards.go:24` | UNVERIFIED |
| `POST /apartments/{apartment_id}/leon` | `App/app/routes/guest_guide.py:148` `leon_save` | `go/internal/web/ai/guide_leon.go:24` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/import` | `App/app/routes/guest_guide.py:180` `guide_import` | `go/internal/web/ai/guide_import.go:25` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/qr/rotate` | `App/app/routes/guest_guide.py:228` `guide_qr_rotate` | `go/internal/web/ai/guide_qr.go:22` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/quick/{step}` | `App/app/routes/guest_guide.py:294` `guide_quick_save` | `go/internal/web/ai/guide_quick.go:50` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/{item_id}` | `App/app/routes/guest_guide.py:333` `guide_card_save` | `go/internal/web/ai/guide_cards.go:20` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/{item_id}/discard` | `App/app/routes/guest_guide.py:360` `guide_card_discard` | `go/internal/web/ai/guide_cards.go:23`, `go/internal/web/ai/guide_cards.go:202-211` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/{item_id}/skip` | `App/app/routes/guest_guide.py:371` `guide_card_skip` | `go/internal/web/ai/guide_cards.go:23`, `go/internal/web/ai/guide_cards.go:202-211` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/{item_id}/delete` | `App/app/routes/guest_guide.py:387` `guide_card_delete` | `go/internal/web/ai/guide_cards.go:23`, `go/internal/web/ai/guide_cards.go:202-211` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/{item_id}/photos` | `App/app/routes/guest_guide.py:402` `guide_photo_add` | `go/internal/web/ai/guide_cards.go:23`, `go/internal/web/ai/guide_cards.go:202-211` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}/delete` | `App/app/routes/guest_guide.py:437` `guide_photo_delete` | `go/internal/web/ai/guide_photos.go:18` | UNVERIFIED |
| `POST /l/{token}/{reservation_id}/guide/leon` | `App/app/routes/guest_leon.py:70` `stay_leon` | `go/internal/web/guest/leon_questions.go:219` | UNVERIFIED |
| `POST /g/{token}/leon` | `App/app/routes/guest_leon.py:97` `qr_leon` | `go/internal/web/guest/leon_questions.go:221` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/questions/{question_id}` | `App/app/routes/guest_questions.py:61` `question_answer` | `go/internal/web/guest/leon_questions.go:224` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/questions/{question_id}/dismiss` | `App/app/routes/guest_questions.py:76` `question_dismiss` | `go/internal/web/guest/leon_questions.go:225` | UNVERIFIED |
| `POST /apartments/{apartment_id}/guide/questions/{question_id}/card` | `App/app/routes/guest_questions.py:86` `question_card` | `go/internal/web/guest/leon_questions.go:226` | UNVERIFIED |
| `POST /havel` | `App/app/routes/havel.py:179` `havel_send` | `go/internal/web/ai/havel_handlers.go:66` | UNVERIFIED |
| `POST /havel/support` | `App/app/routes/havel.py:275` `havel_support` | `go/internal/web/ai/havel_handlers.go:71` | UNVERIFIED |
| `POST /havel/not-helped` | `App/app/routes/havel.py:313` `havel_not_helped` | `go/internal/web/ai/havel_handlers.go:73` | UNVERIFIED |
| `POST /invoices/preview` | `App/app/routes/invoices.py:790` `invoice_preview` | `go/internal/web/invoices/post_issue.go:19` | UNVERIFIED |
| `POST /invoices` | `App/app/routes/invoices.py:814` `invoice_issue` | `go/internal/web/invoices/post_issue.go:20` | UNVERIFIED |
| `POST /invoices/{invoice_id}/paid` | `App/app/routes/invoices.py:930` `invoice_mark_paid` | `go/internal/web/invoices/actions.go:17` | UNVERIFIED |
| `POST /invoices/{invoice_id}/send` | `App/app/routes/invoices.py:961` `invoice_send` | `go/internal/web/invoices/send.go:23` | UNVERIFIED |
| `POST /invoices/{invoice_id}/cancel` | `App/app/routes/invoices.py:1004` `invoice_cancel` | `go/internal/web/invoices/actions.go:18` | UNVERIFIED |
| `POST /apartments/{apartment_id}/leon/setup` | `App/app/routes/leon_setup.py:101` `setup_save` | `go/internal/web/ai/leon_handlers.go:40` | UNVERIFIED |
| `POST /apartments/{apartment_id}/leon/setup/try` | `App/app/routes/leon_setup.py:122` `setup_try` | `go/internal/web/ai/leon_extra.go:25` | UNVERIFIED |
| `POST /mail/unsubscribe/{token}` | `App/app/routes/mail_unsubscribe.py:55` `mail_unsubscribe_submit` | `go/cmd/ubyhost-web/register_web_public.go:32` | UNVERIFIED |
| `POST /demo` | `App/app/routes/onboarding.py:22` `load_demo` | `go/cmd/ubyhost-web/register_web_onboarding_demo.go:24` | UNVERIFIED |
| `POST /demo/reset` | `App/app/routes/onboarding.py:37` `reset_demo` | `go/cmd/ubyhost-web/register_web_onboarding_demo.go:25` | UNVERIFIED |
| `POST /onboarding/dismiss` | `App/app/routes/onboarding.py:57` `onboarding_dismiss` | `go/cmd/ubyhost-web/register_web_onboarding.go:23` | UNVERIFIED |
| `POST /welcome-back/dismiss` | `App/app/routes/onboarding.py:71` `welcome_back_dismiss` | `go/cmd/ubyhost-web/register_web_onboarding.go:25` | UNVERIFIED |
| `POST /onboarding/resume` | `App/app/routes/onboarding.py:82` `onboarding_resume` | `go/cmd/ubyhost-web/register_web_onboarding.go:24` | UNVERIFIED |
| `POST /celebrations/dismiss` | `App/app/routes/onboarding.py:97` `dismiss_celebration` | `go/cmd/ubyhost-web/register_web_onboarding.go:26` | UNVERIFIED |
| `POST /apartments/{apartment_id}/setup` | `App/app/routes/onboarding_wizard.py:342` `setup_action` | `go/internal/web/onboarding/wizard_post.go:45` | UNVERIFIED |
| `POST /account/passkeys/options` | `App/app/routes/passkeys.py:94` `passkey_register_options` | `go/internal/web/auth/passkeys.go:45` | UNVERIFIED |
| `POST /account/security-prompt/seen` | `App/app/routes/passkeys.py:112` `security_prompt_seen` | `go/internal/web/auth/auth.go:54` | UNVERIFIED |
| `POST /account/passkeys` | `App/app/routes/passkeys.py:125` `passkey_register` | `go/internal/web/auth/passkeys.go:46` | UNVERIFIED |
| `POST /account/passkeys/{passkey_id}/rename` | `App/app/routes/passkeys.py:171` `passkey_rename` | `go/internal/web/auth/passkeys.go:47` | UNVERIFIED |
| `POST /account/passkeys/{passkey_id}/delete` | `App/app/routes/passkeys.py:185` `passkey_delete` | `go/internal/web/auth/passkeys.go:48` | UNVERIFIED |
| `POST /login/passkey/options` | `App/app/routes/passkeys.py:202` `passkey_login_options` | `go/internal/web/auth/passkeys.go:49` | UNVERIFIED |
| `POST /login/passkey` | `App/app/routes/passkeys.py:213` `passkey_login` | `go/internal/web/auth/passkeys.go:50` | UNVERIFIED |
| `POST /payments/services` | `App/app/routes/payments.py:155` `payment_service_add` | `go/cmd/ubyhost-web/register_web_payments_pages.go:25` | UNVERIFIED (retired flow where applicable) |
| `POST /payments/services/{service_id}/delete` | `App/app/routes/payments.py:172` `payment_service_delete` | `go/cmd/ubyhost-web/register_web_payments_pages.go:26` | UNVERIFIED (retired flow where applicable) |
| `POST /payments/requests/new` | `App/app/routes/payments.py:181` `payment_request_new` | `go/cmd/ubyhost-web/register_web.go:42` | UNVERIFIED (retired flow where applicable) |
| `POST /payments/requests/{request_id}/link` | `App/app/routes/payments.py:258` `payment_request_link` | `go/cmd/ubyhost-web/register_web.go:44` | UNVERIFIED (retired flow where applicable) |
| `POST /payments/requests/{request_id}/send` | `App/app/routes/payments.py:319` `payment_request_send` | `go/cmd/ubyhost-web/register_web.go:43` | UNVERIFIED (retired flow where applicable) |
| `POST /apartments/{apartment_id}/page` | `App/app/routes/payments.py:442` `property_page_save` | `go/internal/web/booking/property_page_host.go:71` | UNVERIFIED |
| `POST /apartments/{apartment_id}/page/photo-move` | `App/app/routes/payments.py:480` `property_page_photo_move` | `go/internal/web/booking/property_page_host.go:72` | UNVERIFIED |
| `POST /apartments/{apartment_id}/page/photo-delete` | `App/app/routes/payments.py:499` `property_page_photo_delete` | `go/internal/web/booking/property_page_host.go:73` | UNVERIFIED |
| `POST /apartments/{apartment_id}/booking-site` | `App/app/routes/payments.py:596` `booking_site_save` | `go/internal/web/booking/booking_site_setup.go:82` | UNVERIFIED |
| `POST /apartments/{apartment_id}/booking-site/pay` | `App/app/routes/payments.py:635` `booking_site_pay` | `go/internal/web/booking/booking_site_actions.go:42` | UNVERIFIED |
| `POST /apartments/{apartment_id}/booking-site/confirm` | `App/app/routes/payments.py:688` `booking_site_confirm` | `go/internal/web/booking/booking_site_actions.go:44` | UNVERIFIED |
| `POST /apartments/{apartment_id}/booking-site/decline` | `App/app/routes/payments.py:693` `booking_site_decline` | `go/internal/web/booking/booking_site_actions.go:46` | UNVERIFIED |
| `POST /apartments/{apartment_id}/booking-site/cancel` | `App/app/routes/payments.py:697` `booking_site_cancel` | `go/internal/web/booking/booking_site_actions.go:48` | UNVERIFIED |
| `POST /payments/consent` | `App/app/routes/payments.py:737` `payments_consent_accept` | `go/cmd/ubyhost-web/register_web_payments_pages.go:29` | UNVERIFIED (retired flow where applicable) |
| `POST /privacy-requests` | `App/app/routes/privacy_requests.py:38` `privacy_request_create` | `go/cmd/ubyhost-web/register_web_privacy.go:22` | UNVERIFIED |
| `POST /privacy-requests/{request_id}` | `App/app/routes/privacy_requests.py:71` `privacy_request_update` | `go/cmd/ubyhost-web/register_web_privacy.go:23` | UNVERIFIED |
| `POST /p/{slug}/book` | `App/app/routes/property_page.py:294` `property_page_book` | `go/cmd/ubyhost-web/register_web_booking_property.go:19` | UNVERIFIED (retired flow where applicable) |
| `POST /p/{slug}/checkout` | `App/app/routes/property_page.py:331` `property_page_checkout` | `go/cmd/ubyhost-web/register_web_booking_checkout.go:27` | UNVERIFIED (retired flow where applicable) |
| `POST /p/{slug}/b/{booking_id}/{token}/cancel` | `App/app/routes/property_page.py:536` `booking_manage_cancel` | `go/internal/web/booking/cancel_pdfs.go:285` | UNVERIFIED (retired flow where applicable) |
| `POST /account/push/subscribe` | `App/app/routes/push.py:68` `push_subscribe` | `go/cmd/ubyhost-web/register_web.go:35` | UNVERIFIED |
| `POST /account/push/refresh` | `App/app/routes/push.py:90` `push_refresh` | `go/cmd/ubyhost-web/register_web.go:36` | UNVERIFIED |
| `POST /account/push/unsubscribe` | `App/app/routes/push.py:104` `push_unsubscribe` | `go/cmd/ubyhost-web/register_web.go:37` | UNVERIFIED |
| `POST /account/push/test` | `App/app/routes/push.py:115` `push_test` | `go/cmd/ubyhost-web/register_web.go:39` | UNVERIFIED |
| `POST /account/push/devices/{device_id}/delete` | `App/app/routes/push.py:131` `push_device_delete` | `go/cmd/ubyhost-web/register_web.go:38` | UNVERIFIED |
| `POST /signup` | `App/app/routes/signup.py:75` `signup_submit` | `go/internal/web/auth/auth.go:82` | UNVERIFIED |
| `POST /signup/verify` | `App/app/routes/signup.py:149` `signup_verify_submit` | `go/internal/web/auth/auth.go:84` | UNVERIFIED |
| `POST /admin/ads-conversions.csv` | `App/app/routes/signup.py:177` `ads_conversions_csv` | `go/internal/web/auth/auth.go:62` | UNVERIFIED |
| `POST /admin/users/{user_id}/ads-consent/withdraw` | `App/app/routes/signup.py:202` `ads_consent_withdraw` | `go/internal/web/auth/auth.go:63` | UNVERIFIED |
| `POST /settings/privacy/ad-consent` | `App/app/routes/signup.py:216` `ad_consent_settings` | `go/internal/web/auth/auth.go:64` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/guest-pay-preview` | `App/app/routes/stay_fees.py:134` `guest_pay_preview` | `go/cmd/ubyhost-web/register_web_stayfees_guestpay.go:19` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/adjustment` | `App/app/routes/stay_fees.py:1036` `stay_fee_adjustment_add` | `go/internal/web/stayfees/adjust.go:230` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/adjustment/{adjustment_id}/undo` | `App/app/routes/stay_fees.py:1101` `stay_fee_adjustment_undo` | `go/internal/web/stayfees/handlers.go:831` | UNVERIFIED |
| `POST /stay-fees/guest-decision` | `App/app/routes/stay_fees.py:1125` `stay_fee_guest_decision` | `go/internal/web/stayfees/handlers.go:832` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/scope-ruling` | `App/app/routes/stay_fees.py:1175` `stay_fee_scope_ruling` | `go/internal/web/stayfees/handlers.go:833` | UNVERIFIED |
| `POST /stay-fees/confirm-ready` | `App/app/routes/stay_fees.py:1198` `stay_fee_confirm_ready` | `go/cmd/ubyhost-web/register_web_stayfees_confirm.go:19` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/copy-setup` | `App/app/routes/stay_fees.py:1232` `stay_fee_copy_setup` | `go/internal/web/stayfees/handlers.go:834` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/finalize` | `App/app/routes/stay_fees.py:1259` `stay_fee_finalize` | `go/cmd/ubyhost-web/register_web_stayfees_finalize.go:19` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/paid` | `App/app/routes/stay_fees.py:1326` `stay_fee_mark_paid` | `go/internal/web/stayfees/handlers.go:835` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/filings/{filing_id}/sent` | `App/app/routes/stay_fees.py:1359` `stay_fee_mark_filing_sent` | `go/internal/web/stayfees/handlers.go:836` | UNVERIFIED |
| `POST /stay-fees/{apartment_id}/filings/{filing_id}/paid` | `App/app/routes/stay_fees.py:1380` `stay_fee_mark_filing_paid` | `go/internal/web/stayfees/handlers.go:837` | UNVERIFIED |
| `POST /payments/connect/start` | `App/app/routes/stripe_connect.py:83` `connect_start_post` | `go/cmd/ubyhost-web/register_web.go:33` | UNVERIFIED (retired flow where applicable) |
| `POST /webhooks/stripe` | `App/app/routes/stripe_connect.py:113` `stripe_webhook` | `go/cmd/ubyhost-web/register_web.go:24` | UNVERIFIED |

## Appendix B. Language inventory

## Translation source comparison

Guest templates were scanned for literal .T keys. All embedded guest catalog entries were also compared, including entries selected dynamically. Python's effective fallback is English. Host catalog overlap is reported separately. No browser render was run.

### Guest de

SAME 355.


### Guest es

SAME 355.


### Guest fr

SAME 355.


### Guest uk

SAME 355.


### Host catalog shared keys

Compares literal values in host web catalogs with Python host_i18n values for the same language and key. A catalog with shared keys may also contain keys from other Python catalogs or per-page strings. Values shown here are source differences, and whether they change rendered wording requires checking the caller.

| Go catalog | Language | Same | Different | Go keys absent from Python host_i18n |
|---|---|---:|---:|---:|
| `go/internal/hostweb/i18n.json` | cs | 0 | 0 | 0 |
| `go/internal/hostweb/i18n.json` | en | 0 | 0 | 0 |
| `go/internal/hostweb/i18n.json` | vi | 0 | 0 | 0 |
| `go/internal/hostweb/layout/i18n.json` | cs | 423 | 0 | 0 |
| `go/internal/hostweb/layout/i18n.json` | en | 423 | 0 | 0 |
| `go/internal/hostweb/layout/i18n.json` | vi | 381 | 0 | 0 |
| `go/internal/web/ai/guide/i18n.json` | cs | 399 | 0 | 0 |
| `go/internal/web/ai/guide/i18n.json` | en | 399 | 0 | 0 |
| `go/internal/web/ai/guide/i18n.json` | vi | 48 | 0 | 0 |
| `go/internal/web/auth/authpage/i18n.json` | cs | 130 | 0 | 0 |
| `go/internal/web/auth/authpage/i18n.json` | en | 130 | 0 | 0 |
| `go/internal/web/auth/authpage/i18n.json` | vi | 122 | 0 | 0 |
| `go/internal/web/auth/i18n.json` | cs | 28 | 0 | 0 |
| `go/internal/web/auth/i18n.json` | en | 28 | 0 | 0 |
| `go/internal/web/auth/i18n.json` | vi | 26 | 0 | 0 |
| `go/internal/web/auth/opspage/i18n.json` | cs | 170 | 0 | 0 |
| `go/internal/web/auth/opspage/i18n.json` | en | 170 | 0 | 0 |
| `go/internal/web/auth/opspage/i18n.json` | vi | 156 | 0 | 0 |
| `go/internal/web/billing/i18n.json` | cs | 243 | 0 | 0 |
| `go/internal/web/billing/i18n.json` | en | 243 | 0 | 0 |
| `go/internal/web/billing/i18n.json` | vi | 31 | 0 | 0 |
| `go/internal/web/customers/i18n.json` | cs | 4 | 0 | 0 |
| `go/internal/web/customers/i18n.json` | en | 4 | 0 | 0 |
| `go/internal/web/customers/i18n.json` | vi | 2 | 0 | 0 |
| `go/internal/web/customers/templates/i18n.json` | cs | 185 | 0 | 0 |
| `go/internal/web/customers/templates/i18n.json` | en | 185 | 0 | 0 |
| `go/internal/web/customers/templates/i18n.json` | vi | 36 | 0 | 0 |
| `go/internal/web/exports/i18n.json` | cs | 49 | 0 | 0 |
| `go/internal/web/exports/i18n.json` | en | 49 | 0 | 0 |
| `go/internal/web/exports/i18n.json` | vi | 49 | 0 | 0 |
| `go/internal/web/hostweb/i18n.json` | cs | 110 | 0 | 0 |
| `go/internal/web/hostweb/i18n.json` | en | 110 | 0 | 0 |
| `go/internal/web/hostweb/i18n.json` | vi | 110 | 0 | 0 |
| `go/internal/web/housebook/i18n.json` | cs | 87 | 0 | 0 |
| `go/internal/web/housebook/i18n.json` | en | 87 | 0 | 0 |
| `go/internal/web/housebook/i18n.json` | vi | 87 | 0 | 0 |
| `go/internal/web/invoices/i18n.json` | cs | 209 | 0 | 0 |
| `go/internal/web/invoices/i18n.json` | en | 209 | 0 | 0 |
| `go/internal/web/invoices/i18n.json` | vi | 207 | 0 | 0 |
| `go/internal/web/onboarding/onboardingpage/i18n.json` | cs | 67 | 0 | 0 |
| `go/internal/web/onboarding/onboardingpage/i18n.json` | en | 67 | 0 | 0 |
| `go/internal/web/onboarding/onboardingpage/i18n.json` | vi | 67 | 0 | 0 |
| `go/internal/web/onboarding/wizardtext/i18n.json` | cs | 499 | 0 | 0 |
| `go/internal/web/onboarding/wizardtext/i18n.json` | en | 499 | 0 | 0 |
| `go/internal/web/onboarding/wizardtext/i18n.json` | vi | 480 | 0 | 0 |
| `go/internal/web/privacy/i18n.json` | cs | 39 | 0 | 0 |
| `go/internal/web/privacy/i18n.json` | en | 39 | 0 | 0 |
| `go/internal/web/privacy/i18n.json` | vi | 39 | 0 | 0 |
| `go/internal/web/properties/apartmentcreate/i18n.json` | cs | 2 | 0 | 0 |
| `go/internal/web/properties/apartmentcreate/i18n.json` | en | 2 | 0 | 0 |
| `go/internal/web/properties/apartmentcreate/i18n.json` | vi | 1 | 0 | 0 |
| `go/internal/web/properties/apartmentdetail/i18n.json` | cs | 435 | 0 | 0 |
| `go/internal/web/properties/apartmentdetail/i18n.json` | en | 435 | 0 | 0 |
| `go/internal/web/properties/apartmentdetail/i18n.json` | vi | 408 | 0 | 0 |
| `go/internal/web/properties/apartmentdoorcodes/i18n.json` | cs | 4 | 0 | 0 |
| `go/internal/web/properties/apartmentdoorcodes/i18n.json` | en | 4 | 0 | 0 |
| `go/internal/web/properties/apartmentdoorcodes/i18n.json` | vi | 4 | 0 | 0 |
| `go/internal/web/properties/apartmentnew/i18n.json` | cs | 68 | 0 | 0 |
| `go/internal/web/properties/apartmentnew/i18n.json` | en | 68 | 0 | 0 |
| `go/internal/web/properties/apartmentnew/i18n.json` | vi | 68 | 0 | 0 |
| `go/internal/web/properties/apartmentsmallposts/i18n.json` | cs | 22 | 0 | 0 |
| `go/internal/web/properties/apartmentsmallposts/i18n.json` | en | 22 | 0 | 0 |
| `go/internal/web/properties/apartmentsmallposts/i18n.json` | vi | 22 | 0 | 0 |
| `go/internal/web/properties/apartmentupdate/i18n.json` | cs | 8 | 0 | 0 |
| `go/internal/web/properties/apartmentupdate/i18n.json` | en | 8 | 0 | 0 |
| `go/internal/web/properties/apartmentupdate/i18n.json` | vi | 8 | 0 | 0 |
| `go/internal/web/properties/i18n.json` | cs | 574 | 0 | 0 |
| `go/internal/web/properties/i18n.json` | en | 574 | 0 | 0 |
| `go/internal/web/properties/i18n.json` | vi | 563 | 0 | 0 |
| `go/internal/web/properties/smartlocks/i18n.json` | cs | 15 | 0 | 0 |
| `go/internal/web/properties/smartlocks/i18n.json` | en | 15 | 0 | 0 |
| `go/internal/web/properties/smartlocks/i18n.json` | vi | 15 | 0 | 0 |
| `go/internal/web/settings/i18n.json` | cs | 213 | 0 | 0 |
| `go/internal/web/settings/i18n.json` | en | 213 | 0 | 0 |
| `go/internal/web/settings/i18n.json` | vi | 198 | 0 | 0 |
| `go/internal/web/staydetail/i18n.json` | cs | 163 | 0 | 0 |
| `go/internal/web/staydetail/i18n.json` | en | 163 | 0 | 0 |
| `go/internal/web/staydetail/i18n.json` | vi | 163 | 0 | 0 |
| `go/internal/web/staydetail/stayupdate/i18n.json` | cs | 2 | 0 | 0 |
| `go/internal/web/staydetail/stayupdate/i18n.json` | en | 2 | 0 | 0 |
| `go/internal/web/staydetail/stayupdate/i18n.json` | vi | 2 | 0 | 0 |
| `go/internal/web/stayfees/i18n.json` | cs | 14 | 0 | 0 |
| `go/internal/web/stayfees/i18n.json` | en | 14 | 0 | 0 |
| `go/internal/web/stayfees/i18n.json` | vi | 14 | 0 | 0 |
| `go/internal/web/stays/i18n.json` | cs | 421 | 0 | 0 |
| `go/internal/web/stays/i18n.json` | en | 421 | 0 | 0 |
| `go/internal/web/stays/i18n.json` | vi | 393 | 0 | 0 |
| `go/internal/web/submissions/i18n.json` | cs | 107 | 0 | 0 |
| `go/internal/web/submissions/i18n.json` | en | 107 | 0 | 0 |
| `go/internal/web/submissions/i18n.json` | vi | 107 | 0 | 0 |

Shared host keys with differing literal values

## Appendix C. Mail, scheduled jobs and runtime evidence

## Mail

`App/app/mail.py:45–104` is the Python registry. Below, UNVERIFIED means the builder or handler was located and the listed evidence can be used for a follow-up, with at least one of recipient, language, copy, triggers, deduplication or delivery still open. Existing goldens are listed separately from results of a run.

| Mail kind | Verdict | Python | Go | Existing comparison or note |
|---|---|---|---|---|
| claim | DIFFERENT | App/app/claim.py:342–373, App/app/mail_notify.py:1345–1363,1384 | go/internal/web/guest/party.go:487, go/internal/web/stays/claim_seed.go:172,328–366 | Go sends the raw link as text and HTML, without the localized message or the host’s Reply-To. Both keep the token encrypted in the outbox. No body golden located. |
| claim_resend | DIFFERENT | App/app/claim.py:342–373 | go/internal/web/guest/party.go:487, go/internal/web/stays/claim_seed.go:172,328–366, go/internal/web/stays/claim_ops.go:783–811 | Guest resend still goes through the initial-kind builder. Host resend makes the proper kind and also sends only the link. No body golden located. |
| reminder_guest | UNVERIFIED | App/app/claim.py:961, App/app/mail_notify.py:2250 | go/internal/mailjob/reminders.go:33, go/internal/mailnotify/reminder.go:64 | Existing prior content pass supplied by owner. `mailnotify/mailnotify_test.go:78`. |
| reminder_host | UNVERIFIED | App/app/claim.py:990–1009, App/app/mail_notify.py:2335 | go/internal/mailjob/reminders.go:227, go/internal/mailnotify/reminder.go:146 | `mailnotify/mailnotify_test.go:78`, host/guest cases. |
| completion | UNVERIFIED | App/app/claim.py:864, App/app/mail_notify.py:1750 | go/internal/mailnotify/completion.go:55, go/internal/doorcodes/wire/confirmations.go:78, go/cmd/ubyhost-web/door_codes_wire.go:110 | Prior content pass. Missing form trigger known under 2065/2066. Live door-code job does wire the real completion adapter. |
| completion_update | UNVERIFIED | App/app/fee_update.py:180, App/app/mail_notify.py:2133 | go/internal/mailjob/feeupdate.go:250, go/internal/mailnotify/fee_update.go:24 | Prior content pass, `mailnotify/fee_update_test.go:25` and `mailjob/feeupdate_test.go:189`. |
| guest_details_host | UNVERIFIED legacy | App/app/mail_notify.py:1998,2049, App/app/mail.py:59 | go/internal/mail/outbox_markers.go:268 | Registry/builder retained by Python, send-on-completion intentionally removed in 1630. Go still has send-time marker plumbing for existing queued rows. |
| submission_problem | UNVERIFIED | App/app/mail_notify.py:594,937 | go/internal/mail/submission_problem.go:423 | `mail/submission_problem_test.go:38`. |
| invoice_issued | UNVERIFIED | App/app/routes/invoices.py:991, App/app/mail_notify.py:2192 | go/internal/mail/invoice_issued.go:12 | `mail/invoice_issued_test.go:28`. |
| workspace_deletion | UNVERIFIED | App/app/mail_notify.py:973,1232 | go/internal/mail/auth_link.go:261, go/internal/mail/auth_queue.go:352 | `mail/auth_link_test.go:65,123`. |
| stay_fee_report, stay_fee_blocked | UNVERIFIED | App/app/mail_notify.py:1006,1060,1107,1141 | go/internal/stayfeemail/stay_fee_mail.go:141,197, go/internal/stayfeemail/queue.go:93,143 | `stayfeemail/stay_fee_test.go:79,94`, `stayfeemail/job_test.go:410` requires test DB. |
| cancelled_with_guests | UNVERIFIED | App/app/mail_notify.py:1169 | go/internal/mail/cancelled_with_guests.go:32 | `mail/cancelled_with_guests_test.go:12`. |
| double_booking | UNVERIFIED | App/app/mail.py:67,135 retains kind. No current Python sender located. | go/internal/ical/doublebooking.go:62,135–153, go/internal/ubyport/double_booking_notify.go:87, go/internal/mail/double_booking.go:28 | `mail/double_booking_test.go:8` covers builder behavior. No Python comparison golden located. |
| deadline_at_risk, deadline_digest | UNVERIFIED | App/app/filing_watchdog.py:268,324, App/app/mail_notify.py:2437,2564 | go/internal/calendar/filing_watchdog_run.go:357, go/internal/mail/deadline_at_risk.go:114,197 | `calendar/filing_watchdog_run_test.go:312` digest, `calendar/watch_test.go:174` deadline behavior. |
| filing_stalled, filing_stalled_operator | UNVERIFIED | App/app/mail.py:70–71,140–143 says Go deadlines job owns them. Python scheduler is a stub at App/app/scheduler.py:222. | go/internal/calendar/deadlines_job.go:116, go/internal/mail/filing_stalled.go:43 | `mail/filing_stalled_test.go:8–53` and `calendar/filing_stalled_db_test.go:69–211`. No Python golden located. |
| guest_question | UNVERIFIED | App/app/guest_handoff.py:144,181–182 | go/internal/guesthandoff/notify.go:81, go/internal/mail/guest_question_host.go:27 | `mail/guest_question_host_test.go:14`. |
| lifecycle_no_property, lifecycle_no_calendar, lifecycle_no_guest | SAME for daily gate and language rule. Other details UNVERIFIED. | App/app/lifecycle_mail.py:268,296,314, App/app/mail_notify.py:44,1273 | go/internal/lifecyclemail/run.go:299–308,358, go/internal/lifecyclemail/build.go:214 | Both use English and run after 09:00 Prague only once daily with the feature and mail on. `lifecyclemail/lifecyclemail_test.go:193,291,340`. |
| signup_verify, signup_exists, signup_admin | UNVERIFIED | App/app/mail_notify.py:2843,2873,2898,2937,2961,2974 | go/internal/mail/auth_signup.go:116,138,159, go/internal/signup/register.go:328,429,529 | `signup/signup_test.go:270`. |
| email_changed, passkey_added | UNVERIFIED | App/app/mail_notify.py:2730,2767,2795,2823 | go/internal/mail/auth_link.go:218,236, go/internal/mail/auth_queue.go:249,279 | `mail/auth_link_test.go:65,123`. |
| login_link, account_invite, email_confirm | UNVERIFIED | App/app/mail_notify.py:2657,2698, App/app/routes/admin_accounts.py:742 | go/internal/mail/auth_link.go:173, go/internal/mail/auth_queue.go:206, go/internal/web/auth/login.go:51, go/internal/web/auth/admin_users_post.go:60 | `mail/auth_link_test.go:65,123`. |
| door_code, door_code_notice | UNVERIFIED | App/app/door_codes.py:370–425, App/app/mail_notify.py:1533,1604,1702 | go/internal/doorcodes/issue.go:134,191, go/internal/doorcodes/wire/wire.go:53,149,170, go/internal/mailnotify/door_code.go:84,306,333 | Prior content pass for door code. `mailnotify/door_code_test.go:99` incl. notices. |
| havel_support | UNVERIFIED | App/app/mail_notify.py:3002,3026 | go/internal/web/ai/havel_mail.go:132,195 | `web/ai/havel_cards_test.go:210`. |
| ai_budget | MISSING | App/app/ai.py:307–315, App/app/mail_notify.py:3043,3057–3065 | go/internal/anthropic/ai.go:329–350,408,457 | Operator warning email at 80% budget replaced by a log. Caps still apply. No Go mail golden. |
| billing_invoice, billing_trial, billing_overdue, billing_paid | UNVERIFIED | App/app/mail_notify.py:3069,3107,3185,3137 | go/internal/mail/billing_invoice.go:40, go/internal/mail/billing_trial.go:19, go/internal/mail/billing_overdue.go:21, go/internal/mail/billing_paid.go:17 | `billingjob/run_test.go:129` proves selected behavior and expected content. No full Python byte goldens found for this group. |
| payment_request, site_booking_confirmed, site_booking_refunded, site_booking_host, site_booking_request_host, site_booking_request_guest | UNVERIFIED, excluded as retired | App/app/mail.py:48,52–56 | go/internal/appconfig/payments_hidden.go:20 | Listed for inventory only. |

**Delivery and unsubscribe.** Both have production-only SES configuration and use the outbox for failed sends. Verified by source scan (App/app/mail.py:239,669,743,767,820 and go/internal/mail/outbox_config.go:89, go/internal/mail/outbox_ses.go:194, go/internal/mail/outbox_drain.go:44,114,152). Both attach List-Unsubscribe headers for the three lifecycle kinds (App/app/mail.py:171,635 and go/internal/mail/outbox_ses.go:164,186). Token/rendering parity golden exists at go/internal/web/public/unsub_test.go:291, with Python handler App/app/routes/mail_unsubscribe.py:45,56. Live delivery, mail reply routing for other kinds, token body parity, exact SES HTTP payload, and full content parity remain UNVERIFIED.

**Golden rerun.** The existing `mailnotify` tests matching `Golden|MatchesPython` passed for completion, door codes and notices, fee updates, and guest and host reminders. The audit used unchanged Go source and the original local x/text dependency in a temporary module. The broader offline run for `mail`, `mailnotify`, `lifecyclemail` and `stayfeemail` stopped during dependency resolution because the local cache lacks `github.com/stretchr/testify@v1.3.0`. The database-backed fixtures and live delivery remain UNVERIFIED.

## Background jobs

**SAME for the 15 base schedule entries** per App/app/scheduler.py:86–110,767–830 and go/internal/scheduler/scheduler.go:107–147,174–190. The timezone is Europe/Prague. Both exclude retired Stripe from scheduling. Both queues use one open row per kind, a 60-minute lease, five attempts, and 1/5/15/60-minute retry steps with interval cap (App/app/jobqueue.py:27–31,54–97,110–130 and go/internal/scheduler/scheduler.go:277, go/internal/jobs/queue.go:18–25,49–104).

**MISSING stuck-job alert.** Python periodically raises a background-job failure notification when a due row goes unclaimed (App/app/jobqueue.py:144–187,208–211). Go’s worker raises this notification on terminal handler failure and records successes, with no corresponding unclaimed-row watchdog in its poll loop (go/internal/jobs/queue.go:181–230). The Go Operations page still displays late successes and existing failure alerts (go/internal/web/auth/opspage/data.go:375–399).

| Kind and schedule | Python | Go | Behavior reviewed |
|---|---|---|---|
| billing — 06:00 | App/app/scheduler.py:410 | go/cmd/ubyhost-web/register_job_billing.go:24 | Runner present. Invoice writing, customer emails, reconciliation and retry parity UNVERIFIED. |
| billing_snapshot — 06:15 | App/app/scheduler.py:426 | go/cmd/ubyhost-web/register_jobs.go:46 | Month snapshot write present. Snapshot rows at edge cases UNVERIFIED. |
| deadlines — 30 min | App/app/scheduler.py:222 | go/cmd/ubyhost-web/register_jobs.go:88, go/internal/calendar/deadlines_job.go:116 | Already Go-owned on the branch. Filing heartbeat wired. Rules/row effects assessed in filing section. |
| door_codes — 5 min | App/app/scheduler.py:356 | go/cmd/ubyhost-web/register_job_door_codes.go:33,51, go/cmd/ubyhost-web/door_codes_wire.go:72,110 | Both reconcile stays, reconcile cleaning, then process the cleaner code queue. TTLock payload, cutoff behavior, and retries UNVERIFIED. |
| guide_import — hourly | App/app/scheduler.py:375 | go/cmd/ubyhost-web/register_job_guide_import.go:19, go/internal/guideimport/job.go:99,155,291 | Import queue and pending merges present. Apify and AI calls, successful writes and retry behavior UNVERIFIED. |
| ical — 60 min default | App/app/scheduler.py:176 | go/cmd/ubyhost-web/register_jobs.go:56 | Both launch sync and ping on success. Feed formats and per-feed failure handling UNVERIFIED. |
| mail — 5 min | App/app/scheduler.py:239–273 | go/cmd/ubyhost-web/register_job_mail.go:45–141 | SAME step order and retirement exclusion, continues after failed steps, skips success heartbeat on error. Mail-level differences above. |
| meta_capi — 10 min | App/app/scheduler.py:314 | go/cmd/ubyhost-web/register_jobs.go:81, go/internal/metacapi/send.go:335 | Conversion sender wired. Matching provider request, retry, expiry UNVERIFIED. |
| photo_sweep — 12 h | App/app/scheduler.py:276 | go/cmd/ubyhost-web/register_job_photo_sweep.go:18 | Scheduled file-sweep/backstop. Exact eligibility, cleanup and retry UNVERIFIED. |
| posthog — 15 min | App/app/scheduler.py:335 | go/cmd/ubyhost-web/register_jobs.go:74 | Sync wired. Matching event payload, dedupe, retention effects and error paths UNVERIFIED. |
| push — 1 min | App/app/scheduler.py:394 | go/cmd/ubyhost-web/register_jobs.go:66, go/internal/pushsend/pushsend.go:272 | Sender drains due rows. Per-device retry and outage parity UNVERIFIED. |
| retention — 03:30 | App/app/scheduler.py:483, App/app/retention.py:649–657 | go/cmd/ubyhost-web/register_job_retention.go:25, go/internal/retention/retention.go:54–80 | SAME live gate for supplied production config with autopurge on. Go has an extra nonproduction apply condition. Full deletion/data parity UNVERIFIED. |
| stay_fee_mail — 07:00 | App/app/scheduler.py:465 | go/cmd/ubyhost-web/register_job_stay_fee_mail.go:31 | Monthly sealing/report sender wired. Read-write, fee consistency and retry parity UNVERIFIED. |
| stripe_sweep — 04:15 when enabled | App/app/scheduler.py:803–807 | go/internal/scheduler/scheduler.go:126,138–145, go/cmd/ubyhost-web/register_jobs.go:49 | SAME skipped for retired production payments. Old already-queued Python and Go rechecks are kept; feature internals excluded. |
| submit — 10 min default | App/app/scheduler.py:191 | go/cmd/ubyhost-web/register_filing.go:23–39 | Both ping submit heartbeat on a clean run. Filing results assessed in filing section. |

## Deploy and runtime

- **Conditional critical, job lists.** The Go service exits during startup if `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS` disagree, or when scheduler enabled and a scheduled kind is missing from the queue list. The deploy also refuses to start unless `UBYHOST_SCHEDULER=go`. Python previously covered missing Go consumers. See App/app/jobqueue.py:71–76, App/app/scheduler.py:832–848, go/cmd/ubyhost-web/job_config.go:24–70, go/cmd/ubyhost-web/main.go:196–204, go/internal/scheduler/scheduler.go:154–183, deploy/lightsail/scripts/deploy.sh:19–23. Actual lists and switch values are UNVERIFIED. The production description still lists Python for mail and door codes at docs/context/status.md:12. Plan-required list with payments retired has 14 of the 15 kinds, with optional old Stripe entries subject to matching both lists. docs/context/status.md:6 also calls for autopurge off in week one. Supplied autopurge-on settings would delete immediately.
- **Environment inventory.** Found 93 distinct literal Go environment-key reads and 123 keys sent to the Go slot, before computed/indirect lookup names. Nine missing literal names: `UBYHOST_GO_ADDR`, `UBYHOST_MIGRATIONS_DIR` and `UBYHOST_APP_ROOT` are set in go/Dockerfile:15. `UID` and `SV` are from the end-to-end session utility only. `UBYHOST_REPO_ROOT` is for demo seeds and `UBYHOST_TEST_OCR_VALUES` is a test hook. `UBYPORT_ENV` is a legacy fallback, with `UBYHOST_UBYPORT_ENV` passed through compose. `POSTHOG_APP_URL` is missing from compose; Python consumes it at App/app/config.py:529 and Go uses the default in go/internal/web/billing/admin_page.go:131 absent forwarding. The supplied production inventory includes only the PostHog project key, so a broken custom URL is UNVERIFIED. Go's explicit required startup DB variable `UBYHOST_DATABASE_URL` appears in the supplied inventory and compose at deploy/lightsail/docker-compose.yml:120 (Go requirement at go/cmd/ubyhost-web/main.go:187–191). The complete indirect env inventory, actual values, and removed Python variable effects remain UNVERIFIED.
- **Verified wiring only.** Go slot and launcher at deploy/lightsail/docker-compose.yml:95–110,246,258–263, deploy/lightsail/scripts/deploy.sh:441–489. Caddy proxies both slots and checks /healthz in both modes (deploy/lightsail/caddy/Caddyfile.acme:37–41 and deploy/lightsail/caddy/Caddyfile.cloudflare:87–91). Go exposes /healthz and /metrics at go/cmd/ubyhost-web/main.go:110,279–282. Alloy scrapes both slots as well as cAdvisor and node-exporter (deploy/lightsail/monitoring/config.alloy:53–75). Four heartbeat settings are passed in by Compose and their Go calls are wired (deploy/lightsail/docker-compose.yml:132,180–182, go/cmd/ubyhost-web/register_filing.go:39, go/cmd/ubyhost-web/register_jobs.go:62, go/cmd/ubyhost-web/register_job_mail.go:141, go/internal/calendar/deadlines_job.go:116). Actual scrape results, dashboards, health transitions, and outbound pings remain UNVERIFIED.
- **Backup and capacity.** WAL archive spool and WAL-G shipping service remain in compose (deploy/lightsail/docker-compose.yml:33–43,60–78). The backup script looks for either app slot and retries during a swap (deploy/lightsail/scripts/backup.sh:22–45). No live archive/backup drill was performed. The 00023 new table/index and 00024 CHECK constraint changes were inspected only at App/migrations_pg/00023_apartment_entry_code.sql:4 and App/migrations_pg/00024_guide_import_public_url.sql:3–7. Production-sized migration locks/timing, actual WAL output, backups and two-slot peak memory are UNVERIFIED. Each Go slot inherits `UBYHOST_GO_MEM`, default 128 MB, at deploy/lightsail/docker-compose.yml:246,258–263.

## Appendix D. Runtime variable inventory

## Runtime variable inventory (static)

This inventory matches literal, quoted environment keys near a configuration read in Go and Python, plus direct Go Compose environment mappings. Dynamic names need manual inspection. Blank Compose entries depend on the host environment. Source inspection gives no evidence of actual secret values or server configuration.

| Setting | Go reference | Python reference | Go Compose mapping |
|---|---|---|---|
| `POSTHOG_APP_URL` | go/internal/web/billing/admin_page.go:131 | App/app/config.py:529 | — |
| `POSTHOG_ASSETS_HOST` | go/internal/posthog/sync.go:66, go/internal/web/billing/admin_page.go:128 | App/app/config.py:527 | deploy/lightsail/docker-compose.yml:229 |
| `POSTHOG_HOST` | go/internal/posthog/sync.go:65, go/internal/web/billing/admin_page.go:127 | App/app/config.py:525 | deploy/lightsail/docker-compose.yml:230 |
| `POSTHOG_PROJECT_API_KEY` | go/internal/posthog/sync.go:62, go/internal/web/billing/admin_page.go:126 | App/app/config.py:524 | deploy/lightsail/docker-compose.yml:231 |
| `TURNSTILE_HOSTNAMES` | go/internal/turnstile/turnstile.go:83 | App/app/config.py:515 | deploy/lightsail/docker-compose.yml:232 |
| `TURNSTILE_SECRET` | go/internal/turnstile/turnstile.go:91 | App/app/config.py:512 | deploy/lightsail/docker-compose.yml:233 |
| `TURNSTILE_SITE_KEY` | go/internal/turnstile/turnstile.go:78 | — | deploy/lightsail/docker-compose.yml:234 |
| `UBYHOST_ACCESS_LOG` | — | App/app/config.py:443 | — |
| `UBYHOST_ADMIN_EMAIL` | go/internal/web/auth/login.go:598 | App/app/config.py:476 | deploy/lightsail/docker-compose.yml:112 |
| `UBYHOST_ADMIN_USERNAME` | go/internal/web/auth/login.go:531 | App/app/config.py:475 | deploy/lightsail/docker-compose.yml:113 |
| `UBYHOST_ADS_CONVERSION_NAME` | go/internal/signup/signup.go:141 | App/app/config.py:627 | deploy/lightsail/docker-compose.yml:114 |
| `UBYHOST_AI_FEATURES` | go/internal/anthropic/ai.go:92, go/internal/hostweb/layout/shelldata.go:106 | App/app/config.py:567 | deploy/lightsail/docker-compose.yml:150 |
| `UBYHOST_AI_KEY_DAILY_USD_HAVEL` | — | — | deploy/lightsail/docker-compose.yml:151 |
| `UBYHOST_AI_KEY_DAILY_USD_LEON` | — | — | deploy/lightsail/docker-compose.yml:152 |
| `UBYHOST_AI_MAX_INPUT_TOKENS` | — | App/app/config.py:595 | deploy/lightsail/docker-compose.yml:115 |
| `UBYHOST_AI_MAX_TOKENS` | — | App/app/config.py:590 | deploy/lightsail/docker-compose.yml:116 |
| `UBYHOST_AI_MODEL` | go/internal/anthropic/ai.go:102 | App/app/config.py:576 | deploy/lightsail/docker-compose.yml:117 |
| `UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT` | — | — | deploy/lightsail/docker-compose.yml:153 |
| `UBYHOST_AI_MONTHLY_USD_HAVEL` | — | — | deploy/lightsail/docker-compose.yml:154 |
| `UBYHOST_AI_MONTHLY_USD_LEON` | — | — | deploy/lightsail/docker-compose.yml:155 |
| `UBYHOST_AI_PRICE_CACHE_READ` | — | App/app/config.py:603 | deploy/lightsail/docker-compose.yml:156 |
| `UBYHOST_AI_PRICE_CACHE_WRITE` | — | App/app/config.py:604 | deploy/lightsail/docker-compose.yml:157 |
| `UBYHOST_AI_PRICE_INPUT` | — | App/app/config.py:601 | deploy/lightsail/docker-compose.yml:158 |
| `UBYHOST_AI_PRICE_OUTPUT` | — | App/app/config.py:602 | deploy/lightsail/docker-compose.yml:159 |
| `UBYHOST_AI_PROVIDER` | go/internal/anthropic/ai.go:76, go/internal/hostweb/layout/shelldata.go:110 | App/app/config.py:579 | deploy/lightsail/docker-compose.yml:160 |
| `UBYHOST_AI_TEST_EMAILS` | go/internal/hostweb/layout/shelldata.go:116, go/internal/palette/palette.go:315 | App/app/config.py:573 | deploy/lightsail/docker-compose.yml:161 |
| `UBYHOST_ALERT_RETENTION_DAYS` | go/internal/retention/retention.go:88 | App/app/config.py:459 | deploy/lightsail/docker-compose.yml:118 |
| `UBYHOST_ALLOW_PROD_MOCK` | — | App/app/env_guard.py:125 | — |
| `UBYHOST_ANTHROPIC_API_KEY` | go/internal/anthropic/ai.go:100, go/internal/palette/palette.go:307 | App/app/config.py:575 | deploy/lightsail/docker-compose.yml:162 |
| `UBYHOST_APIFY_MONTHLY_RUNS` | go/internal/guideimport/job.go:67 | App/app/config.py:406 | deploy/lightsail/docker-compose.yml:163 |
| `UBYHOST_APIFY_TIMEOUT` | go/internal/guideimport/job.go:67 | App/app/config.py:407 | deploy/lightsail/docker-compose.yml:164 |
| `UBYHOST_APIFY_TOKEN` | go/internal/guideimport/job.go:66, go/internal/web/ai/leon_facts.go:308 | App/app/config.py:405 | deploy/lightsail/docker-compose.yml:165 |
| `UBYHOST_APP_BASE_URL` | go/cmd/ubyhost-web/door_codes_wire.go:153, go/internal/billingjob/send.go:101 | App/app/config.py:422, App/app/env_guard.py:165 | deploy/lightsail/docker-compose.yml:166 |
| `UBYHOST_APP_DOMAIN` | — | App/app/env_guard.py:166, App/app/site_urls.py:80 | — |
| `UBYHOST_APP_ROOT` | go/internal/web/public/utility.go:288, go/internal/web/staticfiles/static.go:23 | — | — |
| `UBYHOST_AUDIT_RETENTION_DAYS` | go/internal/retention/retention.go:85 | App/app/config.py:458 | deploy/lightsail/docker-compose.yml:119 |
| `UBYHOST_AWS_ACCESS_KEY_ID` | go/internal/mail/outbox_config.go:65 | App/app/config.py:542 | deploy/lightsail/docker-compose.yml:167 |
| `UBYHOST_AWS_SECRET_ACCESS_KEY` | go/internal/mail/outbox_config.go:66 | App/app/config.py:543 | deploy/lightsail/docker-compose.yml:168 |
| `UBYHOST_BILLING_BANK_ACCOUNT` | go/internal/billingjob/invoicer.go:296 | App/app/config.py:557 | deploy/lightsail/docker-compose.yml:169 |
| `UBYHOST_BILLING_ENABLED` | go/internal/billingjob/run.go:70, go/internal/doorcodes/wire/services.go:55 | App/app/config.py:555 | deploy/lightsail/docker-compose.yml:170 |
| `UBYHOST_BILLING_IBAN` | go/internal/billingjob/invoicer.go:295 | App/app/config.py:558 | deploy/lightsail/docker-compose.yml:171 |
| `UBYHOST_BILLING_VAT_STATUS` | go/internal/billingjob/invoicer.go:288 | App/app/config.py:560 | deploy/lightsail/docker-compose.yml:172 |
| `UBYHOST_BOOTSTRAP_ADMIN` | — | App/app/config.py:474 | — |
| `UBYHOST_DATABASE_URL` | go/cmd/ubyhost-web/main.go:188, go/cmd/ubyhost-web/register_schema.go:73 | App/app/config.py:93 | deploy/lightsail/docker-compose.yml:120 |
| `UBYHOST_DATA_DIR` | go/cmd/ubyhost-web/register_job_photo_sweep.go:21, go/cmd/ubyhost-web/register_ruian_import.go:36 | App/app/config.py:23 | deploy/lightsail/docker-compose.yml:149 |
| `UBYHOST_DATA_KEYS` | go/internal/secure/datakeys.go:18 | App/app/config.py:279 | deploy/lightsail/docker-compose.yml:173 |
| `UBYHOST_DATA_KEY_LEGACY` | go/internal/secure/datakeys.go:23 | App/app/config.py:291 | deploy/lightsail/docker-compose.yml:174 |
| `UBYHOST_DB` | — | App/app/config.py:92 | — |
| `UBYHOST_DEMO_ENABLED` | go/internal/web/stays/handlers.go:172, go/internal/web/stays/handlers.go:172 | — | deploy/lightsail/docker-compose.yml:121 |
| `UBYHOST_DEPLOYMENT` | go/cmd/ubyhost-web/door_codes_wire.go:163, go/internal/envguard/staging_no_login.go:10 | App/app/config.py:299, App/app/site_urls.py:81 | deploy/lightsail/docker-compose.yml:175 |
| `UBYHOST_DOMAIN` | — | App/app/env_guard.py:88 | — |
| `UBYHOST_DOOR_CODES` | go/cmd/ubyhost-web/cleaning_queue_kick.go:39, go/cmd/ubyhost-web/door_codes_wire.go:140 | App/app/config.py:335 | deploy/lightsail/docker-compose.yml:176 |
| `UBYHOST_DOOR_CODES_LIVE` | go/cmd/ubyhost-web/door_codes_wire.go:141, go/internal/web/auth/opspage/data.go:553 | App/app/config.py:416 | deploy/lightsail/docker-compose.yml:177 |
| `UBYHOST_DPA_VERSION` | go/internal/signup/register.go:397, go/internal/web/public/public.go:148 | App/app/config.py:660 | deploy/lightsail/docker-compose.yml:178 |
| `UBYHOST_ENABLE_SCHEDULER` | go/cmd/ubyhost-web/register_scheduler.go:34, go/cmd/ubyhost-web/register_scheduler.go:54 | App/app/config.py:430 | deploy/lightsail/docker-compose.yml:179 |
| `UBYHOST_GO_ACCESS_PAGE` | go/internal/web/ai/guide_index.go:321, go/internal/web/ai/guide_index.go:360 | — | deploy/lightsail/docker-compose.yml:122 |
| `UBYHOST_GO_ADDR` | go/cmd/ubyhost-web/main.go:205 | — | — |
| `UBYHOST_GO_JOB_KINDS` | go/cmd/ubyhost-web/cleaning_queue_kick.go:42, go/cmd/ubyhost-web/main.go:196 | App/app/config.py:433 | deploy/lightsail/docker-compose.yml:123 |
| `UBYHOST_GO_RETENTION_APPLY` | go/internal/retention/retention.go:74 | — | deploy/lightsail/docker-compose.yml:124 |
| `UBYHOST_GUEST_LANGS` | go/internal/mailjob/reminders.go:49 | App/app/i18n.py:40 | deploy/lightsail/docker-compose.yml:125 |
| `UBYHOST_GUEST_NOTICE_VERSION` | go/internal/web/guest/form_pages_fill.go:16, go/internal/web/guest/shared.go:38 | App/app/config.py:675 | deploy/lightsail/docker-compose.yml:126 |
| `UBYHOST_GUEST_PIN` | go/internal/web/guest/pick_data.go:201, go/internal/web/settings/data.go:407 | App/app/config.py:468 | deploy/lightsail/docker-compose.yml:127 |
| `UBYHOST_GUIDE_PHOTOS_DIR` | go/internal/web/guest/guide_photo.go:43 | — | deploy/lightsail/docker-compose.yml:128 |
| `UBYHOST_HAVEL_MONTHLY` | go/internal/hostweb/layout/shelldata.go:177, go/internal/web/ai/havel_store.go:185 | App/app/config.py:625 | deploy/lightsail/docker-compose.yml:129 |
| `UBYHOST_HAVEL_WEEKLY` | go/internal/hostweb/layout/shelldata.go:175, go/internal/web/ai/havel_store.go:184 | App/app/config.py:624 | deploy/lightsail/docker-compose.yml:130 |
| `UBYHOST_HEADCOUNT_LEAD_LIVE` | go/internal/web/guest/party.go:71, go/internal/web/stays/edit_posts.go:233 | App/app/config.py:417 | deploy/lightsail/docker-compose.yml:131 |
| `UBYHOST_HEARTBEAT_FILING_URL` | go/internal/calendar/filing_watchdog.go:296 | App/app/config.py:332 | deploy/lightsail/docker-compose.yml:180 |
| `UBYHOST_HEARTBEAT_ICAL_URL` | go/cmd/ubyhost-web/register_jobs.go:62 | App/app/config.py:323 | deploy/lightsail/docker-compose.yml:181 |
| `UBYHOST_HEARTBEAT_MAIL_URL` | go/cmd/ubyhost-web/register_job_mail.go:141 | App/app/config.py:324 | deploy/lightsail/docker-compose.yml:132 |
| `UBYHOST_HEARTBEAT_URL` | go/cmd/ubyhost-web/register_filing.go:39 | App/app/config.py:322 | deploy/lightsail/docker-compose.yml:182 |
| `UBYHOST_ICAL_ALLOW_PRIVATE` | go/internal/ical/feedurl.go:154 | App/app/config.py:678 | deploy/lightsail/docker-compose.yml:183 |
| `UBYHOST_ICAL_OPEN_SYNC_MINUTES` | — | App/app/config.py:317 | — |
| `UBYHOST_ICAL_POLL_MINUTES` | go/internal/scheduler/scheduler.go:108, go/internal/web/auth/opspage/data.go:141 | App/app/config.py:315 | deploy/lightsail/docker-compose.yml:184 |
| `UBYHOST_IMPERSONATION_MAX_HOURS` | go/internal/hostweb/layout/layout.go:258, go/internal/session/session.go:264 | App/app/auth.py:45 | deploy/lightsail/docker-compose.yml:185 |
| `UBYHOST_JOB_QUEUE_KINDS` | go/cmd/ubyhost-web/job_config.go:30, go/internal/scheduler/scheduler.go:179 | App/app/config.py:431 | deploy/lightsail/docker-compose.yml:186 |
| `UBYHOST_LEGAL_EFFECTIVE_DATE` | go/internal/web/public/public.go:149 | App/app/config.py:670 | deploy/lightsail/docker-compose.yml:133 |
| `UBYHOST_LEON_QR_MAX` | — | — | deploy/lightsail/docker-compose.yml:135 |
| `UBYHOST_LEON_STAY_MAX` | — | — | deploy/lightsail/docker-compose.yml:136 |
| `UBYHOST_LIFECYCLE_MAIL` | go/internal/lifecyclemail/config.go:54 | App/app/config.py:453 | deploy/lightsail/docker-compose.yml:134 |
| `UBYHOST_MAIL_BACKEND` | go/internal/billingjob/send.go:83, go/internal/calendar/filing_watchdog_run.go:52 | App/app/config.py:539, App/app/env_guard.py:194 | deploy/lightsail/docker-compose.yml:187 |
| `UBYHOST_MAIL_ENABLED` | go/internal/web/guest/party.go:76 | — | deploy/lightsail/docker-compose.yml:137 |
| `UBYHOST_MAIL_FROM` | go/internal/mail/outbox_config.go:63 | App/app/config.py:540 | deploy/lightsail/docker-compose.yml:188 |
| `UBYHOST_MAX_BATCH` | go/internal/ubyport/sweep.go:199 | App/app/config.py:311 | deploy/lightsail/docker-compose.yml:189 |
| `UBYHOST_META_ACCESS_TOKEN` | go/internal/metacapi/send.go:88, go/internal/signup/signup.go:147 | App/app/config.py:636 | deploy/lightsail/docker-compose.yml:190 |
| `UBYHOST_META_DATASET_ID` | go/internal/metacapi/send.go:87, go/internal/signup/signup.go:146 | App/app/config.py:635 | deploy/lightsail/docker-compose.yml:191 |
| `UBYHOST_META_GRAPH_VERSION` | go/internal/metacapi/send.go:83 | App/app/config.py:642 | deploy/lightsail/docker-compose.yml:192 |
| `UBYHOST_META_TEST_EVENT_CODE` | go/internal/metacapi/send.go:89 | App/app/config.py:639 | deploy/lightsail/docker-compose.yml:193 |
| `UBYHOST_MIGRATIONS_DIR` | go/cmd/ubyhost-web/main.go:206, go/cmd/ubyhost-web/register_schema.go:74 | — | — |
| `UBYHOST_MISTRAL_API_KEY` | go/internal/anthropic/ai.go:101, go/internal/palette/palette.go:309 | App/app/config.py:582 | deploy/lightsail/docker-compose.yml:194 |
| `UBYHOST_MISTRAL_MODEL` | go/internal/anthropic/ai.go:103 | App/app/config.py:583 | deploy/lightsail/docker-compose.yml:195 |
| `UBYHOST_MOCK_URL` | go/internal/ubyport/sweep.go:89 | App/app/config.py:304 | deploy/lightsail/docker-compose.yml:196 |
| `UBYHOST_OPERATOR_ADDRESS` | go/internal/billingjob/invoicer.go:293, go/internal/lifecyclemail/config.go:60 | App/app/config.py:501 | deploy/lightsail/docker-compose.yml:197 |
| `UBYHOST_OPERATOR_DIC` | go/internal/billingjob/invoicer.go:294, go/internal/web/public/public.go:137 | App/app/config.py:500 | deploy/lightsail/docker-compose.yml:198 |
| `UBYHOST_OPERATOR_EMAIL` | go/internal/billingjob/invoicer.go:302, go/internal/calendar/filing_stalled.go:293 | App/app/config.py:502 | deploy/lightsail/docker-compose.yml:199 |
| `UBYHOST_OPERATOR_ICO` | go/internal/billingjob/invoicer.go:294, go/internal/lifecyclemail/config.go:59 | App/app/config.py:499 | deploy/lightsail/docker-compose.yml:200 |
| `UBYHOST_OPERATOR_NAME` | go/internal/billingjob/invoicer.go:293, go/internal/lifecyclemail/config.go:58 | App/app/config.py:498 | deploy/lightsail/docker-compose.yml:201 |
| `UBYHOST_OPERATOR_REGISTRY_URL` | go/internal/web/public/public.go:140 | App/app/config.py:505 | deploy/lightsail/docker-compose.yml:138 |
| `UBYHOST_PAYMENTS_HIDDEN` | go/internal/appconfig/payments_hidden.go:24, go/internal/web/staydetail/tpl.go:270 | — | deploy/lightsail/docker-compose.yml:202 |
| `UBYHOST_PAYMENTS_RETIRED` | go/internal/appconfig/payments_hidden.go:10 | App/app/config.py:352 | deploy/lightsail/docker-compose.yml:203 |
| `UBYHOST_PRIVACY_VERSION` | go/internal/signup/register.go:396, go/internal/web/public/public.go:147 | App/app/config.py:654 | deploy/lightsail/docker-compose.yml:204 |
| `UBYHOST_PUBLIC_BASE_URL` | go/cmd/ubyhost-web/door_codes_wire.go:149, go/internal/billingjob/send.go:92 | App/app/config.py:420, App/app/site_urls.py:78 | deploy/lightsail/docker-compose.yml:205 |
| `UBYHOST_RATE_LIMIT_RETENTION_HOURS` | go/internal/retention/retention.go:91 | App/app/config.py:460 | deploy/lightsail/docker-compose.yml:139 |
| `UBYHOST_REPO_ROOT` | go/internal/web/onboarding/demo_seed_mock.go:56 | — | — |
| `UBYHOST_RESTRICTED_BLOCKS_FILING` | — | App/app/config.py:464 | — |
| `UBYHOST_RETENTION_AUTOPURGE` | go/internal/retention/retention.go:73 | App/app/config.py:447 | deploy/lightsail/docker-compose.yml:140 |
| `UBYHOST_RETENTION_NOTICE_DAYS` | go/internal/retention/retention.go:94, go/internal/web/settings/data.go:187 | App/app/config.py:455 | deploy/lightsail/docker-compose.yml:141 |
| `UBYHOST_ROLE` | — | App/app/config.py:440 | — |
| `UBYHOST_RUIAN_ENABLED` | go/internal/ruian/config.go:7 | App/app/ruian.py:46 | deploy/lightsail/docker-compose.yml:206 |
| `UBYHOST_RUIAN_IMPORT` | go/cmd/ubyhost-web/register_ruian_import.go:28 | — | deploy/lightsail/docker-compose.yml:207 |
| `UBYHOST_RUIAN_URL` | go/internal/ruian/suggest_live.go:58 | App/app/ruian.py:26 | deploy/lightsail/docker-compose.yml:142 |
| `UBYHOST_SCHEDULER` | go/internal/scheduler/scheduler.go:65 | App/app/scheduler.py:551 | deploy/lightsail/docker-compose.yml:208 |
| `UBYHOST_SECRET` | go/internal/web/stays/guest_privacy.go:368 | — | deploy/lightsail/docker-compose.yml:143 |
| `UBYHOST_SECRET_KEY` | go/internal/secure/datakeys.go:67 | App/app/config.py:211, App/app/config.py:262 | deploy/lightsail/docker-compose.yml:209 |
| `UBYHOST_SECURE_COOKIES` | go/internal/web/guest/leon_questions.go:893 | — | deploy/lightsail/docker-compose.yml:144 |
| `UBYHOST_SES_REGION` | go/internal/mail/outbox_config.go:64 | App/app/config.py:541 | deploy/lightsail/docker-compose.yml:210 |
| `UBYHOST_SIGNUP_ENABLED` | go/internal/signup/signup.go:108, go/internal/web/billing/admin_page.go:135 | App/app/config.py:549 | deploy/lightsail/docker-compose.yml:211 |
| `UBYHOST_SIGNUP_NOTIFY_EMAIL` | go/internal/signup/signup.go:133 | App/app/config.py:551 | deploy/lightsail/docker-compose.yml:212 |
| `UBYHOST_SMTP_HOST` | — | — | deploy/lightsail/docker-compose.yml:145 |
| `UBYHOST_SOAP_WSA_HEADER` | go/internal/ubyport/client.go:240 | App/app/ubyport/client.py:30 | deploy/lightsail/docker-compose.yml:214 |
| `UBYHOST_STAGING_LOGIN_PASSWORD` | go/internal/web/auth/login.go:553 | App/app/auth.py:805, App/app/config.py:479 | deploy/lightsail/docker-compose.yml:146 |
| `UBYHOST_STAGING_NO_LOGIN` | go/cmd/ubyhost-web/door_codes_wire.go:166, go/internal/envguard/staging_no_login.go:26 | App/app/config.py:490, App/app/env_guard.py:116 | deploy/lightsail/docker-compose.yml:213 |
| `UBYHOST_STAY_FEE_GUEST_PAY` | go/cmd/ubyhost-web/door_codes_wire.go:93, go/internal/mailjob/feeupdate.go:282 | App/app/config.py:401 | deploy/lightsail/docker-compose.yml:215 |
| `UBYHOST_STRIPE_MODE` | go/internal/payments/connect.go:175, go/internal/payments/onboarder.go:76 | App/app/config.py:343 | deploy/lightsail/docker-compose.yml:147 |
| `UBYHOST_STRIPE_MONTHLY_API_CALLS` | go/internal/payments/onboarder.go:117 | App/app/config.py:346 | deploy/lightsail/docker-compose.yml:216 |
| `UBYHOST_STRIPE_SECRET_KEY` | go/internal/payments/onboarder.go:105 | App/app/config.py:344 | deploy/lightsail/docker-compose.yml:217 |
| `UBYHOST_STRIPE_WEBHOOK_SECRET` | go/internal/payments/webhook.go:93 | App/app/config.py:345 | deploy/lightsail/docker-compose.yml:148 |
| `UBYHOST_SUBMIT_SWEEP_MINUTES` | go/internal/calendar/filing_watchdog.go:125, go/internal/scheduler/scheduler.go:112 | App/app/config.py:318 | deploy/lightsail/docker-compose.yml:218 |
| `UBYHOST_TERMS_VERSION` | go/internal/signup/register.go:395, go/internal/web/public/public.go:146 | App/app/config.py:535 | deploy/lightsail/docker-compose.yml:219 |
| `UBYHOST_TEST_OCR_VALUES` | go/internal/web/guest/draft_scan.go:427 | — | — |
| `UBYHOST_TRUSTED_PROXY_CIDRS` | go/internal/clientip/clientip.go:31 | App/app/config.py:691 | deploy/lightsail/docker-compose.yml:220 |
| `UBYHOST_TTLOCK_API_BASE` | go/internal/ttlock/client.go:229 | App/app/config.py:336 | deploy/lightsail/docker-compose.yml:221 |
| `UBYHOST_TTLOCK_CLIENT_ID` | go/internal/palette/palette.go:297, go/internal/ttlock/client.go:230 | App/app/config.py:337 | deploy/lightsail/docker-compose.yml:222 |
| `UBYHOST_TTLOCK_CLIENT_SECRET` | go/internal/palette/palette.go:298, go/internal/ttlock/client.go:231 | App/app/config.py:338 | deploy/lightsail/docker-compose.yml:223 |
| `UBYHOST_TTLOCK_MONTHLY_CALLS` | go/internal/ttlock/client.go:237, go/internal/web/auth/opspage/data.go:552 | App/app/config.py:339 | deploy/lightsail/docker-compose.yml:224 |
| `UBYHOST_UBYPORT_DOMAIN` | go/internal/ubyport/sweep.go:159 | App/app/config.py:308 | deploy/lightsail/docker-compose.yml:225 |
| `UBYHOST_UBYPORT_ENV` | go/internal/envguard/staging_no_login.go:18, go/internal/hostweb/layout/layout.go:615 | App/app/config.py:296 | deploy/lightsail/docker-compose.yml:226 |
| `UBYHOST_UBYPORT_TIMEOUT` | go/internal/ubyport/sweep.go:162 | App/app/config.py:313 | deploy/lightsail/docker-compose.yml:227 |
| `UBYHOST_WEB_PUSH` | go/internal/pushsend/pushsend.go:102, go/internal/pushweb/pushweb.go:265 | App/app/config.py:411 | deploy/lightsail/docker-compose.yml:228 |

