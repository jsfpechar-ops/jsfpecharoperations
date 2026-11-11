# 1110: Queue state tables (email_outbox, push_outbox, ad_click, guide_import)

Status: todo
Depends on: none | Base commit: 70fe25b0 | Branch: task/1110-sm-queue-states
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Declare, in the module that owns each queue, one table of the moves its state column makes today, and add one test file that reads every Python and Go writer as text and fails when a write appears, disappears or moves without the table and the pins changing. Round 1 of [explicit-state-machines](../plans/explicit-state-machines.md): no runtime behaviour changes, nothing reads the new tables, no writer or Go file is edited.

## 2. Context

Rules from the plan that bind this brief: derive, never design (the tables list exactly what the code does; where the code is odd, the test file's docstring lists it under "Open questions" and the test pins what the code does); the table lives in the owning module; writers and Go files are not edited; no migration, no dependency.

The four machines, as the code makes them today (derived by reading every writer):

| Table | Column | Moves | Writers |
|---|---|---|---|
| `OUTBOX_TRANSITIONS` in `App/app/mail.py` | `email_outbox.state` | queued to sending, queued to failed, sending to sent, sending to failed, sending to queued | `mail.py` enqueue, drain, `_deliver`, send_now; `claim.py` expire_on_cancel; `go/internal/ical/reconcile.go` expireOnCancel; `go/internal/ubyport/notify.go` EnqueueMail |
| `PUSH_TRANSITIONS` in `App/app/push.py` | `push_outbox.state` | queued to sent, queued to failed (no claimed state: a claim only raises attempts and next_attempt_at) | `push.py` notify, send_test, `_finish`; `go/internal/pushsend/pushsend.go` SendTest, finish; `go/internal/ubyport/notify.go` QueuePush |
| `SEND_TRANSITIONS` in `App/app/meta_capi.py` | `ad_click.send_state` | NULL to pending, pending to sending, pending to expired, pending to withdrawn, sending to sent, sending to failed, sending to pending, sending to withdrawn | `meta_capi.py` enqueue, expire_unsendable, send_pending; `signup.py` withdraw_consent |
| `IMPORT_TRANSITIONS` in `App/app/guest_guide_import.py` | `guide_import.status` | queued to running, queued to failed, running to done, running to failed, done to used, done to failed, done to expired | `guest_guide_import.py` request_imports, mark_used, `_run_one`, process_queue, purge; `guest_guide_merge.py` `_note_failure` |

The dict helpers the writers use (`App/app/db.py`): `db.update(table, id, values)`, `db.update_if(table, id, values, expected)` (compare-and-set: `values` is the new-values dict, `expected` the where dict), `db.insert(table, values)`.

Open questions (writes with no guard on the old state; these go into the test file docstring, which Step 5 gives in full):

- `App/app/mail.py:688` and `:705`: `_deliver()` writes sent, failed or queued with `WHERE id = ?` only.
- `App/app/push.py:450` and `go/internal/pushsend/pushsend.go:501`: `_finish()` and `finish()` write sent or failed with `WHERE id = ?` only.
- `App/app/signup.py:686` (the state is written at line 693): `withdraw_consent()` sets withdrawn from a value it read earlier; its only guard is `withdrawn_at`.
- `App/app/guest_guide_import.py:356` and `:375`: `_run_one()` writes done or failed with `WHERE id = ?` only. `:393`: `process_queue()` writes failed the same way.
- Nothing sets `email_outbox.state` to bounced or complained, yet `admin_ops.py` reads both and `purge_old()` deletes them.
- Nothing moves a `guide_import` row out of running except `_run_one()` itself, so a worker that dies mid-run leaves the row running for good.

Anchors: if an anchor or excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/mail.py` | edit | add `OUTBOX_TRANSITIONS` after the state constants |
| `App/app/push.py` | edit | add `PUSH_TRANSITIONS` after `TEST_KIND` |
| `App/app/meta_capi.py` | edit | add `SEND_TRANSITIONS` after the state constants line |
| `App/app/guest_guide_import.py` | edit | add `IMPORT_TRANSITIONS` after `log = ...` |
| `App/tests/test_sm_queues.py` | new | the four pinning tests |
| `docs/tasks/1110-report.md` | new | the report (§9) |

No other file may change. The orchestrator adds the test-map row at review.

## 4. Steps

Do the steps in order. After each step's command, commit as shown. Each edit adds lines only; do not change any existing line.

### Step 1: OUTBOX_TRANSITIONS in mail.py

File: `App/app/mail.py`. One edit.

1. Check the anchor: `grep -nF 'COMPLAINED = "complained"' App/app/mail.py | tail -30`. Expected: exactly one line. Not found or more than one: STOP.
2. Use the Edit tool with this `old_string` (one line, exact):

```
COMPLAINED = "complained"
```

and this `new_string` (the same line, then the new block; the block starts with an empty line):

```python
COMPLAINED = "complained"

# Every move email_outbox.state makes today (brief 1110), derived from the code, not
# designed. Nothing reads this at runtime; tests/test_sm_queues.py pins the writers.
# A row is created queued by enqueue() here and by EnqueueMail in go/internal/ubyport/notify.go.
OUTBOX_TRANSITIONS = {
    # drain() and send_now() claim a row; claim.expire_on_cancel() and
    # expireOnCancel in go/internal/ical/reconcile.go fail a queued one
    QUEUED: {SENDING, FAILED},
    # _deliver(): sent, last attempt failed, or back to queued for a retry;
    # drain() also resets a claim older than 10 minutes to queued
    SENDING: {SENT, FAILED, QUEUED},
    SENT: set(),
    FAILED: set(),
    BOUNCED: set(),  # no code sets bounced or complained today; admin_ops reads them
    COMPLAINED: set(),
}
```

3. Check and commit, from the repo root: `cd App && .venv/bin/python -c "from app import mail; print(len(mail.OUTBOX_TRANSITIONS))" 2>&1 | tail -30; cd .. && git add App/app/mail.py && git commit -m "1110 step 1" 2>&1 | tail -30`. Expected: the first line printed is `6`, then a commit line.

### Step 2: PUSH_TRANSITIONS in push.py

File: `App/app/push.py`. One edit.

1. Check the anchor: `grep -nF 'TEST_KIND = "test"' App/app/push.py | tail -30`. Expected: exactly one line. Not found or more than one: STOP.
2. Use the Edit tool with this `old_string` (one line, exact):

```
TEST_KIND = "test"
```

and this `new_string` (the same line, then the new block; the block starts with an empty line):

```python
TEST_KIND = "test"

# Every move push_outbox.state makes today (brief 1110), derived from the code, not
# designed. Nothing reads this at runtime; tests/test_sm_queues.py pins the writers.
# There is no claimed state: drain() claims a row by raising attempts and
# next_attempt_at, and _retry() does the same for a retry; the row stays queued.
# A row is created queued by notify() and send_test() here and by QueuePush and
# SendTest in go/internal.
PUSH_TRANSITIONS = {
    "queued": {"sent", "failed"},  # _finish() here, finish() in go/internal/pushsend/pushsend.go
    "sent": set(),
    "failed": set(),
}
```

3. Check and commit, from the repo root: `cd App && .venv/bin/python -c "from app import push; print(len(push.PUSH_TRANSITIONS))" 2>&1 | tail -30; cd .. && git add App/app/push.py && git commit -m "1110 step 2" 2>&1 | tail -30`. Expected: the first line printed is `3`, then a commit line.

### Step 3: SEND_TRANSITIONS in meta_capi.py

File: `App/app/meta_capi.py`. One edit.

1. Check the anchor: `grep -nF 'PENDING, SENDING, SENT, FAILED, EXPIRED = "pending", "sending", "sent", "failed", "expired"' App/app/meta_capi.py | tail -30`. Expected: exactly one line. Not found or more than one: STOP.
2. Use the Edit tool with this `old_string` (one line, exact):

```
PENDING, SENDING, SENT, FAILED, EXPIRED = "pending", "sending", "sent", "failed", "expired"
```

and this `new_string` (the same line, then the new block; the block starts with an empty line):

```python
PENDING, SENDING, SENT, FAILED, EXPIRED = "pending", "sending", "sent", "failed", "expired"

# Every move ad_click.send_state makes today (brief 1110), derived from the code, not
# designed. None means not queued. Nothing reads this at runtime;
# tests/test_sm_queues.py pins the writers.
SEND_TRANSITIONS = {
    None: {PENDING},  # enqueue()
    # send_pending() claims a row; expire_unsendable(); signup.withdraw_consent()
    PENDING: {SENDING, EXPIRED, "withdrawn"},
    # send_pending(): sent, failed, or back to pending for a retry or a stale claim;
    # signup.withdraw_consent()
    SENDING: {SENT, FAILED, PENDING, "withdrawn"},
    SENT: set(),
    FAILED: set(),
    EXPIRED: set(),
    "withdrawn": set(),  # only signup.withdraw_consent() writes it, with no constant
}
```

3. Check and commit, from the repo root: `cd App && .venv/bin/python -c "from app import meta_capi; print(len(meta_capi.SEND_TRANSITIONS))" 2>&1 | tail -30; cd .. && git add App/app/meta_capi.py && git commit -m "1110 step 3" 2>&1 | tail -30`. Expected: the first line printed is `7`, then a commit line.

### Step 4: IMPORT_TRANSITIONS in guest_guide_import.py

File: `App/app/guest_guide_import.py`. One edit.

1. Check the anchor: `grep -nF 'log = logging.getLogger("ubyhost.guide_import")' App/app/guest_guide_import.py | tail -30`. Expected: exactly one line. Not found or more than one: STOP.
2. Use the Edit tool with this `old_string` (one line, exact):

```
log = logging.getLogger("ubyhost.guide_import")
```

and this `new_string` (the same line, then the new block; the block starts with an empty line):

```python
log = logging.getLogger("ubyhost.guide_import")

# Every move guide_import.status makes today (brief 1110), derived from the code, not
# designed. Nothing reads this at runtime; tests/test_sm_queues.py pins the writers.
# A row is created queued by request_imports().
IMPORT_TRANSITIONS = {
    # _run_one() claims a row; process_queue() fails it when the monthly budget is gone
    "queued": {"running", "failed"},
    "running": {"done", "failed"},  # _run_one()
    # mark_used(); guest_guide_merge._note_failure(); purge() after RAW_DAYS
    "done": {"used", "failed", "expired"},
    "failed": set(),
    "used": set(),
    "expired": set(),
}
```

3. Check and commit, from the repo root: `cd App && .venv/bin/python -c "from app import guest_guide_import as g; print(len(g.IMPORT_TRANSITIONS))" 2>&1 | tail -30; cd .. && git add App/app/guest_guide_import.py && git commit -m "1110 step 4" 2>&1 | tail -30`. Expected: the first line printed is `6`, then a commit line.

### Step 5: the test file

File: `App/tests/test_sm_queues.py` (new). Create it with the Write tool, with exactly this content (it was run against the four tables above and passes):

```python
"""1110: pin every write of the four queue state columns against its table.

Machines: email_outbox.state (mail.OUTBOX_TRANSITIONS), push_outbox.state
(push.PUSH_TRANSITIONS), ad_click.send_state (meta_capi.SEND_TRANSITIONS) and
guide_import.status (guest_guide_import.IMPORT_TRANSITIONS).

Each test reads every Python file under App/app and every non-test Go file under
go/ as text, finds each statement that writes the column, and compares the
writers with a pinned list. A writer is named by its enclosing function, never
by line number. The test fails when a write is added, removed or moved to
another function, when a pinned code fragment changes, and when a pinned move
is missing from the table. It never runs a writer.

Pinned entry: (file, function, code fragment, from-states, to-state).
from-states is a tuple, NEW (the row is inserted) or ANY (the write has no
guard on the old state, so the code gives no from-state).

Open questions (writes with no guard on the old state; line numbers as of
brief 1110, the pins do not depend on them):
- App/app/mail.py:688 and :705, _deliver() writes sent / failed / queued with
  WHERE id = ? only, so a change another writer made in between is overwritten.
- App/app/push.py:450 and go/internal/pushsend/pushsend.go:501, _finish() and
  finish() write sent / failed with WHERE id = ? only.
- App/app/signup.py:686 (write at 693), withdraw_consent() sets withdrawn from a
  value it read earlier; its only guard is withdrawn_at, not send_state.
- App/app/guest_guide_import.py:356 and :375, _run_one() writes done / failed
  with WHERE id = ? only; :393, process_queue() writes failed the same way.
- Nothing sets email_outbox.state to bounced or complained, yet admin_ops.py
  reads both and purge_old() deletes them.
- Nothing moves a guide_import row out of running except _run_one() itself, so
  a worker that dies mid-run leaves the row running for good.
"""
import re
from collections import Counter
from pathlib import Path

from app import guest_guide_import, mail, meta_capi, push

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent
NEW = "new"
ANY = "any"

MAIL = "App/app/mail.py"
CLAIM = "App/app/claim.py"
RECONCILE = "go/internal/ical/reconcile.go"
NOTIFY = "go/internal/ubyport/notify.go"
PUSH = "App/app/push.py"
PUSHSEND = "go/internal/pushsend/pushsend.go"
CAPI = "App/app/meta_capi.py"
SIGNUP = "App/app/signup.py"
IMPORT = "App/app/guest_guide_import.py"
MERGE = "App/app/guest_guide_merge.py"

# ---- scanner ---------------------------------------------------------------

_DEF = re.compile(
    r"^[ \t]*(?:async[ \t]+)?def[ \t]+(\w+)|^func[ \t]+(?:\([^)]*\)[ \t]*)?(\w+)", re.M
)


def _sources():
    files = sorted((APP_DIR / "app").rglob("*.py"))
    files += sorted(p for p in (REPO_DIR / "go").rglob("*.go") if not p.name.endswith("_test.go"))
    return [(p.relative_to(REPO_DIR).as_posix(), p.read_text(encoding="utf-8")) for p in files]


def _call_text(text, start):
    """The text of a call from just inside its opening bracket to the closing one."""
    depth, i, quote = 1, start, None
    while i < len(text) and depth:
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            while i < len(text) and text[i] != "\n":
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    return text[start:i]


def _sites(text, table, col):
    """Offsets of the statements in text that write table.col."""
    found = []
    for m in re.finditer(r"UPDATE\s+%s\s+SET\s+(.*?)\bWHERE\b" % table, text, re.S):
        if re.search(r"\b%s\s*=" % col, m.group(1)):
            found.append(m.start())
    for m in re.finditer(r"INSERT\s+INTO\s+%s\s*\(([^)]*)\)" % table, text):
        if re.search(r"\b%s\b" % col, m.group(1)):
            found.append(m.start())
    helper = r'\bdb\.(?:update|update_if|update_in|insert|insert_in)\(\s*(?:cur\s*,\s*)?"%s"' % table
    for m in re.finditer(helper, text):
        if re.search(r'"%s"\s*:' % col, _call_text(text, m.end())):
            found.append(m.start())
    return found


def _found(table, col):
    """({(file, function): number of writes}, {(file, function): function text})."""
    counts, bodies = Counter(), {}
    for rel, text in _sources():
        if table not in text:
            continue
        marks = [(m.start(), m.group(1) or m.group(2)) for m in _DEF.finditer(text)]
        spans = [
            (start, marks[i + 1][0] if i + 1 < len(marks) else len(text), name)
            for i, (start, name) in enumerate(marks)
        ]
        for offset in _sites(text, table, col):
            start, end, name = next(
                (s for s in spans if s[0] <= offset < s[1]), (0, len(text), "<module>")
            )
            counts[(rel, name)] += 1
            bodies[(rel, name)] = text[start:end]
    return counts, bodies


def _check(table, col, sites, moves, transitions):
    counts, bodies = _found(table, col)
    assert counts == Counter(sites), (
        f"writers of {table}.{col} changed.\nfound:  {dict(sorted(counts.items()))}\n"
        f"pinned: {dict(sorted(sites.items()))}\n"
        "A write was added, removed or moved. Decide the move, add it to the table and the pins."
    )
    assert {(rel, func) for rel, func, *_ in moves} == set(sites), "every pinned writer needs a move"
    destinations = {to for tos in transitions.values() for to in tos}
    for rel, func, fragment, froms, to in moves:
        assert fragment in bodies[(rel, func)], f"{rel} {func}: pinned code changed: {fragment!r}"
        if froms == NEW:
            assert to in transitions, f"{rel} {func}: {to!r} is not a state in the table"
        elif froms == ANY:
            assert to in destinations, f"{rel} {func}: nothing in the table moves to {to!r}"
        else:
            for old in froms:
                assert to in transitions.get(old, set()), (
                    f"{rel} {func}: {old!r} to {to!r} is not in the table"
                )


# ---- email_outbox.state ----------------------------------------------------

OUTBOX_SITES = {
    (MAIL, "enqueue"): 1,
    (MAIL, "drain"): 2,
    (MAIL, "_deliver"): 2,
    (MAIL, "send_now"): 1,
    (CLAIM, "expire_on_cancel"): 1,
    (RECONCILE, "expireOnCancel"): 1,
    (NOTIFY, "EnqueueMail"): 1,
}
_CLAIM_FRAGMENT = '{"state": SENDING, "updated_at": db.utcnow()}, {"state": QUEUED}'
OUTBOX_MOVES = [
    (MAIL, "enqueue", '"state": QUEUED,', NEW, "queued"),
    (MAIL, "drain", "(QUEUED, SENDING, stale)", ("sending",), "queued"),
    (MAIL, "drain", _CLAIM_FRAGMENT, ("queued",), "sending"),
    (MAIL, "_deliver", '"state": SENT,', ANY, "sent"),
    (MAIL, "_deliver", '"state": FAILED if terminal else QUEUED,', ANY, "failed"),
    (MAIL, "_deliver", '"state": FAILED if terminal else QUEUED,', ANY, "queued"),
    (MAIL, "send_now", _CLAIM_FRAGMENT, ("queued",), "sending"),
    (CLAIM, "expire_on_cancel", "(mail.FAILED, now, reservation[\"id\"], mail.QUEUED)", ("queued",), "failed"),
    (RECONCILE, "expireOnCancel", "SET state = 'failed'", ("queued",), "failed"),
    (NOTIFY, "EnqueueMail", "$9, 'queued', 0", NEW, "queued"),
]


def test_email_outbox_writers_match_outbox_transitions():
    _check("email_outbox", "state", OUTBOX_SITES, OUTBOX_MOVES, mail.OUTBOX_TRANSITIONS)


# ---- push_outbox.state -----------------------------------------------------

PUSH_SITES = {
    (PUSH, "notify"): 1,
    (PUSH, "send_test"): 1,
    (PUSH, "_finish"): 1,
    (PUSHSEND, "SendTest"): 1,
    (PUSHSEND, "finish"): 1,
    (NOTIFY, "QueuePush"): 1,
}
_PY_FINISH = "UPDATE push_outbox SET state = ?, last_status = ?, sent_at = ? WHERE id = ?"
_GO_FINISH = "UPDATE push_outbox SET state = $1, last_status = $2, sent_at = $3 WHERE id = $4"
PUSH_MOVES = [
    (PUSH, "notify", "'queued', 0, ?, ?)", NEW, "queued"),
    (PUSH, "send_test", '"state": "queued",', NEW, "queued"),
    (PUSH, "_finish", _PY_FINISH, ANY, "sent"),
    (PUSH, "_finish", _PY_FINISH, ANY, "failed"),
    (PUSHSEND, "SendTest", "'queued', 1, $6, $7)", NEW, "queued"),
    (PUSHSEND, "finish", _GO_FINISH, ANY, "sent"),
    (PUSHSEND, "finish", _GO_FINISH, ANY, "failed"),
    (NOTIFY, "QueuePush", "'queued', 0, $7, $7)", NEW, "queued"),
]


def test_push_outbox_writers_match_push_transitions():
    _check("push_outbox", "state", PUSH_SITES, PUSH_MOVES, push.PUSH_TRANSITIONS)


# ---- ad_click.send_state ---------------------------------------------------

SEND_SITES = {
    (CAPI, "enqueue"): 1,
    (CAPI, "expire_unsendable"): 1,
    (CAPI, "send_pending"): 5,
    (SIGNUP, "withdraw_consent"): 1,
}
_WITHDRAW = '"send_state": "withdrawn" if row["send_state"] in ("pending", "sending")'
SEND_MOVES = [
    (CAPI, "enqueue", '"send_state": PENDING,', (None,), "pending"),
    (CAPI, "expire_unsendable", '(EXPIRED, "older than Meta\'s 7-day event window", PENDING, cutoff)', ("pending",), "expired"),
    (CAPI, "send_pending", "(PENDING, SENDING, _iso(now - STALE_SENDING))", ("sending",), "pending"),
    (CAPI, "send_pending", '{"send_state": SENDING, "next_attempt_at": _iso(now)}', ("pending",), "sending"),
    (CAPI, "send_pending", '"send_state": FAILED if terminal else PENDING,', ("sending",), "failed"),
    (CAPI, "send_pending", '"send_state": FAILED if terminal else PENDING,', ("sending",), "pending"),
    (CAPI, "send_pending", '{"send_state": FAILED, "attempts": attempts, "last_error": str(exc)[:400]}', ("sending",), "failed"),
    (CAPI, "send_pending", '"send_state": SENT,', ("sending",), "sent"),
    (SIGNUP, "withdraw_consent", _WITHDRAW, ("pending", "sending"), "withdrawn"),
]


def test_ad_click_writers_match_send_transitions():
    _check("ad_click", "send_state", SEND_SITES, SEND_MOVES, meta_capi.SEND_TRANSITIONS)


# ---- guide_import.status ---------------------------------------------------

IMPORT_SITES = {
    (IMPORT, "request_imports"): 1,
    (IMPORT, "mark_used"): 1,
    (IMPORT, "_run_one"): 3,
    (IMPORT, "process_queue"): 1,
    (IMPORT, "purge"): 1,
    (MERGE, "_note_failure"): 1,
}
IMPORT_MOVES = [
    (IMPORT, "request_imports", '"status": "queued", "created_at": now,', NEW, "queued"),
    (IMPORT, "mark_used", "SET status = 'used'", ("done",), "used"),
    (IMPORT, "_run_one", "SET status = 'running'", ("queued",), "running"),
    (IMPORT, "_run_one", "SET status = 'done', raw_json = ?", ANY, "done"),
    (IMPORT, "_run_one", "SET status = 'failed', error = ?, finished_at = ?", ANY, "failed"),
    (IMPORT, "process_queue", "SET status = 'failed', error = 'budget'", ANY, "failed"),
    (IMPORT, "purge", "WHEN status = 'done' THEN 'expired'", ("done",), "expired"),
    (MERGE, "_note_failure", "SET status = 'failed', error = ?, raw_json = NULL", ("done",), "failed"),
]


def test_guide_import_writers_match_import_transitions():
    _check("guide_import", "status", IMPORT_SITES, IMPORT_MOVES, guest_guide_import.IMPORT_TRANSITIONS)
```

Then, from the repo root: `git add App/tests/test_sm_queues.py && git commit -m "1110 step 5" 2>&1 | tail -30`. Expected: a commit line.

### Step 6: run the test

From `App/`: `.venv/bin/python -m pytest tests/test_sm_queues.py -q --tb=short -x 2>&1 | tail -30`. Expected: `4 passed`. If it fails, read the last 30 lines and fix it once; the usual cause is a typo copied into Step 5. Fails again: STOP and report.

Do not edit a pin to make the test pass. If a pinned code fragment is "not found", the source differs from this brief: STOP.

### Step 7: report

Write `docs/tasks/1110-report.md` per §9, set `Status: review` at the top of this brief, commit as `1110 step 7`, open one draft PR.

## 5. Do not touch

- Every writer: no edit to `mail.py`, `push.py`, `meta_capi.py`, `guest_guide_import.py`, `guest_guide_merge.py`, `claim.py`, `signup.py` beyond the four additive blocks above. No Go file. No migration, no template, no `db.py`.
- AGENTS.md rules that apply: 4 (no new dependency: the test uses only `re`, `collections`, `pathlib`), 5 (no SQL change), 8 (never push to `main`; keep the PR a draft).
- Do not reference the four tables from any code other than the test.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_sm_queues.py -q --tb=short -x 2>&1 | tail -30` expects `4 passed`.

No other test is needed: no behaviour changed. CI runs the rest.

## 7. Acceptance

- [ ] `git diff --stat main...HEAD 2>&1 | tail -30` shows exactly: the four `App/app/*.py` files with insertions only, `App/tests/test_sm_queues.py`, this brief, `docs/tasks/1110-report.md`.
- [ ] `git diff main...HEAD -- App/app 2>&1 | grep -c '^-[^-]'` prints `0` (no line removed).
- [ ] `tests/test_sm_queues.py` prints `4 passed`.
- [ ] `grep -rn "OUTBOX_TRANSITIONS\|PUSH_TRANSITIONS\|SEND_TRANSITIONS\|IMPORT_TRANSITIONS" App/app | head -50` shows each name only at its definition.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or pinned code fragment is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1110-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/tests/test_sm_queues.py`: the regexes that find writers (`_sites`) and the pins. A write the regexes cannot see (a dynamic table name, a helper called through another name) passes silently; the reviewer checks `grep -rn "email_outbox\|push_outbox\|send_state\|guide_import" App/app go --include=*.py --include=*.go | grep -v _test` shows no writer outside the pins.
- The four additive blocks: states listed must match the table in §2.
- The six open questions: the orchestrator copies them to [known-issues](../context/known-issues.md) and records the table locations in [decisions](../context/decisions.md) at review.

## Owner steps

1. None for this brief. Merge the PR with `scripts/merge-pr-on-green.sh` after the orchestrator's review.
