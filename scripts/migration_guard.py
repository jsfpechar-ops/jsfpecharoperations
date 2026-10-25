#!/usr/bin/env python3
"""Fail when a change edits, renames or deletes a migration that is on the base branch,
or adds migrations that do not continue the numbering without gaps.

Usage: migration_guard.py BASE_REF   (e.g. origin/main)
"""
from __future__ import annotations

import re
import subprocess
import sys

DIR = "App/app/migrations/"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    base = sys.argv[1]
    errors = []
    for line in git("diff", "--name-status", f"{base}...HEAD", "--", DIR).splitlines():
        status, *paths = line.split("\t")
        if status[0] != "A":
            errors.append(f"{status} {' '.join(paths)}: a migration on {base} must never change; add a new file")
    numbers = lambda text: sorted(int(m) for m in re.findall(r"(\d{4})_[^/\s]*\.sql", text))
    before = numbers(git("ls-tree", "--name-only", base, DIR))
    after = numbers(git("ls-tree", "--name-only", "HEAD", DIR))
    added = [n for n in after if n not in before]
    expected = list(range((before[-1] if before else 0) + 1, (before[-1] if before else 0) + 1 + len(added)))
    if added != expected:
        errors.append(f"new migrations {added} must be numbered {expected} (no gaps, no reuse)")
    for error in errors:
        print(f"::error title=Migration guard::{error}")
    print("migration guard: OK" if not errors else f"migration guard: {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
