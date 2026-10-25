# Records of processing (Article 30 GDPR)

**Status:** input for counsel. It records what the code actually does; a
qualified Czech/EU data-protection lawyer should confirm the lawful bases and
the retention periods before it is relied on. Companion: `RETENTION.md` (LD-3),
`INCIDENT_RESPONSE.md` (LD-5), `docs/vendors/README.md` (LD-9).

## A. Processor record — guest data (Art 30(2))

UbyHost is a **processor** for the guest data that each accommodation provider
(the **controller**) collects. The controller is the provider's operating legal
entity, or an alternate controller configured per property
(`apartment.data_controller_entity_id`, else `apartment.legal_entity_id`).

| Item | Detail |
|---|---|
| Controller | Each host's legal entity or its configured alternate controller |
| Processor | The UbyHost operator (`config.OPERATOR_*`) |
| Categories of data subjects | Guests staying at the controller's property |
| Categories of personal data | Name, birth date, nationality, permanent residence; travel document and visa numbers (Fernet-encrypted at rest); drawn signature; optional passport/ID image or PDF (default **off**); stay dates; submitter IP; the e-mail/phone used to claim the stay; police submission envelopes; Doručenka/error PDFs; when the host uses door codes, the door code and its validity times (encrypted, deleted a day after expiry) |
| Processing operations | Guest registration form, house book, police reporting via UbyPort, claim/reminder e-mail delivery, storage, backup; on the host's button press, check-in name and address may be copied into that stay's invoice buyer fields |
| Recipients | Police of the Czech Republic (UbyPort) as a statutory recipient; the subprocessors in the `/subprocessors` register; TTLock (Hangzhou Sciener Intelligent Control Technology Co., Ltd.), the host's own lock provider and not a subprocessor, only for properties with door codes on: lock ID, code, validity times, reference number; stored in Germany, company in China ([DOOR_CODES_LEGAL](DOOR_CODES_LEGAL.md)) |
| Transfers | Cloudflare is a global edge network; AWS production is `eu-central-1`; see the register and LD-9 |
| Security measures | `docs/SECURITY.md`; the code-enforced vs operator-configured split is `TOMS.md` (LD-7) |
| Retention | `RETENTION.md` (LD-3); the six-year house-book duty dominates |

## B. Controller record — the operator's own processing (Art 30(1))

UbyHost is the **controller** for the data below.

| Activity | Data | Purpose | Basis (to confirm) | Retention |
|---|---|---|---|---|
| Host accounts | E-mail address (login), username (internal), display name, TOTP secret (encrypted), recovery-code hashes, last login; login link token hashes (`login_token`, deleted 1 day after expiry); passkey public keys, names, dates and counters (`passkey`, kept until removed by Host or account deleted); WebAuthn challenge hashes (`webauthn_challenge`, deleted 1 day after expiry); urgent-alert devices (`push_subscription`, push address and keys encrypted, removed after 180 days unseen) and queued alerts (`push_outbox`, 30 days), delivered through the browser maker's push service (Apple, Google, Mozilla or Microsoft) with encrypted content | Provide the service | Contract (Art 6(1)(b)) | Life of account + 3 years (audit log 3 years) |
| Accepted terms | `legal_acceptance` rows (document, version, time, method, IP, user agent) | Demonstrate acceptance (Art 5(2), 24) | Legal obligation / accountability | Life of account + 3 years |
| Security logs | `audit`, `rate_limit_event`, `alert`, container logs | Operate, secure, investigate | Security (Art 6(1)(f)); legal obligation for some | Audit 3 y; resolved alerts 12 mo; rate-limit 24 h (Havel limits 32 days) |
| Support mailbox | Messages to/from `support@ubyhost.com`, including Havel (AI) hand-offs (summary, note, last 4 host messages) | Answer support requests; receive a copy of each "door code not created" notice sent to a host (property name, stay date, TTLock error; no guest name, no door code) | Contract / legitimate interest | To be confirmed (LD-9 identifies the provider) |
| Host support assistant, Havel (AI) (**LAWYER REVIEW**, off until enabled) | Host's typed question and up to 4 earlier turns, redacted (names not removed), plus property ids, names and cities, sent to Anthropic per message and not stored by UbyHost; `havel_gap` (redacted question, language, page, no user; may hold a name the host typed); `rate_limit_event` `havel_*` rows (user id, time); one-tap support e-mails | Answer hosts' questions about the app; improve the guide; hand off to support | Legitimate interest, Art 6(1)(f) (balancing in `drafts/havel-ai.md` part 6); hand-off: contract | Chat not stored on the server (kept in the tab's sessionStorage until the tab closes, the host signs out, or 12 h pass); `havel_gap` 90 days; Havel limit rows 32 days; support e-mail as the support mailbox. Processor: Anthropic, PBC, US (see `drafts/havel-ai.md`) |
| Public website | `ubyhost_lang`, `ubyhost_csrf` cookies; Cloudflare edge data | Serve the site, security | Strictly necessary under § 89(3) ZEK | Language cookie 1 y; CSRF matches the session |
| Backups | Encrypted `age` snapshots of the database and key | Disaster recovery | Legal obligation / security | `UBYHOST_BACKUP_RETENTION_DAYS` (30) |
| Host product analytics (PostHog Cloud EU) | Host e-mail, workspace name, sign-up UTM labels, sign-up source, funnel stage | Product analytics for the operator | Legitimate interest (Art 6(1)(f)) — **LAWYER REVIEW** | Processor: PostHog, Inc. (EU region); deletion by hand on account deletion until automated (see known-issues) — **LAWYER REVIEW** |

## Open questions for counsel

- Havel (AI): assumptions A1 to A6 about Anthropic and the support mailbox retention ([drafts/havel-ai.md](drafts/havel-ai.md) part 7).
- Door codes: ship the host-provider copy and confirm TTLock's platform terms ([DOOR_CODES_LEGAL](DOOR_CODES_LEGAL.md) section 9).
- The lawful basis for each row above, and the exact retention for the support
  mailbox.
- Whether the operator is also an independent controller for security logs and
  support, and who notifies a breach (see the review's § 7).
- The controller/processor allocation when an admin impersonates a workspace
  (full read/write).
## C. Optional cleaning schedule, on host instruction
Purpose: coordinate property cleaning without cleaner accounts or guest identity.
Data: property/unit name, checkout and next-arrival dates/times, cleaning dates,
encrypted event notes, property instructions, and an encrypted dedicated permanent
door code. Hosts choose exactly which properties a cleaning-company link exposes;
links store a 256-bit token hash and expiry/revocation metadata, expire after 30
days, and expose only the next 30 days. No guest names, reservation summaries,
registration status or contacts are read into this view. Hosts are told that
anyone holding a link can read its property codes, and link revocation does not
rotate a previously disclosed permanent code.
TTLock remains the host's chosen lock provider under the existing documented
instruction; the permanent-code action sends lock ID, an opaque UH Cleaning
reference and generated PIN through the existing EU API client. No guest or
cleaner identity is sent. Codes are not sent by e-mail or to analytics.
Retention and security: [RETENTION](RETENTION.md), [SECURITY](../SECURITY.md).
