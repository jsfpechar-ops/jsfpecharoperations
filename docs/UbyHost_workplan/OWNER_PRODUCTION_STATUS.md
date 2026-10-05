# Owner production status

Living checklist for **ubyhost.com** (Lightsail). Update this when you complete a gate or change production `.env`. Secrets stay only on the server — never in git.

**Last updated:** 2026-10-05 (from operator + deploy conversation; confirm anything marked “verify” on the server).

---

## Code on GitHub

| Item | Status |
|------|--------|
| Workplan **0001–0034** on `main` | **Done** — merged as PR **#237** |
| WP22/WP24 owner gate (no external counsel wait) | **Done** — PR **#275** merged |
| Litestream preflight when S3 empty | **Done** — PR **#273** merged |
| Follow-up bundle (filing safety, stay-fee fix, tests, Umami signup cleanup) | **Open** — PR **#277** (replaces obsolete draft wp-stack PRs **#238–#274** and filing PRs **#233**, **#235**, **#276**) |

After **#277** merges: run **Deploy production** from `main` again.

---

## Done on your side (operator)

| Area | Status | Notes |
|------|--------|--------|
| Password manager + `UBYHOST_SECRET_KEY` backup | **Done** | Required for Litestream restore |
| SES guest/host mail | **Done** | Live since 2026-09-21 |
| Operator identity in `.env` | **Done** | `UBYHOST_OPERATOR_*` |
| Turnstile | **Done** | Production hostnames |
| healthchecks.io — submit, iCal, mail, backup | **Done** | Reported green |
| Litestream → S3 (eu-central-1) | **Done** | Re-enabled after IAM `ListBucket` fix; restore drill passed |
| Production deploy from `main` | **Done** | Worker + web split (WP06); `ubyport=prod` on worker |
| `UBYHOST_RETENTION_AUTOPURGE=1` | **Done** | WP22 live deletion when due |
| `UBYHOST_GUEST_LANGS` | **Done** | Reviewed — keep **`en,cs`** until DE/ES/FR native review |
| Real hosts on app | **In progress** | Production serving real properties |
| Umami tracking snippet | **Ready** | Set `UMAMI_WEBSITE_ID` + `UMAMI_SCRIPT_URL=https://cloud.umami.is/script.js` in `.env` and deploy |
| WP22/WP24 legal effective date | **Set on server** | `UBYHOST_LEGAL_EFFECTIVE_DATE=2026-10-05` (or your chosen release day) — **verify** after deploy from #275 |
| Better Stack / uptime on `/healthz` | **Done** | Alongside healthchecks |

---

## Still to do (owner) — not blocked on Cursor

| Priority | Task | Why |
|----------|------|-----|
| **High** | Deploy latest `main` after **#275** / **#273** (and **#277** when merged) | Server must run merged retention default + Litestream preflight |
| **High** | `UBYHOST_HEARTBEAT_FILING_URL` + healthchecks **Filing** check (30 min / 30 min) | WP23 watchdog; force red once to test e-mail |
| **High** | `UBYHOST_TRUSTED_PROXY_CIDRS=172.16.0.0/12` when `CLOUDFLARE_PROXY=1` | Stops trusted-proxy warning; correct rate limits behind Cloudflare — see `docs/CLOUDFLARE.md` |
| **High** | Umami in `.env` + deploy; confirm `/` has script, `/login` and `/l/...` do not | WP09 |
| **Medium** | Doručenka on a **new** filing after #237 | Old rows may lack PDF; download on report page |
| **Medium** | Send hosts `compliance/05_manual_filing_fallback.md` | Gate 4 / WP23 “filed by hand” |
| **Medium** | Optional: GDrive off-site backup (`rclone`, `backup-gdrive.sh`, cron) | Complements nightly age backup + Litestream |
| **Low** | Render staging recreate | Only if you want UI test loop before prod deploys — see `STAGING_ON_RENDER_STEP_BY_STEP.md` |
| **Low** | UbyPort **test** portal access | Optional re-verify Doručenka; prod filing already works |
| **Later** | Native review DE/ES/FR before extending `UBYHOST_GUEST_LANGS` | WP26 |
| **Later** | `UBYHOST_SIGNUP_ENABLED=1`, Google/Meta ads, WP16 re-encrypt | Phase 4 — when you choose |

---

## Waiting on (external / optional)

| Item | Who |
|------|-----|
| Optional paid counsel hour | You — not a merge gate (WP22/WP24 shipped on operator decision) |
| Facebook group admins for posts | You |
| Google Ads / Meta when you run ads | You + platform setup |

---

## Obsolete open PRs

Draft PRs **#238–#271**, **#236**, **#233**, **#235**, **#276** duplicate work already on `main` or folded into **#277**. Close them after **#277** merges to avoid confusion.

---

## Quick deploy reminder

```bash
# On server
cd /opt/ubyhost/deploy/lightsail
./scripts/preflight.sh
./scripts/deploy.sh
```

Or GitHub Actions → **Deploy production** → branch `main` → confirm `DEPLOY`.
