# 0021: The database refuses two active properties on one lock

Status: todo
Depends on: PR #325 merged to `main` | Base commit: `main` after PR #325 | Branch: task/0021-one-lock-database-rule
Executor: Cursor local agent (composer, Kimi or GLM) or Claude Haiku | Fits one session

## 1. Objective

A TTLock lock must serve one active property per owner, enforced by the database and not only by the form. Today `_properties_using_lock` in `admin.py` checks this before saving, but two saves at the same moment, or properties that already share a lock, slip through, and a stay's door code would then go to the wrong door.

## 2. Context

Rules that apply (AGENTS.md): rule 5 (schema change = a new `App/app/migrations/` file, SQL only through `db.py` helpers, Postgres-portable), rule 1 (nothing here touches UbyPort), rule 4 (no new dependency). This brief changes no template and no CSS, so rule 7 (browser tests, screenshots) does not apply.

What already exists (do not change it):
- `apartment` columns `owner_user_id`, `lock_provider` (`'ttlock'` or NULL), `lock_id` (text), `archived_at` (NULL while active).
- `db.is_unique_violation(exc)` in `App/app/db.py` is true for a UNIQUE failure on SQLite and Postgres.
- Door codes need `owner_user_id` set, so NULL owners are out of scope. NULLs are distinct in a unique index, so they are never blocked.
- The latest migration is `0007_door_codes.sql`, so the new file is `0008`. Run `python3 scripts/context_lint.py` from the repo root: it prints `next free: ... migration 0008`. If it prints another number, STOP (§8).

Design decisions (already made, do not re-open):
- The index covers only **active** properties (`archived_at IS NULL`) that have door codes switched on (`lock_provider = 'ttlock'`). An archived property sends no codes, so it must not hold a lock.
- Existing duplicates: the migration keeps the **oldest** property (lowest `id`) on the lock and sets `lock_provider = NULL` on the others. The others keep their `lock_id` and hours; the host switches door codes on again after choosing a free lock.
- Restoring an archived property whose lock was taken meanwhile turns its door codes off and tells the host.

Anchor 1, `App/app/routes/admin.py`, inside `_properties_using_lock` (must be found verbatim, exactly once):

```python
        "AND lock_provider = 'ttlock' AND lock_id = ?",
        (owner_id, lock_id),
```

Anchor 2, `App/app/routes/admin.py`, in `_save_apartment_form` (must be found verbatim, exactly once; the two lines are consecutive):

```python
    db.update("apartment", apartment_id, payload)
    if credentials_changed:
```

Anchor 3, `App/app/routes/admin.py`, in `unarchive_apartment` (must be found verbatim, exactly once):

```python
    db.update(
        "apartment",
        apartment_id,
        {"archived_at": None, "active": 1},
    )
    db.audit("apartment_unarchived", f"id={apartment_id}")
    return _back(return_to, msg=_flash(request, "flash.apartments.restored"))
```

Anchor 4, `App/app/host_i18n.py` (exactly one line each; the English one comes first in the file):

```python
        "flash.apartments.restored": "Property restored from archive.",
```
```python
        "flash.apartments.restored": "Ubytování bylo obnoveno z archivu.",
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0008_one_lock_per_property.sql` | create | Clean existing duplicates, then the partial unique index |
| `App/app/routes/admin.py` | edit | Ignore archived properties in the check; catch the unique violation on save; handle restore |
| `App/app/host_i18n.py` | edit | One new message in English and Czech |
| `App/tests/test_one_lock_database_rule.py` | create | 9 tests |
| `docs/tasks/0021-report.md` | create | The report (§9) |

No other file may change. Do not edit `docs/context/*`; the orchestrator does that at review.

## 4. Steps

1. From the repo root run `python3 scripts/context_lint.py`. Confirm the output contains `migration 0008`. Run `git status --short`; it must be empty (no local changes).

2. Create `App/app/migrations/0008_one_lock_per_property.sql` with exactly this content:

```sql
-- A TTLock lock serves one active property per owner. Two properties on one
-- lock would put a stay's code on the wrong door.
--
-- Step 1 keeps the oldest property on a lock that is already shared and turns
-- door codes off on the others (the host picks a lock for them again).
-- Archived properties are ignored: they send no codes.
-- Step 2 makes the database refuse a second active property on the same lock.
UPDATE apartment SET lock_provider = NULL
WHERE lock_provider = 'ttlock' AND lock_id IS NOT NULL AND archived_at IS NULL
  AND id NOT IN (
    SELECT MIN(id) FROM apartment
    WHERE lock_provider = 'ttlock' AND lock_id IS NOT NULL AND archived_at IS NULL
    GROUP BY owner_user_id, lock_id
  );

CREATE UNIQUE INDEX IF NOT EXISTS idx_apartment_one_lock
  ON apartment (owner_user_id, lock_id)
  WHERE lock_provider = 'ttlock' AND lock_id IS NOT NULL AND archived_at IS NULL;
```

3. In `App/app/routes/admin.py`, replace Anchor 1 with:

```python
        "AND lock_provider = 'ttlock' AND lock_id = ? AND archived_at IS NULL",
        (owner_id, lock_id),
```

4. In `App/app/routes/admin.py`, replace Anchor 2 with:

```python
    try:
        db.update("apartment", apartment_id, payload)
    except Exception as exc:
        # Two saves at once can both pass the check above; the database index decides.
        if payload.get("lock_provider") == "ttlock" and db.is_unique_violation(exc):
            return _back(
                f"/apartments/{apartment_id}#door-code",
                err=_flash(request, "flash.error.door_code_lock_taken"),
            )
        raise
    if credentials_changed:
```

5. In `App/app/routes/admin.py`, replace Anchor 3 with:

```python
    values = {"archived_at": None, "active": 1}
    lock_taken = bool(
        apartment["lock_provider"] == "ttlock"
        and apartment["lock_id"]
        and _properties_using_lock(apartment["owner_user_id"], apartment["lock_id"], apartment_id)
    )
    if lock_taken:
        # Another property took the lock while this one was archived.
        values["lock_provider"] = None
    db.update("apartment", apartment_id, values)
    db.audit("apartment_unarchived", f"id={apartment_id}")
    message = "flash.apartments.restored_lock_off" if lock_taken else "flash.apartments.restored"
    return _back(return_to, msg=_flash(request, message))
```

6. In `App/app/host_i18n.py`, insert a new line directly after the English Anchor 4 line (same indentation, 8 spaces):

```python
        "flash.apartments.restored_lock_off": "Restored. Its digital door lock is now used by another property, so door codes are off here. Choose a lock again in the Door code section.",
```

and directly after the Czech Anchor 4 line:

```python
        "flash.apartments.restored_lock_off": "Obnoveno. Jeho digitální zámek už používá jiné ubytování, proto jsou tady kódy ke dveřím vypnuté. Zámek vyberte znovu v sekci Digitální zámek.",
```

7. Create `App/tests/test_one_lock_database_rule.py` with exactly this content:

```python
"""Task 0021: the database itself refuses two active properties on one lock."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from app.routes import admin
from tests.conftest import login_as

USERNAME = "onelockdb-host"
OTHER = "onelockdb-other"
LOCK = {"lock_id": "35662508", "alias": "Vivus_A41", "battery": 80, "tz_offset_ms": 3600000}
MIGRATION = Path(__file__).resolve().parents[1] / "app" / "migrations" / "0008_one_lock_per_property.sql"


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    _cleanup()
    owner = auth.create_account(f"{USERNAME}@example.test", "Host", username=USERNAME)
    other = auth.create_account(f"{OTHER}@example.test", "Other", username=OTHER)
    now = db.utcnow()
    for who in (owner, other):
        db.insert(
            "lock_account",
            {
                "owner_user_id": who,
                "provider": "ttlock",
                "username": f"x_{who}",
                "status": "ok",
                "locks_json": json.dumps([LOCK]),
                "created_at": now,
                "updated_at": now,
            },
        )
    yield owner, other
    _cleanup()


def _cleanup():
    for name in (USERNAME, OTHER):
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))
        if not row:
            continue
        oid = row["id"]
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


_n = 0


def _property(owner: int, name: str, *, lock: bool = True, archived: bool = False) -> int:
    global _n
    _n += 1
    now = db.utcnow()
    entity = db.query_one("SELECT id FROM legal_entity WHERE owner_user_id = ?", (owner,))
    entity_id = entity["id"] if entity else db.insert(
        "legal_entity",
        {"name": "E", "seat": "Praha", "created_at": now, "owner_user_id": owner, "contact_email": "h@example.test"},
    )
    row = {
        "legal_entity_id": entity_id,
        "owner_user_id": owner,
        "internal_name": name,
        "permalink_token": f"onelockdb-{_n}",
        "automation_mode": "manual",
        "default_purpose": "10",
        "active": 1,
        "created_at": now,
    }
    if lock:
        row.update({"lock_provider": "ttlock", "lock_id": LOCK["lock_id"], "checkin_hour": 15, "checkout_hour": 10})
    if archived:
        row["archived_at"] = now
    return db.insert("apartment", row)


def _get(apartment_id: int):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


def _client(username: str) -> TestClient:
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    return client


def _form(apartment_id: int) -> dict:
    row = _get(apartment_id)
    return {
        "internal_name": row["internal_name"],
        "legal_entity_id": str(row["legal_entity_id"]),
        "door_code_section": "1",
        "door_codes": "1",
        "lock_id": LOCK["lock_id"],
        "checkin_hour": "15",
        "checkout_hour": "10",
    }


def test_the_index_exists_after_a_normal_start(world):
    names = [r["name"] for r in db.query("PRAGMA index_list(apartment)")]
    assert "idx_apartment_one_lock" in names


def test_the_database_refuses_a_second_active_property_on_one_lock(world):
    owner, _ = world
    _property(owner, "Flat A")
    with pytest.raises(Exception) as caught:
        _property(owner, "Flat B")
    assert db.is_unique_violation(caught.value)


def test_another_host_may_use_the_same_lock_id(world):
    owner, other = world
    _property(owner, "Flat A")
    _property(other, "Flat B")


def test_an_archived_property_does_not_hold_the_lock(world):
    owner, _ = world
    _property(owner, "Old flat", archived=True)
    _property(owner, "New flat")


def test_the_migration_keeps_the_oldest_property_and_switches_the_others_off(world):
    owner, other = world
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.executescript("DROP INDEX IF EXISTS idx_apartment_one_lock;")
    conn.close()
    oldest = _property(owner, "Oldest")
    newer = _property(owner, "Newer")
    archived = _property(owner, "Archived", archived=True)
    elsewhere = _property(other, "Elsewhere")
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.executescript(MIGRATION.read_text(encoding="utf-8"))
    conn.close()
    assert _get(oldest)["lock_provider"] == "ttlock"
    assert _get(newer)["lock_provider"] is None
    assert _get(archived)["lock_provider"] == "ttlock"
    assert _get(elsewhere)["lock_provider"] == "ttlock"
    assert "idx_apartment_one_lock" in [r["name"] for r in db.query("PRAGMA index_list(apartment)")]


def test_two_saves_at_once_end_with_the_taken_message_not_an_error(world, monkeypatch):
    owner, _ = world
    _property(owner, "Flat A")
    b = _property(owner, "Flat B", lock=False)
    monkeypatch.setattr(admin, "_properties_using_lock", lambda *a, **k: [])
    response = _client(USERNAME).post(f"/apartments/{b}", data=_form(b), follow_redirects=False)
    assert response.status_code == 303
    assert "door-code" in response.headers["location"]
    assert _get(b)["lock_provider"] is None


def test_archiving_a_property_frees_its_lock_for_another(world):
    owner, _ = world
    a = _property(owner, "Flat A")
    b = _property(owner, "Flat B", lock=False)
    client = _client(USERNAME)
    assert client.post(f"/apartments/{a}/archive", data={}, follow_redirects=False).status_code == 303
    client.post(f"/apartments/{b}", data=_form(b), follow_redirects=False)
    assert _get(b)["lock_provider"] == "ttlock"


def test_restoring_a_property_whose_lock_was_taken_turns_its_door_codes_off(world):
    owner, _ = world
    a = _property(owner, "Flat A", archived=True)
    _property(owner, "Flat B")
    response = _client(USERNAME).post(
        f"/apartments/{a}/unarchive", data={}, follow_redirects=True
    )
    assert response.status_code == 200
    assert _get(a)["archived_at"] is None
    assert _get(a)["lock_provider"] is None
    assert "door codes are off here" in response.text


def test_restoring_a_property_whose_lock_is_free_keeps_it(world):
    owner, _ = world
    a = _property(owner, "Flat A", archived=True)
    _client(USERNAME).post(f"/apartments/{a}/unarchive", data={}, follow_redirects=False)
    assert _get(a)["lock_provider"] == "ttlock"
```

8. Run the commands in §6 and write the report (§9).

## 5. Do not touch

- `db.SCHEMA`, `db.ADDED_COLUMNS` (frozen baseline), `App/app/migrations/0001` to `0007`.
- Any template, CSS or JavaScript file.
- `App/app/door_codes.py`, `App/app/ttlock.py`, `App/app/mail_notify.py`, `App/app/env_guard.py`, `App/app/auth.py`.
- `docs/context/*` and `docs/privacy/*` (the orchestrator updates them at review).
- AGENTS.md rules that apply: 5 (migration, db helpers), 8 (never push to `main`; open one PR from your branch).

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_one_lock_database_rule.py -q
```
Expected last line: `9 passed`.

```
.venv/bin/python -m pytest tests/test_migrations.py tests/test_door_code_one_lock_one_property.py tests/test_smart_locks_page.py -q
```
Expected: all pass, 0 failed.

```
.venv/bin/python -m pytest tests -q
```
Expected: 0 failed, apart from at most these 4 which fail in a sandbox without outbound DNS and fail the same way on `main`: `test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses`, `test_feed_url_ssrf.py::test_redirects_are_revalidated_not_followed_blindly`, `test_feed_url_ssrf.py::test_a_redirect_that_drops_https_is_refused`, `test_feed_url_ssrf.py::test_allows_public_https_calendar`. Any other failure: see §8.

From the repo root:

```
python3 scripts/context_lint.py
```
Expected last line: `context lint: OK`.

## 7. Acceptance

- [ ] `0008_one_lock_per_property.sql` exists and the full test run shows `idx_apartment_one_lock` in `PRAGMA index_list(apartment)` (test 1 passes).
- [ ] 9 passed in `test_one_lock_database_rule.py`.
- [ ] `git diff --stat` lists only the five files in §3.
- [ ] No test outside the four sandbox-DNS ones fails.
- [ ] `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in §2 is not found exactly once;
- the lint does not say `migration 0008`;
- a test fails twice after you re-read your edit against §4;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0021-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: the migration (the `UPDATE` must only touch non-archived `ttlock` rows with a lock id and must keep the lowest id per owner and lock), the `try/except` in `_save_apartment_form` (it must re-raise anything that is not a unique violation on a ttlock save), and `unarchive_apartment`.

## Owner steps

Before merging and deploying this to production, check whether any property already shares a lock. Reading only, changes nothing:

1. Open a terminal on the Lightsail server.
2. Run: `cd /opt/ubyhost/deploy/lightsail && docker compose exec ubyhost sqlite3 -readonly /data/ubyhost.db "SELECT owner_user_id, lock_id, COUNT(*) FROM apartment WHERE lock_provider='ttlock' AND lock_id IS NOT NULL AND archived_at IS NULL GROUP BY owner_user_id, lock_id HAVING COUNT(*) > 1;"`
3. Nothing printed means no duplicates, and you can go on.
4. If rows print, each row is one host and one lock used by several properties. After the deploy, the oldest property keeps the lock and the others switch door codes off. Tell that host to choose a lock again for the others (property, section Door code), or to switch them off on purpose.
5. Take a backup first as usual (see [backup and restore](../OPERATIONS.md#backup-and-restore)). The migration changes data.
6. Do the same check on Render staging if you test there (staging's database is wiped when it restarts, so duplicates there disappear anyway).
