# Owner manual setup (consolidated)

**Start here for click-by-click workflow:** **[OWNER_WORKFLOW_STEP_BY_STEP.md](OWNER_WORKFLOW_STEP_BY_STEP.md)** (GitHub, Render, Lightsail, AWS, every patch phase).

This file is the **reference** (tables, gates, preflight rules). Cursor applies code from `series/0001`–`0034` in merge order (`00_README_for_cursor.md`). Per-WP detail stays in `notes/WPNN-*.md` and `05_owner_checklist.md`.

**Do first (not tied to a patch):** Ask the Foreign Police / UbyPort support for access to the **UbyPort test environment** so Gate 2 is not blocked waiting on them.

**Core function (read once):** **[../../UBYPORT_CORE.md](../../UBYPORT_CORE.md)** — filing to UbyPort and receiving/storing the Doručenka PDF is the one thing that must never be wrong. Backups, Litestream, mail, and UI can wait; broken police reporting cannot.

**Already true on production (ubyhost.com):** Guest and host mail via **SES** has been live since 2026-09-21. Keep `UBYHOST_MAIL_BACKEND=ses` and the existing SES variables in the server `.env`; do not revert to `disabled`. **healthchecks.io** dead-man pings are already configured if your checks are green—no need to send ping URLs to Cursor or commit them anywhere (they stay only in `.env` on the server).

---

## 1. Prerequisites before any deploy works

### Accounts and monitoring

| Item | Purpose |
|------|---------|
| [healthchecks.io](https://healthchecks.io) (free) | Dead-man pings for jobs, Litestream, backups, filing watchdog |
| Uptime monitor (UptimeRobot, Better Stack, etc.) | HTTP check `https://<production-domain>/healthz` every minute; e-mail alerts |
| Password manager entry **“UbyHost production”** | Every secret below; never commit values (repo is public) |

### Production server and DNS

- Lightsail instance in **Frankfurt (eu-central-1)**. Workplan assumes **8 GB RAM / 2 vCPU** for production after infrastructure PRs.
- Static IP, app installed per `docs/LIGHTSAIL.md` (`/opt/ubyhost`, `deploy/lightsail/.env`).
- DNS: production hostname → static IP. If using Cloudflare: proxied A record, Full (strict), origin certs in `deploy/lightsail/caddy/certs/` when `CLOUDFLARE_PROXY=1`.

### Server `.env` — required for `preflight.sh` on every deploy

| Variable | Notes |
|----------|--------|
| `UBYHOST_DOMAIN` | Must match TLS host |
| `ACME_EMAIL` | Let's Encrypt / ACME contact |
| `UBYHOST_PUBLIC_BASE_URL` | `https://` URL; host should match `UBYHOST_DOMAIN` |
| `UBYHOST_ADMIN_PASSWORD` | Bootstrap admin; change in UI after first login |
| `UBYHOST_DEPLOYMENT` | `production` on production server |
| `UBYHOST_SECRET_KEY` | ≥ 32 chars, or empty for auto-generate on first boot; **save** generated value in password manager (decrypts DB and field encryption) |

### Operator identity (production only; server `.env` only)

App **refuses to start** in production if name, IČO, or address is empty. Use registered legal entity values:

- `UBYHOST_OPERATOR_NAME`, `UBYHOST_OPERATOR_ICO`, `UBYHOST_OPERATOR_DIC`, `UBYHOST_OPERATOR_ADDRESS`, `UBYHOST_OPERATOR_EMAIL`

Never put real operator PII in the repo.

### GitHub — production environment

Before automated production deploy:

- **Settings → Environments → `production`**: deployment branches limited to **`main`**.
- Secrets (not repository-level): `LIGHTSAIL_HOST`, `LIGHTSAIL_SSH_PRIVATE_KEY`, `LIGHTSAIL_KNOWN_HOSTS` (`ssh-keyscan <static-ip>`).
- Optional variable: `LIGHTSAIL_HEALTH_URL` (e.g. `https://<domain>/healthz`).

### AWS and backups (required for production deploy after WP05 / WP07)

| Area | What |
|------|------|
| **Litestream (WP05)** | S3 bucket in **eu-central-1**, IAM user scoped to prefix, keys in `.env`: `LITESTREAM_S3_BUCKET`, `LITESTREAM_ACCESS_KEY_ID`, `LITESTREAM_SECRET_ACCESS_KEY`, `LITESTREAM_S3_PATH=ubyhost/production` |
| **Nightly backup** | `UBYHOST_BACKUP_AGE_RECIPIENT` = public **age1…** recipient (not the private key) |
| **Backup dead-man (WP07)** | `UBYHOST_BACKUP_PING_URL` — healthchecks check (period 1 day, grace ~2 h). **Production:** leave as-is if the check is already green. |
| **SES** | **Production:** `UBYHOST_MAIL_BACKEND=ses` (already live). `UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION`, `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY` must stay set. **New staging** or a copy of `.env.example` may use `console` / `disabled` until that server has its own SES keys— that does not apply to current production. |

### UbyPort

- Production: `UBYHOST_UBYPORT_ENV=test` until a signed-off test filing, then `prod` (only with `UBYHOST_DEPLOYMENT=production`).
- Staging: `mock` or `test` only (never `prod` on staging).

### Turnstile

- `TURNSTILE_SECRET` from Cloudflare widget (site key can stay placeholder in example; production needs real secret).

---

## 2. Manual steps by patch (0001–0034)

Infrastructure first. After **0001–0005**, owner verifies **Gate 1**: `./scripts/restore_test.sh` passes and healthchecks are green. After **0006–0007**, **Gate 2**: one test filing from staging with `UBYHOST_UBYPORT_ENV=test`, Doručenka PDF downloads. **0008–0021**: at most one PR per day on staging (**Gate 3**). **0022–0034**: only when real hosts are live, unless owner asks.

### 0001 — WP05 Litestream

1. S3 **eu-central-1**: bucket `ubyhost-litestream-<suffix>`. Block public access, versioning, SSE-S3 default encryption.
2. Lifecycle: delete non-current versions after 30 days; remove expired delete markers; **do not** expire current versions.
3. IAM user `ubyhost-litestream` (no console), inline policy from `notes/WP05-litestream.md` (prefix `ubyhost/*`). Create access key.
4. Production `.env`: `LITESTREAM_*` keys, `LITESTREAM_S3_PATH=ubyhost/production`, optional `LITESTREAM_HEARTBEAT_URL` (5 min / 10 min grace).
5. Save `UBYHOST_SECRET_KEY` / `/data/secret_key` in password manager.
6. Deploy → `docker compose logs --tail=30 litestream` (`snapshot complete`) → `./scripts/restore_test.sh`. Repeat restore drill quarterly.

### 0002 — WP06 Worker process

- Production is already on 8 GB bundle: **no resize** (older notes described 2 GB migration; skip if already on 8 GB).
- Deploy; confirm `docker compose logs worker` shows **one** scheduler start and `docker compose logs ubyhost` shows **none**.
- If rolling back this PR: `docker compose stop worker` first.
- Optional: `UBYHOST_HEARTBEAT_URL` (WP07) to detect a dead worker within ~10 minutes.

### 0003 — WP07 Heartbeats, cache, compression

**Production:** if healthchecks are already green, only add any **new** keys this workplan introduces (for example `UBYHOST_HEARTBEAT_FILING_URL` in WP23) and redeploy. Cursor does **not** need your ping URLs—never paste them in chat or the repo.

**New server or first-time setup:** create healthchecks.io checks; put ping URLs in `.env` and redeploy:

| Check | `.env` key | Period | Grace |
|-------|------------|--------|-------|
| UbyPort submit sweep | `UBYHOST_HEARTBEAT_URL` | 10 min | 10 min |
| Calendar sync | `UBYHOST_HEARTBEAT_ICAL_URL` | 60 min | 30 min |
| Mail outbox | `UBYHOST_HEARTBEAT_MAIL_URL` | 5 min | 10 min |
| Nightly backup | `UBYHOST_BACKUP_PING_URL` | 1 day | 2 h |
| Litestream (WP05) | `LITESTREAM_HEARTBEAT_URL` | 5 min | 10 min |

Add external uptime check on `/healthz` (healthchecks does not do HTTP probes). Match periods if you override `UBYHOST_SUBMIT_SWEEP_MINUTES` or `UBYHOST_ICAL_POLL_MINUTES`.

### 0004 — STEP0 Staging deploy target

**Owner choice: staging on Render (recommended for you).** Follow **[STAGING_ON_RENDER_STEP_BY_STEP.md](STAGING_ON_RENDER_STEP_BY_STEP.md)** — click-by-click Render setup, what to put in Environment, manual deploy, and how staging differs from Lightsail production. Production SES and healthchecks stay on Lightsail; Render uses `console` mail and mock UbyPort only.

**Optional alternative:** second **Lightsail** staging server + GitHub environment `staging` + Actions **Deploy staging** (see `notes/STEP0-staging-deploy.md`). Skip this if you use Render.

**Never** put real guest PII on staging (Render or Lightsail).

### 0005 — WP32 Container sizing

- Production `.env`: `UBYHOST_WEB_WORKERS=4` (defaults: web 2g, worker 1g, Litestream 256m, Caddy 256m — leave unless tuning).
- After Litestream heartbeat green ~1 day: `UBYHOST_BACKUP_RETENTION_DAYS=7`.
- Staging (2 GB): `UBYHOST_WEB_WORKERS=2`, `UBYHOST_WEB_MEM=896m`, `UBYHOST_WORKER_MEM=448m`, `UBYHOST_LITESTREAM_MEM=128m`, `UBYHOST_CADDY_MEM=128m`.

### 0006 — WP30 Doručenka PDF

1. Deploy to staging with `UBYHOST_UBYPORT_ENV=test`.
2. File **one** test stay against the real UbyPort test endpoint.
3. Confirm report page shows **Download Doručenka (PDF)**. If UbyPort rejects the header/order, revert and report to Cursor.
4. Before production: verify WSDL / test endpoint lists `VracetPDF` after `Ubytovani` (`notes/WP30-dorucenka-pdf.md`).
5. On real filings, check logs for `DokumentPotvrzeni` and `receipt_pdf_bytes` > 0.

### 0007 — WP31 One automatic resend

- **No server steps.** On staging with mock timeout: one automatic resend in Reports, then no further auto sends.

### 0008 — WP01 Deadline after reporting

- None.

### 0009 — WP02 Property names in guest e-mail

- None.

### 0010 — WP03 Guide second pass

- Read Czech text of the four guide paragraphs once.

### 0011 — WP04 Admin guest data (HIGH RISK)

- Review HIGH RISK diff hunks in the PR.
- Confirm whether UbyPort Doručenka / error PDFs contain document numbers; if not, tell Cursor to unblock receipts for admin support.
- Decide whether admin workspace ZIP export (`/admin/users/{id}/export`) should require a reason (today: audit row only).

### 0012 — WP25 House book, filed-guest locking

- Open Report #2 → Technical details → Response. If no `DokumentPotvrzeni`, UbyPort did not return PDF — tell Cursor.

### 0013 — WP28 UI bug sweep

- No deploy steps. Optional: review `round3/shots/wp28-*.png`; decide open product questions (closed-stay links, cancelled-stay actions, etc.).

### 0014 — WP08 Passport upload hardening

- None.

### 0015 — WP09 Umami, privacy, subprocessors

- Umami Cloud **EU** region: add site, accept DPA, keep PDF. Subprocessor / transfer check (SCCs/DPF).
- Production `.env` only: `UMAMI_SCRIPT_URL`, `UMAMI_WEBSITE_ID`, optional `UMAMI_HOST_URL`, `UMAMI_DOMAINS` if `www` is served. Confirm operator fields match registry.
- After deploy: Umami on `/` only; **not** on `/login` or `/l/...`. Test opt-out on `/privacy`.
- Umami: Replays, Heatmaps, Distinct IDs **off**.
- Confirm Lightsail region **eu-central-1** before “EU, Frankfurt” claims.
- Hosts re-accept privacy policy 1.6 once after release.

### 0016 — WP27 Privacy first

- Confirm Lightsail **eu-central-1** before EU data-location claims.
- Decide when to set `UBYHOST_RETENTION_AUTOPURGE=1` (see Gate 4 / first host).

### 0017 — WP22 Retention alignment

- Read DPA § 11 and guest/host retention copy in the repo. When you accept it, set `UBYHOST_RETENTION_AUTOPURGE=1` on production and deploy (no external lawyer sign-off required unless you want one).
- Bump `UBYHOST_DPA_VERSION` / legal effective date only if you change retention wording later (hosts re-accept).
- Guest/stay-fee/invoice deletion needs `UBYHOST_RETENTION_AUTOPURGE=1`; photo/XML sweeps run regardless.
- Plan host-account closure design before billing hosts.

### 0018 — WP23 Filing watchdog (HIGH RISK)

- healthchecks.io **Filing** check: period 30 min, grace ~30 min → `UBYHOST_HEARTBEAT_FILING_URL`. Force red once to test e-mail.
- Production mail on SES for host mails and digest (heartbeat itself does not need mail).
- Train hosts: after manual UbyPort filing, use **“I filed this stay by hand in UbyPort”** (24 h undo window).

### 0019 — WP24 Terms, DPA, manual-filing texts

- Skim Terms/DPA 1.6 in the repo (especially § 10a, § 17, DPA § 11). External counsel is optional.
- Optional: notify hosts ≥ 30 days ahead (Terms § 22). You may release sooner if you accept that risk.
- Set `UBYHOST_LEGAL_EFFECTIVE_DATE=YYYY-MM-DD` in server `.env` to the release day before deploy (overrides the code default).
- Deploy on or after that date.
- Remove obsolete subprocessors (e.g. Drive/Render) from `/subprocessors` if dropped.

### 0020 — WP26 Guest languages DE/ES/FR

- Native-speaker review (legal notice → privacy → house book term → “claim” wording → mail copy → gendered forms → purpose/cookie strings → long country names). See `notes/WP26-guest-languages.md`.
- Decide default when `Accept-Language` is missing (English today vs Czech).
- **Do not** enable DE/ES/FR in `UBYHOST_GUEST_LANGS` until review is done.

### 0021 — WP33 Overdue stays, guest language switch

- Set `UBYHOST_GUEST_LANGS=en,cs` in production `.env` until each extra language is reviewed; then add (e.g. `en,cs,de`) and restart.
- On staging: confirm overdue unfiled stays appear in default Stays view.

**Gate 4 (first real host):** 0001–0021 merged; Gate 2 Doručenka; all healthchecks green; `UBYHOST_RETENTION_AUTOPURGE=1`; `UBYHOST_GUEST_LANGS` only includes reviewed languages; E2E test filing on staging (Friday before holiday + EU guest); send `compliance/05_manual_filing_fallback.md` to hosts.

### 0022 — WP10 Admin operations

- None (admin job times show “Never” until jobs run).

### 0023 — WP13 Perf logging

- Weekly on server:  
  `docker compose logs --no-color --since 168h app | python3 App/tools/perf_report.py`  
  Compare lock-wait p99 to 50 ms threshold (architecture review 7.2.5).

### 0024 — WP14 DB connection reuse (HIGH RISK)

- None on server (long-lived SQLite WAL is normal).
- Review `db.py` hunks manually in the PR.

### 0025 — WP15 iCal skip unchanged

- None (first sync after deploy reads all feeds once).

### 0026 — WP17 Copy cleanup

- Review changed Czech guest strings (legal notice, `legal_intro`, `privacy`, house book footnote).
- Lawyer re-read shortened guest legal notice (deadline wording moved to reporting section).

### 0027 — WP11 Admin funnel

- None.

### 0028 — WP12 Lifecycle mail

- Set `UBYHOST_OPERATOR_NAME`, `UBYHOST_OPERATOR_ICO`, `UBYHOST_OPERATOR_ADDRESS` (required for tips).
- Keep `UBYHOST_LIFECYCLE_MAIL=0` until self sign-up opt-out and privacy paragraph are live.
- Before enabling: test on staging with `UBYHOST_MAIL_BACKEND=console`; on production send one tip to yourself and check headers.

### 0029 — WP16 Data key / MultiFernet (HIGH RISK)

**Stage 1 — deploy code, no new key**

1. Backup (`deploy/lightsail/scripts/backup.sh` or `App/scripts/backup_data.sh`).
2. Deploy with `UBYHOST_DATA_KEYS` empty.
3. Click through staging, then production.
4. Rollback path: `scripts/reencrypt.py --rollback-new-fields --backup <file>` then old release.

**Stage 2 — add key**

1. Generate Fernet key; store in password manager with age identity.
2. `.env`: `UBYHOST_DATA_KEYS=<key>`, `UBYHOST_DATA_KEY_LEGACY=1`, restart.
3. Rolling back below WP16 without restore is not safe after this.

**Stage 3 — re-encrypt (in app container)**

1. Fresh backup.
2. `python scripts/reencrypt.py --dry-run`
3. `python scripts/reencrypt.py --backup /path/to/backup`
4. `python scripts/reencrypt.py --check` (all zeros; exit 0)
5. Stop if `unreadable` > 0.

**Stage 4 — later**

1. `UBYHOST_DATA_KEY_LEGACY=0`, restart.
2. Data key rotation: `UBYHOST_DATA_KEYS=<new>,<old>`, re-run stage 3, remove old key later.

### 0030 — WP18 Postgres portability

- None for deploy (migrations run at startup).
- If Render staging still exists: check SQLite version there before deploy.

### 0031 — WP19 Guest slugs

- Deploy staging first: old `/l/{token}` + PIN, then slug link without second PIN; rename slug → old URL redirects.
- No DNS/AWS changes. Tell hosts old links still work.

### 0032 — WP20 Self sign-up + Google Ads (HIGH RISK)

- Only when running Google Ads: conversion action “Import > Conversions from clicks”, auto-tagging, customer data terms.
- Production SES is already live; enable sign-up only when lawyer + Google Ads setup are ready (`UBYHOST_SIGNUP_ENABLED=1`).
- Staging: `UBYHOST_SIGNUP_ENABLED=1`, test `?gclid=TEST123`, consent box, verify, Settings → Privacy, CSV export.
- Upload CSV to Google Ads immediately after download; verify `Ad Personalization=Denied` rows.

### 0033 — WP21 Meta Conversions API (HIGH RISK)

- Events Manager dataset + CAPI token (no Pixel). Verify domain in Business Manager.
- Staging: `UBYHOST_META_DATASET_ID`, `UBYHOST_META_ACCESS_TOKEN`, `UBYHOST_META_TEST_EVENT_CODE`; test with `?fbclid=...` and consent box.
- Production: remove `UBYHOST_META_TEST_EVENT_CODE`.
- Counsel approves Meta copy (`CONSENT_VERSIONS["meta"]` if text changes).
- `utm_source=facebook` (or `instagram`) on ad/group links.

### 0034 — WP29 No em dashes

- Skim Czech host strings changed to parentheses/colons.
- Include changed guest strings in WP26 native-speaker review.

---

## 3. Feature flags and switches (off by default)

| Variable / setting | Default | Owner turns on when |
|--------------------|---------|-------------------|
| `UBYHOST_LIFECYCLE_MAIL` | `0` | Self sign-up opt-out + privacy text live (WP12); test on staging first |
| `UBYHOST_SIGNUP_ENABLED` | `0` | Lawyer-approved sign-up + Google Ads setup (WP20) |
| `UMAMI_WEBSITE_ID` / `UMAMI_SCRIPT_URL` | empty | Public marketing analytics configured (WP09); never on guest/auth pages |
| `UBYHOST_META_*` (CAPI) | empty | Meta ads + counsel approval (WP21) |
| `UBYHOST_GUEST_LANGS` | `en,cs` (after WP33) | Add `de`, `es`, `fr` only after native-speaker review (WP26) |
| `UBYHOST_RETENTION_AUTOPURGE` | `0` | **First real host** (Gate 4) — enables scheduled guest-record deletion |

Other production toggles (not “marketing” flags): `UBYHOST_GUEST_PIN=1`, `UBYHOST_ENABLE_SCHEDULER=1`, `UBYHOST_UBYPORT_ENV` starts as `test` then `prod`.

---

## 4. CI vs `preflight.sh` blockers

Two different gates: **GitHub Actions** refuses to *start* a remote deploy; **`deploy/lightsail/scripts/preflight.sh`** (run locally on the server inside `deploy.sh`) refuses to *build/start* the stack.

### GitHub Actions — production deploy

| Blocker | Detail |
|---------|--------|
| Manual only | Workflow **Deploy production**; input `force_confirm` must be **`DEPLOY`** |
| Branch | Deploys **`main`** head only |
| CI | All check runs on commit must **succeed**: `test`, `smoke`, `guest-browser`, `shellcheck`, `docker`, `secrets` |
| Secrets | `production` environment: `LIGHTSAIL_HOST`, `LIGHTSAIL_SSH_PRIVATE_KEY`, `LIGHTSAIL_KNOWN_HOSTS` |
| Server identity | Remote script refuses if server `.env` `UBYHOST_DEPLOYMENT` ≠ target |

### GitHub Actions — staging deploy

| Blocker | Detail |
|---------|--------|
| Environment | `staging` secrets/variable |
| CI | Green CI **required by default**; optional checkbox to skip (staging only) |
| UbyPort | Workflow can set `UBYHOST_UBYPORT_ENV` to `mock` or `test` |

### GitHub Actions — Deploy preflight (read-only)

- Does **not** deploy; SSH prints whether keys are SET/MISSING (never secret values).
- Fails if `LIGHTSAIL_*` missing in chosen environment.
- Use after STEP0 to confirm `UBYHOST_DEPLOYMENT` and Litestream keys present.

### `preflight.sh` — hard errors (deploy stops)

| Condition | Production | Staging |
|-----------|------------|---------|
| Empty `UBYHOST_DOMAIN`, `ACME_EMAIL`, `UBYHOST_PUBLIC_BASE_URL`, `UBYHOST_ADMIN_PASSWORD` | ✓ | ✓ |
| `UBYHOST_DEPLOYMENT=staging` without `UBYHOST_UBYPORT_ENV=mock` or `test` | — | ✓ |
| Staging mock without `COMPOSE_PROFILES=staging` or wrong `UBYHOST_MOCK_URL` | — | ✓ |
| `LITESTREAM_S3_PATH` contains `production` on staging | — | ✓ |
| `COMPOSE_PROFILES=staging` on production | ✓ | — |
| `UBYHOST_UBYPORT_ENV=prod` without `UBYHOST_DEPLOYMENT=production` | ✓ | ✓ |
| `UBYHOST_GUEST_PIN=0` on production | ✓ | — |
| `UBYHOST_ICAL_ALLOW_PRIVATE=1` on production | ✓ | — |
| Empty `UBYHOST_BACKUP_AGE_RECIPIENT` | ✓ | — |
| Empty `UBYHOST_BACKUP_PING_URL` | ✓ | — |
| RAM &lt; ~1.7 GB without `UBYHOST_ALLOW_SMALL_HOST=1` | ✓ | ✓ |
| Empty `LITESTREAM_S3_BUCKET` / access key / secret on production | ✓ | — |
| Invalid `LITESTREAM_S3_PATH` (leading/trailing `/`) | ✓ | ✓ |
| `UBYHOST_SECRET_KEY` shorter than 32 when set | ✓ | ✓ |
| Missing Cloudflare origin certs when `CLOUDFLARE_PROXY=1` | ✓ | ✓ |
| `UBYHOST_WEB_WORKERS` not integer 1–16 (WP32) | ✓ | ✓ |

### `preflight.sh` — warnings only (deploy continues)

- `LITESTREAM_HEARTBEAT_URL` empty on production
- `UBYHOST_DEPLOYMENT` not `production` or `staging`
- Production + `UBYHOST_UBYPORT_ENV=mock`
- `UBYHOST_ENABLE_SCHEDULER=0` on production
- Render-like env vars / `onrender.com` in URLs on Lightsail
- `UBYHOST_PUBLIC_BASE_URL` not `https://` or host ≠ `UBYHOST_DOMAIN`
- Low RAM with `UBYHOST_ALLOW_SMALL_HOST=1`

### Application runtime (not `preflight.sh`)

- Production: empty `UBYHOST_OPERATOR_NAME`, `UBYHOST_OPERATOR_ICO`, or `UBYHOST_OPERATOR_ADDRESS` → app refuses to start.
- `UBYHOST_MAIL_BACKEND=ses` without full SES variables → mail subsystem refuses to start (stack may still boot with `disabled`).

---

## 5. Quick reference — owner gates

| Gate | When | Pass criteria |
|------|------|----------------|
| 1 | After 0001–0005 | `restore_test.sh` OK; all healthchecks green |
| 2 | After 0006–0007 | Test Doručenka PDF from staging + UbyPort test |
| 3 | During 0008–0021 | Staging click-through per PR (≤1 PR/day) |
| 4 | First real host | 0001–0021 done; Gate 2; healthchecks; `UBYHOST_RETENTION_AUTOPURGE=1`; `UBYHOST_GUEST_LANGS` reviewed only |

---

*Sources: `05_owner_checklist.md`, `00_README_for_cursor.md`, `notes/WP*.md`, `notes/STEP0-staging-deploy.md`, `deploy/lightsail/scripts/preflight.sh`, `.github/workflows/deploy-*.yml`.*
