# UbyHost technical compliance audit

**Review date:** 15 September 2026  
**Scope:** repository behavior and product copy, not production configuration  
**Status:** attorney review required

> This is not legal advice. This document maps repository behavior to repository
> claims and identifies questions for qualified Czech and data-protection counsel.
> It does not conclude that UbyHost complies with Act No. 326/1999 Coll., GDPR, or
> any other law.

## Executive summary

UbyHost implements the core mechanics it describes: it collects UbyPort-shaped
guest fields, distinguishes Czech nationals from reportable foreign nationals,
supports manual, scheduled, and post-verification automatic submission, stores
submission XML and Doručenka PDFs, exports a house book, removes passport uploads
after host verification, and can purge guest rows after six years.

The most important gaps for counsel are:

1. **Child signatures:** every online guest must provide a drawn signature, while
   the current public text of § 103 appears to exempt foreign nationals under 15
   from personally completing and signing the form. There is no age field or
   under-15 signature path.
2. **Passport uploads:** the guest flow makes an ID image/PDF mandatory for every
   non-Czech guest, although the privacy notice calls it optional and the cited
   statute appears to require presenting a document, not necessarily uploading a
   copy. Necessity, legal basis, and special-category risk need counsel review.
3. **Retention and backups:** six-year deletion is a host-triggered application
   action, not a scheduled job. Repository backup scripts retain snapshots by
   count, not by a documented time window, and do not demonstrate the policy's
   claims of encrypted off-site copies or automatic backup purging.
4. **Environment isolation:** deployment files configure staging as mock, but the
   application has no hard guard against `UBYHOST_DEPLOYMENT=staging` with
   `UBYHOST_UBYPORT_ENV=prod`.
5. **Rights and incidents:** exports and record correction exist, but there is no
   dedicated data-subject request, restriction, erasure, breach-case, or
   notification workflow. DPA assistance and notification promises therefore
   depend on manual operator procedures not present in the repository.
6. **Operator identity:** `/legal`, `/terms`, `/privacy`, and `/dpa` use
   `UBYHOST_OPERATOR_*`, but guest notices and some host copy hard-code Josef
   Pechar. Environment overrides can make notices inconsistent.

The statutory cross-check used the consolidated public text of Act No. 326/1999
Coll. and Police developer material available on the review date. It supports
§ 100(c)/(f) as the host duties, § 101 as house-book content/retention, § 102 as
the three-working-day reporting rule, and § 103 as guest document/signature
duties. Counsel must verify the authoritative, effective text and how it applies
to UbyHost's exact service and electronic form.

## Claims vs reality matrix

Status means only consistency between copy and repository behavior:

- **CONSISTENT** — implementation supports the stated product claim.
- **INCONSISTENT** — implementation and copy materially differ.
- **UNCLEAR** — production or operational evidence is outside the repository.
- **NEEDS LAWYER** — the technical facts are known, but legal sufficiency or
  wording requires professional interpretation.

| Claim (source) | Actual behavior | Status | Suggested technical change |
|---|---|---|---|
| Foreign guests are reported within three working days (`App/app/i18n.py`, `legal_intro`; `App/app/host_i18n.py`, `guide.legal.reporting_body`) | Reportable means nationality other than `CZE`; immediate, scheduled, and manual modes can all miss the deadline through configuration or host inaction. Deadline warnings exist (`App/app/validation.py`, `guest_is_reportable`; `App/app/reporting.py`, `due_for_automatic_send`; `App/app/deadlines.py`). | NEEDS LAWYER | Say the tool assists with the deadline but cannot guarantee filing; counsel must approve statutory wording. |
| Duties are under “§§ 101–103,” while the guide cites “§ 100” (`App/app/i18n.py`, `why_law`/`privacy_basis_body`; `App/app/host_i18n.py`, `guide.legal.reporting_body`) | Current public text places general host duties in § 100, house-book rules in § 101, reporting in § 102, and guest duties in § 103. | NEEDS LAWYER | Replace broad citations only after Czech counsel confirms the precise proposition attached to each section. |
| Every guest, including Czech nationals, is written into a “domovní kniha” (`App/app/i18n.py`, `legal_intro`/`why_point_czech`; `App/README.md`, “What it keeps”) | Czech records receive `not_required` and remain in the same guest table/export (`App/app/validation.py`, `CZECH_CODE`; `App/app/reporting.py`, `NOT_REQUIRED`; `App/app/housebook.py`, CSV export). | NEEDS LAWYER | Counsel should distinguish the foreigner house book from any Czech-national evidentiary/local-fee register; UI terminology may need separation. |
| Foreign guests are sent to Police; Czech citizens are not (`App/app/i18n.py`, `why_point_report`/`why_point_czech`) | All nationalities except `CZE`, including EU/EEA nationals, are reportable; Czech records are marked `not_required` (`App/app/validation.py`, `guest_is_reportable`; `App/app/reporting.py`, `collect_sendable`). | CONSISTENT | Add tests for representative EU and non-EU nationalities; counsel must approve the legal description. |
| Completing and signing is every guest's legal duty (`App/app/i18n.py`, `why_point_sign`, `signature_help`) | A signature is required for every online row, including children; `INPASS` changes document handling but not signature handling (`App/app/routes/guest.py`, `guest_form_save`; `App/app/validation.py`, `INPASS`; `App/app/reporting.py`, `guest_issues`). | NEEDS LAWYER | Add an age/under-15 workflow only after counsel defines the required record and who, if anyone, signs. |
| The generated registration PDF stands in for a signed house-book page (`App/app/host_i18n.py`, `guide.legal.paper_body`; `App/app/housebook.py`, module docstring) | A base64 signature image is placed into a generated PDF; imported records can merely carry the literal marker `imported` and no rendered signature image (`App/app/housebook.py`, `registration_form_pdf`/`import_housebook_rows`). | NEEDS LAWYER | Label it “application-generated registration PDF” unless counsel confirms legal equivalence and electronic-signature effect. |
| Foreign guests must upload an ID image/PDF (`App/app/i18n.py`, `why_point_passport`, `legal_notice_passport_body`) | Guest-form save blocks non-Czech guests without a valid JPEG/PNG/WebP/PDF. Host-entered guests do not need an upload (`App/app/routes/guest.py`, `guest_form_save`; `App/app/reporting.py`, `guest_needs_passport_photo`). | CONSISTENT | Clarify the host-entry exception; counsel must approve whether upload may be mandatory. |
| Foreign guests “may upload” an ID image/PDF (`App/app/i18n.py`, `privacy_passport_photo_body`; `App/app/privacy_policy_i18n.py`, `privacy.s05_body`; `App/app/dpa_i18n.py`, `dpa.s05_body`) | The online guest flow requires it, so it is not optional for that channel (`App/app/routes/guest.py`, `guest_form_save`). | INCONSISTENT | Describe actual channel-specific behavior, but lawyer must approve necessity and lawful-basis language first. |
| ID upload is visible only to the host (`App/app/i18n.py`, `legal_notice_passport_body`/`privacy_passport_photo_body`) | The authenticated admin route is owner-scoped; the operator and infrastructure necessarily can have technical access (`App/app/routes/admin.py`, passport route; `App/app/access.py`; `App/app/passport_photos.py`, `read_photo`). | INCONSISTENT | Use “available in the app only to authorized host users; infrastructure/operator access is restricted” if operationally true; lawyer must approve. |
| ID upload is deleted immediately after verification (`App/app/i18n.py`, `why_point_passport`/`legal_notice_passport_body`) | Explicit verification and send-as-verification delete the file and clear its marker. Unverified files remain until a 12-hour sweep sees a stay ended more than 30 days ago (`App/app/reporting.py`, `record_host_identity_confirmation`; `App/app/passport_photos.py`, `purge_stale`; `App/app/scheduler.py`, photo sweep). | CONSISTENT | Add the 30-day unverified fallback to the notice; lawyer must approve the retention statement. |
| ID upload is not sent to Police (`App/app/i18n.py`, `legal_notice_passport_body`/`privacy_passport_photo_body`) | UbyPort payload contains text fields, not the upload (`App/app/reporting.py`, `guest_payload`; `App/app/ubyport/soap.py`, request construction). | CONSISTENT | Keep a regression test asserting attachments cannot enter request XML. |
| Registration data/signature is retained six years from the last house-book entry, then deleted (`App/app/i18n.py`, `legal_notice_retention_body`/`privacy_retention_body`) | Expiry is calculated per guest from stay end, not globally from the last book entry. Deletion runs only when a host invokes Settings purge; no scheduled six-year purge exists (`App/app/housebook.py`, `expired_guest_ids`/`purge_expired`; `App/app/routes/admin.py`, `purge_expired_records`; `App/app/scheduler.py`). | INCONSISTENT | Align the retention trigger and automate a reviewed purge policy; lawyer must approve the legal period. |
| Archives hide records; only retention purge permanently deletes them (`App/app/host_i18n.py`, `archive.retention_note`) | Archive is soft deletion. Unsent guests can also be hard-deleted individually; sent guests cannot (`App/app/routes/admin.py`, archive routes/`guest_delete`). | INCONSISTENT | Amend UI copy to mention deletion of unsent entries, or route all deletion through one documented policy. |
| Encrypted server/off-site backups are retained briefly and automatically purged (`App/app/privacy_policy_i18n.py`, `privacy.s11_body`; `App/app/dpa_i18n.py`, `dpa.s15_body`) | `App/scripts/backup_data.sh` and `deploy/lightsail/scripts/backup.sh` copy the SQLite database and keys and retain ten snapshots. Off-site Drive/S3 scripts are optional. Repository code does not establish encryption, a time window, or deletion propagation from live data to old backups. | UNCLEAR | Publish the actual backup inventory, encryption layer, cadence, restore access, and expiry; avoid promises until production evidence exists. Lawyer must approve. |
| Settings shows backup status and production creates encrypted backups (`App/app/host_i18n.py`, `guide.security.backups`) | No application backup-status implementation was found. Operational scripts exist outside the app (`App/scripts/backup_data.sh`; `deploy/lightsail/scripts/`). | INCONSISTENT | Remove the status claim or implement monitored status from the real backup job; describe encryption only when verified. |
| Immediate mode sends after host verification (`App/app/host_i18n.py`, `guide.reporting.immediate_detail`) | Guest save alone does not submit. Host save/verification can invoke immediate submission (`App/app/reporting.py`, `try_immediate_submit`; `App/app/routes/admin.py`, verify/save routes). | CONSISTENT | Keep this wording and regression tests. |
| Immediate mode sends “the moment the guest signs” (`App/README.md`, “Choosing how much it does by itself”) | Guest save does not directly submit; host action is required. | INCONSISTENT | Say “after the host verifies the guest” in README. |
| Scheduled mode sends after check-in plus configured delay; manual requires a host click (`App/app/host_i18n.py`, `guide.reporting.*`) | `due_for_automatic_send` applies the delay and manual mode is excluded from automatic sweeps (`App/app/reporting.py`, `due_for_automatic_send`/automatic sweep). | CONSISTENT | State that incomplete, unverified, rejected, or misconfigured records still require host action. |
| Accepted records are not automatically resent; duplicates are blocked (`App/README.md`, duplicate warning; `App/app/host_i18n.py`, resend copy) | Submission claims prevent concurrent sends; sent rows are skipped unless deliberate resend is requested; duplicate-classified blocked rows are not resent (`App/app/reporting.py`, `claim_sendable`/`collect_sendable`/`submit_batch`). | CONSISTENT | Retain the warning and periodically verify Police error-code mapping. |
| Staging/mock never sends to Police (`docs/DEPLOYMENT.md`; `App/app/terms_i18n.py`, `terms.s07_body`; `App/app/host_i18n.py`, environment banners) | Checked-in deployment defaults set staging to mock, but `endpoint_for` trusts `UBYHOST_UBYPORT_ENV`; there is no staging→prod prohibition (`App/app/config.py`, `endpoint_for`; `App/app/reporting.py`, `client_for`; `render.yaml`; `App/render_start.sh`). | INCONSISTENT | Add a fail-closed environment invariant or qualify documentation as configuration, not guarantee. |
| Demo records never reach real Police (`App/app/terms_i18n.py`, `terms.s14_body`; `App/app/host_i18n.py`, `guide.demo.body`) | Demo isolation relies on environment configuration; no per-record “demo” prohibition at the UbyPort client boundary was identified (`App/app/reporting.py`; `App/app/config.py`). | UNCLEAR | Add a data-level demo guard before any non-mock submission. |
| Doručenka PDF and exact sent XML are stored (`App/README.md`, “What it keeps”) | Submission rows store receipt/error PDF, request XML, response XML, pseudo-stamp, endpoint, and per-record outcome (`App/app/db.py`, `submission` schema; `App/app/reporting.py`, `submit_batch`; `App/app/ubyport/soap.py`). | CONSISTENT | Define retention/export/deletion behavior for submission artifacts; lawyer must approve period. |
| The app keeps an audit log of “everything” (`App/README.md`, “What it keeps”) | Many security, guest, retention, and submission actions are audited, but coverage is not universal. Hosts see only the latest 500 rows, while all rows remain in SQLite; no audit retention job exists (`App/app/db.py`, `audit`; `App/app/routes/admin.py`, settings query). | INCONSISTENT | Replace “everything” with an enumerated event list; define audit retention and access. |
| Host can export and Operator assists with rights (`App/app/privacy_policy_i18n.py`, `privacy.s14_body`; `App/app/dpa_i18n.py`, `dpa.s12_body`/`dpa.s15_body`) | House-book/stay CSV and registration-PDF exports exist. There is no dedicated access, portability, restriction, objection, anonymization, or instructed-erasure workflow. Unsent guests can be deleted; sent guests cannot (`App/app/housebook.py`; `App/app/routes/admin.py`, export/`guest_delete`). | UNCLEAR | Document the manual request runbook and add scoped export/restriction/deletion tools after counsel defines exceptions. |
| No automated decision-making or profiling (`App/app/privacy_policy_i18n.py`, `privacy.s15_body`; `App/app/i18n.py`, `privacy_rights_body`) | Deterministic validation, status classification, bot/rate-limit checks, and scheduling occur, but no decision with an identified legal/similarly significant effect was found (`App/app/validation.py`; `App/app/reporting.py`; `App/app/rate_limit.py`; `App/app/turnstile.py`). | NEEDS LAWYER | Counsel should confirm that refusal-related form blocking and security scoring are described accurately. |
| Party size is collected because feeds do not provide it (`App/app/routes/guest.py`, `set_party_size` docstring; `App/app/i18n.py`, `party_question`) | The declared count is stored on the reservation and used for completeness; it is not in the Police payload (`App/app/db.py`, `reservation.declared_guests`; `App/app/reporting.py`, `expected_guest_count`/`guest_payload`). | NEEDS LAWYER | Add party-size purpose and retention to the guest notice, or avoid persistence if only transient coordination is needed. |
| Optional e-mail may be stored for manual stays (`App/app/db.py`, `reservation.guest_email`; `App/app/routes/admin.py`, manual stay fields) | E-mail is reservation metadata and is not sent in `guest_payload`; guest privacy categories do not clearly mention it (`App/app/reporting.py`, `guest_payload`; `App/app/i18n.py`, `privacy_data_body`). | INCONSISTENT | Add a purpose/retention disclosure or remove the field; lawyer must approve. |
| Controller is the host-configured legal entity; Operator is processor for Guest Data (`App/app/terms_i18n.py`, `terms.s03_body`/`terms.s05_body`; `App/app/privacy_policy_i18n.py`, `privacy.s03_body`; `App/app/dpa_i18n.py`, `dpa.s03_body`) | Guest privacy resolves the apartment's legal entity; owner scoping separates host accounts; operator details come from config on legal routes (`App/app/routes/guest.py`, `_controller`; `App/app/access.py`; `App/app/operator.py`; `App/app/routes/legal.py`). | CONSISTENT | Counsel should verify role allocation for support, security, backups, and independent operator purposes. |
| Guest notice identifies the software operator (`App/app/i18n.py`, `privacy_processor_body`) | This string hard-codes ***REMOVED*** while `/legal` uses `UBYHOST_OPERATOR_*` (`App/app/config.py`; `App/app/operator.py`; `App/app/routes/legal.py`). | INCONSISTENT | Render operator identity dynamically in guest notices and all legal copy. |
| Host must configure a complete controller identity/contact (`App/app/privacy_policy_i18n.py`, `privacy.guest_note`) | The guest privacy page can fall back to “ask your host” when controller details are missing (`App/app/i18n.py`, `privacy_controller_missing`; `App/app/routes/guest.py`, `_controller`). | INCONSISTENT | Block publication/live use until required controller fields are complete; lawyer must define required fields. |
| Subprocessors include AWS Lightsail, Render, Cloudflare, Drive/S3, and support/e-mail tools (`App/app/privacy_policy_i18n.py`, `privacy.s09_body`; `App/app/dpa_i18n.py`, `dpa.s11_body`) | Repository deployment docs support Lightsail, Render, Cloudflare, and optional Drive/S3 scripts; actual enabled services, regions, contracts, and support tools cannot be verified from code (`docs/DEPLOYMENT.md`; `docs/LIGHTSAIL.md`; `docs/CLOUDFLARE.md`; `deploy/lightsail/`). | UNCLEAR | Maintain an instance-specific subprocessor register and change-notice process; lawyer must approve DPA mechanism. |
| Data stays in the EU / processing is primarily EEA (`App/app/i18n.py`, `privacy_recipients_body`; `App/app/privacy_policy_i18n.py`, `privacy.s10_body`; `App/app/dpa_i18n.py`, `dpa.s17_body`) | Police transfer is Czech. Repository docs suggest EU hosting, but Cloudflare, support tools, and optional backup locations/transfer paths are not established by code (`docs/DEPLOYMENT.md`; `docs/CLOUDFLARE.md`; deployment scripts). | UNCLEAR | Replace absolute “stays within the EU” unless production data-flow and vendor-region evidence supports it; lawyer must approve transfer language. |
| Security includes encrypted credentials, HTTPS/HSTS, production TOTP, Cloudflare controls, isolation, and backups (`App/app/privacy_policy_i18n.py`, `privacy.s12_body`; `App/app/dpa_i18n.py`, `dpa.s10_body`) | Credential/TOTP encryption and authentication controls exist; HTTPS/Cloudflare/backups are deployment concerns. SQLite guest fields and local backup copies are not application-encrypted (`App/app/db.py`; `App/app/auth.py`; `docs/CLOUDFLARE.md`; `App/scripts/backup_data.sh`). | UNCLEAR | Split code-enforced controls from operator-configured controls and verify the live technical-organisational-measures inventory. |
| Operator will notify on personal-data breaches (`App/app/privacy_policy_i18n.py`, `privacy.s18_body`; `App/app/dpa_i18n.py`, `dpa.s14_body`) | Submission/PIN alerts exist, but no breach register, assessment, contact escalation, regulator/data-subject notice, or tested notification workflow was found (`App/app/alerts.py`; `App/app/routes/guest.py`; `docs/SECURITY.md`). | UNCLEAR | Create and test an operational incident/breach runbook; do not imply the app performs notification. Lawyer must approve thresholds and deadlines. |
| DPA supports audit and Article 28 information (`App/app/dpa_i18n.py`, `dpa.s16_body`) | The DPA promises a manual contractual process; no evidence package, certification, audit portal, or request workflow is implemented (`App/app/templates/dpa.html`; `App/app/routes/legal.py`). | UNCLEAR | Maintain a current TOMs/data-flow/subprocessor/retention evidence packet and named request owner. |
| The app helps with records of processing (`App/app/dpa_i18n.py`, `dpa.review_body`) | Copy expressly says it does not replace the host's records of processing. No RoPA generator exists (`App/app/dpa_i18n.py`; `App/app/templates/guide.html`). | CONSISTENT | Keep this limitation prominent. |
| Legal pages display version 1.2 dated 15 September 2026 (`App/app/terms_i18n.py`, `terms.effective`; `App/app/privacy_policy_i18n.py`, `privacy.effective`; `App/app/dpa_i18n.py`, `dpa.effective`) | Acceptance audit defaults identify versions as 1.1 (`App/app/config.py`, `TERMS_VERSION`/`PRIVACY_VERSION`/`DPA_VERSION`). | INCONSISTENT | Align configured versions with displayed versions and test them from one source of truth. |

## Guest-facing vs host-facing gaps

- Guest copy calls the ID upload both mandatory and optional. Host/DPA copy calls
  it optional even though the online foreign-guest path cannot submit without it.
- “Only the host sees it” omits restricted operator/infrastructure access and is
  stronger than the technical access model.
- Guest copy says data remains in the EU, while host policy uses qualified
  Chapter V transfer language.
- Guest copy says six years from the last house-book entry; code calculates each
  row from stay end and relies on a host clicking purge.
- Guest copy says every person, including children, must sign. Host guide also
  says signatures are mandatory, but neither exposes the under-15 issue for
  counsel review.
- English is the foreign-guest default (`App/app/i18n.py`,
  `DEFAULT_LANGUAGE`), with Czech available. Whether an English-first interface
  can serve as the relevant Czech statutory document is a question for counsel;
  translations should be legally reviewed as paired texts.
- Host guide accurately describes post-verification immediate sending, while the
  README previously described sending on guest signature.
- Host copy advertises backup status and encryption that the application itself
  does not verify.
- Guest notices hard-code the operator; host legal routes use environment-driven
  operator data.

## Operator obligations for a hosted third-party service

If ***REMOVED*** operates the hosted instance for third-party hosts, the
following repository-backed facts must remain accurate operationally:

1. `UBYHOST_OPERATOR_NAME`, `_ICO`, `_DIC`, `_ADDRESS`, `_EMAIL`, and
   `_REGISTRY_URL` in `App/app/config.py` must identify the actual contracting
   operator. Hard-coded identities in `App/app/i18n.py` and
   `App/app/host_i18n.py` must match until made dynamic.
2. `/legal`, `/terms`, `/privacy`, and `/dpa` are rendered with
   `App/app/operator.py` through `App/app/routes/legal.py`; changes to entity,
   contact, deployment, support, or subprocessors require a coordinated EN/CS
   review and version update.
3. Each host must configure the actual controller legal entity and contact for
   every property. The current fallback is not a complete identity.
4. The production inventory must record which of Lightsail, Render, Cloudflare,
   Google Drive, S3, e-mail, and support systems actually process personal data,
   where, under which account/region, and under what retention.
5. Operator procedures—not application features—must currently handle data
   subject requests, deletion/return on termination, DPA audit requests,
   subprocessor objections/change notices, and breach notifications.
6. Deployment controls must verify `deployment`, `ubyport_env`, endpoint,
   credentials, backups, restore tests, TOTP, proxy trust, and controller details
   before live guest data is accepted.
7. Stored request/response XML, Doručenka/error PDFs, audit rows, logs, database
   snapshots, and key material need explicit owners and retention schedules.

## Risk-ranked attorney review list

### P0 — police submission, identity document, signature, or retention claims

1. Confirm the exact statutory sections and scope for host reporting, house-book
   content, retention, guest presentation of documents, signatures, children
   under 15, Czech nationals, and EU nationals.
2. Decide whether making a passport/ID copy mandatory is necessary and
   proportionate, and identify the lawful basis for that copy separately from
   the underlying registration fields.
3. Determine whether a drawn signature image in an application-generated PDF
   has the claimed legal effect, including for imported records.
4. Reconcile “six years from last entry” with per-row expiry, manual purge, all
   submission artifacts, audit records, server logs, and backups.
5. Require a hard technical separation preventing staging/demo data from
   reaching production Police endpoints.

### P1 — GDPR-shaped notice and DPA gaps

1. Complete purposes/categories for party size, manual-stay e-mail, IP address,
   audit/security logs, attachment metadata, submission artifacts, and support.
2. Replace hard-coded operator identity and incomplete controller fallback.
3. Verify subprocessors, regions, international transfers, safeguards, notice
   of changes, and “data stays in the EU.”
4. Document actual rights-assistance, deletion/return, backup expiry, incident
   notification, and audit-evidence procedures promised in the DPA.
5. Assess whether systematic guest-link/security monitoring or identity-document
   processing triggers a DPIA, and whether document images may reveal special
   categories.
6. Define separate Operator-controller legal bases and retention for host
   accounts, security logs, support, and billing.

### P2 — clarity and operational accuracy

1. Replace absolutes such as “everything,” “only,” “never,” and “immediately”
   where exceptions exist.
2. Keep README, guide, banners, and legal pages synchronized on submission modes.
3. Define audit-log visibility and retention.
4. Add instance-specific “last verified” dates for subprocessors, hosting,
   backups, and security controls.
5. Have bilingual counsel review EN/CS semantic parity, not merely key parity.

## Questions for counsel

- Which exact subsections of §§ 100–103 support each reporting, house-book,
  presentation, signature, and retention sentence?
- May or must Czech-national records be kept in the same “domovní kniha,” or
  should UbyHost present a separate register?
- Must all EU/EEA/Swiss nationals be reported by an accommodation provider in
  this context, and are there exceptions the binary `CZE` rule misses?
- What must be signed, in what form, and by whom for guests under 15 or guests
  using a parent's document?
- Is a drawn signature image embedded in a generated PDF sufficient for the
  product's claimed purpose?
- Is retaining a passport/ID image necessary and proportionate when the host can
  inspect the document without retaining a copy?
- If an image may reveal ethnic origin, health, religion, or other special
  categories, what additional basis and safeguards are required?
- What is the correct retention anchor for database rows, signed forms,
  Doručenka/error PDFs, XML, audit logs, server/security logs, and backups?
- Which guest and host purposes/legal bases must be listed separately?
- Is the controller/processor allocation accurate for security monitoring,
  support access, fraud prevention, backups, and Police transmission?
- What minimum controller identity/contact must appear before a guest form can
  be used?
- Does the subprocessor/change-objection mechanism and transfer wording meet the
  intended hosted-service arrangement?
- What manual or technical functionality is required to substantiate access,
  correction, restriction, portability, objection, erasure, and deletion/return
  promises?
- Does this processing require a DPIA or DPO, and if not, should the notice say
  anything about those conclusions?
- What breach-assessment, documentation, notification, and communication
  procedure must exist behind the policy promise?
- Is English-first guest copy acceptable for the statutory form/notice, and what
  Czech-language text must be controlling?
- How should failed, late, corrected, and duplicate Police submissions be
  described without implying successful filing?

## Technical verification boundaries

This review read the application, templates, tests, and checked-in deployment
material. It did not verify live cloud settings, executed vendor contracts,
backup objects, restore tests, log stores, support inboxes, Police credentials,
or the authoritative legal effect of cited sources. Official UbyPort appendix 5
describes the web-service interface; the repository's statement that § 10.5
“requires first-save validation” is a paraphrase that should be checked against
the full current operating rules by counsel and the integration owner.
