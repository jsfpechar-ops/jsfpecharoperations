#!/usr/bin/env python3
"""Write the Python oracle for the Go UbyPort outcome port (reporting.plan_outcome).

Dev tool, never run in production. Invented test data only: it reads
tests/golden/ubyport/outcome/cases.json, never reads .env, config files or the
database, and makes no network calls. Usage: ubyport_golden_outcome.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

APP_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = APP_ROOT / "tests" / "golden" / "ubyport" / "outcome" / "cases.json"
DEFAULT_OUT = APP_ROOT / "tests" / "golden" / "ubyport" / "outcome"
SUBMISSION_ID = 900
NOW = "2026-11-01T10:00:00+00:00"

sys.path.insert(0, str(APP_ROOT))

from app import reporting  # noqa: E402
from app.ubyport.client import SubmissionResult  # noqa: E402


def make_receipt_lookup(receipts_held: List[int]):
    """Return the id when it holds a receipt, else None; a falsy id is None."""

    def lookup(previous_submission_id):
        if not previous_submission_id:
            return None
        return previous_submission_id if previous_submission_id in receipts_held else None

    return lookup


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    pairs = [(dict(guest), {"id": guest["reservation_id"]}) for guest in case["guests"]]
    raw = case["result"]
    result = SubmissionResult(
        endpoint="test",
        request_xml="",
        response_xml="",
        header_errors=raw["header_errors"],
        record_errors=list(raw["record_errors"]),
        receipt_pdf=raw["receipt_pdf"],
    )
    plan = reporting.plan_outcome(
        pairs,
        result,
        SUBMISSION_ID,
        NOW,
        case["codebook"],
        case["severities"],
        receipt_lookup=make_receipt_lookup(list(case["receipts_held"])),
    )
    return {
        "state": plan["state"],
        "accepted": plan["accepted"],
        "failed": plan["failed"],
        "blocked": plan["blocked"],
        "first_accepts": plan["first_accepts"],
        "duplicate_accepts": plan["duplicate_accepts"],
        "guest_writes": [[guest_id, values] for guest_id, values in plan["guest_writes"]],
        "exhausted": [guest["id"] for guest, _reservation in plan["exhausted"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="directory for expected.json")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    expected: Dict[str, Any] = {}
    for case in cases:
        if case["name"] in expected:
            raise SystemExit(f"duplicate case name: {case['name']}")
        expected[case["name"]] = run_case(case)

    args.out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(expected, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    (args.out / "expected.json").write_text(text, encoding="utf-8")
    print(f"wrote {len(expected)} cases to {args.out / 'expected.json'}")


if __name__ == "__main__":
    main()
