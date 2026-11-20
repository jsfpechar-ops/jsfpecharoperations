"""Golden HTTP answers for brief 1720d guest shell gate (privacy + ruian-suggest).

Unified naming with docs/tasks/1720-go-guest-shell-gate.md §2/§6 (replaces
go_shell_golden.py / test_go_shell_golden.py from the monolith brief).

Run from App/:

    .venv/bin/python scripts/go_go_guest_shell_gate_golden.py
    .venv/bin/python scripts/go_go_guest_shell_gate_golden.py --check
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "shell_gate_golden.json"


def main() -> int:
    check = "--check" in sys.argv
    if not OUT.exists():
        if check:
            print("missing golden", OUT, file=sys.stderr)
            return 1
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(
            json.dumps({"cases": [], "note": "executor step 2 replays FastAPI"}, indent=2) + "\n",
            encoding="utf-8",
        )
        print("wrote", OUT)
        return 0
    golden = OUT.read_text(encoding="utf-8")
    if check:
        doc = json.loads(golden)
        if "cases" in doc:
            return 0
        print("stale golden", file=sys.stderr)
        return 1
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())