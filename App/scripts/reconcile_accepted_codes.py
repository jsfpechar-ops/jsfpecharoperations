#!/usr/bin/env python3
"""Mark guests filed whose last UbyPort answer was an accept (K-F13).

Until the police letter of 24 September 2026, code 112 ("Oznámeno pozdě",
severity 0) was read as "batch not received", so guests whose record came back
with only 112 sit in ``error`` or ``blocked`` although the register holds them.
Resending them produces duplicates.

The decision is made from the guest's own submission row (the codes UbyPort
returned for that record), not from the stored message text. Dry run by
default: it prints counts and guest ids only, never personal data. Check two
or three of the listed guests in the UbyPort web application, then run again
with ``--apply``. A second ``--apply`` changes nothing.

    .venv/bin/python scripts/reconcile_accepted_codes.py
    .venv/bin/python scripts/reconcile_accepted_codes.py --apply
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import codelists, db, reporting  # noqa: E402
from app.ubyport import errors as uby_errors  # noqa: E402


def candidates():
    severities = codelists.error_severities()
    found = []
    rows = db.query(
        "SELECT * FROM guest WHERE submit_state IN (?, ?) AND submission_id IS NOT NULL",
        (reporting.ERROR, reporting.BLOCKED),
    )
    for guest in rows:
        submission = db.query_one("SELECT * FROM submission WHERE id = ?", (guest["submission_id"],))
        if not submission:
            continue
        guest_ids = json.loads(submission["guest_ids"] or "[]")
        record_errors = json.loads(submission["record_errors"] or "[]")
        if guest["id"] not in guest_ids:
            continue
        index = guest_ids.index(guest["id"])
        record = record_errors[index] if index < len(record_errors) else ""
        codes = uby_errors.split_codes(submission["header_errors"]) + uby_errors.split_codes(record)
        if codes and all(uby_errors.is_accepted_code(code, severities) for code in codes):
            found.append((guest, submission, codes))
    return found


def main(argv) -> int:
    apply = "--apply" in argv
    db.init_db()
    found = candidates()
    print(f"guests answered with accepted codes only: {len(found)}")
    for guest, submission, codes in found:
        print(f"  guest={guest['id']} submission={submission['id']} codes={';'.join(codes)}")
    if not apply:
        print("dry run: nothing changed. Re-run with --apply.")
        return 0
    marked = 0
    for guest, submission, codes in found:
        # Only if nothing moved the guest since the scan (a sweep or a host send).
        changed = db.update_if("guest", guest["id"], {
            "submit_state": reporting.SENT,
            "submitted_at": guest["submitted_at"] or submission["created_at"],
            "receipt_submission_id": guest["receipt_submission_id"]
            or (submission["id"] if submission["receipt_pdf"] else None),
            "last_errors": None,
            "submit_attempts": 0,
            "updated_at": db.utcnow(),
        }, {"submit_state": guest["submit_state"], "submission_id": guest["submission_id"]})
        if not changed:
            continue
        marked += 1
        db.audit(
            "guest_marked_filed_by_severity",
            f"guest={guest['id']} submission={submission['id']} codes={';'.join(codes)}",
            actor="operator",
        )
    print(f"marked filed: {marked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
