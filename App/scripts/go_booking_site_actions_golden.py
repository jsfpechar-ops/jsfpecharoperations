"""Golden shape for brief 1710d host booking-site POST routes.

Run from App/:

    .venv/bin/python scripts/go_booking_site_actions_golden.py
    .venv/bin/python scripts/go_booking_site_actions_golden.py --check
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "booking" / "testdata" / "booking_site_actions_golden.json"

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
        "routes": [
            "POST /apartments/{apartment_id}/booking-site/pay",
            "POST /apartments/{apartment_id}/booking-site/confirm",
            "POST /apartments/{apartment_id}/booking-site/decline",
            "POST /apartments/{apartment_id}/booking-site/cancel",
        ],
        "flash_keys": [
            "payments.page.saved",
            "bsite.err.direct_taken",
            "bsite.flash.direct_confirm",
            "bsite.flash.cancelled_direct",
        ],
    }
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())