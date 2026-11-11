# 1121: A guest blocked as a duplicate stays blocked when an edit changes no reported field

Status: review
Depends on: PR #920 merged to main (tables and pin tests present) | Base commit: main after PR #920 | Branch: task/1121-sm-duplicate-blocked-edit
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK: police filing (`guest.submit_state`). Exact diffs only. Change nothing else.

## Open questions (for the orchestrator or owner; this brief does not decide them)

1. **Host banner copy now overstates.** `App/app/templates/guest_form_admin.html:36` shows, for any `error` or `blocked` guest, `guest.admin.banner.rejected_help` = "Correct the data and save. That puts it back in the queue." (`App/app/host_i18n.py:4604`). After this brief, saving a duplicate-blocked guest without changing a reported field does **not** put it back in the queue, and the save flash (`flash.guests.saved`, `App/app/routes/admin.py:4757`) says nothing about it. Not changed here (no copy change in this brief).
2. **"Reported field" is the wire record, not the register's duplicate key.** This brief reuses `reporting.filed_record_changed` (`App/app/reporting.py:239`), which compares `guest_payload()` (`reporting.py:180`), the same test host `guest_update` already uses for `sent` rows (`routes/admin.py:4687`). `docs/UBYPORT_CORE.md:44-45` says the register keys duplicates on dates, surname, first name, birth date, nationality, document number and purpose, "not note, visa or address". So an edit that changes only the note, visa number or address still resets to `pending` (allowed by the ruling) and the next send will most likely be answered 150 again. No code holds the duplicate-key list, so this brief does not invent one. Owner to rule whether a later brief should narrow the reset to the duplicate key.
3. **Normalisation falls back to today.** The comparison is on normalised values (`validation.normalise_guest`, names upper-cased). A legacy row whose stored value the form now normalises differently (for example a lower-case surname stored before normalisation) reads as a reported-field change and resets to `pending`, which is today's behaviour, not a new risk.
4. **A new signature alone keeps the block.** The signature is not in `guest_payload()`, so it is not reported; a host or guest who only re-signs leaves a duplicate-blocked guest `blocked`. This follows the ruling literally.
5. **OPERATIONS.md text after merge.** Brief 1118's new section says "Changes with brief 1121: an edit that changes no field reported to the police will leave the guest `blocked`". Once this merges, that sentence describes the code; the orchestrator updates the tense in a later docs change (not here, to avoid two open briefs on `docs/OPERATIONS.md`).
6. **Line cites in brief 1105 have moved** on the PR #920 branch: `admin.py` 4722-4730 is now 4718-4729; `guest.py` 2523 is now 2568, 2345 is now 2390. The anchors below are quoted text, not line numbers.

## 1. Objective

A guest that the police register refused as a duplicate (`submit_state` `blocked`, `last_errors` naming the duplicate) must stay `blocked` when a host edit (`guest_update`) or a guest form save (`guest_form_save`) changes no field reported to the police. Today any such edit sets `pending`, clears `last_errors` and resets `submit_attempts`, which removes the resend refusal and lets the next sweep send a record the register cannot accept, adding another duplicate against the host.

## 2. Context

Owner ruling (2026-11-11, "do the recommended", brief 1118 Rulings item 1): "An edit that changes no field reported to the police must leave a duplicate-blocked guest `blocked`; an edit to a reported field may reset it. Reason: a second duplicate cannot be accepted and counts against the host."

Rules: SQL only through `App/app/db.py` helpers; keep the existing compare-and-set (`db.update_if(..., {"submit_state": <old state>}, ...)`) unchanged; no copy, template, mail, migration or dependency change. No Go twin exists: `go/internal/hostweb` has no guest edit handler, and every Go file that names `submit_state` is in `go/internal/ubyport` or `go/internal/ical` (sweep, outcome, collect, recovery, stay dates) or only reads it (`go/internal/calendar/handler.go:119`). The Go sweep already skips a duplicate-blocked guest (`go/internal/ubyport/collect.go:211`: `if c.submitState == collectGuestBlocked && blockedAsDuplicate(c.lastErrors) {`), so keeping the state `blocked` protects both sweeps.

Excerpts. Each must exist verbatim; if one is not found, STOP (section 8).

`App/app/reporting.py` (lines 239-245), the existing "reported field" test, used today for `sent` rows:

```python
def filed_record_changed(stored, proposed, reservation) -> bool:
    """Would saving ``proposed`` make the house book differ from what was filed?

    Compared as the UbyPort record, so a stay date left empty (which files the
    booking's dates) is not mistaken for a change.
    """
    return guest_payload(stored, reservation) != guest_payload(proposed, reservation)
```

`App/app/reporting.py` (lines 1303-1309), the duplicate predicate:

```python
def blocked_as_duplicate(guest) -> bool:
    """True when UbyPort refused this record because it already holds it."""
    try:
        stored = guest["last_errors"] or ""
    except (IndexError, KeyError):
        return False
    return any(uby_errors.is_duplicate(part) for part in stored.split(" | "))
```

`App/app/reporting.py` (lines 1586-1593), how `collect_sendable` uses it (the exact predicate this brief reuses: state `BLOCKED` and `blocked_as_duplicate`):

```python
        if guest["submit_state"] == BLOCKED and not allow_resend:
            continue
        # allow_resend is the host overriding caution, not overriding the law.
        # A record blocked because the register already holds it cannot be
        # accepted on a second try, so sending it again buys nothing and adds
        # another unjustified duplicate against the host.
        if guest["submit_state"] == BLOCKED and blocked_as_duplicate(guest):
            continue
```

`App/app/routes/admin.py` (lines 4718-4736), `guest_update`, the state writes:

```python
    if guest["submit_state"] == reporting.SENT:
        # Already filed: the record in the register is what it is. The host's
        # edit is saved, but the state (and so the proof pointer) is kept.
        pass
    elif not validation.guest_is_reportable(payload["nationality"]):
        payload["submit_state"] = reporting.NOT_REQUIRED
    elif guest["submit_state"] in (reporting.ERROR, reporting.BLOCKED, reporting.NOT_REQUIRED):
        # Rule 10.4(5): correcting a rejected record must make it sendable again.
        payload["submit_state"] = reporting.PENDING
        payload["last_errors"] = None
        # The retry budget restarts too, or a record the sweep had given up on
        # would stay given up on even after the host fixed what was wrong.
        payload["submit_attempts"] = 0
    if not db.update_if(
        "guest",
        guest_id,
        payload,
        {"submit_state": guest["submit_state"]},
```

When `update_if` updates zero rows, `guest_update` returns `_back(f"/guests/{guest_id}", err=_flash(request, "flash.error.guest_changed_retry"))` (line 4741). This brief does not change that.

`App/app/routes/guest.py` (lines 2568-2573 and 2594-2600), `guest_form_save`: the payload always writes `submit_state` and `last_errors`, then resets attempts:

```python
            "submit_state": (
                reporting.NOT_REQUIRED
                if not validation.guest_is_reportable(values["nationality"])
                else reporting.PENDING
            ),
            "last_errors": None,
```

```python
    if reporting.guest_correction_resets_attempts(existing):
        # Rule 10.4(5): a correction makes the record sendable again, and a
        # guest fixing their own form is a correction like any other. Without
        # this the sweep kept skipping the row at SUBMISSION_MAX_AUTO_ATTEMPTS
        # for ever while the stranded-records card resolved itself, so the
        # guest was never filed and nothing said so.
        payload["submit_attempts"] = 0
```

Then (lines 2604-2614) the edit is a compare-and-set on `{"submit_state": existing["submit_state"]}`; on zero rows updated it returns `_unavailable(request, lang, "already_filed", 403, token, reservation_id=reservation_id)`. This brief does not change that. A `sent` row never reaches this code (refused at line 2390).

Pin test `App/tests/test_sm_guest_submit_state.py`: it finds writes by the patterns `"submit_state": <x>`, `["submit_state"] = <x>`, `submit_state=<x>` and `UPDATE guest SET submit_state`. This brief adds none of these (it adds `del payload["submit_state"]`, a `pass` branch and a helper that only reads the state), removes none, and changes no guard. `blocked -> pending` stays (a reported-field edit). So `PINNED` and `reporting.TRANSITIONS` do **not** change; step 9 proves it. The new helper must not contain the word `TRANSITIONS` (`test_nothing_reads_transitions_at_runtime` counts it in `reporting.py`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_submission_duplicate_blocked_edit.py` | Create | Failing-first tests (a)-(d) for both edit paths |
| `App/app/reporting.py` | Edit | Add `edit_keeps_duplicate_block` after `blocked_as_duplicate` |
| `App/app/routes/admin.py` | Edit | `guest_update`: one new `elif` branch that keeps the state |
| `App/app/routes/guest.py` | Edit | `guest_form_save`: drop the state and error text from the payload, skip the attempts reset |
| `docs/tasks/1121-report.md` | Create | Report |
| `docs/tasks/1121-sm-duplicate-blocked-edit.md` | Edit | `Status:` line only |

No other file may change. `App/tests/test_sm_guest_submit_state.py` and `reporting.TRANSITIONS` stay unchanged.

## 4. Steps

Run every command from `App/` unless it says otherwise. Commit after each step with the message `1121 step k`.

1. Create `App/tests/test_submission_duplicate_blocked_edit.py` with exactly this content:

```python
"""Brief 1121: an edit that changes nothing reported keeps a duplicate block.

A guest the register refused as a duplicate (submit_state 'blocked' and
last_errors naming the duplicate) cannot be accepted on a second try, so
collect_sendable skips it even on a deliberate resend. Before 1121 any host or
guest edit set 'pending', cleared last_errors and reset submit_attempts, which
removed that skip and let the next sweep send the record again. An edit to a
field reported to the police (reporting.filed_record_changed) still resets, and
a guest blocked for any other reason behaves as before.
"""
from __future__ import annotations

from app import db, reporting
from tests.test_guest_edit_until_filed import _guest_on_device, _resave, stay  # noqa: F401
from tests.test_submission_retry_cap import SIGNATURE, _cleanup, _seed, host  # noqa: F401

DUPLICATE = "150: Duplicate record"
NOT_DUPLICATE = "104: Invalid date of birth"


def _host_form(**overrides):
    # The seeded guest's reported fields as the host form posts them. The seed
    # stores them already normalised, so posting them unchanged changes no
    # field guest_payload() reports.
    data = {
        "surname": "SMITH",
        "first_name": "JOHN",
        "birth_date": "01.01.1990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Street 1",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "signature": SIGNATURE,
    }
    data.update(overrides)
    return data


def _blocked_host_guest(token, last_errors):
    apartment, _reservation, guest_id = _seed(token, surname="SMITH", auto=True)
    db.update(
        "guest",
        guest_id,
        {
            "first_name": "JOHN",
            "submit_state": reporting.BLOCKED,
            "last_errors": last_errors,
            "submit_attempts": 1,
        },
    )
    return apartment, guest_id


def _blocked_guest_on_device(token, stay_id, last_errors):
    browser, row = _guest_on_device(token, stay_id)
    db.update(
        "guest",
        row["id"],
        {
            "submit_state": reporting.BLOCKED,
            "last_errors": last_errors,
            "submit_attempts": 1,
        },
    )
    return browser, row["id"]


def _row(guest_id):
    return db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))


def _sendable_ids(apartment_id):
    # The widest gate there is: a host resend, past the schedule and the cap.
    pairs = reporting.collect_sendable(
        apartment_id, ignore_automation=True, allow_resend=True
    )
    return [guest["id"] for guest, _reservation in pairs]


def _assert_still_blocked(guest_id):
    after = _row(guest_id)
    assert after["submit_state"] == reporting.BLOCKED
    assert after["last_errors"] == DUPLICATE
    assert after["submit_attempts"] == 1


def _assert_reset(guest_id):
    after = _row(guest_id)
    assert after["submit_state"] == reporting.PENDING
    assert after["last_errors"] is None
    assert after["submit_attempts"] == 0


# (a) host edit of a non-reported field on a duplicate-blocked guest
def test_host_edit_of_an_unreported_field_keeps_the_duplicate_block(host):
    apartment, guest_id = _blocked_host_guest("tok-1121-a", DUPLICATE)
    try:
        saved = host.post(
            f"/guests/{guest_id}", data=_host_form(doc_type="pas"), follow_redirects=False
        )
        assert saved.status_code == 303
        assert "err=" not in saved.headers["location"]
        assert _row(guest_id)["doc_type"] == "pas", "the other columns are still saved"
        _assert_still_blocked(guest_id)
        assert guest_id not in _sendable_ids(apartment["id"])
    finally:
        _cleanup(apartment["id"])


# (c) host edit of a reported field still resets, as today
def test_host_edit_of_a_reported_field_still_resets_a_duplicate_block(host):
    apartment, guest_id = _blocked_host_guest("tok-1121-c", DUPLICATE)
    try:
        saved = host.post(
            f"/guests/{guest_id}",
            data=_host_form(doc_number="P7654321"),
            follow_redirects=False,
        )
        assert saved.status_code == 303
        _assert_reset(guest_id)
        assert guest_id in _sendable_ids(apartment["id"])
    finally:
        _cleanup(apartment["id"])


# (d) host edit of a guest blocked for another reason: unchanged behaviour
def test_host_edit_of_a_guest_blocked_for_another_reason_still_resets(host):
    apartment, guest_id = _blocked_host_guest("tok-1121-d", NOT_DUPLICATE)
    try:
        saved = host.post(
            f"/guests/{guest_id}", data=_host_form(doc_type="pas"), follow_redirects=False
        )
        assert saved.status_code == 303
        _assert_reset(guest_id)
        assert guest_id in _sendable_ids(apartment["id"])
    finally:
        _cleanup(apartment["id"])


# (b) guest form save that changes no reported field
def test_guest_resave_without_a_reported_change_keeps_the_duplicate_block(stay):
    token, stay_id = stay
    browser, guest_id = _blocked_guest_on_device(token, stay_id, DUPLICATE)
    assert _resave(browser, token, stay_id, guest_id).status_code == 303
    _assert_still_blocked(guest_id)
    apartment_id = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?", (stay_id,)
    )["apartment_id"]
    assert guest_id not in _sendable_ids(apartment_id)


# (c) guest form save that changes a reported field still resets
def test_guest_resave_with_a_reported_change_still_resets_a_duplicate_block(stay):
    token, stay_id = stay
    browser, guest_id = _blocked_guest_on_device(token, stay_id, DUPLICATE)
    assert _resave(browser, token, stay_id, guest_id, surname="Jones").status_code == 303
    _assert_reset(guest_id)


# (d) guest form save of a guest blocked for another reason: unchanged
def test_guest_resave_of_a_guest_blocked_for_another_reason_still_resets(stay):
    token, stay_id = stay
    browser, guest_id = _blocked_guest_on_device(token, stay_id, NOT_DUPLICATE)
    assert _resave(browser, token, stay_id, guest_id).status_code == 303
    _assert_reset(guest_id)
```

   Command (no `-x` here, so every test reports): `.venv/bin/python -m pytest tests/test_submission_duplicate_blocked_edit.py -q --tb=line 2>&1 | tail -30`
   Expected: `2 failed, 4 passed`. The two failures are `test_host_edit_of_an_unreported_field_keeps_the_duplicate_block` and `test_guest_resave_without_a_reported_change_keeps_the_duplicate_block`, each at `assert after["submit_state"] == reporting.BLOCKED` (`'pending' == 'blocked'`). If any other test fails, or these two fail on a different line, STOP (section 8): the fixtures do not match and the fault is not shown.

2. In `App/app/reporting.py`, add the helper after `blocked_as_duplicate`. Anchor: `grep -nF 'return any(uby_errors.is_duplicate(part) for part in stored.split(" | "))' app/reporting.py` (one hit). Exact diff:

```diff
     return any(uby_errors.is_duplicate(part) for part in stored.split(" | "))
 
 
+def edit_keeps_duplicate_block(stored, proposed, reservation) -> bool:
+    """Brief 1121: does this edit leave a duplicate block in place?
+
+    True when ``stored`` is blocked because the register already holds the
+    record (the test collect_sendable uses to refuse a resend) and saving
+    ``proposed`` changes no field reported to the police (filed_record_changed).
+    Such an edit is not a corrected record, so it must not reopen the record
+    for sending: a second duplicate cannot be accepted and counts against the
+    host. An edit that changes a reported field is a new record and resets as
+    before.
+    """
+    return (
+        _field(stored, "submit_state") == BLOCKED
+        and blocked_as_duplicate(stored)
+        and not filed_record_changed(stored, proposed, reservation)
+    )
+
+
 def receipt_submission_id(previous_submission_id: Optional[int]) -> Optional[int]:
```

   Command: `.venv/bin/python -c "from app import reporting; print(reporting.edit_keeps_duplicate_block({'submit_state': 'pending', 'last_errors': None}, {}, None))" 2>&1 | tail -30`
   Expected: `False`.

3. In `App/app/routes/admin.py`, `guest_update`, add one branch. Anchor: `grep -nF 'elif guest["submit_state"] in (reporting.ERROR, reporting.BLOCKED, reporting.NOT_REQUIRED):' app/routes/admin.py` (one hit, about line 4723). Exact diff:

```diff
     elif not validation.guest_is_reportable(payload["nationality"]):
         payload["submit_state"] = reporting.NOT_REQUIRED
+    elif reporting.edit_keeps_duplicate_block(guest, {**dict(guest), **payload}, reservation):
+        # Brief 1121: the register refused this record as one it already holds,
+        # and this edit changes nothing it reports. The state, the error text
+        # and the retry count are kept; the other columns are saved.
+        pass
     elif guest["submit_state"] in (reporting.ERROR, reporting.BLOCKED, reporting.NOT_REQUIRED):
         # Rule 10.4(5): correcting a rejected record must make it sendable again.
         payload["submit_state"] = reporting.PENDING
```

   The `db.update_if(..., {"submit_state": guest["submit_state"]}, ...)` that follows is not changed.
   Command: `.venv/bin/python -m pytest tests/test_submission_duplicate_blocked_edit.py -q --tb=line 2>&1 | tail -30`
   Expected: `1 failed, 5 passed`; the one failure is `test_guest_resave_without_a_reported_change_keeps_the_duplicate_block`.

4. In `App/app/routes/guest.py`, `guest_form_save`, replace the `if` that resets attempts. Anchor: `grep -nF '    if reporting.guest_correction_resets_attempts(existing):' app/routes/guest.py` (one hit, about line 2594). Exact diff:

```diff
-    if reporting.guest_correction_resets_attempts(existing):
+    if existing and reporting.edit_keeps_duplicate_block(
+        existing, {**dict(existing), **payload}, reservation
+    ):
+        # Brief 1121: the register refused this record as one it already holds,
+        # and this save changes nothing it reports. The state, the error text
+        # and the retry count are not written; the other columns are saved.
+        del payload["submit_state"]
+        del payload["last_errors"]
+    elif reporting.guest_correction_resets_attempts(existing):
         # Rule 10.4(5): a correction makes the record sendable again, and a
         # guest fixing their own form is a correction like any other. Without
```

   The rest of that block (`payload["submit_attempts"] = 0`) and the `db.update_if(..., {"submit_state": existing["submit_state"]}, ...)` below are not changed.
   Command: `.venv/bin/python -m pytest tests/test_submission_duplicate_blocked_edit.py -q --tb=short -x 2>&1 | tail -30`
   Expected: `6 passed`.

5. The pin test, unchanged, still passes (no write added or removed, no guard changed, `blocked -> pending` still made by both writers).
   Command: `.venv/bin/python -m pytest tests/test_sm_guest_submit_state.py -q --tb=short -x 2>&1 | tail -30`
   Expected: all passed, 0 failed. If it fails, STOP (section 8); do not edit `PINNED` or `TRANSITIONS`.

6. The neighbouring tests of both edit paths and the duplicate guard.
   Command: `.venv/bin/python -m pytest tests/test_guest_edit_until_filed.py tests/test_submission_retry_cap.py tests/test_duplicate_guard.py -q --tb=short -x 2>&1 | tail -30`
   Expected: all passed, 0 failed.

7. Test-map row "Filing, UbyPort, claim".
   Command: `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short -x 2>&1 | tail -30`
   Expected: all passed, 0 failed.

8. Test-map row "Guest pages" (the guest route changed; no template changed, so no screenshot).
   Command: `.venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x -rs 2>&1 | tail -30`
   Expected: all passed, 0 failed, 0 skipped.

9. Context lint, from the repo root.
   Command: `python3 scripts/context_lint.py 2>&1 | tail -30`
   Expected: no `ERROR` line that names a 1121 file. `WARN ... is named by open briefs ... 1121-sm-duplicate-blocked-edit.md; say which goes first` for `App/app/reporting.py`, `App/app/routes/admin.py` and `App/app/routes/guest.py` is expected (other open briefs name the same files; the anchors protect the order). An `ERROR` that names only another file (on 2026-11-11 main had `docs/context/decisions.md: ~2214 tokens > cap 2200`) is not this brief's: copy the line into the report under Deviations and do not fix it.

10. Write the report (section 9) and set `Status: review` in this file.

## 5. Do not touch

- `App/tests/test_sm_guest_submit_state.py`, `reporting.TRANSITIONS`, `collect_sendable`, `blocked_as_duplicate`, `filed_record_changed`, `guest_payload`, `FILED_FIELDS`.
- Every `db.update_if` call and its `expected` / `extra_where`: the compare-and-set stays exactly as it is.
- Any template, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/i18n*`, mail, `docs/OPERATIONS.md`, `go/`, `.github/`, migrations.
- AGENTS.md rules 1 (filing correctness first), 5 (SQL only through `db.py` helpers), 8 (never push to `main`).

## 6. Commands

From `App/`, in this order, each must end as section 4 says:

1. `.venv/bin/python -m pytest tests/test_submission_duplicate_blocked_edit.py -q --tb=line 2>&1 | tail -30` before the fix: `2 failed, 4 passed`.
2. `.venv/bin/python -m pytest tests/test_submission_duplicate_blocked_edit.py -q --tb=short -x 2>&1 | tail -30` after steps 2-4: `6 passed`.
3. `.venv/bin/python -m pytest tests/test_sm_guest_submit_state.py -q --tb=short -x 2>&1 | tail -30`: passed.
4. `.venv/bin/python -m pytest tests/test_guest_edit_until_filed.py tests/test_submission_retry_cap.py tests/test_duplicate_guard.py -q --tb=short -x 2>&1 | tail -30`: passed.
5. The filing row (step 7) and the guest pages row (step 8, `-rs`, 0 skipped).
6. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`: no `ERROR` naming a 1121 file (step 9).

## 7. Acceptance

- [ ] Step 1 output shows exactly the two named tests failing at the `BLOCKED` assertion (proof of the fault on today's code).
- [ ] `tests/test_submission_duplicate_blocked_edit.py`: 6 passed.
- [ ] `tests/test_sm_guest_submit_state.py` passes with no change to it (`git diff --stat` does not list it).
- [ ] `git diff --stat` lists only the files in section 3.
- [ ] `grep -c 'edit_keeps_duplicate_block' App/app/reporting.py App/app/routes/admin.py App/app/routes/guest.py` prints 1, 1, 1.
- [ ] Filing row and guest pages row: 0 failed, guest pages 0 skipped.
- [ ] Context lint: no `ERROR` names a 1121 file.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found, or is found more than once;
- step 1 does not give exactly the two named failures;
- a test fails twice;
- the pin test fails (do not edit it);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1121-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output (step 1's output in full up to 30 lines: it is the proof of the fault).
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read in full:

- `App/app/routes/admin.py` `guest_update` (from `@router.post("/guests/{guest_id}")` to its `return`).
- `App/app/routes/guest.py` `guest_form_save` (whole function).
- `App/app/reporting.py` `collect_sendable`, `blocked_as_duplicate`, `filed_record_changed`, `guest_payload`, and the new `edit_keeps_duplicate_block`.
- `App/tests/test_submission_duplicate_blocked_edit.py` (new).
- `App/tests/test_sm_guest_submit_state.py` (unchanged; confirm it still pins the same writes and `blocked -> pending`).

Check: the new branch in `guest_update` sits after the `sent` and not-reportable branches, so those behave as before; the guest path deletes `submit_state` and `last_errors` only in the kept-block case and never skips the compare-and-set.

## Owner steps

1. Open the pull request the executor made for branch `task/1121-sm-duplicate-blocked-edit`.
2. Wait until every check is green.
3. In a terminal at the repo root, run `scripts/merge-pr-on-green.sh <PR number>` (use the number shown on the pull request page).
