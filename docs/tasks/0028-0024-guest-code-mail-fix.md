# 0028: Fix 0024: the guest door-code e-mail is sent again

Status: todo
Depends on: 0024 (branch `task/0024-door-code-immediate-handover`) | Base commit: `06585a7` | Branch: `task/0024-door-code-immediate-handover` (commit on top; never rebase or force-push)
Executor: Claude Haiku 5.5, effort high (or Cursor composer, Kimi, GLM) | Fits one session

## 1. Objective

0024 step 7 was not applied. `build_door_code` now requires `first_use_by`, but `_send_code_mail` does not pass it, so every guest door-code e-mail fails with a `TypeError`. `send_code_mail` catches that and only logs `door_code_mail_failed`, so no test noticed. Pass the value, and add the test that would have caught it.

## 2. Context

Rules: 1 to 9 of AGENTS.md; nothing new. The test must **fail before** the fix and **pass after** it.

Anchor E1, `App/app/door_codes.py`, inside `_send_code_mail` (exactly once):
```python
    content = mail_notify.build_door_code(
        lang=lang,
        property_name=apartment["internal_name"] or "",
        checkin=shown["checkin"],
        checkout=shown["checkout"],
    )
```
Anchor E2, `App/tests/test_door_code_handover.py` (exactly once):
```python
from app import config, db, door_codes, mail_notify, ttlock
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_door_code_handover.py` | edit | one import, one test |
| `App/app/door_codes.py` | edit | one line |
| `docs/tasks/0024-door-code-immediate-handover.md` | edit | status line only (if the file exists on this branch) |
| `docs/tasks/0028-report.md` | create | report |

No other file may change.

## 4. Steps

1. `git fetch origin task/0024-door-code-immediate-handover && git checkout task/0024-door-code-immediate-handover && git pull origin task/0024-door-code-immediate-handover`.
2. Replace anchor E2 with:
```python
from app import config, db, door_codes, mail, mail_notify, ttlock
```
3. At the end of `App/tests/test_door_code_handover.py` add:
```python


def test_the_guest_door_code_mail_is_queued_with_the_deadline(monkeypatch):
    """The whole path: code made, guest has an address, the mail is queued (task 0028)."""
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "99"))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    now = db.utcnow()
    db.execute(
        "INSERT INTO reservation_claim (reservation_id, state, email, lang, created_at, updated_at) "
        "VALUES (?, 'claimed', 'guest@example.test', 'en', ?, ?)",
        (stay, now, now),
    )
    try:
        door_codes.reconcile()
        row = db.query_one(
            "SELECT payload FROM email_outbox WHERE reservation_id = ? AND kind = 'door_code'",
            (stay,),
        )
        assert row is not None, "the guest door-code mail was not queued"
        text = mail.delivery_body(json.loads(row["payload"]))
        assert "4821937" in text
        assert "If you have not used it by" in text
    finally:
        db.execute("DELETE FROM reservation_claim WHERE reservation_id = ?", (stay,))
```
4. From `App/`: `.venv/bin/python -m pytest tests/test_door_code_handover.py -q`. Expected: `1 failed, 7 passed`, and the failure says `the guest door-code mail was not queued`. Copy the last 5 lines into the report. Any other result: STOP (§8).
5. Replace anchor E1 with:
```python
    content = mail_notify.build_door_code(
        lang=lang,
        property_name=apartment["internal_name"] or "",
        checkin=shown["checkin"],
        checkout=shown["checkout"],
        first_use_by=shown["first_use_by"],
    )
```
6. If `docs/tasks/0024-door-code-immediate-handover.md` exists on this branch, set its line 3 to `Status: review`. If it does not exist, skip this step and say so in the report.
7. Run §6, commit (`0028: guest door-code mail gets its deadline again`), `git push origin task/0024-door-code-immediate-handover`.

## 5. Do not touch

Everything else 0024 changed. Do not loosen or delete any test.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_door_code_handover.py tests/test_door_codes_safeguards.py tests/test_guest_mail.py -q` → 0 failed.
- `.venv/bin/python -m pytest tests -q` → 0 failed apart from the four DNS tests listed in 0023 §2.

From the repo root: `python3 scripts/context_lint.py` → last line `context lint: OK`.

## 7. Acceptance

- [ ] Step 4 output shows the new test failing before the fix.
- [ ] §6 passes after it.
- [ ] `grep -n 'first_use_by=shown' App/app/door_codes.py` prints one line.
- [ ] `git diff --stat 06585a7` lists only §3 files.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found exactly once; step 4 does not fail as stated; a test fails twice after the fix; a file outside §3 needs a change; a step is unclear; you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0028-report.md` (1,000 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

The one-line change in `_send_code_mail`; the new test's before/after output.

## Owner steps

1. After the push, open a PR for `task/0024-door-code-immediate-handover` into `main` on GitHub (Compare & pull request), and wait for the checks to go green.
2. Tell the orchestrator; it re-checks and then you merge with `scripts/merge-pr-on-green.sh <PR number>`.
