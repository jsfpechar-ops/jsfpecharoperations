#!/usr/bin/env python3
"""Stream only app-side signing/bootstrap key files as a tar archive."""
from __future__ import annotations

import argparse
import io
import os
import sys
import tarfile
from pathlib import Path

DATA_DIR = Path(os.environ.get("UBYHOST_DATA_DIR", "/data"))
KEY_FILES = ("secret_key", "initial_admin_credentials")


def key_names_present() -> list[str]:
    """Names of the key files that exist, refusing symlinks.

    Callers use this to prove the current backup actually carries key material
    before retention is allowed to prune an older bundle.
    """
    present: list[str] = []
    for name in KEY_FILES:
        path = DATA_DIR / name
        if path.is_symlink():
            print(f"Refusing symlink key file: {name}", file=sys.stderr)
            raise SystemExit(1)
        if path.is_file():
            present.append(name)
    return present


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="print keys_found=<n> instead of streaming the archive",
    )
    args = parser.parse_args()

    present = key_names_present()
    if args.check_only:
        # Names only: never print file contents or key material.
        print(f"keys_found={len(present)}")
        return 0

    # Streaming mode avoids creating a plaintext archive on the shared volume.
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
        marker = tarfile.TarInfo("keys-bundle-version.txt")
        marker_data = b"version=1\n"
        marker.size = len(marker_data)
        marker.mode = 0o600
        archive.addfile(marker, io.BytesIO(marker_data))
        for name in present:
            archive.add(DATA_DIR / name, arcname=name, recursive=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
