# Security overview

UbyHost is a self-hosted FastAPI application handling sensitive guest data. This document
summarises the threat model, controls, and known limitations.

## Architecture

| Layer | Control |
|-------|---------|
| **Transport** | HTTPS in production (`Secure` cookies are forced for production); Cloudflare **HSTS** (6 months, no preload) on `ubyhost.com` |
| **Host auth** | Signed session cookie, `HttpOnly`, `SameSite=Strict`, `Secure` on HTTPS, session-version invalidation |
| **Host 2FA** | Authenticator-app TOTP required in production; one-use recovery codes |
| **Guest access** | 100-bit permalink token + optional six-digit PIN + signed PIN cookie bound to token and current PIN; the claim secret is stored hashed and never written into a mail body |
| **Multi-tenant** | All host routes resolve resources through `access.*` joins on `owner_user_id` |
| **Secrets** | UbyPort passwords, host TOTP secrets, guest travel-document numbers, birth date, street and town of residence, signatures, the UbyPort request envelope and queued claim secrets encrypted at rest (MultiFernet over `UBYHOST_DATA_KEYS`, separate from the session secret; the old key derived from `SECRET_KEY` is kept for decryption until `scripts/reencrypt.py` has run); `SECRET_KEY` in `data/secret_key` |
| **Uploads** | Passport photos/PDFs: type/size/magic-byte checks; host-only download route |

## Hardening (application)

- **iCal SSRF**: calendar URLs resolved and blocked if they point to private, loopback, link-local, or metadata addresses; each hop is fetched over TCP to the validated address without a second DNS lookup (DNS rebinding safe); redirects re-validated (max 3 hops). `UBYHOST_ICAL_ALLOW_PRIVATE` is ignored in production.
- **Login brute force**: sliding-window limits per IP+username and across usernames from one IP (`rate_limit_event` table).
- **Guest PIN brute force**: limit (10 failures / 15 min per IP+token), non-blocking progressive delay on wrong PIN, constant-time compare; **new** PINs are six digits (legacy four-digit PINs still accepted until rotated). Rotating a PIN invalidates prior PIN sessions.
- **Guest claim mail abuse**: claim/resend sends are capped per IP+token (10 requests / 15 min), per recipient (5 / hour), and per reservation (8 / hour). The caps bound bulk misuse, not a guest retrying; failed or validation-rejected submissions still consume the IP+token budget. An active provisional hold for the same address does not re-send unless the guest explicitly resends after a 1-minute cooldown, and a *different* address may take the stay over once the hold is older than a 60-second grace window (which rotates the token, killing the earlier link). Production claim/resend forms require Cloudflare Turnstile (`guest_claim`).
- **Guest claim links in mail**: the secret is hashed in `reservation_claim` and is **not** stored in a mail body. A queued message keeps a marker where the secret belongs and the secret beside it in the payload, encrypted with the same Fernet key as other secrets; the real link is substituted at send time. `console_mail_log` stores the marker form, and Settings puts the secret back only for the workspace that owns the message. A secret that cannot be decrypted fails the send and retries — it is never replaced by an empty value, so a guest cannot be handed a link that does not work.
- **Host CSRF**: production host/authentication POSTs require a signed token bound to a host-only, `HttpOnly`, `SameSite=Strict` CSRF cookie. The CSRF nonce is independent of the login session so legitimate forms survive session rotation and Safari's omission of strict cookies on an externally opened first page. Critical login, stay-send, guest-edit, identity-check, and re-send forms render the token server-side; JavaScript covers the remaining host forms. Invalid same-site forms redirect back with a retry message instead of downloading a JSON error. Without a valid token, cross-site `Origin`/`Referer` values are rejected; `www` and apex hostnames are treated as equivalent. Staging/local environments retain `SameSite=Strict` session protection so test and administrative clients remain usable. Guest permalink forms remain outside this control boundary.
- **Bot protection**: Cloudflare Turnstile gates production host login, guest claim/resend when mail is enabled, and guest PIN after three failures; the backend validates token, action, hostname, and client IP. The `ubyhost.com` zone uses **custom Managed Challenge rules** on `/login` and private app paths (Free **Bot Fight Mode** stays off so Google can fetch `/sitemap.xml`), plus **leaked-credential mitigation** and **client-side security**. See [CLOUDFLARE.md](CLOUDFLARE.md).
- **Security alerts**: repeated guest PIN failures create an audit event and a host-visible warning.
- **Guest authorization lifetime**: successful PIN authorization expires after seven days.
- **Open redirects**: host `return_to`, login/language `next`, and signed 2FA continuation values pass one normalized local-path validator; alert dismiss uses a same-host referer path only.
- **Headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and a conservative Content Security Policy. Inline script/style remains allowed for existing templates.
- **API surface**: FastAPI `/docs` and `/redoc` disabled.
- **Health check**: production returns only status, version, and data-volume writability; deployment and UbyPort environment are shown only outside production.
- **Calendar response limits**: iCal downloads stop at 5 MiB and at three redirects; every redirect target is revalidated.
- **Secrets and backups**: generated key/initial-credential files and local backup directories are owner-only. Production snapshots are encrypted with `age` (OPS-1) and the private identity is held offline, never on the server.
- **Guest document numbers at rest**: `guest.doc_number` and `guest.visa_number` are stored Fernet-encrypted (`doc_number_enc`, `visa_number_enc`) and the plaintext columns are blanked on every write. Reads go through `db.decrypt_field`, which **raises** on a value it cannot decrypt rather than returning empty, so a lost key cannot turn into an empty `cDocN` in a police filing. A one-shot backfill (`App/scripts/migrate_encrypt_doc_fields.py`) moves pre-existing rows across; the plaintext column stays readable as a fallback until it has run.
- **UbyPort transport**: production/test endpoints keep TLS verification enabled and SOAP/NTLM requests reject redirects.
- **Filesystem permissions**: the data directory is owner-only, the SQLite database and deployment `.env` are mode `0600`, and deployment scripts repair those modes.

## Residual risks

| Risk | Mitigation / note |
|------|-------------------|
| **Rate limits** | SQLite-backed; effective per app instance; use Cloudflare rate rules for edge protection. |
| **Guest PIN entropy** | New PINs are 6 digits; rotate old 4-digit PINs. Always use PIN in production (`UBYHOST_GUEST_PIN=1`). |
| **Admin impersonation** | Intentional full read/write support access; audited; admin role only. Actions taken while previewing mutate the host workspace. |
| **iCal DNS rebinding** | Mitigated by pinning each fetch to the IP(s) returned at validation time (no `getaddrinfo` on connect). Keep egress restrictions as defence in depth. |
| **Guest POST CSRF** | Guest forms do not carry host authority and require the scoped permalink/PIN cookie. Keep PIN protection enabled. |
| **Overlapping stay selection** | One apartment permalink/PIN can select any active stay inside its configured visibility window. Keep the window short and avoid overlapping links where booking-date disclosure is unacceptable. |
| **Content Security Policy** | Existing inline scripts/styles require `'unsafe-inline'`; Jinja autoescape remains the primary XSS control. Remove inline code before tightening this directive. |
| **Stateless logout** | Logout clears the browser cookie but does not revoke a copied token. Password changes, account disablement, and 2FA changes increment `session_version`; ordinary sessions expire after 12 hours (30 days with “remember me”). |
| **Backups** | Production snapshots are encrypted with `age` and the identity is held offline (OPS-1); the key never travels with the copy. Passport attachments are not in the database backup and are short-lived by design. |

## Source-control hygiene

This repository is public. Secrets that are committed — even once, even to a
feature branch, even briefly before a revert — remain readable from the git
history forever. A `secret_key` and a SQLite database containing guest PII were
committed early in the project and only removed during a pre-publication audit,
which required a full `git filter-repo` history rewrite and force-push.

- Never commit `UBYHOST_SECRET_KEY`, `.env`, the SQLite database, backups, or
  real guest PII. `App/data/*` is git-ignored by design (only `.gitkeep` is
  tracked); runtime secrets belong on the server's persistent volume.
- If a secret reaches git history, deleting the file is not enough — scrub it
  from every ref with `git filter-repo`, force-push, and rotate the key.
- Before publicising the repository, audit history with
  `git log --all -S <secret>` and `git grep -I <secret> $(git rev-list --all)`.

## Reporting

Report suspected vulnerabilities to the software operator (see `/legal`).
