#!/usr/bin/env python3
"""Backfill legal_acceptance from legacy login audit rows (BE-1).

Before BE-1, the only acceptance evidence was a free-text ``audit`` detail on
the non-2FA login path: ``terms_vX privacy_vY dpa_vZ accepted``. This script
turns each such row into ``legal_acceptance`` rows with ``method='backfill'``.

Idempotent through the UNIQUE (user_account_id, document, version) constraint:
a second run inserts nothing. Run it from ``App/`` as a deploy step:

    .venv/bin/python scripts/backfill_legal_acceptance.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import acceptance, db  # noqa: E402


def main() -> int:
    db.init_db()
    inserted = acceptance.backfill_from_audit()
    # Counts only, never personal data (Rule 8).
    print(f"legal_acceptance rows inserted: {inserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
