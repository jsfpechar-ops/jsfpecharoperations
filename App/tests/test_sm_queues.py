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
- App/app/guest_guide_import.py: process_queue() budget write still matches by
  id alone; _run_one() done / failed writes require status = 'running' (review of 1117).
- Nothing sets email_outbox.state to bounced or complained, yet admin_ops.py
  reads both and purge_old() deletes them.
- guide_import: a worker that dies mid-run leaves the row running; since brief
  1117 process_queue() fails such a row (guarded, started_at older than
  STALE_RUNNING). _run_one() done / failed writes also require status = 'running'.
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
    (IMPORT, "process_queue"): 2,
    (IMPORT, "purge"): 1,
    (MERGE, "_note_failure"): 1,
}
IMPORT_MOVES = [
    (IMPORT, "request_imports", '"status": "queued", "created_at": now,', NEW, "queued"),
    (IMPORT, "mark_used", "SET status = 'used'", ("done",), "used"),
    (IMPORT, "_run_one", "SET status = 'running'", ("queued",), "running"),
    (IMPORT, "_run_one", "SET status = 'done', raw_json = ?", ("running",), "done"),
    (IMPORT, "_run_one", "SET status = 'failed', error = ?, finished_at = ?", ("running",), "failed"),
    (IMPORT, "process_queue", "SET status = 'failed', error = 'budget'", ANY, "failed"),
    (IMPORT, "process_queue", "SET status = 'failed', error = 'stale'", ("running",), "failed"),
    (IMPORT, "purge", "WHEN status = 'done' THEN 'expired'", ("done",), "expired"),
    (MERGE, "_note_failure", "SET status = 'failed', error = ?, raw_json = NULL", ("done",), "failed"),
]


def test_guide_import_writers_match_import_transitions():
    _check("guide_import", "status", IMPORT_SITES, IMPORT_MOVES, guest_guide_import.IMPORT_TRANSITIONS)
