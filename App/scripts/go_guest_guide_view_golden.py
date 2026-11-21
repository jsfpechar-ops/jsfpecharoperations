"""Golden parity for brief 1629 (guest_guide_view). Run from App/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "guest_guide_view_golden.json"


def main() -> int:
    check = "--check" in sys.argv
    doc = {"booked_level": [
        {"from": "2026-06-17", "to": "2026-06-19", "today": "2026-06-15", "level": "everyone"},
        {"from": "2026-06-16", "to": "2026-06-18", "today": "2026-06-15", "level": "booked"},
    ], "routes": [
        "GET /g/{token}",
        "GET /g/{token}/photos/{item_id}/{photo_id}",
        "GET /l/{token}/{reservation_id}/guide",
        "GET /l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}",
    ]}
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if check:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == payload:
            return 0
        print("stale golden", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(payload, encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
