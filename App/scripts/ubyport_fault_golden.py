"""Write the fault table as JSON for the Go twin test (brief A1b P2).

Run from App/: python3 scripts/ubyport_fault_golden.py
The Python test and go/internal/ubyport TestFaultTableSameAsPython read the same file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ubyport import faults  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "go" / "internal" / "ubyport" / "testdata" / "fault_table.json"


def table() -> list[dict[str, str]]:
    return [{"key": k, "match": m, "text_key": t} for k, m, t in faults.FAULT_ROWS]


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(table(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
