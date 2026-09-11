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
        "SELECT * FROM apartment WHERE id = ? AND owner_user_id = ?",
        (apartment_id, owner_id(request)),
    )


def entity(request: Request, entity_id: int):
    return db.query_one(
        "SELECT * FROM legal_entity WHERE id = ? AND owner_user_id = ?",
        (entity_id, owner_id(request)),
    )


def reservation(request: Request, reservation_id: int):
    return db.query_one(
        "SELECT r.* FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.id = ? AND a.owner_user_id = ?",
        (reservation_id, owner_id(request)),
    )


def guest(request: Request, guest_id: int):
    return db.query_one(
        "SELECT g.* FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE g.id = ? AND a.owner_user_id = ?",
        (guest_id, owner_id(request)),
    )


def submission(request: Request, submission_id: int):
    return db.query_one(
        "SELECT s.* FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE s.id = ? AND a.owner_user_id = ?",
        (submission_id, owner_id(request)),
    )


def feed(request: Request, feed_id: int):
    return db.query_one(
        "SELECT f.* FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
        "WHERE f.id = ? AND a.owner_user_id = ?",
        (feed_id, owner_id(request)),
    )


def alert(request: Request, alert_id: int):
    return db.query_one(
        "SELECT * FROM alert WHERE id = ? AND owner_user_id = ?",
        (alert_id, owner_id(request)),
    )


def apartments(request: Request, columns: str = "*", include_archived: bool = False):
    sql = f"SELECT {columns} FROM apartment WHERE owner_user_id = ?"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY internal_name"
    return db.query(sql, (owner_id(request),))


def entities(request: Request):
    return db.query(
        "SELECT * FROM legal_entity WHERE owner_user_id = ? ORDER BY name",
        (owner_id(request),),
    )
