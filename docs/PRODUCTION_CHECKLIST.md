# Production go-live checklist (MLJNO / Kubelíkova)

Use this when moving the **`ubyhost`** Render service from setup to live reporting.
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

## Phase 2 — Render production service

- [ ] Blueprint applied; `ubyhost` service on **Starter** with disk enabled
  (`render.yaml` disk block).
- [ ] `UBYHOST_ADMIN_USERNAME` and `UBYHOST_ADMIN_PASSWORD` set in Render (production only).
- [ ] `UBYHOST_UBYPORT_ENV=test` (stay on test until Phase 4 passes).
- [ ] `UBYHOST_DEPLOYMENT=production`
- [ ] Domain on Cloudflare (or `.cz` nameservers → Cloudflare) — see
      [CLOUDFLARE.md](CLOUDFLARE.md)
- [ ] Proxied A record, SSL **Full (strict)**, origin certificate on server
- [ ] `UBYHOST_PUBLIC_BASE_URL` resolves to the production URL (set automatically via
  `RENDER_EXTERNAL_URL` in the blueprint).
- [ ] First deploy completed; `/healthz` shows `deployment: production`, `ubyport_env: test`.
- [ ] Admin login works; password changed from bootstrap value.
- [ ] Run `scripts/backup_data.sh` once and confirm a backup file exists.

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

- [ ] In Render, set `UBYHOST_UBYPORT_ENV=prod` on **`ubyhost` only** (not staging).
- [ ] Redeploy production; Settings shows red **prod** badge.
- [ ] Submit one real guest batch; archive Doručenka.
- [ ] Enable Render deploy notifications and periodic off-site backups.

## Ongoing operations

| Task | Frequency |
|------|-----------|
| `backup_data.sh` | Weekly (cron) + after major changes |
| Review failed submissions / alerts | Daily during high season |
| Staging deploy after merges | Automatic; spot-check critical UI changes |
| Production deploy | Manual until CI history is trusted |
| Rotate admin password | After staff changes |
| UbyPort password | Only when police issues a new WS account |

## Staging (`ubyhost-staging`)

Keep staging on `mock` forever. Use it to:

- Train new staff on the UI
- Verify PRs before production deploy
- Test calendar import and guest flows without police side effects

Never copy production SQLite into staging without anonymising guest data (GDPR).
