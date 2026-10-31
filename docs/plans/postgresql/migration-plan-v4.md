# UbyHost migration plan v4: SQLite → PostgreSQL → Go

Status: active. Owner: Josef. Written 2026-10-31 from plan v3.0 checked against `main` (ab0f25b) and PR #592 (`feat/postgresql-runtime-and-cutover-kit`, 59 files, +6764).
Supersedes v3.0 (owner's draft, not in the repo). Decisions are in [decisions](../../context/decisions.md) under 2026-10-31.

Owner decisions on 2026-10-31: migrate to PostgreSQL now; the Go port is in scope now, not deferred; nothing waits for a load test. Police filing is officially confirmed by the police, so the `ws_uby_test` run is dropped. Police deadline is 3 working days skipping weekends only.

## 1. What v3.0 got wrong (checked against the code)

| v3.0 claim | Code says | Effect on the plan |
|---|---|---|
| Caddy arrives with the Go route-flip | `caddy` is already a service in `deploy/lightsail/docker-compose.yml` with two Caddyfiles; #592 adds a maintenance mode to both | Route-flip is a Caddyfile edit, not new infrastructure |
| Holiday list hardcoded, unchecked 2027+ | `App/app/deadlines.py` computes holidays per year (Easter included), no fixed list | No 2027 bug. Owner still drops holidays (decision), which only shortens deadlines: safe side |
| Tenancy: "64 raw lookups, 10 owner-clause, NULL-owner rows match `IS NULL`" | No `owner_id` tenancy column. Hosts are scoped by `host_id`/`user_id` and a signed cookie of owned guest ids (`routes/guest.py:_owned_ids`). Routes contain ~63 bare `WHERE id = ?` reads, most in admin pages (`admin.py` 15, `admin_accounts.py` 16) that are platform-admin only | Risk is real but unmeasured. First step is a scoped audit (step 3), not a blind rewrite |
| `BEGIN IMMEDIATE` becomes a global advisory lock | True: `db_postgres.py:716` takes `pg_advisory_xact_lock(WRITER_LOCK_ID)` on every write transaction | Keeps SQLite semantics, also keeps the single-writer ceiling. Removing it is a Go-phase task, not a cutover task |
| 15 jobs | Correct: 10 interval + 5 cron in `scheduler.py:start`; `door_codes`, `push`, `guide_import` at 1 min (`job_intervals()`) | Interval fix stays (step 1) |
| PDF is a scheduled job | Correct in v3.0 changelog: reportlab inline in requests | G4 ports a request path, not a job |
| Production auto-deploys with no gate | `deploy-production.yml` runs on green CI for `main` and uses the GitHub environment `production` | The gate is a GitHub setting (required reviewer on the environment), zero code. Owner decision |
| 45 PG tests skip in CI | Correct: `ci.yml` has no Postgres service; `test_db_postgres.py` skips without `UBYHOST_DATABASE_URL` | Must be fixed before #592 merges (step 4) |
| `ws_uby_test` run, SOAP golden files before Go | Filing confirmed by the police; golden files only guard a rewrite of the submit path | Dropped from pre-Postgres work; one request-XML snapshot test returns before G5 |
| Lightsail and Render both named as production | Lightsail is production, Render is staging | Wording only |
| cAdvisor/Alloy spam every 5 s | Both services exist in compose; the spam cannot be verified from the repo | Not in this plan; fix when it bothers the owner |
| Load test gates Go | Owner decision: no gate | Load test stays as a measurement in step 13, not a gate |

Steps the v3.0 plan listed that are dropped: `ws_uby_test` run (C1–C2), holiday list extension to 2027+ (R-07), "ADR-001 Postgres yes/no" (decided), "Lightsail plan upsize" (owner does this ad hoc), any "defer until proven" gate.

## 2. PR #592 as it stands

Open, 0 reviews, mergeable. SQLite stays the default; Postgres only with `UBYHOST_DATABASE_URL`. Verified by its author on a local PG 18.6: 45 PG tests, schema apply, transfer and `--verify-only`. Not verified anywhere: the Docker image (postgres 18.6 + pgBackRest 2.60), encrypted backup → restore → PITR, the cutover state machine (`deploy/lightsail/scripts/postgres-cutover.sh`, 491 lines) and the 484-line owner runbook. Open items are listed in `docs/tasks/0456-review-report.md` on the branch.

Judgement: the runtime half (0455) is reviewable and small enough to merge after an independent review. The operations half (0456) is ~1,500 lines of shell nobody has run; it is the main risk of the whole migration and it exists only because Postgres is self-hosted. See open decision D1.

## 3. Ordered steps

Sizes: S = one Haiku chat, M = 2–3 Haiku chats, L = a Fable brief plus several Haiku chats. "Fable" means Fable writes the brief and reviews the report; Haiku implements. Nothing is deferred; order is by dependency and risk.

| # | Step | Why | Size | Model | Depends on |
|---|---|---|---|---|---|
| 1 | Job intervals: `door_codes` 5 min, `guide_import` 60 min, `push` after checking what it sends ([0457](../../tasks/0457-job-intervals.md)) | ~4,300 empty runs/day, hides real errors, costs nothing to fix | S | Haiku | none |
| 2 | Deadline rule: 3 working days, weekends only ([0458](../../tasks/0458-deadline-weekends-only.md)) | Owner decision; shortens deadlines on holiday weeks, never lengthens | S | Haiku | none |
| 3 | Tenancy audit and fix ([0459](../../tasks/0459-tenancy-audit.md), then fix briefs) | Cross-host data read is a legal and reputational risk today, with any database. Must be fixed before any route is ported to Go, or the port copies the bug | L | Fable brief, Haiku | none |
| 4 | Postgres service in CI so `test_db_postgres.py` runs with 0 skipped ([0460](../../tasks/0460-postgres-tests-in-ci.md)) | 45 tests that never run in CI are not tests. Merge gate for #592 | S | Haiku | none |
| 5 | Independent review of #592 runtime half (`db.py`, `db_postgres.py`, `config.py`, `pg_schema.py`, `sqlite_to_postgres.py`) | HIGH RISK database code, 0 reviews so far | M | Fable brief, Haiku fixes | 4 |
| 6 | Decide D1 (managed vs self-hosted Postgres). If managed: strip the pgBackRest/Docker half of #592 to a cutover script plus runbook. If self-hosted: rehearse the full kit on a disposable VM (build image, encrypted backup, restore, PITR, every abort path) | The unrehearsed half is the biggest single risk; a managed database removes most of it | M (managed) / L (self-hosted) | Fable brief, Haiku; owner runs the rehearsal | 5, D1 |
| 7 | Merge #592, deploy with `UBYHOST_DATABASE_URL` unset | Code on main, production still SQLite, zero risk | S | owner | 5, 6 |
| 8 | Cutover on synthetic data on staging (Render or a Lightsail copy), then production in a maintenance window: prepare → stop writers → transfer → verify → authorize → start writers | The irreversible step. The runbook's abort path works only before the first Postgres write | M | Fable brief, owner executes | 7 |
| 9 | Stop Litestream, enable Postgres backups, first restore drill from the real backup; update `restore-drill.yml` | A backup that was never restored is not a backup (R-12) | S | Haiku, owner drill | 8 |
| 10 | Migration authority: adopt goose (or keep the Python runner, decision D3) and freeze the SQLite DDL path | Two migration authorities during the Go port is how schemas drift (R-14) | M | Fable brief, Haiku | 8 |
| 11 | Replace the global advisory writer lock with per-row locking where the code needs it (`submission_claim`, sequences, invoices); `EXPLAIN` every poll query and add the missing indexes in the same brief | The lock keeps the SQLite single-writer ceiling on Postgres; it must go before a second worker or the Go worker exists | M | Fable brief, Haiku | 8, 3 |
| 12 | Scheduler to a durable queue: River (Go) or a Postgres `job` table with `SKIP LOCKED` consumed by the Python worker first, so the Go worker can take jobs one at a time | Removes the `scheduler.lock` single-instance ceiling (R-02) and gives per-job rollback during the Go port (R-18) | L | Fable brief, Haiku | 10, 11 |
| 13 | G1: Go service skeleton behind Caddy, health, metrics, goose, shared crypto conformance fixtures (Fernet/MultiFernet, session cookie, passkey) | Crypto parity is the one thing that cannot be rolled back per feature: a wrong key derivation locks every user out | L | Fable brief, Haiku | 7, 10 |
| 14 | G2: read-only routes (`/privacy`, `/legal`, `/healthz`, `/metrics`, guide pages) route-flipped in the Caddyfile | Safest first flip; rollback is one Caddy line | M | Haiku | 13 |
| 15 | G3: worker jobs one at a time via the queue (ical, mail, photo sweep, retention, billing crons), each with its own feature flag | Per-job rollback; Python keeps the job until Go proves it | L | Fable brief, Haiku | 12, 13 |
| 16 | G4: auth, sessions, host UI, PDF (content acceptance tests, not byte parity) | The bulk of the port. Tenancy fix (3) must be done before this starts | L | Fable brief, Haiku | 3, 14 |
| 17 | G5: UbyPort submit path. Before touching it: a snapshot test of the current request XML (golden file from the mock, no `ws_uby_test` run). Port with batch 32, timeout 60 s, transport retry with idempotency on `submission_claim` | Filing correctness beats every feature (rule 1). Golden file guards the rewrite | L | Fable brief, Haiku | 15, 16 |
| 18 | G6: retire the Python web and worker, remove SQLite code paths, final docs | Done state | M | Haiku | 17 |

Steps 1, 2, 3, 4 start now, in parallel. Steps 11 and 12 can run while G1–G2 are built. Everything not in this table is out: load test, Lightsail resizing, ARES/VAT cleanup, log-noise tuning, Rust or Node.

## 4. Decisions (owner, 2026-10-31: all four taken as recommended)

- **D1 Managed or self-hosted Postgres.** Self-hosted is what #592 builds: postgres 18.6 + pgBackRest in Docker on the same VM, S3 repository, encrypted key bundles, all unrehearsed. Managed (Lightsail database or RDS) gives automatic backups and PITR, removes ~1,500 lines of ops shell, costs about 15 USD/month and runs PG 16/17, not 18. Recommendation: managed. Nothing in #592's runtime half needs PG 18.
- **D2 Deploy gate.** Add a required reviewer to the GitHub `production` environment (one settings click) or keep auto-deploy on green `main`. With cutover and route-flips ahead, recommendation: add the reviewer now.
- **D3 Migration tool for the Go era.** goose on `App/app/migrations/`-equivalent SQL files, or keep the Python runner until G6. Recommendation: goose at step 10, Python runner frozen the same day, so there is one authority.
- **D4 Queue.** River (Go only; Python cannot enqueue natively) or a plain Postgres `job` table with `SKIP LOCKED` that both runtimes use. Recommendation: the table; River can be added at G6 if ever needed.

## 5. Risks kept from v3.0, renumbered

R-03 tenancy (critical, step 3), R-05 police transport retry (G5), R-08 deploy gate (D2), R-12 unrehearsed backups (6, 9), R-14 two migration authorities (10), R-15 PG tests skip (4), R-16 crypto conformance (14), R-18 dual job ownership (12, 16), R-19 one-minute jobs (1), R-21 `ical changed=8` every run (check in step 11; likely the feed hash is not stored). Closed: R-04 (police confirmed), R-07 (holidays computed, then dropped), R-01 (advisory lock reproduces it; handled in 11).

## 6. Load facts (production export 2026-10-31, 37 min, 7 apartments)

| Measured | Value | At 2000 apartments (×286, linear) |
|---|---|---|
| Real page requests | 6 in 37 min; `/metrics` 73 | ~1,700/37 min, still trivial for 4 uvicorn workers |
| `db_ms`, `lock_ms` | 0 on every request; WAL segments 0.2–7.9 KB | Write volume is not the problem on either database |
| `door_codes` sweep | every 60 s, 80–180 ms, all counters 0 | 25–50 s per run if the scan is O(total): the worker would spend most of each minute on nothing. Step 1 (interval) and step 11 (`EXPLAIN`, indexes) fix this |
| `ical` | 8 feeds in 1.8 s at startup; `changed=8` with `created=updated=cancelled=0`, `not_modified=0` | ~2,300 feeds ≈ 9 min per hourly run if sequential. Feed hash/ETag caching does not work (R-21); fix in step 11, concurrency comes with the queue (step 12) |
| `submit` sweep | every 10 min, `apartments=7 submitted=0 failed=0` | Normal: filing happens at guest submit; the sweep is the retry net |
| `push`, `guide_import` | every 60 s, zero work | Pure waste; 0457 |
| cAdvisor | ~7 error lines/min for stale container ids | Noise only; not a plan step |

Conclusion: nothing in the measured load needs Postgres or Go for throughput. The ceilings are the single worker loop (R-02) and query shape, which steps 1, 11 and 12 remove. Postgres is for backups, tenancy and multi-instance; Go is the owner's maintainability choice.
