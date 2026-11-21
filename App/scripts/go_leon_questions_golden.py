"""Golden HTTP answers for brief 1726 (guest_leon + guest_questions).

Run from App/:

    .venv/bin/python scripts/go_leon_questions_golden.py
    .venv/bin/python scripts/go_leon_questions_golden.py --check
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "leon_questions_golden.json"

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
                "name": "signed_out_questions",
                "method": "GET",
                "path": "/apartments/901/guide/questions",
                "body": "",
                "user": 0,
                "status": 303,
                "location": "/login",
                "flash_key": "",
            },
            {
                "name": "questions_index_ok",
                "method": "GET",
                "path": "/apartments/901/guide/questions",
                "body": "",
                "user": 1,
                "status": 200,
                "location": "",
                "flash_key": "",
            },
            {
                "name": "question_answer_ok",
                "method": "POST",
                "path": "/apartments/901/guide/questions/11",
                "body": "_csrf=golden",
                "user": 1,
                "status": 303,
                "location": "/apartments/901/guide/questions/11",
                "flash_key": "flash.guest_question.sent",
            },
            {
                "name": "leon_stay_not_live",
                "method": "GET",
                "path": "/l/stay-example/501/guide/leon",
                "body": "",
                "user": 0,
                "status": 404,
                "location": "",
                "flash_key": "",
            },
            {
                "name": "leon_qr_not_live",
                "method": "GET",
                "path": "/g/qr-example/leon",
                "body": "",
                "user": 0,
                "status": 404,
                "location": "",
                "flash_key": "",
            },
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.exit(main())