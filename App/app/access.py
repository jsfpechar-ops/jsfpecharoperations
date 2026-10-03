"""Ownership-aware database lookups for host routes.

Every host object is reached through its apartment owner. Keeping these joins
in one module makes an omitted ownership check conspicuous in code review and
prevents numeric IDs from becoming cross-account access.
"""
from __future__ import annotations

from fastapi import Request

from . import auth, db


# What a masked document or visa number keeps visible while an admin supports
# a host: enough to match a guest's word on the phone, not enough to copy.
MASK_KEEP = 3
MASK_CHAR = "\u2022"


def identity_visible(request: Request, guest_id: int | None = None) -> bool:
    """Whether this request may see a guest's identity data in full.

    Identity data means document and visa numbers, signatures, passport
    photos, and every export that carries them. The host always sees it. An
    admin inside the host's workspace sees it only for a guest revealed (with
    a logged reason) in this impersonation; with no ``guest_id`` (bulk
    exports, the workspace ZIP) the answer while impersonating is always no.
    """
    if not auth.impersonating(request):
        return True
    if guest_id is None:
        return False
    return int(guest_id) in auth.revealed_guest_ids(request)


def mask_identifier(value) -> str:
    """A document or visa number with all but its last characters hidden."""
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= MASK_KEEP:
        return MASK_CHAR * 3
    return MASK_CHAR * 3 + text[-MASK_KEEP:]


def identifier_for(request: Request, guest_id, value) -> str:
    """``value`` in full when the guest's identity is visible, masked otherwise."""
    if identity_visible(request, guest_id):
        return "" if value is None else str(value)
    return mask_identifier(value)


def owner_id(request: Request) -> int | None:
    workspace = auth.workspace_user(request)
    return int(workspace["id"]) if workspace else None


def apartment(request: Request, apartment_id: int):
    return db.query_one(
        f"SELECT * FROM apartment WHERE id = ? AND {db.null_safe_eq('owner_user_id')}",
        (apartment_id, owner_id(request)),
    )


def entity(request: Request, entity_id: int):
    return db.query_one(
        f"SELECT * FROM legal_entity WHERE id = ? AND {db.null_safe_eq('owner_user_id')}",
        (entity_id, owner_id(request)),
    )


def apartment_for_reservation(reservation, owner_user_id: int | None = None):
    """The apartment a reservation belongs to.

    A caller that already holds a reservation from an owner-scoped query passes
    no owner; one working from a bare apartment id passes the owner so the same
    join guards it. Either way the apartment a route acts on is reached through
    this module rather than a bare ``SELECT * FROM apartment``.
    """
    return db.query_one(
        f"SELECT * FROM apartment WHERE id = ? AND (? IS NULL OR {db.null_safe_eq('owner_user_id')})",
        (reservation["apartment_id"], owner_user_id, owner_user_id),
    )


def reservation(request: Request, reservation_id: int, columns: str = "r.*"):
    """One reservation, reached through its apartment's owner.

    ``columns`` exists because several routes need a couple of apartment columns
    alongside the stay (the permalink, the automation mode). Passing them here
    keeps the ownership join in one place instead of a route writing its own
    copy of the join and quietly forgetting the ``owner_user_id`` clause.
    """
    return db.query_one(
        f"SELECT {columns} FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE r.id = ? AND {db.null_safe_eq('a.owner_user_id')}",
        (reservation_id, owner_id(request)),
    )


def guest(request: Request, guest_id: int):
    return db.query_one(
        "SELECT g.* FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE g.id = ? AND {db.null_safe_eq('a.owner_user_id')}",
        (guest_id, owner_id(request)),
    )


def submission(request: Request, submission_id: int, columns: str = "s.*"):
    """One submission, reached through its apartment's owner (see ``reservation``)."""
    return db.query_one(
        f"SELECT {columns} FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        f"WHERE s.id = ? AND {db.null_safe_eq('a.owner_user_id')}",
        (submission_id, owner_id(request)),
    )


def feed(request: Request, feed_id: int):
    return db.query_one(
        "SELECT f.* FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
        f"WHERE f.id = ? AND {db.null_safe_eq('a.owner_user_id')}",
        (feed_id, owner_id(request)),
    )


def alert(request: Request, alert_id: int):
    return db.query_one(
        f"SELECT * FROM alert WHERE id = ? AND {db.null_safe_eq('owner_user_id')}",
        (alert_id, owner_id(request)),
    )


def apartments(request: Request, columns: str = "*", include_archived: bool = False):
    sql = f"SELECT {columns} FROM apartment WHERE {db.null_safe_eq('owner_user_id')}"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY internal_name"
    return db.query(sql, (owner_id(request),))


def entities(request: Request, include_archived: bool = False):
    sql = f"SELECT * FROM legal_entity WHERE {db.null_safe_eq('owner_user_id')}"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY name"
    return db.query(sql, (owner_id(request),))
