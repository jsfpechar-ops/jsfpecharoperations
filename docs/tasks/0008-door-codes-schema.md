# 0008: Door codes, schema and settings

Status: done
Depends on: none | Base commit: 9f4709f | Branch: task/0008-door-codes-schema
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Add the tables, columns and settings the TTLock door-code feature needs, plus the retention step that wipes a door code's PIN after checkout. Nothing uses them yet. No behaviour changes.

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md` §5 (data model). Read only §5.
- Rule 5: SQL only through `App/app/db.py` helpers, Postgres-portable. A schema change is a new file in `App/app/migrations/`. Migrations are applied by `db.init_db()` from files named `NNNN_name.sql` (`App/app/db.py`, `migration_files`). Copy the style of `App/app/migrations/0006_passkeys.sql`: a comment block on top, `CREATE TABLE IF NOT EXISTS`, `INTEGER PRIMARY KEY AUTOINCREMENT`, `TEXT` timestamps.
- Rule 2: every new personal-data field gets a retention line in `App/app/retention.py` and a row in `docs/privacy/RETENTION.md`.
- Rule 3: no secret in git. `TTLOCK_CLIENT_SECRET` is env only.
- Retention steps take `(today, dry_run, owner_user_id)` and return a count, and are listed in `STEPS` in `App/app/retention.py`. Copy `_webauthn_challenge_step` (it returns 0 when `owner_user_id` is not None).
- Config reads env like `HEARTBEAT_URL = os.environ.get("UBYHOST_HEARTBEAT_URL", "").strip()` in `App/app/config.py`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0007_door_codes.sql` | create | Step 1 |
| `App/app/config.py` | edit | Step 2 |
| `App/app/retention.py` | edit | Step 3 |
| `App/tests/test_door_codes_schema.py` | create | Step 4 |
| `docs/privacy/RETENTION.md` | edit | One table row, step 5 |
| `docs/ENVIRONMENT.md` | edit | New section, step 5 |

No other file may change.

## 4. Steps

1. Create `App/app/migrations/0007_door_codes.sql` with a comment block that says what each table is for, then exactly:
   ```sql
   ALTER TABLE apartment ADD COLUMN lock_provider TEXT;
   ALTER TABLE apartment ADD COLUMN lock_id TEXT;
   ALTER TABLE apartment ADD COLUMN checkin_hour INTEGER;
   ALTER TABLE apartment ADD COLUMN checkout_hour INTEGER;

   CREATE TABLE IF NOT EXISTS lock_account (
       id                INTEGER PRIMARY KEY AUTOINCREMENT,
       owner_user_id     INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
       provider          TEXT NOT NULL DEFAULT 'ttlock',
       username          TEXT NOT NULL,
       password_enc      TEXT,
       access_token_enc  TEXT,
       refresh_token_enc TEXT,
       token_expires_at  TEXT,
       token_version     INTEGER NOT NULL DEFAULT 0,
       status            TEXT NOT NULL DEFAULT 'ok',
       locks_json        TEXT,
       locks_fetched_at  TEXT,
       created_at        TEXT NOT NULL,
       updated_at        TEXT NOT NULL,
       UNIQUE (owner_user_id, provider)
   );

   CREATE TABLE IF NOT EXISTS door_code (
       id               INTEGER PRIMARY KEY AUTOINCREMENT,
       reservation_id   INTEGER NOT NULL UNIQUE REFERENCES reservation(id) ON DELETE CASCADE,
       apartment_id     INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
       lock_id          TEXT NOT NULL,
       code_kind        TEXT NOT NULL DEFAULT 'random',
       state            TEXT NOT NULL DEFAULT 'pending',
       pin_enc          TEXT,
       provider_code_id TEXT,
       valid_from       TEXT,
       valid_to         TEXT,
       attempts         INTEGER NOT NULL DEFAULT 0,
       next_attempt_at  TEXT,
       claimed_at       TEXT,
       last_error       TEXT,
       notified_at      TEXT,
       issued_at        TEXT,
       revoked_at       TEXT,
       created_at       TEXT NOT NULL,
       updated_at       TEXT NOT NULL
   );
   CREATE INDEX IF NOT EXISTS idx_door_code_due ON door_code (state, next_attempt_at);

   CREATE TABLE IF NOT EXISTS lock_api_usage (
       month    TEXT NOT NULL,
       provider TEXT NOT NULL,
       calls    INTEGER NOT NULL DEFAULT 0,
       PRIMARY KEY (month, provider)
   );
   ```
2. In `App/app/config.py`, next to the other env settings, add:
   ```python
   # Door codes (TTLock). Off unless UBYHOST_DOOR_CODES=1; the secret is env only.
   DOOR_CODES_ENABLED = os.environ.get("UBYHOST_DOOR_CODES", "0") in ("1", "true", "yes")
   TTLOCK_API_BASE = os.environ.get("UBYHOST_TTLOCK_API_BASE", "https://euapi.ttlock.com").rstrip("/")
   TTLOCK_CLIENT_ID = os.environ.get("UBYHOST_TTLOCK_CLIENT_ID", "").strip()
   TTLOCK_CLIENT_SECRET = os.environ.get("UBYHOST_TTLOCK_CLIENT_SECRET", "").strip()
   TTLOCK_MONTHLY_CALLS = int(os.environ.get("UBYHOST_TTLOCK_MONTHLY_CALLS", "30000"))
   # Codes work from 1 h before check-in to 1 h after check-out: covers lock clock
   # drift and any daylight-saving mismatch in the lock. Hours have no default; the host sets them.
   DOOR_CODE_BUFFER_HOURS = 1
   ```
3. In `App/app/retention.py`, add `_door_code_pin_step(today, dry_run, owner_user_id)`. It returns 0 when `owner_user_id` is not None. Otherwise it counts (dry run) or sets `pin_enc = NULL, updated_at = db.utcnow()` on rows where `pin_enc IS NOT NULL AND valid_to IS NOT NULL AND valid_to < ?`, the cutoff being now minus 1 day as a UTC ISO string in the same format as `db.utcnow()`. Docstring: "Door codes: the PIN is only useful during the stay; wipe it a day after the code expires. The row stays for the stay's record." Add `("door_code_pins", _door_code_pin_step)` to `STEPS`, after `("webauthn_challenges", ...)`.
4. Create `App/tests/test_door_codes_schema.py`, using `db.init_db()` like `App/tests/test_retention_alignment.py`. Tests:
   - `test_migration_creates_door_code_tables_and_columns`: `PRAGMA table_info` shows the 4 apartment columns and the 3 tables.
   - `test_one_door_code_per_reservation`: a second `door_code` insert for the same `reservation_id` raises `sqlite3.IntegrityError`.
   - `test_pin_is_wiped_a_day_after_expiry`: one row with `valid_to` 2 days ago and one with `valid_to` in 1 hour, both with `pin_enc` set. A dry run returns 1 and changes nothing. A real run returns 1, the old row's `pin_enc` is NULL, the new row's is unchanged.
   - `test_door_codes_are_off_by_default`: `config.DOOR_CODES_ENABLED is False` when `UBYHOST_DOOR_CODES` is unset.
   Create the needed `apartment` and `reservation` rows with the helpers the retention tests use, and delete everything the test made in a fixture.
5. Docs:
   - `docs/privacy/RETENTION.md`, table "What the code deletes or minimises", two new rows: `| Door code PIN | door_code.pin_enc | code expiry | 1 day after the code expires | retention.py door-code-PIN step | Minimisation |` and `| TTLock connection (UbyHost-made TTLock user, its encrypted password and tokens, cached lock list) | lock_account | host removes it, or the account is deleted | until then | Smart locks page Remove; cascade from user_account | Contract |`.
   - `docs/ENVIRONMENT.md`: a new section `## Door codes (TTLock)` after `## Mail`, a table in the same format as the others, one row per variable in step 2 (`UBYHOST_DOOR_CODES`, `UBYHOST_TTLOCK_API_BASE`, `UBYHOST_TTLOCK_CLIENT_ID`, `UBYHOST_TTLOCK_CLIENT_SECRET`, `UBYHOST_TTLOCK_MONTHLY_CALLS`). The secret row says "Secret. Lightsail `.env` only, never in git."

## 5. Do not touch

Everything not in §3. `App/app/db.py` (the runner already picks up the new file). No UI, no route, no scheduler job, no mail.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (expected: all pass). From the repo root: `python3 scripts/context_lint.py` (expected last line: `context lint: OK`).

## 7. Acceptance

- [ ] The 4 tests in step 4 pass. The full suite passes.
- [ ] `tests/test_migrations.py` passes unchanged (an empty and an upgraded database end with the same schema).
- [ ] `git diff --stat` shows only the files in §3.
- [ ] `grep -rn "TTLOCK_CLIENT_SECRET" App/app` shows only the line in `config.py`.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or name in §2 is not found;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0008-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/migrations/0007_door_codes.sql`
- `App/app/retention.py` (the new step only)

## Owner steps

None for this task. The feature stays off (`UBYHOST_DOOR_CODES` unset).
