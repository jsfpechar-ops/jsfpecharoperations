"""Golden HTTP answers for brief 1710b GET /booking-sites.

Run from App/:

    .venv/bin/python scripts/go_booking_sites_list_golden.py
    .venv/bin/python scripts/go_booking_sites_list_golden.py --check
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = (
    APP.parent
    / "go"
    / "internal"
    / "web"
    / "booking"
    / "testdata"
    / "booking_sites_list_golden.json"
)

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
                "name": "signed_out",
                "method": "GET",
                "path": "/booking-sites",
                "user": 0,
                "status": 303,
                "location": "/login",
            },
            {
                "name": "single_apartment",
                "method": "GET",
                "path": "/booking-sites",
                "user": 1,
                "status": 303,
                "location": "/apartments/11/booking-site",
            },
            {
                "name": "list_two",
                "method": "GET",
                "path": "/booking-sites",
                "user": 2,
                "status": 200,
                "location": "",
            },
        ],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())