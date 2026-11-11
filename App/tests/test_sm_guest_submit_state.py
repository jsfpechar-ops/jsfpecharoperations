"""Pin every write of guest.submit_state against reporting.TRANSITIONS (brief 1105).

guest.submit_state is the police-filing record of each guest. This test reads
the Python and Go writer sources as text, finds every statement that writes the
column, and compares them with a pinned list. It fails when a write is added,
removed or changed, when a pinned move is not in reporting.TRANSITIONS, and
when the table lists a move no pinned writer makes. It changes nothing at
runtime: no writer reads the table.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app import reporting

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
APP_PKG = APP / "app"
GO_DIR = REPO / "go"

PENDING = reporting.PENDING
SENT = reporting.SENT
ERROR = reporting.ERROR
BLOCKED = reporting.BLOCKED
NOT_REQUIRED = reporting.NOT_REQUIRED
STATES = {PENDING, SENT, ERROR, BLOCKED, NOT_REQUIRED}
NEW = "<new row>"  # an INSERT: the row has no state yet
# From-any: the write has no submit_state test in its WHERE clause, and collect
# admits every state (a host resend carries sent or blocked guests; nothing
# excludes a reportable guest still marked not_required).
ANY = frozenset(STATES)

# (file from the repo root, kind, token, from-states, to-states, guard, writer)
#   kind "dict":      a "submit_state": <token> key in a values dict or Go map
#   kind "subscript": payload["submit_state"] = <token>
#   kind "kwarg":     submit_state=<token> keyword argument
#   kind "sql":       UPDATE guest SET submit_state = ...; the token is "cas" when
#                     the WHERE clause also tests submit_state, "none" when not
#   guard: "cas" compare-and-set on the old state, "none" no state test in the
#   WHERE clause (from-any in SQL; the from-states are what the code just before
#   the write admits), "insert" a new row.
PINNED = [
    ("App/app/reporting.py", "dict", "SENT", ANY, {SENT}, "none",
     "plan_outcome: accepted"),
    ("App/app/reporting.py", "dict", "new_state", ANY, {ERROR, BLOCKED, SENT}, "none",
     "plan_outcome: refused, or record-level duplicate (150) = sent"),
    ("App/app/reporting.py", "dict", "NOT_REQUIRED", {PENDING, ERROR, BLOCKED}, {NOT_REQUIRED}, "none",
     "collect_sendable: guest not reportable"),
    ("App/app/reporting.py", "sql", "cas", {PENDING, ERROR, BLOCKED}, {SENT}, "cas",
     "mark_filed_by_hand"),
    ("App/app/reporting.py", "sql", "cas", {SENT}, {PENDING, ERROR, BLOCKED}, "cas",
     "undo_filed_by_hand: back to manual_prev_state, else pending"),
    ("App/app/routes/admin.py", "dict", "(", {NEW}, {PENDING, NOT_REQUIRED}, "insert",
     "guest_create"),
    ("App/app/routes/admin.py", "subscript", "reporting.NOT_REQUIRED",
     {PENDING, ERROR, BLOCKED, NOT_REQUIRED}, {NOT_REQUIRED}, "cas",
     "guest_update: nationality not reportable (sent is kept)"),
    ("App/app/routes/admin.py", "subscript", "reporting.PENDING",
     {ERROR, BLOCKED, NOT_REQUIRED}, {PENDING}, "cas",
     "guest_update: rule 10.4(5)"),
    ("App/app/routes/guest.py", "dict", "(",
     {NEW, PENDING, ERROR, BLOCKED, NOT_REQUIRED}, {PENDING, NOT_REQUIRED}, "cas",
     "guest form save: insert, or edit of a row that is not sent"),
    ("App/app/demo.py", "kwarg", "(", {NEW}, {PENDING, NOT_REQUIRED}, "insert",
     "_guest: setup-guide demo stay"),
    ("go/internal/ubyport/outcome.go", "dict", "outcomeSent", ANY, {SENT}, "none",
     "PlanOutcome: accepted (applied by updateGuest in store.go)"),
    ("go/internal/ubyport/outcome.go", "dict", "newState", ANY, {ERROR, BLOCKED, SENT}, "none",
     "PlanOutcome: refused, or duplicate = sent (applied by updateGuest in store.go)"),
    ("go/internal/ubyport/collect.go", "sql", "none", {PENDING, ERROR, BLOCKED}, {NOT_REQUIRED}, "none",
     "collect: guest not reportable"),
]

# "submit_state": <value>, but not the update_if guard {"submit_state": guest["submit_state"]}
# and not the Go allow-list entry "submit_state": true.
DICT_RE = re.compile(r'"submit_state"\s*:\s*(?!\w+\[\s*"submit_state"\s*\])(?!true\b)([\w.]+|\()')
SUBSCRIPT_RE = re.compile(r'\[\s*"submit_state"\s*\]\s*=(?!=)\s*([\w.]+|\()')
KWARG_RE = re.compile(r'(?<![\w"\'.])submit_state=(?!=)\s*([\w.]+|\()')
UPDATE_RE = re.compile(r'UPDATE guest SET ([^"`]*)')
ASSIGN_RE = re.compile(r"\bsubmit_state\s*=")


def _sources():
    py = sorted(APP_PKG.rglob("*.py"))
    go = sorted(p for p in GO_DIR.rglob("*.go") if not p.name.endswith("_test.go"))
    return py + go


def _found():
    """(file, kind, token) for every write of submit_state in the writer sources."""
    found = []
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO).as_posix()
        for m in DICT_RE.finditer(text):
            found.append((rel, "dict", m.group(1)))
        for m in SUBSCRIPT_RE.finditer(text):
            found.append((rel, "subscript", m.group(1)))
        for m in KWARG_RE.finditer(text):
            found.append((rel, "kwarg", m.group(1)))
        # Join adjacent Python string literals split over lines.
        joined = re.sub(r'"\s*\n\s*f?"', "", text)
        for m in UPDATE_RE.finditer(joined):
            parts = re.split(r"\bWHERE\b", m.group(1), maxsplit=1)
            if not ASSIGN_RE.search(parts[0]):
                continue
            where = parts[1] if len(parts) > 1 else ""
            found.append((rel, "sql", "cas" if ASSIGN_RE.search(where) else "none"))
    return found


def _pinned_moves():
    moves = set()
    for _file, _kind, _token, froms, tos, _guard, _writer in PINNED:
        for old in froms:
            if old == NEW:
                continue
            for new in tos:
                if old != new:
                    moves.add((old, new))
    return moves


def test_scan_finds_the_known_writers():
    """The scanners are not silently matching nothing."""
    assert len(_found()) >= len(PINNED)


def test_every_write_is_pinned():
    found = Counter(_found())
    pinned = Counter(entry[:3] for entry in PINNED)
    assert found == pinned, (
        "A write of guest.submit_state was added, removed or changed. "
        f"Only in the code: {sorted((found - pinned).elements())}. "
        f"Only in PINNED: {sorted((pinned - found).elements())}. "
        "Update PINNED and reporting.TRANSITIONS to what the code does."
    )


def test_pinned_states_are_real():
    for entry in PINNED:
        assert set(entry[3]) <= STATES | {NEW}, entry
        assert set(entry[4]) <= STATES, entry


def test_sql_pins_name_their_guard():
    for _file, kind, token, _froms, _tos, guard, writer in PINNED:
        if kind == "sql":
            assert token == guard, writer


def test_every_pinned_move_is_in_transitions():
    for old, new in sorted(_pinned_moves()):
        assert new in reporting.TRANSITIONS.get(old, set()), (
            f"{old} -> {new} is made by a writer but missing from reporting.TRANSITIONS"
        )


def test_transitions_lists_no_move_the_code_does_not_make():
    table = {(old, new) for old, targets in reporting.TRANSITIONS.items() for new in targets}
    assert table == _pinned_moves()


def test_transitions_covers_every_state():
    assert set(reporting.TRANSITIONS) == STATES
    for old, targets in reporting.TRANSITIONS.items():
        assert targets <= STATES
        assert old not in targets


def test_new_rows_start_pending_or_not_required():
    starts = set()
    for entry in PINNED:
        if NEW in entry[3]:
            starts |= set(entry[4])
    assert starts == {PENDING, NOT_REQUIRED}


def test_go_batch_writes_go_through_the_generic_writer():
    store = (GO_DIR / "internal" / "ubyport" / "store.go").read_text(encoding="utf-8")
    assert re.search(r'"submit_state":\s+true,', store)
    assert '"UPDATE guest SET " + strings.Join(sets, ", ")' in store


def test_nothing_reads_transitions_at_runtime():
    own = (APP_PKG / "reporting.py").read_text(encoding="utf-8")
    assert len(re.findall(r"\bTRANSITIONS\b", own)) == 1
    for path in APP_PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "reporting.TRANSITIONS" not in text, path
        assert not re.search(r"from \.?reporting import[^\n]*\bTRANSITIONS\b", text), path
