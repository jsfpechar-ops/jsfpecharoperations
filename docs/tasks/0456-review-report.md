# 0456 review — PostgreSQL operations/cutover kit (APPLIED, NOT REHEARSED)

Status: **applied in the combined PR branch `feat/postgresql-runtime-and-cutover-kit`,
for engineer review. Not merged, not deployed, no production access.** The
encrypted pgBackRest restore/PITR and the cutover state machine have **not** been
rehearsed: Docker and a buildable pgBackRest are absent on the preparation host.
No rehearsal is claimed.

## Base / contents

Based on `main` `31f8468e` (with 0455 runtime, tests and the 23-file operations
kit applied on top). The kit was applied from
`docs/plans/postgresql/ubyhost-handoff/handoff/UNREVIEWED-postgresql-operations.patch`
(23 files, +1269/−42), then fixed. Work is local commits only.

## What changed after applying the draft

Mechanical (Lead): executable modes on every new script; `abort-to-sqlite` now
removes `UBYHOST_DATABASE_URL` instead of writing an empty value (which 0455
rejects); restore target moved to `/restore/18/docker` to match the rehearsal
`PGDATA`, with a `PG_VERSION` + `pg_controldata` check.

Operations fixes (9 commits):

- **B1 maintenance mode** now works: both Caddy templates serve a visible 503
  while `UBYHOST_MAINTENANCE=1`; the 0421 not-Cloudflare `abort` guard is
  untouched and still first in Caddy's fixed directive order. `maintenance_on`
  force-recreates caddy, validates the mounted file in-container, proves the
  running container carries the flag, and `prepare` reverts the page if the
  proof fails. Validated with Caddy v2.11.7 locally; no Docker stack test.
- **B3 transfer retry**: new `transfer-retry` verb; only from
  `transfer_in_progress`, proves the target schema is still empty via psql,
  refuses a populated target (points at `transfer-recovery-verify`), otherwise
  retries with a fresh stamp/artifact.
- **H3/H4**: Litestream is stopped and verified gone during `stop-writers`,
  recorded, and restarted on abort only if this cutover stopped it; mutating
  verbs take an exclusive `flock`; state dir defaults to
  `$PG_OPS_ROOT/.postgres-cutover-state` (gitignored, env-overridable).
- **H5/H7**: restore requires only restore credentials (no age
  recipient/forward-backup env); the rehearsal container is internal-network
  only and cannot reach the production DB/S3.
- **H6/H1/H2/H8**: `prepare` runs preflight; `start-postgres` is rerun-safe
  (skips an existing stanza); abort restores SQLite cron rows; key backup fails
  closed unless it proves key material before upload/prune; marker/Compose
  guards distinguish "absent" from "cannot inspect"; the snapshot makes one
  write-capable retry only after a read-only WAL failure, removing partial files.
- **B5**: all required PG variables added to `deploy/lightsail/.env.example`
  (names/placeholders only) and a 484-line numbered owner runbook
  `docs/plans/postgresql/owner-cutover-runbook.md`.
- **B6**: least-privilege role proposal (`postgres/roles.sql` +
  `scripts/postgres-create-roles.sh`): app DML role, migration/DDL owner, backup
  grants commented for the DBA; passwords via files/`\getenv`; does not force the app DSN.

## Static evidence (this host, no Docker)

| Check | Result |
|---|---|
| `bash -n` all touched/new scripts | 29/29 deploy scripts + new App helper exit 0 |
| `shellcheck -S error` (CI scope) | exit 0 |
| `py_compile` new Python helpers | exit 0 |
| Caddy validate, both templates, maintenance 0 and 1 | exit 0; matcher adapts to `0 == 1`/`1 == 1`; 503/200 behaviour tested on a scratch port |
| `yaml.safe_load` both compose files | parses; rehearsal has no egress network; postgres has no published ports |
| synthetic key-bundle + snapshot-copy checks | pass (no secrets) |
| secret scan of the diff | only variable names/placeholders, no values |
| new `App/tests/test_postgres_operations_scripts.py` | static safety suite (modes, syntax, maintenance, transfer retry, restore layout, compose isolation, env example, runbook, py_compile, secret scan, role proposal) |

## NOT verified — engineer passes required

Docker image build; encrypted pgBackRest full/diff → restore to a fresh volume →
PITR; read-only rehearsal start + 0455 `sqlite_to_postgres --verify-only`
reconciliation; the full cutover state machine and every abort/retry path;
visible maintenance page through Cloudflare; off-host S3/rclone key bundles and
retention; disaster restore; restricted-role grants actually applied.

## Remaining file:line decisions (from the ops review)

- `scripts/postgres-cutover.sh` Litestream discovery keys on the Compose project
  label `ubyhost`; confirm the project name after any compose rename.
- `App/scripts/create_postgres_cutover_snapshot.py` (H8): the fallback opens the
  SQLite source write-capable once so SQLite can recover a hot WAL (no app rows
  written). Accept the documented `.backup` behaviour or require a clean
  shutdown before cutover — owner decision.
- `scripts/postgres-backup.sh` runs `pgbackrest check`, not a full `verify`; a
  real repository check should add `verify` (slow) to the daily job or the
  rehearsal.
- The restore→read-only-start→reconcile flow is manual (runbook §8); no scripted
  rehearsal because Docker is unavailable here.
- `postgres/pgbackrest.conf` assumes path-style S3; confirm the bucket's
  addressing style or choose a new bucket (owner decision).
- `postgres/roles.sql` backup-role grants and switching the app DSN to
  `ubyhost_app` are NOT applied; 0455 `pg_schema.py` uses one DSN, so
  migration-vs-app role separation needs an engineer decision (runbook §9).
- Maintenance proof is "running caddy carries the flag + config validates"; the
  actual page through Cloudflare is an owner browser step (runbook §3).

## Confirmations

No merge, deploy, production access, secrets or `main` push. SQLite remains the
default; PostgreSQL becomes active only with an explicit `UBYHOST_DATABASE_URL`
and an explicit, rehearsed owner cutover.
