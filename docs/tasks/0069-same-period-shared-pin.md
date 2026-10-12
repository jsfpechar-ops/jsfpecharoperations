# 0069: Never hand a cancelled stay's PIN to the next guest

Status: review
Depends on: 0067, 0068 (merged) | Base commit: 0e8e468 | Branch: task/0069-same-period-shared-pin
Executor: Cursor local agent (composer) | Fits one session

## 1. Objective

TTLock support (2026-10-12): a type-3 `get` for a period whose earlier code was **not** deleted returns that same code. So when a cancelled stay's delete failed and the same hours are booked again, the new guest would get the cancelled guest's PIN. This brief detects that and gives the guest a custom code instead, keeps retrying failed random-code deletes until the code's end (as custom codes already do), and maps TTLock's monthly-limit error `30007`.

## 2. Context

- TTLock facts: [TTLOCK](../TTLOCK.md) (error table, "What TTLock support confirmed"). Plan §6.
- Detection: after a random `get`, if another `door_code` row on the **same lock** with the **same window** already holds the returned `provider_code_id`, the code is shared. Treat it like `-1026`: same custom-code path, but a new host mail `period_shared` that tells the host to delete the old code (it still opens the door). Support gets a copy.
- Rule 2: no new outbound request (`add` already exists). Rule 5: no schema change. Rule 9.
- No template, CSS or guest page changes.

Anchor A, `App/app/door_codes.py`, found verbatim once:

```python
PERIOD_TAKEN = "period_taken"
```

Anchor B, `App/app/door_codes.py`, in `issue()`, found verbatim once (16-space indent on `try:`):

```python
                try:
                    pin, code_id = ttlock.create_period_code(
                        int(account["id"]),
                        row["lock_id"],
                        start_ms,
                        end_ms,
                        name,
                        priority,
                    )
                    kind = "random"
                except ttlock.TTLockError as create_exc:
                    if create_exc.kind != PERIOD_TAKEN:
                        raise
                    log.error(
                        "DOOR_CODE_PROBLEM stage=period_taken reservation=%s door_code=%s",
                        reservation["id"],
                        door_code_id,
                    )
                    mail_notify.door_code_notice(door_code_id, "period_taken")
```

Anchor C, `App/app/door_codes.py`, in `issue()`, found verbatim once:

```python
                            (RETRYING, "period_taken:-1026", now_iso, now_iso, door_code_id),
```

Anchor D, `App/app/door_codes.py`, in `_handle_moves()`, found verbatim once (12-space indent on the inner `try:`):

```python
            try:
                pin, code_id = ttlock.create_period_code(
                    int(account["id"]),
                    row["lock_id"],
                    start_ms,
                    end_ms,
                    name,
                    priority,
                )
                code_kind = "random"
            except ttlock.TTLockError as create_exc:
                if create_exc.kind != PERIOD_TAKEN:
                    raise
                mail_notify.door_code_notice(int(row["id"]), "period_taken")
```

Anchor E, `App/app/door_codes.py`, in `_revoke_one()`, found verbatim once:

```python
        kind = exc.kind or "transient"
        is_custom = (row["code_kind"] or "") == "custom"
        if is_custom and kind in GATEWAY_RETRY_KINDS:
```

Anchor F, `App/app/door_codes.py`, in `_revoke_one()`, found verbatim once (8-space indent on `elif`):

```python
        elif kind in ("offline", "transient", "network", "rate") and attempts < 3:
            delays = (1, 15, 60)
            next_at = _iso(now + timedelta(minutes=delays[min(attempts - 1, 2)]))
            db.execute(
                "UPDATE door_code SET claimed_at = NULL, next_attempt_at = ?, last_error = ?, "
                "updated_at = ? WHERE id = ?",
                (next_at, kind[:40], now_iso, row_id),
            )
        else:
```

Anchor G, `App/app/ttlock.py`, found verbatim once:

```python
    30006: "rate",
```

Anchor H, `App/app/mail_notify.py`, found verbatim once:

```python
_SUPPORT_COPY_VARIANTS = ("failed", "delayed", "period_taken", "moved_not_deleted")
```

Anchor I, `App/app/host_i18n.py`: the line starting `        "mail.door_code_notice.period_taken.body":`, once in `en` (about line 3856) and once in `cs` (about line 4702).

Anchor J, `App/tests/test_door_codes_safeguards.py`: the whole function `def test_a_random_code_delete_stops_after_three_failures(monkeypatch):` (about line 960), up to the blank lines before `def test_a_move_into_the_stay_window_keeps_the_code`.

If any anchor is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/door_codes.py` | edit | Steps 1 to 5 |
| `App/app/ttlock.py` | edit | Step 6 |
| `App/app/mail_notify.py` | edit | Step 7 |
| `App/app/host_i18n.py` | edit | Step 8 |
| `App/tests/test_door_codes_safeguards.py` | edit | Step 9 |

No other file may change. One exception: if an existing test fails only because its fake `create_period_code` returns the same code id for two stays on the same lock and window, give the second stay a different id in that fake, and list it in the report.

## 4. Steps

1. `door_codes.py`, after anchor A add:

```python
# A type-3 ``get`` for a period whose earlier code was never deleted returns
# that same code (TTLock support, 2026-10-12). Such a code is never reused.
PERIOD_SHARED = "period_shared"
```

Then, directly above `def issue(door_code_id: int, *, allow_gateway: bool = False) -> bool:`, add:

```python
def _create_random(
    account_id: int,
    lock_id: str,
    start_ms: int,
    end_ms: int,
    name: str,
    priority: str,
    door_code_id: int,
) -> Tuple[str, str]:
    pin, code_id = ttlock.create_period_code(account_id, lock_id, start_ms, end_ms, name, priority)
    other = db.query_one(
        "SELECT id FROM door_code WHERE lock_id = ? AND provider_code_id = ? "
        "AND valid_from = ? AND valid_to = ? AND id != ?",
        (lock_id, str(code_id), _ms_to_iso(start_ms), _ms_to_iso(end_ms), door_code_id),
    )
    if other:
        raise ttlock.TTLockError("period already has an undeleted code", kind=PERIOD_SHARED)
    return pin, code_id


```

2. Replace anchor B with:

```python
                try:
                    pin, code_id = _create_random(
                        int(account["id"]),
                        row["lock_id"],
                        start_ms,
                        end_ms,
                        name,
                        priority,
                        door_code_id,
                    )
                    kind = "random"
                except ttlock.TTLockError as create_exc:
                    if create_exc.kind not in (PERIOD_TAKEN, PERIOD_SHARED):
                        raise
                    log.error(
                        "DOOR_CODE_PROBLEM stage=%s reservation=%s door_code=%s",
                        create_exc.kind,
                        reservation["id"],
                        door_code_id,
                    )
                    mail_notify.door_code_notice(door_code_id, create_exc.kind)
```

3. Replace anchor C with:

```python
                            (
                                RETRYING,
                                "period_taken:-1026"
                                if create_exc.kind == PERIOD_TAKEN
                                else "period_taken:shared",
                                now_iso,
                                now_iso,
                                door_code_id,
                            ),
```

(Both values start with `period_taken`, so the next worker run goes straight to `add`, as today.)

4. Replace anchor D with:

```python
            try:
                pin, code_id = _create_random(
                    int(account["id"]),
                    row["lock_id"],
                    start_ms,
                    end_ms,
                    name,
                    priority,
                    int(row["id"]),
                )
                code_kind = "random"
            except ttlock.TTLockError as create_exc:
                if create_exc.kind not in (PERIOD_TAKEN, PERIOD_SHARED):
                    raise
                mail_notify.door_code_notice(int(row["id"]), create_exc.kind)
```

5. Replace anchor E with:

```python
        kind = exc.kind or "transient"
        # Every code, random or custom, is retried until its end: an undeleted
        # code is handed again to the next stay with the same hours.
        if kind in GATEWAY_RETRY_KINDS:
```

Then replace anchor F with just:

```python
        else:
```

Run `grep -n 'is_custom' App/app/door_codes.py` and expect no output.

6. `ttlock.py`, after anchor G add the line:

```python
    30007: "budget",
```

7. `mail_notify.py`, replace anchor H with:

```python
_SUPPORT_COPY_VARIANTS = ("failed", "delayed", "period_taken", "period_shared", "moved_not_deleted")
```

8. `host_i18n.py`, directly after each anchor I line, add two lines. In `en`:

```python
        "mail.door_code_notice.period_shared.subject": "%(property)s: an old door code still covers the stay from %(date)s",
        "mail.door_code_notice.period_shared.body": "TTLock still holds a code for exactly the hours of the stay from %(date)s, for example the code of a cancelled stay that UbyHost could not delete. TTLock gives one random code per period, so UbyHost gave this guest a code of their own. The old code still opens the door during this stay. Delete it in the TTLock app.",
```

In `cs`:

```python
        "mail.door_code_notice.period_shared.subject": "%(property)s: pobyt od %(date)s pokrývá i starý kód ke dveřím",
        "mail.door_code_notice.period_shared.body": "TTLock má stále kód pro přesně hodiny pobytu od %(date)s, například kód zrušeného pobytu, který UbyHost nemohl smazat. TTLock dává pro jedno období jen jeden náhodný kód, proto UbyHost dal tomuto hostovi vlastní kód. Starý kód během tohoto pobytu stále otevírá dveře. Smažte ho v aplikaci TTLock.",
```

9. `test_door_codes_safeguards.py`: replace the whole function of anchor J with these three tests:

```python
def test_a_random_code_delete_keeps_trying_until_its_end(monkeypatch):
    delete_calls = {"n": 0}

    def offline(*args, **kwargs):
        delete_calls["n"] += 1
        raise ttlock.TTLockError("gateway offline", code=-2012, kind="offline")

    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "rand-1"))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    row = db.query_one("SELECT id, code_kind FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["code_kind"] == "random"

    db.execute(
        "UPDATE reservation SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (db.utcnow(), stay),
    )
    monkeypatch.setattr(ttlock, "delete_code", offline)

    for _ in range(5):
        db.execute(
            "UPDATE door_code SET next_attempt_at = NULL, claimed_at = NULL WHERE id = ?",
            (row["id"],),
        )
        door_codes.reconcile()
        state = db.query_one("SELECT state FROM door_code WHERE id = ?", (row["id"],))
        assert state["state"] == door_codes.REVOKE_PENDING

    assert delete_calls["n"] == 5
    notices = db.query(
        "SELECT idempotency_key FROM email_outbox "
        "WHERE reservation_id = ? AND idempotency_key LIKE '%:cancelled_not_deleted'",
        (stay,),
    )
    assert len(notices) == 1


def test_an_undeleted_code_for_the_same_hours_is_never_handed_out_again(monkeypatch):
    """TTLock returns the old PIN for the same period while the old code exists."""

    def offline(*args, **kwargs):
        raise ttlock.TTLockError("gateway offline", code=-2012, kind="offline")

    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "rand-1"))
    monkeypatch.setattr(ttlock, "add_custom_code", lambda *a, **k: ("7654321", "add-1"))
    monkeypatch.setattr(ttlock, "delete_code", offline)
    _, _, first = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    db.execute(
        "UPDATE reservation SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (db.utcnow(), first),
    )
    door_codes.reconcile()

    _, _, second = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (second,))
    assert row["state"] == door_codes.ISSUED
    assert row["provider_code_id"] == "add-1"
    assert row["code_kind"] == "custom"
    assert db.decrypt_field(row["pin_enc"]) == "7654321"
    notices = db.query(
        "SELECT idempotency_key FROM email_outbox "
        "WHERE reservation_id = ? AND idempotency_key LIKE '%:period_shared'",
        (second,),
    )
    assert len(notices) == 1


def test_the_monthly_limit_error_counts_as_budget():
    assert ttlock.ERROR_KINDS[30007] == "budget"
```

10. Run the commands in §6.

## 5. Do not touch

`App/app/migrations/`, every template, every other i18n key, the `period_taken` mail strings, `App/tests/test_ttlock.py`. Hard rules 2, 3, 5, 8, 9 apply.

## 6. Commands

From `App/`:

```
grep -n 'is_custom' app/door_codes.py                       # expect no output
.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_handover.py tests/test_confirmation_with_door_code.py tests/test_ttlock.py -q   # expect all pass
.venv/bin/python -m pytest tests -q                          # expect all pass
```

From the repo root: `python3 scripts/context_lint.py` (expect OK).

## 7. Acceptance

- [ ] The grep gives no output.
- [ ] The three new tests pass, and the door-code test files pass.
- [ ] The full suite passes, or only failures that also fail on `main` remain (name them in the report; CI decides).
- [ ] `git diff --stat` lists only the files in §3 (plus the §3 exception, if used).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0069-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/door_codes.py`: `_create_random` query (same lock, same window, other row), both call sites, `_revoke_one` now retries random codes until `valid_to`.
- `App/tests/test_door_codes_safeguards.py`: the replaced test and the two new ones.

## Owner steps

1. Open the PR the executor pushed and check that CI is green.
2. Merge it with `scripts/merge-pr-on-green.sh <PR number>`.
3. On staging, optional: hand-add two stays with the same dates and hours, register the first, unplug the gateway, cancel it, then register the second. The second guest must get a different code, and you get "an old door code still covers the stay".
