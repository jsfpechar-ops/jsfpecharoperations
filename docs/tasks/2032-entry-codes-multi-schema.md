# 2032: Goose 00023 — `apartment_entry_code` table (up to 3 extra codes), retention, export guard

Status: review
Depends on: 1661, 1662 | Base commit: fill from `git rev-parse --short HEAD` | Branch: task/2032-entry-codes-multi-schema
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (migration + retention of a secret): brief reviewed as exact diff

## 1. Objective

Owner decisions 2026-11-22 (D1, D2): an apartment has up to 3 extra entry codes besides the TTLock door code, each with a type (`building_entrance`, `gate`, `garage`, `bike_room`, `other`; `other` needs a custom label). Add table `apartment_entry_code` with one additive goose file, copy any existing `apartment.entry_code_*` value into position 1, keep the old columns (dropped by a later brief), extend retention step `entry_codes` (Go + Python twin + golden) to the new table, and extend the export guard. No reader or writer yet (1665-1667).

## 2. Context (verified on main)

- Highest goose file: `App/migrations_pg/00022_apartment_entry_code_guide_url.sql`, so the new file is `00023`. Header style of 00022: `-- +goose Up`, comment lines, `IF NOT EXISTS`, then `-- +goose Down`.
- Goose-only tables are already accepted: `go/internal/schema/expected.go:86-117` (`Compare`) only counts an actual table missing from `e.Tables` as `ExtraTables`, and `go/internal/schema/expected_test.go:56` pins `s.Current` true with `ExtraTables == 1`; Python's `db.postgres_schema_status` loops only over `expected.keys()` and reports `extra_tables` separately (`App/app/db.py:1396`, `:1437`). Goose-only tables exist already (`00020_guest_contract.sql:12` `guest_form_snapshot`, `00021_ruian_address.sql:29`). Only goose-only `ADD COLUMN` needed brief 1660. **No schema-check change is needed**; step 5 proves it.
- Retention today, `go/internal/retention/steps.go:417-435` `stepEntryCodes`: `cutoff := r.daysAgoISO(1)`; `where := entry_code_enc IS NOT NULL AND ((COALESCE(entry_code_until,'') <> '' AND entry_code_until < $1) OR (COALESCE(archived_at,'') <> '' AND archived_at < $1))`; counts with `r.scalar`, returns early on `r.dry || n == 0`, then `r.exec(... UPDATE apartment SET entry_code_enc = NULL ...)`. It returns 0 when `r.owner != nil`. Registered at `go/internal/retention/retention.go:150`, label at `:280`. Python twin `App/app/retention.py:515-534` `_entry_code_step` (same shape, `?` params, `_scalar`, `db.execute`), registered `:579`, label `:611`. Golden: `App/scripts/retention_golden.py` (PostgreSQL only; the table snapshot dict has `"apartment_entry_code"` at `:89-90`, selecting `entry_code_enc` from `apartment`). Python test: `App/tests/test_retention_entry_code.py` (SQLite; `_ensure_entry_code_columns()` adds the goose-only columns by hand because SQLite has no twin; the new test creates the new table the same way).
- Export guard: `go/internal/web/exports/entry_code_guard_test.go` fails when a non-test `.go` file in that package contains the text `entry_code` or `SELECT * FROM apartment`. Table name `apartment_entry_code` contains `entry_code`, so the guard already covers it; the test only needs an explicit second assertion (step 6).
- Stored codes are secrets: Fernet ciphertext (`go/internal/secure`), never plaintext, never logged. Retention rule: erase 1 day after `valid_until` or 1 day after the apartment is archived; no end date = until the host clears it (plan "Stored copy").

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00023_apartment_entry_code.sql` | new | step 1 |
| `go/internal/schema/expected_schema.json` and files under `go/internal/schema/testdata/` the script rewrites | regenerated | `App/scripts/pg_schema_golden.py` |
| `go/internal/retention/steps.go` | edit | `stepEntryCodes` also covers the new table |
| `go/internal/retention/retention.go` | edit | none unless the label at `:280` needs the same words (leave it) |
| `go/internal/retention/steps_entry_codes_test.go` | new | DB test of step 3 (pattern: other DB tests in that package; skips without `UBYHOST_TEST_DATABASE_URL`) |
| `App/app/retention.py` | edit | `_entry_code_step` twin |
| `App/scripts/retention_golden.py` | edit | add the new table to the snapshot dict (`:89`) |
| `go/internal/retention/testdata/` golden file the script rewrites | regenerated | the script |
| `App/tests/test_retention_entry_code.py` | edit | cases for the new table |
| `go/internal/web/exports/entry_code_guard_test.go` | edit | step 6 |
| `docs/privacy/RETENTION.md` | edit | one line for the new table |

No other file may change. `apartment.entry_code_*` columns stay.

## 4. Steps

1. New `App/migrations_pg/00023_apartment_entry_code.sql`:

```sql
-- +goose Up
-- Up to three extra entry codes per apartment (brief 2032, owner decisions 2026-11-22 D1, D2).
-- Goose-only table: no SQLite twin, no schema_migrations row. Additive. code_enc is Fernet ciphertext, never plaintext.
CREATE TABLE IF NOT EXISTS apartment_entry_code (
    id BIGSERIAL PRIMARY KEY,
    apartment_id BIGINT NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 3),
    code_type TEXT NOT NULL CHECK (code_type IN ('building_entrance', 'gate', 'garage', 'bike_room', 'other')),
    custom_label TEXT,
    code_enc TEXT NOT NULL,
    valid_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT apartment_entry_code_position_key UNIQUE (apartment_id, position),
    CONSTRAINT apartment_entry_code_other_label CHECK (code_type <> 'other' OR COALESCE(BTRIM(custom_label), '') <> ''),
    CONSTRAINT apartment_entry_code_label_len CHECK (custom_label IS NULL OR char_length(custom_label) <= 60)
);

INSERT INTO apartment_entry_code (apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
SELECT id,
       1,
       CASE WHEN COALESCE(BTRIM(entry_code_label), '') IN ('', 'Building entrance') THEN 'building_entrance' ELSE 'other' END,
       CASE WHEN COALESCE(BTRIM(entry_code_label), '') IN ('', 'Building entrance') THEN NULL ELSE LEFT(BTRIM(entry_code_label), 60) END,
       entry_code_enc,
       NULLIF(entry_code_until, ''),
       to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
       to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
FROM apartment
WHERE entry_code_enc IS NOT NULL
ON CONFLICT (apartment_id, position) DO NOTHING;

-- +goose Down
DROP TABLE IF EXISTS apartment_entry_code;
```

   Before writing, check the timestamp format other goose files and Python write: `grep -n "to_char\|utcnow" App/migrations_pg/0002*.sql App/app/db.py | head -5`. If the stored format is not `YYYY-MM-DDTHH:MM:SSZ`, copy the format in use. Do not use a `DO`/`$$` block (goose needs `-- +goose StatementBegin` for those).
2. From `App/` run `.venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -10` (no database needed). Only `go/internal/schema/expected_schema.json` and its testdata may change; if not, STOP.
3. Go retention. In `stepEntryCodes` (`steps.go:421`) keep the existing `apartment` code, and add after it a second statement pair for the new table. Counts add up, one return value:

```go
	newWhere := `apartment_id IN (SELECT a.id FROM apartment a WHERE COALESCE(a.archived_at, '') <> '' AND a.archived_at < $1)
		OR (COALESCE(valid_until, '') <> '' AND valid_until < $1)`
	m, err := r.scalar(ctx, `SELECT COUNT(*) FROM apartment_entry_code WHERE `+newWhere, cutoff)
	if err != nil {
		return n, err
	}
	if !r.dry && m > 0 {
		if _, err := r.exec(ctx, `DELETE FROM apartment_entry_code WHERE `+newWhere, cutoff); err != nil {
			return n + m, err
		}
	}
	return n + m, nil
```

   Restructure the early return so the old block's `if err != nil || r.dry || n == 0 { return n, err }` no longer returns before the new table is handled (run the new part in every case; skip only the writes when `r.dry`). Rows are deleted, not nulled (`code_enc` is NOT NULL). Never log a value; no new log line.
4. Python twin in `App/app/retention.py:515` `_entry_code_step`: same logic with `?` params (`cutoff, cutoff` for the subquery and the date) and `DELETE FROM apartment_entry_code WHERE ...`; add the count to `count`. Python's SQLite has no such table in production, but the step runs against PostgreSQL in production and the golden; for SQLite tests guard with `db.table_exists("apartment_entry_code")` if such a helper exists (`grep -n "def table_exists\|def has_table" App/app/db.py | head -3`); if none exists, wrap the new part in `try/except Exception` that returns the old count only when the error text contains `no such table`. Nothing else is caught.
5. Golden: add `"apartment_entry_code": "SELECT apartment_id::text || '|' || position::text || '|' || code_enc FROM apartment_entry_code ORDER BY id"` next to `retention_golden.py:89`, and seed rows the way the script seeds the `apartment` entry-code rows (read `:60-110` and `grep -n "entry_code" App/scripts/retention_golden.py`): one expired row, one archived-apartment row, one future row, one with no date. Regenerate with `UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg&port=5433' .venv/bin/python scripts/retention_golden.py 2>&1 | tail -10` (command from the script's header; if no PostgreSQL is running at that path: STOP). Also prove the schema check: with the same database migrated, run `cd go && go test ./internal/schema/ 2>&1 | tail -10` and `cd App && .venv/bin/python -m pytest tests/test_db_schema_status.py -q --tb=short -x 2>&1 | tail -10` (use the real name from `ls tests | grep -i schema_status`); both must stay green with the new table present.
6. Export guard: in `entry_code_guard_test.go` add `TestNoExportReadsEntryCodeTable`: same directory walk, fail when any non-test file contains `apartment_entry_code`. (It is already caught by `entry_code`; the explicit test pins the table name.)
7. Tests. Go (`steps_entry_codes_test.go`): rows for an expired date, an archived apartment, a future date, no date → only the first two are deleted; dry run deletes nothing and returns the same count; `r.owner != nil` returns 0; the unique key refuses a second row at the same position; the CHECK refuses `other` with an empty label and a 4th position. Python: extend `test_retention_entry_code.py` with the same four cases against a hand-created SQLite table (copy `_ensure_entry_code_columns`).
8. `docs/privacy/RETENTION.md`: one line next to the entry-code line (`grep -n "entry_code\|Entry code\|entry code" docs/privacy/RETENTION.md | head -3`): "Extra entry codes (`apartment_entry_code`): encrypted; deleted 1 day after valid-until or after the apartment is archived; with no end date until the host clears them." If no entry-code line exists, add it to the table in the same style.
9. Run §6, commit per step.

## 4b. Guest order helper (owner D5)

Add `entryCodeGuestOrder(rows, hasLock)` next to the table's Go access code: returns rows plus a door-code slot sorted gate, building_entrance, DOOR, garage, bike_room, other; same type keeps `position` order. Table test with all six kinds, two of one type, and no lock.

## 5. Do not touch

`apartment.entry_code_*` columns (no `DROP`), `App/app/db.py`, `go/internal/schema/*.go` (only the regenerated golden files change), any reader or writer of the codes, Leon, guides, exports other than the guard test.

## 6. Commands

From `App/`: `.venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -10`
From `App/`: `.venv/bin/python -m pytest tests/test_retention_entry_code.py tests/test_retention*.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`
From `go/`: `gofmt -l internal/retention/ internal/web/exports/ 2>&1 | tail -5`; `go vet ./internal/retention/ ./internal/schema/ ./internal/web/exports/ 2>&1 | tail -10`
From `go/`, with `UBYHOST_TEST_DATABASE_URL` set: `go test ./internal/retention/ ./internal/schema/ ./internal/web/exports/ 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] `00023` applies on a fresh and on a migrated database; Down drops the table; the copy puts an existing code at position 1 as `building_entrance`, or `other` plus its label when the label was not the default.
- [ ] Go and Python schema checks stay "current" with the new table (extra table is tolerated).
- [ ] Retention: expired and archived rows deleted, future and no-date rows kept, dry run changes nothing; Go and Python counts equal in the golden.
- [ ] Guard test names the table; no log line, audit value or export carries a code.
- [ ] RETENTION.md has the line.

## 8. Stop and ask

Stop if: 00023 is already taken; the schema golden changes anything but the new table; no PostgreSQL for the golden; the schema check marks the new table as a mismatch (then a goose-only-table rule is missing: write that up, do not patch `db.py`); a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/2032-report.md` (≤600 tokens), `Status: review`, one PR.

## Risk list (for the reviewer)

`00023` copy statement (ciphertext moved, never decrypted), `stepEntryCodes` DELETE predicate (a wrong predicate deletes live codes), the Python SQLite guard.

## Owner steps

1. None: additive table, nothing reads it until 1665-1667. Merge with `scripts/merge-pr-on-green.sh`; the deploy applies the migration.
