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
| Categories of personal data | Name, birth date, nationality, permanent residence; travel document and visa numbers (Fernet-encrypted at rest); drawn signature; optional passport/ID image or PDF (default **off**); stay dates; submitter IP; the e-mail/phone used to claim the stay; police submission envelopes; Doručenka/error PDFs |
| Processing operations | Guest registration form, house book, police reporting via UbyPort, claim/reminder e-mail delivery, storage, backup |
| Recipients | Police of the Czech Republic (UbyPort) as a statutory recipient; the subprocessors in the `/subprocessors` register |
| Transfers | Cloudflare is a global edge network; AWS production is `eu-central-1`; see the register and LD-9 |
| Security measures | `docs/SECURITY.md`; the code-enforced vs operator-configured split is `TOMS.md` (LD-7) |
| Retention | `RETENTION.md` (LD-3); the six-year house-book duty dominates |

## B. Controller record — the operator's own processing (Art 30(1))

UbyHost is the **controller** for the data below.

| Activity | Data | Purpose | Basis (to confirm) | Retention |
|---|---|---|---|---|
| Host accounts | E-mail address (login), username (internal), display name, TOTP secret (encrypted), recovery-code hashes, last login; login links stored only as hashes (`login_token`); passkey public keys, names, dates and counters (`passkey`), WebAuthn challenge hashes (`webauthn_challenge`) | Provide the service | Contract (Art 6(1)(b)) | Life of account + 3 years |
| Accepted terms | `legal_acceptance` rows (document, version, time, method, IP, user agent) | Demonstrate acceptance (Art 5(2), 24) | Legal obligation / accountability | Life of account + 3 years |
| Security logs | `audit`, `rate_limit_event`, `alert`, container logs | Operate, secure, investigate | Security (Art 6(1)(f)); legal obligation for some | Audit 3 y; resolved alerts 12 mo; rate-limit 24 h |
| Support mailbox | Messages to/from `support@ubyhost.com` | Answer support requests | Contract / legitimate interest | To be confirmed (LD-9 identifies the provider) |
| Public website | `ubyhost_lang`, `ubyhost_csrf` cookies; Cloudflare edge data | Serve the site, security | Strictly necessary under § 89(3) ZEK | Language cookie 1 y; CSRF matches the session |
| Backups | Encrypted `age` snapshots of the database and key | Disaster recovery | Legal obligation / security | `UBYHOST_BACKUP_RETENTION_DAYS` (30) |

## Open questions for counsel

- The lawful basis for each row above, and the exact retention for the support
  mailbox.
- Whether the operator is also an independent controller for security logs and
  support, and who notifies a breach (see the review's § 7).
- The controller/processor allocation when an admin impersonates a workspace
  (full read/write).
