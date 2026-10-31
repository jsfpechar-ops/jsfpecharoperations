#!/usr/bin/env python3
"""Create a verified SQLite cutover snapshot on tmpfs with no guest output."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def _copy_snapshot(source: Path, destination: Path, *, read_only: bool) -> None:
    """Copy the source into a new snapshot file.

    A read-only connection is tried first so the source really is untouched.
    After an unclean stop SQLite may need to recover a hot -wal before it will
    read consistently in read-only mode; the caller then falls back to a
    write-capable connection for the recovery only (the backup API itself never
    writes application data). A failed attempt never leaves a partial snapshot.
    """
    mode = "ro" if read_only else "rw"
    source_uri = f"{source.as_uri()}?mode={mode}"
    src = sqlite3.connect(source_uri, uri=True)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
        integrity = dst.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise RuntimeError("snapshot failed integrity_check")
        foreign_keys = dst.execute("PRAGMA foreign_key_check").fetchone()
        if foreign_keys is not None:
            raise RuntimeError("snapshot failed foreign_key_check")
        dst.commit()
    finally:
        dst.close()
        src.close()


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

    try:
        _copy_snapshot(source, destination, read_only=True)
    except sqlite3.Error as exc:
        destination.unlink(missing_ok=True)
        print(
            "Read-only snapshot failed ("
            f"{type(exc).__name__}: {exc}); retrying with a write-capable connection so "
            "SQLite can recover a hot WAL. No application writes are issued.",
            file=sys.stderr,
        )
        try:
            _copy_snapshot(source, destination, read_only=False)
        except (sqlite3.Error, RuntimeError) as retry_exc:
            destination.unlink(missing_ok=True)
            print(f"SQLite cutover snapshot failed: {retry_exc}", file=sys.stderr)
            return 1
    except RuntimeError as exc:
        destination.unlink(missing_ok=True)
        print(f"SQLite cutover snapshot failed: {exc}", file=sys.stderr)
        return 1

    os.chmod(destination, 0o600)
    print("SQLite snapshot integrity and foreign-key checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
