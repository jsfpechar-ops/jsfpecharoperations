#!/usr/bin/env python3
"""Stream only app-side signing/bootstrap key files as a tar archive."""
from __future__ import annotations

import io
import os
import sys
import tarfile
from pathlib import Path

DATA_DIR = Path(os.environ.get("UBYHOST_DATA_DIR", "/data"))
KEY_FILES = ("secret_key", "initial_admin_credentials")


def main() -> int:
    # Streaming mode avoids creating a plaintext archive on the shared volume.
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
        marker = tarfile.TarInfo("keys-bundle-version.txt")
        marker_data = b"version=1\n"
        marker.size = len(marker_data)
        marker.mode = 0o600
        archive.addfile(marker, io.BytesIO(marker_data))
        for name in KEY_FILES:
            path = DATA_DIR / name
            if path.is_symlink():
                print(f"Refusing symlink key file: {name}", file=sys.stderr)
                return 1
            if path.is_file():
                archive.add(path, arcname=name, recursive=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
