"""The transport policy and fault keys agree with Go (A1b P1).

Both sides read go/internal/ubyport/testdata/transport_policy.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from app import reporting
from app.ubyport import faults

FIXTURE = Path(__file__).resolve().parents[2] / "go" / "internal" / "ubyport" / "testdata" / "transport_policy.json"


def test_backoff_cases_match_the_shared_fixture():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    now = datetime.fromisoformat(doc["now"])
    for case in doc["backoff"]:
        rows = [
            {
                "state": row["state"],
                "cause": row["cause"],
                "mode": row["mode"],
                "finished_at": (now - timedelta(minutes=row["minutes_ago"])).isoformat(),
            }
            for row in case["rows"]
        ]
        got = reporting.transport_backoff_from_rows(rows, now)
        if "next_minutes" in case:
            assert got == now + timedelta(minutes=case["next_minutes"]), case["name"]
        elif "next_utc" in case:
            assert got == datetime.fromisoformat(case["next_utc"]), case["name"]
        else:
            assert got is None, case["name"]


def test_fault_codes_match_the_shared_fixture():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in doc["faults"]:
        assert faults.code_for(case["cause"], case["detail"]) == case["code"], case
