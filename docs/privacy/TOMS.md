# Technical and organisational measures (Article 32)

**Status:** input for counsel (LD-7). Split into what the code enforces and what
the operator must configure. `docs/SECURITY.md` is the threat-model source; link
this from `dpa_i18n.py` § 10 once counsel approves.

## A. Code-enforced

| Measure | Where |
|---|---|
| Encryption of travel-document numbers and drawn signatures at rest (Fernet) | `db.ENCRYPTED_GUEST_COLUMNS`, `README`/`SECURITY.md` |
| Encrypted passport attachments at rest | `passport_photos` (BE-12) |
| Host authentication, session versioning, TOTP 2FA in production | `auth.py` |
| CSRF on host posts; validated redirects | `security.py` |
| Guest access: permalink token + PIN + hashed claim secret | `auth.py`, `claim.py` |
| Multi-tenant isolation through `owner_user_id` joins | `access.py` |
| At-rest overwrite on delete (SQLite `secure_delete`) | `db.connect` |
| Read auditing (exports, passport views, real actor) | BE-6 |
| Access logs carry route templates only; bounded rotation | OPS-3 |
| Retention job (dry-run by default) | BE-2/3/4 |
| Encrypted backups, key held offline, fail-closed | OPS-1/OPS-2 |

## B. Operator-configured

| Measure | Evidence |
|---|---|
| Cloudflare protections (WAF, challenges, leaked-credential mitigation, HSTS) | `docs/CLOUDFLARE.md` |
| Backup key custody (offline `age` identity) | `docs/OPERATIONS.md` § "Backup and restore" |
| Lightsail host access, SSH keys, patch cadence | `docs/LIGHTSAIL.md` |
| Two-factor authentication on every vendor account | vendor evidence file |
| Backup restore test at least quarterly | `docs/OPERATIONS.md` |
| Vendor DPAs and regions | `docs/vendors/README.md` (LD-9) |
| No production data in dev tools / AI assistants | `docs/vendors/README.md` |

## C. Not yet in place

- Names and birth dates remain unencrypted for search/sort (`docs/archive/FOLLOWUPS.md`).
- Passport-image encryption applies to new writes and the migration, not to
  plaintext files an operator copied elsewhere.
- These gaps are listed in the retention schedule and the audit reconciliation
  for counsel.
