# Records of processing activities, Art. 30 GDPR [Záznamy o činnostech zpracování, čl. 30 GDPR]

Internal document. Not published. Show it to the ÚOOÚ on request (Art. 30(4)).
Reasoned drafting, not attorney advice. Facts are taken from the code at commit `8691757` (WP21) of the repository and from `04_legal_positions.md`.
Replaces `docs/privacy/ROPA.md` once the owner approves it (that file is an earlier, shorter version).

Last reviewed: 4 October 2026. Review again when a feature, subprocessor or retention period changes, and at least once a year.

## Identification [Identifikace]

| Item | Value |
|---|---|
| Controller and processor [Správce a zpracovatel] | [OWNER TO FILL: name], IČO [OWNER TO FILL], [OWNER TO FILL: address], self-employed person (OSVČ). Read by the app from `UBYHOST_OPERATOR_NAME`, `UBYHOST_OPERATOR_ICO`, `UBYHOST_OPERATOR_ADDRESS`. |
| Contact [Kontakt] | support@ubyhost.com (`UBYHOST_OPERATOR_EMAIL` default) |
| Data protection officer [Pověřenec] | None appointed. Position: not required under Art. 37(1), because the core activity is a software service, not large-scale regular and systematic monitoring and not large-scale special-category data. [OWNER TO CONFIRM] |
| EU representative [Zástupce v EU] | Not applicable (established in the Czech Republic) |

## Shared security measures [Společná bezpečnostní opatření]

Every row below refers to these codes in its "Security" column. Detail: `docs/SECURITY.md`, `docs/privacy/TOMS.md`.

| Code | Measure | Where in code or config |
|---|---|---|
| S1 | HTTPS only, HSTS on `ubyhost.com`, secure cookies in production | `security.py`, Cloudflare zone |
| S2 | Host login by single-use e-mail link (token stored only as SHA-256 hash, 1 day after expiry); optional TOTP 2FA and passkeys (public key only, biometric data never leaves the device); recovery codes stored hashed; session versioning; host sessions up to 400 days until logout | `auth.py` |
| S3 | Login and guest PIN rate limits; Cloudflare Turnstile on host login, on guest claim/resend, and on the guest PIN after 3 failures | `rate_limit.py`, `turnstile.py`, `routes/guest.py` |
| S4 | Guest access by 100-bit link token plus 6-digit PIN; PIN authorisation lasts 7 days; claim secret stored hashed | `auth.py`, `claim.py`, `routes/guest.py` |
| S5 | Field encryption at rest (MultiFernet, `UBYHOST_DATA_KEYS`, separate from the session secret): travel document and visa numbers, birth date, street and town of residence, signatures, UbyPort web-service passwords, TOTP secrets, UbyPort request envelope, queued claim secrets; ID files encrypted on disk | `db.py` (`ENCRYPTED_GUEST_COLUMNS`), `passport_photos.py` |
| S6 | Tenant isolation: every host query joins on `owner_user_id` | `access.py` |
| S7 | Admin support access: document and visa numbers masked, signatures, photos and identity exports held back unless the admin reveals one guest with a logged reason | `access.py` (`identity_visible`, `mask_identifier`), `routes/admin.py` (`reveal-identity`) |
| S8 | Audit log of security events and reads: exports, ID photo views, identity reveals, impersonation with the real actor | `db.audit`, BE-6 |
| S9 | Backups: nightly `age`-encrypted snapshot, private key offline, 30-day retention; Litestream continuous replica to a private S3 bucket in eu-central-1 (Block Public Access, SSE-S3, versioning, dedicated IAM user, 7-day window, non-current versions deleted after 30 days). The replica does not contain the data keys or ID photos | `deploy/lightsail/litestream.yml`, `deploy/lightsail/README.md` |
| S10 | Logs carry route templates only (no tokens, no query strings); uvicorn access log off; Docker log rotation 5 x 10 MB | OPS-3, `docker-compose.yml` |
| S11 | SQLite `secure_delete`, data directory and database file mode 0600 | `db.connect`, deploy scripts |
| S12 | Incident register at `/admin/incidents` | `incidents.py` |

## Part A: UbyHost as controller, Art. 30(1) [Část A: UbyHost jako správce, čl. 30 odst. 1]

| # | Activity [Činnost] | Purpose and legal basis [Účel a právní základ] | Data subjects and data [Subjekty a údaje] | Recipients [Příjemci] | Transfers outside EEA [Předání mimo EHP] | Retention [Doba uložení] | Security |
|---|---|---|---|---|---|---|---|
| A1 | Host accounts, login and 2FA | Provide the contracted service. Art. 6(1)(b) | Hosts and their staff users: username, display name, login e-mail address, login link token hashes (`login_token`, deleted 1 day after expiry), TOTP secret (encrypted), recovery-code hashes, passkey public keys/names/dates/counters (`passkey`), WebAuthn challenge hashes (`webauthn_challenge`, deleted 1 day after expiry), last login, session version | AWS (hosting, SES for account e-mail) | None (eu-central-1) | While the account is active. When an admin schedules deletion, the account is disabled and the whole workspace is deleted 30 days later (`WORKSPACE_DELETION_DAYS = 30`). Unverified self sign-ups are deleted after 7 days (`signup.UNVERIFIED_TTL_DAYS`). | S1, S2, S3, S5, S6, S8, S9 |
| A2 | Self sign-up and verification | Create the account requested by the host. Art. 6(1)(b) | Prospective hosts: e-mail, name, sign-up time, verification token state | AWS SES | None | Unverified: 7 days. Verified: becomes A1 | S1, S3 (Turnstile), S9 |
| A3 | Acceptance of terms, DPA and privacy notice | Prove what the host accepted. Art. 6(1)(c) with Art. 5(2), 28(9) | Hosts: document, version, time, method, IP address, user agent (`legal_acceptance`) | None | None | Life of the account; deleted with the workspace. For long-inactive accounts the acceptance step uses `UBYHOST_AUDIT_RETENTION_DAYS` (1095 days) after last login. [OWNER TO DECIDE: keep 3 years after account deletion as proof, as `04_legal_positions.md` section 4 suggests; the code currently deletes it with the workspace] | S5, S8, S9 |
| A4 | Support and operator e-mail | Answer requests, give instructions under the DPA. Art. 6(1)(b) and (f) | Hosts, occasionally guests who write in: e-mail address, message content | Mailbox provider [OWNER TO FILL: provider of support@ubyhost.com] | [OWNER TO FILL] | [OWNER TO FILL: proposed 3 years after the last message] | Provider 2FA [OWNER TO CONFIRM] |
| A5 | Security logs, alerts, rate limits, incident register | Secure the service and investigate incidents. Art. 6(1)(f); Art. 33(5) for the register | Hosts, guests, visitors: IP address (in rate-limit rows), actor username, action, time; incident descriptions | None | None | Audit 3 years (`UBYHOST_AUDIT_RETENTION_DAYS=1095`); resolved alerts 12 months; rate-limit events 24 hours; container logs by rotation; incident records [OWNER TO DECIDE: proposed 5 years after closure] | S6, S8, S10, S12 |
| A6 | Onboarding and lifecycle e-mails (max. 3) | Help new customers finish setup. Art. 6(1)(f); § 7(3) zákon 480/2004 Sb. | Hosts: e-mail, setup state, opt-out flag and time, sends log (`lifecycle_mail_sent`) | AWS SES | None | Send log: life of the account. Opt-out: as long as such e-mails are sent | S1, S9 |
| A7 | Website statistics on public marketing pages (Umami Cloud) | Measure page use. Art. 6(1)(f); exemption § 89(3) zákon 127/2005 Sb. per `04_legal_positions.md` section 1 | Visitors: page, referrer, browser, device type, country, short-lived visit hash. No cookies. Only loaded when `UMAMI_WEBSITE_ID` is set | Umami Software, Inc. (processor) | Umami Cloud EU region. US company. [UNVERIFIED: Umami DPA content, SCCs] | Umami Cloud default retention [UNVERIFIED] | Tracker limited to public pages, `data-do-not-track`, `data-exclude-search` |
| A8 | Google Ads click measurement (gclid, gbraid, wbraid) | Measure campaigns. Art. 6(1)(a) consent; § 89(3) zákon 127/2005 Sb. | Hosts who ticked the box: click ID, click time, consent time and text version, upload time, `signup_source`, `utm_*` | Google Ireland Ltd. (independent controller), via manual CSV upload | Google's own transfers under its terms [UNVERIFIED] | Click IDs deleted 90 days after the click or 30 days after upload, whichever is first, and at once on withdrawal (`signup.ID_RETENTION_DAYS`). Consent record: with the account | S5 not applied (IDs are short-lived), S8, S9 |
| A9 | Meta Conversions API (fbclid to `fbc`) | Measure Facebook and Instagram campaigns. Art. 6(1)(a) consent; joint control with Meta for collection and sending (Art. 26) | Hosts who ticked the Meta box: `fbc`, browser user agent, click time, consent text version, event ID, send state | Meta Platforms Ireland Ltd. (joint controller, then independent controller) | Meta's onward transfers [UNVERIFIED: Meta European Data Transfer Addendum not read] | `fbc` and user agent deleted 7 days after sending, at once after failure or withdrawal, at the latest 90 days after the click | S1, S8 |
| A10 | Cookies needed to run the site | Language and CSRF protection. Strictly necessary, § 89(3) | Visitors and hosts: `ubyhost_lang`, `ubyhost_csrf`, session cookie | Cloudflare (edge) | Cloudflare global network, DPF and SCCs | Language 1 year; CSRF and session as in S2 | S1 |
| A11 | Bot protection (Cloudflare Turnstile, Managed Challenge) | Protect login, PIN and claim forms. Art. 6(1)(f) | Visitors, hosts, guests: IP address, browser signals | Cloudflare, Inc. | Yes, US. EU-US DPF and SCCs (Cloudflare DPA) | Cloudflare's own retention [UNVERIFIED] | S3 |
| A12 | UbyHost's own invoices to hosts | Tax and accounting duties. Art. 6(1)(c) | Hosts: name, IČO, DIČ, address, amounts | Accountant [OWNER TO FILL], tax authority | None | 10 years from the end of the tax period (§ 35 zákon 235/2004 Sb.) | [OWNER TO FILL: where these invoices are made. No billing of hosts was found in the code; the in-app invoice module is the host's own tool, see B6] |
| A13 | Data-subject request register | Prove handling of requests within one month. Art. 6(1)(c), Art. 12(3) | Requesters: name, contact, request type, dates (`data_subject_request`) | None | None | Deleted with the workspace. [OWNER TO DECIDE: keep 3 years after closing the request] | S6, S8 |
| A14 | Backups of the whole database | Disaster recovery. Art. 6(1)(f) and Art. 32 | Everything in A and B | AWS S3 (Litestream replica, encrypted archives); Google Drive only if the owner turns that job on | None for S3. Google Drive [OWNER TO CONFIRM whether used] | Nightly archives 30 days; Litestream 7 days plus 30 days for non-current versions | S9 |

## Part B: UbyHost as processor, Art. 30(2) [Část B: UbyHost jako zpracovatel, čl. 30 odst. 2]

Controller for every row: each host, or the alternate controller entity configured on the property (`apartment.data_controller_entity_id`, else `apartment.legal_entity_id`). Contact details for each controller are in the `legal_entity` table (`name`, `contact_email`). Contract: DPA at `/dpa` (version shown on the page) accepted at sign-up.

Categories of processing are carried out on the controller's instructions as defined in DPA § 8: in-app settings, actions in the interface, and written requests.

| # | Activity [Činnost] | Purpose (controller's) [Účel] | Data subjects and data [Subjekty a údaje] | Recipients [Příjemci] | Transfers outside EEA | Retention [Doba uložení] | Security |
|---|---|---|---|---|---|---|---|
| B1 | Guest registration form and house book [domovní kniha] | Host's duty under § 101 and § 103 zákon 326/1999 Sb. | Guests, including children: surname, first name, birth date, nationality, travel document number and type, visa number, residence abroad, purpose of stay, stay dates, drawn signature, note, party size, submitter IP | Host users; AWS (hosting) | None | 6 years from the end of each stay, deleted on 31 January after the period ends (`housebook.retention_cutoff`). Submitter IP 90 days after stay end. The scheduled job is dry-run until `UBYHOST_RETENTION_AUTOPURGE=1` [OWNER TO DECIDE: turn on] | S2 to S11 |
| B2 | Police reporting of foreign guests through UbyPort | Host's duty under § 102 zákon 326/1999 Sb. (3 working days) | Foreign guests: the B1 fields mapped to the UbyPort `Ubytovany` record (no photos, no signatures). Host: UbyPort web-service user name and password (encrypted), IDUB | Police of the Czech Republic, Directorate of the Alien Police Service (statutory recipient) | None | Request and response XML: 90 days (`reporting.purge_submission_payloads`). Submission row with Doručenka PDF and result: 6 years | S5 (envelope and password encrypted), TLS verification, no redirects |
| B3 | Optional ID document photos or PDFs | Identity check chosen by the host. Not a statutory requirement | Guests: image or PDF of a passport or ID card (may show a face, MRZ, and other data) | Host users only. Not sent to the police | None | Deleted when the host marks the guest verified; otherwise 7 days after check-in; never later than 30 days after upload (`passport_photos.purge_stale`, every 12 h). Feature is off by default per property (`passport_photo_policy='off'`) | S5 (encrypted files), S7, S8, upload type and size checks |
| B4 | Guest claim, reminder and receipt e-mails | Let a guest open the private form and get a copy | Guests: e-mail address (masked on screens), language, claim state; phone last 4 digits from the booking if present | AWS SES | None | Claim e-mail and reservation contact 30 days after stay end; outbox and mail log 14 days | S4, S5 (secret encrypted in queue) |
| B5 | Calendar sync (iCal) | Create stays from Airbnb, Booking.com and other calendars | Booking dates, booking label; no guest identity data from the iCal | None (UbyHost fetches the host's own feed URL) | None | Stays follow B1 | SSRF protection on fetch |
| B6 | Host invoices to guests (in-app invoice tool) | Host's own tax documents | Guests or guest companies named on the invoice: name, address, IČO/DIČ if any, amounts, payment method | Host users | None | 10 years from issue (`invoices.purge_expired`) | S6, S9 |
| B7 | Stay-fee evidence [evidence k poplatku z pobytu] | Host's duty under § 3g zákon 565/1990 Sb. | Guests: stay nights, age-based exemption, host's exemption reason; sealed period PDFs and CSVs | Host users. UbyHost does not file or pay the fee to the municipality | None | 6 years, deleted on the same 31 January rule as B1 | S5 (snapshots encrypted), S6 |
| B8 | Data-subject request help and per-guest export | Help the host answer guests (Art. 28(3)(e)) | Guests: the guest's own record | Host users | None | With B1 | S6, S8 |
| B9 | Admin support inside a host workspace | Help the host on request; fix errors | All B data, with identity data masked unless revealed for one guest with a logged reason | UbyHost admin (the owner) | None | Audit 3 years | S7, S8 |
| B10 | Backups of guest data | Disaster recovery for the host | All B data | AWS S3 | None | As A14 | S9 |

Subprocessors for Part B (published at `/subprocessors`): AWS (Lightsail, SES, S3) in eu-central-1; Cloudflare, Inc. (Turnstile, proxy); Google Drive only if the owner enables the backup job; Render only for demo data, not production guest data.

## Open points for the owner [Otevřené body]

1. Fill in the identification table and A4, A12.
2. Decide retention for A3, A5 (incident records) and A13 after the account ends. The code deletes them with the workspace.
3. Confirm Google Drive is not used for production backups, or keep it in the register.
4. DPA § 11 (`dpa_i18n.py`) still names Render and Google Drive as subprocessors in general terms. Keep it in line with `/subprocessors`.
5. Turn on `UBYHOST_RETENTION_AUTOPURGE=1` once the 6-year rule is accepted. Until then B1, B6 and B7 rows are not deleted automatically.
