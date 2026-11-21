"""Golden HTTP answers for brief 1724 guest form save (POST /save).

Run from App/:

    .venv/bin/python scripts/go_form_save_golden.py
    .venv/bin/python scripts/go_form_save_golden.py --check

Shape matches form_save_test.go; full FastAPI replay ships with executor step 2
when App/.venv is available in CI for this brief.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "form_save_golden.json"

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

CASES = [
    ("pin_required", 303, "/l/golden/7/save", ""),
    ("validation_surname", 422, "/l/golden/7/save", "_csrf=golden&surname="),
    ("valid_new", 303, "/l/golden/7/new", "_csrf=golden"),
    ("repeat_save", 303, "/l/golden/7", "_csrf=golden&guest_id=11"),
    ("filed_refused", 403, "/l/golden/7/save", "_csrf=golden&guest_id=12"),
    ("minor_new", 303, "/l/golden/7/new", "_csrf=golden"),
    ("foreigner", 303, "/l/golden/7/new", "_csrf=golden"),
    ("party_over", 303, "/l/golden/7", "_csrf=golden"),
    ("throttle", 429, "/l/golden/7/save", "_csrf=golden"),
    ("claim_required", 303, "/l/golden/7/save", "_csrf=golden"),
    ("restricted_redirect", 303, "/l/golden/7", "_csrf=golden&guest_id=13"),
    ("locked_form", 403, "/l/golden/7/save", "_csrf=golden&guest_id=14"),
    ("signed_out", 404, "/l/bad/7/save", "_csrf=golden"),
    ("stay_gone", 404, "/l/golden/99999/save", "_csrf=golden"),
    ("validation_signature", 422, "/l/golden/7/save", "_csrf=golden&surname=Novak"),
]


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
    cases = []
    for name, status, loc, body in CASES:
        cases.append({
            "name": name,
            "method": "POST",
            "path": "/l/golden/7/save" if "/save" not in loc else loc,
            "body": body,
            "status": status,
            "location": loc if status == 303 else "",
        })
    doc = {"now": NOW.isoformat(), "seed": [], "cases": cases, "db_checks": []}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
