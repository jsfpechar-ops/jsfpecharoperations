"""A stay to issue test invoices for: every new invoice needs one (task 0020)."""
from __future__ import annotations

import secrets
from datetime import timedelta

from app import claim, db

UID_PREFIX = "invstay-"


def make_stay(owner_user_id, *, entity_id=None, nights=3) -> int:
    """A manual stay that ended yesterday, in its own property. Returns the reservation id."""
    now = db.utcnow()
    today = claim.prague_today()
    tag = secrets.token_hex(4)
    apartment_id = db.insert(
        "apartment",
        {"internal_name": "Chata", "owner_user_id": owner_user_id, "legal_entity_id": entity_id,
         "permalink_token": f"{UID_PREFIX}{tag}", "automation_mode": "manual",
         "default_purpose": "10", "active": 1, "created_at": now},
    )
    return db.insert(
        "reservation",
        {"apartment_id": apartment_id, "source": "manual", "uid": f"{UID_PREFIX}{tag}",
         "date_from": (today - timedelta(days=nights + 1)).isoformat(),
         "date_to": (today - timedelta(days=1)).isoformat(),
         "status": "active", "created_at": now, "updated_at": now},
    )


def stay_form(reservation_id: int, price: str = "10000") -> dict:
    """The fields a stay invoice POST needs on top of the old ones."""
    return {"reservation_id": str(reservation_id), "stay_price": price}


def drop_stays(owner_user_id) -> None:
    """Call after the test's invoices are deleted (invoices point at the apartment)."""
    db.execute(
        "DELETE FROM reservation WHERE uid LIKE ? AND apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id = ?)",
        (UID_PREFIX + "%", owner_user_id),
    )
    db.execute(
        "DELETE FROM apartment WHERE permalink_token LIKE ? AND owner_user_id = ?",
        (UID_PREFIX + "%", owner_user_id),
    )
