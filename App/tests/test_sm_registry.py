"""1171: every stored state/status column is pinned by a TRANSITIONS table or exempt with a reason.

The columns come from the real schema: the SQLite schema the app builds
(SCHEMA, ADDED_COLUMNS and the numbered migrations) plus a text scan of
App/migrations_pg/*.sql, so a column added to only one backend still shows up.
A new `state`, `status`, `*_state` or `*_status` column fails here until it has
a pin test (test_sm_<machine>.py) or an EXEMPT line with a reason.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import db
from test_sm_go_parity import PYTHON_TABLES

APP = Path(__file__).resolve().parents[1]
COLUMN_RE = re.compile(r"(^|_)(state|status)$")
PG_TABLE_RE = re.compile(r"^CREATE TABLE (?:IF NOT EXISTS )?(?:public\.)?(\w+) \(", re.MULTILINE)
PG_COLUMN_RE = re.compile(r"^\s+(\w+)\s+(?:text|bigint|integer|boolean|smallint|numeric|character)", re.MULTILINE | re.IGNORECASE)
PG_ADD_RE = re.compile(r"ALTER TABLE\s+(?:ONLY\s+)?(?:public\.)?(\w+)\s+ADD COLUMN\s+(?:IF NOT EXISTS\s+)?(\w+)", re.IGNORECASE)

PINNED = set(PYTHON_TABLES)

# "table.column": why it has no TRANSITIONS table. Keep each reason to one line.
EXEMPT = {
    "bank_payment.status": "CHECK of 4 values, one writer (bank_import).",
    "billing_month_snapshot.status": "Copy of billing_account.status taken once a month; never updated.",
    "cleaning_event.state": "CHECK of 3 values, written by the calendar sync only.",
    "data_subject_request.status": "CHECK of 5 values, one writer (dsr).",
    "guest.manual_prev_state": "Stores the submit_state an undo restores; the machine is guest.submit_state.",
    "guest_question.status": "CHECK of 3 values, one writer.",
    "guide_item.state": "CHECK, one writer (guide facts).",
    "ical_feed.last_status": "Result of the last fetch, overwritten every poll; no transitions.",
    "invoice.vat_status": "Snapshot of the seller's VAT status at issue; never changes.",
    "legal_entity.vat_status": "Fact about the company set by the host, not a lifecycle.",
    "lock_account.status": "Connection health of a smart-lock account; set by the lock sync.",
    "push_outbox.last_status": "Last HTTP result text of a push attempt; the machine is push_outbox.state.",
    "reservation.status": "Two values (confirmed, cancelled).",
    "stripe_account.onboarding_state": "Mirrors Stripe; Stripe decides the transitions.",
}

HELP = (
    "New or unlisted state/status column(s): {names}.\n"
    "Either add a TRANSITIONS table in the owning module, a pin test "
    "App/tests/test_sm_<machine>.py and (if Go writes it) a twin in "
    "go/internal/statemachine/tables.go plus a PYTHON_TABLES entry in "
    "test_sm_go_parity.py, or add \"table.column\" to EXEMPT in "
    "App/tests/test_sm_registry.py with a one-line reason. "
    "Rules: docs/context/rules.md#state-machines"
)


def _sqlite_columns() -> set:
    found = set()
    for table, columns in db._expected_sqlite_columns().items():
        for column in columns:
            if COLUMN_RE.search(column[0]):
                found.add(f"{table}.{column[0]}")
    return found


def _postgres_columns() -> set:
    found = set()
    for path in sorted((APP / "migrations_pg").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for block in re.split(r"(?m)^(?=CREATE TABLE )", text):
            head = PG_TABLE_RE.match(block)
            if not head:
                continue
            body = block.split("\n);", 1)[0]
            for column in PG_COLUMN_RE.findall(body):
                if COLUMN_RE.search(column):
                    found.add(f"{head.group(1)}.{column}")
        for table, column in PG_ADD_RE.findall(text):
            if COLUMN_RE.search(column):
                found.add(f"{table}.{column}")
    return found


def discovered() -> set:
    return _sqlite_columns() | _postgres_columns()


def test_every_state_column_is_pinned_or_exempt():
    missing = sorted(discovered() - PINNED - set(EXEMPT))
    assert not missing, HELP.format(names=", ".join(missing))


def test_exempt_entries_are_current():
    found = discovered()
    stale = sorted(set(EXEMPT) - found)
    assert not stale, f"EXEMPT lists columns that no longer exist: {', '.join(stale)}. Remove them."
    both = sorted(set(EXEMPT) & PINNED)
    assert not both, f"Pinned machines must not be in EXEMPT: {', '.join(both)}. Remove them."
    assert all(reason.strip() for reason in EXEMPT.values()), "Every EXEMPT entry needs a reason."


def test_pinned_columns_exist():
    gone = sorted(PINNED - discovered())
    assert not gone, f"PYTHON_TABLES names columns that do not exist: {', '.join(gone)}"
