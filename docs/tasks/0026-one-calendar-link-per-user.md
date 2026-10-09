# 0026: A host cannot add the same calendar link to two of their properties

Status: todo
Depends on: none (independent of PR #325) | Base commit: `main` (`81c1122` or later) | Branch: task/0026-one-calendar-link-per-user
Executor: Claude Haiku 5.5, effort high (or Cursor composer, Kimi, GLM) | Fits one session

## 1. Objective

When a host adds a calendar link that is already on one of **their own** properties (the same one or another), UbyHost refuses it and names that property. Today the same link on two properties makes every booking two stays, and so two police filings (known issue K-F20, rule 1).

## 2. Context

Owner decision 2026-10-09: the check is per user only. Links on other users' properties are never looked at.

Rules: 1 (filing correctness), 5 (SQL through `db.py` helpers, Postgres-portable; `db.null_safe_eq` for the owner column, which can be NULL), 9 (copy), 4 (no dependency). No schema change; no migration.

Only one route saves a calendar link: `add_feed` in `App/app/routes/admin.py` (`demo.py` seeds demo data and is out of scope).

Anchor C1, `App/app/routes/admin.py` (exactly once):
```python
@router.post("/apartments/{apartment_id}/feeds")
async def add_feed(apartment_id: int, request: Request):
```
Anchor C2, same file (exactly once, inside `add_feed`):
```python
    except FeedUrlError as exc:
        return _back(f"/apartments/{apartment_id}", err=_flash(request, exc.key))
    db.insert(
        "ical_feed",
```
Anchor C3, `App/app/host_i18n.py`: the line `        "flash.error.feed_added_unreadable": (` appears exactly **twice**: first in the English block, then in the Czech block.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | one helper + one check |
| `App/app/host_i18n.py` | edit | one message, en and cs |
| `App/tests/test_feed_no_duplicate_per_user.py` | create | 4 tests (full code in step 4) |
| `docs/context/known-issues.md` | edit | delete the K-F20 row |
| `docs/tasks/0026-report.md` | create | report |

No other file may change.

## 4. Steps

1. In `admin.py`, directly **above** anchor C1 (above the `@router.post` line), insert:
```python
def _feed_already_added(apartment_id: int, url: str) -> str:
    """The name of this owner's property that already has ``url``, or "".

    One booking calendar belongs to one property: the same link on two of the
    owner's properties turns every booking into two stays and two police
    filings. Only this owner's properties are checked, never other users'.
    """
    apartment = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return ""
    row = db.query_one(
        "SELECT a.id, a.internal_name FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
        f"WHERE {db.null_safe_eq('a.owner_user_id')} AND f.url = ? ORDER BY a.id LIMIT 1",
        (apartment["owner_user_id"], url),
    )
    if not row:
        return ""
    return row["internal_name"] or f"#{row['id']}"


```
2. Replace anchor C2 with:
```python
    except FeedUrlError as exc:
        return _back(f"/apartments/{apartment_id}", err=_flash(request, exc.key))
    already = _feed_already_added(apartment_id, url)
    if already:
        return _back(
            f"/apartments/{apartment_id}",
            err=_flash(request, "flash.error.feed_duplicate", property=already),
        )
    db.insert(
        "ical_feed",
```
3. In `host_i18n.py`, directly **above the first** C3 line (English) insert:
```python
        "flash.error.feed_duplicate": "This calendar link is already added to %(property)s. One booking calendar belongs to one property, otherwise every booking would be reported to the police twice.",
```
and directly **above the second** C3 line (Czech) insert:
```python
        "flash.error.feed_duplicate": "Tento odkaz na kalendář už je přidaný u %(property)s. Jeden kalendář rezervací patří k jedné nemovitosti, jinak by se každá rezervace hlásila policii dvakrát.",
```
4. Create `App/tests/test_feed_no_duplicate_per_user.py` with exactly this content:
```python
"""One host cannot add the same calendar link twice (task 0026)."""
from __future__ import annotations

from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app import auth, db, feed_url, icalsync
from app.main import app
from tests.conftest import login_as

URL = "https://www.airbnb.com/calendar/ical/123.ics?s=abc"
USERS = ("dupfeed-a", "dupfeed-b")


@pytest.fixture
def homes(monkeypatch):
    db.init_db()
    _cleanup()
    # No network in tests: accept the link as typed and import nothing.
    monkeypatch.setattr(feed_url, "validate_calendar_url", lambda url: url.strip())
    monkeypatch.setattr(icalsync, "sync_all", lambda apartment_id: {"created": 0, "errors": 0})
    out = {}
    now = db.utcnow()
    for username in USERS:
        owner = auth.create_account(f"{username}@example.test", username, username=username)
        entity = db.insert(
            "legal_entity",
            {"name": username, "seat": "Praha", "created_at": now, "owner_user_id": owner},
        )
        flats = []
        for n, name in enumerate(("Flat A", "Flat B")):
            flats.append(
                db.insert(
                    "apartment",
                    {
                        "legal_entity_id": entity,
                        "owner_user_id": owner,
                        "internal_name": name,
                        "permalink_token": f"{username}-tok-{n}",
                        "automation_mode": "manual",
                        "default_purpose": "10",
                        "active": 1,
                        "created_at": now,
                    },
                )
            )
        out[username] = flats
    yield out
    _cleanup()


def _cleanup():
    for username in USERS:
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (username,)):
            oid = row["id"]
            for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
                db.execute("DELETE FROM ical_feed WHERE apartment_id = ?", (apt["id"],))
                db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _add(username, apartment_id, url=URL):
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    return client.post(
        f"/apartments/{apartment_id}/feeds",
        data={"url": url, "label": "Airbnb", "own_name": "Airbnb"},
        follow_redirects=False,
    )


def _count(apartment_id):
    return len(db.query("SELECT id FROM ical_feed WHERE apartment_id = ?", (apartment_id,)))


def test_the_same_link_on_a_second_property_of_the_same_host_is_refused(homes):
    flat_a, flat_b = homes["dupfeed-a"]
    assert _add("dupfeed-a", flat_a).status_code == 303
    response = _add("dupfeed-a", flat_b)
    assert response.status_code == 303
    assert "already added to Flat A" in unquote(response.headers["location"])
    assert _count(flat_a) == 1
    assert _count(flat_b) == 0


def test_the_same_link_twice_on_one_property_is_refused(homes):
    flat_a, _ = homes["dupfeed-a"]
    _add("dupfeed-a", flat_a)
    response = _add("dupfeed-a", flat_a)
    assert "already added to Flat A" in unquote(response.headers["location"])
    assert _count(flat_a) == 1


def test_another_host_may_use_the_same_link(homes):
    _add("dupfeed-a", homes["dupfeed-a"][0])
    other = homes["dupfeed-b"][0]
    response = _add("dupfeed-b", other)
    assert "already added" not in unquote(response.headers["location"])
    assert _count(other) == 1


def test_a_different_link_on_the_second_property_is_fine(homes):
    flat_a, flat_b = homes["dupfeed-a"]
    _add("dupfeed-a", flat_a)
    response = _add("dupfeed-a", flat_b, url=URL + "-other")
    assert "already added" not in unquote(response.headers["location"])
    assert _count(flat_b) == 1
```
5. In `docs/context/known-issues.md` delete the one line that starts with `| K-F20 |`.
6. Run the §6 commands in order.

## 5. Do not touch

`icalsync.py`, `feed_url.py`, `demo.py`, migrations, templates. Existing calendar links already saved twice are **not** removed or changed (owner decision: block new ones only).

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_feed_no_duplicate_per_user.py -q` → `4 passed`.
- `.venv/bin/python -m pytest tests/test_endtoend.py -q` → 0 failed.
- `.venv/bin/python -m pytest tests -q` → 0 failed apart from the four DNS tests listed in 0023 §2.

From the repo root: `python3 scripts/context_lint.py` → last line `context lint: OK`.

## 7. Acceptance

- [ ] `4 passed` for the new file.
- [ ] `grep -c '"flash.error.feed_duplicate"' App/app/host_i18n.py` prints `2`.
- [ ] `grep -c 'K-F20' docs/context/known-issues.md` prints `0`.
- [ ] `git diff --stat main` lists only §3 files.
- [ ] `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found as stated; a test fails twice after re-reading your edit against §4; an existing test fails; a file outside §3 needs a change; a new dependency seems needed; a step is unclear; you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0026-report.md` (1,500 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`admin.py`: the check runs **after** URL validation and **before** `db.insert`; the query is limited to this owner (`null_safe_eq`), never all users.

## Owner steps

1. After merge and deploy, nothing else is needed. A link that differs in any character (for example a newly exported Airbnb link) counts as a different link.
