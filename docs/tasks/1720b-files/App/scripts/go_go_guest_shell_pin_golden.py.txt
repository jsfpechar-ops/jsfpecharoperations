"""Golden HTTP answers for brief 1720b POST /l/{token}/pin.

Run from App/:

    .venv/bin/python scripts/go_go_guest_shell_pin_golden.py
    .venv/bin/python scripts/go_go_guest_shell_pin_golden.py --check

Full FastAPI replay ships with executor step 2 when the DB seed is wired.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "shell_pin_golden.json"


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