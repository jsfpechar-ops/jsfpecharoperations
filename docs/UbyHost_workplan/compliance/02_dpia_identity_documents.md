# DPIA: guest identity document data and ID photos (Art. 35 GDPR)

Internal document. Not published, but share it with a host on request (DPA § 13 says UbyHost provides information to help the host with its own DPIA).
Reasoned drafting, not attorney advice. Facts are from the code at commit `8691757`. Replaces the engineering note `docs/privacy/DPIA.md` once approved.

| Item | Value |
|---|---|
| Prepared by | [OWNER TO FILL: name], operator of UbyHost, as processor |
| Date | 4 October 2026 |
| Next review | 4 October 2027, or earlier if the ID photo feature, the retention rule, the hosting region or the admin support access changes |
| Controllers | Each host (accommodation provider). The host remains responsible for its own DPIA (Art. 35(1)). This document is the processor's assessment the host can rely on and adapt |

## 1. Is a DPIA needed? [Je DPIA nutná?]

Position: yes, do one, even if not strictly mandatory.

- Identity document numbers are not special-category data, but the EDPB criteria (WP248 rev.01) count "data of a highly personal nature" and "large scale" as risk factors. One platform holds many hosts' guest records, and the data enables identity fraud. Two criteria are met: sensitive data (document numbers, document images that can show a face) and data about vulnerable people (children are entered on a parent's passport). A third may apply over time (scale across many controllers).
- Photos of a face are not biometric data under Art. 9 unless processed with technical means for unique identification (Recital 51). UbyHost does no face matching, OCR or MRZ reading. So Art. 9 does not apply. [Interpretation]
- The ÚOOÚ list of processing that needs a DPIA [UNVERIFIED: list not opened this session] should be checked once. The conclusion does not depend on it.

## 2. Description of the processing [Popis zpracování]

| Element | What happens (from the code) |
|---|---|
| Data collected | Text fields on the guest form: surname, first name, birth date, nationality, travel document number, visa number, residence abroad, purpose of stay, stay dates, drawn signature. For children listed on a parent's passport, the parent's document number (`child_in_passport`). |
| Optional ID file | A property setting `passport_photo_policy` with two values: `off` (default) and `required_foreign`. When on, a foreign guest must upload a photo (max. 5 MB) or PDF (max. 15 MB) of the document. Images are re-encoded and all metadata (EXIF, GPS) is stripped (`passport_photos.reencode_image`). |
| How the guest gets in | A private link (`/l/{token}` or the readable `/l/{name}-{code}`), plus a 6-digit PIN given by the host. |
| Where it is stored | SQLite database on AWS Lightsail, Frankfurt (eu-central-1). ID files in `/data/passport_photos`, encrypted. |
| Who sees it | The host's users. The UbyHost admin only in support mode, with identity data masked (section 5). |
| Where it goes | Text fields for foreign guests go to the Police of the Czech Republic through the UbyPort web service with the host's own web-service credentials. ID files and signatures never go to the police (`reporting.guest_payload` has no file field). |
| How long | Text fields: 6 years after the stay ends (§ 101(4) zákon 326/1999 Sb.). ID files: deleted on verification, otherwise 7 days after check-in, never later than 30 days after upload. UbyPort XML envelopes: 90 days. Backups: 30 days (nightly archives), 7 days (Litestream). |

## 3. Necessity and proportionality [Nezbytnost a přiměřenost]

| Question | Answer |
|---|---|
| Legal basis (host's) | Art. 6(1)(c): § 101 to § 103 zákon 326/1999 Sb. require the house book and the police report with the document number. Children on a parent's passport: the police guidance says to enter the parent's document number and a note (Policie ČR, "Vyplňování přihlašovacího tiskopisu", rubrika 6 point 7). |
| Is every text field needed? | Yes. The fields match the statutory record and the UbyPort `Ubytovany` structure (`cSurN`, `cFirstN`, `cDate`, `cNati`, `cDocN`, `cVisN`, `cResi`, `cPurp`, `cNote`). Fields the police mark as unused (`cPlac`, `cSpz`) are sent empty. |
| Is the ID photo needed? | No statute requires a copy of the document. It is only a check tool for hosts who cannot see guests in person. That is why it is off by default, kept for days, not years, and never sent on. A host that turns it on must decide it is necessary for its property (DPA § 5). [UNVERIFIED: the Czech ID card act limits copying of a Czech občanský průkaz; foreign guests are the only ones asked when the policy is `required_foreign`] |
| Minimisation | Metadata stripped from images. Czech guests are not reported. Contact e-mail is masked on guest screens and deleted 30 days after the stay. Document numbers are masked to the last 3 characters for the admin. |
| Accuracy | Field validation (`validation.py`), allowed-character rules, nationality code list. Hosts can correct a record; a corrected filing is re-sent by the host. |
| Transparency | Guest privacy notice on the form names the controller (host entity) and UbyHost as processor; the acknowledgement version, language and time are stored. |
| Rights | Guests contact the host. UbyHost provides a per-guest export (`/guests/{id}/export.json`) and a request register (`/privacy-requests`). Erasure is limited by the 6-year duty. |
| Processor terms | DPA at `/dpa`; subprocessors at `/subprocessors`; all in the EEA except Cloudflare (edge, DPF and SCCs). |

## 4. Risks [Rizika]

Scale: likelihood and severity each Low, Medium, High. Risk is to the guests, not to UbyHost.

| # | Risk | Source | Likelihood before measures | Severity | Inherent risk |
|---|---|---|---|---|---|
| R1 | Someone other than the guest opens the form and reads or alters data (shared or guessed link) | Link forwarded in a chat, guessing of the readable link, PIN brute force | Medium | Medium | Medium |
| R2 | Mass theft of guest records from the server or database | Server compromise, stolen credentials of the owner, vulnerability in the app | Low | High (identity fraud, document numbers for many people) | High |
| R3 | Leak through backups | S3 bucket made public, leaked IAM key, archive copied elsewhere | Low | High | Medium |
| R4 | Unauthorised reading by the processor's own admin | Support session, curiosity, compromised admin account | Low | High | Medium |
| R5 | One host sees another host's guests | Missing ownership check | Low | High | Medium |
| R6 | ID photos kept longer than needed | Host never verifies; job fails | Medium | Medium (images are richer than text) | Medium |
| R7 | Data reaches the wrong recipient | Wrong e-mail for claim link, wrong UbyPort account | Medium | Low to Medium | Medium |
| R8 | Wrong or missing police report | UbyPort outage, rejected record, misconfigured credentials | Medium | Medium for the host (fine), Low for the guest | Medium |
| R9 | Encryption key loss makes records unreadable | Loss of `UBYHOST_DATA_KEYS` | Low | Medium (house book cannot be shown at inspection) | Low to Medium |
| R10 | Children's data handled like adults' | Under-15 path, parent's passport | Medium | Medium | Medium |

## 5. Measures in place [Přijatá opatření]

All of these are in the code or deploy configuration today.

| Risk | Measure | Where |
|---|---|---|
| R1 | 100-bit link token plus 6-digit PIN; PIN cookie bound to the token and current PIN, valid 7 days; rotating the PIN ends old sessions | `auth.py`, `routes/guest.py` |
| R1 | PIN rate limit 10 failures per 15 minutes per IP and token, progressive delay, constant-time compare | `rate_limit.py`, `SECURITY.md` |
| R1 | Cloudflare Turnstile after 3 wrong PINs and on claim/resend; backend checks token, action, hostname and IP | `turnstile.py` |
| R1 | Repeated PIN failures create an audit event, a host warning, and an `incident_review` alert (5 rate-limited links in 24 h) | `incidents.suggest_review_if_frequent` |
| R1 | Readable link (about 30 bits) only leads to the PIN page, never to data | `SECURITY.md`, `guest_slug.py` |
| R2 | Field encryption with MultiFernet: document and visa numbers, birth date, street and town, signatures, UbyPort password, UbyPort request envelope. Keys in `UBYHOST_DATA_KEYS`, outside the database | `db.py`, WP16 |
| R2 | ID files encrypted on disk | `passport_photos.save_photo` (`db.encrypt_blob`) |
| R2 | Host TOTP 2FA required in production; Cloudflare managed challenges and leaked-credential checks on login | `auth.py`, `docs/CLOUDFLARE.md` |
| R2 | Logs carry route templates only, no tokens; access log off | OPS-3 |
| R3 | Nightly backups encrypted with `age`, private key held offline, 30 days | `backup.sh`, OPS-1 |
| R3 | Litestream replica to a private S3 bucket in eu-central-1: Block Public Access on, SSE-S3, versioning, dedicated IAM user limited to the prefix. The replica has no data keys and no ID photos, so encrypted fields stay unreadable | `litestream.yml`, `deploy/lightsail/README.md` |
| R4 | Admin support mode masks document and visa numbers to the last 3 characters and holds back signatures, photos and identity exports. One guest can be revealed only with a typed reason, which is audited (`guest_identity_revealed`) | `access.identity_visible`, `routes/admin.py` |
| R4 | Every impersonation, reveal, export and photo view is audited with the real actor | `db.audit`, BE-6 |
| R5 | All host queries go through ownership joins on `owner_user_id` | `access.py` |
| R6 | Deletion on verification; 12-hourly sweep deletes files 7 days after check-in and at most 30 days after upload, even if the host never acts; orphan sweep | `passport_photos.purge_stale`, `scheduler._job_photo_sweep` |
| R6 | Feature off by default; only `required_foreign` exists | `routes/admin.py` |
| R7 | Claim e-mail rate limits per IP, recipient and stay; claim secret hashed; address masked on screens | `claim.py` |
| R8 | Deadline warnings, rejection and transport alerts, "outcome unknown" state with advice to check in the UbyPort web application before resending, duplicate protection | `reporting.py`, `deadlines.py` |
| R8 | Host terms § 10: host checks status and files by hand when needed; manual filing guide (`05_manual_filing_fallback.md`) | `terms_i18n.py` |
| R9 | Owner keeps a copy of the keys in a password manager; restore test script | `deploy/lightsail/scripts/restore_test.sh` |
| R10 | Child entered with the parent's document number, following police guidance | `validation.py` (`INPASS`) |
| All | Incident register and breach runbook | `/admin/incidents`, `03_breach_response_runbook.md` |

## 6. Residual risk [Zbytkové riziko]

| # | Residual likelihood | Residual severity | Residual risk | Why |
|---|---|---|---|---|
| R1 | Low | Medium | Low | PIN, rate limits and Turnstile make guessing impractical. A forwarded link with its PIN still works for 7 days: this depends on the host. |
| R2 | Low | Medium | Medium | Names and stay dates remain in clear text in the database and the Litestream replica. Encrypted fields protect the most harmful data only while the keys stay off the same machine image. The keys are on the server at runtime, so a full server compromise exposes everything. |
| R3 | Low | Medium | Low | Private bucket, encrypted fields; clear-text names remain in the replica. |
| R4 | Low | Medium | Low | Solo operator with full server access can bypass the app. Mitigated by audit and personal commitment, not by technology. |
| R5 | Low | High | Low | Central ownership checks; keep them covered by tests. |
| R6 | Low | Low | Low | Hard cap of 30 days enforced by the job. |
| R7 | Low | Low | Low | |
| R8 | Medium | Low (for guests) | Low | Host's own fallback. |
| R9 | Low | Medium | Low | Depends on the owner's key copy. |
| R10 | Medium | Low | Low | Legal effect of the drawn signature for children is still open. [UNVERIFIED] |

Remaining improvements, not blockers:
1. Encrypt surname, first name and nationality too, or accept the clear text for search and sorting (`FOLLOWUPS.md` W2.2).
2. Turn on `UBYHOST_RETENTION_AUTOPURGE=1`, so the 6-year deletion actually runs.
3. Test a full restore every quarter and record it.
4. Keep 2FA on AWS, Cloudflare, GitHub and the mailbox [OWNER TO CONFIRM].

## 7. Conclusion [Závěr]

The processing is necessary for the hosts' statutory duties, and the optional ID photo is limited in time and scope. With the measures in section 5, the residual risk is low to medium, not high. Prior consultation with the ÚOOÚ under Art. 36 is therefore not required. Re-assess if UbyHost ever adds automatic reading of documents (OCR, MRZ, face matching), keeps ID photos longer, or moves data outside the EEA.

Sign-off: [OWNER TO FILL: name, date].
