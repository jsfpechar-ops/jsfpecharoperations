"""Golden redirects for brief 1707 smart-locks POST routes.

Run from App/:

    .venv/bin/python scripts/go_smart_locks_golden.py
    .venv/bin/python scripts/go_smart_locks_golden.py --check
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "properties" / "testdata" / "smart_locks_golden.json"

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


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
                "name": "signed_out_setup",
                "method": "POST",
                "path": "/smart-locks/setup",
                "status": 303,
                "location": "/login",
                "flash_key": "",
                "body": "_csrf=x",
                "user": 0,
            },
            {
                "name": "signed_out_refresh",
                "method": "POST",
                "path": "/smart-locks/refresh",
                "status": 303,
                "location": "/login",
                "flash_key": "",
                "body": "_csrf=x",
                "user": 0,
            },
            {
                "name": "signed_out_remove",
                "method": "POST",
                "path": "/smart-locks/remove",
                "status": 303,
                "location": "/login",
                "flash_key": "",
                "body": "_csrf=x",
                "user": 0,
            },
        ],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())