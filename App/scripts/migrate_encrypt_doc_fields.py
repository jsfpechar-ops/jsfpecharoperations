#!/usr/bin/env python3
"""Move guest travel-document numbers into their encrypted columns.

Run once per deployment, after the release that adds ``doc_number_enc`` and
``visa_number_enc`` and before the release that stops reading the plaintext
columns:

    .venv/bin/python scripts/migrate_encrypt_doc_fields.py --dry-run
    .venv/bin/python scripts/migrate_encrypt_doc_fields.py

Idempotent and re-runnable. A row whose encrypted column is already populated
only has its stale plaintext blanked; a second run finds nothing left to do.

The plaintext is not merely overwritten: the app connects with
``PRAGMA secure_delete = ON`` and this script vacuums the file afterwards, so
the numbers are not left readable in the freed pages. To go back to a release
that reads only the plaintext column, run it with ``--rollback`` first —
otherwise the old code files an empty ``cDocN``.

Refuses to run when no key is established: without ``UBYHOST_SECRET_KEY`` and
without the key file in the data directory, this process would mint a key of its
own, encrypt the numbers with it, blank the plaintext and report success, and
the app would then be unable to read a single guest.

Never run this at import time -- it writes to the database, so it belongs to the
deploy, where a failure is visible and can be retried.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402

# Read and write the raw columns. The app's own query helpers decrypt on the
# way out, which is exactly what this script must not do: it needs to see
# whether the ciphertext is already there.
SELECT_SQL = (
    "SELECT id, doc_number, visa_number, doc_number_enc, visa_number_enc FROM guest"
)


def require_the_app_key() -> None:
    """Stop before encrypting anything under a key the running app does not have.

    ``db.encrypt_field`` derives its key from ``UBYHOST_SECRET_KEY`` or from the
    key file in the data directory, and creates one when neither is there. A
    backfill that ran that way would encrypt every document number under a key
    nobody else has, blank the plaintext and report success — and the app would
    then be unable to read a single guest.
    """
    try:
        config.require_secret_key()
    except RuntimeError as exc:
        raise SystemExit(
            f"Refusing to run: {exc}. This run would create a new key and encrypt"
            " the document numbers with it, and the app could not read them back."
            " Point UBYHOST_SECRET_KEY or UBYHOST_DATA_DIR at the key the app uses"
            " and run again."
        ) from exc


def open_database() -> sqlite3.Connection:
    """Open the app's database, adding the columns this release needs.

    A database the app has not opened since the upgrade is missing the ``*_enc``
    columns, and the SELECT below would fail with "no such column". ``init_db()``
    adds them — but it also creates the schema, so the file is checked first: run
    against the wrong path it would otherwise create an empty database there and
    report a successful migration.
    """
    path = Path(db.config.DB_PATH)
    if not path.exists():
        raise SystemExit(
            f"No database at {path}. Point UBYHOST_DB at the file the app uses."
        )
    conn = db.connect()
    try:
        found = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'guest'"
        ).fetchone()
    finally:
        conn.close()
    if not found:
        raise SystemExit(
            f"{path} does not look like a UbyHost database. Point UBYHOST_DB at "
            "the right file."
        )
    db.init_db()
    return db.connect()


def migrate(dry_run: bool = False) -> Dict[str, int]:
    """Encrypt what is still in the clear and blank the plaintext columns."""
    require_the_app_key()
    counts = {"scanned": 0, "encrypted": 0, "blanked": 0, "vacuumed": 0}
    conn = open_database()
    try:
        rows = conn.execute(SELECT_SQL).fetchall()
        counts["scanned"] = len(rows)
        for row in rows:
            updates: Dict[str, Any] = {}
            for name, enc in db.ENCRYPTED_GUEST_COLUMNS.items():
                plain = row[name]
                if not plain:
                    continue
                if not row[enc]:
                    updates[enc] = db.encrypt_field(plain)
                    counts["encrypted"] += 1
                updates[name] = None
                counts["blanked"] += 1
            if not updates or dry_run:
                continue
            sets = ", ".join(f"{column} = ?" for column in updates)
            conn.execute(
                f"UPDATE guest SET {sets} WHERE id = ?",
                [*updates.values(), row["id"]],
            )
        if counts["blanked"] and not dry_run:
            # secure_delete overwrites the freed pages, but the file itself is
            # still as long as it ever was and the pages may sit in the WAL.
            # VACUUM rewrites it so the plaintext is not recoverable by reading
            # the raw file.
            conn.execute("VACUUM")
            counts["vacuumed"] = 1
    finally:
        conn.close()
    return counts


def rollback(dry_run: bool = False) -> Dict[str, int]:
    """Put the document numbers back in the plaintext columns.

    The release that reads only the encrypted columns is the one to run this
    against before rolling back to an older release, which reads only the
    plaintext column. Without it the old code files an empty ``cDocN``.
    """
    require_the_app_key()
    counts = {"scanned": 0, "restored": 0, "cleared": 0}
    conn = open_database()
    try:
        rows = conn.execute(SELECT_SQL).fetchall()
        counts["scanned"] = len(rows)
        for row in rows:
            updates: Dict[str, Any] = {}
            for name, enc in db.ENCRYPTED_GUEST_COLUMNS.items():
                token = row[enc]
                if not token:
                    continue
                updates[name] = db.decrypt_field(token)
                updates[enc] = None
                counts["restored"] += 1
                counts["cleared"] += 1
            if not updates or dry_run:
                continue
            sets = ", ".join(f"{column} = ?" for column in updates)
            conn.execute(
                f"UPDATE guest SET {sets} WHERE id = ?",
                [*updates.values(), row["id"]],
            )
        if counts["cleared"] and not dry_run:
            conn.execute("VACUUM")
    finally:
        conn.close()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change without writing anything",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help=(
            "decrypt the numbers back into the plaintext columns, for rolling "
            "back to a release that reads only those"
        ),
    )
    args = parser.parse_args()

    if args.rollback:
        counts = rollback(dry_run=args.dry_run)
        verb = "would be" if args.dry_run else "were"
        print(
            f"{counts['scanned']} guest row(s) scanned; "
            f"{counts['restored']} document field(s) {verb} decrypted back into "
            f"the plaintext column and {counts['cleared']} ciphertext value(s) "
            f"{verb} cleared."
        )
    else:
        counts = migrate(dry_run=args.dry_run)
        verb = "would be" if args.dry_run else "were"
        print(
            f"{counts['scanned']} guest row(s) scanned; "
            f"{counts['encrypted']} document field(s) {verb} encrypted and "
            f"{counts['blanked']} plaintext value(s) {verb} blanked."
        )
    if args.dry_run:
        print("Dry run: nothing was written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
