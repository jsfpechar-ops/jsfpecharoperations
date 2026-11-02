#!/usr/bin/env python3
"""Write the Python oracle for the Go UbyPort request port (ZapisUbytovane XML).

Dev tool, never run in production. Invented test data only: it reads
tests/golden/ubyport/cases.json, never reads .env, config files or the
database, and makes no network calls. Usage: ubyport_golden.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from app import reporting  # noqa: E402
from app.ubyport import soap  # noqa: E402

DEFAULT_OUT = APP_DIR / "tests" / "golden" / "ubyport"
CASES = DEFAULT_OUT / "cases.json"
AUTH_CODE = "GOLDEN-AUTH"


def render(case: dict) -> str:
    header = reporting.header_from_apartment(case["apartment"])
    guests = [reporting.guest_payload(g, case["reservation"]) for g in case["guests"]]
    return soap.build_zapis_ubytovane(
        header, guests, auth_code=AUTH_CODE, include_wsa_header=case["wsa"]
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for case in cases:
        xml = render(case)
        (args.out / f"{case['name']}.xml").write_bytes(xml.encode("utf-8"))
    print(f"golden files written: {len(cases)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
