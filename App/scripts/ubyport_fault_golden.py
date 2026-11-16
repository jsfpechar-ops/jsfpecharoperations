"""Write the fault table and the English fault copy as JSON for the Go twin tests (A1b P2).

Run from App/: python3 scripts/ubyport_fault_golden.py
The Python tests and go/internal/ubyport TestFaultTableSameAsPython /
TestFaultMailCopySameAsPython read the same files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import host_i18n  # noqa: E402
from app.ubyport import faults  # noqa: E402

GO_DIR = Path(__file__).resolve().parents[2] / "go" / "internal" / "ubyport" / "testdata"
OUT = GO_DIR / "fault_table.json"
COPY_OUT = GO_DIR / "fault_copy_en.json"
COPY_KEYS = ("ubyport.fault.uby_runtime_no_errors", "ubyport.fault.uby_runtime", "ubyport.fault.unknown")


def table() -> list[dict[str, str]]:
    return [{"key": k, "match": m, "text_key": t} for k, m, t in faults.FAULT_ROWS]


def copy_en() -> dict[str, str]:
    return {key: host_i18n.STRINGS["en"][key] for key in COPY_KEYS}


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(table(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    COPY_OUT.write_text(json.dumps(copy_en(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} and {COPY_OUT}")
