#!/usr/bin/env python3
"""List active accounts that still have no login e-mail (task 0006).

Migration 0005 removed every password, so an account without a login e-mail
cannot log in after the e-mail login update. Run this on the server before
deploying, then set an address for each id in /admin/users. Read-only; it
prints the account id and role only, never a name or an address:

    .venv/bin/python scripts/list_accounts_without_email.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402


def main() -> int:
    db.init_db()
    rows = db.query(
        "SELECT id, role FROM user_account "
        "WHERE active = 1 AND (email IS NULL OR TRIM(email) = '') ORDER BY id"
    )
    for row in rows:
        print(f"id={row['id']} role={row['role']}")
    print(f"active accounts without a login e-mail: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
