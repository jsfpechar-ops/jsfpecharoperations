# 0025: One guest email: the registration confirmation carries the door code

Status: todo
Depends on: 0024 merged | Base commit: `main` after 0024 | Branch: task/0025-confirmation-with-door-code
Executor: Claude Haiku 5.5, effort high (or Cursor composer, Kimi, GLM) | Fits one session

## 1. Objective

Today a guest with a door code gets two emails: the registration confirmation, then the door-code email. From now on the confirmation waits for the code (normally seconds, at most about 1 minute) and carries it. If no code comes, the confirmation goes out without it, and 0024's hand-over email tells the host and support.

## 2. Context

Owner decision 2026-10-09. Rules: 1 (UbyPort first: the police submission must stay **before** any door-code work in the guest request), 2, 4, 7.

How it works after this brief:
1. Guest finishes the form → `reporting.submit_stay_if_complete` (unchanged, first) → `door_codes.on_registration_complete` (first TTLock try) → `claim.maybe_notify_completion`.
2. Code made → confirmation with the code. Still trying → confirmation held. No code coming (no lock, codes off, failed) → confirmation without code.
3. Held confirmations are released by: the retry 1 min later succeeding (with code) or failing (0024 hand-over, then without code); and a safety sweep that sends any confirmation still held 5 min after registration, without code.
4. A code made **after** the confirmation went (a moved stay, a budget delay) still gets its own door-code email, as today.

Anchors, each verbatim exactly once:

B1 `App/app/routes/guest.py`:
```python
    await run_in_threadpool(
        lambda: claim.maybe_notify_completion(
            db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,)),
            apartment,
        )
    )
    await run_in_threadpool(reporting.submit_stay_if_complete, apartment["id"], reservation_id)
    await run_in_threadpool(door_codes.on_registration_complete, reservation_id)
```
B2 `App/app/claim.py`:
```python
def maybe_notify_completion(reservation, apartment) -> None:
```
B3 `App/app/claim.py` (same function):
```python
    lang = claim["lang"] or "en"
    content = _guest_mail_content(
        "completion",
        apartment,
        reservation,
        lang=lang,
        stay_url=_stay_link(apartment, reservation),
    )
    payload = mail_notify.guest_payload(apartment, content, lang)
```
B4 `App/app/claim.py` (same function):
```python
        (db.utcnow(), db.utcnow(), reservation["id"]),
    )
    mail.drain(limit=4)
```
B5 `App/app/claim.py`, in `_guest_mail_content`: the signature line `    stay_complete: bool = False,` followed by `) -> Dict[str, str]:`, and the call
```python
            return mail_notify.build_completion(
                lang=lang,
                property_name=property_name,
                dates=dates,
                stay_url=stay_url or "",
                host=host,
            )
```
B6 `App/app/mail_notify.py`, `build_completion` signature line `    host: Optional[Dict[str, str]] = None,\n) -> Dict[str, str]:\n    """The receipt.` and the line `    text_lines = [intro]`.
B7 `App/app/door_codes.py`, `_send_code_mail`:
```python
    if not claim or not (claim["email"] or "").strip():
        return
```
B8 `App/app/door_codes.py`, in `issue`: the line `            mail_notify.door_code_notice(door_code_id, "failed")` (exactly **twice**).
B9 `App/app/door_codes.py`, in `reconcile`: `    _phase("budget_alerts", _budget_alerts)`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/guest.py` | edit | order of the three calls |
| `App/app/claim.py` | edit | hold, code in the confirmation, `force` |
| `App/app/mail_notify.py` | edit | door-code blocks in `build_completion` |
| `App/app/door_codes.py` | edit | 2 helpers, release on failure, safety sweep |
| `App/tests/test_confirmation_with_door_code.py` | create | 8 tests (full code in step 11) |
| `docs/tasks/0025-report.md` | create | report |

No other file may change (if an existing test fails because the order changed, STOP, §8).

## 4. Steps

1. B1 → same three calls in this order: `submit_stay_if_complete`, `on_registration_complete`, `maybe_notify_completion` (keep each call exactly as written).
2. `door_codes.py`, add after `send_code_mail`:
```python
HOLD_CONFIRMATION_MINUTES = 5


def completion_door_code(reservation: dict, apartment: dict) -> Tuple[str, Optional[dict], Optional[dict]]:
    """What the registration confirmation does about the door code.

    ("hold", None, None): a code is still being made, wait for it.
    ("with", row, fields): the code exists and was not sent; put it in.
    ("without", None, None): no code is coming.
    """
    if not config.DOOR_CODES_ENABLED:
        return "without", None, None
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (reservation["id"],))
    if not row:
        return "without", None, None
    if row["state"] in (PENDING, ISSUING, RETRYING):
        return "hold", None, None
    if row["state"] == ISSUED and row["pin_enc"] and not row["notified_at"]:
        shown = view(reservation, apartment)
        if shown and shown.get("state") == "issued":
            return "with", row, {
                "checkin": shown["checkin"],
                "checkout": shown["checkout"],
                "first_use_by": shown["first_use_by"],
            }
    return "without", None, None


def _release_confirmation(reservation_id: int, *, force: bool = False) -> None:
    """Send a held registration confirmation (lazy import: claim imports us)."""
    from . import claim

    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    if not reservation:
        return
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
    if apartment:
        claim.maybe_notify_completion(reservation, apartment, force=force)


def _release_held_confirmations() -> int:
    """Safety net: no confirmation waits longer than HOLD_CONFIRMATION_MINUTES."""
    now = _now()
    cutoff = _iso(now - timedelta(minutes=HOLD_CONFIRMATION_MINUTES))
    # Only stays this brief can have held: they have a door_code row and
    # registered in the last day. Older stays must never get a late confirmation.
    oldest = _iso(now - timedelta(hours=24))
    rows = db.query(
        "SELECT r.id FROM reservation r JOIN reservation_claim c ON c.reservation_id = r.id "
        "JOIN door_code dc ON dc.reservation_id = r.id "
        "WHERE c.state = 'claimed' AND c.email IS NOT NULL AND c.email <> '' "
        "AND c.completion_notified_at IS NULL AND r.status = 'active' "
        "AND r.registration_completed_at < ? AND r.registration_completed_at > ? LIMIT ?",
        (cutoff, oldest, BATCH),
    )
    for row in rows:
        log.error(
            "DOOR_CODE_PROBLEM stage=confirmation_without_code reservation=%s", row["id"]
        )
        _release_confirmation(int(row["id"]), force=True)
    return len(rows)
```
3. B7: after it insert
```python
    if not claim["completion_notified_at"]:
        # The confirmation has not gone yet: the code travels inside it.
        _release_confirmation(int(reservation["id"]))
        again = db.query_one("SELECT notified_at FROM door_code WHERE id = ?", (door_code_id,))
        if again and again["notified_at"]:
            return
```
4. B8: after **each** of the two lines insert (same indent) `            _release_confirmation(int(reservation["id"]))`.
5. B9: after it insert `    _phase("held_confirmations", _release_held_confirmations)`.
6. B2 → `def maybe_notify_completion(reservation, apartment, *, force: bool = False) -> None:`.
7. B3 → 
```python
    lang = claim["lang"] or "en"
    from . import door_codes

    mode, code_row, code_fields = door_codes.completion_door_code(reservation, apartment)
    if mode == "hold" and not force:
        return
    content = _guest_mail_content(
        "completion",
        apartment,
        reservation,
        lang=lang,
        stay_url=_stay_link(apartment, reservation),
        door_code=code_fields,
    )
    payload = mail_notify.guest_payload(apartment, content, lang)
    if code_row is not None:
        payload[mail.DOOR_CODE_KEY] = code_row["pin_enc"]
```
8. B4 → 
```python
        (db.utcnow(), db.utcnow(), reservation["id"]),
    )
    if code_row is not None:
        db.execute(
            "UPDATE door_code SET notified_at = ?, updated_at = ? WHERE id = ?",
            (db.utcnow(), db.utcnow(), code_row["id"]),
        )
    mail.drain(limit=4)
```
9. B5: add `    door_code: Optional[Dict[str, str]] = None,` after `stay_complete: bool = False,`; add `door_code=door_code,` after `host=host,` in the `build_completion` call.
10. B6: add `    door_code: Optional[Dict[str, str]] = None,` before `) -> Dict[str, str]:`; after `    text_lines = [intro]` insert
```python
    if door_code:
        code_title = _guest_text(lang, "door_code_title")
        times = _guest_text(
            lang, "door_code_times", checkin=door_code["checkin"], checkout=door_code["checkout"]
        )
        first_use = _guest_text(lang, "door_code_first_use", deadline=door_code["first_use_by"])
        blocks.extend([
            _block_heading(code_title),
            _block_paragraph(mail.DOOR_CODE_MARKER, size=22),
            _block_paragraph(times),
            _block_paragraph(first_use),
        ])
        text_lines.extend(["", code_title, mail.DOOR_CODE_MARKER, times, first_use])
```
11. Create `App/tests/test_confirmation_with_door_code.py` with exactly this content:
```python
"""The registration confirmation carries the door code (task 0025)."""
from __future__ import annotations

import json

import pytest

from app import claim, config, db, door_codes, mail, ttlock
# _env is the autouse fixture of that file; importing it here applies it here too.
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401

PIN = "4821937"


@pytest.fixture(autouse=True)
def _claims(_env, monkeypatch):
    monkeypatch.setattr(
        claim.reporting,
        "reservation_progress",
        lambda _r: {"expected": 1, "filled": 1, "incomplete": False, "status": "complete"},
    )
    yield
    db.execute(
        "DELETE FROM reservation_claim WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE uid LIKE 'dc-safe-%')"
    )


def _claim(stay):
    now = db.utcnow()
    db.execute(
        "INSERT INTO reservation_claim (reservation_id, state, email, lang, created_at, updated_at) "
        "VALUES (?, 'claimed', 'guest@example.test', 'en', ?, ?)",
        (stay, now, now),
    )


def _guest_registers(stay):
    """What the guest form does once everyone is in (the order from step 1)."""
    _claim(stay)
    door_codes.on_registration_complete(stay)
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
    claim.maybe_notify_completion(reservation, apartment)


def _guest_mails(stay):
    return db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND kind IN ('completion', 'door_code') "
        "ORDER BY id",
        (stay,),
    )


def _text(row):
    return mail.delivery_body(json.loads(row["payload"]))


def _works(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: (PIN, "99"))


def _refuses(monkeypatch, kind="transient"):
    def refused(*args, **kwargs):
        raise ttlock.TTLockError("refused", code=-1026, kind=kind)

    monkeypatch.setattr(ttlock, "create_period_code", refused)


def _due_now(stay):
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))


def test_a_code_made_at_once_rides_in_the_confirmation(monkeypatch):
    _works(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    mails = _guest_mails(stay)
    assert [m["kind"] for m in mails] == ["completion"]
    assert PIN in _text(mails[0])
    assert "If you have not used it by" in _text(mails[0])
    row = db.query_one("SELECT notified_at FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["notified_at"]


def test_a_held_confirmation_goes_with_the_code_after_the_retry(monkeypatch):
    _refuses(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    assert _guest_mails(stay) == []
    _works(monkeypatch)
    _due_now(stay)
    door_codes.reconcile()
    mails = _guest_mails(stay)
    assert [m["kind"] for m in mails] == ["completion"]
    assert PIN in _text(mails[0])


def test_two_refusals_send_the_confirmation_without_a_code_and_tell_the_host(monkeypatch):
    _refuses(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    _due_now(stay)
    door_codes.reconcile()
    mails = _guest_mails(stay)
    assert [m["kind"] for m in mails] == ["completion"]
    assert "If you have not used it by" not in _text(mails[0])
    assert db.query(
        "SELECT id FROM email_outbox WHERE reservation_id = ? AND kind = 'door_code_notice'",
        (stay,),
    )


def test_a_property_without_a_lock_sends_the_confirmation_at_once():
    _, apartment, stay = _stay(registered_minutes_ago=0)
    db.execute("UPDATE apartment SET lock_provider = NULL, lock_id = NULL WHERE id = ?", (apartment,))
    _guest_registers(stay)
    assert [m["kind"] for m in _guest_mails(stay)] == ["completion"]


def test_codes_switched_off_send_the_confirmation_at_once(monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    assert [m["kind"] for m in _guest_mails(stay)] == ["completion"]


def test_a_confirmation_never_waits_more_than_five_minutes(monkeypatch):
    lines = []
    monkeypatch.setattr(door_codes.log, "error", lambda msg, *args, **kw: lines.append(msg % args))
    _refuses(monkeypatch, kind="budget")  # budget: TTLock is asked again only in 60 min
    _, apartment, stay = _stay(registered_minutes_ago=6)
    _guest_registers(stay)
    assert _guest_mails(stay) == []
    door_codes.reconcile()
    mails = _guest_mails(stay)
    assert [m["kind"] for m in mails] == ["completion"]
    assert any(l.startswith("DOOR_CODE_PROBLEM stage=confirmation_without_code") for l in lines), lines


def test_an_old_stay_never_gets_a_late_confirmation(monkeypatch):
    _refuses(monkeypatch, kind="budget")
    _, apartment, stay = _stay(registered_minutes_ago=2 * 24 * 60)
    _claim(stay)
    door_codes.ensure_row(stay)
    door_codes.reconcile()
    assert _guest_mails(stay) == []


def test_a_code_made_after_the_confirmation_gets_its_own_mail(monkeypatch):
    _works(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    db.execute("UPDATE door_code SET notified_at = NULL WHERE reservation_id = ?", (stay,))
    row = db.query_one("SELECT id FROM door_code WHERE reservation_id = ?", (stay,))
    door_codes.send_code_mail(int(row["id"]))
    assert [m["kind"] for m in _guest_mails(stay)] == ["completion", "door_code"]
```
12. Run the §6 commands in order.

## 5. Do not touch

`reporting.py`, `ubyport/`, `mail.py`, `ttlock.py`, templates, i18n files, migrations. Rule 1: `submit_stay_if_complete` stays the first of the three calls.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_confirmation_with_door_code.py tests/test_door_code_handover.py tests/test_door_codes_safeguards.py tests/test_guest_mail.py -q` → 0 failed.
- `.venv/bin/python -m pytest tests -q` → 0 failed apart from the four DNS tests listed in 0023 §2.

From the repo root: `python3 scripts/context_lint.py` → `context lint: OK`.

## 7. Acceptance

- [ ] §6 passes as stated.
- [ ] In `guest.py`, `submit_stay_if_complete` comes before `on_registration_complete`, which comes before `maybe_notify_completion`.
- [ ] `grep -c 'DOOR_CODE_PROBLEM' App/app/door_codes.py` prints `4`.
- [ ] `git diff --stat main` lists only §3 files.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found as stated; an existing test fails because of the new order or the held confirmation; a circular-import error appears; a test fails twice; a file outside §3 needs a change; a step is unclear; you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0025-report.md` (1,500 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`guest.py` order; `claim.maybe_notify_completion` (hold only when `mode == "hold"` and not forced; `notified_at` set only with the code); `_send_code_mail` fall-through; the safety sweep query (Postgres-portable, `LIMIT ?`; must only match stays with a `door_code` row registered in the last 24 h, so old stays never get a late confirmation).

## Owner steps

1. On staging, with TTLock keys added back **and** `UBYHOST_STAGING_NO_LOGIN` removed: register a test stay on the property with your lock. Expect one email with the confirmation and the code.
2. Render → service → **Logs** → search `DOOR_CODE_PROBLEM`: nothing should appear for that stay.
