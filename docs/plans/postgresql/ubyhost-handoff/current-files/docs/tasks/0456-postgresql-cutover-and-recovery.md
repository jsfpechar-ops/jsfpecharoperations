# 0456: PostgreSQL deployment, cutover and recovery kit

Status: blocked — exact patch review and 0455 interface integration pending
Depends on: 0455 | Base: codex/ubyhost-corrections-20261030
Executor: Haiku 5.5 (latest owner-supplied AGENTS.md)

## 1. Objective

Provide the locally verified configuration, backup/restore, cutover and recovery code needed for an owner-operated SQLite-to-PostgreSQL migration. No production actions are performed by this task. The final delivery is full code in the portable bundle, not a promise to write scripts later.

## 2. Context

Current deployment is deploy/lightsail/docker-compose.yml with web role ubyhost, separate worker, shared data volume, Caddy and optional Litestream. Current backup encrypts DB and secret-key material with age, copies encrypted archives off-host using existing rclone scripts, and applies time-based retention. Secret-key loss makes existing encrypted application data unreadable. Images/files are outside the DB and need their own preservation contract.

Read the Deploy routing row: LIGHTSAIL relevant architecture/deploy/environment sections and OPERATIONS Backup and restore. Inspect the actual deploy/backup/restore/healthcheck scripts and env example before editing. Do not assume service names or stop ordering.

The owner explicitly requests PostgreSQL migration code. Production remains unchanged until the owner performs the rehearsed cutover. The owner approved pgBackRest on 2026-10-30; use a verified pinned release for backup-chain management. The owner also approved pinned psycopg3 after evaluation. Do not add other unapproved dependencies or assume a new paid hosting service. Reuse the existing host architecture unless evidence requires an owner decision.

## 3. Files

Replace with an exact allowlist and full proposed diffs before implementation. Candidate scope: optional PostgreSQL compose overlay and its env example; narrowly scoped deploy/lightsail/scripts PostgreSQL backup/restore/cutover/recovery tools; a new numbered owner runbook; focused shell/integration tests using disposable local data. Do not modify the active SQLite production default, secrets, actual env files, unrelated monitoring config, or existing DB schema implementation owned by 0455.

## 4. Steps

### Deployment contract

- Pin and verify PostgreSQL image/version using official sources; private networking, no public database port. Separate DB volume, health checks and graceful stop. Validate compose configuration locally without exposing interpolated secrets.
- Agree UBYHOST_DATABASE_URL and transfer/reconciliation command names with 0455. Configure web and worker consistently; prevent mixed backends and accidental SQLite fallback when PostgreSQL was requested.
- Use restricted runtime credentials and separate migration/backup capabilities as appropriate; avoid embedding secrets in command lines, output or git. Keep SQLite volume and encryption keys intact.
- Start no migration automatically on normal web startup. No destructive database reset as a recovery shortcut.
- State measured resource and recovery limits. Do not claim the earlier unverified512MB/1GB caps or zero added operational cost.

### Backup and restore contract

- Supply executable PostgreSQL backup and restore code, not merely a pg_dump suggestion. Use compatible pg_dump/pg_restore and retain the existing encrypted/off-host/time-based-retention discipline.
- Preserve encryption keys and non-DB assets. Never print secret settings or include them in public reports.
- A daily dump does not replace continuous SQLite recovery. Implement/rehearse the chosen PostgreSQL WAL/base-backup recovery path using approved tools or identify the exact new-tool decision before implementation. Do not silently downgrade RPO or call an on-host spool an off-host backup.
- Missing encryption recipient in production fails closed. Partial backup never replaces last successful backup. Retention must not remove the last recoverable base/WAL chain.
- Restore to an explicitly isolated empty target by default; refuse accidental overwrite of a running production target. Validate restore by full reconciliation and focused app checks.
- Record actual local restore evidence and explain what off-host/production rehearsal remains an owner operation. No fabricated server timings or RPO/RTO.

### Cutover contract

1. Preflight software, destination identity, credentials without disclosure, storage, backups, schema version, current reconciliation and application version.
2. Enter visible maintenance mode and stop/quiesce web mutations, worker, scheduler and webhook writers. Drain in-flight activity; verify no other app host or job can write. Do not rely on a file flag that independent workers ignore.
3. Produce final consistent SQLite snapshot and encrypted recovery artifact, with successful integrity/foreign-key checks.
4. Invoke0455 transfer into isolated empty PostgreSQL target and require all-table hashes/counts, sequences, filing/receipt and financial aggregate reconciliation.
5. Keep writes disabled while starting/verifying read-only smoke behavior; do not call external police, locks, mail or payment APIs in rehearsal.
6. Require an explicit owner cutover acknowledgement before enabling PostgreSQL writers; record a durable state marker for the point beyond which SQLite rollback is unsafe.
7. Start backend-consistent web/worker, verify health, normal synthetic rehearsal operations, job behavior and backup freshness. Production smoke details stay owner-operated and privacy-safe.

### Recovery contract

- Before any PostgreSQL writes, revert service configuration to the preserved SQLite snapshot only after verifying no destination-authoritative change occurred.
- After PostgreSQL writes, never restart against stale SQLite. Supply executable PostgreSQL restore/forward-recovery steps and reconciliation of external-effect outcomes. Any reverse transfer needs its own full verification and explicit owner decision.
- An ambiguous cutover state fails closed to maintenance; scripts must not guess which database is authoritative.
- Make scripts rerunnable by explicit state transitions; refuse stale checkpoints/target identities. Trap failure and retain maintenance mode instead of auto-resuming mixed writers.

## 5. Do not touch

No production servers, DNS, live databases, actual secrets, paid services, remote publication or deployments. No unapproved new tools. No global pruning, deleting source data, disabling integrity constraints, or logging guest rows.

## 6. Commands

Replace with exact syntax validation, fixture/state-machine tests, local compose validation, backup/restore integration commands and expected results after reading source. Tests must cover each failure transition, rerun/refusal behavior, encryption failure, incomplete restore, pre-write rollback and post-write rollback refusal. Use only disposable synthetic DBs and isolated directories.

## 7. Acceptance

- [ ] Every file contains full executable code and supported prerequisites.
- [ ] Runtime backend/configuration matches0455 and preserves SQLite default.
- [ ] No unsafe overwrite, mixed backend start or post-write stale SQLite fallback.
- [ ] Local transfer, encrypted backup and restore rehearsal succeeds with reconciliation.
- [ ] Failures preserve recoverable data and maintenance state.
- [ ] Owner instructions are numbered, exact, and distinguish preparation from irreversible cutover.
- [ ] No actual production action claimed.

## 8. Stop and ask

Stop only dependent work for missing owner dependency choices, unavailable genuine required tooling after supported setup attempts, unverified source anchors or unsafe target state. Preserve independent work and prepare a concrete continuation at session limits.

## 9. Report

Return exact changed files, full scripts/configuration, interfaces agreed with0455, actual commands/results, local synthetic restore report, recovery-state evidence and numbered owner-only steps. Explicitly separate local verification from production/off-host rehearsal.
