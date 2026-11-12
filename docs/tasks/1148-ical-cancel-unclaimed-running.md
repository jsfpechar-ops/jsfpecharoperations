# 1148: iCal cancel with a `running` or `outcome_unknown` filing: defer a fresh `running`, alert otherwise (K-F20), Python

Status: todo
Depends on: 1144 (order only) | Base commit: 21c87fc6 (HEAD of branch claude/zealous-maxwell-a7ub54) | Branch: task/1148-ical-cancel-running
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list. Go twin: brief 1148b (runs after this one; it reuses the copy keys added here). Do both before merging either.

## 1. Objective

Close K-F20 in Python. An iCal cancel (event or vanished-stay sweep) today ignores a submission that is `running` or `outcome_unknown` once its claim is gone. After this brief: a `running` submission younger than 30 minutes defers the cancel (the sweep recovers and resends it first); any other cancel of a stay whose filing is `running` or `outcome_unknown` still cancels, but raises one host alert `cancelled_filing_unconfirmed` saying the police register may hold the guests.

## 2. Context

Owner ruling: "do the recommended, simulate what is best for the user". Options were (a) leave, (b) defer while `running` is younger than the claim TTL, (c) b plus an alert. Simulation result: pick (c), with (b) re-aimed (below).

What cancel does (icalsync.py `_cancel_existing_stay`, sweep in `sync_feed`): `reservation.status = 'cancelled'`, guest access locked, queued mail failed. It never withdraws a UbyPort filing and never touches the guest rows. But `collect_sendable` only reads `r.status = 'active'` stays (reporting.py:1557, 1577), so after a cancel nothing ever resends or resolves an in-doubt batch for that stay.

Simulated with a throwaway test on SQLite (App/.venv), cancel event arriving for a stay whose guest is `pending`:
- `outcome_unknown` batch, guest pointing at it: stay `cancelled`, `collect_sendable` returns 0 guests, `apartment_in_doubt` is False, the only host signal is `cancelled_with_guests` ("Nothing will be reported for it"), which is wrong when the register may already hold the guest.
- `running` batch, claim 400 s old (crash): stay `cancelled`, guest `submission_id` is NULL; `recover_stale_submissions` then marks it `outcome_unknown` and raises the critical `submission_outcome_unknown`, which the next retry pass resolves as "the host filed by hand" (reporting.py:2246) because `apartment_in_doubt` ignores cancelled stays (reporting.py:1768).

Why option (b) as worded is a no-op: the claim is stamped before the submission row and refreshed before each batch (reporting.py:1700, 1750), and one UbyPort call times out at 60 s (Python client.py:96) or 180 s (Go client.go:61), both under the 300 s TTL (reporting.py:97). A `running` row younger than the TTL with no live claim practically cannot exist. The real case is the crash: claim stale, row still `running` until the next sweep runs `recover_stale_submissions` (reporting.py:2410, every `SUBMIT_SWEEP_MINUTES` = 10, config.py:318, only for apartments not in `manual` mode). A guest is not pointed at a `running` row (only at `outcome_unknown`, reporting.py:2127), so the existing `_send_in_flight` `running` branch does not see it; `submission.guest_ids` (JSON) is the only link.

| # | Timeline | Today | New (this brief) |
|---|---|---|---|
| T1 | Worker crashes mid-send; claim stale; row `running`; cancel arrives within 30 min | Cancelled. Recover later makes `outcome_unknown`; critical alert auto-resolved as "filed by hand"; register may hold the guest; host told only "nothing will be reported" | Cancel deferred, feed digest not stored. Sweep recovers, auto-resends at once (reporting.py:2410). Accepted or duplicate: guest `sent`, next poll raises `cancelled_after_report` (correct). Still unknown: cancel + new alert |
| T2 | Same, but `running` row older than 30 min, or apartment in `manual` mode (never recovered) | Cancelled silently | Cancelled, new alert (never defers for ever) |
| T3 | UbyPort accepted, answer lost (`outcome_unknown`, reporting.py:1826); guest cancels on Airbnb | Cancelled; retry chain dead (collect skips cancelled); critical alert silently resolved; wrong filing stands unmentioned | Cancelled (calendar is the truth), warning `cancelled_filing_unconfirmed`: check UbyPort, the register may list guests of a cancelled stay |
| T4 | Cancel 1 s after the claim expired | Cancelled (claim guard passes, icalsync.py:586) | Same as T1 or T3 by the row state; no gap |
| T5 | Long `outcome_unknown` chain (30 min, 2 h, 6 h, 12 h, then final notice, reporting.py:2236 to 2264) | Cancelled silently | Cancelled + alert. Deferring would hold the stay ~20 h and for ever after the 5th try: rejected |
| T6 | Cancel, then the host re-books the same dates (new UID) | Old stay cancelled silently; new stay files normally | Old stay carries the alert, so the host can check the register for a record of the same people before the new stay files |
| T7 | `running` row that never resolves | Cancelled silently | Deferred for at most 30 min (bounded by `created_at`), then cancel + alert |
| T8 | Claim live (normal send) | Deferred (1139) | Unchanged |
| T9 | Guest already `sent` | `cancelled_after_report` | Unchanged |

Residual, not fixed here: the older `cancelled_with_guests` mail, push and alert still say "Nothing will be reported for it" when a filing was in doubt; the new alert is the correction. A `running` row of a stay in `manual` mode that is older than 30 min is alerted but never recovered by the sweep (separate matter).

Anchors, current code (`App/app/icalsync.py`):

`_send_in_flight` ends with (lines ~398 to 407):
```python
    return bool(
        db.query_one(
            "SELECT 1 AS n FROM guest g "
            "JOIN submission s ON s.id = g.submission_id "
            "WHERE g.reservation_id = ? AND g.archived_at IS NULL "
            "AND g.submit_state != ? AND s.state IN ('running', 'outcome_unknown') "
            "LIMIT 1",
            (reservation_id, reporting.SENT),
        )
    )
```
`_cancel_existing_stay` (~620 to 637):
```python
    if not _cancel_reservation_unless_claimed(existing["id"], now):
        log.warning(
            "ical_cancel_deferred_in_flight apartment_id=%s reservation_id=%s",
            apartment_id,
            existing["id"],
        )
        return True
    from . import claim as stay_claim

    stay_claim.expire_on_cancel(existing)
    _warn_if_guests_registered(existing, apartment_id, "cancelled")
```
Sweep in `sync_feed` (~1075 to 1087):
```python
        if not _cancel_reservation_unless_claimed(row["id"], now):
            deferred_in_flight = True
            log.warning(
                "ical_cancel_deferred_in_flight apartment_id=%s reservation_id=%s",
                feed["apartment_id"],
                row["id"],
            )
            continue
        from . import claim as stay_claim

        stay_claim.expire_on_cancel(row)
        _warn_if_guests_registered(row, feed["apartment_id"], "disappeared")
```
Alerts: `alerts.raise_alert(level, kind, message, detail, dedupe_key=, apartment_id=, reservation_id=, params=)` dedupes on an open key (alerts.py:440). The card is built at render time from `notification.<kind>.title` / `.detail` and `params` (alerts.py `_present_stored`), so a new kind needs only copy keys. Go writes alerts with the same params, so one copy set serves both.

Test helpers (`App/tests/test_icalsync.py`): `_moved_stay(tmp_path, monkeypatch)` -> `(feed_id, reservation_id, guest_id)` (stay 2099-01-10..12, uid `moved-stay`, apartment in `manual` mode); `_sync(feed_id)`; `MOVED_STAY_FEED`; `_stored_stays(tmp_path, monkeypatch, name, *, stored, returned)` -> `(feed_id, apartment_id, uids)`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/icalsync.py | edit | imports, helpers, 2 call-site edits (event, sweep) |
| App/app/host_i18n.py | edit | en and cs copy, 2 keys each |
| App/app/host_vi_i18n.py | edit | vi copy, 2 keys |
| App/tests/test_icalsync.py | edit | imports, helpers, 6 tests |
| App/tests/test_alert_language.py | edit | one kind in STORED_KINDS |
| docs/OPERATIONS.md | edit | one row in the alert kinds table |
| docs/tasks/1148-ical-cancel-unclaimed-running.md | status | `review` at the end |
| docs/tasks/1148-report.md | create | report |

No other file may change.

## 4. Steps

Commit after each step: `git add -A && git commit -qm "1148 step N"`.

**Step 1. Imports and helpers in icalsync.py.**
(a) Replace `import hashlib\nimport logging` with `import hashlib\nimport json\nimport logging`. Replace `from datetime import date, datetime, timedelta` with `from datetime import date, datetime, timedelta, timezone`.
(b) Replace the `return bool(\n        db.query_one(\n            "SELECT 1 AS n FROM guest g "\n            "JOIN submission s ...` block quoted in §2 (the final `return bool(...)` of `_send_in_flight`, nothing else) with:
```python
    return _pointed_at_open_submission(reservation_id)


# A cancel waits for a send whose claim is gone only this long: the sweep
# (every SUBMIT_SWEEP_MINUTES) recovers and resends it well inside the window,
# and a row older than this is reported to the host instead of held for ever.
RUNNING_CANCEL_DEFER_SECONDS = 30 * 60


def _pointed_at_open_submission(reservation_id: int) -> bool:
    """An unsent guest of the stay points at a running or outcome_unknown batch."""
    return bool(
        db.query_one(
            "SELECT 1 AS n FROM guest g "
            "JOIN submission s ON s.id = g.submission_id "
            "WHERE g.reservation_id = ? AND g.archived_at IS NULL "
            "AND g.submit_state != ? AND s.state IN ('running', 'outcome_unknown') "
            "LIMIT 1",
            (reservation_id, reporting.SENT),
        )
    )


def _running_submission_covers_stay(reservation_id: int, newer_than: Optional[str] = None) -> bool:
    """A `running` batch of this apartment lists an unsent guest of the stay.

    A guest is not pointed at a running batch, only ``submission.guest_ids``
    names it. ``newer_than`` (an ISO UTC stamp) limits the rows by ``created_at``.
    """
    guests = {
        row["id"]
        for row in db.query(
            "SELECT id FROM guest WHERE reservation_id = ? AND archived_at IS NULL "
            "AND submit_state != ?",
            (reservation_id, reporting.SENT),
        )
    }
    if not guests:
        return False
    sql = (
        "SELECT s.guest_ids FROM submission s JOIN reservation r "
        "ON r.apartment_id = s.apartment_id WHERE r.id = ? AND s.state = 'running'"
    )
    params: List[Any] = [reservation_id]
    if newer_than:
        sql += " AND s.created_at >= ?"
        params.append(newer_than)
    for row in db.query(sql, params):
        try:
            listed = json.loads(row["guest_ids"] or "[]")
        except ValueError:
            continue
        if guests & set(listed):
            return True
    return False


def _running_defers_cancel(reservation_id: int) -> bool:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=RUNNING_CANCEL_DEFER_SECONDS)
    ).replace(microsecond=0).isoformat()
    return _running_submission_covers_stay(reservation_id, cutoff)


def _alert_if_filing_in_doubt(reservation: Any, apartment_id: int) -> None:
    """After a cancel: tell the host the register may hold this stay's guests."""
    if not (
        _pointed_at_open_submission(reservation["id"])
        or _running_submission_covers_stay(reservation["id"])
    ):
        return
    alerts.raise_alert(
        "warning",
        "cancelled_filing_unconfirmed",
        f"A stay from {reservation['date_from']} was cancelled in the calendar while the "
        "report of its guests to the police was unconfirmed.",
        "Check in UbyPort whether the guests are listed.",
        dedupe_key=f"cancelled_filing_unconfirmed:{reservation['id']}",
        apartment_id=apartment_id,
        reservation_id=reservation["id"],
        params={"date": reservation["date_from"]},
    )
```
Command: `cd App && .venv/bin/python -c "import app.icalsync" 2>&1 | tail -30`. Expected: no output.

**Step 2. Event call site.** In `_cancel_existing_stay`, replace the quoted block (`if not _cancel_reservation_unless_claimed(existing["id"], now):` through `stay_claim.expire_on_cancel(existing)\n    _warn_if_guests_registered(existing, apartment_id, "cancelled")`) with:
```python
    if _running_defers_cancel(existing["id"]) or not _cancel_reservation_unless_claimed(
        existing["id"], now
    ):
        log.warning(
            "ical_cancel_deferred_in_flight apartment_id=%s reservation_id=%s",
            apartment_id,
            existing["id"],
        )
        return True
    from . import claim as stay_claim

    stay_claim.expire_on_cancel(existing)
    _alert_if_filing_in_doubt(existing, apartment_id)
    _warn_if_guests_registered(existing, apartment_id, "cancelled")
```
Command: `cd App && .venv/bin/python -c "import app.icalsync" 2>&1 | tail -30`. Expected: no output.

**Step 3. Sweep call site.** Replace the sweep block quoted in §2 with:
```python
        if _running_defers_cancel(row["id"]) or not _cancel_reservation_unless_claimed(
            row["id"], now
        ):
            deferred_in_flight = True
            log.warning(
                "ical_cancel_deferred_in_flight apartment_id=%s reservation_id=%s",
                feed["apartment_id"],
                row["id"],
            )
            continue
        from . import claim as stay_claim

        stay_claim.expire_on_cancel(row)
        _alert_if_filing_in_doubt(row, feed["apartment_id"])
        _warn_if_guests_registered(row, feed["apartment_id"], "disappeared")
```
Command: `cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass, none failed.

**Step 4. Copy.** Three Edit calls, each `old_string` is the whole existing `notification.cancelled_after_report.detail` line of that file (grep first: `grep -c 'notification.cancelled_after_report.detail' App/app/host_i18n.py App/app/host_vi_i18n.py` must print `2` and `1`; the key appears once per language). Keep the old line and add the two new lines straight after it, same indentation (8 spaces in host_i18n.py, 4 in host_vi_i18n.py). No em dash anywhere.
- host_i18n.py, en block (the line ending `merely moved.",`):
```
        "notification.cancelled_filing_unconfirmed.title": "Stay from %(date)s was cancelled while its police report was unconfirmed.",
        "notification.cancelled_filing_unconfirmed.detail": "UbyPort may already hold the guests of this stay, and we will not send them again. Check in UbyPort whether they are listed. If they are, the register lists guests of a cancelled stay.",
```
- host_i18n.py, cs block (the line starting `"Zkontrolujte, zda byla rezervace`):
```
        "notification.cancelled_filing_unconfirmed.title": "Pobyt od %(date)s byl zrušen, ale nebylo jisté, zda policie hlášení přijala.",
        "notification.cancelled_filing_unconfirmed.detail": "UbyPort už může mít hosty tohoto pobytu a znovu je neodešleme. Zkontrolujte v UbyPortu, zda jsou uvedeni. Pokud ano, registr eviduje hosty zrušeného pobytu.",
```
- host_vi_i18n.py:
```
    "notification.cancelled_filing_unconfirmed.title": "Lượt lưu trú từ %(date)s bị hủy khi chưa rõ cảnh sát đã nhận khai báo hay chưa.",
    "notification.cancelled_filing_unconfirmed.detail": "UbyPort có thể đã có khách của lượt lưu trú này và chúng tôi sẽ không gửi lại. Hãy kiểm tra trong UbyPort xem họ có trong danh sách không. Nếu có, sổ đăng ký đang lưu khách của một lượt lưu trú đã hủy.",
```
Command: `cd App && .venv/bin/python -c "from app import host_i18n as h; print([h.translate(l,'notification.cancelled_filing_unconfirmed.title',date='D')[:25] for l in ('en','cs','vi')])" 2>&1 | tail -30`. Expected: three non-key strings, each containing `D`.

**Step 5. Tests.**
(a) `App/tests/test_icalsync.py` top: replace `import json\nimport time\n\nimport pytest` with `import json\nimport time\nfrom datetime import datetime, timedelta, timezone\n\nimport pytest`, and `from app import config, db, icalsync` with `from app import alerts, config, db, icalsync`.
(b) `App/tests/test_alert_language.py`: add this line in `STORED_KINDS` straight after the `"cancelled_after_report": {...},` line: `    "cancelled_filing_unconfirmed": {"date": "2026-09-11"},`.
(c) Append to the end of `App/tests/test_icalsync.py`:
```python
def _cancel_feed(monkeypatch):
    monkeypatch.setattr(
        icalsync,
        "fetch_feed",
        lambda _url: MOVED_STAY_FEED.replace(
            "SUMMARY:Reserved", "SUMMARY:Reserved\nSTATUS:CANCELLED"
        ),
    )


def _seed_submission(reservation_id, guest_id, state, *, hours_old=0, point=False):
    apartment_id = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,)
    )["apartment_id"]
    created = (
        (datetime.now(timezone.utc) - timedelta(hours=hours_old))
        .replace(microsecond=0)
        .isoformat()
    )
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": created,
            "mode": "auto",
            "state": state,
            "guest_ids": json.dumps([guest_id]),
        },
    )
    if point:
        db.update("guest", guest_id, {"submission_id": submission_id})
    return submission_id


def _status(reservation_id):
    return db.query_one("SELECT status FROM reservation WHERE id = ?", (reservation_id,))["status"]


def test_a_cancel_event_with_an_unconfirmed_filing_cancels_and_alerts(monkeypatch, tmp_path):
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    _seed_submission(reservation_id, guest_id, "outcome_unknown", point=True)
    _cancel_feed(monkeypatch)

    stats = _sync(feed_id)

    assert _status(reservation_id) == "cancelled"
    assert stats["cancelled"] == 1
    alert = alerts.open_alert(f"cancelled_filing_unconfirmed:{reservation_id}")
    assert alert is not None and alert["level"] == "warning"


def test_a_cancel_event_with_a_settled_filing_raises_no_unconfirmed_alert(monkeypatch, tmp_path):
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    _seed_submission(reservation_id, guest_id, "ok", point=True)
    _cancel_feed(monkeypatch)

    _sync(feed_id)

    assert _status(reservation_id) == "cancelled"
    assert alerts.open_alert(f"cancelled_filing_unconfirmed:{reservation_id}") is None


def test_a_fresh_running_filing_defers_the_cancel_until_the_sweep_recovers_it(monkeypatch, tmp_path):
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    submission_id = _seed_submission(reservation_id, guest_id, "running")
    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES (?, 'old', ?)",
        (guest_id, time.time() - 3600),
    )
    _cancel_feed(monkeypatch)

    stats = _sync(feed_id)

    assert _status(reservation_id) == "active"
    assert stats["cancelled"] == 0
    assert db.query_one("SELECT body_sha256 FROM ical_feed WHERE id = ?", (feed_id,))["body_sha256"] is None
    assert alerts.open_alert(f"cancelled_filing_unconfirmed:{reservation_id}") is None

    db.update("submission", submission_id, {"state": "outcome_unknown"})
    db.update("guest", guest_id, {"submission_id": submission_id})
    stats = _sync(feed_id)

    assert _status(reservation_id) == "cancelled"
    assert stats["cancelled"] == 1
    assert alerts.open_alert(f"cancelled_filing_unconfirmed:{reservation_id}") is not None


def test_an_old_running_filing_does_not_hold_the_cancel_for_ever(monkeypatch, tmp_path):
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    _seed_submission(reservation_id, guest_id, "running", hours_old=2)
    _cancel_feed(monkeypatch)

    stats = _sync(feed_id)

    assert _status(reservation_id) == "cancelled"
    assert stats["cancelled"] == 1
    assert alerts.open_alert(f"cancelled_filing_unconfirmed:{reservation_id}") is not None


def _vanished_stay_with_guest(tmp_path, monkeypatch, name):
    feed_id, apartment_id, uids = _stored_stays(
        tmp_path, monkeypatch, name, stored=10, returned=9
    )
    gone = db.query_one(
        "SELECT id FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, uids[9]),
    )["id"]
    now = db.utcnow()
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": gone,
            "stay_from": "2099-03-01",
            "stay_to": "2099-03-05",
            "entered_by": "guest",
            "submit_state": "pending",
            "created_at": now,
            "updated_at": now,
        },
    )
    return feed_id, gone, guest_id


def test_a_vanished_stay_with_an_unconfirmed_filing_cancels_and_alerts(monkeypatch, tmp_path):
    feed_id, gone, guest_id = _vanished_stay_with_guest(tmp_path, monkeypatch, "sweep-unknown.sqlite3")
    _seed_submission(gone, guest_id, "outcome_unknown", point=True)

    stats = _sync(feed_id)

    assert _status(gone) == "cancelled"
    assert stats["cancelled"] == 1
    assert alerts.open_alert(f"cancelled_filing_unconfirmed:{gone}") is not None


def test_a_vanished_stay_with_a_fresh_running_filing_is_deferred(monkeypatch, tmp_path):
    feed_id, gone, guest_id = _vanished_stay_with_guest(tmp_path, monkeypatch, "sweep-running.sqlite3")
    _seed_submission(gone, guest_id, "running")

    stats = _sync(feed_id)

    assert _status(gone) == "active"
    assert stats["cancelled"] == 0
    assert db.query_one("SELECT body_sha256 FROM ical_feed WHERE id = ?", (feed_id,))["body_sha256"] is None
```
Command: `cd App && .venv/bin/python -m pytest tests/test_icalsync.py -q --tb=short -x -k "unconfirmed or fresh_running or old_running" 2>&1 | tail -30`. Expected: 6 passed. (If `_sync` returns no `cancelled` key for the sweep, the 1139 sweep test shows the shape: reuse its assertions.)

**Step 6. Revert bite.** (Each: run, see FAIL, `git checkout App/app/icalsync.py`, run again, see pass.)
(a) `sed -i 's/^    _alert_if_filing_in_doubt(existing, apartment_id)$/    pass/' App/app/icalsync.py && sed -i 's/^        _alert_if_filing_in_doubt(row, feed\["apartment_id"\])$/        pass/' App/app/icalsync.py`, then `cd App && .venv/bin/python -m pytest tests/test_icalsync.py -q --tb=line -k "unconfirmed or old_running" 2>&1 | tail -30`. Expected: failures (at least `..._cancels_and_alerts` x2 and `old_running`). Then `git checkout App/app/icalsync.py` and the same pytest: pass.
(b) `sed -i 's/_running_defers_cancel(existing\["id"\]) or not/False or not/; s/_running_defers_cancel(row\["id"\]) or not/False or not/' App/app/icalsync.py`, then `-k "fresh_running"`. Expected: both `fresh_running` tests FAIL. `git checkout App/app/icalsync.py`, rerun: pass.

**Step 7. Docs.** In `docs/OPERATIONS.md`, after the table row that starts `| \`cancelled_after_report\``, add:
`| \`cancelled_filing_unconfirmed\` | warning | A stay was cancelled in the calendar (or vanished) while a guest of it was in a \`running\` or \`outcome_unknown\` filing, so the register may hold guests of a cancelled stay. A \`running\` filing younger than 30 minutes defers the cancel instead. | Not auto-cleared; the host checks UbyPort. |`
Command: `grep -c cancelled_filing_unconfirmed docs/OPERATIONS.md`. Expected: `1`.

**Step 8. Area run and lint.** `cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_go_host_i18n.py tests/test_stale_submission.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. Then from the repo root `python3 scripts/context_lint.py | tail -3`: OK.

## 5. Do not touch

`App/app/reporting.py`, `claim.py`, `expire_on_cancel`, `_send_in_flight` behaviour (only its tail is moved into a helper with the same query), `go/`, migrations, `host_i18n` Go catalogs (`i18n_keys.txt` is not edited). Hard rules: 1 (filing correctness first), 4 (no dependency), 5 (SQL through `db`), 9 (copy: no em dash, one explanation in one place).

## 6. Commands

Those in each step. Step 8 is the test-map row for calendar and alerts and copy. No full suite.

## 7. Acceptance

- [ ] Event and sweep cancel both go through `_running_defers_cancel` and `_alert_if_filing_in_doubt`.
- [ ] 6 new tests pass; both revert bites fail then pass.
- [ ] No sentinel `%(` in the new cards; en, cs, vi keys exist.
- [ ] Step 8 green, lint OK, only §3 files changed.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear.

## 9. Report

Write `docs/tasks/1148-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines, §7 ticked, both revert-bite results, deviations, questions, owner steps left (push the branch; open the PR as a draft and keep it until 1148b is ready).

## Risk list (for the reviewer)

`_running_submission_covers_stay` (JSON overlap, 30 min cutoff string compare against `db.utcnow()` format), the two call sites (a deferred sweep must drop the digest), `_alert_if_filing_in_doubt` (dedupe key), the moved `_send_in_flight` tail (same query).

## Owner steps

1. Nothing before review. After 1148b is also green, merge both PRs with `scripts/merge-pr-on-green.sh`.
