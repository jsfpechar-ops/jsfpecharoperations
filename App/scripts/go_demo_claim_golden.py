"""Golden rows for brief 1597a demo claim exports.

Run from App/:

    .venv/bin/python scripts/go_demo_claim_golden.py
    .venv/bin/python scripts/go_demo_claim_golden.py --check
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "stays" / "testdata" / "demo_claim_golden.json"

NOW = datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc)


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
        "cases": [
            {
                "name": "provisional",
                "state": "provisional",
                "email": "guest@example.test",
                "locked": False,
                "declared_guests": 2,
                "outbox_kind": "claim",
            },
            {
                "name": "claimed",
                "state": "claimed",
                "email": "guest@example.test",
                "locked": False,
                "declared_guests": None,
                "outbox_kind": "",
            },
            {
                "name": "locked",
                "state": "claimed",
                "email": "guest@example.test",
                "locked": True,
                "declared_guests": None,
                "outbox_kind": "",
            },
        ],
    }
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.exit(main())