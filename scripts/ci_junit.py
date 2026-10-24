#!/usr/bin/env python3
"""Turn a pytest JUnit report into GitHub annotations and step outputs.

Usage: ci_junit.py REPORT LABEL [--no-skips]
Prints "LABEL: N passed, N failed, N skipped", one ::error annotation per
failure, writes summary= and failure_1..3= to $GITHUB_OUTPUT, and exits 1
when the report is missing or empty, a test failed, or (--no-skips) any
test was skipped. Skipped browser tests mean a broken browser, not a pass.
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    report, label = Path(sys.argv[1]), sys.argv[2]
    no_skips = "--no-skips" in sys.argv[3:]
    if not report.exists():
        print(f"::error title={label}::test report {report} is missing")
        return 1
    cases = list(ET.parse(report).iter("testcase"))
    failures = []
    skipped = 0
    for case in cases:
        if case.find("skipped") is not None:
            skipped += 1
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is None:
            continue
        title = (case.get("classname", "") + "." + case.get("name", ""))[:200]
        text = problem.text or problem.get("message", "")
        detail = text[-6000:].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title={title}::{detail}")
        failures.append(title + ": " + " ".join(text.split())[-3500:])
    passed = len(cases) - len(failures) - skipped
    summary = f"{label}: {passed} passed, {len(failures)} failed, {skipped} skipped"
    print(summary)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"summary={summary}\n")
            for index, detail in enumerate(failures[:3], 1):
                fh.write(f"failure_{index}={detail}\n")
    if not cases or failures or (no_skips and skipped):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
