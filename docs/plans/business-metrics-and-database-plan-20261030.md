# Plan: business metrics now, Postgres later (analytics replica + a shelf-ready migration)

Status: plan for owner decision, 2026-10-30. Written at the owner's request ("be my CTO"). Supersedes the tool-neutral recommendation in [data-tool-research-20261029.md](data-tool-research-20261029.md).

**Revision history (same day, four steers):**
1. **Rev 1:** Postgres on a managed DB ($15/mo) + Metabase.
2. **Rev 2:** owner relaxed privacy as a driver ("full in for efficiency"); options re-weighed.
3. **Rev 3:** owner noted the existing $44/mo 8 GB Lightsail bundle; production Postgres moved onto that box, $0/mo.
4. **Rev 4 (final, this text):** owner steer — "consider the migration for the next executive CTO." **Production stays SQLite.** The migration becomes a fully pre-analyzed playbook with explicit triggers (§4), owned by whoever holds the CTO seat when a trigger fires. Business metrics ship **now** through an analytics replica (§5) — the production database is untouched, so the BI blocker dies without a migration.

## 0. Owner constraints (2026-10-30, the owner's words)

- "I want to be scalable into the future, don't want to keep changing apps, ideally want to stay with one as long as possible on free tier."
- "Don't worry about privacy or users data, lets go full in for efficiency."
- "I already have a Lightsail instance for 44 USD."
- "Consider the migration for the next executive CTO."
- PostHog already covers web analytics. Nothing covers business metrics (MRR, invoices, churn).
- Billing went live in production 2026-10-29; Stripe Connect rails (0435-0442) and property pages (0430-0434) are mid-flight.
- Solo operator: every hour must earn itself; risk belongs where the revenue is.

## 1. The recommendation now

**Do nothing to the production database.** SQLite stays, Litestream stays, the four backup layers stay. Instead, one new scheduled job copies the money tables into a small **analytics Postgres container** on the existing 8 GB instance (a read-only copy by construction), and **self-hosted Metabase OSS** runs on top of that copy. Total: **$0/month, zero production risk, business metrics in one brief.** The SQLite-to-Postgres migration is fully pre-analyzed below (§6) and waits for its triggers (§4) — the next executive CTO (a future chat, a future hire, or the owner) executes a playbook that is already written, not a project that must be re-discovered.

The anti-churn principle survives untouched: the Postgres-portable SQL rules (`ON CONFLICT`, `RETURNING`, no `lastrowid`) are the standing insurance that the migration, whenever it happens, is a project measured in sessions, not months.

## 2. The strategic principle: anti-churn lives at the data layer

The owner's stated fear is changing tools every year. Two mechanisms kill that churn:

- **The portable-SQL rules** make the production database switchable at low cost at any time. That is why they exist; they stay verbatim.
- **The analytics replica** makes the BI layer independent of whatever the production database is. Metabase, Looker Studio, or any future tool points at the replica; switching BI tools is a weekend, and switching the production DB (§6) never re-triggers a BI change.

Together: both layers are swappable, so nothing needs to be switched *now* to be safe *later*.

## 3. Why deferral is the right call (the CTO reasoning)

The original case for migrating now had three legs. Under the full-repo audit, two of them disappear and one gets a cheaper answer:

1. **"BI needs a connectable database"** — true, but BI needs *a* database, not *the* database. The replica (§5) gives Metabase a real Postgres with zero production coupling. Cheaper and safer than migrating production to get the same dashboards.
2. **"Concurrency is arriving"** — not yet. The app is single-host, write volume is calendar-sync + filings + month-end billing; SQLite's single-writer model has not shown contention. The ceiling exists but there is no evidence we are near it. The rule "no logic may assume a single writer" already keeps the door open.
3. **"Backups get simpler"** — Litestream + the four layers (0421) work and are drilled. No reason to churn a working, drilled backup system while billing is days old.

Risk timing: with billing live since yesterday and the payments rails mid-flight, the highest-risk week to churn the data layer is this one. Nothing about deferral is wasted: the audit numbers, the staging plan, the backup mapping and the escape hatches are all written down (§6) — that work is banked.

## 4. Triggers: when the next executive CTO pulls the ripcord

Execute the playbook (§6) when **any** of these fires:

- **T1 — A second app server is needed** (scaling, zero-downtime deploys, split worker host). This is the original rules.md condition, restated.
- **T2 — Real write contention**: SQLite `SQLITE_BUSY`/lock timeouts show up in the logs or Grafana, or the month-end billing run visibly degrades the app.
- **T3 — The box is out of headroom** for app + worker + monitoring + replica + Metabase, and the bundle upgrade path is exhausted.
- **T4 — HA/managed-database requirements appear** (real paying scale, contractual uptime, multi-AZ) — at that point the playbook's RDS escape hatch is the target, not Lightsail managed DB (its daily-only backups regress today's ~10 s Litestream RPO).
- **T5 — The replica stops being enough**: sync lag becomes a decision problem (e.g. needing intraday MRR), or the money tables outgrow the nightly-copy pattern.

Until a trigger fires, the playbook is dormant — reviewed when the owner's monthly check looks at spend and Grafana, not acted on.

## 5. The interim build: analytics replica + Metabase (the only new thing)

**What ships:** one brief, one PR.

- **Sync job**: a new scheduled job in the existing `scheduler.py` pattern (like `retention` at 03:30) — e.g. `analytics_sync` nightly. It reads the money tables through `db.py` helpers and writes them into the analytics Postgres: `billing_month_snapshot`, `platform_invoice`, `billing_account` (plan, discount, trial state), stay-fee aggregates, host account counts, churn/trial-ending views. Money tables only, by design: business metrics need revenue, not guest data.
- **Compose**: a `postgres-analytics` service (digest-pinned, `mem_limit: 512m`, profile `analytics`, joins `ubyhost-web`, no published ports) plus the Metabase service (`mem_limit: 1g`, profile `analytics`). Both live inside the existing $44 instance's headroom.
- **Read-only by construction**: the replica cannot corrupt production because it is a copy, not a connection. No read-only-user discipline needed against the live DB.
- **Health**: the job raises a `job_failed` alert on failure (existing pattern) and gets a `UBYHOST_HEARTBEAT_BACKUP_URL`-style heartbeat ping (existing healthchecks.io pattern) so silent staleness is impossible.
- **First dashboards** (from the cockpit plan §12): MRR + movement waterfall, plan mix, churn watchlist (trials ending, overdue invoices), portfolio aging, fee vs. subscription revenue. **Alerts**: overdue invoice, trial ending without conversion, MRR drop — the morning checklist automated.
- **Fallback unchanged**: the 0446 export endpoint and `backup.sh`/restore drills keep working exactly as today; the replica adds, replaces nothing.

If Looker Studio is ever preferred (co-equal per rev 2), it points at the replica's Postgres: publishing the replica endpoint (never the production DB) with a Google IP allowlist is an ops line item, acceptable per the owner's steer.

## 6. The migration playbook (shelf-ready; owned by the next executive CTO)

Pre-analyzed 2026-10-30 against the full repo. **Do not start until a §4 trigger fires.** Read §4 first, then this.

**Audit numbers:** ~46 files use `db.immediate()`, ~51 `PRAGMA` references, one connection layer (`App/app/db.py`, 69 KB), 31+ migrations to replay (`0001` frozen `db.SCHEMA`), Litestream in the deploy path, filing path (ZapisUbytovane, SOAP, Doručenka PDFs) as the crown-jewel regression surface.

**Target (rev 3 analysis stands):** Postgres container on the existing 8 GB instance, private network only, $0 marginal. Managed DB demoted (daily-only backups regress Litestream's ~10 s RPO); RDS is the HA escape hatch. Neon rejected for production (Free cannot disable scale-to-zero; 100 CU-hrs suspends under continuous load) but used for disposable branch rehearsals.

**Backup mapping (0421 layers):** Litestream → WAL-G on the same S3 bucket (continuous WAL archiving, same RPO class); `backup.sh` `sqlite3 .backup` → `pg_dump` variant; Drive weekly and Lightsail instance snapshots unchanged.

**Stages when executed:**
1. `db.py` Postgres connection branch behind `UBYHOST_DB_URL` (one documented `ENVIRONMENT.md` row); CI dual-database. SQLite stays default.
2. Staging rehearsal: migrations replayed on a Neon free branch or the host's staging compose profile; full suite + filing dry-run green, twice.
3. Data-migration rehearsal: row counts, billing totals in Kč reconciled to the cockpit, snapshots month-by-month.
4. Cutover morning: final Litestream restore point; migrate on-host; flip the env var; smoke host app, admin, billing run, one filing dry-run; Grafana watch. Rollback: flip back — the SQLite file is untouched.
5. Close out: rules.md Database section updated ("UbyHost runs on Postgres…"), LIGHTSAIL.md rows updated, Litestream decommissioned after two clean weeks, WAL-G joins the restore drill.

**Hard gates:** filing path green before and after; HIGH RISK filing rule requires a written owner decision — the trigger + this playbook presented as that decision.

## 7. PostHog and Grafana

- **PostHog Cloud EU**: unchanged (web/product analytics, funnel). Host-app instrumentation is unlocked by the efficiency steer but waits for a real question to answer.
- **Grafana Cloud free**: ops only. Optional free additions: a postgres-exporter panel for the analytics DB; the existing `metrics.py` app job is the pattern.

## 8. Sequencing

| Phase | What | Effort | When |
|---|---|---|---|
| 1 | Analytics sync job + `postgres-analytics` + Metabase compose services; first dashboards + alerts | 1-2 briefs | now |
| 2 | Dashboards tuned to the cockpit plan §12; heartbeat wired | 1 brief | after phase 1 |
| 3 | Migration playbook review (this doc §4-§6) | 0 — read it | each monthly check |
| 4 | Migration execution | 5 sessions (§6) | only when a §4 trigger fires |

The UX smoothness plan (PR #581) and the payments rails (0435-0442) are independent and higher-priority than anything here.

## 9. Costs

| Item | Monthly |
|---|---|
| Everything existing (Lightsail 8 GB, S3, PostHog, Grafana, SES…) | unchanged |
| Analytics Postgres container + Metabase on the existing instance | $0 |
| **Total new** | **$0** |

## 10. Decisions needed from the owner

- **D1 — Production database stays SQLite.** The migration is deferred to §4 triggers; this document is the written record of that decision and the playbook the next executive CTO executes.
- **D2 — $0 new monthly spend confirmed.**
- **D3 — Metabase OSS self-hosted confirmed as the BI tool**, pointing at the analytics replica. Looker Studio remains a co-equal alternative against the same replica.
- Lines in `docs/context/decisions.md` when the phase-1 PR lands.

## 11. Non-goals

No production database change now, no managed database, no BigQuery, no warehouse, no per-seat BI, no Supabase, no Neon in production, no change to the backup layers, no change to PostHog or Grafana scopes, no change to guest pages.

## 12. What if we do nothing

Stated honestly: SQLite + the 0446 export endpoint + spreadsheets answers every business question at this scale for $0. The cost is the owner's morning checklist staying manual and the BI blocker surviving. Phase 1 costs one brief and closes it; the migration playbook costs nothing to keep.

## 13. Repo assets this plan builds on (audit 2026-10-30)

- **Restore drills are institutionalized** (`restore-drill.yml`): a future WAL-G path joins an existing habit.
- **The heartbeat pattern exists** (`UBYHOST_HEARTBEAT_FILING_URL`, `UBYHOST_HEARTBEAT_MONITORING_URL`): the sync job's health uses the same healthchecks.io pattern.
- **The scheduler pattern exists** (`retention` at 03:30, `photo_sweep`): `analytics_sync` is one more row in `OPERATIONS.md`'s jobs table.
- **The staging compose profile and mock UbyPort run on the host**: rehearsal environments already exist.
- **In-app analytics stay**: the funnel dashboard (0018, `admin_funnel.py`), `billing_analytics.py`, and the 0446 export endpoint keep their roles; Metabase is the operator layer on the money tables.
- **Env discipline exists** (`ENVIRONMENT.md`, `.env.example`, `env_guard.py`): new vars get documented rows.
- **No new subprocessors**: everything self-hosted; the vendor evidence file is unchanged.
- **Execution runs through the task system**: phase 1 is one or two `docs/tasks/NNNN-*.md` briefs, merged with `merge-pr-on-green.sh`, deployed by the owner.
