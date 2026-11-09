# 1070: File registered guests at the deadline cap

Status: todo
Depends on: owner yes (owner question 3 in docs/tasks/1069-report.md) | Base commit: 0d851ca4ae25776e1e4ddcf3b2fa4b4e25f126da | Branch: task/1070-file-at-deadline-cap
Executor: Fable 5.2 (Tier A) | Fits one session: 30 tool calls, 60k tokens
Review: a fresh Fable reviews this brief before it runs, and the full diff afterwards.

**HIGH RISK (filing).** Exact diff only. Apply the diff and the test file below as written; do not redesign.

## 1. Objective

Registered, valid guests of a stay are filed no later than the existing deadline cap (6 h before the legal deadline), even when the stay is short of its declared count or has no count. Today `due_for_automatic_send` says no until quiet completion (12 h without a guest-row write, plus a sweep), so a write after about deadline minus 12 h gets the registered people filed after the legal deadline (1069 report, bug 9, summary 3a, Q5).

## 2. Context

Rules (AGENTS.md hard rule 1 and [UBYPORT_CORE](../UBYPORT_CORE.md)): filing correctness beats every other feature; "Auto-submit & scheduler: stays never filed or filed twice" is the risk row this touches. [submit_state](../OPERATIONS.md#the-submit_state-state-machine): `sent` is never resent automatically.

What must stay exactly as it is:

- `manual` properties never file on their own (`due_for_automatic_send` returns False first; the sweep skips `automation_mode = 'manual'`).
- An open `ubyport_auth_failed:<apartment_id>` alert pauses the sweep and the save-time send for that property (`sweep`, `submit_stay_if_complete`). No change.
- No double filing: `collect_sendable` skips `SENT` rows, `claim_sendable` leases each guest in `submission_claim` and re-reads the row. No change.
- `registration_completed_at` and the 12-quiet-hours rule (`refresh_registration_completed_at`, `HEADCOUNT_QUIET_HOURS = 12`) are unchanged. This change does not set the stamp, so door codes (`door_codes.py`), lifecycle mails (`lifecycle_mail.py`) and fees, which read the stamp, are unchanged.
- Each guest still has to pass `guest_is_complete`, `signature_dates_stale`, the reportable check and the retry bound in `collect_sendable` before it is sent.
- A person who registers after the cap filing is filed by the existing path: the next sweep's `collect_sendable` (the cap time is already past, so the new row is due; the filed rows are `SENT` and skipped).

Anchor excerpt, `App/app/reporting.py` (`due_for_automatic_send`, about lines 1090-1119), must be found verbatim:

```python
    mode = apartment["automation_mode"]
    if mode == "manual":
        return False
    # No completion, no send. The sweep refreshes the quiet-window completion
    # before it asks, so a stay that has gone quiet is not held open for ever;
    # eligibility still comes from the guests' own forms, never from the fact
    # that this code was deployed.
    completed_at = reservation["registration_completed_at"]
    if not completed_at:
        return False
```

The only caller that asks this function is `collect_sendable` (`reporting.py` about line 1498, `if not ignore_schedule:`); host sends and the completion send pass `ignore_schedule=True` and never reach it.

Dates (computed with `deadlines.reporting_deadline`): check-in Mon 2026-11-09, deadline Wed 2026-11-11 23:59:59 Prague (CET) = 22:59:59 UTC, cap 17:59:59 Prague = 16:59:59 UTC.

Time pattern: the existing filing tests freeze time by passing `now=` to `due_for_automatic_send` (`App/tests/test_deadlines.py::test_scheduled_send_is_pulled_forward_to_the_deadline_margin`) and drive the sweep on the real clock with timestamps relative to `datetime.now` (`App/tests/test_send_controls.py`). The new tests do the same: unit tests with `now=`, sweep tests with a stay anchored ten days in the past and guest rows written one hour ago.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/reporting.py` | edit | `due_for_automatic_send`: when no completion stamp, return True once the cap time has passed |
| `App/tests/test_deadline_cap_filing.py` | create | 11 tests, (a) to (f) below |
| `docs/tasks/1070-report.md` | create | the report |

No other file may change.

## 4. Steps

0. **Orchestrator adds the decision line.** Placeholder: before this brief runs, the orchestrator appends the owner's yes to owner question 3 (1069 report) to `docs/context/decisions.md` and replaces this step with the line it added. If this step still reads "Placeholder", STOP (§8): there is no owner yes.

1. Branch from main.
   ```bash
   git fetch origin main 2>&1 | tail -3
   git checkout -b task/1070-file-at-deadline-cap origin/main 2>&1 | tail -3
   ```
   Expected: `Switched to a new branch 'task/1070-file-at-deadline-cap'`.

2. Check the anchor.
   ```bash
   grep -n "    # No completion, no send. The sweep refreshes the quiet-window completion" App/app/reporting.py | head -5
   ```
   Expected: exactly one line (about 1093). Zero or two lines: STOP.

3. Apply the code diff. Write it to a file exactly as below, check it, apply it.
```bash
cat > /tmp/1070.diff <<'EOF'
diff --git a/App/app/reporting.py b/App/app/reporting.py
--- a/App/app/reporting.py
+++ b/App/app/reporting.py
@@ -1090,29 +1090,33 @@ def due_for_automatic_send(
     mode = apartment["automation_mode"]
     if mode == "manual":
         return False
-    # No completion, no send. The sweep refreshes the quiet-window completion
-    # before it asks, so a stay that has gone quiet is not held open for ever;
-    # eligibility still comes from the guests' own forms, never from the fact
-    # that this code was deployed.
-    completed_at = reservation["registration_completed_at"]
-    if not completed_at:
-        return False
-    completed = _as_utc(completed_at)
-    if completed is None:
-        return False
     current = now or datetime.now(timezone.utc)
     if current.tzinfo is None:
         current = current.replace(tzinfo=timezone.utc)
-    delay = timedelta(
-        hours=0 if mode == "immediate" else (apartment["submit_after_hours"] or 24)
-    )
-    send_at = completed.astimezone(timezone.utc) + delay
     if anchor is _ANCHOR_UNSET:
         anchor = reservation_deadline_anchor(reservation)
+    latest = None
     if anchor is not None:
         deadline_local = deadlines.reporting_deadline(anchor) - timedelta(
             hours=AUTOMATIC_SEND_DEADLINE_MARGIN_HOURS
         )
         latest = deadline_local.replace(tzinfo=ZoneInfo(config.TIMEZONE)).astimezone(timezone.utc)
+    # Before the deadline margin: no completion, no send. The sweep refreshes
+    # the quiet-window completion before it asks, so a stay that has gone
+    # quiet is not held open for ever. From the margin on (brief 1070), the
+    # people already registered are filed even when the stay is short of its
+    # declared count or has none: waiting for the quiet window could file them
+    # after the legal deadline. Each guest is still checked for a complete form
+    # by the caller, SENT rows are never collected, and anyone who registers
+    # later is filed by the next sweep.
+    completed_at = reservation["registration_completed_at"]
+    completed = _as_utc(completed_at) if completed_at else None
+    if completed is None:
+        return latest is not None and current.astimezone(timezone.utc) >= latest
+    delay = timedelta(
+        hours=0 if mode == "immediate" else (apartment["submit_after_hours"] or 24)
+    )
+    send_at = completed.astimezone(timezone.utc) + delay
+    if latest is not None:
         send_at = min(send_at, latest)
     return current.astimezone(timezone.utc) >= send_at
EOF
git apply --check /tmp/1070.diff && git apply /tmp/1070.diff && git diff --stat | tail -3
```
   Copy the block exactly (no indent). Expected: `App/app/reporting.py | 32 ++++++++++++----------` and `1 file changed, 18 insertions(+), 14 deletions(-)`. `git apply --check` fails: STOP (do not hand-edit).

   What the diff does: the cap time (`latest`) is computed first. With a completion stamp, nothing changes (`min(completed + delay, latest)`). Without one (or with a stamp that does not parse), the stay is due once `latest` has passed; with no deadline anchor it stays not due, as today. `manual` still returns False on the first line.

4. Create `App/tests/test_deadline_cap_filing.py` with exactly this content (Write tool):

```python
"""Brief 1070: registered guests are filed by the deadline cap.

A stay short of its declared count, or with no count at all, completes only
after 12 quiet hours. The deadline cap (6 h before the legal deadline) must
file the people already registered without waiting for that, and nothing
else about filing may change.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app import alerts, config, db, reporting
from app.ubyport.client import SubmissionResult
from tests.test_send_controls import SIGNATURE

# Check-in Mon 9 Nov 2026. Legal deadline in code: Wed 11 Nov 23:59:59 Prague
# (CET, UTC+1) = 22:59:59 UTC. Cap: 17:59:59 Prague = 16:59:59 UTC.
CHECK_IN = "2026-11-09"
LAST_WRITE = "2026-11-11T13:00:00+00:00"  # 14:00 Prague on the deadline day
BEFORE_CAP = datetime(2026, 11, 11, 16, 59, tzinfo=timezone.utc)
AFTER_CAP = datetime(2026, 11, 11, 17, 0, tzinfo=timezone.utc)
DEADLINE_UTC = datetime(2026, 11, 11, 22, 59, 59, tzinfo=timezone.utc)


def _fresh_db(monkeypatch, tmp_path, name):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / name)
    db.init_db()


def _stay(mode, *, date_from, expected, guests, updated_at=None, token="tok-1070"):
    """One apartment, one stay, ``guests`` complete guest forms."""
    now = db.utcnow()
    touched = updated_at or now
    entity_id = db.insert(
        "legal_entity",
        {"name": "Test", "seat": "Praha", "ico": "12345678", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Flat",
            "city_en": "Prague",
            "permalink_token": token,
            "automation_mode": mode,
            "submit_after_hours": 24,
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    start = date.fromisoformat(date_from)
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"stay-{token}",
            "date_from": date_from,
            "date_to": (start + timedelta(days=30)).isoformat(),
            "status": "active",
            "expected_guests_override": expected,
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_ids = [_add_guest(reservation_id, i, touched) for i in range(guests)]
    return apartment_id, reservation_id, guest_ids


def _add_guest(reservation_id, index, touched):
    return db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": f"Smith{chr(65 + index)}",
            "first_name": "John",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": f"P123456{index}",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "is_lead": 1 if index == 0 else 0,
            "entered_by": "host",
            "signature_png": SIGNATURE,
            "signed_at": touched,
            "identity_verified_at": touched,
            "submit_state": reporting.PENDING,
            "created_at": touched,
            "updated_at": touched,
        },
    )


def _reservation(reservation_id):
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))


def _states(guest_ids):
    return [
        db.query_one("SELECT submit_state FROM guest WHERE id = ?", (gid,))["submit_state"]
        for gid in guest_ids
    ]


class _FakeClient:
    """Accepts every record and remembers the size of each batch."""

    def __init__(self):
        self.batches = []

    def submit(self, _header, guests):
        self.batches.append(len(guests))
        return SubmissionResult(
            endpoint="test",
            request_xml="<request/>",
            response_xml="<response/>",
            record_errors=["" for _ in guests],
        )


def _fake_register(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client)
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])
    return client


def _past_check_in():
    # Ten days ago: the cap and the deadline have long passed on the real clock.
    return (date.today() - timedelta(days=10)).isoformat()


def _an_hour_ago():
    # Well inside the 12 quiet hours, so the stay cannot complete quietly.
    return (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat()


# --- the decision itself, on a frozen clock (now=) ---------------------------


def test_a_short_stay_is_due_at_the_cap_before_the_deadline(monkeypatch, tmp_path):
    """(a) 2 of 3 registered, last write 14:00 on the deadline day."""
    _fresh_db(monkeypatch, tmp_path, "cap-a.db")
    apartment_id, reservation_id, _ids = _stay(
        "scheduled", date_from=CHECK_IN, expected=3, guests=2, updated_at=LAST_WRITE
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = _reservation(reservation_id)
    assert not reservation["registration_completed_at"]

    assert reporting.due_for_automatic_send(apartment, reservation, now=BEFORE_CAP) is False
    assert reporting.due_for_automatic_send(apartment, reservation, now=AFTER_CAP) is True
    assert AFTER_CAP < DEADLINE_UTC


def test_a_stay_with_no_expected_count_is_due_at_the_cap(monkeypatch, tmp_path):
    """(b) The host entered the stay; no count was ever declared."""
    _fresh_db(monkeypatch, tmp_path, "cap-b.db")
    apartment_id, reservation_id, _ids = _stay(
        "immediate", date_from=CHECK_IN, expected=None, guests=1, updated_at=LAST_WRITE
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = _reservation(reservation_id)
    assert reporting.expected_guest_count(reservation) is None

    assert reporting.due_for_automatic_send(apartment, reservation, now=BEFORE_CAP) is False
    assert reporting.due_for_automatic_send(apartment, reservation, now=AFTER_CAP) is True


def test_a_completed_stay_keeps_its_schedule(monkeypatch, tmp_path):
    """(c) Completion plus delay, capped as before."""
    _fresh_db(monkeypatch, tmp_path, "cap-c.db")
    apartment = {"automation_mode": "scheduled", "submit_after_hours": 24}
    reservation = {
        "id": -1,
        "date_from": CHECK_IN,
        "registration_completed_at": "2026-11-10T08:00:00+00:00",
    }
    # 24 h after completion is Wed 08:00 UTC, earlier than the cap.
    assert reporting.due_for_automatic_send(
        apartment, reservation, now=datetime(2026, 11, 11, 7, 59, tzinfo=timezone.utc)
    ) is False
    assert reporting.due_for_automatic_send(
        apartment, reservation, now=datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
    ) is True
    # 48 h after completion is later than the cap, so the cap wins.
    apartment["submit_after_hours"] = 48
    assert reporting.due_for_automatic_send(apartment, reservation, now=BEFORE_CAP) is False
    assert reporting.due_for_automatic_send(apartment, reservation, now=AFTER_CAP) is True
    # Immediate sends at completion.
    immediate = {"automation_mode": "immediate", "submit_after_hours": 24}
    assert reporting.due_for_automatic_send(
        immediate, reservation, now=datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    ) is True


def test_a_manual_property_is_never_due(monkeypatch, tmp_path):
    """(d) manual stays manual, before and after the cap and the deadline."""
    _fresh_db(monkeypatch, tmp_path, "cap-d.db")
    apartment = {"automation_mode": "manual", "submit_after_hours": 24}
    reservation = {"id": -1, "date_from": CHECK_IN, "registration_completed_at": None}
    for moment in (AFTER_CAP, DEADLINE_UTC + timedelta(days=3)):
        assert reporting.due_for_automatic_send(apartment, reservation, now=moment) is False


def test_a_stay_without_a_deadline_anchor_still_waits_for_completion(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path, "cap-anchor.db")
    apartment = {"automation_mode": "immediate", "submit_after_hours": 24}
    reservation = {"id": -1, "date_from": None, "registration_completed_at": None}
    assert reporting.due_for_automatic_send(apartment, reservation, now=AFTER_CAP) is False


# --- the sweep, on the real clock (stays anchored in the past) ---------------


def test_the_sweep_files_a_short_stay_past_the_cap(monkeypatch, tmp_path):
    """(a) end to end: filed without waiting for the quiet hours."""
    _fresh_db(monkeypatch, tmp_path, "sweep-a.db")
    client = _fake_register(monkeypatch)
    _apartment_id, reservation_id, guest_ids = _stay(
        "scheduled", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(),
    )

    summary = reporting.sweep()

    assert summary["failed"] == 0
    assert client.batches == [2]
    assert _states(guest_ids) == [reporting.SENT, reporting.SENT]
    # The 12-quiet-hours rule is unchanged: the stay is still not complete.
    assert not _reservation(reservation_id)["registration_completed_at"]


def test_the_sweep_files_a_stay_with_no_expected_count_past_the_cap(monkeypatch, tmp_path):
    """(b) end to end."""
    _fresh_db(monkeypatch, tmp_path, "sweep-b.db")
    client = _fake_register(monkeypatch)
    _apartment_id, reservation_id, guest_ids = _stay(
        "immediate", date_from=_past_check_in(), expected=None, guests=1,
        updated_at=_an_hour_ago(),
    )

    reporting.sweep()

    assert client.batches == [1]
    assert _states(guest_ids) == [reporting.SENT]
    assert not _reservation(reservation_id)["registration_completed_at"]


def test_the_sweep_does_not_file_a_short_stay_before_the_cap(monkeypatch, tmp_path):
    """(c) Before the cap nothing changes: the short stay still waits."""
    _fresh_db(monkeypatch, tmp_path, "sweep-c.db")
    client = _fake_register(monkeypatch)
    _apartment_id, _reservation_id, guest_ids = _stay(
        "immediate", date_from=date.today().isoformat(), expected=3, guests=2,
        updated_at=_an_hour_ago(),
    )

    reporting.sweep()

    assert client.batches == []
    assert _states(guest_ids) == [reporting.PENDING, reporting.PENDING]


def test_the_sweep_leaves_manual_and_auth_failed_properties_alone(monkeypatch, tmp_path):
    """(d) No automatic filing for manual, or while the login is refused."""
    _fresh_db(monkeypatch, tmp_path, "sweep-d.db")
    client = _fake_register(monkeypatch)
    _m_apartment, _m_res, manual_ids = _stay(
        "manual", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(), token="tok-1070-manual",
    )
    locked_apartment, _l_res, locked_ids = _stay(
        "immediate", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(), token="tok-1070-locked",
    )
    alerts.raise_alert(
        "critical",
        "ubyport_auth_failed",
        "Flat: login refused.",
        dedupe_key=f"ubyport_auth_failed:{locked_apartment}",
        apartment_id=locked_apartment,
    )

    reporting.sweep()

    assert client.batches == []
    assert _states(manual_ids + locked_ids) == [reporting.PENDING] * 4


def test_a_later_completion_does_not_file_twice(monkeypatch, tmp_path):
    """(e) Filed at the cap, then the stay completes: nothing is sent again."""
    _fresh_db(monkeypatch, tmp_path, "sweep-e.db")
    client = _fake_register(monkeypatch)
    apartment_id, reservation_id, guest_ids = _stay(
        "immediate", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(),
    )
    reporting.sweep()
    assert client.batches == [2]

    # The host lowers the count: the stay completes now.
    db.update("reservation", reservation_id, {"expected_guests_override": 2})
    reporting.submit_stay_if_complete(apartment_id, reservation_id)
    reporting.sweep()

    assert _reservation(reservation_id)["registration_completed_at"]
    assert client.batches == [2]
    assert _states(guest_ids) == [reporting.SENT, reporting.SENT]


def test_a_person_who_registers_after_the_cap_filing_is_filed(monkeypatch, tmp_path):
    """(f) The late person goes alone; the filed two are not sent again."""
    _fresh_db(monkeypatch, tmp_path, "sweep-f.db")
    client = _fake_register(monkeypatch)
    _apartment_id, reservation_id, guest_ids = _stay(
        "scheduled", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(),
    )
    reporting.sweep()
    assert client.batches == [2]

    late_id = _add_guest(reservation_id, 2, db.utcnow())
    reporting.sweep()

    assert client.batches == [2, 1]
    assert _states(guest_ids + [late_id]) == [reporting.SENT] * 3
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_deadline_cap_filing.py -q --tb=short 2>&1 | tail -30`
   Expected: `11 passed`.

5. Prove the tests test the change: run them on the old code, then put the change back.
   ```bash
   git diff App/app/reporting.py > /tmp/1070-applied.diff
   git checkout -- App/app/reporting.py
   (cd App && .venv/bin/python -m pytest tests/test_deadline_cap_filing.py -q --tb=no 2>&1 | tail -3)
   git apply /tmp/1070-applied.diff && git diff --stat | tail -2
   ```
   Expected on the old code: `6 failed, 5 passed` (the two `due_at_the_cap` tests, the two `sweep_files` tests, `later_completion`, `registers_after`). After `git apply`: `App/app/reporting.py` changed again, 18 insertions, 14 deletions.

6. Filing row of the test-map, plus the existing send-control tests (they hold the other `due_for_automatic_send` cases).
   ```bash
   cd App && .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py tests/test_send_controls.py -q --tb=short -x 2>&1 | tail -30
   ```
   Expected: all passed, 0 failed (the brief writer saw 430 passed plus the 4 `test_ubyport_sample_pdf.py` tests, which need `pypdf`/`pdfplumber` from `requirements-dev.txt`). `test_send_controls.py::test_legacy_completed_reservation_is_not_auto_eligible_on_deploy` must still pass unchanged.

7. Lint, from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: `OK` (a `status.md` over-cap line or a "named by open briefs" warning for `App/app/reporting.py` is acceptable; note it in the report).

8. Write `docs/tasks/1070-report.md` (§9), set this brief to `Status: review`, commit the three files of §3 and this brief, push the branch, open the PR (base `main`). If `gh` is read-only, hand the owner `gh pr create --base main --head task/1070-file-at-deadline-cap --fill`. Do not merge.

## 5. Do not touch

- Every file not in §3. In particular `refresh_registration_completed_at`, `_forms_quiet_for`, `HEADCOUNT_QUIET_HOURS`, `AUTOMATIC_SEND_DEADLINE_MARGIN_HOURS`, `submit_stay_if_complete`, `sweep`, `collect_sendable`, `claim_sendable`, `door_codes.py`, `lifecycle_mail.py`, mail templates, `stay_fee*.py`, `host_i18n.py`.
- Existing tests: none may be edited or deleted.
- Hard rules 1 (filing correctness), 3 (public repo), 8 (never push to `main`; merge only with `scripts/merge-pr-on-green.sh`, by the owner's flow).

## 6. Commands

Listed in steps 3-7 with expected results. Never the full suite.

## 7. Acceptance

- [ ] Step 0 holds the owner's decision line (not the placeholder).
- [ ] `git diff --stat origin/main` shows only the §3 files plus this brief; `App/app/reporting.py` is 18 insertions, 14 deletions.
- [ ] `tests/test_deadline_cap_filing.py`: 11 passed on the new code; 6 failed, 5 passed on the old code (step 5).
- [ ] Step 6: 0 failed.
- [ ] `python3 scripts/context_lint.py`: OK.

## 8. Stop and ask

Stop, and write the report, if: step 0 still says "Placeholder"; the step 2 anchor is not found exactly once; `git apply --check` fails; a test fails twice; step 5 does not give `6 failed, 5 passed`; a file outside §3 needs a change; you reach 25 tool calls or about 50k tokens; you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/1070-report.md` (600 tokens at most), `Status: review` here: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

Read the full diff of `App/app/reporting.py` and the whole new test file. Check:

1. With a stamp, the result is identical to before (`min(completed + delay, latest)`; no anchor, no cap).
2. Without a stamp: due only when an anchor exists and `now >= latest`; `manual` still False first.
3. Edge cases the change brings, for the review to accept or refuse:
   - A stay with one started-but-invalid form: its valid co-guests are now filed at the cap; the invalid one is still skipped by `guest_is_complete` (this also ends 1069 bug 1's "co-guests wait" at the cap).
   - A stored stamp that does not parse is now treated as no stamp (filed at the cap), where it used to block automatic filing for ever.
   - First sweep after deploy: every active stay already past its cap with registered, unsent, non-manual guests and no stamp is filed in that sweep (late; UbyPort answers 112, which is accepted). That is the point of the change, but it can be a burst. The owner can count them first (step 1 below).
   - People filed at the cap are `SENT`, so the guest link can no longer edit or remove them (`guest_form_locked`); same as after any filing today.
   - Push/celebration hooks that react to `SENT` fire at the cap filing, through the existing `submit_batch` path; no new mail.
4. The new tests use the real clock only with stays ten days in the past or today, so they do not depend on the run date.

## Owner steps

1. Before merging, optional: ask the orchestrator for the read-only production count of active, non-manual stays past their cap with unsent complete guests and no `registration_completed_at`, to know how many will be filed (late) on the first sweep after deploy.
2. Review the PR, then merge it with `scripts/merge-pr-on-green.sh` as usual.
3. Deploy as usual. Then open the dashboard after the next sweep (10 minutes) and check that the stays shown "Due now" or "Overdue" with registered people now show those people as filed.
