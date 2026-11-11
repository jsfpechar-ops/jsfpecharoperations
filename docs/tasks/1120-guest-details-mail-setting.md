# 1120: Guest details mail, part a: column and `guest_mail_pref` module

Status: todo
Depends on: none | Base commit: 169ee203 | Branch: task/1120-guest-details-mail-setting
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Split note: the plan's brief 1120 would not fit 30 tool calls (two migrations, a module, a route, a template, i18n, two test files, the UX gate). It is two briefs: **1120 (this file)** is the backend, **[1120b](1120b-guest-details-mail-settings-page.md)** is the switch on the settings page and the UX gate. 1120b depends on this one.

## 1. Objective

Add a per-workspace-owner switch "full guest details in the confirmation e-mail" (a boolean, on by default) and the one function the mail briefs call, `guest_mail_pref.full_details(owner_user_id)`. The function is True only when the switch is on and the owner has accepted the current DPA, so no guest detail leaves in a mail before the DPA that describes it is accepted.

## 2. Context

Plan: docs/plans/guest-details-mail.md. Rules that apply (docs/context/rules.md, Database): all SQL goes through `App/app/db.py` helpers, parameterised, no SQLite-only syntax. A schema change SQLite reads needs BOTH a file in `App/app/migrations/` and a goose twin in `App/migrations_pg/` (next number = highest + 1). The workspace owner is a row in `user_account` (hosts are their own workspace owner; `stay_fee_auto.emails_enabled` and `lifecycle_mail` keep their per-owner switches on `user_account` the same way). So the column goes on `user_account`.

Newest SQLite migration, `App/app/migrations/0043_guest_signed_for.sql` (form to copy: a `--` comment line with the brief number and a line saying whether it is personal data, then the statement):
```
-- Brief 1089: which adult guest signed for a guest under 15, in which role, when and under which wording.
-- Personal data about the adult and the child, kept with the guest row and deleted with it.
ALTER TABLE guest ADD COLUMN signed_for_guest_id INTEGER;
```
Newest goose twin, `App/migrations_pg/00014_guest_signed_for.sql`:
```
-- +goose Up
-- Twin of App/app/migrations/0043_guest_signed_for.sql (brief 1089).
-- pg_schema apply runs the SQLite file first, so statements are IF NOT EXISTS.
ALTER TABLE guest ADD COLUMN IF NOT EXISTS signed_for_guest_id BIGINT;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (43, 'guest_signed_for', '2026-11-10T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 43;
ALTER TABLE guest DROP COLUMN IF EXISTS signed_for_guest_id;
```
The acceptance API (`App/app/acceptance.py`):
```
def pending(user_id: int) -> List[str]:
    """The documents whose current version this account has not accepted."""
def record(
    user_id: int, docs: Iterable[str], method: str, request: Optional[Any] = None
) -> List[str]:
```
`db.audit(action, detail="", actor="host", owner_user_id=None)` exists. The test that pins the migration count, `App/tests/test_migrations.py`:
```
@pytest.mark.sqlite_only
def test_python_runner_is_frozen():
    assert max(v for v, _n, _p in db.migration_files()) == 43
```
Privacy (AGENTS rule 2): the new column is a boolean preference of the host about their own account. It is not personal data about a guest or a person, so no line is needed in `App/app/retention.py`; the column is deleted with the `user_account` row. Do not edit retention.py.

If an excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/migrations/0044_guest_details_mail.sql | create | the column |
| App/migrations_pg/00015_guest_details_mail.sql | create | goose twin |
| App/tests/test_migrations.py | edit | pin 43 becomes 44 |
| App/app/guest_mail_pref.py | create | `full_details`, `set_full_details` |
| App/tests/test_guest_mail_pref.py | create | three behaviour tests plus a setter test |

No other file may change.

## 4. Steps

1. Create `App/app/migrations/0044_guest_details_mail.sql` with exactly:
```
-- Brief 1120: the host's switch for full guest details in the confirmation e-mail (1 = on, the default).
-- A boolean preference of the account, not personal data; it goes with the user_account row.
ALTER TABLE user_account ADD COLUMN guest_details_mail INTEGER NOT NULL DEFAULT 1;
```
Command: `cat App/app/migrations/0044_guest_details_mail.sql | tail -30`. Expected: the three lines.

2. Create `App/migrations_pg/00015_guest_details_mail.sql` with exactly:
```
-- +goose Up
-- Twin of App/app/migrations/0044_guest_details_mail.sql (brief 1120).
-- pg_schema apply runs the SQLite file first, so statements are IF NOT EXISTS.
ALTER TABLE user_account ADD COLUMN IF NOT EXISTS guest_details_mail BIGINT NOT NULL DEFAULT 1;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (44, 'guest_details_mail', '2026-11-11T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 44;
ALTER TABLE user_account DROP COLUMN IF EXISTS guest_details_mail;
```
Command: `ls App/migrations_pg | tail -3`. Expected: `00013_...`, `00014_guest_signed_for.sql`, `00015_guest_details_mail.sql`.

3. In `App/tests/test_migrations.py`, replace `    assert max(v for v, _n, _p in db.migration_files()) == 43` with `    assert max(v for v, _n, _p in db.migration_files()) == 44`.
Command: `cd App && .venv/bin/python -m pytest tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed. If the tail shows a count other than 44 or a failure about another pinned number, STOP.

4. Create `App/app/guest_mail_pref.py` with exactly:
```python
"""Whether the host's confirmation mail carries full guest details (brief 1120).

The switch is ``user_account.guest_details_mail`` of the workspace owner, on by
default. Full details leave only after the owner accepted the DPA version that
describes them, so ``full_details`` also reads ``acceptance.pending``. Other
modules call this function and never read the column.
"""
from __future__ import annotations

from . import acceptance, db


def switch_on(owner_user_id: int) -> bool:
    """The stored switch alone, for the settings page."""
    row = db.query_one(
        "SELECT guest_details_mail FROM user_account WHERE id = ?", (owner_user_id,)
    )
    return bool(row) and bool(row["guest_details_mail"])


def full_details(owner_user_id: int) -> bool:
    """True when the workspace switch is on AND the owner accepted the current DPA."""
    if not switch_on(owner_user_id):
        return False
    return "dpa" not in acceptance.pending(owner_user_id)


def set_full_details(owner_user_id: int, enabled: bool, *, actor: str) -> None:
    """Store the switch and audit the change (ids only, no guest data)."""
    db.execute(
        "UPDATE user_account SET guest_details_mail = ? WHERE id = ?",
        (1 if enabled else 0, owner_user_id),
    )
    db.audit(
        "guest_details_mail_on" if enabled else "guest_details_mail_off",
        f"user_id={owner_user_id} by={actor}",
        owner_user_id=owner_user_id,
    )
```
Command: `cd App && .venv/bin/python -c "from app import guest_mail_pref; print(guest_mail_pref.full_details.__name__)" 2>&1 | tail -30`. Expected: `full_details`.

5. Create `App/tests/test_guest_mail_pref.py` with exactly:
```python
"""1120: the guest-details mail switch and the DPA gate behind full_details."""
from __future__ import annotations

import pytest

from app import acceptance, auth, db, guest_mail_pref

USERNAME = "guest-mail-pref-owner"


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (user["id"],))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(
        "guest-mail-pref-owner@example.test", "Pref Demo", role="host", username=USERNAME
    )
    try:
        yield owner_id
    finally:
        _cleanup()


def _accept_everything(owner_id):
    acceptance.record(owner_id, acceptance.DOCUMENTS, "test")
    assert acceptance.pending(owner_id) == []


def test_the_switch_is_on_by_default(owner):
    assert guest_mail_pref.switch_on(owner) is True
    _accept_everything(owner)
    assert guest_mail_pref.full_details(owner) is True


def test_switching_off_gives_false(owner):
    _accept_everything(owner)
    guest_mail_pref.set_full_details(owner, False, actor=USERNAME)
    assert guest_mail_pref.switch_on(owner) is False
    assert guest_mail_pref.full_details(owner) is False
    guest_mail_pref.set_full_details(owner, True, actor=USERNAME)
    assert guest_mail_pref.full_details(owner) is True


def test_on_but_dpa_pending_gives_false(owner):
    assert "dpa" in acceptance.pending(owner)
    assert guest_mail_pref.switch_on(owner) is True
    assert guest_mail_pref.full_details(owner) is False
    acceptance.record(owner, ["terms", "privacy"], "test")
    assert guest_mail_pref.full_details(owner) is False
    acceptance.record(owner, ["dpa"], "test")
    assert guest_mail_pref.full_details(owner) is True


def test_an_unknown_account_gives_false():
    db.init_db()
    assert guest_mail_pref.full_details(999999999) is False
```
Command: `cd App && .venv/bin/python -m pytest tests/test_guest_mail_pref.py -q --tb=short -x 2>&1 | tail -30`. Expected: `4 passed`.

6. Run the test-map row for the changed area (Database, migrations) plus the goose name check.
Command: `cd App && .venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py tests/test_goose_migrations.py -q --tb=short -x 2>&1 | tail -30`. Expected: no failures (Postgres-only tests may show as skipped; that is fine here, they are not browser tests).

7. Lint the docs: from the repo root, `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no new error for this brief.

## 5. Do not touch

- `App/app/retention.py` (the column is a boolean preference, not personal data; see §2).
- `App/app/db.py` (`db.SCHEMA` and `db.ADDED_COLUMNS` never change), `App/app/mail_notify.py` and `App/app/claim.py` (briefs 1121 and 1122 own them), `App/app/acceptance.py`, any template, route or i18n file (that is 1120b).
- No new dependency. SQL only through `db.py` helpers. Public repo: no secrets, no real guest data in tests. No `INSERT OR IGNORE`, no `lastrowid`.

## 6. Commands

As in the steps; all end `| tail -30`. Run only these. No full suite, no browser tests.

## 7. Acceptance

- [ ] `0044_guest_details_mail.sql` and `00015_guest_details_mail.sql` exist and match §4 exactly.
- [ ] `tests/test_guest_mail_pref.py` shows `4 passed`.
- [ ] `tests/test_migrations.py tests/test_db_*.py tests/test_goose_migrations.py` pass.
- [ ] `git diff --stat` lists only the five files of §3.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1120-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/migrations_pg/00015_guest_details_mail.sql` and `App/app/migrations/0044_guest_details_mail.sql`: the pair must agree (version 44, column name, default 1).
- `App/app/guest_mail_pref.py`: `full_details` is the gate for all guest data in mail.

## Owner steps

None. Merge with `scripts/merge-pr-on-green.sh`. Nothing is visible to hosts until 1120b and 1121 ship.
