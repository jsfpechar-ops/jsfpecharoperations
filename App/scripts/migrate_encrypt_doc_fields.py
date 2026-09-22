#!/usr/bin/env python3
"""Move guest travel-document numbers into their encrypted columns.

Run once per deployment, after the release that adds ``doc_number_enc`` and
``visa_number_enc`` and before the release that stops reading the plaintext
columns:

    .venv/bin/python scripts/migrate_encrypt_doc_fields.py --dry-run
    .venv/bin/python scripts/migrate_encrypt_doc_fields.py

Idempotent and re-runnable. A row whose encrypted column is already populated
only has its stale plaintext blanked; a second run finds nothing left to do.

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

from app import db  # noqa: E402

# Read and write the raw columns. The app's own query helpers decrypt on the
# way out, which is exactly what this script must not do: it needs to see
# whether the ciphertext is already there.
SELECT_SQL = (
    "SELECT id, doc_number, visa_number, doc_number_enc, visa_number_enc FROM guest"
)


def migrate(dry_run: bool = False) -> Dict[str, int]:
    """Encrypt what is still in the clear and blank the plaintext columns."""
    counts = {"scanned": 0, "encrypted": 0, "blanked": 0}
    conn = db.connect()
    try:
        try:
            rows = conn.execute(SELECT_SQL).fetchall()
        except sqlite3.OperationalError as exc:
            raise SystemExit(
                f"{exc}: {db.config.DB_PATH} does not look like a UbyHost "
                "database. Point UBYHOST_DB at the right file."
            ) from exc
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
    args = parser.parse_args()

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
