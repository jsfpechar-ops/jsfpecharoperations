"""First-time setup progress for a host workspace."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import db, validation


def _apartment_issues(apartment) -> List[validation.Issue]:
    data = dict(apartment)
    data["uby_ws_password"] = db.decrypt_secret(apartment["uby_ws_password_enc"])
    return validation.errors_only(validation.validate_apartment(data))


def progress(owner_user_id: int) -> Dict[str, Any]:
    """Return setup steps and the next action for a workspace."""
    entity_count = int(
        db.query_one(
            "SELECT COUNT(*) AS n FROM legal_entity WHERE owner_user_id IS ?",
            (owner_user_id,),
        )["n"]
    )
    apartments = db.query(
        "SELECT a.*, "
        "  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1) AS feeds "
        "FROM apartment a "
        "WHERE a.archived_at IS NULL AND a.owner_user_id IS ? "
        "ORDER BY a.id",
        (owner_user_id,),
    )
    apartment_count = len(apartments)
    feed_count = sum(int(apartment["feeds"] or 0) for apartment in apartments)
    setup_issues = []
    for apartment in apartments:
        issues = _apartment_issues(apartment)
        if issues:
            setup_issues.append({"apartment": apartment, "issues": issues})
    first_apartment = apartments[0] if apartments else None

    steps = [
        {
            "id": "entity",
            "title": "Legal entity",
            "detail": "The company or sole trader registered in UbyPort.",
            "done": entity_count > 0,
            "url": "/entities",
            "action": "Add legal entity",
        },
        {
            "id": "property",
            "title": "Property",
            "detail": "Each flat or house you rent out.",
            "done": apartment_count > 0,
            "url": "/apartments/new" if entity_count else "/entities",
            "action": "Add property",
        },
        {
            "id": "calendars",
            "title": "Calendar links",
            "detail": "Airbnb or Booking.com iCal URLs so stays appear automatically.",
            "done": feed_count > 0,
            "url": f"/apartments/{first_apartment['id']}#calendars" if first_apartment else "/apartments/new",
            "action": "Connect calendars",
        },
        {
            "id": "automation",
            "title": "Automation & UbyPort",
            "detail": "Web-service credentials and when reports are sent.",
            "done": apartment_count > 0 and not setup_issues,
            "url": (
                f"/automation#apartment-{first_apartment['id']}"
                if first_apartment
                else "/automation"
            ),
            "action": "Finish automation",
        },
        {
            "id": "guest_link",
            "title": "Guest link",
            "detail": "Paste into your Airbnb or Booking.com check-in message.",
            "done": (
                apartment_count > 0
                and feed_count > 0
                and not setup_issues
            ),
            "url": (
                f"/apartments/{first_apartment['id']}#communication"
                if first_apartment
                else "/apartments"
            ),
            "action": "Copy guest link",
        },
    ]

    current = next((step for step in steps if not step["done"]), None)
    completed = sum(1 for step in steps if step["done"])
    return {
        "steps": steps,
        "current": current,
        "completed": completed,
        "total": len(steps),
        "finished": completed == len(steps),
        "setup_issues": setup_issues,
        "first_apartment_id": first_apartment["id"] if first_apartment else None,
    }
