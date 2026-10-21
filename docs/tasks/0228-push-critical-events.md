# 0228: Wire the four critical alerts

Status: review
Depends on: 0225 | Branch: claude/project-thread-w35ftw
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Queue a push next to the existing e-mail for exactly four events: UbyPort did not accept a report, a police deadline is at risk, a stay's door code is missing, and a cancelled stay had registered guests. Nothing else.

## 2. Context

- Owner decision 2026-10-21: critical alerts only, never "nice to know". `push.notify` refuses any kind outside `push.KINDS`.
- A transport error (UbyPort unreachable, retried automatically) is **not** pushed; the deadline watch pushes if it lasts.
- Each helper never raises: a push that cannot be queued must never be the reason a filing, a calendar sync or a door-code run fails (same contract as `mail_notify.submission_problem`).
- One push per event per device: keys are the stay id, or the property id plus the local day for filing problems (the same rule as that e-mail).
- Click targets are app paths only: `/reservations/<id>`, or `/reservations` when several stays are affected.
- `push.notify(owner_user_id, kind, *, key, url, params)` from 0225 does the queueing.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/push.py` | edit | four helpers |
| `App/app/reporting.py` | edit | filing problem hook |
| `App/app/filing_watchdog.py` | edit | deadline hook |
| `App/app/door_codes.py` | edit | door code hook |
| `App/app/icalsync.py` | edit | cancelled-with-guests hook |
| `App/tests/test_push_events.py` | new | tests |

No other file may change.

## 4. Steps

**Step 1.** `App/app/push.py`. Anchor: `# --- retention ---`. Insert BEFORE that line:

```python
# --- the four urgent events (brief 0228) ----------------------------------------
# Each runs next to the e-mail for the same event and never raises: an alert
# that cannot be queued must never be the reason a filing, a calendar sync or a
# door-code run fails.


def _day(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except ValueError:
        return str(value or "")


def filing_problem(apartment: Any, submission_id: Optional[int]) -> int:
    """UbyPort did not accept a report. One push per property and local day."""
    try:
        from . import deadlines, mail_notify

        stays = mail_notify.stays_for_submission(submission_id)
        return notify(
            apartment["owner_user_id"],
            "filing_problem",
            key=f"{apartment['id']}:{deadlines.local_now().date().isoformat()}",
            url=f"/reservations/{stays[0]['id']}" if len(stays) == 1 else "/reservations",
            params={"property": apartment["internal_name"] or ""},
        )
    except Exception:
        log.exception("push_filing_problem_failed submission_id=%s", submission_id)
        return 0


def deadline_at_risk(stay: Dict[str, Any]) -> int:
    """A stay is about to miss the police deadline (filing_watchdog). Once per stay."""
    try:
        deadline = stay["deadline"]
        return notify(
            stay["owner_user_id"],
            "deadline_at_risk",
            key=str(stay["reservation_id"]),
            url=f"/reservations/{stay['reservation_id']}",
            params={
                "property": stay["property"],
                "date": stay["arrival"].strftime("%d.%m.%Y"),
                "deadline": f"{deadline.strftime('%d.%m.%Y')} {deadline.strftime('%H:%M')}",
            },
        )
    except Exception:
        log.exception("push_deadline_failed reservation_id=%s", stay.get("reservation_id"))
        return 0


def door_code_missing(reservation_id: int) -> int:
    """Registered guests still have no door code. Once per stay."""
    try:
        row = db.query_one(
            "SELECT r.id, r.date_from, a.owner_user_id, a.internal_name "
            "FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
            (reservation_id,),
        )
        if not row:
            return 0
        return notify(
            row["owner_user_id"],
            "door_code",
            key=str(row["id"]),
            url=f"/reservations/{row['id']}",
            params={"property": row["internal_name"] or "", "date": _day(row["date_from"])},
        )
    except Exception:
        log.exception("push_door_code_failed reservation_id=%s", reservation_id)
        return 0


def cancelled_with_guests(apartment_id: int, reservation_id: int) -> int:
    """The calendar cancelled a stay whose guests had registered. Once per stay."""
    try:
        row = db.query_one(
            "SELECT r.id, r.date_from, a.owner_user_id, a.internal_name "
            "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
            "WHERE r.id = ? AND a.id = ?",
            (reservation_id, apartment_id),
        )
        if not row:
            return 0
        return notify(
            row["owner_user_id"],
            "cancelled_with_guests",
            key=str(row["id"]),
            url=f"/reservations/{row['id']}",
            params={"property": row["internal_name"] or "", "date": _day(row["date_from"])},
        )
    except Exception:
        log.exception("push_cancelled_failed reservation_id=%s", reservation_id)
        return 0


```

Run: `cd App && .venv/bin/python -c "import app.push" 2>&1 | tail -3`. Expected: no error.

**Step 2.** `App/app/reporting.py`. In the import line `from . import access, alerts, codelists, config, db, deadlines, mail_notify, passport_photos, validation` add `push, ` before `validation` (so: `..., passport_photos, push, validation`). Then anchor (the rejected branch, NOT the two `transport=True` calls):

```python
        mail_notify.submission_problem(
            apartment,
            submission_id,
            state=state,
            reason=" ".join(detail_bits),
        )
```

Insert after it:

```python
        # Brief 0228: the same news on the host's phone, once per property a day.
        push.filing_problem(apartment, submission_id)
```

Check with `grep -n "push.filing_problem" App/app/reporting.py`: exactly one line.

**Step 3.** `App/app/filing_watchdog.py`. In `from . import config, db, deadlines, mail, mail_notify, reporting, validation` add `push, ` before `reporting`. Then anchor inside `notify_hosts`:

```python
        if stay.get("mailed_at"):
            continue
        try:
```

Replace with:

```python
        if stay.get("mailed_at"):
            continue
        # Brief 0228: also on the host's phone. Queued once per stay, even when
        # there is no address to mail and this loop sees the stay again.
        push.deadline_at_risk(stay)
        try:
```

**Step 4.** `App/app/door_codes.py`. In `from . import alerts, config, db, deadlines, mail, mail_notify, ttlock` add `push, ` before `ttlock`. Then anchor:

```python
        mail_notify.door_code_delayed_notice(int(row["reservation_id"]), reason)
```

Insert after it (same indentation):

```python
        push.door_code_missing(int(row["reservation_id"]))
```

**Step 5.** `App/app/icalsync.py`. In `from . import alerts, config, db, deadlines, host_i18n, mail_notify, reporting` add `, push` after `mail_notify` (so: `..., mail_notify, push, reporting`). Then anchor:

```python
    mail_notify.cancelled_with_guests(apartment_id, reservation["id"], variant)
```

Insert after it:

```python
    push.cancelled_with_guests(apartment_id, reservation["id"])
```

Run: `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -3`. Expected: no error.

**Step 6.** Create `App/tests/test_push_events.py` with exactly:

```python
"""Brief 0228: exactly four events reach the host's phone, once each."""
from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path

import pytest

from app import auth, config, db, push
from tests.test_push import Browser

APP = Path(__file__).resolve().parent.parent / "app"


@pytest.fixture(autouse=True)
def push_on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "WEB_PUSH", True)
    yield


@pytest.fixture
def stay():
    username = f"pe{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Push Events", role="host", username=username)
    apartment_id = db.insert("apartment", {
        "internal_name": "Byt Vinohrady", "owner_user_id": owner,
        "permalink_token": f"pe{secrets.token_hex(5)}", "active": 1, "created_at": db.utcnow(),
    })
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "date_from": "2026-10-24", "date_to": "2026-10-26",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    push.save_subscription(owner, Browser().subscription(), lang="en", device="iPhone")
    yield {"owner": owner, "apartment_id": apartment_id, "reservation_id": reservation_id}
    db.execute("DELETE FROM push_outbox WHERE user_account_id = ?", (owner,))
    db.execute("DELETE FROM push_subscription WHERE user_account_id = ?", (owner,))


def _queued(owner):
    return db.query(
        "SELECT kind, url, params FROM push_outbox WHERE user_account_id = ? ORDER BY id", (owner,)
    )


def test_a_door_code_problem_is_pushed_once_per_stay(stay):
    assert push.door_code_missing(stay["reservation_id"]) == 1
    assert push.door_code_missing(stay["reservation_id"]) == 0
    [row] = _queued(stay["owner"])
    assert row["kind"] == "door_code" and row["url"] == f"/reservations/{stay['reservation_id']}"
    assert "24.10.2026" in row["params"] and "Byt Vinohrady" in row["params"]


def test_a_cancelled_stay_with_guests_is_pushed_once(stay):
    assert push.cancelled_with_guests(stay["apartment_id"], stay["reservation_id"]) == 1
    assert push.cancelled_with_guests(stay["apartment_id"], stay["reservation_id"]) == 0
    assert _queued(stay["owner"])[0]["kind"] == "cancelled_with_guests"


def test_a_deadline_at_risk_is_pushed_once_with_the_deadline(stay):
    record = {
        "owner_user_id": stay["owner"], "reservation_id": stay["reservation_id"],
        "property": "Byt Vinohrady", "arrival": datetime(2026, 10, 24),
        "deadline": datetime(2026, 10, 27, 23, 59),
    }
    assert push.deadline_at_risk(record) == 1
    assert push.deadline_at_risk(record) == 0
    [row] = _queued(stay["owner"])
    assert "27.10.2026 23:59" in row["params"]


def test_a_filing_problem_is_pushed_once_per_property_and_day(stay):
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (stay["apartment_id"],))
    assert push.filing_problem(apartment, None) == 1
    assert push.filing_problem(apartment, None) == 0
    [row] = _queued(stay["owner"])
    assert row["kind"] == "filing_problem" and row["url"] == "/reservations"


def test_the_helpers_never_raise(stay):
    assert push.door_code_missing(-1) == 0
    assert push.deadline_at_risk({"reservation_id": 1}) == 0
    assert push.filing_problem(None, None) == 0


def test_each_event_is_wired_exactly_once_next_to_its_e_mail():
    sources = {
        "reporting.py": "push.filing_problem(",
        "filing_watchdog.py": "push.deadline_at_risk(",
        "door_codes.py": "push.door_code_missing(",
        "icalsync.py": "push.cancelled_with_guests(",
    }
    for name, call in sources.items():
        assert (APP / name).read_text(encoding="utf-8").count(call) == 1, name
    # Nothing else in the app queues a push.
    callers = [
        path.name for path in APP.rglob("*.py")
        if "push.notify(" in path.read_text(encoding="utf-8") and path.name != "push.py"
    ]
    assert callers == []
```

Run: `cd App && .venv/bin/python -m pytest tests/test_push_events.py -q --tb=short -x 2>&1 | tail -15`. Expected: all pass. If the `apartment` or `reservation` insert needs another NOT NULL column, add only that column to the fixture and say so in the report.

## 5. Do not touch

`mail_notify.py`, `mail.py`, the two `transport=True` calls in `reporting.py`, `push.KINDS`. Hard rules: UbyPort filing correctness first (the hook is after the e-mail call and cannot raise), no new dependency.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_push_events.py tests/test_push.py -q --tb=short -x`
2. `.venv/bin/python -m pytest tests/test_filing_watchdog.py tests/test_submission_*.py tests/test_ubyport_*.py tests/test_stale_submission.py -q --tb=short -x`
3. `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_icalsync.py tests/test_feed_*.py -q --tb=short -x`
4. From the repo root: `python3 scripts/context_lint.py`

## 7. Acceptance

- [ ] §6 passes.
- [ ] `git diff --stat` lists only §3 files.

## 8. Stop and ask

As in TEMPLATE §8. Also stop if any filing, door-code or calendar test fails after the hook (report the last 30 lines; do not change those tests).

## 9. Report

`docs/tasks/0228-report.md` per TEMPLATE §9; set `Status: review`.

## Risk list (for the reviewer)

`App/app/push.py` helpers, the four one-line hooks.

## Owner steps

None.
