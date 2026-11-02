#!/usr/bin/env python3
"""Write the Python oracle for the Go UbyPort response port (parse and classify).

Dev tool, never run in production. Invented test data only: it reads the
responses in tests/golden/ubyport/responses/, never reads .env, config files or
the database, and makes no network calls. Usage: ubyport_golden_responses.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from app.ubyport import errors, soap  # noqa: E402

DEFAULT_OUT = APP_DIR / "tests" / "golden" / "ubyport" / "responses"
INPUTS = DEFAULT_OUT
SCALAR_METHODS = ("TestDostupnosti", "MaximalniDelkaSeznamu")
PARSE_ERROR = "parse_error"


def _call(fn, *args: Any) -> Any:
    try:
        return fn(*args)
    except ET.ParseError:
        return PARSE_ERROR


def responses() -> dict:
    out = {}
    for path in sorted(INPUTS.glob("*.xml")):
        text = path.read_bytes().decode("utf-8")
        out[path.name] = {
            "fault": soap.parse_fault(text),
            "element_names": soap.response_element_names(text),
            "zapis": _call(soap.parse_zapis_response, text),
            "scalar": {m: _call(soap.parse_scalar_response, text, m) for m in SCALAR_METHODS},
            "ciselnik": _call(soap.parse_ciselnik_response, text),
        }
    return out


def classify_cases() -> dict:
    cases = json.loads((INPUTS / "classify_cases.json").read_text(encoding="utf-8"))
    out = {}
    for case in cases:
        codebook = case.get("codebook")
        state, messages = errors.classify(
            case.get("header"),
            case.get("record"),
            codebook=codebook,
            lang=case.get("lang") or "en",
            severities=case.get("severities"),
        )
        out[case["name"]] = {
            "state": state,
            "messages": messages,
            "record_is_duplicate": errors.record_is_duplicate(case.get("record"), codebook),
        }
    if len(out) != len(cases):
        raise SystemExit("classify case names must be unique")
    return out


def tables() -> dict:
    return {
        "known_codes": errors.KNOWN_CODES,
        "known_severity": errors.KNOWN_SEVERITY,
        "fallback_text": errors.FALLBACK_TEXT,
        "accepted_max_severity": errors.ACCEPTED_MAX_SEVERITY,
        "max_pdf_bytes": soap.MAX_PDF_BYTES,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    doc = {"tables": tables(), "responses": responses(), "classify": classify_cases()}
    args.out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    (args.out / "expected.json").write_text(text, encoding="utf-8")
    print(f"golden response expectations written: {len(doc['responses'])} responses, {len(doc['classify'])} classify cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
