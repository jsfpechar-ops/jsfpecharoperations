# Plan: business metrics and the database endgame (Postgres + Metabase)

Status: plan for owner decision, 2026-10-30. Written at the owner's request ("be my CTO") after the Looker Studio / Neon / Supabase discussion. Supersedes the tool-neutral recommendation in [data-tool-research-20261029.md](data-tool-research-20261029.md): the owner now wants a scalable, churn-resistant stack, not a deferral. Nothing here is executed yet; every phase needs its own PR.

**Revision 2 (2026-10-30):** the owner's steer — "don't worry about privacy or users data, lets go full in for efficiency." Data location, subprocessors, and PII-minimization are removed as decision drivers; the objective is owner time, cost predictability, and speed.

**Revision 3 (2026-10-30, decisive):** the owner pointed out production already runs on a **General purpose 8 GB / 2 vCPU / 160 GB Lightsail bundle ($44/mo)** — ~4 GB free above the container caps, a four-layer backup system (Litestream→S3 continuous, daily on-volume snapshots, weekly Drive off-site, daily Lightsail instance snapshots), and digest-pinned images as the repo convention. Production Postgres therefore moves **onto the existing instance** as one more Compose service. Total new spend for the whole plan: **$0/month.** The Lightsail managed database is demoted to a documented escape hatch — its automated backups are daily-only, which would **regress** recovery point from today's ~10 s Litestream RPO to up to 24 h. That fact alone disqualifies it as the default.

## 0. Owner constraints (2026-10-30, the owner's words)

- "I want to be scalable into the future, don't want to keep changing apps, ideally want to stay with one as long as possible on free tier."
- "Don't worry about privacy or users data, lets go full in for efficiency."
- "I already have a Lightsail instance for 44 USD."
- PostHog already covers web analytics (marketing pages, funnel). Nothing covers business metrics (MRR, invoices, churn).
- "SQLite has been an enormous blocker" (2026-10-30, on BI tooling). The app is getting real users; billing is live in-app.
- Solo operator: every hour of ops time must earn itself; costs must be predictable, not metered surprises.

## 1. The recommendation in one paragraph

Move the production database from SQLite to **PostgreSQL running as a Compose service on the existing $44/mo Lightsail instance**, with continuous WAL archiving to the existing S3 bucket replacing Litestream, then stand up **self-hosted Metabase OSS (free)** on the same box for business metrics. PostHog stays for web/product analytics, Grafana stays for ops. Total new cost: **$0/month**. This is the last database migration UbyHost should ever do. Efficiency-wise it is the strongest version of the plan: no new AWS resources, no new providers, no new bills, the database lives where the app lives (as it does today with SQLite), and the backup promise stays the same class as what runs in production right now.

## 2. The strategic principle: anti-churn lives at the data layer

The owner's stated fear is changing tools every year. The fix is not picking a "final BI tool" — it is making the **contract** stable so every layer above the database is swappable.

The stable contract is the Postgres schema: `billing_month_snapshot`, `platform_invoice`, `billing_account`, the stay-fee tables. Every serious BI tool (Metabase, Looker Studio, Grafana, Superset, Power BI, Tableau, a future hire's favourite) speaks SQL against Postgres. Once the database is Postgres:

- Switching BI tools later = re-point a connection + rebuild dashboards. No app change, no migration project.
- The warehouse question (BigQuery et al.) never opens, because at this scale Postgres answers business questions directly.

So: churn-proof the database (one migration, once), keep the BI layer thin and replaceable. Do the opposite — keep SQLite and pick a cloud BI tool — and every future tool needs a sync layer, an export job, or a connector hack. That is the churn the owner is trying to avoid.

## 3. Why Postgres, and why now (the CTO call)

Three needs converge at the same time:

1. **BI needs a connectable database.** No serious BI tool reads SQLite natively (Metabase cannot; Looker Studio cannot). Every one of them reads Postgres natively. This is the blocker the owner keeps hitting.
2. **Concurrency is arriving.** Paying users, subscriptions, invoices: SQLite's single-writer model is fine today, but the ceiling appears as operational pain (write contention under backup, lock timeouts during month-end billing runs), not as traffic. Postgres removes the ceiling permanently.
3. **The infrastructure for Postgres is already bought.** The 8 GB / 2 vCPU box has ~4 GB free above the container caps, the app+DB already share a host today (SQLite is on the same volume as the app), the deploy convention (digest-pinned Compose services, profile-gated) slots a `postgres` service in exactly where `litestream` sits now, and the S3 bucket, retention layers, and restore drills already exist. The marginal cost of Postgres here is one Compose service and one env-var switch in `db.py`.

The current rule says "UbyHost runs on SQLite. Postgres comes only when a second app server is needed." This plan proposes the owner-approved update: **Postgres comes when live business metrics + multi-user write load justify it — which is now, at $0 marginal cost.** The portability rules below it (`ON CONFLICT`, `RETURNING`, no `lastrowid`, `null_safe_eq`, no SQLite-only syntax) stay verbatim; the repo has been writing Postgres-portable SQL for exactly this day. That foresight is what makes this a Medium-risk project instead of a rewrite.

## 4. Where Postgres runs (options re-weighed, rev 3)

| Option | Cost | Verdict |
|---|---|---|
| **Postgres container on the existing 8 GB instance** | **$0 marginal** | **Recommended.** Joins the `ubyhost-web` Compose network as a `postgres` service (digest-pinned like caddy/alloy/litestream), no port published to the host — unreachable from outside, exactly like the app. Same failure domain as today (app + DB on one host is the status quo with SQLite). Caps: `mem_limit: 1g` (`UBYHOST_PG_MEM`) — with web 2g + worker 1g + caddy 256m + alloy 512m + the rest, caps sum to ~5.5 GB on an 8 GB box, leaving OS/Docker/page cache the same class of headroom as today. Backup continuity in §4.1. |
| **Lightsail managed DB, Frankfurt ($15/mo)** | $15/mo | **Demoted to escape hatch.** The decisive fact: its automated backups are **daily** with no point-in-time recovery — moving to it would regress RPO from today's ~10 s (Litestream) to up to 24 h, on the one system (guest filings) where losing a day is the worst outcome. It also adds $180/yr for patching-and-isolation benefits the solo operator can get from a digest bump. Keep as the documented lift-and-shift target if the box ever runs out of headroom (pg_dump hop, one session). |
| Neon, free tier (100 CU-hrs/project/mo, 1 GB, 10 branches) | $0 | **Rejected for production, promoted for staging.** Free cannot disable scale-to-zero (compute suspends after 5 min idle) and continuous traffic exhausts 100 CU-hrs in days, after which compute is **suspended until the next month** — an outage, not a bill. But as the rehearsal environment it is ideal: zero install, zero ops, disposable copy-on-write branches for migration rehearsals (§5). |
| Postgres on a new instance | $7-20/mo | Rejected: new bill for no failure-isolation benefit at this scale. |
| Supabase (free: 500 MB, pauses after 7 days) | $0/$25 | Rejected: 90% of the bundle unused; a paused production database is an outage with extra steps. |
| Amazon RDS | ~$13-20/mo effective | Rejected for now. Escape hatch if HA/multi-AZ is ever genuinely needed. |

### 4.1 Backup continuity: WAL archiving replaces Litestream, same promise

Today's four layers (0421) map one-to-one:

| Layer | Today (SQLite) | After cutover (Postgres) |
|---|---|---|
| Continuous off-site | Litestream → S3, 10 s sync | **WAL-G → same S3 bucket**, continuous WAL archiving, same RPO class (seconds/minutes) |
| Quick local copy | `backup.sh` daily (`sqlite3 .backup`) | `backup.sh` variant running `pg_dump` daily to the same `/data/backups` age-encrypted retention |
| Independent off-site | `backup-gdrive.sh` weekly | unchanged |
| Whole-server snapshot | Lightsail automatic daily snapshots (7-day) | unchanged — it captures the Postgres volume too |

WAL-G slots into Compose as a profile service shaped exactly like `litestream` (same env pattern, same S3 credentials, `depends_on` the app, digest-pinned image). The restore runbook gets a WAL-G equivalent of the Litestream restore block; the quarterly rebuild drill covers it from then on. **Litestream stays in place until the cutover PR disables it** — the old and new continuous layers overlap during the migration window.

## 5. The migration project (Medium risk, staged)

Audit numbers from 2026-10-30: ~46 files use `db.immediate()`, ~51 `PRAGMA` references, one connection layer (`App/app/db.py`), 31+ migrations to replay, and the filing path (ZapisUbytovane, SOAP, Doručenka PDFs) as the crown-jewel regression surface.

**Stage 1 — Compose service + connection branch (1-2 sessions).** Add the digest-pinned `postgres` service (profile-gated, `UBYHOST_PG_MEM` cap, joins `ubyhost-web`, no published ports) and the WAL-G profile service. `db.py` gains a Postgres connection branch selected by an env var (`UBYHOST_DB_URL`); SQLite stays the default. CI runs the suite against both.

**Stage 2 — staging rehearsal (1 session).** Replay all migrations on a **Neon free-tier project** (or a local Compose `postgres` on the dev machine — either is a real Postgres). Full pytest + guest e2e + a filing dry-run. Fix dialect gaps as they surface (`PRAGMA` calls, transaction tweaks). Exit gate: everything green, twice.

**Stage 3 — data migration rehearsal (1 session).** The migration script runs on-host (the SQLite file and Postgres are on the same volume — no network transfer, the simplest possible migration). Reconciliation checks: row counts per table, billing totals in Kč matched to the admin cockpit, snapshot tables matched month by month. Rehearse against a throwaway Neon branch loaded with a production backup first; then once on-host with the stack stopped.

**Stage 4 — cutover (one quiet morning).** Maintenance notice; final Litestream restore point saved; run the migration on-host; flip `UBYHOST_DB_URL`; smoke test the host app, admin, billing run, and one filing dry-run; watch Grafana for a day. Rollback: unset the env var, restart on the untouched SQLite file (kept in place, never deleted), WAL-G and Litestream both warm for two weeks.

**Stage 5 — close out (same week).** `rules.md` Database section updated in the cutover PR: "UbyHost runs on Postgres (container on the production instance, Frankfurt). SQLite is the dev/staging default." `docs/LIGHTSAIL.md` lines updated ("Do not buy Lightsail managed MySQL" row and the "Managed database: not needed" cost row). Litestream service removed after two clean weeks; backup runbook + restore drill updated to the WAL-G path.

**Hard gates:** the filing path must pass its tests unchanged before and after; HIGH RISK filing changes need a written owner decision first — this document, once the owner approves it, is that decision for the cutover step itself.

## 6. Business metrics: Metabase OSS (default), Looker Studio (co-equal alternative)

### 6.1 Metabase, self-hosted on the same box

- Free forever, unlimited dashboards and users (unlike the $100/mo Cloud Starter).
- One more Compose service on the 8 GB instance (`mem_limit: 1g`), talking to Postgres over the private `ubyhost-web` network. Sizing check: web 2g + worker 1g + pg 1g + metabase 1g + caddy/alloy/exporters ~1.2g ≈ 6.2 GB in caps on 8 GB — caps are ceilings, actual usage is far lower, and the documented bundle-upgrade path exists if it ever gets tight.
- Connects through a **read-only Postgres user**. The read-only rule is an operational guardrail, not privacy: a typo'd BI query must never be able to touch production; incident recovery is the most expensive activity a solo operator has.
- Alerts (e-mail) on: overdue invoices, trials ending without conversion, MRR drop — the churn watchlist from the revenue-cockpit plan, automated instead of a morning checklist.
- The de-facto startup standard: if the owner ever hires, the next person already knows it.

### 6.2 Looker Studio — a legitimate alternative

With data location off the table (owner, 2026-10-30), the choice is purely capability vs ops:

| | Metabase OSS (self-hosted) | Looker Studio (free) |
|---|---|---|
| Cost | $0 | $0 |
| Hosting effort | One container to keep updated | Zero |
| SQL | Full SQL editor + visual builder | Presentation layer; attached queries, weaker |
| Alerts/scheduling | Built-in, e-mail | Limited |
| Setup requirement | Private network only | A DB endpoint reachable from Google's connector IP ranges — possible with a published port + allowlist, one ops line item, acceptable per owner |
| Switching later | Either to the other is a weekend, because the Postgres contract holds (§2) | same |

Metabase remains the default on capability (full SQL, alerts, the churn-watchlist automation); Looker Studio is equally acceptable on principle. If the owner ever wants zero-hosting BI, activating it against the same Postgres is a non-event.

### 6.3 Rejected

- **Enterprise Looker** ($60k+/yr): absurd for one operator. The sensible "Looker" is Looker Studio.
- **BigQuery**: a warehouse + ETL pipeline for data that fits in Postgres memory. Never at this scale.
- **Power BI / Tableau**: per-seat pricing ($14/$75 user/mo) for a single viewer.
- **Superset**: Flask+Redis+Celery ops burden exceeds Metabase's for one person.
- **Grafana for business tables**: stays ops-only (Loki + Prometheus), as today.
- **PostHog for business metrics**: event analytics ≠ SQL reporting; MRR and invoices live in the database, and shipping them as events duplicates the source of truth.

## 7. PostHog and Grafana

- **PostHog Cloud EU**: unchanged for web/product analytics and the host funnel. **New option unlocked by the efficiency steer:** instrumenting the host app itself (feature usage, onboarding drop-off) is now available — a separate small decision, not part of this plan.
- **Grafana Cloud free**: ops only. Optional later (free, ops-scope): a postgres exporter panel — connections, cache hit ratio, WAL-lag alert — next to the existing panels.

## 8. Sequencing

| Phase | What | Effort | Depends on |
|---|---|---|---|
| 0 | Nothing changes today. The 0446 export endpoint still ships — the tool-neutral surface and fallback path. | — | — |
| 1 | `postgres` + WAL-G Compose services; `db.py` Postgres branch behind env var; CI dual-database | 1-2 sessions | owner D1+D2 |
| 2 | Staging rehearsal (Neon free or local Compose): migrations replayed, suite green on Postgres | 1 session | phase 1 |
| 3 | Data-migration rehearsal + reconciliation checks | 1 session | phase 2 |
| 4 | Cutover morning + smoke + one-day Grafana watch | 1 morning | phase 3, quiet window |
| 5 | Metabase container + read-only user + first dashboard set + alerts | 1 session | phase 4 |
| 6 | Optional: postgres exporter in Grafana; Looker Studio eval; host-app PostHog instrumentation | later | — |

The UX smoothness plan (PR #581) is independent: different surface, no shared files. Run in parallel or in either order.

## 9. Costs

| Item | Monthly |
|---|---|
| Lightsail General purpose 8 GB bundle | $44 (unchanged, already paid) |
| Postgres container on that instance | $0 |
| WAL-G → existing S3 bucket | $0 (marginal storage) |
| Neon free tier (staging/rehearsal) | $0 |
| Metabase OSS self-hosted | $0 |
| PostHog, Grafana, S3 | unchanged |
| **Total new spend for the whole plan** | **$0** |

Governance overhead dropped as a decision driver per the owner's steer. The only paperwork left is the `decisions.md` lines in §10.

## 10. Decisions needed from the owner

- **D1 — Postgres migration approved.** Updates the Database rule (rules.md) and the LIGHTSAIL.md cost/architecture rows in the cutover PR. This document, once approved, is the written owner decision the HIGH RISK filing rule requires.
- **D2 — zero new monthly spend confirmed** (Postgres on the existing $44 instance; managed DB explicitly declined on RPO grounds).
- **D3 — BI tool confirmed.** Metabase by default; Looker Studio equally acceptable — a taste decision, reversible in a weekend either way.
- Each gets its line in `docs/context/decisions.md` when the corresponding PR lands.

## 11. Non-goals

No BigQuery, no data warehouse, no enterprise Looker, no per-seat BI, no Supabase bundle, no Neon for production, no Lightsail managed database (RPO regression), no new AWS resources, no change to PostHog or Grafana scopes, no change to guest pages, and no SPA rewrite (that debate lives in the UX plan).

## 12. What if we do nothing

Stated honestly, because it is viable: SQLite + the 0446 export endpoint + spreadsheets answers every business question at this scale, for $0. The cost of doing nothing is the status quo the owner described: the BI blocker stays, every future tool needs a sync layer, and the migration debt grows with the data. The trigger for this plan is that the owner wants live dashboards and wants to stop changing tools — and with revision 3, closing the question permanently costs nothing per month.

## 13. Repo assets this plan builds on (audit 2026-10-30)

The plan above was written against the full repo. These existing assets make each phase cheaper than it looks on paper:

- **Restore drills are already institutionalized**: `restore-drill.yml` runs the rebuild drill; the WAL-G restore path joins it instead of needing a new habit.
- **The heartbeat pattern exists**: `UBYHOST_HEARTBEAT_FILING_URL` and `UBYHOST_HEARTBEAT_MONITORING_URL` already alert on silent failure via healthchecks.io. WAL-G archive health gets a `UBYHOST_HEARTBEAT_BACKUP_URL` sibling — same pattern, same runbook.
- **A staging compose profile already runs on the production host** (`staging` + `mock-ubyport`), so Phase 2 can rehearse against a Postgres right next to the app; Neon branches stay for disposable full-data rehearsals.
- **The metrics pipeline already has an app job**: `metrics.py` exports `ubyhost_requests_total` etc. to Grafana Cloud Prometheus; a postgres exporter joins the same stack (`OBSERVABILITY.md` pattern, compose profile `monitoring`).
- **In-app analytics already exist and stay**: the funnel dashboard (0018, `admin_funnel.py`), `billing_analytics.py` and the 0446 export endpoint answer host-facing and export questions. Metabase is the operator-side layer on top of the money tables, not a replacement for any of these.
- **Env var discipline exists**: `ENVIRONMENT.md` + `.env.example` + `env_guard.py` mean `UBYHOST_DB_URL` gets one documented row with a wrong-if-absent note, exactly like every other var.
- **No new subprocessors either way**: Postgres on the existing instance and self-hosted Metabase keep the vendor evidence file (`docs/vendors/README.md`) unchanged — efficient and true.
- **Execution runs through the existing task system**: each phase becomes one or two `docs/tasks/NNNN-*.md` briefs, merged with `scripts/merge-pr-on-green.sh`, deployed by the owner. Nothing about the workflow changes.
