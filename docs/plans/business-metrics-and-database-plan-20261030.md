# Plan: business metrics and the database endgame (Postgres + Metabase)

Status: plan for owner decision, 2026-10-30. Written at the owner's request ("be my CTO") after the Looker Studio / Neon / Supabase discussion. Supersedes the tool-neutral recommendation in [data-tool-research-20261029.md](data-tool-research-20261029.md): the owner now wants a scalable, churn-resistant stack, not a deferral. Nothing here is executed yet; every phase needs its own PR.

## 0. Owner constraints (2026-10-30, the owner's words)

- "I want to be scalable into the future, don't want to keep changing apps, ideally want to stay with one as long as possible on free tier."
- PostHog already covers web analytics (marketing pages, funnel). Nothing covers business metrics (MRR, invoices, churn).
- "SQLite has been an enormous blocker" (2026-10-30, on BI tooling). The app is getting real users; billing is live in-app.
- Privacy-first culture: minimal subprocessors, data stays in-house where possible.
- Solo operator: every euro of monthly cost and every hour of ops time must earn itself.

## 1. The recommendation in one paragraph

Move the production database from SQLite to **PostgreSQL on a Lightsail managed database in Frankfurt (~$15/month)**, then stand up **self-hosted Metabase OSS (free)** against it for business metrics. PostHog stays for web/product analytics, Grafana stays for ops. Zero new subprocessors: the database stays inside the existing AWS account, Metabase runs on the existing host. Total new cost: ~$15/month. This is the last database migration UbyHost should ever do.

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
3. **Backups get simpler, not harder.** A managed Postgres includes AWS-native automated backups and snapshots. Litestream (which must be run and monitored by hand) is retired rather than replaced with another bespoke system.

The current rule says "UbyHost runs on SQLite. Postgres comes only when a second app server is needed." This plan proposes the owner-approved update: **Postgres comes when live business metrics + multi-user write load justify $15/mo — which is now.** The portability rules below it (`ON CONFLICT`, `RETURNING`, no `lastrowid`, `null_safe_eq`, no SQLite-only syntax) stay verbatim; the repo has been writing Postgres-portable SQL for exactly this day. That foresight is what makes this a Medium-risk project instead of a rewrite.

## 4. Where Postgres runs (options considered)

| Option | Cost | Verdict |
|---|---|---|
| **Lightsail managed DB, Frankfurt (micro: 1 vCPU, 1 GB RAM, 40 GB SSD)** | **$15/mo** | **Recommended.** Same AWS account and region as the app, flat price, automated daily backups + manual snapshots, private endpoint (no public exposure). No new subprocessor — AWS is already in the ROPA. Backup retention on automated backups is 7 days; supplement with monthly manual snapshots + monthly `pg_dump` to the existing S3 bucket. |
| Postgres container on the existing Lightsail host | $0 | Rejected for production, kept for staging. You become the backup/patch/monitoring system, the box is RAM-tight (app + monitoring + Metabase + Postgres), and a host failure takes app + DB together. This is Litestream's problems again, with more moving parts. |
| Neon (serverless Postgres, free tier: ~100 CU-hours/mo, 1 GB) | $0 | Rejected for production. Guest filing data would move to a new subprocessor (Databricks); scale-to-zero adds cold starts to app queries; free-tier projects are deleted after prolonged inactivity — unacceptable for a production database. Fine for throwaway experiments. |
| Supabase (free tier: 500 MB, pauses after 7 days inactivity) | $0 / $25 Pro | Rejected. 90% of the bundle (auth, storage, realtime, edge functions) goes unused; free tier pauses break a production app; it adds a subprocessor. The database inside Supabase is just Postgres — which you can own next to the app instead. |
| Amazon RDS | ~$13-20/mo effective for a small Single-AZ db.t-class + storage | Rejected for now: per-hour + storage billing complexity for no benefit at this scale. The escape hatch is real and documented: Lightsail → RDS is a standard `pg_dump` hop if HA/multi-AZ is ever genuinely needed. |

**Backup runbook after cutover:** automated daily backups (7-day retention) + one monthly manual snapshot + monthly `pg_dump` compressed to the existing S3 bucket (same bucket Litestream uses today). Litestream keeps running until the cutover PR, is disabled the morning of the cutover, and is decommissioned after two clean weeks.

## 5. The migration project (Medium risk, staged)

The audit numbers from 2026-10-30: ~46 files use `db.immediate()`, ~51 `PRAGMA` references, one connection layer (`App/app/db.py`), 31+ migrations to replay, Litestream in the deploy path, and the filing path (ZapisUbytovane, SOAP, Doručenka PDFs) as the crown-jewel regression surface.

**Stage 1 — provision and branch (1-2 sessions).** Create the Lightsail managed Postgres (private, Frankfurt, PostgreSQL 16). `db.py` gains a Postgres connection branch selected by an env var; SQLite stays the default. CI runs the suite against both.

**Stage 2 — staging rehearsal (1 session).** Replay all migrations on a staging Postgres (the container option from §4 is fine here). Full pytest + guest e2e + a filing dry-run against staging. Fix dialect gaps as they surface (this is where `PRAGMA` calls and transaction tweaks get resolved). Exit gate: everything green, twice.

**Stage 3 — data migration rehearsal (1 session).** Migration script through `db.py` (or pgloader); reconciliation checks: row counts per table, billing totals in Kč matched to the admin cockpit, snapshot tables matched month by month. Rehearse end-to-end once with production data restored to staging.

**Stage 4 — cutover (one quiet morning).** Maintenance notice; final Litestream restore point saved; migrate; flip the env var; smoke test the host app, admin, billing run, and one filing dry-run; watch Grafana for a day. Rollback plan: flip the env var back and restore from the Litestream point (kept warm for two weeks).

**Stage 5 — close out (same week).** `rules.md` Database section updated in the cutover PR: "UbyHost runs on Postgres (Lightsail managed, Frankfurt). SQLite is the dev/staging default." Litestream decommissioned after two clean weeks. Backup runbook added to the deploy docs.

**Hard gates:** the filing path must pass its tests unchanged before and after; HIGH RISK filing changes need a written owner decision first — this document, once the owner approves it, is that decision for the cutover step itself.

## 6. Business metrics: Metabase OSS (primary), Looker Studio (documented Plan B)

### 6.1 Metabase, self-hosted

- Free forever, unlimited dashboards and users (unlike the $100/mo Cloud Starter — self-hosting is strictly better for one operator).
- One Docker container on the existing Lightsail host (the planned 2 GB bundle covers it) or a $5-6 dedicated instance.
- Connects directly to Postgres through a **read-only user** granted only the money tables: `billing_month_snapshot`, `platform_invoice`, `billing_account`, stay-fee summaries. **No guest PII is granted to the BI role** — business metrics need revenue tables, not guest tables. This keeps the BI layer out of the guest-data blast radius entirely.
- **The database is never exposed to the internet**: Metabase talks to Postgres on the private network. Compare Looker Studio below.
- Alerts (e-mail) on: overdue invoices, trials ending without conversion, MRR drop — the churn watchlist from the revenue-cockpit plan, automated instead of a morning checklist.
- It is the de-facto startup standard: if the owner ever hires, the next person already knows it.

### 6.2 Looker Studio — why it is the Plan B, not the pick

| | Metabase OSS (self-hosted) | Looker Studio (free) |
|---|---|---|
| Cost | $0 software (+ hosting on existing box) | $0 |
| Where business data lives | **Your server only** | **Google's cloud** |
| DB exposure | Private network, no public endpoint | Requires a publicly reachable endpoint allowlisted to Google's published connector IP ranges |
| SQL | Full SQL editor + visual builder | Presentation layer; SQL via attached queries, weaker |
| Alerts/scheduling | Built-in | Limited |
| Ops cost | One Docker container to keep updated | Zero |

Looker Studio is a perfectly good tool and stays documented as the swap-in alternative: thanks to §2 it connects to the same Postgres whenever the owner wants it, and switching is a weekend, not a project. The reasons it loses the default slot: business data (MRR, customer names) leaves to a new subprocessor, the database must be reachable from the internet, and its SQL surface is weaker than Metabase's.

### 6.3 Rejected

- **Enterprise Looker** ($60k+/yr, BigQuery-centric): absurd for one operator. If you heard "Looker", the sensible version is Looker Studio.
- **BigQuery**: opens a warehouse + ETL pipeline for data that fits in Postgres memory. Never at this scale.
- **Power BI / Tableau**: per-seat pricing ($14/$75 user/mo) for a single viewer.
- **Superset**: more power than needed; Flask+Redis+Celery ops burden exceeds Metabase's for one person.
- **Grafana for business tables**: stays ops-only (Loki + Prometheus), as today.
- **PostHog for business metrics**: event analytics ≠ SQL reporting. MRR and invoices live in the database; shipping them to PostHog as events duplicates the source of truth and puts money data in a second place.

## 7. PostHog and Grafana: unchanged

- **PostHog Cloud EU**: web/product analytics, cookieless page views on marketing pages, host funnel from the server. Unchanged. The BI layer answers "how is the business doing"; PostHog answers "how do people use the site". Different questions, different tools, no overlap.
- **Grafana Cloud free**: ops only. Optional later (free, ops-scope): a Postgres exporter panel — connections, cache hit ratio, replication/backup status — next to the existing Loki/Prometheus panels.

## 8. Sequencing

| Phase | What | Effort | Depends on |
|---|---|---|---|
| 0 | Nothing changes today. The 0446 export endpoint still ships — it is the tool-neutral surface and the fallback analysis path. | — | — |
| 1 | Lightsail managed Postgres provisioned; `db.py` Postgres branch behind env var; CI dual-database | 1-2 sessions | owner D1+D2 |
| 2 | Staging rehearsal: migrations replayed, full suite green on Postgres | 1 session | phase 1 |
| 3 | Data-migration rehearsal + reconciliation checks | 1 session | phase 2 |
| 4 | Cutover morning + smoke + one-day Grafana watch | 1 morning | phase 3, quiet window |
| 5 | Metabase container + read-only user + first dashboard set + alerts | 1 session | phase 4 |
| 6 | Optional: Postgres panel in Grafana; Looker Studio eval if ever wanted | later | — |

The UX smoothness plan (PR #581) is independent: different surface, no shared files. Run in parallel or in either order.

## 9. Costs

| Item | Monthly |
|---|---|
| Lightsail managed Postgres (micro, Frankfurt) | $15 |
| Metabase OSS self-hosted | $0 |
| PostHog, Grafana, S3 | unchanged |
| **Total new** | **~$15** |

No new subprocessors: AWS is already in the ROPA. One ROPA review line to confirm ("analytics and BI run on the same infrastructure; no new processors"). If the Looker Studio Plan B is ever activated, that changes: Google enters the ROPA with a new line.

## 10. Decisions needed from the owner

- **D1 — Postgres migration approved.** Updates the Database rule (rules.md) in the cutover PR. This document, once approved, is the written owner decision the HIGH RISK filing rule requires.
- **D2 — $15/mo for the Lightsail managed database approved.**
- **D3 — Metabase OSS self-hosted confirmed as the business-metrics tool** (Looker Studio documented as the swap-in alternative, not the default).
- Each gets its line in `docs/context/decisions.md` when the corresponding PR lands.

## 11. Non-goals

No BigQuery, no data warehouse, no enterprise Looker, no per-seat BI, no Supabase bundle, no Neon for production, no guest PII in the BI layer, no change to PostHog or Grafana scopes, no change to guest pages, and no SPA rewrite (that debate lives in the UX plan).

## 12. What if we do nothing

Stated honestly, because it is viable: SQLite + the 0446 export endpoint + spreadsheets answers every business question at this scale, for $0. The cost of doing nothing is the status quo the owner described: the BI blocker stays, every future tool needs a sync layer, and the migration debt grows with the data. The trigger for this plan is that the owner wants live dashboards, wants to stop changing tools, and is willing to spend $15/mo to close the question permanently.
