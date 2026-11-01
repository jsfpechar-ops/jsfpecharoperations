"""One-time host consent to the UbyHost payment terms before Stripe (0624).

A host sees the plain-language summary once, before the first trip to
Stripe. Bumping VERSION shows it again to every host. The evidence is an
audit row (action payments_terms_accepted, detail version=...), the same
pattern as the door-code and Leon terms; retention never expires it. Only the
account id, the version and the time are stored: no IP, no user agent.
"""
from __future__ import annotations

from . import db

VERSION = "2026-11-01"
ACTION = "payments_terms_accepted"


def accepted(owner_user_id: int) -> bool:
    """True when this host accepted the current version."""
    return db.query_one(
        "SELECT id FROM audit WHERE owner_user_id = ? AND action = ? AND detail = ?",
        (owner_user_id, ACTION, f"version={VERSION}"),
    ) is not None


def record(owner_user_id: int) -> None:
    """Store the acceptance once (a second call changes nothing)."""
    if accepted(owner_user_id):
        return
    db.audit(ACTION, f"version={VERSION}", owner_user_id=owner_user_id)
