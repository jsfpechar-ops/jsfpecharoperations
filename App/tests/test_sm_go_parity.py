"""1119: every Python transition table equals its Go twin in go/internal/statemachine/tables.go.

The Go file is read as text, never compiled. Its layout is fixed (see the
package comment there): one machine per `"table.column": {` line, one row per
line as `"from": {"to1", "to2"},`, the machine closed by `},`. A table changed
in one language and not the other fails here with the machine and the pair.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import (
    billing,
    booking_site,
    claim,
    cleaning_codes,
    door_codes,
    guest_guide_import,
    mail,
    meta_capi,
    payment_request,
    push,
    reporting,
)

APP = Path(__file__).resolve().parents[1]
TABLES_GO = APP.parent / "go" / "internal" / "statemachine" / "tables.go"

NO_ROW = "<none>"

# "table.column": the Python table. None keys (claim, meta_capi, submission)
# are the Go NoRow. Sets and tuples are compared as sets.
PYTHON_TABLES = {
    "ad_click.send_state": meta_capi.SEND_TRANSITIONS,
    "billing_account.status": billing.TRANSITIONS,
    "cleaning_code.state": cleaning_codes.TRANSITIONS,
    "door_code.state": door_codes.TRANSITIONS,
    "email_outbox.state": mail.OUTBOX_TRANSITIONS,
    "guest.submit_state": reporting.TRANSITIONS,
    "guide_import.status": guest_guide_import.IMPORT_TRANSITIONS,
    "payment_request.status": payment_request._TRANSITIONS,
    "push_outbox.state": push.PUSH_TRANSITIONS,
    "reservation_claim.state": claim.TRANSITIONS,
    "site_booking.status": booking_site._TRANSITIONS,
    "submission.state": reporting.SUBMISSION_TRANSITIONS,
}

MACHINE_RE = re.compile(r'^\t"([a-z_]+\.[a-z_]+)": \{$')
ROW_RE = re.compile(r'^\t\t"([^"]+)":\s+\{(.*)\},$')
CLOSE = "\t},"
STATE_RE = re.compile(r'"([^"]*)"')


def parse_go_tables() -> dict:
    """{machine: {from_state: set(to_states)}} from tables.go, plain line scan."""
    lines = TABLES_GO.read_text(encoding="utf-8").splitlines()
    start = lines.index("var Tables = map[string]map[string][]string{")
    tables: dict = {}
    machine = None
    for number, line in enumerate(lines[start + 1:], start + 2):
        if line == "}":
            assert machine is None, f"tables.go:{number}: machine {machine} is not closed"
            return tables
        if machine is None:
            found = MACHINE_RE.match(line)
            assert found, f"tables.go:{number}: expected a machine line, got {line!r}"
            machine = found.group(1)
            assert machine not in tables, f"tables.go:{number}: machine {machine} listed twice"
            tables[machine] = {}
        elif line == CLOSE:
            machine = None
        else:
            found = ROW_RE.match(line)
            assert found, f"tables.go:{number}: expected a row line in {machine}, got {line!r}"
            source = found.group(1)
            assert source not in tables[machine], f"tables.go:{number}: {machine} row {source!r} listed twice"
            tables[machine][source] = set(STATE_RE.findall(found.group(2)))
    raise AssertionError("tables.go: the closing '}' of Tables was not found")


def python_rows(table: dict) -> dict:
    return {(NO_ROW if source is None else source): set(targets) for source, targets in table.items()}


def test_go_has_exactly_the_python_machines():
    go = parse_go_tables()
    assert set(go) == set(PYTHON_TABLES), (
        f"machines only in Go: {sorted(set(go) - set(PYTHON_TABLES))}; "
        f"machines only in Python: {sorted(set(PYTHON_TABLES) - set(go))}"
    )


@pytest.mark.parametrize("machine", sorted(PYTHON_TABLES))
def test_machine_matches_go(machine):
    go = parse_go_tables().get(machine)
    assert go is not None, f"{machine}: not in tables.go"
    py = python_rows(PYTHON_TABLES[machine])
    py_pairs = {(a, b) for a, targets in py.items() for b in targets}
    go_pairs = {(a, b) for a, targets in go.items() for b in targets}
    missing_in_go = sorted(py_pairs - go_pairs)
    extra_in_go = sorted(go_pairs - py_pairs)
    assert not missing_in_go and not extra_in_go, (
        f"{machine}: Python and Go differ. "
        f"In Python only (add to tables.go): {missing_in_go}. "
        f"In Go only (add to the Python table, or remove from tables.go): {extra_in_go}."
    )
    assert set(py) == set(go), (
        f"{machine}: rows differ. In Python only: {sorted(set(py) - set(go))}. "
        f"In Go only: {sorted(set(go) - set(py))}."
    )


def test_go_no_row_constant_is_the_literal_used_in_tables():
    text = TABLES_GO.read_text(encoding="utf-8")
    assert f'const NoRow = "{NO_ROW}"' in text
