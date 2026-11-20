"""Golden HTTP answers for brief 1722 guest party routes.

Run from App/:

    .venv/bin/python scripts/go_party_golden.py
    .venv/bin/python scripts/go_party_golden.py --check

Shape matches party_test.go; full FastAPI replay ships with executor step 2
when App/.venv is available in CI for this brief.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "party_golden.json"

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
                "name": "party_bad_size",
                "method": "POST",
                "path": "/l/tok1722/1722/party",
                "body": "party_size=0&_csrf=golden",
                "user": 0,
                "status": 303,
                "location": "/l/tok1722/1722?party_error=1",
                "flash_key": "",
            },
            {
                "name": "party_saved",
                "method": "POST",
                "path": "/l/tok1722/1722/party",
                "body": "party_size=2&_csrf=golden",
                "user": 0,
                "status": 303,
                "location": "/l/tok1722/1722",
                "flash_key": "",
            },
            {
                "name": "count_feature_off",
                "method": "POST",
                "path": "/l/tok1722/1722/count",
                "body": "count=2&shown=2&_csrf=golden",
                "user": 0,
                "status": 404,
                "location": "",
                "flash_key": "",
            },
            {
                "name": "another_ok",
                "method": "POST",
                "path": "/l/tok1722/1722/another",
                "body": "_csrf=golden",
                "user": 0,
                "status": 303,
                "location": "/l/tok1722/1722/new",
                "flash_key": "",
            },
            {
                "name": "another_unknown_stay",
                "method": "POST",
                "path": "/l/tok1722/99999/another",
                "body": "_csrf=golden",
                "user": 0,
                "status": 404,
                "location": "",
                "flash_key": "",
            },
        ],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())