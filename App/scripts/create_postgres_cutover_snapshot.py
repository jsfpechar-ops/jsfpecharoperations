#!/usr/bin/env python3
"""Create a verified SQLite cutover snapshot on tmpfs with no guest output."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/data/ubyhost.db")
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()

    source = Path(args.source)
    destination = Path(args.destination)
    if destination.parent != Path("/dev/shm") or destination.exists() or destination.is_symlink():
        print("Destination must be a new file directly under /dev/shm.", file=sys.stderr)
        return 2
    if not source.is_file() or source.is_symlink():
        print("The source SQLite database is missing or is a symlink.", file=sys.stderr)
        return 2

    os.umask(0o077)
    free_bytes = os.statvfs(destination.parent).f_bavail * os.statvfs(destination.parent).f_frsize
    required_bytes = source.stat().st_size + 64 * 1024 * 1024
    if free_bytes < required_bytes:
        print("tmpfs space is below the measured SQLite size plus 64 MiB safety margin.", file=sys.stderr)
        return 1

    source_uri = f"file:{source}?mode=ro"
    src = sqlite3.connect(source_uri, uri=True)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
        integrity = dst.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            print("SQLite cutover snapshot failed integrity_check.", file=sys.stderr)
            return 1
        foreign_keys = dst.execute("PRAGMA foreign_key_check").fetchone()
        if foreign_keys is not None:
            print("SQLite cutover snapshot failed foreign_key_check.", file=sys.stderr)
            return 1
        dst.commit()
    finally:
        dst.close()
        src.close()
    os.chmod(destination, 0o600)
    print("SQLite snapshot integrity and foreign-key checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
