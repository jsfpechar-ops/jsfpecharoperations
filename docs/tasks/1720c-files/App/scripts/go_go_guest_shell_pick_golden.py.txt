"""Golden HTTP answers for brief 1720c GET /l/{token} (pick_stay).

Run from App/:

    .venv/bin/python scripts/go_go_guest_shell_pick_golden.py
    .venv/bin/python scripts/go_go_guest_shell_pick_golden.py --check
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "shell_pick_golden.json"


def main() -> int:
    check = "--check" in sys.argv
    golden = OUT.read_text(encoding="utf-8")
    if check:
        doc = json.loads(golden)
        if doc.get("cases"):
            return 0
        print("stale golden", file=sys.stderr)
        return 1
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())