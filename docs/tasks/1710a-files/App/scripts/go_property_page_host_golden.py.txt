"""Golden HTTP answers for brief 1710a property page host routes.

Run from App/:

    .venv/bin/python scripts/go_property_page_host_golden.py
    .venv/bin/python scripts/go_property_page_host_golden.py --check

Shape matches go/internal/web/booking/property_page_host_test.go. Full FastAPI
replay lands when the executor runs with App/.venv in CI.
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
    / "property_page_host_golden.json"
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
                "path": "/apartments/11/page",
                "user": 0,
                "status": 303,
                "location": "/login",
            },
            {
                "name": "save_redirect",
                "method": "POST",
                "path": "/apartments/11/page",
                "body": "_csrf=golden&description=test",
                "user": 1,
                "status": 303,
                "location": "/apartments/11/page",
                "flash_key": "payments.page.saved",
            },
            {
                "name": "photo_move",
                "method": "POST",
                "path": "/apartments/11/page/photo-move",
                "body": "_csrf=golden&path=%2Fphotos%2Fproperty%2Fabcd.jpg&dir=up",
                "user": 1,
                "status": 303,
                "location": "/apartments/11/page",
            },
            {
                "name": "foreign_apartment",
                "method": "GET",
                "path": "/apartments/99/page",
                "user": 1,
                "status": 404,
            },
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.exit(main())