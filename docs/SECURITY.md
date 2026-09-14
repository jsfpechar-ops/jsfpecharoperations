# Security overview

UbyHost is a self-hosted FastAPI application handling sensitive guest data. This document
summarises the threat model, controls, and known limitations.

## Architecture

| Layer | Control |
|-------|---------|
| **Transport** | HTTPS in production (`Secure` cookies when `PUBLIC_BASE_URL` is `https://`) |
| **Host auth** | Signed session cookie, `HttpOnly`, `SameSite=strict`, session version invalidation |
| **Host 2FA** | Authenticator-app TOTP required in production; one-use recovery codes |
| **Guest access** | Unguessable permalink token + optional 4-digit PIN + signed PIN cookie bound to token |
| **Multi-tenant** | All host routes resolve resources through `access.*` joins on `owner_user_id` |
| **Secrets** | UbyPort passwords encrypted at rest (Fernet); `SECRET_KEY` in `data/secret_key` |
| **Uploads** | Passport photos/PDFs: type/size/magic-byte checks; host-only download route |

## Hardening (application)

- **iCal SSRF**: calendar URLs resolved and blocked if they point to private, loopback, link-local, or metadata addresses; redirects re-validated (max 3 hops, no automatic `requests` redirect following).
- **Login brute force**: sliding-window limit per IP+username (`rate_limit_event` table).
- **Guest PIN brute force**: limit (10 failures / 15 min per IP+token), progressive delay on wrong PIN, constant-time compare; **new** PINs are six digits (legacy four-digit PINs still accepted until rotated).
- **Bot protection**: Cloudflare Turnstile gates production host login and appears on guest PIN after three failures; the backend validates token, action, hostname, and client IP.
- **Security alerts**: repeated guest PIN failures create an audit event and a host-visible warning.
- **Guest authorization lifetime**: successful PIN authorization expires after seven days.
- **Open redirects**: `return_to` and login `next` accept local paths only; alert dismiss uses referer path only.
- **Headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
- **API surface**: FastAPI `/docs` and `/redoc` disabled.

## Residual risks

| Risk | Mitigation / note |
|------|-------------------|
| **CSRF on host POST forms** | `SameSite=strict` session cookie reduces cross-site risk; dedicated CSRF tokens remain future hardening. |
| **Rate limits** | SQLite-backed; effective per app instance; use Cloudflare rate rules for edge protection. |
| **`/healthz`** | Exposes deployment tier and UbyPort env (for monitoring). |
| **Guest PIN entropy** | New PINs are 6 digits; rotate old 4-digit PINs. Always use PIN in production (`UBYHOST_GUEST_PIN=1`). |
| **Admin impersonation** | Intentional for support; audited; admin role only. |

## Reporting

Report suspected vulnerabilities to the software operator (see `/legal`).
