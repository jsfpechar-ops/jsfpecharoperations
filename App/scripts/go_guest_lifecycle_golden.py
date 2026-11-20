"""Golden HTTP answers for brief 1735 (guest_lifecycle).

Run from App/:

    .venv/bin/python scripts/go_guest_lifecycle_golden.py
    .venv/bin/python scripts/go_guest_lifecycle_golden.py --check
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "stays" / "testdata" / "guest_lifecycle_golden.json"

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
    doc = 
    doc = {
        "now": NOW.isoformat(),
        "seed": [],
        "cases": [
  {
    "body": "_csrf=golden",
    "flash_key": "flash.error.reported_kept",
    "location": "/guests/201",
    "method": "POST",
    "name": "archive_sent_refused",
    "path": "/guests/201/archive",
    "status": 303,
    "user": 1
  },
  {
    "body": "_csrf=golden",
    "flash_key": "flash.housebook.archived",
    "location": "/housebook",
    "method": "POST",
    "name": "archive_ok",
    "path": "/guests/202/archive",
    "status": 303,
    "user": 1
  },
  {
    "body": "_csrf=golden",
    "flash_key": "flash.housebook.restored",
    "location": "/housebook",
    "method": "POST",
    "name": "unarchive_ok",
    "path": "/guests/203/unarchive",
    "status": 303,
    "user": 1
  },
  {
    "body": "_csrf=golden",
    "flash_key": "flash.error.reported_kept",
    "location": "/guests/204",
    "method": "POST",
    "name": "delete_sent_refused",
    "path": "/guests/204/delete",
    "status": 303,
    "user": 1
  },
  {
    "body": "_csrf=golden",
    "flash_key": "flash.guests.removed",
    "location": "/reservations/20",
    "method": "POST",
    "name": "delete_ok",
    "path": "/guests/205/delete",
    "status": 303,
    "user": 1
  },
  {
    "body": "_csrf=golden",
    "flash_key": "flash.error.confirm_duplicate",
    "location": "/guests/206",
    "method": "POST",
    "name": "resend_no_confirm",
    "path": "/guests/206/resend",
    "status": 303,
    "user": 1
  }
],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.exit(main())
