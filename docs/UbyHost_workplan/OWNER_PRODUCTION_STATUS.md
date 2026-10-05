# Owner production status

Living checklist for **ubyhost.com** (Lightsail). Update this when you complete a gate or change production `.env`. Secrets stay only on the server — never in git.

**Last updated:** 2026-10-05 (operator confirmations).

---

## Code on GitHub

| Item | Status |
|------|--------|
| Workplan **0001–0034** on `main` | **Done** — PR **#237** |
| WP22/WP24 owner gate | **Done** — PR **#275** |
| Litestream preflight when S3 empty | **Done** — PR **#273** |
| Follow-up bundle (filing, stay-fee, tests, Umami cleanup) | **Open** — PR **#277** — merge then deploy |

---

## Done on your side (operator)

| Area | Status | Notes |
|------|--------|--------|
| Password manager + `UBYHOST_SECRET_KEY` backup | **Done** | |
| SES guest/host mail | **Done** | |
| Operator identity in `.env` | **Done** | |
| Turnstile | **Done** | |
| healthchecks.io (submit, iCal, mail, backup, **Filing**) | **Done** | `UBYHOST_HEARTBEAT_FILING_URL` in `.env` |
| Litestream → S3 | **Done** | Restore drill passed |
| Production deploy / worker / `ubyport=prod` | **Done** | |
| `UBYHOST_RETENTION_AUTOPURGE=1` | **Done** | |
| `UBYHOST_LEGAL_EFFECTIVE_DATE` | **Done** | Confirmed on server |
| Umami (`UMAMI_WEBSITE_ID` + `UMAMI_SCRIPT_URL`) | **Done** | Public pages only; verify `/login` has no tracker after deploy |
| Cloudflare + `UBYHOST_TRUSTED_PROXY_CIDRS` | **Done** | See note below if unsure about orange-cloud |
| `UBYHOST_GUEST_LANGS` | **Done** | Reviewed; extra languages enabled in `.env` |
| Render staging | **Done** | |
| Real hosts on production | **Done** | |
| Better Stack / uptime on `/healthz` | **Done** | |

---

## Still to do (owner)

| Priority | Task | Notes |
|----------|------|--------|
| **High** | Deploy **`main`** after **#277** merges (and after **#275**/**#273** if not redeployed since) | `preflight.sh` + `deploy.sh` or GitHub Deploy production |
| **Medium** | Doručenka on a **new** filing | You will verify download on report page |
| **Low** | Optional GDrive off-site backup | Not required if Litestream + nightly backup OK |
| **Later** | Sign-up ads (`UBYHOST_SIGNUP_ENABLED`), WP16 re-encrypt, marketing | When you choose |

---

## Manual filing guide — do you need to “send” anything?

**No separate document mail-out is required** if hosts use the product:

- In-app **Host guide** (`/guide`) includes the manual UbyPort fallback (same content as `compliance/05_manual_filing_fallback.md`, kept in sync by tests).
- On each stay, the **“I filed this stay by hand in UbyPort”** button (24 h undo) is WP23.

Optional onboarding: mention `/guide#` reporting section in your welcome e-mail to new hosts. The markdown file in the repo is for **you** and counsel, not something every host must receive as an attachment.

---

## Cloudflare: proxied or not — will the app break?

**No.** With your current `.env` (`CLOUDFLARE_PROXY=1` + `UBYHOST_TRUSTED_PROXY_CIDRS=172.16.0.0/12`), the app is configured for the usual **orange-cloud** setup (visitor → Cloudflare → your Lightsail origin with origin cert). It will run either way:

| DNS in Cloudflare | What happens |
|-------------------|----------------|
| **Proxied** (orange cloud) | Expected. Caddy sees Cloudflare; real client IP comes from `CF-Connecting-IP` when the peer is in `TRUSTED_PROXY_CIDRS`. Rate limits apply per guest/host IP, not one shared bucket. |
| **DNS only** (grey cloud) | Still works. Visitors hit your IP directly; `CF-Connecting-IP` may be absent — the app uses the direct connection IP. Origin cert / `Caddyfile.cloudflare` still fine if you use Cloudflare origin TLS. |

**Quick check:** Cloudflare → **DNS** → your `A` record. Orange cloud = proxied.

**Quick sanity after deploy:** site loads on `https://ubyhost.com`, `/healthz` OK, log in as host, open a stay — no errors. If worker logs no longer warn about `UBYHOST_TRUSTED_PROXY_CIDRS` unset, you are good.

---

## Waiting on (optional)

Optional counsel, Facebook/Google/Meta when you run ads — not production blockers.

---

## Obsolete open PRs

Close draft **#238–#271**, **#236**, and superseded **#233**, **#235**, **#272**, **#274**, **#276** after **#277** merges.

---

## Quick deploy

```bash
cd /opt/ubyhost/deploy/lightsail
./scripts/preflight.sh
./scripts/deploy.sh
```
