"""Golden HTTP cases for brief 1712 cancel and PDF routes.

Run from App/:

    .venv/bin/python scripts/go_cancel_pdfs_golden.py
    .venv/bin/python scripts/go_cancel_pdfs_golden.py --check
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "booking" / "testdata" / "cancel_pdfs_golden.json"


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
        "now": "2026-11-28T10:00:00+00:00",
        "seed": [],
        "cases": [
            {
                "name": "bad_token_cancel",
                "method": "POST",
                "path": "/p/old-town/b/501/{bad}/cancel",
                "status": 404,
            },
            {
                "name": "bad_token_invoice",
                "method": "GET",
                "path": "/p/old-town/b/501/{bad}/invoice.pdf",
                "status": 404,
            },
            {
                "name": "cancel_not_visible",
                "method": "POST",
                "path": "/p/old-town/b/503/{good}/cancel",
                "status": 404,
            },
            {
                "name": "invoice_no_row",
                "method": "GET",
                "path": "/p/old-town/b/501/{good}/invoice.pdf",
                "status": 404,
            },
            {
                "name": "correction_no_row",
                "method": "GET",
                "path": "/p/old-town/b/501/{good}/correction.pdf",
                "status": 404,
            },
            {
                "name": "calendar_paid",
                "method": "GET",
                "path": "/p/old-town/b/501/{good}/calendar.ics",
                "status": 200,
                "content_type": "text/calendar; charset=utf-8",
            },
        ],
    }
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())