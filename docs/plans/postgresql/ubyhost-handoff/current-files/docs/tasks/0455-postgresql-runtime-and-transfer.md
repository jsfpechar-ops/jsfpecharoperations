# 0455: PostgreSQL runtime compatibility and verified SQLite transfer

Status: blocked — exact patch review required before implementation
Depends on: 0452 | Base: 8b5317d0 plus reviewed 0452 changes | Branch: codex/ubyhost-corrections-20261030
Executor: Haiku 5.5 (latest owner-supplied AGENTS.md)

## 1. Objective

Supply every application and transfer-code change required to run the existing UbyHost application on PostgreSQL, while retaining SQLite as an explicit supported fallback before cutover. The owner expanded scope on 2026-10-30; this supersedes the earlier decision to defer writing migration code, but does not authorize production migration or deployment.

## 2. Context

Current config.py defines UBYHOST_DB as a SQLite path. db.py currently opens SQLite, performs PRAGMAs, owns thread connections, transactions, startup schema/migrations, encrypted row hydration and insert/update helpers. Existing application exception handlers use sqlite3.IntegrityError. Baseline schema and migration SQL include AUTOINCREMENT. These are verified portability concerns, not permission to rewrite unrelated code.

AGENTS database rules: all SQL through db.py helpers, frozen SCHEMA/ADDED_COLUMNS unchanged, schema changes via numbered migrations, no new dependency without owner decision. The owner explicitly approved pinned psycopg3 on 2026-10-30 after reviewing the necessity evaluation. Record the pinned requirement and hashes; no other unapproved dependencies. PostgreSQL itself is explicitly requested. No credentials, real data, server access or remote writes in this task.

Read narrow source ranges first; document a complete targeted portability inventory. Do not audit unrelated application behavior.

## 3. Files

Before implementation, replace this section with an exact allowlist and full diff for the database runtime, schema conversion and transfer path. Candidate ownership: app/db.py; app/config.py; a narrowly scoped app PostgreSQL adapter module; PostgreSQL schema/bootstrap files; scripts for transfer/reconciliation; relevant DB/migration/filing/money tests; approved driver requirement/lock files. Do not modify other agents' guest templates or host work.

Preserve the public db helper contracts. Review all direct connection/cursor callers and SQLite exception catches that affect the backend. Either preserve their behavior through a documented adapter or change the exact callers in the allowlist. No incomplete silent shim.

## 4. Steps

### Runtime contract

- SQLite remains default unless an explicit PostgreSQL configuration is set. Reject contradictory backend configuration and malformed settings without logging DSNs/passwords.
- Keep SQL parameter binding safe. A placeholder converter must distinguish literals, quoted identifiers and comments, including literal question marks/percent signs; no naive global replacement.
- Preserve mapping and integer row access, rowcount, RETURNING, hydration and encrypted write handling. Transfer raw stored bytes/text without calling decryption or re-encryption helpers.
- Preserve transaction nesting, rollback after errors, connection reuse/cleanup, request metrics and cross-process startup locking. Do not treat aborted PostgreSQL transactions as reusable.
- Define equivalent immediate-writer serialization where existing application correctness depends on it; use PostgreSQL locking with bounded timeouts and tests. Do not blindly retry a write after an uncertain outcome.
- PostgreSQL read-only export uses one repeatable-read, read-only transaction; maintain 0452 snapshot/publication contracts.
- Support schema initialization and every current migration under PostgreSQL without mutating the frozen SQLite baseline. Preserve indexes, unique/partial constraints, foreign keys, defaults and checks. Fail on unsupported DDL instead of skipping it.
- Keep SQLite tests passing. Run real PostgreSQL tests in a disposable local database; mocks alone do not establish backend compatibility.

### Transfer contract

1. Require explicit source snapshot, destination connection setting and output report. Secrets come from environment/secret files, never command arguments echoed into reports.
2. Never mutate the source. Use a consistent SQLite snapshot; check integrity and foreign keys, schema version, supported columns and source value compatibility before destination writes.
3. Destination must be an explicitly isolated empty target. Refuse populated/unknown schemas; never silently truncate or drop an existing target.
4. Copy every application table and column, including receipts/blobs, encrypted data, filing states, ownership, payment references, snapshot records and schema history. Preserve nulls, IDs and exact money. Do not omit tables because no immediate feature uses them.
5. Validate all rows and constraints within a controlled transaction. Defer declared deferrable constraints where appropriate; do not disable triggers globally or bypass constraint checks.
6. Restore identity/sequence state above imported IDs, including empty-table semantics. Prove the next normal db.insert succeeds without collision.
7. Reconcile row counts and deterministic typed hashes for every table/column, with canonical null/integer/text/blob handling. Report only table names, counts, hashes and aggregate mismatch categories—no guest data, secrets or raw rows.
8. Reconcile filing-state counts, accepted receipts, billed/paid-marker totals, invoice corrections and account counts separately. Money reconciliation stays exact and does not claim paid markers equal cash.
9. Failure rolls back the target transaction and preserves the source and prior successful report. Successful retry must not duplicate data; refuse mismatched pre-existing runs.
10. Support verification-only mode against an already populated rehearsal/cutover target. A verified copy is not permission to start production writers.

## 5. Do not touch

No production data, credentials, live services, frozen SQLite baseline definitions, or unrelated guest/host changes. The driver is approved; no other unapproved dependencies.

## 6. Commands

- SQLite regression and actual PostgreSQL helper contracts, including bound punctuation, injection-shaped input, row indexing/hydration, RETURNING, uniqueness/error handling, transaction rollback/nesting and contention.
- Full current-schema bootstrap and migrations, not a toy table only.
- All-table synthetic transfer with nulls, Unicode, binary values, encrypted sentinels, foreign keys, unique and partial constraints, historical schema rows and sequence checks.
- Nonempty destination, inconsistent source, source-schema drift, constraint violation and interrupted transfer fail safely.
- Reconciliation detects a modified value even with matching row counts, missing/extra rows and sequences out of range.
- Focused UbyPort filing claim/acceptance/receipt and invoice/payment invariants on PostgreSQL. No actual external calls.
- Export tests on both backends; read-only enforcement and repeatable snapshot under a concurrent committed write.
- No secret or guest fixture value in logs/reports; no production network destinations.

Replace this list with exact test-map files/commands and expected results once source/fixtures are verified. Zero skipped required integration tests; unavailable PostgreSQL tooling requires local setup using approved dependencies rather than a mocked pass.

## 7. Acceptance

- [ ] Real PostgreSQL runtime and complete transfer tests pass.
- [ ] All-table reconciliation and sequence checks pass.
- [ ] SQLite regression checks pass.
- [ ] No secret or guest data appears in reports.

### Operational handoff dependency

Task0456 owns deployment overlay, encrypted backups/restoration, cutover/recovery scripts and owner instructions. Agree backend env names, driver installation, migration CLI and schema contract with its executor before finalizing either. Existing encryption keys and non-DB files remain required. Source rollback is allowed only before destination writes; post-write recovery must restore PostgreSQL or explicitly reconcile changes/external side effects.

## 8. Stop and ask

Stop dependent changes for missing driver approval, unverified source anchors, unsupported schema/data, or destination safety checks. Preserve independent progress and return a concrete continuation for session limits.

## 9. Report

Return full exact code and diff, current baseline, actual commands/results, synthetic reconciliation report, recovered-backup evidence, and remaining owner-only production steps. Do not claim production readiness merely from successful connection or row counts. All application changes remain local until the owner reviews the package.
