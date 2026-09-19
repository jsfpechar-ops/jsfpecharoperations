"""First-time setup progress for a host workspace."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import config, db, validation


def _dismissed_key(owner_user_id: int) -> str:
    return f"onboarding_dismissed_{owner_user_id}"


def is_dismissed(owner_user_id: Optional[int]) -> bool:
    return bool(
        owner_user_id
        and db.get_setting(_dismissed_key(owner_user_id), "0") == "1"
    )


def set_dismissed(owner_user_id: int, dismissed: bool) -> None:
    db.set_setting(_dismissed_key(owner_user_id), "1" if dismissed else "0")


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
    ready_entity_count = int(
        db.query_one(
            "SELECT COUNT(*) AS n FROM legal_entity "
            "WHERE owner_user_id IS ? AND TRIM(COALESCE(name, '')) != '' "
            "AND TRIM(COALESCE(seat, '')) != '' "
            "AND TRIM(COALESCE(ico, '')) != '' "
            "AND TRIM(COALESCE(contact_email, '')) != ''",
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

    # Wording lives in host_i18n under "onboarding.<id>.{title,detail,action}",
    # so a Czech host reads the setup steps in Czech and this module stays
    # about what is actually done and where to go next.
    steps = [
        {
            "id": "entity",
            "done": ready_entity_count > 0,
            "url": "/entities",
            "learn_url": "/guide#setup",
        },
        {
            "id": "property",
            "done": apartment_count > 0,
            "url": "/apartments/new" if entity_count else "/entities",
            "learn_url": "/guide#setup",
        },
        {
            "id": "calendars",
            "done": feed_count > 0,
            "url": f"/apartments/{first_apartment['id']}#calendars" if first_apartment else "/apartments/new",
            "learn_url": "/guide#stays",
        },
        {
            "id": "automation",
            "done": apartment_count > 0 and not setup_issues,
            "url": (
                f"/automation#apartment-{first_apartment['id']}"
                if first_apartment
                else "/automation"
            ),
            "learn_url": "/guide#reporting",
        },
        {
            "id": "guest_link",
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
            "learn_url": "/guide#guests",
        },
    ]

    current = next((step for step in steps if not step["done"]), None)
    completed = sum(1 for step in steps if step["done"])
    finished = completed == len(steps)
    finish = None
    if finished and first_apartment:
        token = first_apartment["permalink_token"] or ""
        policy = first_apartment["passport_photo_policy"] or "off"
        finish = {
            "apartment_id": first_apartment["id"],
            "name": first_apartment["internal_name"],
            "permalink": f"{config.PUBLIC_BASE_URL}/l/{token}",
            "permalink_token": token,
            "pin": first_apartment["permalink_pin"] or "",
            "passport_policy": policy,
            "communication_url": f"/apartments/{first_apartment['id']}#communication",
            "property_url": f"/apartments/{first_apartment['id']}",
        }
    return {
        "steps": steps,
        "current": current,
        "completed": completed,
        "total": len(steps),
        "percent": round((completed / len(steps)) * 100) if steps else 100,
        "finished": finished,
        "finish": finish,
        "dismissed": is_dismissed(owner_user_id),
        "setup_issues": setup_issues,
        "first_apartment_id": first_apartment["id"] if first_apartment else None,
    }
