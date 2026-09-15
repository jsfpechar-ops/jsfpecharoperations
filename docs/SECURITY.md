# Security overview

UbyHost is a self-hosted FastAPI application handling sensitive guest data. This document
summarises the threat model, controls, and known limitations.

## Architecture

| Layer | Control |
|-------|---------|
| **Transport** | HTTPS in production (`Secure` cookies are forced for production); Cloudflare **HSTS** (6 months, no preload) on `ubyhost.com` |
| **Host auth** | Signed session cookie, `HttpOnly`, `SameSite=Strict`, `Secure` on HTTPS, session-version invalidation |
| **Host 2FA** | Authenticator-app TOTP required in production; one-use recovery codes |
| **Guest access** | 100-bit permalink token + optional six-digit PIN + signed PIN cookie bound to token and current PIN |
| **Multi-tenant** | All host routes resolve resources through `access.*` joins on `owner_user_id` |
| **Secrets** | UbyPort passwords encrypted at rest (Fernet); `SECRET_KEY` in `data/secret_key` |
| **Uploads** | Passport photos/PDFs: type/size/magic-byte checks; host-only download route |

## Hardening (application)

- **iCal SSRF**: calendar URLs resolved and blocked if they point to private, loopback, link-local, or metadata addresses; redirects re-validated (max 3 hops, no automatic `requests` redirect following). `UBYHOST_ICAL_ALLOW_PRIVATE` is ignored in production.
- **Login brute force**: sliding-window limits per IP+username and across usernames from one IP (`rate_limit_event` table).
- **Guest PIN brute force**: limit (10 failures / 15 min per IP+token), non-blocking progressive delay on wrong PIN, constant-time compare; **new** PINs are six digits (legacy four-digit PINs still accepted until rotated). Rotating a PIN invalidates prior PIN sessions.
- **Host CSRF**: production and staging host/authentication POSTs require a signed CSRF token bound to the current host session and reject cross-site browser metadata. Guest permalink forms remain outside this control boundary.
- **Bot protection**: Cloudflare Turnstile gates production host login and appears on guest PIN after three failures; the backend validates token, action, hostname, and client IP. The `ubyhost.com` zone also has **Bot Fight Mode**, **leaked-credential mitigation** (login traffic checked against known-leak signals at the edge), and **client-side security** (script inventory in the browser). See [CLOUDFLARE.md](CLOUDFLARE.md).
- **Security alerts**: repeated guest PIN failures create an audit event and a host-visible warning.
- **Guest authorization lifetime**: successful PIN authorization expires after seven days.
- **Open redirects**: host `return_to`, login/language `next`, and signed 2FA continuation values pass one normalized local-path validator; alert dismiss uses a same-host referer path only.
- **Headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and a conservative Content Security Policy. Inline script/style remains allowed for existing templates.
- **API surface**: FastAPI `/docs` and `/redoc` disabled.
- **Health check**: production returns only status, version, and data-volume writability; deployment and UbyPort environment are shown only outside production.
- **Calendar response limits**: iCal downloads stop at 5 MiB and at three redirects; every redirect target is revalidated.
- **Secrets and backups**: generated key/initial-credential files and local backup directories are owner-only. Backups still require operator-managed encryption before off-server storage.
- **UbyPort transport**: production/test endpoints keep TLS verification enabled and SOAP/NTLM requests reject redirects.
- **Filesystem permissions**: the data directory is owner-only, the SQLite database and deployment `.env` are mode `0600`, and deployment scripts repair those modes.

## Residual risks

| Risk | Mitigation / note |
|------|-------------------|
| **Rate limits** | SQLite-backed; effective per app instance; use Cloudflare rate rules for edge protection. |
| **Guest PIN entropy** | New PINs are 6 digits; rotate old 4-digit PINs. Always use PIN in production (`UBYHOST_GUEST_PIN=1`). |
| **Admin impersonation** | Intentional full read/write support access; audited; admin role only. Actions taken while previewing mutate the host workspace. |
| **iCal DNS rebinding** | DNS answers are screened before each request/redirect, but the HTTP client performs its own lookup. Restrict instance egress and metadata access at the host/cloud-network layer. |
| **Guest POST CSRF** | Guest forms do not carry host authority and require the scoped permalink/PIN cookie. Keep PIN protection enabled. |
| **Content Security Policy** | Existing inline scripts/styles require `'unsafe-inline'`; Jinja autoescape remains the primary XSS control. Remove inline code before tightening this directive. |
| **Stateless logout** | Logout clears the browser cookie but does not revoke a copied token. Password changes, account disablement, and 2FA changes increment `session_version`; ordinary sessions expire after 12 hours (30 days with “remember me”). |
| **Backups** | Local permissions do not encrypt the database, key, passport attachments, or receipts. Encrypt before copying off-host and protect access to both backup and key. |

## Reporting

Report suspected vulnerabilities to the software operator (see `/legal`).
