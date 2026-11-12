# 1161: a crash-stuck `running` filing is recovered in every apartment mode (K-F23), Python

Status: review (Postgres area run left to CI; local ubytest unreliable)
Depends on: 1154 (merged: an iCal date move waits while a `running` row lists an unsent guest of the stay) | Base commit: 174db7a2 (HEAD of branch claude/zealous-maxwell-a7ub54) | Branch: task/1161-stuck-running-all-modes
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list. Go twin: brief 1161b (the Go service runs the live `submit` job, so 1161b is the one that fixes production). Do both before merging either. Run 1161 first.

## 1. Objective

Close K-F23 in Python. The sweep skips `manual` and inactive apartments and any apartment with an open `ubyport_auth_failed` alert, and only the sweep (or the start of a send) rewrites a crash-stuck `running` batch to `outcome_unknown`. There, an iCal date move (deferred since 1154) waits on every poll with only a log line and the host sees nothing. After this brief `sweep()` first runs `recover_stale_submissions` for every apartment that has a `running` batch, in any mode, active or not, auth failed or not. Recovery only rewrites the row (its existing critical alert `submission_outcome_unknown` then shows the host the problem); it never sends to UbyPort.

## 2. Context

Rule 1: UbyPort filing correctness beats every other feature. The reasoning is here; read nothing else.

**Decision (from the code).** Option "call recovery from the iCal sync path" is rejected: the Go iCal package would have to import `ubyport` and the iCal poll runs hourly, so it would be a second, slower recovery path. Chosen: the sweep (every 10 minutes) runs recovery for every apartment with a `running` row before its normal loop. One place per runtime, no new alert, no new copy.

**Why `recover_stale_submissions(apartment_id)` is safe to call for any apartment** (`App/app/reporting.py`, def at line 2085):
- It judges staleness by the send claim, never by row age or mode: a `running` row whose guests hold a claim younger than `SUBMISSION_CLAIM_TTL_SECONDS` (5 minutes) is skipped, so a live send is never touched.
- Both its transactions take `db.lock_key(cur, "submit_apartment", apartment_id)`, the same lock a send holds, and the write is `UPDATE ... WHERE id = ? AND state = 'running'` with a `rowcount != 1` guard, so an outcome recorded by the send after the scan stands.
- It is idempotent: a second call finds no `running` row and returns 0 without alerting.
- It never calls `submit_batch`, the SOAP client or a retry. It only sets `state='outcome_unknown'`, `finished_at`, `error_text`, points unsent guests at the row, and raises the critical alert `submission_outcome_unknown:<apartment_id>` (deduped).
- A manual send already calls it first (`submit_for_apartment`, line 2360), so running it for a manual apartment is the same code on a different trigger.

**Production runtime.** `docs/context/status.md`: "Go jobs = queue: billing_snapshot, stripe_sweep, ical, push, submit". `UBYHOST_GO_JOB_KINDS` (docs/ENVIRONMENT.md) names `submit`, `go/cmd/ubyhost-web/main.go` handler `"submit"` calls `ubyport.Sweep`, and Python's `jobqueue` leaves Go kinds to it. So the Python sweep runs only if `submit` is removed from `UBYHOST_GO_JOB_KINDS` (rollback, disaster recovery). Python and Go must still behave the same.

**Alert copy already exists** (`App/app/host_i18n.py` lines ~9161 and 9199, cs/en, plus vi): `notification.submission_outcome_unknown.title/detail`. No new copy. Residual, not fixed here: the detail says the system resends by itself; in `manual` mode it does not (the host resends from the stay). That text is already what a manual-mode host sees after an unclear manual send. Owner decision if the wording should change; this brief leaves it.

**What stays deferred.** The recovered row is `outcome_unknown` and the guest is pointed at it, so `icalsync._send_in_flight` keeps returning True (via `_pointed_at_open_submission`) and the move stays deferred until the host resolves it. That is the intended end state: the difference is that the host now sees the critical alert.

Anchor, current code (`App/app/reporting.py`, lines 2395 to 2397; the `def` line occurs once in the file):
```python
def sweep(owner_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Scheduled pass over active apartments, optionally for one workspace."""
    summary = {"apartments": 0, "submitted": 0, "failed": 0}
```
Test helpers already in `App/tests/test_stale_submission.py` (imports `json, sqlite3, time, date, timedelta, pytest, alerts, db, reporting` present): `_guest(reservation, name, now)`, `_batch(apartment, guests, now)` (a `running` row, no pointer), and an autouse fixture that deletes every apartment with `permalink_token = 'stale-sweep'` and the user `stale-sweep-owner` after each test. The new tests reuse that token and user so the fixture cleans them.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/reporting.py | edit | new `_recover_stuck_running_batches`, one call in `sweep()` |
| App/tests/test_stale_submission.py | edit | append 7 test cases (3 test functions plus one parametrized by 4) and 3 helpers |
| docs/OPERATIONS.md | edit | one sentence in the `submit` job row |
| docs/tasks/1161-stuck-running-recovered-in-all-modes.md | status | `review` at the end |
| docs/tasks/1161-report.md | create | report |

No other file may change. No copy, no migration, no alert kind, no dependency, no new outbound request, no new personal-data field.

## 4. Steps

Commit after each step: `git add -A && git commit -qm "1161 step N"`. Work from `App/` for every command. Postgres run uses `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest` (start it first if `pg_isready -h localhost` says no response: `pg_ctlcluster 16 main start`).

**Step 1. Tests first (they must fail before the fix).** Append this block to the end of `App/tests/test_stale_submission.py` (the file currently ends with the line `    assert client.calls == 1`; keep two blank lines before the block):
```python
# --- K-F23: a crash-stuck running batch is recovered in every mode -----------


def _stuck_apartment(*, mode="manual", active=1, auth_failed=False, claim_age=None):
    """One apartment with a stay, an unsent guest and a ``running`` batch (no pointer).

    ``claim_age`` None means no claim row (a crash); a number is the claim's age
    in seconds.
    """
    db.init_db()
    now = db.utcnow()
    owner_id = db.insert(
        "user_account",
        {"username": "stale-sweep-owner", "password_hash": "x", "role": "host",
         "active": 1, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {"owner_user_id": owner_id, "internal_name": "Stuck flat",
         "permalink_token": "stale-sweep", "automation_mode": mode,
         "active": active, "created_at": now},
    )
    reservation_id = db.insert(
        "reservation",
        {"apartment_id": apartment_id, "uid": "stuck-1", "date_from": "2099-01-10",
         "date_to": "2099-01-12", "status": "active", "created_at": now, "updated_at": now},
    )
    guest_id = _guest(reservation_id, "Stuck", now)
    batch_id = _batch(apartment_id, [guest_id], now)
    if claim_age is not None:
        db.insert(
            "submission_claim",
            {"guest_id": guest_id, "claim_token": "t", "claimed_at": time.time() - claim_age},
        )
    if auth_failed:
        alerts.raise_alert(
            "critical", "ubyport_auth_failed", "Auth failed", "Bad password",
            dedupe_key=f"ubyport_auth_failed:{apartment_id}", apartment_id=apartment_id,
        )
    return owner_id, apartment_id, reservation_id, guest_id, batch_id


def _no_send(monkeypatch):
    """Record every send path; the recovery pass must call none of them."""
    calls = []
    for name in ("submit_batch", "submit_for_apartment", "_retry_outcome_unknown_batches"):
        monkeypatch.setattr(reporting, name, lambda *a, _n=name, **k: calls.append(_n) or [])
    return calls


def _state(batch_id):
    return db.query_one("SELECT state FROM submission WHERE id = ?", (batch_id,))["state"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "manual"},
        {"mode": "manual", "claim_age": 600},
        {"mode": "immediate", "active": 0},
        {"mode": "immediate", "auth_failed": True},
    ],
    ids=["manual", "manual-stale-claim", "inactive", "auth-failed"],
)
def test_a_stuck_running_batch_is_recovered_when_the_sweep_skips_the_apartment(
    monkeypatch, kwargs
):
    from app import icalsync

    owner_id, apartment_id, reservation_id, guest_id, batch_id = _stuck_apartment(**kwargs)
    calls = _no_send(monkeypatch)
    assert not alerts.open_alert(f"submission_outcome_unknown:{apartment_id}")

    reporting.sweep(owner_user_id=owner_id)

    assert _state(batch_id) == "outcome_unknown"
    assert db.query_one("SELECT submission_id FROM guest WHERE id = ?", (guest_id,))[
        "submission_id"
    ] == batch_id
    alert = alerts.open_alert(f"submission_outcome_unknown:{apartment_id}")
    assert alert and alert["level"] == "critical"
    assert icalsync._send_in_flight(reservation_id), "the date move keeps waiting"
    assert calls == [], "recovery rewrites the row, it never sends"


def test_an_auto_apartment_stuck_batch_is_still_recovered_once(monkeypatch):
    owner_id, apartment_id, _reservation_id, _guest_id, batch_id = _stuck_apartment(
        mode="immediate"
    )
    _no_send(monkeypatch)

    reporting.sweep(owner_user_id=owner_id)
    reporting.sweep(owner_user_id=owner_id)

    assert _state(batch_id) == "outcome_unknown"
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM alert WHERE dedupe_key = ?",
        (f"submission_outcome_unknown:{apartment_id}",),
    )["n"] == 1


def test_a_live_claim_is_never_recovered_in_manual_mode(monkeypatch):
    owner_id, apartment_id, _reservation_id, guest_id, batch_id = _stuck_apartment(
        mode="manual", claim_age=10
    )
    _no_send(monkeypatch)

    reporting.sweep(owner_user_id=owner_id)

    assert _state(batch_id) == "running"
    assert db.query_one("SELECT submission_id FROM guest WHERE id = ?", (guest_id,))[
        "submission_id"
    ] is None
    assert not alerts.open_alert(f"submission_outcome_unknown:{apartment_id}")


def test_the_recovery_pass_stays_inside_the_workspace_it_was_asked_for(monkeypatch):
    owner_id, apartment_id, _reservation_id, _guest_id, batch_id = _stuck_apartment()
    _no_send(monkeypatch)

    reporting.sweep(owner_user_id=owner_id + 100000)

    assert _state(batch_id) == "running"
    assert not alerts.open_alert(f"submission_outcome_unknown:{apartment_id}")
```
Command: `.venv/bin/python -m pytest tests/test_stale_submission.py -q --tb=line -k "stuck_running or auto_apartment_stuck or live_claim_is_never or recovery_pass_stays" 2>&1 | tail -30`. Expected (fix not yet applied): `4 failed, 3 passed`; the 4 failures are the four `test_a_stuck_running_batch_is_recovered_when_the_sweep_skips_the_apartment[...]` cases (`manual`, `manual-stale-claim`, `inactive`, `auth-failed`).

**Step 2. The fix in `App/app/reporting.py`.** Replace the exact anchor text
```python
def sweep(owner_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Scheduled pass over active apartments, optionally for one workspace."""
    summary = {"apartments": 0, "submitted": 0, "failed": 0}
```
with
```python
def _recover_stuck_running_batches(owner_user_id: Optional[int] = None) -> None:
    """Rewrite crash-stuck ``running`` batches of EVERY apartment (K-F23).

    ``sweep()`` skips ``manual`` and inactive apartments and those with an open
    ``ubyport_auth_failed`` alert, so a batch a crash left ``running`` there
    stayed invisible and silently held an iCal date move. Recovery only rewrites
    the row (``outcome_unknown``, guests pointed, critical alert); it never sends,
    so it is safe in every mode. The retry and the send stay in ``sweep()``.
    """
    for row in db.query(
        "SELECT DISTINCT s.apartment_id FROM submission s "
        "JOIN apartment a ON a.id = s.apartment_id "
        "WHERE s.state = 'running' AND (? IS NULL OR a.owner_user_id = ?)",
        (owner_user_id, owner_user_id),
    ):
        try:
            recover_stale_submissions(row["apartment_id"])
        except Exception:
            log.exception(
                "stuck_running_recovery_failed apartment_id=%s", row["apartment_id"]
            )


def sweep(owner_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Scheduled pass over active apartments, optionally for one workspace."""
    summary = {"apartments": 0, "submitted": 0, "failed": 0}
    _recover_stuck_running_batches(owner_user_id)
```
(The new function ends with one blank line and the `def sweep` line follows after a second blank line: two blank lines between top-level functions.) Do not touch the `recover_stale_submissions(apartment["id"])` call inside the loop: it stays, and is a no-op after the pre-pass.
Command: `.venv/bin/python -m pytest tests/test_stale_submission.py -q --tb=short 2>&1 | tail -30`. Expected: `23 passed`.

**Step 3. Docs sentence.** In `docs/OPERATIONS.md`, in the `submit` row of the job table, replace the exact text
```
| `submit` | `UBYHOST_SUBMIT_SWEEP_MINUTES` (10) | Sends everything currently sendable for apartments not in `manual` mode. |
```
with
```
| `submit` | `UBYHOST_SUBMIT_SWEEP_MINUTES` (10) | Sends everything currently sendable for apartments not in `manual` mode. First, for every apartment in any mode, it rewrites a send that crashed (a `running` batch with no live claim) to `outcome_unknown`, which raises the critical `submission_outcome_unknown` alert; that pass sends nothing. |
```
Command: `grep -c "that pass sends nothing" ../docs/OPERATIONS.md`. Expected: `1`.

**Step 4. Revert bites.** Commit step 3 first so `git checkout` restores the files. After each bite run `git checkout app/reporting.py` and the same pytest; expected `7 passed`.
Bite pytest command (used in all three): `.venv/bin/python -m pytest tests/test_stale_submission.py -q --tb=no -k "stuck_running or auto_apartment_stuck or live_claim_is_never or recovery_pass_stays" 2>&1 | tail -10`.
(a) In `sweep()` delete the line `    _recover_stuck_running_batches(owner_user_id)`. Expected: `4 failed, 3 passed` (the four parametrized cases).
(b) In `_recover_stuck_running_batches` replace `AND (? IS NULL OR a.owner_user_id = ?)",` with `AND (? IS NULL OR 1 = 1)",` and replace the line `        (owner_user_id, owner_user_id),` with `        (owner_user_id,),`. Expected: `1 failed, 6 passed`: `test_the_recovery_pass_stays_inside_the_workspace_it_was_asked_for`.
(c) Inside the `try:` of `_recover_stuck_running_batches` replace `recover_stale_submissions(row["apartment_id"])` with `db.execute("UPDATE submission SET state = 'outcome_unknown' WHERE state = 'running' AND apartment_id = ?", (row["apartment_id"],))` (a recovery that ignores the claim). Expected: `6 failed, 1 passed`; passes only `test_the_recovery_pass_stays_inside_the_workspace_it_was_asked_for`; the live-claim test `test_a_live_claim_is_never_recovered_in_manual_mode` is among the failures.

**Step 5. Lint and area runs.**
`.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30`. Expected: `All checks passed!`.
Default (SQLite): `.venv/bin/python -m pytest tests/test_stale_submission.py tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_submission_*.py tests/test_ubyport_*.py tests/test_no_em_dashes.py -q --tb=short -x -rs 2>&1 | tail -30`. Expected: all pass, 0 skipped.
Postgres: the same command with `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest` in front. Expected: all pass; the only skip allowed is `tests/test_ical_skip_unchanged.py:191: sqlite_only`.
(`tests/test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses` fails in the sandbox on a clean checkout too; it is not in this run. If you run the whole test-map iCal row and only it fails, say so in the report and do not fix it.)

## 5. Do not touch

`recover_stale_submissions` itself, `_retry_outcome_unknown_batches`, `submit_for_apartment`, `icalsync.py`, any template or copy file, `alerts.py`, the loop body of `sweep()`. Hard rules from AGENTS.md: 1 (filing correctness), 2 (no new outbound request, no personal-data field), 4 (no dependency), 5 (SQL in `db` helpers: the new query uses `db.query` with `?` params and is Postgres-portable), 9 (no new copy).

## 6. Commands

All from `App/`, each ending `2>&1 | tail -30`: Step 1 (expect `4 failed, 3 passed`), Step 2 (`23 passed`), Step 3 (`1`), Step 4 bites (expect as written, each restored to `7 passed`), Step 5 (ruff clean; area runs green). From the repo root: `python3 scripts/context_lint.py | tail -3` (expect `context lint: OK`; a status.md WARN is the orchestrator's).

## 7. Acceptance

- [ ] A `running` batch with no claim or a claim older than 5 minutes, in a `manual` apartment, an inactive apartment and an apartment with an open `ubyport_auth_failed` alert, is `outcome_unknown` after `sweep()`, its guest points at it, one critical `submission_outcome_unknown` alert is open, `icalsync._send_in_flight` is True, and `submit_batch`, `submit_for_apartment` and `_retry_outcome_unknown_batches` were never called.
- [ ] A claim younger than 5 minutes in a manual apartment: row stays `running`, no pointer, no alert.
- [ ] An auto-mode apartment behaves as before; two sweeps leave exactly one alert row.
- [ ] `sweep(owner_user_id=other)` leaves another workspace's stuck row alone.
- [ ] Bites (a) `4 failed`, (b) `1 failed`, (c) `6 failed`, each green after `git checkout`.
- [ ] ruff clean; SQLite and Postgres area runs green; lint OK; only section 3 files changed.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- Postgres cannot be started (then report the SQLite run only and say so);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1161-report.md` (600 tokens at most) and set `Status: review`. The report has: the files changed (`git diff --stat`); each command with the last 5 lines of its output; section 7 ticked; deviations; questions; owner steps left.

## Risk list (for the reviewer)

- `App/app/reporting.py`: `_recover_stuck_running_batches` and its one call at the top of `sweep()`. Check it only calls `recover_stale_submissions` (no send), and the owner scope.
- `App/tests/test_stale_submission.py`: the live-claim test and the no-send assertion.

## Owner steps

1. Push `task/1161-stuck-running-all-modes` and open a draft PR; keep it draft until 1161b is also ready.
2. Merge both with `scripts/merge-pr-on-green.sh`; green merges auto-deploy. No server step: the Go service (1161b) is what the live `submit` job runs.
