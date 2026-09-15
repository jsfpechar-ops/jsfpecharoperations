# Defensive application security review — 2026-09-15

## Posture summary

UbyHost has a sound application-level ownership model for a single-operator
Lightsail deployment and consistently joins host resources through their apartment
owner. The review found no confirmed cross-tenant read or write path, and regression
coverage now includes stays, guests, submission documents, and passport photos.
The most important code gaps were missing host CSRF tokens, vulnerable web-framework
pins, PIN rotation that did not revoke authorization, outbound redirect handling, and
unbounded calendar downloads; these are fixed. Guest links remain appropriate only with the production-default PIN enabled,
and legacy four-digit PINs should be rotated. Residual risk is concentrated in
operator controls: network egress, encrypted off-host backups, edge rate limiting,
and secret rotation.

## Findings

| ID | Severity | Area | Finding | Status |
|----|----------|------|---------|--------|
| UH-01 | High | Supply chain | Pinned multipart, HTTP, and framework packages had published 2026 advisories. | Fixed: upgraded FastAPI, Starlette, python-multipart, and requests; dependency audit is clean. |
| UH-02 | Medium | CSRF | Host and authentication POST forms relied only on `SameSite=Strict`. | Fixed in production: requests require a signed, session-bound token and same-origin browser metadata. Staging/local retain strict-cookie protection for automation compatibility. |
| UH-03 | Medium | Redirects | Several `return_to` and continuation paths bypassed the stricter local-path helpers. | Fixed: host redirects use one normalized local-path validator. |
| UH-04 | Medium | Availability | Calendar responses had redirect limits but no response-size ceiling. | Fixed: 5 MiB ceiling, explicit three-hop limit, malformed/userinfo URL rejection. |
| UH-05 | Medium | Secrets | Existing secret-key permissions were not repaired; generated files were not created atomically. | Fixed: owner-only modes are enforced and key creation is exclusive. |
| UH-06 | Low | Information disclosure | Production `/healthz` exposed deployment and UbyPort environment labels. | Fixed: production output omits those fields while retaining monitoring status. |
| UH-07 | Low | Guest links | Newly generated permalink tokens provided about 50 bits of entropy. | Fixed: new tokens provide about 100 bits; existing links remain valid until rotated. |
| UH-08 | Low | Browser hardening | No CSP limited framing, object content, base URLs, or form destinations. | Mitigated: CSP added; inline script/style allowances remain documented. |
| UH-09 | Low | File rendering | Uploaded passport documents were type/size/magic checked and owner-scoped, but lacked a document-specific browser sandbox. | Fixed: passport responses receive a restrictive sandbox CSP. |
| UH-10 | Low | Multi-tenancy | Existing ownership checks were strong, but document descendants had limited negative coverage and unauthorized XML returned an empty 200. | Fixed: unauthorized XML is 404 and cross-owner photo/XML tests were added. |
| UH-11 | Medium | SSRF | URL/DNS screening cannot fully remove DNS-rebinding risk because the HTTP stack resolves again when connecting. | Documented residual; requires egress and metadata-network controls. |
| UH-12 | Medium | Backups | Backups contain the database and the key needed to decrypt service credentials and are not encrypted by the app. | Mitigated with owner-only local permissions; off-host encryption needs operator action. |
| UH-13 | Low | Rate limiting | SQLite limits are per application database/instance and do not replace edge controls. | Documented residual. |
| UH-14 | Low | Logout | Signed sessions are stateless; logout clears the current cookie without revoking a copied token. | Documented residual; sensitive account changes invalidate all sessions. |
| UH-15 | High | Guest PIN | A PIN authorization cookie was bound only to the permalink and remained valid after PIN rotation. | Fixed: authorization is bound to a keyed fingerprint of the current PIN. |
| UH-16 | Medium | Availability | Wrong-PIN progressive delay blocked the async worker. | Fixed: delay now yields through `asyncio.sleep`. |
| UH-17 | Medium | UbyPort transport | The SOAP/NTLM client followed HTTP redirects by default. | Fixed: redirects are disabled and 3xx responses fail closed. |
| UH-18 | Medium | Authentication | Login throttling was only per IP+username, allowing failures to be distributed across usernames. | Fixed: an aggregate per-IP window is enforced as a second limit. |
| UH-19 | Medium | Production configuration | `UBYHOST_ICAL_ALLOW_PRIVATE` could disable SSRF screening in production. | Fixed: the override is effective only outside production. |
| UH-20 | Low | Tenant metadata | Reservation detail trusted a guest's submission foreign key without matching the apartment. | Fixed: submission metadata must belong to the reservation apartment. |
| UH-21 | Medium | Guest isolation | One apartment token/PIN authorizes all active stays in the configured visibility window, exposing limited booking dates across overlapping stays. | Accepted product residual; keep the window short or adopt stay-specific secrets before using wider windows. |

## Control review notes

- Authentication cookies are `HttpOnly`, `SameSite=Strict`, and always `Secure` in
  production. Password, account-state, and 2FA changes bump
  `session_version`.
- Production forces TOTP setup. Login and TOTP failures share SQLite-backed
  per-client and aggregate IP limits, and unknown usernames take the password-hash path.
- Host resource routes use `access.*` or explicit `owner_user_id` joins. Global user
  administration and impersonation are restricted to administrators and audited.
- Guest PIN comparison is constant-time and failure-limited. Authorization cookies are
  token-and-PIN-bound, so PIN rotation revokes prior sessions. New PINs are six digits;
  four-digit database values remain accepted only for compatibility.
- Jinja autoescape is enabled and no application template uses `safe` for untrusted
  values. CSP adds defense in depth but is not yet a strict script policy.
- Passport uploads retain the existing JPEG/PNG/WebP/PDF size and magic-byte checks.
  Downloads require host ownership through the guest-to-reservation-to-apartment join.
- UbyPort endpoints are configuration-selected, production TLS verification remains
  enabled, redirects are rejected, and logs do not intentionally include passwords.
- `.env`, database files, generated credentials, and `secret_key` are ignored or
  stored outside the repository. A tracked-file check found no runtime secret.

## Residual risk register

| Risk | Owner action |
|------|--------------|
| DNS rebinding or unexpected iCal egress | Deny instance access to cloud metadata and private management networks; allow only required outbound destinations where practical. |
| Legacy guest PINs | Regenerate links/PINs for apartments still using four digits. |
| Edge abuse and distributed guessing | Keep Cloudflare proxy, Turnstile, and rate rules enabled; alert on sustained failures. |
| Backup compromise | Encrypt backups before off-host transfer, restrict restore access, and test restoration without exposing production data. |
| Secret-key rotation | Schedule a maintenance window: changing the key logs out users and requires re-entry of encrypted UbyPort passwords. |
| Admin impersonation | Restrict administrator accounts, retain audit history, and use impersonation only for support. Impersonation is full read/write access, not a read-only preview. |
| Inline CSP allowances | Move inline template scripts/styles to static assets, then remove `'unsafe-inline'`. |
| Copied stateless session after logout | Use password reset, account disablement, or 2FA reset when compromise is suspected. |
| Overlapping guest stays | Keep `permalink_window_days` minimal and use separate apartment links where booking-date separation is required. |

## Operator checklist

- Set `UBYHOST_DEPLOYMENT=production`, an HTTPS `UBYHOST_PUBLIC_BASE_URL`, and
  `UBYHOST_GUEST_PIN=1`.
- Confirm host cookies carry `Secure`, `HttpOnly`, and `SameSite=Strict` at the edge.
- Keep Cloudflare bot protection, Turnstile, and login/guest-PIN rate rules enabled.
- Block instance metadata and unnecessary private-network egress from the app container.
- Rotate legacy guest PINs and guest links shared beyond their intended booking.
- Store `UBYHOST_SECRET_KEY` in the protected deployment environment; back it up
  separately and never rotate it without a credential-reentry plan.
- Encrypt database/secret backups before transfer and periodically test a restore.
- Remove `initial_admin_credentials` after the first password change and require TOTP
  for every production administrator.
- Run the pinned dependency audit during routine updates and rebuild the container
  when security pins change.

## Verification

- Full application suite: `328 passed`.
- Focused security/tenancy/SSRF suite: `94 passed`.
- Local mock smoke check: `32 pages checked`; no dead pages or server errors.
- Dependency audit against `App/requirements.txt`: no known vulnerabilities.
- Tracked-file review: no runtime `.env`, database, secret key, or initial credential file.
