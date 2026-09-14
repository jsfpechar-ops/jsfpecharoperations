#!/usr/bin/env python3
"""Regenerate the static annotated UbyPort WS credential sample PDF."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ubyport_sample_pdf import default_static_path, write_sample_pdf  # noqa: E402


def main() -> int:
    path = write_sample_pdf(default_static_path())
    print(f"Wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
