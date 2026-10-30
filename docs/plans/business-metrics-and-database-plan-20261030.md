# Plan: business metrics now, Postgres later (analytics replica + a shelf-ready migration)

Status: plan for owner decision, 2026-10-30. Written at the owner's request ("be my CTO"). Supersedes the tool-neutral recommendation in [data-tool-research-20261029.md](data-tool-research-20261029.md).

**Revision history (same day, four steers):**
1. **Rev 1:** Postgres on a managed DB ($15/mo) + Metabase.
2. **Rev 2:** owner relaxed privacy as a driver ("full in for efficiency"); options re-weighed.
3. **Rev 3:** owner noted the existing $44/mo 8 GB Lightsail bundle; production Postgres moved onto that box, $0/mo.
4. **Rev 4:** owner steer — "consider the migration for the next executive CTO." **Production stays SQLite.** The migration becomes a fully pre-analyzed playbook with explicit triggers (§4), owned by whoever holds the CTO seat when a trigger fires. Business metrics ship **now** through an analytics replica (§5) — the production database is untouched, so the BI blocker dies without a migration.

5. **Rev 5:** the owner asked for the complete runway of pending steps to be part of the plan — everything that must be done, in gate order (§8), before anything new pushes further.

6. **Rev 6 (this text, post-review correction):** defines and reconciles the business metrics BEFORE any new infrastructure (§5a); Metabase OSS over a separate analytics copy is the preferred candidate, conditional on measured capacity, recovery and operational cost — "no additional hosting subscription" is a target, not a zero-cost or zero-risk guarantee. Metric/UX contract work proceeds independently of infrastructure. The first application step is a small read-only extraction (brief 0444), not the sync job.

## 0. Owner constraints (2026-10-30, the owner's words)

- "I want to be scalable into the future, don't want to keep changing apps, ideally want to stay with one as long as possible on free tier."
- "Don't worry about privacy or users data, lets go full in for efficiency."
- "I already have a Lightsail instance for 44 USD."
- "Consider the migration for the next executive CTO."
- PostHog already covers web analytics. Nothing covers business metrics (MRR, invoices, churn).
- Billing went live in production 2026-10-29; Stripe Connect rails (0435-0442) and property pages (0430-0434) are mid-flight.
- Solo operator: every hour must earn itself; risk belongs where the revenue is.

## 1. The recommendation now

**Do nothing to the production database.** SQLite stays, Litestream stays, the four backup layers stay. Instead, the path is: first define and reconcile the metrics (§5a), then a small read-only extraction of verified values (brief 0444), then — only if its preconditions (§5) hold — one scheduled job copying minimal, field-minimized money tables into an **analytics Postgres container** on the existing 8 GB instance (a read-only copy by construction), with **self-hosted Metabase OSS** on top. Corrected framing: the target is no additional hosting subscription, not a $0 or zero-risk guarantee; capacity, recovery and operating cost are measured before anything ships (§5), and a read-only copy removes most — not all — production risk (the sync job reads production through db.py). The SQLite-to-Postgres migration is fully pre-analyzed below (§6) and waits for its triggers (§4) — the next executive CTO (a future chat, a future hire, or the owner) executes a playbook that is already written, not a project that must be re-discovered.

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

## 5a. Metric definitions and reconciliation (REV 6: before any infrastructure)

These definitions bind every surface that shows a money number (cockpit, export, future Metabase). A metric without a definition here is not published.

| Metric | Required meaning |
|---|---|
| Subscription MRR | Effective recurring platform price, net of VAT and recurring discounts, normalized monthly. Excludes trials, one-off fees (carry, supplementary) and guest/merchant payment volume (Stripe rails money is not platform revenue) |
| Issued invoices | Count and amount reported SEPARATELY, with currency, tax treatment (BILLING_VAT_STATUS), voids, credits (storno) and replacements (corrective chain) defined |
| Overdue invoices | Explicit due-date rule, status rule (voided = excluded, paid_on set = excluded) and remaining-balance rule (no partial payments exist in source) |
| Collections | Distinguishes invoice `paid_on` status from actual cash: `bank_payment` rows with `matched_invoice_id` are the only allocation evidence; unmatched payments are not collections |
| MRR movement | Opening + new + expansion − contraction − churn = closing; explicit reactivation policy and sufficient snapshot history required; missing history is reported as unavailable, never zero |
| Account churn | Eligible paying accounts lost in period ÷ eligible accounts at period start; a cancellation REQUEST (`cancel_at_period_end`) differs from an effective end |
| Trials / account counts | Explicit grain (billing_account row vs user_account), eligibility (trial_started_at) and date basis (Europe/Prague business dates); joins must not multiply accounts |

Money rules: integer minor units (haler) or exact decimals; never float. Currencies stay separate (CZK only today) until an FX policy exists. Business dates are Europe/Prague. Missing history means unavailable, not zero.

Source gaps to resolve before any extraction ships (reverified against source 2026-10-30):

- `portfolio()` computes current quote-derived values (whole-Kč via `billing.quote`, net of recurring discount, incl. carry); annual normalization rounds whole-Kč (`_monthly`). VAT-exempt (`BILLING_VAT_STATUS=non_payer` default) — verify with the owner whether that is the filing reality.
- Invoice aggregates sum `total_haler` then truncate to whole CZK (`// 100`); storno marks the corrected invoice `voided = 1` and requires it unpaid; `mark_paid` only sets `paid_on`/`paid_via` on unpaid, unvoided, non-storno invoices. No partial payments, refunds or allocations exist in source.
- "Collected" today = invoices with `paid_on` in the month (status-derived). A cash-allocation ledger does not exist; `bank_payment.matched_invoice_id` (set by `bank_import`) is the only allocation evidence.
- Existing-row trends do not prove a complete historical month series; the snapshot job writes the CURRENT month only (scheduler daily + billing mutations). Historical movement/churn metrics are not yet verifiable.
- Billing tables are defined in migrations `0023_billing.sql` and `0031_billing_discount_snapshot.sql` (verified); scheduler call site `_job_billing_snapshot` (verified).

## 5. The interim build: analytics copy + Metabase (candidate, conditional)

**Preconditions (all measured before this phase starts):**

- Headroom: RAM, CPU, disk growth and I/O of app + workers + monitoring + backups on the 8 GB box, measured with the analytics services added. Earlier 512 MB Postgres / 1 GB Metabase caps were unverified.
- Recovery: Metabase needs a persistent production application database for dashboards/users/configuration, separate from its reporting connection; embedded H2 is not acceptable. Configuration/application data backed up off-host; restoring a dashboard and access settings demonstrated.
- Operational cost: refresh runs, stale-generation handling, upgrades and one more service to watch, accepted by the owner.

**Target architecture:**

```
Production SQLite
  -> consistent minimal snapshot (db.py helpers, explicit field minimization)
  -> isolated analytics load (staging generations: run id, schema version, source timestamp)
  -> validated published generation (transactional publish after validation)
  -> Metabase OSS (read-only BI role, private database networking)
```

**Requirements:** SQL only through `db.py` helpers; consistent extraction with explicit field minimization (contact/name fields do not enter the extract by default); staging generations with run id, schema version and source timestamp; transactional publication after validation; idempotent retries; correction/deletion propagation; a failed refresh retains the last successful generation, visibly stale; dashboards display the last successful source time and the expected refresh; freshness/missed-heartbeat checks independent of the sync job; a read-only BI reporting role and private database networking.

**What ships when the preconditions hold:**

- **Sync job**: a new scheduled job in the existing `scheduler.py` pattern (like `retention` at 03:30) — e.g. `analytics_sync` nightly. It reads the money tables through `db.py` helpers and writes them into the analytics Postgres: `billing_month_snapshot`, `platform_invoice`, `billing_account` (plan, discount, trial state), stay-fee aggregates, host account counts, churn/trial-ending views. Money tables only, by design: business metrics need revenue, not guest data.
- **Compose**: a `postgres-analytics` service (digest-pinned, profile `analytics`, joins `ubyhost-web`, no published ports) plus the Metabase service (profile `analytics`). Memory limits are set AFTER the §5 precondition measurement, not assumed (earlier 512 MB / 1 GB figures were unverified).
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
3. Data-migration rehearsal: row counts, billing totals in minor units reconciled to the cockpit, snapshots month-by-month; money and filing rehearsals explicitly verified.
4. Cutover morning: final Litestream restore point; migrate on-host; flip the env var; smoke host app, admin, billing run, one filing dry-run; Grafana watch. Rollback: flipping back is only safe BEFORE Postgres accepts new authoritative writes; after that, rollback requires a rehearsed reverse reconciliation (and quiescence of web mutations, workers, schedulers and callbacks, with final reconciliation before destination writes). An untouched SQLite file is not a rollback plan once the destination has accepted writes.
5. Close out: rules.md Database section updated ("UbyHost runs on Postgres…"), LIGHTSAIL.md rows updated, Litestream decommissioned after two clean weeks, WAL-G joins the restore drill.

**Hard gates:** filing path green before and after; HIGH RISK filing rule requires a written owner decision — the trigger + this playbook presented as that decision.

## 7. PostHog and Grafana

- **PostHog Cloud EU**: unchanged (web/product analytics, funnel). Host-app instrumentation is unlocked by the efficiency steer but waits for a real question to answer.
- **Grafana Cloud free**: ops only. Optional free additions: a postgres-exporter panel for the analytics DB; the existing `metrics.py` app job is the pattern.

## 8. The runway: what must be done, in order

**Nothing in a lower gate starts before the gates above it are closed.** Source of truth for each line: [status](../context/status.md) (updated 2026-10-29 — re-check it before executing; some rows may already be closed), plus this plan and the UX plan. Each gate lists its exit criterion.

**Gate 0 — the owner queue (one batched morning: merges, deploys, staging checks, letters)**

1. Merge the reviewed PRs with `scripts/merge-pr-on-green.sh`: Guide + Leon #465-468; the 0291-0302 buttons/fees/invoice line; #435 (passkey); TTLock #434 once its CI row is green.
2. Production deploy of everything merged since the last deploy (Actions → Deploy production, `force_confirm=DEPLOY`).
3. Add `uk` to `UBYHOST_GUEST_LANGS` and redeploy (0196 guest form).
4. Owner staging tests: TTLock change / calendar-stays / DST; door codes 0037-0038 owner steps; stay-fee e-mail 0220-0224; root login/calendar review (from #432).
5. Cloudflare rules 3-4 (0291-0302 row); passkey phone + iPad checks (0280-0283, 0290).
6. Credential letter to data box ybndqw9; verify `/healthz`.
7. 0403-0405 (guide import / Leon setup) reviews closed.

*Exit: no reviewed-but-unmerged PR older than a week; production runs the merged main; staging rows in status are ticked.*

**Gate 1 — the money path (the only code work that outranks this plan)**

8. 0429 payments UX: close the pending CI browser row, merge the line (#553 rails and #554 fix are already merged).
9. 0435-0436 card and QR rails; 0430-0434 property pages; 0437-0442 Stripe Connect v2 port and fixes: review, merge, deploy each on green.
10. End-to-end money check in production: a host signs up, connects Stripe, a guest pays, an invoice exists, billing records it. 0448 (first plan to legacy hosts) is already merged and live.
11. OPS-2: after the next age-encrypted backup lands, purge the legacy plaintext backups from Lightsail/S3 per the backup runbook.

*Exit: a host can be paid end-to-end without hand-holding; the backup layers are all encrypted.*

**Gate 2 — parked decisions (cheap to make; each unblocks a row elsewhere)**

12. Founder-price flag on the customer page vs discount-% only (status Blocked row).
13. Lawyer round: legal v1.7 signature, TDM §11 confirmation (0195), the Terms/DPA line from the file-retention plan, and the K-L rows.
14. HIGH RISK filing rows K-F02/K-F03/K-F07, stale signed dates K-F18, secret rotation K-S10: schedule each or explicitly park it with a date.
15. Support mailbox vendor choice (vendors.md open row).

*Exit: every status Blocked row is either closed or has an owner and a date.*

**Gate 3 — this plan, Phase 1 (starts only when Gates 0-1 are closed; Gate 2 can run in parallel)**

16. First: metric definitions (§5a) reconciled and brief 0444 (small read-only extraction of current portfolio values and invoice issue/paid aggregates) built and merged — no scheduler registration, no new dependencies, no migrations, no containers.
16b. Then, only if the §5 preconditions hold: brief for the `analytics_sync` scheduled job + `postgres-analytics` + Metabase compose services (§5), following the task system.
17. Build, review, merge on green; deploy with the `analytics` profile; wire the heartbeat (existing healthchecks.io pattern).
18. First dashboards and alerts (§5); tune against the cockpit plan §12.

*Exit: MRR, plan mix, churn watchlist and overdue-invoice alerts exist outside the morning checklist.*

**Gate 4 — the UX plan**

19. PR #581 review and merge, then its workstreams W1-W5 per its own sequencing — after the money path, in parallel with Gate 3.

*Exit: UX plan merged; its briefs enter the normal task queue.*

**Gate 5 — dormant**

20. The Postgres playbook (§4-§6): read once at each monthly check; execute only when a trigger fires. Until then: nothing.

## 9. Costs

| Item | Monthly |
|---|---|
| Everything existing (Lightsail 8 GB, S3, PostHog, Grafana, SES…) | unchanged |
| Analytics Postgres container + Metabase on the existing instance | $0 subscription (target; RAM/CPU/disk headroom and ops time are real costs, measured per §5) |
| **Total new subscription** | **$0 (target, not a guarantee)** |

## 10. Decisions needed from the owner

- **D1 — Production database stays SQLite.** The migration is deferred to §4 triggers; this document is the written record of that decision and the playbook the next executive CTO executes.
- **D2 — no additional hosting subscription is the target** (confirmed). It is not a zero-cost or zero-risk guarantee: headroom, ops time and recovery work are real and measured per §5.
- **D3 — Metabase OSS self-hosted is the preferred candidate, conditional on the §5 preconditions**, pointing at the analytics copy. Looker Studio remains a co-equal alternative against the same copy.
- Lines in `docs/context/decisions.md` when the phase-1 PR lands.

## 11. Non-goals

No production database change now, no managed database, no BigQuery, no warehouse, no per-seat BI, no Supabase, no Neon in production, no change to the backup layers, no change to PostHog or Grafana scopes, no change to guest pages. The read-only extraction (0444) ships without scheduler registration, new drivers, schema migrations, containers, Metabase deployment, secrets or production queries, and makes no historical movement/churn claims.

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
