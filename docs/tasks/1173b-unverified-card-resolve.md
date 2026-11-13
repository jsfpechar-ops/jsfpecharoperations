# 1173b: the "door code not confirmed" card closes when it no longer applies

Status: todo
Depends on: 1173 | Base commit: tip of task/1173-issue-queue-starvation (or main after 1173 is merged) | Branch: task/1173b-unverified-card-resolve
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 20 calls used)

## 1. Objective

The warning card `door_code_pin_unverified:<reservation>` (raised in `_tell_host_unverified`, brief 1168) is never resolved: it stays on the host's dashboard after the stay is revoked, expired, given a new code or moved. Resolve it in each of those cases. Also renumber two test docstrings (review cosmetics).

## 2. Context

`alerts.resolve(dedupe_key)` (App/app/alerts.py) sets `resolved_at` on the open alert with that key. Cases and where each is done:

| Case | Where | How |
|---|---|---|
| Successful issue or re-issue (`_reissue_lost_pin` calls `issue()`) | `issue()`, next to the existing `door_code_failed`/`door_code_delayed` resolves | `alerts.resolve(f"door_code_pin_unverified:{reservation['id']}")` |
| Successful date move (a new code replaces the unconfirmed one) | `_handle_moves`, right after the `door_code_replaced` audit | same call with `row['reservation_id']` |
| Revoke, expiry, deleted row | new `_resolve_unverified_cards()`, called in `reconcile` after the `issued -> expired` update | one `UPDATE alert ... WHERE kind = 'door_code_pin_unverified' AND resolved_at IS NULL AND NOT EXISTS (a door_code row of that reservation in state issued)`. A sweep, because the bulk expiry update does not know the reservation ids. A cancelled stay moves `issued -> revoke_pending` on the next tick, so the card closes then (the stay is gone, the card is moot). |

The card is raised only after `_keep_issued` made the row `issued` again, so the sweep never closes a card that was just raised. `_resolve_unverified_cards` also runs on rows `_reissue_lost_pin` just put to `pending`; `issue()` resolves in the same call when it succeeds.

**`door_code_reissued` card: left as it is.** It is an `info` card about a past event (a lost code was replaced), not about a state that ends, and the host can dismiss it. No change.

Behaviour is the same on SQLite and PostgreSQL (plain `UPDATE ... NOT EXISTS`); the bites below are shown on both anyway.

Anchors: each `sub(old, new)` asserts `old` occurs exactly once; if not, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | two `alerts.resolve` lines, `_resolve_unverified_cards`, one call in `reconcile` |
| App/tests/test_door_code_unverified_card.py | create | 4 tests: move, re-issue, cancel, expiry |
| App/tests/test_admin_operations.py | edit | docstring `Task 1170` -> `Task 1172` |
| App/tests/test_door_code_host_notices.py | edit | docstring `1166` -> `1168` |
| docs/tasks/1173b-report.md | create | report |

No other file may change. (`test_null_order_portability.py` was renumbered in 1173. If `grep -rn '1157' App/tests/test_door_code*.py App/tests/test_admin_operations.py` finds a docstring that names a brief by its old number, list it in the report; do not change it.)

## 4. Steps

Commands run from the repo root unless `cd App`. End the commit message with the attribution lines your session gives you. Never use `git rebase`, `git commit --amend`, `git stash` or `git commit -a`; `git add` only the named files.

1. Preflight: 1173 is in the tree. Expect `1`, an empty status, and the new branch.
```bash
grep -c 'RELEASE_RETRY_MINUTES = ' App/app/door_codes.py; git status --short | tail -5; git checkout -b task/1173b-unverified-card-resolve | tail -3
```
2. Edit `App/app/door_codes.py` (four anchors). Expect `ok App/app/door_codes.py`.
```bash
python3 - <<'PY'
p = "App/app/door_codes.py"
s = open(p, encoding="utf-8").read()

def sub(old, new):
    global s
    assert s.count(old) == 1, ("anchor not found exactly once", old[:70])
    s = s.replace(old, new)

sub(
r'''        alerts.resolve(f"door_code_delayed:{reservation['id']}")
        db.audit(
            "door_code_issued",''',
r'''        alerts.resolve(f"door_code_delayed:{reservation['id']}")
        alerts.resolve(f"door_code_pin_unverified:{reservation['id']}")
        db.audit(
            "door_code_issued",''',
)

sub(
r'''                owner_user_id=row["owner_user_id"],
            )
            send_code_mail(int(row["id"]))
            if old_code_id and old_code_id != code_id:''',
r'''                owner_user_id=row["owner_user_id"],
            )
            alerts.resolve(f"door_code_pin_unverified:{row['reservation_id']}")
            send_code_mail(int(row["id"]))
            if old_code_id and old_code_id != code_id:''',
)

sub(
r'''def reconcile() -> Dict[str, int]:''',
r'''def _resolve_unverified_cards() -> None:
    """Close the "code not confirmed" card of a stay whose code is no longer issued (1173b).

    Covers revoke, expiry and a deleted row. A new code (issue, move) resolves the card where it is made.
    """
    db.execute(
        "UPDATE alert SET resolved_at = ? WHERE kind = ? AND resolved_at IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM door_code dc "
        "WHERE dc.reservation_id = alert.reservation_id AND dc.state = ?)",
        (db.utcnow(), "door_code_pin_unverified", ISSUED),
    )


def reconcile() -> Dict[str, int]:''',
)

sub(
r'''    counts["expired"] += int(expired or 0)
''',
r'''    counts["expired"] += int(expired or 0)
    _phase("unverified_cards", _resolve_unverified_cards)
''',
)

open(p, "w", encoding="utf-8").write(s)
print("ok", p)
PY
```
3. Create `App/tests/test_door_code_unverified_card.py`. Expect `written`.
```bash
cat > App/tests/test_door_code_unverified_card.py <<'EOF'
"""Task 1173b: the "door code not confirmed" card closes when its stay has a new code, is revoked or expires.

The card is raised by _tell_host_unverified (task 1168) with the key door_code_pin_unverified:<reservation>.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app import alerts, db, deadlines, door_codes, ttlock
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401
from tests.test_ttlock_lock_setup import _moved_stay

OLD = "2000-01-01T00:00:00+00:00"
CARD = "door_code_pin_unverified"


@pytest.fixture
def lock(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "code-1"))
    monkeypatch.setattr(door_codes, "send_code_mail", lambda row_id: None)


def _row(row_id: int):
    return db.query_one("SELECT * FROM door_code WHERE id = ?", (row_id,))


def _card(stay: int) -> None:
    apartment = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (stay,))["apartment_id"]
    alerts.raise_alert(
        "warning", CARD, "Door code could not be confirmed on the lock",
        dedupe_key=f"{CARD}:{stay}", apartment_id=apartment, reservation_id=stay,
    )


def _open(stay: int):
    return alerts.open_alert(f"{CARD}:{stay}")


def _issued_stay(monkeypatch):
    """A stay with an issued code on its own window (no move pending)."""
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("1111111", "c1"))
    _, _, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["state"] == door_codes.ISSUED
    return stay, int(row["id"])


def test_the_unconfirmed_card_closes_when_a_move_makes_a_new_code(monkeypatch):
    stay, _ = _moved_stay(monkeypatch)
    _card(stay)
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("2222222", "code-2"))
    door_codes.reconcile()
    assert _open(stay) is None


def test_the_unconfirmed_card_closes_when_a_lost_code_is_issued_again(monkeypatch, lock):
    stay, row_id = _issued_stay(monkeypatch)
    _card(stay)
    db.execute(
        "UPDATE door_code SET state = ?, pin_enc = NULL, provider_code_id = NULL, attempts = 0, "
        "next_attempt_at = NULL, last_error = 'pin_lost' WHERE id = ?",
        (door_codes.PENDING, row_id),
    )
    assert door_codes.issue(row_id, allow_gateway=True)
    assert _open(stay) is None


def test_the_unconfirmed_card_closes_when_the_stay_is_cancelled(monkeypatch):
    stay, _ = _issued_stay(monkeypatch)
    _card(stay)
    door_codes.reconcile()
    assert _open(stay) is not None  # the code is still issued: the card stays
    db.execute("UPDATE reservation SET status = 'cancelled' WHERE id = ?", (stay,))
    door_codes.reconcile()
    assert _open(stay) is None


def test_the_unconfirmed_card_closes_when_the_code_expires(monkeypatch):
    stay, row_id = _issued_stay(monkeypatch)
    _card(stay)
    today = deadlines.local_now().date()
    db.execute(  # the stay is over: no move is wanted, the code's window has ended
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=1)).isoformat(), stay),
    )
    db.execute("UPDATE door_code SET valid_to = ? WHERE id = ?", (OLD, row_id))
    door_codes.reconcile()
    assert _row(row_id)["state"] == door_codes.EXPIRED
    assert _open(stay) is None
EOF
echo written
```
4. Renumber the two docstrings. Expect two `ok` lines.
```bash
python3 - <<'PY'
p = "App/tests/test_admin_operations.py"
s = open(p, encoding="utf-8").read()

def sub(old, new):
    global s
    assert s.count(old) == 1, ("anchor not found exactly once", old[:70])
    s = s.replace(old, new)

sub(
r'''"""Task 1170: NULL sorts first''',
r'''"""Task 1172: NULL sorts first''',
)

open(p, "w", encoding="utf-8").write(s)
print("ok", p)
PY
python3 - <<'PY'
p = "App/tests/test_door_code_host_notices.py"
s = open(p, encoding="utf-8").read()

def sub(old, new):
    global s
    assert s.count(old) == 1, ("anchor not found exactly once", old[:70])
    s = s.replace(old, new)

sub(
r'''"""1166: three door-code problems''',
r'''"""1168: three door-code problems''',
)

open(p, "w", encoding="utf-8").write(s)
print("ok", p)
PY
```
5. New tests, SQLite. Expect `4 passed`.
```bash
cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_door_code_unverified_card.py -q --tb=short -x 2>&1 | tail -30
```
6. Test-map rows (door codes and TTLock, admin ops) plus state-machine tests, SQLite. Expect `524 passed, 2 skipped` (the 2 Playwright skips are fine).
```bash
cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_admin_operations.py tests/test_issue_queue_starvation.py tests/test_sm_*.py -q --tb=short -x 2>&1 | tail -30
```
7. Lint. Expect `All checks passed!`.
```bash
cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30
```
8. PostgreSQL: start if needed, apply the schema, run steps 5 and 6 on it. Expect `accepting connections`, no schema error, `4 passed`, then `377 passed, 3 skipped`. If PostgreSQL will not start, write "not run" in the report.
```bash
pg_isready -h localhost || sudo pg_ctlcluster 16 main start
cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python scripts/pg_schema.py apply --expect-database ubytest 2>&1 | tail -3
```
```bash
cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_unverified_card.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_admin_operations.py tests/test_issue_queue_starvation.py -q --tb=short -x 2>&1 | tail -30
```
9. Commit the change first (the bites are undone with `git checkout HEAD -- <file>`). Expect an empty status afterwards.
```bash
git add App/app/door_codes.py App/tests/test_door_code_unverified_card.py App/tests/test_admin_operations.py App/tests/test_door_code_host_notices.py
git commit -q -m '1173b: close the unverified-code card when it no longer applies' && git status --short | tail -5
```
Steps 10 to 12 are revert-bites. Each bite edits `door_codes.py` only, runs the card tests on SQLite and PostgreSQL, restores the file and proves the tree is clean. The bite must FAIL; a pass means the test guards nothing: STOP.
10. Bite C1. No resolve in `issue()`. From the repo root:
```bash
cd App && sed -i '/door_code_pin_unverified:{reservation/d' app/door_codes.py && git diff --stat | tail -3
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_door_code_unverified_card.py -q --tb=no 2>&1 | tail -8
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_unverified_card.py -q --tb=no 2>&1 | tail -8
cd .. && git checkout HEAD -- App/app/door_codes.py && git diff HEAD --stat | tail -3
```
   Expect: the `git diff --stat` after the `sed` shows `1 file changed`; both databases: `1 failed, 3 passed` (`..._when_a_lost_code_is_issued_again`); the last command prints nothing (empty `git diff HEAD --stat`). If it prints anything, run `git checkout HEAD -- App/app/door_codes.py` again and check again before going on.
11. Bite C2. No resolve after a move. From the repo root:
```bash
cd App && sed -i '/door_code_pin_unverified:{row/d' app/door_codes.py && git diff --stat | tail -3
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_door_code_unverified_card.py -q --tb=no 2>&1 | tail -8
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_unverified_card.py -q --tb=no 2>&1 | tail -8
cd .. && git checkout HEAD -- App/app/door_codes.py && git diff HEAD --stat | tail -3
```
   Expect: the `git diff --stat` after the `sed` shows `1 file changed`; both databases: `1 failed, 3 passed` (`..._when_a_move_makes_a_new_code`); the last command prints nothing (empty `git diff HEAD --stat`). If it prints anything, run `git checkout HEAD -- App/app/door_codes.py` again and check again before going on.
12. Bite C3. The sweep never matches. From the repo root:
```bash
cd App && sed -i 's/(db.utcnow(), "door_code_pin_unverified", ISSUED),/(db.utcnow(), "none", ISSUED),/' app/door_codes.py && git diff --stat | tail -3
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_door_code_unverified_card.py -q --tb=no 2>&1 | tail -8
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_unverified_card.py -q --tb=no 2>&1 | tail -8
cd .. && git checkout HEAD -- App/app/door_codes.py && git diff HEAD --stat | tail -3
```
   Expect: the `git diff --stat` after the `sed` shows `1 file changed`; both databases: `2 failed, 2 passed` (`..._when_the_stay_is_cancelled`, `..._when_the_code_expires`); the last command prints nothing (empty `git diff HEAD --stat`). If it prints anything, run `git checkout HEAD -- App/app/door_codes.py` again and check again before going on.
13. Context lint. Expect an OK line.
```bash
python3 scripts/context_lint.py | tail -3
```
14. Write `docs/tasks/1173b-report.md` (section 9), set `Status: review` here, then (before it `git diff HEAD --stat` must list only the two docs):
```bash
git diff HEAD --stat | tail -5
git add docs/tasks/1173b-report.md docs/tasks/1173b-unverified-card-resolve.md
git commit -q -m '1173b: report' && git status --short | tail -3
```

## 5. Do not touch

Anything outside section 3, including `_tell_host_unverified`, the `door_code_reissued` card, i18n files, schema. Hard rules 3, 4, 5 of AGENTS.md. Do not push, merge or deploy.

## 6. Commands

In the steps (SQLite: 5, 6; PostgreSQL: 8 and the bites; ruff 7; lint). No Go change, so no Go commands. Never the full suite.

## 7. Acceptance

- [ ] `git diff <base> --stat` lists exactly the four files of section 3 plus the two task docs.
- [ ] Steps 5, 6, 7 green on SQLite; step 8 green on PostgreSQL (or "not run").
- [ ] Each bite fails the named test(s) on both databases and `git diff HEAD --stat` was empty after each.
- [ ] Lint OK.

## 8. Stop and ask

Stop, and write the report as `blocked`, if an anchor assertion fails, a test fails twice, a bite passes, you reach 25 tool calls or about 50k tokens, a file outside section 3 needs a change, or you need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/1173b-report.md` (600 tokens at most): 1. `git diff --stat`; 2. each command with the last 5 lines (SQLite and PostgreSQL side by side for the bites); 3. section 7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py`: the two `alerts.resolve` lines and `_resolve_unverified_cards` (its `UPDATE alert` touches only kind `door_code_pin_unverified`).

## Owner steps

1. Open the PR when the checks are green, including test-postgres and test-postgres-full, and merge with `scripts/merge-pr-on-green.sh`.
