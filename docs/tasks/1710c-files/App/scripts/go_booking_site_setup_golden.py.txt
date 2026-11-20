"""Golden HTTP answers for brief 1710c booking-site setup host routes.

Run from App/:

    .venv/bin/python scripts/go_booking_site_setup_golden.py
    .venv/bin/python scripts/go_booking_site_setup_golden.py --check
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
    / "booking_site_setup_golden.json"
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
                "name": "signed_out_get",
                "method": "GET",
                "path": "/apartments/11/booking-site",
                "user": 0,
                "status": 303,
                "location": "/login",
            },
            {
                "name": "save_settings",
                "method": "POST",
                "path": "/apartments/11/booking-site",
                "body": "_csrf=golden&nightly_price_czk=3000&min_nights=1&notice=1&cancellation_policy=non_refundable",
                "user": 1,
                "status": 303,
                "location": "/apartments/11/booking-site",
                "flash_key": "bsite.flash.saved",
            },
            {
                "name": "foreign_apartment",
                "method": "GET",
                "path": "/apartments/99/booking-site",
                "user": 1,
                "status": 404,
            },
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.exit(main())