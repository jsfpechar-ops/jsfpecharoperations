# Compliance

This page is an index of what the repository shows. It is **not** legal advice.
Legal positions and lawyer-review status live in
[docs/UbyHost_workplan/04_legal_positions.md](UbyHost_workplan/04_legal_positions.md)
and [docs/privacy/](privacy/) (not read in full in this pass; read before relying on any statement here).

## Personal data inventory (from `App/app/db.py` SCHEMA)

| Entity / table | Personal data | Protection in code | Source |
|---|---|---|---|
| `user_account` | e-mail, username, TOTP secret, recovery code hashes | TOTP secret encrypted (`totp_secret_enc`); recovery codes hashed | `db.py:95-107` |
| `guest` | full name, birth date, nationality, document and visa numbers, residence address, signature image, filer IP | `doc_number_enc`, `visa_number_enc`, `signature_png_enc` (Fernet); **plaintext columns still exist beside them** | `db.py:215-269`, `db.py:222-225` |
| `submission` | guest data as sent to the police (`request_xml_enc`), response XML and receipts (plaintext), submitter IP | request encrypted; receipts not encrypted at this layer | `db.py:271-293`, `db.py:1734-1740` |
| `invoice`, `invoice_item` | billing name, address, tax ID | invoices are PDFs as BLOBs | `db.py:417-471` |
| `ical_feed` | the feed URL (acts as a secret) | — | `db.py:180` |
| `email_outbox` | recipient and message bodies | — | `db.py:382` |
| `audit` | actor, actions | retained 1095 days (`UBYHOST_AUDIT_RETENTION_DAYS`) | `db.py:320`, `config.py:232` |
| `data_subject_request` | DSR requests | — | `db.py:618` |
| `passport photos` (files) | passport images | encrypted blob (`passport_photos.py:201`); deleted 30 days after stay end | `OPERATIONS.md` (`photo_sweep`) |

## Retention

- Guest rows: six-year cutoff. Invoices: ten years (`docs/OPERATIONS.md` § Scheduled jobs, `retention` job; migration `0023` header). The `retention` job **only counts** unless `UBYHOST_RETENTION_AUTOPURGE=1` (`App/app/retention.py:594`, `App/app/config.py:221`).
- Claim e-mail: 30-day grace (`retention.py:25`). Submitter IP: 90-day grace (`retention.py:28`).
- Rate-limit events: 24 h (`UBYHOST_RATE_LIMIT_RETENTION_HOURS`, `config.py:234`). Alerts: 365 days (`config.py:233`). Audit: 1095 days (`config.py:232`).
- Passport images: deleted for stays that ended more than 30 days ago; submission envelopes blanked after 90 days (`docs/OPERATIONS.md` `photo_sweep`).
- Signup purge deletes unverified stale accounts (`App/app/signup.py:728-740`).
- Retention policy document: `docs/privacy/RETENTION.md` (not read in this pass).

## Processing basis
`⚠️ UNKNOWN — needs human input`: the legal basis per processing activity is in `docs/privacy/ROPA.md` (not read in this pass). Confirm before the migration freezes the data model.

## Deletion and export (data-subject requests)
- DSR module: `App/app/dsr.py`; table `data_subject_request` (`db.py:618-639`); statuses `open`, `extended`, `fulfilled`, `refused`, `withdrawn` (`dsr.py:26`); due-soon window 5 days (`dsr.py:14`); extension is one month (`dsr.py:29`).
- Guest export: `dsr.guest_export` (`dsr.py:87`). Deletion path: `⚠️ UNKNOWN` — read `App/app/dsr.py` and `App/app/routes/privacy_requests.py` to confirm what "erase" does.
- Who may invoke: `⚠️ UNKNOWN` — admin vs. host. `dsr.list_for_owner` is owner-scoped (`dsr.py:40-45`).
- Backups: deletion from encrypted backups is `⚠️ UNKNOWN` (see [runbook § Backups](runbook.md#backups)).

## Data residency
- SES region `eu-central-1` (`App/app/config.py:315`).
- Render staging `frankfurt` (`render.yaml`).
- PostHog EU endpoints (`App/app/config.py:299-303`).
- TTLock EU API (`App/app/config.py:169`).
- Lightsail region: `⚠️ UNKNOWN — needs human input`: check the AWS console for the instance and the S3 bucket for Litestream/backups (name not in this pass).
- Stripe, Anthropic, Mistral, Cloudflare: US or other locations are `⚠️ UNKNOWN`; confirm from vendor DPAs.

## DPA and subprocessors
- Subprocessor list is generated from `App/app/subprocessors_i18n.py` (named in code; contents not read in this pass). `docs/vendors/` holds vendor evidence (`docs/OPERATIONS.md` § Purging pre-OPS-1 plaintext backups references it).
- Vendors referenced in code: AWS (SES, S3), Stripe, Anthropic, Mistral (optional), Cloudflare (Turnstile, proxy), PostHog (EU), Meta (Conversions API, `App/app/meta_capi.py`), TTLock, Apify (`UBYHOST_APIFY_TOKEN`, `App/app/config.py:183` — `⚠️ UNKNOWN` what it is used for), Google Drive (off-site backups per `docs/OPERATIONS.md`), Better Stack and healthchecks.io (`docs/context/status.md`).
- DPA status per vendor: `⚠️ UNKNOWN` — see `docs/vendors/README.md`.

## Known gaps and open questions
1. Plaintext document and visa number columns remain beside encrypted ones (`db.py:222-225`). Is the plaintext column still written, and can it be dropped?
2. Receipts (`submission.receipt_pdf`) and `response_xml` are plaintext (`db.py:287-291`). Are they personal data for the retention schedule?
3. Retention autopurge is off by default (`config.py:221`). Is it enabled in production? (Env value not in repo.)
4. Backups carry the database and the key in the same archive (`docs/OPERATIONS.md` § Backup). Confirm the age identity custody.
5. AI vendors may receive guest text (guide translation, Leon chat). Confirm the DPA and whether guest data is sent.
6. Meta Conversions API and PostHog: confirm the consent basis (cookie inventory `App/app/cookie_inventory.py`; `docs/privacy/`).
