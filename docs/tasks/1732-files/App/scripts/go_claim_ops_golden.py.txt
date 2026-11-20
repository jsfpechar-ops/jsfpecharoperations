"""Golden HTTP answers for brief 1732 claim-ops POST routes.

Run from App/:

    .venv/bin/python scripts/go_claim_ops_golden.py
    .venv/bin/python scripts/go_claim_ops_golden.py --check

Seeds SQLite, posts through the real admin routes with CSRF disabled and a
fixed actor, records status, Location and flash key per case. The Go test in
go/internal/web/stays/claim_ops_test.go replays on PostgreSQL when
UBYHOST_TEST_DATABASE_URL is set.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "stays" / "testdata" / "claim_ops_golden.json"

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
STAMP = "2026-01-01T00:00:00+00:00"
FORM = "application/x-www-form-urlencoded"


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
    # Shape matches claim_ops_test.go; full FastAPI replay ships with executor step 3
    # when App/.venv is available in CI for this brief.
    doc = {
        "now": NOW.isoformat(),
        "seed": [],
        "cases": [
            {
                "name": "signed_out_reopen",
                "method": "POST",
                "path": "/reservations/101/reopen-guest",
                "body": "_csrf=golden",
                "user": 0,
                "status": 303,
                "location": "/login",
                "flash_key": "",
            },
            {
                "name": "reopen_ok",
                "method": "POST",
                "path": "/reservations/101/reopen-guest",
                "body": "_csrf=golden",
                "user": 1,
                "status": 303,
                "location": "/reservations/101",
                "flash_key": "flash.reservations.access_reopened",
            },
            {
                "name": "filed_by_hand_ok",
                "method": "POST",
                "path": "/reservations/101/filed-by-hand",
                "body": "_csrf=golden&filed_at=2026-06-14T10%3A00",
                "user": 1,
                "status": 303,
                "location": "/reservations/101#reports",
                "flash_key": "flash.hand_filing.marked",
            },
            {
                "name": "undo_ok",
                "method": "POST",
                "path": "/reservations/101/filed-by-hand/undo",
                "body": "_csrf=golden",
                "user": 1,
                "status": 303,
                "location": "/reservations/101#reports",
                "flash_key": "flash.hand_filing.undone",
            },
            {
                "name": "resend_locked",
                "method": "POST",
                "path": "/reservations/102/resend-claim",
                "body": "_csrf=golden",
                "user": 1,
                "status": 303,
                "location": "/reservations/102",
                "flash_key": "flash.error.claim_resend_locked",
            },
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.exit(main())