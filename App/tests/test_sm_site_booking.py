"""Pin every write of site_booking.status against booking_site._TRANSITIONS (brief 1103).

Reads the writer sources as text. Fails when a write is added, removed or
changed, and when a pinned move is not allowed by the table. Writers are not
edited by this test; the table lists only what the code does today.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from app import booking_site

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
APP_PKG = APP / "app"

# Moves the code is known to make that the table does not allow:
# (from-state, to-state, reason). Empty: the code and the table agree.
KNOWN_EXCEPTIONS: set = set()

# 1. Direct SQL writers: (file, from-states in the WHERE ... status IN (...), to-state).
PINNED_SQL = [
    ("booking_direct.py", {"requested", "expired"}, "paid"),
    ("booking_direct.py", {"requested", "expired"}, "cancelled"),
    ("booking_webhook.py", {"pending", "expired"}, "paid"),
]

# 2. The one generic writer: set_status builds UPDATE ... SET status = ? itself.
PINNED_DYNAMIC = ["booking_site.py"]

# 3. Callers of booking_site.set_status with a literal target: (file, from-states, to-state).
#    The from-states are read from the code around the call by the brief author.
PINNED_CALLS = [
    ("booking_cancel.py", {"paid"}, "cancelled"),
    ("booking_cancel.py", {"cancelled"}, "refunded"),
    ("booking_checkout.py", {"pending"}, "expired"),
    ("booking_checkout.py", {"requested"}, "expired"),
    ("booking_webhook.py", {"pending"}, "expired"),
    ("booking_webhook.py", {"pending", "expired"}, "clash_refunded"),
]

# 3b. Moves the table allows that no writer makes today (see the brief's Open questions).
UNUSED_TABLE_MOVES = {("paid", "refunded"), ("paid", "clash_refunded")}

# 4. Row creation: the only place a status is first written.
PINNED_INSERT_FILES = ["booking_site.py"]
PINNED_INSERT_STATES = {"pending", "requested"}

# 5. The demo seeder (mock-only, removed by "Clear demo") inserts one booking
#    directly as 'paid' (a new row, not a move) and later sets reservation_id
#    on it with no status change. Pinned by function, helper and state.
#    (file, function, helper, status written or None)
PINNED_DEMO_HELPER_WRITES = [
    ("demo.py", "_enrich_extras", "insert", "paid"),
    ("demo.py", "_enrich_extras", "update", None),
]
PINNED_DEMO_NAME_MENTIONS = 1  # the "Clear demo" table list, a DELETE by apartment_id


def _py_files():
    return sorted(p for p in APP_PKG.rglob("*.py"))


def _joined(path: Path) -> str:
    """Source text with adjacent string literals on separate lines joined."""
    text = path.read_text(encoding="utf-8")
    return re.sub(r"\"\s*\n\s*\"", "", text)


def _update_statements(text: str):
    """Yield the SET part and the WHERE part of every UPDATE site_booking literal."""
    for m in re.finditer(r"UPDATE site_booking SET ([^\"]*)", text):
        parts = re.split(r"\bWHERE\b", m.group(1), maxsplit=1)
        yield parts[0], (parts[1] if len(parts) > 1 else "")


def _status_writers():
    """(file name, from-states or None, to-state or None) for every status UPDATE."""
    found = []
    for path in _py_files():
        for set_part, where_part in _update_statements(_joined(path)):
            if not re.search(r"\bstatus\s*=", set_part):
                continue
            to_match = re.search(r"\bstatus\s*=\s*'(\w+)'", set_part)
            from_match = re.search(r"\bstatus IN \(([^)]*)\)", where_part)
            froms = (frozenset(re.findall(r"'(\w+)'", from_match.group(1)))
                     if from_match else None)
            found.append((path.name, froms, to_match.group(1) if to_match else None))
    return found


def _set_status_calls():
    """(file name, to-state) for every booking_site.set_status call with a literal target."""
    found = []
    for path in _py_files():
        if path.name == "booking_site.py":
            continue
        text = _joined(path)
        for m in re.finditer(r"booking_site\.set_status\(\s*[^,]+,\s*\"(\w+)\"", text):
            found.append((path.name, m.group(1)))
        # a call whose target is not a literal would escape the pin
        calls = len(re.findall(r"booking_site\.set_status\(", text))
        literal = len(re.findall(r"booking_site\.set_status\(\s*[^,]+,\s*\"\w+\"", text))
        assert calls == literal, f"{path.name}: set_status with a non-literal target"
    return found


def test_scan_finds_something():
    """The scanners are not silently matching nothing."""
    assert len(_status_writers()) >= 4
    assert len(_set_status_calls()) >= 6


def test_direct_sql_writers_are_pinned():
    found = sorted(
        (f, tuple(sorted(froms)) if froms else None, to)
        for f, froms, to in _status_writers() if to is not None
    )
    pinned = sorted((f, tuple(sorted(froms)), to) for f, froms, to in PINNED_SQL)
    assert found == pinned, (
        "A direct UPDATE site_booking SET status = '...' changed. Update PINNED_SQL "
        "and make sure booking_site._TRANSITIONS allows the move."
    )


def test_dynamic_writer_is_pinned():
    found = sorted(f for f, froms, to in _status_writers() if to is None)
    assert found == sorted(PINNED_DYNAMIC), (
        "Only booking_site.set_status may write status = ? ; found " + repr(found)
    )


def test_set_status_callers_are_pinned():
    found = sorted(_set_status_calls())
    pinned = sorted((f, to) for f, froms, to in PINNED_CALLS)
    assert found == pinned, (
        "A booking_site.set_status caller changed. Update PINNED_CALLS."
    )


def _demo_helper_writes(table: str = "site_booking"):
    """(file, function, helper, status literal or None) for db.insert/update calls on the table in demo.py."""
    path = APP_PKG / "demo.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for func in tree.body:
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"update", "update_if", "update_in", "insert", "insert_in"}
                and any(isinstance(a, ast.Constant) and a.value == table for a in node.args[:2])
            ):
                continue
            status = None
            for arg in node.args:
                if isinstance(arg, ast.Dict):
                    for key, value in zip(arg.keys, arg.values):
                        if isinstance(key, ast.Constant) and key.value == "status" and isinstance(value, ast.Constant):
                            status = value.value
            out.append((path.name, func.name, node.func.attr, status))
    return out


def test_no_other_code_touches_the_table_by_helper():
    """db.insert/update/update_in helpers take the table name as a string."""
    found = []
    for path in _py_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"""["']site_booking["']""", text):
            found.append(path.name)
    assert sorted(found) == sorted(PINNED_INSERT_FILES + ["demo.py"]), found
    source = (APP_PKG / "booking_site.py").read_text(encoding="utf-8")
    assert len(re.findall(r"""db\.\w+\(\s*["']site_booking["']""", source)) == 1
    assert 'db.insert("site_booking"' in source
    assert 'if status not in ("pending", "requested"):' in source
    assert PINNED_INSERT_STATES == {"pending", "requested"}


def test_demo_seeder_site_booking_writes_are_pinned():
    """demo.py is allowed exactly the pinned writes, by function, helper and state."""
    assert sorted(_demo_helper_writes()) == sorted(PINNED_DEMO_HELPER_WRITES)
    text = (APP_PKG / "demo.py").read_text(encoding="utf-8")
    mentions = len(re.findall(r"""["']site_booking["']""", text))
    assert mentions == len(PINNED_DEMO_HELPER_WRITES) + PINNED_DEMO_NAME_MENTIONS
    # a seeded status is a created row, so it must still be a real status
    for _f, _fn, helper, status in PINNED_DEMO_HELPER_WRITES:
        if helper == "insert":
            assert status in booking_site.STATUSES
    assert not re.search(r"UPDATE\s+site_booking|INSERT\s+INTO\s+site_booking", text, re.I)


def test_go_and_migrations_do_not_write_site_booking_status():
    go_dir = REPO / "go"
    for path in sorted(go_dir.rglob("*.go")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"UPDATE\s+site_booking", text, re.I), path
        assert not re.search(r"INSERT\s+INTO\s+site_booking", text, re.I), path
    for path in sorted((APP_PKG / "migrations").glob("*")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"UPDATE\s+site_booking", text, re.I), path


def test_every_pinned_move_is_in_the_table():
    moves = set()
    for _f, froms, to in PINNED_SQL + PINNED_CALLS:
        for frm in froms:
            moves.add((frm, to))
    for frm, to in sorted(moves):
        if (frm, to) in KNOWN_EXCEPTIONS:
            continue
        assert to in booking_site._TRANSITIONS[frm], f"{frm} -> {to} is not in _TRANSITIONS"


def test_table_states_match_statuses():
    table = booking_site._TRANSITIONS
    assert set(table) == set(booking_site.STATUSES)
    for to_states in table.values():
        assert to_states <= set(booking_site.STATUSES)


def test_table_has_no_unpinned_moves():
    """The table lists the pinned moves plus the known unused ones, nothing else."""
    used = {(frm, to) for _f, froms, to in PINNED_SQL + PINNED_CALLS for frm in froms}
    table = {(frm, to) for frm, tos in booking_site._TRANSITIONS.items() for to in tos}
    assert table - used == UNUSED_TABLE_MOVES
