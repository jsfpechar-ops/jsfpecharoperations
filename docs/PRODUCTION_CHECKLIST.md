# Production go-live checklist (MLJNO / Kubelíkova)

Use this when moving **production (AWS Lightsail, ubyhost.com)** from setup to live
reporting. Staging stays on Render **`ubyhost-staging`** (`mock`) only.
Your police registration documents confirm the accommodation; this checklist does not
repeat any passwords from those PDFs.

## Property facts (from registration)

| Field | Value |
|-------|-------|
| Five-letter mark | `MLJNO` |
| IDUB | `100124005169` |
| Address | Kubelíkova 697/13, Prague |

These must match **exactly** in UbyHost → apartment settings and in the police register.

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
- [ ] `.env`: `UBYHOST_DEPLOYMENT=production`, `UBYHOST_UBYPORT_ENV=test`, `UBYHOST_PUBLIC_BASE_URL=https://ubyhost.com`
- [ ] Domain on Cloudflare — [CLOUDFLARE.md](CLOUDFLARE.md): proxied A record, SSL **Full (strict)**, origin certs on server, **HSTS** (6 months, no subdomains/preload), **Bot Fight Mode**, **leaked credentials**, **client-side security**
- [ ] `./scripts/deploy.sh` completed; `/healthz` shows `deployment: production`, `ubyport_env: test`
- [ ] Admin login works; password changed from bootstrap value
- [ ] `./scripts/backup.sh` once; optional weekly **Google Drive** (`backup-gdrive.sh`). S3 optional — can defer

## Phase 3 — Configure the apartment

- [ ] Create entity (host / company) for the legal operator.
- [ ] Add apartment with mark `MLJNO`, IDUB `100124005169`, address as registered.
- [ ] Enter UBY-WS username and password; **Test connection** / refresh code lists.
- [ ] Set submission mode (immediate / scheduled / manual) per your operating rules.
- [ ] Paste Airbnb and Booking.com iCal export URLs.
- [ ] Copy the guest permalink into check-in messages on both platforms.
- [ ] Enable guest PIN if `UBYHOST_GUEST_PIN=1` (recommended on production).

## Phase 4 — Validate on test UbyPort

- [ ] Import or create a real upcoming stay (or a controlled test stay you will cancel
  with the police if needed).
- [ ] Complete the guest form (or enter test guests yourself).
- [ ] Submit to UbyPort **test**; confirm Doručenka PDF and no field rejections.
- [ ] Fix any validation errors (nationality codes, address format, dates).
- [ ] Confirm house book CSV export looks correct.

## Phase 5 — Go live

- [ ] On Lightsail `.env`, set `UBYHOST_UBYPORT_ENV=prod` (never on Render staging).
- [ ] `./scripts/deploy.sh`; Settings shows red **prod** badge.
- [ ] Submit one real guest batch; archive Doručenka.
- [ ] Weekly off-site backup (Google Drive cron); monitor `/healthz` and logs.

## Ongoing operations

| Task | Frequency |
|------|-----------|
| `backup_data.sh` | Weekly (cron) + after major changes |
| Review failed submissions / alerts | Daily during high season |
| Staging deploy after merges | Automatic; spot-check critical UI changes |
| Production deploy | `git pull` + `./scripts/deploy.sh` on Lightsail after merges to `main` |
| Rotate admin password | After staff changes |
| UbyPort password | Only when police issues a new WS account |

## Staging (`ubyhost-staging`)

Keep staging on `mock` forever. Use it to:

- Train new staff on the UI
- Verify PRs before production deploy
- Test calendar import and guest flows without police side effects

Never copy production SQLite into staging without anonymising guest data (GDPR).
