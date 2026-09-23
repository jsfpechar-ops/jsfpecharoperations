"""Ownership-aware database lookups for host routes.

Every host object is reached through its apartment owner. Keeping these joins
in one module makes an omitted ownership check conspicuous in code review and
prevents numeric IDs from becoming cross-account access.
"""
from __future__ import annotations

from fastapi import Request

from . import auth, db


def owner_id(request: Request) -> int | None:
    workspace = auth.workspace_user(request)
    return int(workspace["id"]) if workspace else None


def apartment(request: Request, apartment_id: int):
    return db.query_one(
        "SELECT * FROM apartment WHERE id = ? AND owner_user_id IS ?",
        (apartment_id, owner_id(request)),
    )


def entity(request: Request, entity_id: int):
    return db.query_one(
        "SELECT * FROM legal_entity WHERE id = ? AND owner_user_id IS ?",
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
        "SELECT * FROM apartment WHERE id = ? AND (? IS NULL OR owner_user_id IS ?)",
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
        "WHERE r.id = ? AND a.owner_user_id IS ?",
        (reservation_id, owner_id(request)),
    )


def guest(request: Request, guest_id: int):
    return db.query_one(
        "SELECT g.* FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE g.id = ? AND a.owner_user_id IS ?",
        (guest_id, owner_id(request)),
    )


def submission(request: Request, submission_id: int, columns: str = "s.*"):
    """One submission, reached through its apartment's owner (see ``reservation``)."""
    return db.query_one(
        f"SELECT {columns} FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE s.id = ? AND a.owner_user_id IS ?",
        (submission_id, owner_id(request)),
    )


def feed(request: Request, feed_id: int):
    return db.query_one(
        "SELECT f.* FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
        "WHERE f.id = ? AND a.owner_user_id IS ?",
        (feed_id, owner_id(request)),
    )


def alert(request: Request, alert_id: int):
    return db.query_one(
        "SELECT * FROM alert WHERE id = ? AND owner_user_id IS ?",
        (alert_id, owner_id(request)),
    )


def apartments(request: Request, columns: str = "*", include_archived: bool = False):
    sql = f"SELECT {columns} FROM apartment WHERE owner_user_id IS ?"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY internal_name"
    return db.query(sql, (owner_id(request),))


def entities(request: Request, include_archived: bool = False):
    sql = "SELECT * FROM legal_entity WHERE owner_user_id IS ?"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY name"
    return db.query(sql, (owner_id(request),))
