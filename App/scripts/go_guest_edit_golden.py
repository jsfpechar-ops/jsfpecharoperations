"""Golden HTTP answers for brief 1733 host guest add/edit routes.

Run from App/:

    .venv/bin/python scripts/go_guest_edit_golden.py
    .venv/bin/python scripts/go_guest_edit_golden.py --check

Shape matches guest_edit_test.go; full FastAPI replay ships with executor step 2
when App/.venv is available in CI for this brief.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "stays" / "testdata" / "guest_edit_golden.json"

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
                "name": "signed_out_new",
                "method": "GET",
                "path": "/reservations/101/guests/new",
                "body": "",
                "user": 0,
                "status": 303,
                "location": "/login",
                "flash_key": "",
            },
            {
                "name": "new_form_ok",
                "method": "GET",
                "path": "/reservations/101/guests/new",
                "body": "",
                "user": 1,
                "status": 200,
                "location": "",
                "flash_key": "",
            },
            {
                "name": "create_validation",
                "method": "POST",
                "path": "/reservations/101/guests",
                "body": "_csrf=golden&surname=&first_name=",
                "user": 1,
                "status": 200,
                "location": "",
                "flash_key": "",
            },
            {
                "name": "create_ok",
                "method": "POST",
                "path": "/reservations/101/guests",
                "body": "_csrf=golden&surname=Novak&first_name=Jan&nationality=CZE&birth_date=01011990&res_country=CZE&purpose=10&legal_ack=1&signature=data:image/png;base64,AAAA",
                "user": 1,
                "status": 303,
                "location": "/reservations/101",
                "flash_key": "flash.guests.added",
            },
            {
                "name": "edit_not_found",
                "method": "GET",
                "path": "/guests/99999",
                "body": "",
                "user": 1,
                "status": 404,
                "location": "",
                "flash_key": "",
            },
            {
                "name": "update_restricted",
                "method": "POST",
                "path": "/guests/102",
                "body": "_csrf=golden",
                "user": 1,
                "status": 303,
                "location": "/reservations/101",
                "flash_key": "flash.error.guest_restricted",
            },
            {
                "name": "update_filed_locked",
                "method": "POST",
                "path": "/guests/103",
                "body": "_csrf=golden&surname=Changed&first_name=Guest&nationality=DEU",
                "user": 1,
                "status": 303,
                "location": "/guests/103",
                "flash_key": "flash.error.guest_filed_locked",
            },
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.exit(main())