# 0455 review — PostgreSQL runtime draft (BLOCKED, do not merge)

Status: blocked. The 0455 review gate is not closed. The draft patch applies
mechanically but is **not fit to apply**: it corrupts the invoice builder, ships
no tests, and leaves one SQLite-only caller unported. Recorded base
`8b5317d0`; this branch is stacked on the open #587 branch (`7e5994f0`), which
carries the reviewed 0452 dependency.

Reviewer environment: macOS arm64, Python 3.12, psycopg 3.3.6, embedded
PostgreSQL **16.2** (pgserver); no Docker, pgBackRest or PostgreSQL 18 binaries.

## Draft inventory

| Patch | Files | Lines |
|---|---|---|
| `handoff/UNREVIEWED-postgresql-runtime.patch` | 19 | +2940 / −878 |
| `handoff/UNREVIEWED-postgresql-operations.patch` | 23 | +1269 / −42 |

Both still pass `git apply --check`; that is not evidence of correctness.

## Blocking findings

### F1 (critical) — wrong-target hunk destroys `App/app/invoices.py`

The runtime patch's `App/app/invoices.py` hunk replaces the 846-line invoice
builder with a byte-identical copy of `App/app/routes/invoices.py`:

```
$ diff -q App/app/invoices.py <(git show HEAD:App/app/routes/invoices.py)
# after applying the draft: IDENTICAL
```

Applying the draft therefore deletes the builder and duplicates the router.
Import fails immediately:

```
ImportError: attempted relative import beyond top-level package
  File ".../App/app/invoices.py", line 14
```

Reverting only that file restores imports and the SQLite DB row (20 passed), so
the remaining hunks are mechanically usable — but the patch as shipped cannot
be applied. The builder's own PG portability was never reviewed (`invoices.py`
contains no `PRAGMA`/`sqlite3` calls today, so this is a target error, not a
required rewrite).

### F2 — no persisted PostgreSQL coverage (0455 acceptance)

Neither draft adds a test. `grep -E '^\+\+\+ b/.*tests'` finds nothing. The brief
requires persisted PostgreSQL integration tests **and** SQLite regression
checks; the reported experiments in the handoff are not that evidence.

### F3 — unported SQLite-only caller

`App/app/routes/stay_fees.py:805` still catches `sqlite3.IntegrityError`; on
PostgreSQL the driver raises a different exception, so this caller silently
loses its conflict handling. `admin_helpers.py` only mentions `sqlite3.Row` in a
docstring. 0455 §3 requires every direct caller/exception catch to be reviewed.

### F4 — tooling gaps

- `python scripts/pg_schema.py ...` fails with `ModuleNotFoundError: No module
  named 'app'` unless the caller sets `PYTHONPATH` (the export script bootstraps
  its own path; this one does not).
- `config.py` rejects socket-style PostgreSQL URLs
  (`postgresql:///db?host=/tmp/...`), which is how disposable/embedded servers
  connect. Production hostname URLs are unaffected, but the local test fixture
  contract needs an owner decision before tests can be persisted.

### F5 — PostgreSQL version target not verified

The smoke below ran on 16.2. The handoff's reported experiments were on 18.6;
the brief's real-server requirement therefore remains open until the 18.6 matrix
runs. No CI job installs PostgreSQL.

### F6 — operations (0456) only statically reviewed

Applied to a throwaway worktree: all 23 files apply, every shell script passes
`bash -n`, both new Python scripts pass `py_compile`. `shellcheck` is not
installed here and **no encrypted restore/PITR rehearsal, Docker build, cutover
failure test or runbook execution was possible**. 0456 stays blocked until 0455
interfaces are settled and this kit is rehearsed.

## What did work (evidence for the continuation)

After dropping only the F1 hunk, against embedded PostgreSQL 16.2:

```
pg schema version: 33
pg select: 1
pg placeholder literal: a?b          # '?' inside a string is not rewritten
pg readonly rows: 0                  # readability transaction (repeatable read, read only)
duplicate insert: integrity_errors caught
transfer OK: copied-and-verified tables= 67
verify OK: verify-only               # sqlite_to_postgres.py on a 67-table synthetic snapshot
```

SQLite regression with the remaining hunks:

```
pytest tests/test_migrations.py tests/test_db_*.py -q  → 20 passed
pytest tests/test_guest_*.py tests/test_billing_*.py -q → 684 passed, 5 skipped
```

(The 5 skips are browser/AI tests without Playwright in this review venv.)

## Required before 0455 can leave `blocked`

1. Regenerate the patch from current `main` (`1f31d41a`): drop the bogus
   `App/app/invoices.py` hunk, diff the builder explicitly, and port
   `routes/stay_fees.py`.
2. Write persisted tests: schema apply/validate, placeholder lexer, readonly
   transaction, integrity mapping, encrypted round-trip, writer serialisation,
   and a SQLite→PG transfer + verify-only reconciliation. SQLite rows must stay
   green.
3. Verify on disposable PostgreSQL 18.6 (the handoff target) and record the
   exact image/tool versions; decide the socket-URL fixture contract.
4. Then 0456: rehearse pgBackRest encrypted restore/PITR and failure ordering in
   Docker before the kit can be called ready.
5. After 0455/0456: final complete-file bundle, manifest, placement script and
   fresh combined patch; owner cutover remains manual.

No production access, secrets, merge or deployment was used in this review.
