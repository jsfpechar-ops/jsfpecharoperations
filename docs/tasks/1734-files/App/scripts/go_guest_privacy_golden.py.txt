"""Golden HTTP answers for brief 1734 (guest_privacy).

Run from App/:

    .venv/bin/python scripts/go_guest_privacy_golden.py
    .venv/bin/python scripts/go_guest_privacy_golden.py --check
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "stays" / "testdata" / "guest_privacy_golden.json"

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
    "flash_key": "",
    "location": "/login",
    "method": "POST",
    "name": "signed_out_restrict",
    "path": "/guests/101/restrict",
    "status": 303,
    "user": 0
  },
  {
    "body": "_csrf=golden&reason=note",
    "flash_key": "flash.guest.restricted",
    "location": "/reservations/10",
    "method": "POST",
    "name": "restrict_ok",
    "path": "/guests/101/restrict",
    "status": 303,
    "user": 1
  },
  {
    "body": "_csrf=golden",
    "flash_key": "flash.guest.unrestricted",
    "location": "/reservations/10",
    "method": "POST",
    "name": "unrestrict_ok",
    "path": "/guests/101/unrestrict",
    "status": 303,
    "user": 1
  },
  {
    "body": "_csrf=golden",
    "flash_key": "flash.error.czech_no_verification",
    "location": "/guests/102",
    "method": "POST",
    "name": "verify_czech_refused",
    "path": "/guests/102/verify-identity",
    "status": 303,
    "user": 1
  },
  {
    "body": "_csrf=golden",
    "flash_key": "flash.guests.id_check_recorded",
    "location": "/guests/103",
    "method": "POST",
    "name": "verify_ok",
    "path": "/guests/103/verify-identity",
    "status": 303,
    "user": 1
  },
  {
    "body": "",
    "flash_key": "",
    "location": "",
    "method": "GET",
    "name": "passport_hidden",
    "path": "/guests/104/passport-photo",
    "status": 403,
    "user": 1
  },
  {
    "body": "_csrf=golden&reason=support",
    "flash_key": "",
    "location": "/guests/105",
    "method": "POST",
    "name": "reveal_not_impersonating",
    "path": "/guests/105/reveal-identity",
    "status": 303,
    "user": 1
  }
],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.exit(main())
