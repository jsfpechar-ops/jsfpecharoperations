# Retention schedule

**Status:** input for counsel. It matches the code as of this plan; the periods
marked **counsel** are not yet signed off, and the retention job that applies
them ships **dry-run** until `UBYHOST_RETENTION_AUTOPURGE=1` (decision G-D4).

The six-year house-book duty is a floor under § 101 of Act 326/1999 Coll. and,
under the GDPR storage-limitation principle, also a ceiling.

## What the code deletes or minimises

| Data item | Where | Trigger | Period | Mechanism (code path) | Basis |
|---|---|---|---|---|---|
| Guest record (name, DOB, nationality, residence, purpose, stay dates, signature) | `guest` | stay end | 6 years (**counsel**: per-row vs "last entry", G-D4) | `retention.py` guest step → `housebook.purge_expired` | § 101 Act 326/1999 |
| Travel document / visa number | `guest.doc_number_enc` / `visa_number_enc` | stay end | same as guest record | same step | § 101 |
| Optional passport/ID image | `DATA_DIR/passport_photos/…` | verification, archive, or stay end + 30 d | 30 days after stay end | `passport_photos.purge_stale` (12 h sweep); delete on verify/archive | Proportionality (Art 5(1)(e)) |
| Claim e-mail | `reservation_claim.email` | stay end | 30 days (G-D5) | `retention.py` claim-email step | Storage limitation |
| Reservation e-mail / phone fragment | `reservation.guest_email`, `phone_last4` | stay end | 30 days (G-D5) | `retention.py` reservation-contact step | Storage limitation |
| Submitter IP | `guest.filled_ip` | stay end | 90 days (G-D6, counsel) | `retention.py` submitter-IP step | Dispute evidence window |
| Empty reservations | `reservation` | six-year cutoff | 6 years | `retention.py` empty-reservation step | § 101 |
| Submission envelopes (XML with doc numbers) | `submission.request_xml`, `response_xml` | submission created | 90 days | `reporting.purge_submission_payloads` (12 h sweep) | Minimisation |
| Orphaned submissions | `submission` | six-year cutoff, no guest points at it | 6 years | `housebook.purge_orphan_submissions` | § 101 evidence |
| Invoices | `invoice`, `invoice_item` | issue date | 10 years | `invoices.purge_expired` | Accounting law |
| Mail rows | `email_outbox`, `console_mail_log` | created | 14 days | `mail.purge_old` | Minimisation |
| Audit rows | `audit` | created | 3 years, except `legal_accepted` (G-D7) | `retention.py` audit step | Accountability |
| Acceptance evidence | `legal_acceptance` | account disabled + 3 years | life of account + 3 years (G-D7) | `retention.py` acceptance step | Accountability |
| Resolved alerts | `alert` | resolved | 12 months (G-D7) | `retention.py` alert step | Operations |
| Rate-limit events | `rate_limit_event` | created | 24 hours (G-D7) | `retention.py` rate-limit step | Security |
| Login links | `login_token` (hash, account, address, purpose, times) | expiry | 1 day after expiry; deleted with the account | `retention.py` login-token step (`login_link.purge`) | Security |
| Passkeys | `passkey` | created | until removed by the host or the account is deleted | `retention.py` workspace deletion; cascade | Contract |
| WebAuthn challenges | `webauthn_challenge` | expiry (5 min) | 1 day after expiry | `retention.py` webauthn-challenge step (`passkeys.purge`) | Security |
| Door code PIN | `door_code.pin_enc` | code expiry | 1 day after the code expires | `retention.py` door-code-PIN step | Minimisation |
| TTLock connection (UbyHost-made TTLock user, its encrypted password and tokens, cached lock list) | `lock_account` | host removes it, or the account is deleted | until then | Smart locks page Remove; cascade from user_account | Contract |
| Container logs | Docker `json-file` | rotation | 5 × 10 MB per service | `docker-compose.yml` `logging:`; uvicorn access log off (OPS-3) | Security |
| Encrypted backups | `/data/backups`, Drive, S3 | snapshot age | 30 days local/off-site (G-D3) | `backup_data.sh` `UBYHOST_BACKUP_RETENTION_DAYS`; S3 lifecycle | Disaster recovery |

## Copy alignment (pending counsel)

The published copy still says the six-year clock runs "from the last entry" in
one place while the code computes it per guest from the stay end. The strings to
reconcile are `privacy_retention_body` in `i18n.py`, § 11 of
`privacy_policy_i18n.py` and § 15 of `dpa_i18n.py`. LD-3 lists these as
LEGAL-GATED COPY but gives no replacement wording, so they were left as the
approved text; counsel must supply the wording (see `docs/archive/FOLLOWUPS.md`). The same
change covers the false "encrypted backups" claim in those two documents.
