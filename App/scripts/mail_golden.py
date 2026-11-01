#!/usr/bin/env python3
"""Write the Python oracle for the Go submission_problem mail renderer (0552).

Dev tool, never run in production. Invented test data only: it reads
tests/golden/mail/cases.json, never reads .env, config files or the database,
and makes no network calls. Usage: mail_golden.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR / "tests" / "golden" / "mail"
CASES = DEFAULT_OUT / "cases.json"

# config reads these once, at import time, so they are set before ``app``.
# The two origins differ on purpose: the logo uses the public one and the
# links use the app one, so a swapped pair shows up in the bytes.
os.environ["UBYHOST_APP_BASE_URL"] = "https://app.example.test"
os.environ["UBYHOST_PUBLIC_BASE_URL"] = "https://www.example.test"
sys.path.insert(0, str(APP_DIR))

from app import mail_notify  # noqa: E402


def render(case: dict) -> dict:
    return mail_notify.build_submission_problem(
        property_name=case["property_name"],
        state=case["state"],
        reason=case["reason"],
        transport=case["transport"],
        stays=case["stays"],
        submission_id=case["submission_id"],
        lang="en",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for case in cases:
        parts = render(case)
        name = case["name"]
        (args.out / f"{name}.subject.txt").write_bytes(parts["subject"].encode("utf-8"))
        (args.out / f"{name}.text.txt").write_bytes(parts["text"].encode("utf-8"))
        (args.out / f"{name}.html").write_bytes(parts["html"].encode("utf-8"))
    print(f"golden files written: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
