# UbyHost: GDPR / ePrivacy compliance review

**Date:** 27 September 2026
**Repo reviewed:** `jsfpechar-ops/jsfpecharoperations` @ `34f5cd1` (main, 27 Sep 2026 10:48 CEST)
**Companion:** `GDPR_REMEDIATION_PLAN.md` (the Cursor-executable backlog for Phase 3)
**Status:** engineering analysis, not legal advice. Items marked **NEEDS LAWYER** need a qualified Czech/EU data-protection lawyer before you ship.

Confidence labels used in Phase 1:

- **[SETTLED]**: statute text or binding case law.
- **[EVOLVING]**: guidance, a pending proposal, a pending appeal, or enforcement practice that can move.
- **[INTERPRETATION]**: my own engineering and legal reading. Verify it before relying on it.

---

## Phase 0: current state of the codebase

### 0.1 What the repo documents about itself

The repo already has an unusually thorough compliance paper trail. This review builds on it and does not repeat it:

| Doc | What it establishes |
|---|---|
| `docs/TECHNICAL_COMPLIANCE_AUDIT.md` (15 Sep, re-verified 24 Sep 2026) | Claims-vs-code matrix. Flags child signatures, passport uploads, manual six-year purge, backups, missing rights and breach workflow, and operator-identity drift |
| `docs/SECURITY.md` | Threat model and controls (Fernet at rest, TOTP, CSRF, SSRF, Turnstile, headers) |
| `docs/OPERATIONS.md` § "Retention and what is actually deleted", § "Backup and restore" | States plainly that the six-year purge is manual only, `guest.filled_ip` is never deleted, and **backups are not encrypted and carry the key** |
| `FOLLOWUPS.md` (W2.2) | Names, birth dates and signatures are still cleartext. The doc-number backfill script is not wired into deploy |
| `CURSOR_REMEDIATION_PLAN.md` | Existing agent-execution conventions. The new plan copies them |

### 0.2 Tech stack (verified in code)

| Layer | Fact | Where |
|---|---|---|
| Language/framework | Python, FastAPI 0.141 / Starlette 1.3, Jinja2 server-rendered templates, vanilla JS | `App/requirements.txt`, `App/app/main.py` |
| DB | **SQLite** (WAL, `secure_delete=ON`, `foreign_keys=ON`), raw SQL through the `db.query/insert/update` helpers. No ORM | `App/app/db.py` |
| Migrations | Append-only: `CREATE TABLE IF NOT EXISTS` in the `SCHEMA` literal, plus the `ADDED_COLUMNS` tuple applied by `_add_missing_columns()` at `init_db()` | `App/app/db.py:18`, `:482`, `init_db()` |
| Background jobs | APScheduler `BackgroundScheduler`, Europe/Prague. Jobs: `ical`, `submit`, `deadlines`, `mail`, `photo_sweep` (12 h) | `App/app/scheduler.py:128-160` |
| Host auth | Username + password hash, signed `ubyhost_session` cookie (HttpOnly, SameSite=Strict, Secure), `session_version` invalidation, TOTP 2FA required in production, recovery codes | `App/app/auth.py:25`, `:319-328`, `:305` |
| Guest auth | Permalink token + 6-digit PIN, `ubyhost_pin` cookie (7 days), claim link with hashed secret | `App/app/auth.py:460`, `:525`, `App/app/claim.py` |
| CSRF | Signed token + `ubyhost_csrf` cookie | `App/app/security.py:18`, `:98-111` |
| Hosting (prod) | AWS Lightsail, Docker Compose (`ubyhost` + `caddy:2-alpine`), Cloudflare proxy with an origin cert | `deploy/lightsail/docker-compose.yml`, `caddy/Caddyfile.cloudflare` |
| Hosting (staging) | Render `ubyhost-staging`, mock UbyPort | `render.yaml`, `App/render_start.sh` |
| Email | AWS SES `eu-central-1` (boto3), outbox table, console backend for staging | `App/app/config.py:173-177`, `App/app/mail.py` |
| Police integration | UbyPort SOAP over NTLM (`requests_ntlm`), TLS verified, no redirects | `App/app/ubyport/soap.py`, `client.py` |
| Bot protection | Cloudflare Turnstile on `/login`, guest claim and PIN | `App/app/turnstile.py`, `templates/login.html:51`, `guest/claim.html:55`, `guest/pin.html` |
| CI/CD | GitHub Actions `ci.yml`. Production deploy is manual `workflow_dispatch`, pinned to main | `.github/workflows/` |
| Marketing site | **Same FastAPI app, same origin.** `/`, `/jak-to-funguje`, `/cenik`, `/pruvodce/{slug}`, `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors` | `App/app/routes/legal.py:18-124`, `templates/landing.html` |

### 0.3 Personal data inventory (where it lives)

| Data | Storage | At rest | Retention in code |
|---|---|---|---|
| Guest surname, first name, birth date, nationality, residence street/city/country, purpose, stay dates | `guest` table (`db.py:131`) | **Plaintext** | Deleted only by the host's **Settings → purge** button (`routes/exports.py:357` → `housebook.purge_expired`). No scheduled job |
| Travel document and visa number | `guest.doc_number_enc`, `visa_number_enc` | Fernet (`db.py` `ENCRYPTED_GUEST_COLUMNS`). Plaintext columns stay as a read fallback until the backfill runs | Same as above |
| Drawn signature (base64 PNG) | `guest.signature_png` (`db.py:150`) | **Plaintext** | Same as above |
| Guest IP at submission | `guest.filled_ip` (`db.py:153`, written at `routes/guest.py:1560`) | Plaintext | Never deleted separately (`docs/OPERATIONS.md` says so) |
| Passport/ID image or PDF (optional, per-property policy, default `off`) | Files `DATA_DIR/passport_photos/{guest_id}.ext` | **Plaintext files**, mode 0600 (`passport_photos.py:98`) | Deleted on identity verification, archive or delete. 12-hour sweep removes files 30 days after stay end (`PHOTO_GRACE_DAYS=30`) |
| Guest claim e-mail, masked e-mail, language | `reservation_claim` (`db.py:265`) | Plaintext | **Never deleted** (no `DELETE FROM reservation_claim` anywhere) |
| Reservation data (dates, iCal summary, reservation URL, `phone_last4`, `guest_email`, `declared_guests`) | `reservation` (`db.py:109`) | Plaintext | **Never deleted** |
| Police request/response XML (full guest data incl. doc numbers) | `submission.request_xml/response_xml` | Plaintext | Blanked after 90 days by the 12-hour sweep (`reporting.purge_submission_payloads`, `SUBMISSION_PAYLOAD_DAYS=90`) |
| Doručenka / error PDFs | `submission.receipt_pdf/error_pdf` | Plaintext | Deleted only with orphan submissions after the six-year cutoff |
| Mail bodies, recipients | `email_outbox`, `console_mail_log` | Claim secret encrypted in payload | 14 days (`mail.purge_old`, `mail.py:438`) |
| Host accounts | `user_account` (username, display name, password hash, TOTP secret encrypted) | Mixed | Never deleted (disable only: `admin_accounts.py:472`) |
| Host legal entities (IČO, address, bank account/IBAN, contacts) | `legal_entity` | Plaintext | Manual delete (`admin.py:470`) |
| Invoices (buyer name, address, e-mail) | `invoice`, `invoice_item` | Plaintext, immutable triggers | 10 years via the same manual button (`invoices.purge_expired`) |
| Audit trail (actor, action, detail; `login_failed` stores the IP) | `audit` (`db.py:227`) | Plaintext | **Never deleted** |
| Rate-limit events (IP:username keys) | `rate_limit_event` | Plaintext | Pruned only per key when that key is checked again (`rate_limit.py:30`). Stale keys persist |
| Alerts | `alert` | Plaintext | Never deleted (except demo) |
| Container stdout logs | Docker json-file driver | Plaintext | **No rotation configured** (`docker-compose.yml` has no `logging:`). Uvicorn access log on by default (`Dockerfile:34`) and records request paths, including `/l/{token}/…` guest permalink tokens |
| Backups | `/data/backups/<stamp>/ubyhost.db` **plus `secret_key`** (`App/scripts/backup_data.sh:33-45`) | **Unencrypted; key travels with the DB** | Last 10 snapshots by count (`:54`). Off-site copies to Google Drive/S3 via `rclone copy` (`backup-gdrive.sh:39`, `backup-s3.sh:42`) are **never pruned** |

Application logs are PII-light. E-mail addresses are masked (`mail.py:290-296`, `:365-371`). No SOAP bodies are logged.

### 0.4 Cookies, tracking, analytics, consent

- **No analytics, ad pixels, tag managers, heatmaps, chat widgets, or third-party fonts** anywhere. I grepped templates, JS, CSS and config for gtag/GTM/GA/Plausible/Matomo/Hotjar/PostHog/Segment/Meta/Clarity/Sentry/Intercom/Google Fonts/CDNs.
- **CSP enforces this** (`main.py:147-152`): `script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com`, `connect-src 'self' https://challenges.cloudflare.com`, `img-src 'self' data:`. The only external script is Turnstile.
- **Cookies set by the app** (all first-party):

  | Name | Set at | Purpose | Lifetime |
  |---|---|---|---|
  | `ubyhost_session` | `auth.py:320` | Host login | 12 h / 30 d with "remember me" |
  | `ubyhost_csrf` | `security.py:103` | CSRF | `CSRF_MAX_AGE` = remember-me session max age (`security.py:19`) |
  | `ubyhost_lang` | `host_i18n.py:3811` | Host/public language | 1 year |
  | `ubyhost_pin` | `auth.py:528` | Guest PIN session | 7 days |
  | `ubyhost_owned` | `routes/guest.py:137` | Forms submitted on this device | 60 days |
  | `ubyhost_claim` | `routes/guest.py:252` | Claimed-reservation access | 60 days |
  | `ubyhost_guest_lang` | `routes/guest.py:38/264` | Guest language | 60 days |

- **localStorage** (host UI only): `ubyhost-command-recents` (URLs of recent command-palette items, `static/app.js:606`), `ubyhost-saved-stay-views` (`:838`), and a sidebar-collapsed flag (`:313`).
- **Cloudflare edge** (not in the repo): Managed Challenge on `/login` and private paths, leaked-credential mitigation, client-side security, and Email Address Obfuscation (visible on the live page as `/cdn-cgi/l/email-protection`). These can set Cloudflare cookies (e.g. `__cf_bm`, `cf_clearance`). I could not inspect live response headers: my in-app browser is blocked from ubyhost.com by org policy. **Verify these in the Cloudflare dashboard.**
- **Consent management:** none, and none is needed today (see Phase 1 §2). The privacy policy §7 describes necessary cookies in prose (`privacy_policy_i18n.py:112-131`). There is no per-cookie table.
- **Acceptance of Terms/DPA/Privacy:** browsewrap line on the login page (`templates/login.html:42`). Versions are logged into `audit.detail` as free text **only on the non-2FA login path** (`routes/admin_accounts.py:106-114`). The 2FA path (`:168`), which is **mandatory in production**, logs `two_factor_login` with **no versions**. So production has no acceptance evidence.
- **Guest legal notice:** the guest must tick `legal_ack` (`routes/guest.py:1485`). The tick is validated but **not persisted**, and no notice version is recorded.

### 0.5 Retention, deletion, export, audit tooling

| Capability | Exists? | Where |
|---|---|---|
| Six-year guest purge | Yes, **manual button only** | `routes/exports.py:357`, `housebook.py:467` |
| Passport image sweep | Yes, automatic every 12 h | `scheduler.py` `_job_photo_sweep`, `passport_photos.purge_stale` |
| Submission XML purge (90 d) | Yes, automatic | `reporting.purge_submission_payloads` |
| Mail purge (14 d) | Yes, automatic | `mail.purge_old` |
| Reservation / claim e-mail / audit / alert / user purge | **No** | none |
| House book CSV, per-guest registration PDF, PDFs zip, receipts zip, submission XML download, reservations CSV | Yes | `routes/exports.py:41-265` |
| Per-guest data-subject export (Art 15/20 bundle) | **No** (PDF and CSV partly substitute) | none |
| Restriction flag (Art 18) | **No** | none |
| Delete unsent guest | Yes. Sent guests are refused | `routes/admin.py:1918-1942` |
| Workspace export or deletion at contract end | **No** | none |
| Audit of *views/downloads* of guest data (passport image, exports) | **No.** Mutations are audited; reads are not | `routes/admin.py:1837`, `routes/exports.py` (no `db.audit` calls) |
| Audit actor identity | Weak. Most calls use default `actor="host"`; the workspace is recorded but not the individual user or impersonator | `db.py:681` |
| Breach/incident register | **No** | none |
| Backup status in Settings | **No** (but host guide copy claims it; see audit doc) | none |

### 0.6 Third parties and subprocessors found

| Provider | Role in code | Evidence | DPA mechanism (Phase 1 §5) |
|---|---|---|---|
| AWS Lightsail (hosting) | Prod host | `deploy/lightsail/`, `docs/LIGHTSAIL.md` | AWS GDPR DPA auto-incorporated in Service Terms |
| AWS SES | Transactional mail | `mail.py`, `config.py:175` (`eu-central-1`) | Same AWS DPA |
| AWS S3 (optional) | Off-site backup | `backup-s3.sh` | Same AWS DPA |
| Cloudflare | DNS, proxy, TLS, Turnstile, WAF, challenges, obfuscation | `docs/CLOUDFLARE.md`, `turnstile.py` | Cloudflare DPA incorporated in Self-Serve Subscription Agreement |
| Render | Staging/demo (mock) | `render.yaml` | render.com/dpa (DPF-certified) |
| **Google Drive** (optional) | Off-site backup via rclone | `backup-gdrive.sh` | **Only if a Workspace/Cloud account with Google's processor terms. A personal Google account has no processor DPA** |
| Czech Police (UbyPort) | Recipient (statutory), not a processor | `ubyport/` | n/a: independent recipient under law |
| Airbnb / Booking.com iCal | Data *source* (host-supplied feed URLs) | `icalsync.py` | n/a: not a processor for UbyHost |
| support@ubyhost.com mailbox | Support channel | `config.py:149`, `_public_footer.html:19` | **Unknown provider. Not in the subprocessor register** |
| GitHub, Cursor (dev tooling, `.cursor/`) | Code only | `.cursor/*`, `.github/` | Processor only if production data or logs are ever exposed to them (e.g. the Cloudflare observability MCP in `.cursor/mcp.json`) |
| AI/LLM at runtime | **None found** | grep | n/a |
| Payments | **None.** QR Platba strings only; no gateway | `payments.py:1-6` | n/a |

### 0.7 Code smells and gaps relevant to GDPR (headline)

1. **Backups defeat the encryption.** `backup_data.sh` writes `secret_key` beside the unencrypted DB (`:42-45`), and `backup-gdrive.sh` uploads both to Google Drive. The subprocessor register says Drive holds "encrypted backup archives" (`subprocessors_i18n.py:66-68`). That statement is false.
2. **No acceptance evidence in production** (2FA login path logs no versions).
3. **Six-year purge is manual.** Reservations, claim e-mails, audit rows, alerts and rate-limit rows are **never** deleted.
4. **Access logs are unbounded** and contain guest permalink tokens and IPs. There is no Docker log rotation.
5. **Guest notice acknowledgement is not persisted.**
6. **Reads of sensitive data are not audited**, and audit actors are coarse.
7. **No DSR, restriction, workspace-termination or incident tooling.**
8. **Controller identity is not enforced.** The guest privacy page falls back to "ask your host" (`templates/guest/privacy.html:28`), and the readiness checklist only checks the property manager's e-mail (`routes/admin.py:124-128`).
9. Passport images and signatures are stored as plaintext on the volume. This is a proportionality point under Art 32, not a hard rule.
10. The doc-number backfill (`scripts/migrate_encrypt_doc_fields.py`) is not run by `deploy.sh`.

---

## Phase 1: research

### 1. GDPR requirements for this data set

| Topic | Requirement | Label | Source |
|---|---|---|---|
| Lawful basis, guest registration data | Art 6(1)(c) legal obligation. Under Art 6(3) the basis must be laid down in Member State law. Here that is Act 326/1999 Coll. §§ 99–103: § 101 house book (6 years from last entry), § 102 report within 3 working days, § 103 guest duties. The repo's notice already states Art 6(1)(c) (`i18n.py:389`) | SETTLED (statute). Scope for EU nationals, Czech nationals and under-15s is NEEDS LAWYER | GDPR Art 6; Act 326/1999 §§ 101–102 ([zakonyprolidi](https://www.zakonyprolidi.cz/cs/1999-326), [muj-pravnik summary](https://muj-pravnik.cz/co-je-eturista/)) |
| Lawful basis, passport image upload | **Not** required by § 103, which requires *presenting* a document. The optional upload therefore needs its own basis (likely Art 6(1)(f), or the host's contract), plus a necessity and proportionality test | INTERPRETATION, NEEDS LAWYER | Czech guidance treats copying ID documents without a legal basis or consent as unlawful, and says accommodation providers should record only what's necessary ([ÚOOU PDF](https://uoou.gov.cz/media/tiskove-zpravy/dokumenty/prokazovani-totoznosti-a-zpracovani-osobnich-udaju.pdf), [epravo](https://www.epravo.cz/top/clanky/brante-se-nezakonnemu-kopirovani-osobnich-dokladu-75872.html)) |
| Special categories (Art 9) | Nationality, passport number and DOB are **not** Art 9 categories. A passport photo is biometric data only when processed "through specific technical means" (Recital 51); UbyHost does no face matching. But the CJEU reads "revealing" special data broadly (C-184/20, *OT*, 2022), and a document image can reveal ethnic origin or religion (head covering) | SETTLED text; application is INTERPRETATION | GDPR Art 9, Recital 51; CJEU C-184/20 |
| Criminal-offence data (Art 10) | Police reporting is not criminal-conviction data | INTERPRETATION (high confidence) | GDPR Art 10 |
| National ID numbers | Art 87 allows Member States to set conditions. I found no Czech rule that specifically governs foreign passport numbers beyond Act 326/1999 | INTERPRETATION, verify | GDPR Art 87; Act 110/2019 Coll. |
| Transparency | Art 13 notice at collection, in plain language, suitable for children where relevant (Recital 58). The repo has a guest notice and privacy page | SETTLED | GDPR Arts 12–13 |
| Rights | Access (15), rectification (16), erasure (17, limited by 17(3)(b) legal obligation), restriction (18), portability (20: applies only to consent or contract bases, so **not** to 6(1)(c) guest data), objection (21: not available against 6(1)(c)). One-month response deadline (Art 12(3)) | SETTLED | GDPR Arts 12, 15–21 |
| Storage limitation | Data must be deleted when the purpose ends (Art 5(1)(e)). The six-year statutory period is a floor for the house book and, under GDPR, effectively a ceiling | SETTLED principle; the anchor date is NEEDS LAWYER | GDPR Art 5(1)(e); Act 326/1999 § 101 |
| Security | Art 32 risk-based measures (encryption, pseudonymisation, access control, restore testing). Backups are in scope | SETTLED | GDPR Art 32 |
| Accountability | Art 5(2) and Art 24: you must be able to *demonstrate* compliance (logs, records, versions) | SETTLED | GDPR Arts 5(2), 24 |
| Records of processing | Art 30(1) (as controller for host accounts and marketing) and **Art 30(2) (as processor for hosts' guest data)**. The <250-employee exemption doesn't apply because the processing is not occasional | SETTLED; exemption reading is INTERPRETATION | GDPR Art 30(5) |
| Breach | Processor must notify the controller "without undue delay" (Art 33(2)). The controller notifies ÚOOU within 72 h (33(1)) and data subjects if high risk (34). Every breach must be documented (33(5)) | SETTLED | GDPR Arts 33–34 |
| DPIA | Art 35 when processing is likely high-risk. ÚOOU publishes positive and negative lists. Relevant triggers: systematic processing of identity documents, possible vulnerable subjects (children), innovative online check-in, multiple controllers on one platform | Requirement SETTLED; whether it triggers here is NEEDS LAWYER | [ÚOOU DPIA page](https://uoou.gov.cz/profesional/posouzeni-vlivu-na-ochranu-osobnich-udaju-dpia) |
| IP/device data of host accounts | Personal data. Basis is Art 6(1)(b) contract and 6(1)(f) security. Retention must be defined | SETTLED; periods are INTERPRETATION | GDPR Arts 4(1), 6 |
| Transfers | Chapter V. EU–US DPF adequacy remains valid: the General Court dismissed *Latombe* on 3 Sep 2025, and the appeal C-703/25 P is **pending at the CJEU with no hearing date announced**. SCCs are the fallback | EVOLVING | [IAPP](https://iapp.org/news/a/european-general-court-dismisses-latombe-challenge-upholds-eu-us-data-privacy-framework), [WilmerHale](https://www.wilmerhale.com/en/insights/blogs/wilmerhale-privacy-and-cybersecurity-law/20251201-european-court-of-justice-to-review-challenge-to-eu-us-data-privacy-framework) |
| GDPR reform | The Commission's **Digital Omnibus** (19 Nov 2025) would amend GDPR and move cookie rules into a new GDPR Art 88a/88b. The Data Omnibus part is **still in negotiation**; realistic application is 2027 or later | EVOLVING. Do **not** build to it | [Taylor Wessing](https://www.taylorwessing.com/en/global-data-hub/2026/the-digital-omnibus-proposal/gdh---the-digital-omnibus---cookies), [Secure Privacy](https://secureprivacy.ai/blog/eu-digital-omnibus-what-article-88a-changes-for-cookie-consent-2026) |

### 2. ePrivacy and Czech cookie law for the marketing site

- **Rule [SETTLED]:** ePrivacy Directive Art 5(3), transposed as **§ 89(3) of Act 127/2005 Coll. (ZEK)**. Since **1 Jan 2022** (Act 374/2021 Coll.) this is **opt-in**: you need prior, demonstrable consent for any storage or access on the device, except (a) transmission of a communication and (b) what is strictly necessary for a service the user explicitly requested. ([ÚOOU](https://uoou.gov.cz/udeleny-pokuty-ve-vysi-temer-45-mil-kc); [Rowan Legal](https://rowan.legal/aktualne/stanovisko-spolku-pro-ochranu-osobnich-udaju-k-pravni-uprave-cookies-v-ceske-republice-od-zacatku-roku-2022/))
- **Consent quality [SETTLED]:** GDPR Art 4(11) and 7. Pre-ticked boxes are invalid (CJEU C-673/17 *Planet49*, 2019).
- **What counts as strictly necessary [EVOLVING guidance]:** EDPB Guidelines 2/2023 on the technical scope of Art 5(3) (final, Oct 2024) read "storage or access" broadly. It covers localStorage, pixels, and device signals read by JS, not only cookies ([EDPB](https://www.edpb.europa.eu/documents/guideline/guidelines-22023-on-technical-scope-of-art-53-of-eprivacy-directive_en)). Session, CSRF, security (Turnstile or challenge on a login you asked for) and a language cookie set when you click the switcher are **commonly treated as exempt** [INTERPRETATION]. Analytics, even "privacy-friendly" analytics, generally are **not** exempt under current law. The Omnibus would exempt first-party aggregated statistics, but that is **not law**.
- **What this means for UbyHost today [INTERPRETATION, high confidence]:** the site sets only strictly necessary first-party cookies and loads no trackers. **No consent banner is legally required, and adding one would be noise.** The obligation is transparency: an accurate per-cookie list, which ÚOOU calls out when it is missing. You must add a compliant CMP the moment any analytics or marketing tag is added.
- **ÚOOU enforcement trend [EVOLVING]:**
  - In the first half of 2022 ÚOOU monitored banners and listed deficiencies: non-technical cookies without consent, disproportionate cookie lifetimes, no reject option on the first layer, unequal button prominence, missing per-cookie information, info only in a foreign language ([ÚOOU, 30 Jun 2022](https://uoou.gov.cz/cs/cookies-listy-vykazuji-radu-nedostatku)).
  - In 2023 it moved to fines: **CZK 4.443 m** issued, **CZK 898 k** the largest final fine, and it named reject options pushed into deeper layers as a deceptive design pattern ([ÚOOU, 2 Aug 2023](https://uoou.gov.cz/udeleny-pokuty-ve-vysi-temer-45-mil-kc)).
- **EU trend [EVOLVING]:** in Sept 2025 CNIL fined **SHEIN €150 m** and **Google €325 m** for cookie and consent failures ([CNIL](https://www.cnil.fr/en/cookie-regulation-cnil-continuing-action-plan-initiated-2019-and-has-imposed-two-fines-shein-and)).
- **Accommodation-specific enforcement:** my searches found no ÚOOU decision on online check-in platforms specifically. **Uncertain, verify.** The relevant Czech guidance I found is the long-standing ÚOOU position against copying identity documents without a legal basis (see §1).

### 3. Czech-specific requirements for UbyPort-related data

| Point | Finding | Label |
|---|---|---|
| Duty holder | *Ubytovatel*: anyone providing accommodation for payment (§ 99) | SETTLED ([muj-pravnik](https://muj-pravnik.cz/co-je-eturista/)) |
| Report | To Police ČR within **3 working days** of arrival (§ 102). Since 1 Sep 2025 UbyPort rejects duplicates (repo `README.md`) | SETTLED; the counting rule (arrival day included?) is an open decision D3 in `CURSOR_REMEDIATION_PLAN.md` |
| House book | Contents (name, DOB, nationality, document no., visa no., stay dates, etc.), kept **6 years from the last entry** (§ 101). Paper or electronic | SETTLED text; per-row vs whole-book anchor is NEEDS LAWYER |
| Penalties | Up to **CZK 50,000** for breaching reporting or house-book duties (§ 156, per the secondary source) | Verify against current consolidated text |
| Special category? | Police-bound data is **not** Art 9 or Art 10 data per se. It is ordinary personal data processed under a legal obligation, with elevated risk (identity documents) | INTERPRETATION |
| Czech nationals | Czech nationals have no § 102 reporting duty. Whether they belong in the § 101 "domovní kniha" or in a separate municipal-fee register (Act 565/1990 Coll.) affects basis and retention | NEEDS LAWYER (already flagged in the repo audit) |
| **eTurista** (pending) | An amendment to Act 159/1999 Coll. would create a central register run by the Ministry for Regional Development, cover all guests, and **shorten foreigner reporting to 24 h**. As of the latest sources I found (May–Aug 2026) it is **not in force**, with MMR aiming at 2027 | EVOLVING ([muj-pravnik, 4 May 2026](https://muj-pravnik.cz/co-je-eturista/), [e-turista.cz](https://www.e-turista.cz/)) |
| EU STR Regulation (EU) 2024/1028 | Applies from 20 May 2026. It governs host registration numbers and platform data-sharing, not guest data directly, but it will drive the Czech implementation | SETTLED that it applies; national scheme EVOLVING |

### 4. CMP best practice (only relevant if you add non-essential tags)

The consensus of the EDPB Cookie Banner Taskforce (Jan 2023) and ÚOOU:

- **Acceptable:**
  - "Reject all" on the **first layer**, as a button of equal size, colour and contrast to "Accept all".
  - No pre-ticked purposes.
  - Granular purposes on the second layer.
  - Nothing non-essential fires before consent.
  - Withdrawal as easy as consent (a persistent footer link).
  - A per-cookie list (name, provider, purpose, lifetime) in Czech.
  - Proportionate consent lifetime (6–13 months is common; interpretation).
  - Consent records kept: timestamp, banner/policy version, choices, pseudonymous ID.
- **Dark patterns:** reject as a link instead of a button, reject only in layer 2, low-contrast reject, pre-ticked boxes, "legitimate interest" toggles for tracking, cookie walls, banners that block reading, "by continuing to browse you accept".
- Sources: [EDPB taskforce report](https://service.betterregulation.com/sites/default/files/2023-01/edpb_20230118_report_cookie_banner_taskforce_en.pdf), [Hunton summary](https://www.huntonprivacyblog.com/2023/01/27/edpb-publishes-report-of-outcome-of-the-cookie-banner-taskforce/), and the ÚOOU pages above.
- The Omnibus proposal would add one-click reject, a six-month re-ask bar and browser signals [EVOLVING, not law].

### 5. Data Processing Agreements and subprocessors

- **Art 28(3) [SETTLED]:** a written contract (electronic form is fine, Art 28(9)) with the mandatory clauses: documented instructions, confidentiality, Art 32 security, subprocessor conditions, assistance with rights and breaches, deletion or return at the end, and audit. The subprocessor chain must flow down equivalent terms (28(4)). The controller's general authorisation needs notice of changes and a right to object (28(2)). The repo's `/subprocessors` page promises 30 days' notice (`subprocessors_i18n.py`).
- **Two layers apply here:** (a) **host (controller) ↔ UbyHost operator (processor)**: the `/dpa` page, accepted at login; (b) **operator ↔ subprocessors**.

Cross-check against the Phase 0 third parties:

| Provider | DPA status | Action |
|---|---|---|
| AWS (Lightsail, SES, S3) | AWS GDPR DPA is incorporated into the AWS Service Terms and applies automatically ([AWS](https://docs.aws.amazon.com/whitepapers/latest/navigating-gdpr-compliance/aws-data-processing-addendum-dpa.html)) | Record region (eu-central-1) and account ID in the vendor file. Confirm Lightsail region |
| Cloudflare | Customer DPA incorporated into the Self-Serve Subscription Agreement, with SCCs ([Cloudflare DPA](https://www.cloudflare.com/cloudflare-customer-dpa/)) | Keep a copy. Global network means a transfer; document it |
| Render | [render.com/dpa](https://render.com/dpa) incorporated by the Terms. DPF-certified | Only needed if Render ever holds real data. Keep staging data synthetic |
| Google Drive | Processor terms exist **only** for Workspace/Cloud customers. A consumer Google account has no processor DPA ([Google Workspace DPA](https://workspace.google.com/terms/dpa_terms.html)) | **Stop using a personal Drive**, or move to Workspace with the Cloud Data Processing Addendum. Encrypt before upload regardless |
| Support mailbox provider | Unknown | Identify it, sign its DPA, and add it to the register |
| Czech Police | Statutory recipient, not a processor | List as a recipient, not a subprocessor |

---

## Phase 2: compliance gap analysis

Key: **COVERED** = found in code or config, with a cite. **GAP** = missing or contradicted. **LAWYER** = needs legal review. IDs link to the backlog in `GDPR_REMEDIATION_PLAN.md`.

### 2A. Marketing website (ubyhost.com public pages)

| # | Requirement | Status | Evidence / note | Backlog |
|---|---|---|---|---|
| M-1 | No non-essential cookies or trackers without consent | **COVERED** | No trackers found. CSP `main.py:147-152` blocks third-party scripts except Turnstile. Public pages set only `ubyhost_lang` / `ubyhost_csrf` | MK-1 (guardrail test) |
| M-2 | Cloudflare edge features don't inject tracking (Web Analytics/RUM, Zaraz) and their cookies are documented | **GAP** (unverifiable from the repo) | Email obfuscation is live. Challenge cookies are possible | MK-2 |
| M-3 | Per-cookie and storage disclosure (name, purpose, lifetime, party), in Czech | **GAP** | Prose only in `privacy_policy_i18n.py:112-131`. localStorage keys and Cloudflare cookie names are not listed | MK-3, FE-4 |
| M-4 | Proportionate lifetime of preference cookie | **LAWYER** (low) | `ubyhost_lang` lasts 1 year (`host_i18n.py:3805-3818`) | MK-4 |
| M-5 | CMP that meets ÚOOU/EDPB guidance *if* analytics are added | N/A today, **GAP as a process** | No policy stops someone adding GA later | MK-1, MK-5 |
| M-6 | Operator identification and legal pages | **COVERED** | `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors` (`routes/legal.py:69-135`), identity from `config.OPERATOR_*` | – |
| M-7 | No personal data collected via forms | **COVERED** | `mailto:` only (`pricing.html:66,86`, `_public_footer.html:19`) | – |
| M-8 | Subprocessor register accurate | **GAP** | Says Drive backups are "encrypted" (`subprocessors_i18n.py:66-68`); the scripts upload plaintext DB plus key. Support mailbox provider is missing | LD-4 |
| M-9 | Transfer statements accurate (Cloudflare global, DPF) | **LAWYER** | `subprocessors_i18n.py` Cloudflare location text | LD-4, lawyer list |

### 2B. Application / dashboard (guest check-in, host login, storage)

| # | Requirement | Status | Evidence / note | Backlog |
|---|---|---|---|---|
| A-1 | Lawful basis stated for guest registration fields | **COVERED** (text) / **LAWYER** (scope) | `i18n.py:389-393` states Art 6(1)(c) and §§ 101–103 | LD-8 |
| A-2 | Separate basis for optional passport upload, signature, claim e-mail, party size | **LAWYER** | Upload policy default `off` (`db.py` `passport_photo_policy`) | lawyer list |
| A-3 | Art 13 notice shown before collection | **COVERED** | `templates/guest/_legal_notice.html`, `guest/privacy.html` | – |
| A-4 | Proof the notice was shown (version, time, language) | **GAP** | `legal_ack` validated but not stored (`routes/guest.py:1485`, payload `:1553-1570`) | BE-5, FE-2 |
| A-5 | Controller identity complete before the guest form goes live | **GAP** | Fallback text `guest/privacy.html:28`. Readiness only checks PM e-mail (`routes/admin.py:124-128`) | BE-7, FE-6 |
| A-6 | Host acceptance of Terms/DPA/Privacy provable, per version | **GAP** | Versions logged only on the non-2FA path (`admin_accounts.py:106-114`), not on 2FA (`:168`), which production enforces. Free-text detail only | BE-1, FE-1 |
| A-7 | DPA concluded in writing (Art 28(9)) | **LAWYER** | Browsewrap on the login line (`login.html:42`) | BE-1, FE-1, lawyer list |
| A-8 | Encryption of highest-risk fields at rest | **COVERED** for doc/visa no. (`db.py` `ENCRYPTED_GUEST_COLUMNS`) / **GAP** for signature, passport files, DOB (plaintext) | `passport_photos.py:98`, `db.py:150` | BE-12 (P2) |
| A-9 | Backfill of legacy plaintext doc numbers actually executed | **GAP** | Script exists, not in `deploy.sh` (`FOLLOWUPS.md` W2.2) | BE-11 |
| A-10 | Automated deletion at end of the retention period | **GAP** | Manual button only (`routes/exports.py:357`) | BE-2 |
| A-11 | Retention anchor (per-row vs last entry) | **LAWYER** | `housebook.expired_guest_ids` uses per-guest stay end | lawyer list |
| A-12 | Reservation rows, claim e-mails, `guest_email`, `phone_last4` deleted when no longer needed | **GAP** | No delete path | BE-3 |
| A-13 | `filled_ip` retention defined | **GAP** | Kept for the life of the record (`docs/OPERATIONS.md`) | BE-3 |
| A-14 | Rights: access/copy | Partial **COVERED** / **GAP** | Registration PDF and house-book CSV exist (`routes/exports.py:64, 212`). No per-subject bundle and no request log | BE-8, FE-5 |
| A-15 | Rights: rectification | **COVERED** | Host guest edit `admin.py:1742`. Guest edit `routes/guest.py` `/edit/{guest_id}` | – |
| A-16 | Rights: erasure (where 17(3)(b) doesn't bar it) | Partial **COVERED** | Unsent guests deletable (`admin.py:1918`). Sent rows refused with a reason | BE-8 |
| A-17 | Rights: restriction (Art 18) | **GAP** / **LAWYER** (interaction with the reporting duty) | none | BE-9 |
| A-18 | Rights request register with 1-month deadline tracking | **GAP** | none | BE-8, FE-5 |
| A-19 | Host account data: export and deletion at contract end (Art 28(3)(g)) | **GAP** | Disable only (`admin_accounts.py:472`) | BE-10 |
| A-20 | Session and auth security | **COVERED** | `docs/SECURITY.md`. TOTP required in production (`auth.py:305`) | – |
| A-21 | Guest pages not cached | **COVERED** | `Cache-Control: no-store` (`main.py:157-158`) | – |

### 2C. Backend data handling and third parties

| # | Requirement | Status | Evidence / note | Backlog |
|---|---|---|---|---|
| B-1 | Backups encrypted, key held separately | **GAP (P0)** | `backup_data.sh:42-45` copies the key into the snapshot. `docs/OPERATIONS.md` "Backups are not encrypted" | OPS-1 |
| B-2 | Off-site backup provider has an Art 28 DPA, EU region, bounded retention | **GAP (P0)** | `backup-gdrive.sh`/`backup-s3.sh` use `rclone copy` with no pruning. Drive account type unknown | OPS-2 |
| B-3 | Backup retention by time, documented, propagating deletions | **GAP** | Count-based (10) `backup_data.sh:54` | OPS-1, LD-3 |
| B-4 | Backup status claim in UI matches reality | **GAP** | Audit doc: INCONSISTENT | OPS-1, FE-3 |
| B-5 | Server log minimisation and rotation | **GAP (P1)** | Uvicorn access log on (`Dockerfile:34`) with tokens in paths. No compose `logging:` | OPS-3 |
| B-6 | Audit log retention defined | **GAP** | `audit` never pruned | BE-4 |
| B-7 | Rate-limit and alert table pruning | **GAP** (low) | `rate_limit.py:30` per key only. Alerts never deleted | BE-4 |
| B-8 | Access to sensitive data is logged (who viewed or exported) | **GAP** | No `db.audit` in `routes/exports.py`; passport photo view `admin.py:1837` not audited | BE-6 |
| B-9 | Audit actor identifies the individual user and impersonator | **GAP** | `db.audit(... actor="host")` default | BE-6 |
| B-10 | Breach detection, register, processor→controller notification | **GAP** | Only PIN-abuse and submission alerts (`alerts.py`) | BE-13, LD-5 |
| B-11 | Transport security to Police | **COVERED** | TLS verify, no redirects (`docs/SECURITY.md`, `ubyport/soap.py`) | – |
| B-12 | Staging never holds real data | **COVERED** (guard) | `env_guard.py`, `render_start.sh` | LD-9 (policy) |
| B-13 | Mail content minimisation | **COVERED** | Claim secret not in body; 14-day purge (`mail.py:438`); masked in logs | – |
| B-14 | Submission XML (full doc numbers) short-lived | **COVERED** | 90-day blanking (`reporting.py:1624-1666`) | – |
| B-15 | Passport images short-lived | **COVERED** | 30-day sweep + delete on verify (`passport_photos.py:117-188`) | – |
| B-16 | Subprocessor DPAs on file (AWS, Cloudflare, Render, Google, support mailbox) | **GAP (docs)** | Not verifiable from the repo | LD-9 |
| B-17 | RoPA (Art 30(1) and 30(2)) | **GAP** | None in the repo | LD-1 |
| B-18 | DPIA | **LAWYER** | None in the repo | LD-2 |
| B-19 | AI/LLM tools with production data | **COVERED** (none at runtime) / **GAP** (policy for dev tools) | `.cursor/mcp.json` includes Cloudflare observability | LD-9 |

---

## Items that must not be automated without a qualified Czech/EU data-protection lawyer

1. **Retention anchor and periods.** Should the six-year clock run per guest from the stay end (current code) or from the last house-book entry (§ 101 wording)? Also: periods for Doručenka/XML, audit logs, IPs, claim e-mails, reservations, invoices (10 y), and backups. Do not auto-delete until these are signed off. The plan builds the job in dry-run mode first.
2. **Passport/ID image upload.** Is it necessary and proportionate? What is the lawful basis? Does it create Art 9 exposure? Does ÚOOU's position on copying documents apply? Until you decide, keep the default `off`.
3. **Signatures.** What legal effect does a drawn signature in an app-generated PDF have? What is the under-15 path, and who signs for a child on a parent's passport?
4. **Scope of reportable guests.** EU/EEA/Swiss nationals, the treatment of Czech nationals (§ 101 house book vs the municipal-fee register), and the exact § 100–103 citations in guest copy.
5. **Rights limits.** When erasure, restriction or objection must be refused because of § 101, and whether a restricted record may still be reported. Response wording to data subjects.
6. **Controller/processor allocation.** Operator as independent controller (security logs, support, billing). Admin impersonation (full read/write into host workspaces). Who notifies a breach, and when.
7. **Contract formation.** Is browsewrap on the login line a valid acceptance of the Terms and an Art 28 DPA, or is clickwrap required? This matters especially where a host is a natural person or consumer.
8. **Cross-border transfers.** Cloudflare global processing, DPF reliance while C-703/25 P is pending, and any US support access by AWS/Google. Whether a TIA is needed. Whether "data stays in the EU" may be said at all.
9. **DPIA and DPO necessity**, and what the public notice should say about those conclusions.
10. **Workspace termination.** Operator deletion vs the host's own six-year duty. The format and timing of return, and what the operator may keep.
11. **§ 89(3) ZEK exemption** for Turnstile, Cloudflare challenge cookies (`__cf_bm`, `cf_clearance`), and a 1-year language cookie.
12. **eTurista and 24-hour reporting.** Monitor the Act 159/1999 amendment. Do not change deadline logic until it is promulgated.
13. **Controlling language.** Whether Czech must be the controlling text of the guest notice, and a bilingual legal review of EN/CS parity.

---

## Sources

- GDPR (Regulation (EU) 2016/679); ePrivacy Directive 2002/58/EC (as amended)
- Act 326/1999 Coll.: [zakonyprolidi.cz](https://www.zakonyprolidi.cz/cs/1999-326); summary in [muj-pravnik.cz, eTurista article (4 May 2026)](https://muj-pravnik.cz/co-je-eturista/)
- [ÚOOU: Cookies lišty vykazují řadu nedostatků (30 Jun 2022)](https://uoou.gov.cz/cs/cookies-listy-vykazuji-radu-nedostatku)
- [ÚOOU: Uděleny pokuty ve výši téměř 4,5 mil. Kč (2 Aug 2023)](https://uoou.gov.cz/udeleny-pokuty-ve-vysi-temer-45-mil-kc)
- [ÚOOU: Prokazování totožnosti a zpracování osobních údajů (PDF)](https://uoou.gov.cz/media/tiskove-zpravy/dokumenty/prokazovani-totoznosti-a-zpracovani-osobnich-udaju.pdf); [epravo: kopírování dokladů](https://www.epravo.cz/top/clanky/brante-se-nezakonnemu-kopirovani-osobnich-dokladu-75872.html)
- [ÚOOU DPIA](https://uoou.gov.cz/profesional/posouzeni-vlivu-na-ochranu-osobnich-udaju-dpia)
- [Rowan Legal: cookies from 2022](https://rowan.legal/aktualne/stanovisko-spolku-pro-ochranu-osobnich-udaju-k-pravni-uprave-cookies-v-ceske-republice-od-zacatku-roku-2022/)
- [EDPB Cookie Banner Taskforce report (Jan 2023)](https://service.betterregulation.com/sites/default/files/2023-01/edpb_20230118_report_cookie_banner_taskforce_en.pdf); [Hunton summary](https://www.huntonprivacyblog.com/2023/01/27/edpb-publishes-report-of-outcome-of-the-cookie-banner-taskforce/)
- [EDPB Guidelines 2/2023 on technical scope of Art 5(3)](https://www.edpb.europa.eu/documents/guideline/guidelines-22023-on-technical-scope-of-art-53-of-eprivacy-directive_en)
- [CNIL: SHEIN and Google cookie fines (Sept 2025)](https://www.cnil.fr/en/cookie-regulation-cnil-continuing-action-plan-initiated-2019-and-has-imposed-two-fines-shein-and)
- [Taylor Wessing: Digital Omnibus and cookies](https://www.taylorwessing.com/en/global-data-hub/2026/the-digital-omnibus-proposal/gdh---the-digital-omnibus---cookies); [Secure Privacy: Art 88a status](https://secureprivacy.ai/blog/eu-digital-omnibus-what-article-88a-changes-for-cookie-consent-2026)
- [IAPP: Latombe dismissed](https://iapp.org/news/a/european-general-court-dismisses-latombe-challenge-upholds-eu-us-data-privacy-framework); [WilmerHale: CJEU appeal](https://www.wilmerhale.com/en/insights/blogs/wilmerhale-privacy-and-cybersecurity-law/20251201-european-court-of-justice-to-review-challenge-to-eu-us-data-privacy-framework)
- [AWS DPA](https://docs.aws.amazon.com/whitepapers/latest/navigating-gdpr-compliance/aws-data-processing-addendum-dpa.html); [Cloudflare Customer DPA](https://www.cloudflare.com/cloudflare-customer-dpa/); [Render DPA](https://render.com/dpa); [Google Workspace DPA](https://workspace.google.com/terms/dpa_terms.html)
- [e-turista.cz](https://www.e-turista.cz/) (status tracker for the pending eTurista amendment)
