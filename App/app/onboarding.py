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
            f"SELECT COUNT(*) AS n FROM legal_entity WHERE {db.null_safe_eq('owner_user_id')}",
            (owner_user_id,),
        )["n"]
    )
    ready_entity_count = int(
        db.query_one(
            "SELECT COUNT(*) AS n FROM legal_entity "
            f"WHERE {db.null_safe_eq('owner_user_id')} AND TRIM(COALESCE(name, '')) != '' "
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
        f"WHERE a.archived_at IS NULL AND {db.null_safe_eq('a.owner_user_id')} "
        "ORDER BY a.id",
        (owner_user_id,),
    )
    apartment_count = len(apartments)
    feed_count = sum(int(apartment["feeds"] or 0) for apartment in apartments)
    # A host who takes direct bookings has no iCal feed to connect. A stay typed
    # in by hand has to satisfy the calendar step, or that host can never finish.
    manual_stays = int(
        db.query_one(
            "SELECT COUNT(*) AS n FROM reservation r "
            "JOIN apartment a ON a.id = r.apartment_id "
            f"WHERE {db.null_safe_eq('a.owner_user_id')} AND a.archived_at IS NULL "
            "AND r.status = 'active' AND r.source = 'manual'",
            (owner_user_id,),
        )["n"]
    )
    has_stays = feed_count > 0 or manual_stays > 0
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
            "done": has_stays,
            "url": f"/apartments/{first_apartment['id']}#calendars" if first_apartment else "/apartments/new",
            "manual_url": "/reservations#add-stay-panel",
            "learn_url": "/guide#stays",
        },
        {
            "id": "automation",
            "done": apartment_count > 0 and not setup_issues,
            # The credentials and the address both live on the property page, so
            # this is the one place the step can actually be finished.
            "url": (
                f"/apartments/{first_apartment['id']}#ubyport"
                if first_apartment
                else "/apartments/new"
            ),
            "learn_url": "/guide#reporting",
        },
        {
            "id": "guest_link",
            "done": (
                apartment_count > 0
                and has_stays
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
