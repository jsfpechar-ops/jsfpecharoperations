#!/usr/bin/env python3
"""Encrypt guest signatures and passport attachments at rest (BE-12).

Signatures move from ``guest.signature_png`` (plaintext) to
``signature_png_enc``; passport image/PDF files on disk are replaced by a
Fernet-encrypted ``<guest_id>.<ext>.enc`` and the plaintext file is deleted.

Run once per deployment after the release that adds the column and switches the
store:

    .venv/bin/python scripts/migrate_encrypt_signatures.py --dry-run
    .venv/bin/python scripts/migrate_encrypt_signatures.py

Idempotent: a row whose encrypted column is already populated, or a file that
already has an ``.enc`` sibling, is skipped. ``--check`` prints how many
plaintext values remain and exits non-zero when any do.

Refuses to run without the app key, for the same reason as the document-number
migration: encrypting under a key this process invented would make the values
unreadable to the app.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db, passport_photos  # noqa: E402

SIGNATURE_SQL = "SELECT id, signature_png, signature_png_enc FROM guest"


def require_the_app_key() -> None:
    try:
        config.secret_key()
    except Exception as exc:  # noqa: BLE001 - surfaced as a refusal
        raise SystemExit(
            f"Refusing to run: {exc}. Point UBYHOST_SECRET_KEY or UBYHOST_DATA_DIR "
            "at the key the app uses and run again."
        ) from exc


def open_database() -> sqlite3.Connection:
    path = Path(config.DB_PATH)
    if not path.exists():
        raise SystemExit(f"No database at {path}. Point UBYHOST_DB at the file the app uses.")
    db.init_db()
    return db.connect()


def migrate_signatures(dry_run: bool = False) -> Dict[str, int]:
    counts = {"scanned": 0, "encrypted": 0, "blanked": 0}
    conn = open_database()
    try:
        rows = conn.execute(SIGNATURE_SQL).fetchall()
        counts["scanned"] = len(rows)
        for row in rows:
            plain = row["signature_png"]
            if not plain:
                continue
            if not row["signature_png_enc"]:
                counts["encrypted"] += 1
                if not dry_run:
                    conn.execute(
                        "UPDATE guest SET signature_png_enc = ? WHERE id = ?",
                        (db.encrypt_field(plain), row["id"]),
                    )
            counts["blanked"] += 1
            if not dry_run:
                conn.execute(
                    "UPDATE guest SET signature_png = NULL WHERE id = ?", (row["id"],)
                )
        if counts["blanked"] and not dry_run:
            conn.execute("VACUUM")
    finally:
        conn.close()
    return counts


def migrate_passport_files(dry_run: bool = False) -> Dict[str, int]:
    counts = {"found": 0, "encrypted": 0}
    directory = passport_photos.PHOTOS_DIR
    if not directory.is_dir():
        return counts
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name.endswith(passport_photos.ENC_SUFFIX):
            continue
        if path.suffix.lower() not in passport_photos.ALL_EXTENSIONS:
            continue
        counts["found"] += 1
        target = path.with_name(path.name + passport_photos.ENC_SUFFIX)
        if target.exists():
            continue
        counts["encrypted"] += 1
        if not dry_run:
            target.write_bytes(db.encrypt_blob(path.read_bytes()))
            try:
                target.chmod(0o600)
            except OSError:
                pass
            path.unlink()
    return counts


def remaining() -> Dict[str, int]:
    conn = open_database()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM guest "
            "WHERE signature_png IS NOT NULL AND signature_png_enc IS NULL"
        ).fetchone()
    finally:
        conn.close()
    files = 0
    directory = passport_photos.PHOTOS_DIR
    if directory.is_dir():
        for path in directory.iterdir():
            if (
                path.is_file()
                and not path.name.endswith(passport_photos.ENC_SUFFIX)
                and path.suffix.lower() in passport_photos.ALL_EXTENSIONS
            ):
                files += 1
    return {"plaintext_signatures": row["n"], "plaintext_files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument(
        "--check",
        action="store_true",
        help="print the remaining plaintext counts; exit non-zero when any remain",
    )
    args = parser.parse_args()

    if args.check:
        counts = remaining()
        print(
            "plaintext signatures remaining: {plaintext_signatures}; "
            "plaintext passport files remaining: {plaintext_files}".format(**counts)
        )
        return 1 if any(counts.values()) else 0

    require_the_app_key()
    signatures = migrate_signatures(dry_run=args.dry_run)
    files = migrate_passport_files(dry_run=args.dry_run)
    verb = "would be" if args.dry_run else "were"
    print(
        f"{signatures['scanned']} guest row(s) scanned; "
        f"{signatures['encrypted']} signature(s) {verb} encrypted and "
        f"{signatures['blanked']} plaintext value(s) {verb} blanked; "
        f"{files['encrypted']} passport file(s) {verb} encrypted."
    )
    if args.dry_run:
        print("Dry run: nothing was written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
