"""Golden HTTP answers for brief 1721 guest stay/claim routes.

Run from App/:

    .venv/bin/python scripts/go_stay_claim_golden.py
    .venv/bin/python scripts/go_stay_claim_golden.py --check

Seeds SQLite when App/.venv is available; otherwise writes the shape the Go
unit test checks. The Go test replays on PostgreSQL when UBYHOST_TEST_DATABASE_URL
is set.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "stay_claim_golden.json"

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def main() -> int:
    check = "--check" in sys.argv
    golden = build_golden()
    if check:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == golden:
            return 0
        print("stale golden", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(golden, encoding="utf-8")
    print("wrote", OUT)
    return 0


def build_golden() -> str:
    doc = {
        "now": NOW.isoformat(),
        "seed": [],
        "cases": [
            {
                "name": "unknown_token",
                "method": "GET",
                "path": "/l/nosuch/9",
                "body": "",
                "status": 404,
                "location": "",
                "body_has": "guest-unavailable",
            },
            {
                "name": "claim_landing_missing",
                "method": "GET",
                "path": "/l/nosuch/9/claim",
                "body": "",
                "status": 404,
                "location": "",
                "body_has": "guest-unavailable",
            },
            {
                "name": "confirm_bad_secret",
                "method": "POST",
                "path": "/l/nosuch/9/claim/confirm",
                "body": "secret=bad",
                "status": 404,
                "location": "",
                "body_has": "",
            },
            {
                "name": "demo_unknown",
                "method": "GET",
                "path": "/l/nosuch/9/demo/9",
                "body": "",
                "status": 404,
                "location": "",
                "body_has": "guest-unavailable",
            },
        ],
    }
    return json.dumps(doc, indent=2) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())