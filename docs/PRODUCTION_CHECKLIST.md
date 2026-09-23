# Production go-live checklist (MLJNO / Kubelíkova)

Use this when moving **production (AWS Lightsail, ubyhost.com)** from setup to live
reporting. Staging stays on Render **`ubyhost-staging`** (`mock`) only.
Your police registration documents confirm the accommodation; this checklist does not
repeat any passwords from those PDFs.

Operational detail (restore, backups, deploy failure modes): **[LIGHTSAIL.md](LIGHTSAIL.md)**.

## Property facts (from registration)

| Field | Value |
|-------|-------|
| Five-letter mark | `MLJNO` |
| IDUB | `100124005169` |
| Address | Kubelíkova 697/13, Prague |

These must match **exactly** in UbyHost → apartment settings and in the police register.

## Environment model (never mix)

| Where | `UBYHOST_DEPLOYMENT` | `UBYHOST_UBYPORT_ENV` | Purpose |
|-------|----------------------|------------------------|---------|
| Laptop | `local` | `mock` | Dev |
| Render `ubyhost-staging` | `staging` | `mock` **forever** | Demos / PR UX |
| Lightsail pre-live | `production` | **`test`** | Real SOAP, not the live register |
| Lightsail live | `production` | **`prod`** | Real police reporting |

The app **refuses to start** if `UBYPORT_ENV=prod` without `DEPLOYMENT=production`, or if `prod` is combined with Render (`RENDER=true`, `onrender.com` URLs). `render_start.sh` also exits on `prod`.

## Phase 1 — Credentials (before any deploy to prod)

- [ ] Request **UBY-WS web-service** credentials from the Foreign Police:
  - E-mail: `reguby@pcr.cz`
  - Data box: `ybndqw9`
  - State: webová služba UBY-WS, your IČO, IDUB `100124005169`, full address
- [ ] Wait for `UBY-WS…` username and password (separate from the `ub…` portal login
  in your registration PDFs).
- [ ] Store the web-service password only in UbyHost (encrypted at rest), never in git.

## Phase 2 — Lightsail production stack

- [ ] Instance running; app at `/opt/ubyhost/deploy/lightsail` — see [LIGHTSAIL.md](LIGHTSAIL.md)
- [ ] `.env`: `UBYHOST_DEPLOYMENT=production`, `UBYHOST_UBYPORT_ENV=test`, `UBYHOST_PUBLIC_BASE_URL=https://ubyhost.com`, `UBYHOST_GUEST_PIN=1`, `UBYHOST_ENABLE_SCHEDULER=1`
- [ ] Domain on Cloudflare — [CLOUDFLARE.md](CLOUDFLARE.md): proxied A record, SSL **Full (strict)**, origin certs on server, **HSTS** (6 months, no subdomains/preload), **Bot Fight Mode Off** + SEO custom Rules 1–3 (verified bots skip + Managed Challenge on `/login` and private paths), **leaked credentials**, **client-side security**
- [ ] Google Search Console — [SEARCH_CONSOLE.md](SEARCH_CONSOLE.md): Domain property verified, `sitemap.xml` submitted, live URL test OK for `/` and `/sitemap.xml`
- [ ] `./scripts/preflight.sh` then `./scripts/deploy.sh` completed
- [ ] Public `/healthz` → `status: ok`, `data_dir_writable: true` (production **omits** env labels by design)
- [ ] `./scripts/status.sh` → `deployment= production`, `ubyport_env= test`
- [ ] Admin login works; password changed from bootstrap value; 2FA enrolled
- [ ] `./scripts/backup.sh` once; restore drill: `./scripts/restore.sh <stamp>` on a **copy** or after a fresh backup (prove login + one stay)
- [ ] Weekly **Google Drive** cron (`backup-gdrive.sh`) after `rclone config`. S3 optional — can defer
- [ ] GitHub: `LIGHTSAIL_HOST` / SSH key present; leave `LIGHTSAIL_AUTO_DEPLOY` **unset** until you want CI to ship every green `main`

## Phase 3 — Configure the apartment

- [ ] Create entity (host / company) for the legal operator.
- [ ] Add apartment with mark `MLJNO`, IDUB `100124005169`, address as registered.
- [ ] Enter UBY-WS username and password; **Test connection** / refresh code lists.
- [ ] Set submission mode (immediate / scheduled / manual) per your operating rules.
- [ ] Paste Airbnb and Booking.com iCal export URLs.
- [ ] Copy the guest permalink into check-in messages on both platforms.
- [ ] Guest PIN enabled (`UBYHOST_GUEST_PIN=1`).

## Phase 4 — Validate on test UbyPort (go-live gate)

Do this on Lightsail with **test**, never on Render, never with `prod`. Label the stay **TEST**. Dates in the near future.

**Operator SSH (copy-paste):**

```bash
ssh ubuntu@YOUR_STATIC_IP
cd /opt/ubyhost/deploy/lightsail
./scripts/status.sh
# Confirm ubyport_env= test  and  endpoint contains ws_uby_test
```

### Test script — record evidence

Fill the report at the bottom of this file. No guest PII in git.

1. [ ] Create or import one controlled stay (label TEST). Screenshot: Stays list.
2. [ ] Complete guest registration (host-entered **or** guest link) with realistic **foreign** guest data that passes validation (nationality codes, residence, purpose of stay). Screenshot: stay detail complete.
3. [ ] Submit batch to UbyPort **test**. Screenshot: Reports row.
4. [ ] Confirm submission `state` is `ok` (or document `partial` / `error`). Download Doručenka PDF. In Reports, stored request XML matches what you intended to send. House book row exists.
5. [ ] Duplicate: submit the same guest again **once** on **test**. Expect code **150** / duplicate handling — guest should not be blindly retried. Screenshot: blocked/duplicate messaging. Do **not** spam.
6. [ ] Transport failure (test only): wrong WS password **once**, or briefly set an unreachable timeout if you can, then restore the real password. Host must see **Could not reach UbyPort** / transport alert; guests stay pending (no silent drop). Screenshot: alert + Reports `transport_error`.
7. [ ] Export house book CSV — fields match the submitted guest.

If UBY-WS credentials are not on this machine, stop after documenting SSH steps; do not invent a SOAP success.

## Phase 5 — Go live (only after Phase 4 sign-off)

Operator approval required in the working session. This repo must **not** flip prod by itself.

- [ ] Phase 4 report signed (operator name + date below)
- [ ] On Lightsail `.env`, set `UBYHOST_UBYPORT_ENV=prod` (never on Render staging).
- [ ] `./scripts/preflight.sh && ./scripts/deploy.sh`
- [ ] `./scripts/status.sh` shows `ubyport_env= prod`; Settings shows red **prod** badge
- [ ] Submit **one** real guest batch; archive Doručenka (PDF + date)
- [ ] Weekly off-site backup still running; no pager — check Reports daily in season

### Rollback

```bash
cd /opt/ubyhost/deploy/lightsail
# stop live sends
sed -i 's/^UBYHOST_UBYPORT_ENV=.*/UBYHOST_UBYPORT_ENV=test/' .env
./scripts/deploy.sh
./scripts/status.sh   # ubyport_env= test
```

Already-accepted **prod** records stay in the police register. Do not resend them. If personal data in the register is wrong, correct via the app if UbyPort allows, otherwise contact the police (see errors below).

## Ongoing operations

| Task | Frequency |
|------|-----------|
| `backup.sh` | Daily cron + after major changes |
| `backup-gdrive.sh` | Weekly |
| Review failed submissions / alerts | Daily during high season |
| Staging deploy after merges | Manual on Render; mock only |
| Production deploy | SSH `git pull` + `./scripts/deploy.sh` **or** GitHub **workflow_dispatch** after CI green |
| Rotate admin password | After staff changes |
| UbyPort password | Only when police issues a new WS account |
| Disk (`df`, photo dir) | Weekly; sooner if uploads pile up |

## Staging (`ubyhost-staging`)

Keep staging on `mock` forever. Use it to:

- Train new staff on the UI
- Verify PRs before production deploy
- Test calendar import and guest flows without police side effects

Never copy production SQLite into staging without anonymising guest data (GDPR).

## UbyPort errors → host actions

Codes are interpreted in `App/app/ubyport/errors.py` and shown on the guest/report UI. The live codebook is cached from `DejMiCiselnik(Chyby)`.

| Code / class | Meaning | Host action |
|--------------|---------|-------------|
| *(none)* / submission `ok` | Batch accepted | Archive Doručenka; done |
| **106** | Invalid guest field | Fix the field, resend that guest |
| **1** | Incorrect file extension | Should not occur for SOAP; check Doručenka; do not loop |
| **112** | Reported late (3 working days) | **Do not resend** as a fix; `not_correctable`. Note for the file; police may still hold/refuse |
| **150** / text contains `duplic` | Duplicate — register already has the row | App treats this as already sent / not blindly retried. Submission is recorded as `ok_duplicate`; the Doručenka link points at the submission that holds it. **Do not** hammer submit |
| Other correctable codes | Rejected, worth a fix | Edit guest, one resend |
| `not_correctable` | Duplicate, late, or similar | Stop; read Doručenka |
| `transport_error` / `UbyportTransportError` | Timeout, NTLM/auth, TLS, SOAP fault | Alert: “could not deliver”. Guests stay **pending**. Fix network/password; retry **once**. No data deleted |
| `not_configured` | Missing mark/IDUB/WS login | Complete apartment UBY-WS settings |
| Header errors on Doručenka | Whole batch problem | Open error PDF; fix apartment header (IDUB/mark/address) |

XML for a submission is stored on the `submission` row (`request_xml` / `response_xml`) for comparison with the Doručenka. Never commit those files.

## UbyPort test submission report

| Field | Value |
|-------|-------|
| Date (Europe/Prague) | _YYYY-MM-DD_ |
| Operator | _name_ |
| Host | Lightsail / _(no access — not executed)_ |
| `.env` `UBYHOST_DEPLOYMENT` | production |
| `.env` `UBYHOST_UBYPORT_ENV` | **test** |
| `status.sh` endpoint | _must contain `ws_uby_test`_ |
| Apartment mark / IDUB | MLJNO / 100124005169 |
| Stay id / label | TEST … |
| Guest nationality (no full PII in git) | e.g. GBR |
| Submission id | |
| Submission `state` | ok / ok_duplicate / partial / error / transport_error |
| Doručenka downloaded | yes / no |
| XML stored in Reports | yes / no |
| House book row | yes / no |
| Duplicate test (150) | pass / skip / notes |
| Transport failure test | pass / skip / notes |
| CSV export checked | yes / no |
| Screenshots / log paths (local, not git) | |
| Sign-off for **prod** flip | **no** until this table is complete and operator approves |

**This repository run (15 September 2026):** UBY-WS credentials and Lightsail SSH were **not** available in the agent environment. Phase 4 was **not** executed against `ubyport.pcr.cz`. Mock pytest + local `backup_data.sh` were executed instead. **Technical recommendation: no-go for `prod` until this report is filled on Lightsail.**
