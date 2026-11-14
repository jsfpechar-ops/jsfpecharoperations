# 1631: Schema, retention and export exclusion for entry code + external guide URL

Status: todo
Depends on: none | Base commit: d39b1351 | Branch: task/1631-entry-code-schema
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (migrations): brief reviewed as exact diff

## 1. Objective

Add four columns to `apartment` — `entry_code_enc` (encrypted), `entry_code_label`, `entry_code_until` (nullable date), `guide_external_url` (nullable) — via a goose migration, wire retention and export exclusion. No UI yet; later briefs 1632-1634 build on this.

## 2. Context

Rules (`docs/context/rules.md` §Database, §Privacy): schema changes are goose files only in `App/migrations_pg/NNNNN_name.sql` (next number = highest + 1; today highest is `00017_goose_parity.sql`, so this is `00018_...`). Goose files must be additive (old image keeps working). `App/app/migrations/` is frozen at 0045 (`tests/test_sqlite_migrations_frozen.py`); `db.SCHEMA` and `db.ADDED_COLUMNS` never change — read the new columns through the existing added-column accessor pattern, do not extend `db.SCHEMA`. After adding the file, rerun `App/scripts/pg_schema_golden.py` (regenerates `go/internal/schema/expected_schema.json` and the parity artifacts). Rule 2 (AGENTS.md): a new personal-data field gets a line in `App/app/retention.py`.

Anchor 1, `App/app/retention.py:495-511` (the pattern to copy for the new purge step):

```python
def _door_code_pin_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Door codes: the PIN is only useful during the stay; wipe it a day after the code expires.

    The row stays for the stay's record.
    """
    if owner_user_id is not None:
        return 0
    cutoff = _days_ago_iso(1)
    where = "pin_enc IS NOT NULL AND valid_to IS NOT NULL AND valid_to < ?"
```

Anchor 2, the step registry in the same file — find it with `grep -n "door_code_pins" App/app/retention.py` (expect hits near lines 558 and 589):

```python
    ("door_code_pins", _door_code_pin_step),
```

and the human-readable label map:

```python
        "door_code_pins": "valid_to more than 1 day ago",
```

Secrets pattern to copy, `App/app/cleaning_codes.py:119-124`:

```python
def save_manual(apartment_id: int, value: str) -> None:
    if auth.staging_no_login():
        raise ValueError("login_required")
    pin = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9*#-]{1,32}", pin):
        raise ValueError("code")
```

Encryption helper: `db.encrypt_field(...)` / `db.decrypt_field(...)` (used for `pin_enc`; see `door_codes.py`). The new column must be encrypted with the same helper — never plaintext.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00018_apartment_entry_code_guide_url.sql` | new | additive `ALTER TABLE apartment ADD COLUMN ...` x4; follow the style of `00017_goose_parity.sql` |
| `go/internal/schema/expected_schema.json` | regenerated | output of `App/scripts/pg_schema_golden.py` |
| `go/internal/schema/` parity test data, if the golden script regenerates it | regenerated | same script |
| `App/app/retention.py` | edit | doc line + `_entry_code_step` purge (nulls `entry_code_enc` when `entry_code_until` is more than 1 day past, mirroring `_door_code_pin_step`) + registry entry + label |
| `App/app/routes/exports.py` | edit | workspace export must not select/emit `entry_code_enc` (nor plaintext-able derivations) |
| `App/tests/test_migrations.py` or a new small test | add | asserts the four columns exist in pg schema and that the export omits `entry_code_enc` |

No other file may change.

## 4. Steps

1. Write the goose file (additive `ALTER TABLE apartment ADD COLUMN entry_code_enc TEXT`, `entry_code_label TEXT`, `entry_code_until TEXT` (ISO date, nullable), `guide_external_url TEXT`). Check an existing file for the exact goose header conventions used in this repo.
2. Run the golden: from repo root `python3 App/scripts/pg_schema_golden.py` (check its `--help` first if unsure); commit the regenerated `go/internal/schema/expected_schema.json` and any parity output. Run `cd go && go test ./internal/schema/...`.
3. `retention.py`: add `_entry_code_step` mirroring `_door_code_pin_step` (wipe `entry_code_enc` to NULL once `entry_code_until < today - 1 day`; if `entry_code_until` is NULL, never auto-wipe — the host clears it), register it next to `("door_code_pins", _door_code_pin_step)` and add its label next to `"door_code_pins": ...`. Add the required new-field doc line where retention documents fields.
4. `routes/exports.py`: exclude `entry_code_enc` from the apartment export (find the apartment columns list with `grep -n "apartment" App/app/routes/exports.py`).
5. Add the test; run the commands in §6.

## 5. Do not touch

`App/app/migrations/` (frozen), `db.SCHEMA`/`db.ADDED_COLUMNS` in `App/app/db.py`, any guest template, `routes/guest.py`, `mail.py`, `mail_notify.py`, `claim.py` (later briefs), any `.env`/secret, and do not commit data. Never `git add -A`; run `git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_'` before committing.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py -q --tb=short -x 2>&1 | tail -30`
From `App/`: `.venv/bin/python -m pytest tests/test_retention*.py tests/test_privacy_*.py tests/test_pii_encryption.py -q --tb=short -x 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`
From repo root: `cd go && go test ./internal/schema/... 2>&1 | tail -10`

## 7. Acceptance

- [ ] `00018_*.sql` applies cleanly and is additive; golden files regenerated and committed; `go test ./internal/schema/...` green.
- [ ] Migration + retention + pii-encryption test rows green.
- [ ] `grep -n entry_code App/app/routes/exports.py` shows the column excluded (only the exclusion, never a SELECT of it).
- [ ] `git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_'` prints nothing.

## 8. Stop and ask

Stop and write the report if: an excerpt is not found; a test fails twice; you reach 25 tool calls or ~50k tokens; a file outside §3 needs a change; §5 would be touched; the golden script wants to rewrite unrelated files (investigate before committing); you need push/merge/deploy (hand to owner).

## 9. Report

Write `docs/tasks/1631-report.md` (≤600 tokens), set `Status: review`, open one PR. Report: files changed (`git diff --stat`), each command with last 5 lines, §7 ticked, deviations, owner steps left.

## Risk list (for the reviewer)

`App/migrations_pg/00018_apartment_entry_code_guide_url.sql`, `App/app/retention.py`, `App/app/routes/exports.py`, `go/internal/schema/expected_schema.json`.

## Owner steps

1. `python3 scripts/pg_schema.py apply` on staging, then production (per `docs/context/rules.md` §Database the app refuses to start while a migration is pending).
2. Go-first decision pending (decisions.md 2026-11-14): these apartment-settings/guide/mail paths are still Python-served; decide port-first vs Python-now for briefs 1632-1634.
