# 0455 review — PostgreSQL runtime and verified SQLite transfer

Status: **review gate closed locally; PR open for owner review. Not merged, not
deployed, no production access.** Supersedes the blocked review-only report on
`feat/0455-postgresql-runtime-review` (PR #588). 0456 stays blocked; ops half: 0461.

## Branch

`feat/0455-postgresql-runtime`, based on `main` `31f8468e` (the merged #587,
which carries the reviewed 0452 dependency); local commits only.

## Environment (exact)

macOS arm64, Python 3.12.14, psycopg 3.3.6. PostgreSQL **18.6** built from the
official source tarball
`ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2` (SHA-256
`555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f`),
`server_version_num=180006`, `initdb --no-locale` (collation `C`), disposable
disposable cluster on `127.0.0.1:55432` + Unix socket. Docker absent; pgBackRest 2.60.0 source not buildable here (no
pkg-config/OpenSSL/lz4 dev libs), so no restore/PITR rehearsal is claimed.

## Exact allowlist (diff vs `7e5994f0`)

25 files, **+3773/−93**. New: `db_postgres.py` (+842), `sqlite_to_postgres.py`
(+372), `pg_schema.py` (+156), `tests/test_db_postgres.py` (+1563). Changed:
`db.py` (+473/−33), `config.py` (+167/−1), `reencrypt.py` (+75/−21),
`tests/conftest.py` (+8/−1), requirements (+73), and 14 small caller ports
(integrity mapping, NOCASE username equality, null-safe equality,
`date()`/`instr()`/`PRAGMA`, month range) in `alerts, auth, billing_analytics,
dsr, guest_slug, housebook, main, passport_photos, reporting, retention,
stay_fee_auto, stripe_connect, routes/{exports,invoices,stay_fees}`.

Dropped from the unreviewed draft: the whole `invoices.py` hunk (+940/−803), a
wrong-target copy of `routes/invoices.py` that deleted the invoice builder.
`invoices.py` is byte-identical to HEAD; the builder needs no port.

## PR #588 findings — resolution

- **F1 critical hunk** — dropped; builder unchanged, imports pass. Closed.
- **F2 no persisted tests** — closed: 45 PostgreSQL 18.6 + SQLite regression
  tests (schema, lexer, readonly, integrity, encryption, writers, transfer and
  failure paths, config contract).
- **F3 stay-fees catch** — ported to `db.integrity_errors()`; whole app
  classified: no remaining SQLite catch/`PRAGMA`/`lastrowid` in app paths.
- **F4a** — both CLIs bootstrap `sys.path`; run without `PYTHONPATH`.
- **F4b socket URLs** — TCP unchanged; libpq Unix-socket URLs accepted and
  connect; relative host, hostname+`host`, missing DB, fragments,
  duplicate/contradictory ports rejected; socket dir is in the target
  fingerprint, credentials never; errors never echo the DSN.
- **F5** — verified on real 18.6, not 16.x. **F6** — 0456 remains blocked by
  design (see gaps).

## Extra fixes found in Lead review

Audit addendum: PostgreSQL has no `instr()` or two-argument `date(t, mod)`;
invoice search and monthly analytics ported (`strpos`, Python month boundary,
`db.sqlite_date_expr` for `date(col)` NULL semantics), SQLite unchanged.
Privacy: transfer constraint failures printed psycopg `DETAIL: Key (email)=(…)`;
now operation + table + SQLSTATE only. Lock timeout: 55P03 during `BEGIN` left
an open transaction and was masked; now rolls back and re-raises
`LockNotAvailable`, connection reusable. Draft `Sequence` import fixed.

## Recorded commands (from `App/`)

| Command | Result |
|---|---|
| `pytest tests/test_migrations.py tests/test_db_*.py -q --tb=short -x` | exit 0, **20 passed, 45 skipped** (PG module under SQLite row) |
| `UBYHOST_DATABASE_URL=… ubyhost_test_lead pytest tests/test_db_postgres.py -q --tb=short -x` (fresh DB, twice) | exit 0, **45 passed, 0 failed, 0 skipped** (7.14 s / 7.43 s) |
| `pytest tests/test_guest_*.py tests/test_billing_*.py -q --tb=short` | exit 0, **684 passed, 5 skipped** (browser/AI without Playwright, unchanged) |
| `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` | exit 0 |
| `pg_schema.py apply --expect-database ubyhost_test_lead` | exit 0, version **33**, **67** tables, **6** invoice triggers |
| `sqlite_to_postgres.py --source … --report … --expect-database …` then `--verify-only` | exit 0, `copied-and-verified tables=67`, `verify-only OK` |

Also independently checked on 18.6: read-only repeatable-read export refuses
writes; literal `?`/`%` values round-trip; duplicate username raises
`UniqueViolation` caught by `db.integrity_errors()`; 8 concurrent writers
serialise; sequence continues above imported IDs (101 → 102; empty → 1); a
tampered target value is detected with matching row counts; report JSON holds no
raw values; config rejects malformed URLs without echoing credentials.

## Remaining gaps / owner-only steps

1. **0456 operations kit unrehearsed** (no Docker, no buildable pgBackRest):
   encrypted restore/PITR, cutover failure ordering and runbook unverified. It
   needs the Caddy maintenance mode, restricted DB role, restore/rehearsal
   layout, transfer retry path, runbook/tests, `100755` modes. Phase 2/3
   packaging is blocked on it.
2. **No CI PostgreSQL job**: the 45 PG tests skip in CI unless a disposable
   server is provided; recorded 18.6 run is local evidence.
3. **Cluster locale is part of the contract**: recorded cluster is `C`, matching
   SQLite ASCII-only `lower()`/`LIKE`; other locales widen `ILIKE` for
   non-ASCII text. The operations kit must pin the locale.
4. `SUM(integer)` returns `numeric`/`Decimal` on PG; call sites render/coerce,
   not changed — behavioural difference to watch.
5. **Restricted runtime role not exercised** (superuser in tests); separate
   migration/backup/runtime roles are a 0456 requirement.
6. Schema DDL renderer is strict by design: future migrations with new
   SQLite-only syntax fail closed for review. Socket URLs validate only
   `host`/`port`; other libpq parameters are outside the fingerprint.

## Confirmations

No merge, deploy, production access or query, secrets, or `main` push.
Owner merges and performs the cutover after 0456 is rehearsed.
