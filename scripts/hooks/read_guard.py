#!/usr/bin/env python3
"""PreToolUse hook: block Read calls that would load more than MAX_LINES lines."""
import json
import os
import sys

MAX_LINES = 350


def main() -> int:
    if os.environ.get("ALLOW_FULL_READ") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Read":
        return 0
    args = data.get("tool_input") or {}
    path = args.get("file_path") or ""
    limit = args.get("limit")
    if isinstance(limit, int) and 0 < limit <= MAX_LINES:
        return 0
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
            if b"\0" in head:
                return 0
            lines = head.count(b"\n") + sum(chunk.count(b"\n") for chunk in iter(lambda: fh.read(65536), b""))
    except OSError:
        return 0
    if lines <= MAX_LINES:
        return 0
    sys.stderr.write(
        f"Blocked: {path} has {lines} lines. Grep for the symbol, then Read with "
        f"offset and limit (150 lines or fewer), or ask a Haiku subagent to answer from it.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
