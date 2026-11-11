# 1115: `claim.start_claim` writes only over the claim row it read

Status: todo
Depends on: PR #920 merged | Base commit: PR #920 merged to main | Branch: task/1115-sm-claim-start-guard
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [explicit state machines, rounds 2 to 4](../plans/explicit-state-machines-rounds-2-4.md), round 2. Round 1 brief: `docs/tasks/1109-sm-reservation-claim-state.md` ("Open questions"). Brief by Opus 5.5, 2026-11-11.

**Guest-data access.** `reservation_claim.state` decides which guest may see and edit a stay's guest data. Exact diffs only. Change nothing the steps do not name.

## 1. Objective

`start_claim` in `App/app/claim.py` reads the claim row, decides, then writes it with no condition on what it read, so a `confirm` that commits in between is undone: the `claimed` row goes back to `provisional` with another guest's e-mail address. The write gains `AND state = ? AND token_version = ?` with the values it read; when it matches no row, the function decides again from a fresh read, once, which for a confirmed stay is the existing `already_claimed` answer.

## 2. Context

### The fault (verified by the brief writer on PR #920's code; do not re-verify)

`App/app/claim.py`, `start_claim` (line 248): `claim = ensure_row(reservation["id"])` (line 266) is a plain read through `db.query_one`. The decision uses `claim["state"]`, `claim["email"]`, `claim["provisional_until"]`, `claim["updated_at"]` and `claim["token_version"]`. Then the write, lines 300 to 320:

```
    version = int(claim["token_version"] or 0) + 1
    db.execute(
        "UPDATE reservation_claim SET state = ?, email = ?, email_masked = ?, lang = ?, "
        "token_hash = ?, token_version = ?, provisional_until = ?, declared_guests = ?, "
        "updated_at = ? WHERE reservation_id = ?",
```

`start_claim` takes no lock and opens no transaction: `db.execute` (`App/app/db.py` line 1952) runs one statement on the thread's connection and returns its row count. `confirm` (line 671) does take `with db.immediate() as cur:` and `db.lock_key(cur, "reservation", reservation_id)` (lines 705 to 706), but `lock_key` (`App/app/db.py` line 957) is a Postgres advisory lock that serialises only writers that also take it, and on SQLite `BEGIN IMMEDIATE` holds the write lock only for `confirm`'s own block. Nothing serialises `start_claim` against `confirm`, so the fault is real.

The interleaving: guest A's hold is past `HOLD_TAKEOVER_SECONDS`; guest B's `start_claim` reads `provisional` (A's address); A's `confirm` commits `claimed`; B's write sets `state = provisional`, `email = B`, a new `token_hash`, `token_version + 1`. A's device cookie names the old `token_version` (`App/app/routes/guest.py` lines 279 to 287, `_device_holds_claim`), so A is cut off and B now holds the stay. The same gap lets a `release` be undone by a claimed-stay resend, and lets two takeovers write the same `token_version` (the second overwrites the first's address and secret).

The brief writer ran the step 2 test on PR #920's code in a scratch venv: both tests fail (`assert 'provisional' == 'claimed'`, `assert 'second@claim.test' == 'third@claim.test'`). With steps 3 to 5 applied both pass; with steps 6 to 11 the pin test passes (10 passed); `tests/test_claim_*.py` gives 118 passed.

### What happens on zero rows (the fix)

When the guarded write matches no row, `start_claim` calls itself once with the same arguments and `_retry=False`. The fresh call reads the row as it is now and takes the path that already exists for it: a `claimed` row with `resend=False` returns `False, "already_claimed", None` (the existing check `if claim["state"] == CLAIMED and not resend:`, line 270); an active hold for another address returns `False, "held", None` (line 283). No mail is queued by the losing call (the return comes before `mail.enqueue`). If the second write also matches no row, it returns `False, "held", None`, the existing code whose copy (`App/app/i18n.py` line 185) is "Someone else is confirming this stay. Try again in a few minutes." No new code, copy, template or mail.

### The pin test (round 1)

`App/tests/test_sm_reservation_claim_state.py` pins each state write with the states its WHERE clause allows. Its scanner reads the states from constant names (`UNCLAIMED`, `PROVISIONAL`, `CLAIMED`) in the guard's parameter. The new guard's parameter is `claim["state"]`, which names none, so the scanner gives it an empty guard. Steps 6 to 11 add a marker `AS_READ` for "the WHERE clause requires the state the function read", pin `start_claim` with it, and let the moves check treat `AS_READ` as any from-state. The set of moves does not change, so `claim.TRANSITIONS` does not change.

### Rules

- Compare-and-swap only: the guard is in the same `UPDATE`. Never add a read before the write.
- Python only. No Go twin: Go does not write this column (pinned by `test_go_writes_no_claim_state`).
- No migration, no dependency, no template, copy or mail change.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_claim_start_guard.py` | create | two tests that run a second writer between the read and the write |
| `App/app/claim.py` | edit | `start_claim`: guarded write and the zero-row branch |
| `App/tests/test_sm_reservation_claim_state.py` | edit | pin the new guard as `AS_READ` |
| `docs/tasks/1115-report.md` | create | the report |

No other file may change.

## 4. Steps

### Step 1. Branch and check the base

```
git checkout main && git pull && git checkout -b task/1115-sm-claim-start-guard
grep -c "TRANSITIONS = {" App/app/claim.py
ls App/tests/test_sm_reservation_claim_state.py
```

Expected: `1`, and the file is listed. If either fails, PR #920 is not merged: STOP (§8).

### Step 2. Create `App/tests/test_claim_start_guard.py` (fails on today's code)

Full content:

```python
"""Brief 1115: start_claim writes only over the claim row it read.

``start_claim`` reads the claim row, decides, then writes. These tests run a
second writer between that read and the write, by patching ``claim.ensure_row``
(the read ``start_claim`` uses) so the other writer commits right after it.
No threads, no sleeps: the order is fixed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import claim, db
from tests.test_claim_mail import TOKEN, _cleanup, _seed


def _age_hold_past_takeover(reservation_id: int) -> None:
    """Keep the hold active but older than the takeover window."""
    started = datetime.now(timezone.utc) - timedelta(
        seconds=claim.HOLD_TAKEOVER_SECONDS + 5
    )
    until = (started + timedelta(minutes=claim.HOLD_MINUTES)).replace(
        microsecond=0
    ).isoformat()
    db.execute(
        "UPDATE reservation_claim SET provisional_until = ? WHERE reservation_id = ?",
        (until, reservation_id),
    )


def _fixtures(current):
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    return reservation, apartment


def _clear_mail():
    db.execute("DELETE FROM email_outbox")
    db.execute("DELETE FROM console_mail_log")
    db.execute("DELETE FROM rate_limit_event")


def test_confirm_between_read_and_write_keeps_the_claim(monkeypatch):
    """A confirm that commits after start_claim's read must win.

    Before 1115 the takeover write had no state condition, so it put the
    claimed row back to provisional and replaced the confirmed address.
    """
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation, apartment = _fixtures(current)
        ok, err, first_secret = claim.start_claim(
            reservation, apartment, email="first@claim.test", party_size=2, lang="en"
        )
        assert ok, err
        _age_hold_past_takeover(current)

        real_ensure_row = claim.ensure_row
        reads = []

        def read_then_confirm(reservation_id):
            row = real_ensure_row(reservation_id)
            reads.append(reservation_id)
            if len(reads) == 1:
                assert claim.confirm(reservation, first_secret)
            return row

        monkeypatch.setattr(claim, "ensure_row", read_then_confirm)
        result = claim.start_claim(
            reservation, apartment, email="second@claim.test", party_size=2, lang="en"
        )
        monkeypatch.undo()

        row = claim.ensure_row(current)
        assert row["state"] == "claimed"
        assert row["email"] == "first@claim.test"
        assert row["token_hash"] is None
        assert result == (False, "already_claimed", None)
    finally:
        _clear_mail()
        _cleanup()


def test_takeover_between_read_and_write_is_not_overwritten(monkeypatch):
    """Two takeovers on one hold: the one that wrote first keeps the hold.

    Both read the same row and the same token_version; without the
    token_version condition the second write replaced the first one's address
    and secret under the same version number.
    """
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation, apartment = _fixtures(current)
        ok, err, _secret = claim.start_claim(
            reservation, apartment, email="first@claim.test", party_size=2, lang="en"
        )
        assert ok, err
        _age_hold_past_takeover(current)

        real_ensure_row = claim.ensure_row
        reads = []
        other = {}

        def read_then_other_takeover(reservation_id):
            row = real_ensure_row(reservation_id)
            reads.append(reservation_id)
            if len(reads) == 1:
                other["result"] = claim.start_claim(
                    reservation, apartment, email="third@claim.test", party_size=2, lang="en"
                )
            return row

        monkeypatch.setattr(claim, "ensure_row", read_then_other_takeover)
        result = claim.start_claim(
            reservation, apartment, email="second@claim.test", party_size=2, lang="en"
        )
        monkeypatch.undo()

        assert other["result"][0] is True, other["result"]
        third_secret = other["result"][2]
        row = claim.ensure_row(current)
        assert row["state"] == "provisional"
        assert row["email"] == "third@claim.test"
        assert row["token_hash"] == claim.token_hash(third_secret)
        assert result == (False, "held", None)
    finally:
        _clear_mail()
        _cleanup()
```

From `App/`:

```
.venv/bin/python -m pytest tests/test_claim_start_guard.py -q --tb=line 2>&1 | tail -30
```

Expected: `2 failed`, with `assert 'provisional' == 'claimed'` and `assert 'second@claim.test' == 'third@claim.test'`. That is the fault. If either test passes here, STOP (§8). Commit `1115 step 2`.

### Step 3. `App/app/claim.py`: add the retry flag to the signature

Anchor (unique together): `    resend: bool = False,` followed by `) -> Tuple[bool, str, Optional[str]]:` (lines 255 to 256).

```diff
     resend: bool = False,
+    _retry: bool = True,
 ) -> Tuple[bool, str, Optional[str]]:
     """Return (ok, error_code, secret_if_any). Secret is only for tests/console."""
```

Command: `grep -n "_retry: bool = True," App/app/claim.py 2>&1 | tail -30`. Expected: one line, `256:`. Commit `1115 step 3`.

### Step 4. `App/app/claim.py`: guard the write

Anchor: `    version = int(claim["token_version"] or 0) + 1` (line 300 before step 3).

```diff
     version = int(claim["token_version"] or 0) + 1
-    db.execute(
+    # 1115: write only over the row read above. A confirm, release or other
+    # start_claim that committed since then changed the state or the
+    # token_version, and this write then matches no row.
+    written = db.execute(
         "UPDATE reservation_claim SET state = ?, email = ?, email_masked = ?, lang = ?, "
         "token_hash = ?, token_version = ?, provisional_until = ?, declared_guests = ?, "
-        "updated_at = ? WHERE reservation_id = ?",
+        "updated_at = ? WHERE reservation_id = ? AND state = ? AND token_version = ?",
         (
             PROVISIONAL if claim["state"] != CLAIMED else CLAIMED,
```

Command: `grep -n 'WHERE reservation_id = ? AND state = ? AND token_version = ?' App/app/claim.py 2>&1 | tail -30`. Expected: one line. Commit `1115 step 4`.

### Step 5. `App/app/claim.py`: the two guard values and the zero-row branch

Anchor: the end of the same statement, the only `    link = (` in the file:

```diff
             party_size if claim["state"] != CLAIMED else None,
             now,
             reservation["id"],
+            claim["state"],
+            int(claim["token_version"] or 0),
         ),
     )
+    if written != 1:
+        # The row moved under this call: decide again from a fresh read, once,
+        # exactly as a new request would (a confirmed stay answers
+        # "already_claimed"). Losing twice in a row answers "held".
+        if _retry:
+            return start_claim(
+                reservation,
+                apartment,
+                email=email,
+                party_size=party_size,
+                lang=lang,
+                resend=resend,
+                _retry=False,
+            )
+        return False, "held", None
     link = (
         f"{config_public(apartment)}/l/{apartment['permalink_token']}/"
```

From `App/`:

```
.venv/bin/python -m pytest tests/test_claim_start_guard.py -q --tb=line 2>&1 | tail -30
```

Expected: `2 passed`. Commit `1115 step 5`.

### Step 6. Pin test: confirm it now fails as expected

From `App/`:

```
.venv/bin/python -m pytest tests/test_sm_reservation_claim_state.py -q --tb=line 2>&1 | tail -30
```

Expected: `1 failed, 9 passed`, the failure in `test_python_writes_match_pin` (`'start_claim', ()` against `'start_claim', ('claimed', 'provisional', 'unclaimed')`). Any other result: STOP (§8). No commit.

### Step 7. `App/tests/test_sm_reservation_claim_state.py`: the marker

```diff
 ANY = ("claimed", "provisional", "unclaimed")
 INSERT = ("(insert)",)
+AS_READ = ("(as read)",)
 STATE_NAMES = {"UNCLAIMED": "unclaimed", "PROVISIONAL": "provisional", "CLAIMED": "claimed"}
```

### Step 8. Same file: the `PINNED_WRITES` comment and the `start_claim` row

```diff
 # INSERT: the statement creates the row. ANY: the WHERE clause has no state
-# condition (brief 1109, "Open questions").
+# condition (brief 1109, "Open questions"). AS_READ: the WHERE clause requires
+# the state the function read before the write (brief 1115).
 PINNED_WRITES = [
     ("App/app/claim.py", "ensure_row", INSERT, ("unclaimed",)),
     ("App/app/claim.py", "expire_holds", ("provisional",), ("unclaimed",)),
-    ("App/app/claim.py", "start_claim", ANY, ("claimed", "provisional")),
+    ("App/app/claim.py", "start_claim", AS_READ, ("claimed", "provisional")),
```

### Step 9. Same file: the `PINNED_MOVES` comment

```diff
-# None as a from-state means "no row yet". start_claim has no state condition
-# in its WHERE clause: its from-states are the ones its Python checks let
+# None as a from-state means "no row yet". start_claim's WHERE clause requires
+# the state it read: its from-states are the ones its Python checks let
 # through before the write.
```

### Step 10. Same file: the scanner, in `_sql_write`

```diff
     allowed = set()
     for elt in elts[first:first + count]:
-        allowed.update(_states(elt))
+        allowed.update(_states(elt) or AS_READ)
     return tuple(sorted(allowed)), to
```

### Step 11. Same file: `test_moves_match_writes`

```diff
         assert {t for _, t in moves[key]} == to, key
-        allowed = {None} if guard == INSERT else set(guard)
+        allowed = {None} if guard == INSERT else set(ANY) if guard == AS_READ else set(guard)
         for frm, _ in moves[key]:
```

From `App/`:

```
.venv/bin/python -m pytest tests/test_sm_reservation_claim_state.py tests/test_claim_start_guard.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `12 passed`. Commit `1115 steps 7-11`.

### Step 12. The test-map row (filing, UbyPort, claim)

From `App/`: the command in §6. Expected: no failure. If only `tests/test_endtoend.py` tests fail, run `.venv/bin/python -m pytest tests/test_endtoend.py -q --tb=short 2>&1 | tail -30` alone: the brief writer saw the same 13 `test_endtoend.py` failures in the combined run with and without this change (a scratch venv; alone it gives 28 passed). If it passes alone, note that under Deviations and go on; otherwise STOP (§8).

### Step 13. Context lint

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no `ERROR` line that names a file of §3. (On 2026-11-11 main already had an unrelated `ERROR docs/context/decisions.md` cap line and a `WARN` that 0245 also names `App/app/claim.py`; note those under Deviations, do not fix them.)

### Step 14. Report

Write `docs/tasks/1115-report.md` (§9) and set this brief's `Status: review`. Commit `1115 report`, push the branch, open one PR titled `1115: guard the start_claim write on the state it read`.

## 5. Do not touch

- `confirm`, `release`, `expire_holds`, `ensure_row`, `claim.TRANSITIONS` and every other function in `App/app/claim.py`; `App/app/db.py`; any route, template, i18n or mail file; `go/`.
- Hard rules 1 (filing correctness), 2 (privacy), 5 (SQL through the `db.py` helpers), 8 (never push to `main`).

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_claim_start_guard.py tests/test_sm_reservation_claim_state.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=line 2>&1 | tail -30
```

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Step 2 output showed `2 failed` before steps 3 to 5 (quoted in the report).
- [ ] `grep -c 'AND state = ? AND token_version = ?' App/app/claim.py` prints `1`.
- [ ] The first §6 command: `12 passed`.
- [ ] The test-map row: no failure, or only the `test_endtoend.py` ordering failures of step 12 with `test_endtoend.py` green alone.
- [ ] `git diff --stat main` lists only the four files of §3.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- step 2 does not fail, or step 6 does not fail as stated;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1115-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output (step 2's failing run included).
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Open questions (for the reviewer and owner; the executor does nothing about them)

- **`release` with no state check (round 1).** `App/app/claim.py:752` (`release`, UPDATE at 759) bumps `token_version` from any state, and its caller `reservation_release_claim` (`App/app/routes/admin.py:4330`, call at 4338) checks login and ownership only. Decision: releasing an `unclaimed` row is **not harmful to a guest**. What reads `token_version`: (1) the device cookie, which grants access only when the row is `claimed` (`App/app/routes/guest.py:279-287`, `_device_holds_claim` requires `claim.is_claimed(row)`), so on an unclaimed row it grants nothing before or after; (2) the e-mailed secret, but an unclaimed row has `token_hash` NULL (set by `expire_holds`, claim.py:137, and by `release`, claim.py:759), so there is no live link to invalidate; (3) the form draft generation (`App/app/routes/guest.py:330-334`, checked at `App/app/guest_draft.py:140`), but drafts are saved only behind `_require_claim_session` (`App/app/routes/guest.py:2782`), and every way into `unclaimed` either already bumped the version (`release`) or came from a hold never confirmed at that version (`expire_holds`), so no draft at the current version exists to lose; (4) the mail idempotency key `claim:{id}:v{version}` (claim.py, `mail.enqueue` in `start_claim`), where a skipped number is harmless. One side effect that is not about the version: `release` also clears `guest_access_locked_at` (claim.py:762), so releasing a locked unclaimed stay reopens it. The host's page hides the button for unclaimed stays (`App/app/templates/reservation_detail.html:183`), so only a stale page or a hand-made POST by the stay's own host reaches it. No change proposed; if the owner wants it, a later brief adds `AND state IN (?, ?)` with `PROVISIONAL, CLAIMED` to `release`.
- **Retry depth.** The zero-row branch retries once. A second loss in a row returns `held`; the brief writer found no path where that happens without a third writer landing in the same few milliseconds.
- **Not run here:** the brief writer ran the tests with system Python 3 in a scratch venv built from `App/requirements.txt` (SQLite backend). The Postgres backend was not run; the guard uses only `=` conditions and `db.execute`'s row count, which `db.py` documents as the same on both engines (`App/app/db.py:1952`).

## Risk list (for the reviewer)

Read in full: `App/app/claim.py` `start_claim` (line 248 onward) and `confirm` (line 671 onward); `App/tests/test_claim_start_guard.py`; `App/tests/test_sm_reservation_claim_state.py` (the scanner change in `_sql_write` and `test_moves_match_writes`).

## Owner steps

None beyond the usual: when CI is green, run `scripts/merge-pr-on-green.sh` with the PR number.
