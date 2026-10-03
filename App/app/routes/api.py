"""The command-palette JSON API.

The host UI fetches this on Ctrl-K. It answers with JSON rather than a page, so
it lives apart from the host pages in ``routes/admin.py``. ``admin.router``
includes this router, so the host POST protection is unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import access, auth, config, db, guest_slug, host_i18n

router = APIRouter()


@router.get("/api/command-palette")
def command_palette(request: Request):
    guard = auth.require_login(request)
    if guard:
        return JSONResponse({"items": []}, status_code=401)
    owner_user_id = access.owner_id(request)
    lang = host_i18n.lang_from_request(request)
    t = lambda key, **kwargs: host_i18n.translate(lang, key, **kwargs)
    items: List[Dict[str, Any]] = [
        {"label": t("nav.overview"), "group": t("command.group.pages"), "url": "/", "keywords": "dashboard"},
        {"label": t("nav.stays"), "group": t("command.group.pages"), "url": "/reservations", "keywords": "bookings calendar"},
        {"label": t("nav.reports"), "group": t("command.group.pages"), "url": "/submissions", "keywords": "ubyport dorucenka"},
        {"label": t("nav.housebook"), "group": t("command.group.pages"), "url": "/housebook", "keywords": "export csv"},
        {"label": t("nav.invoices"), "group": t("command.group.pages"), "url": "/invoices", "keywords": "faktura invoice doklad"},
        {"label": t("nav.stay_fees"), "group": t("command.group.pages"), "url": "/stay-fees", "keywords": "poplatek z pobytu hlaseni city tax"},
        {"label": t("nav.settings"), "group": t("command.group.pages"), "url": "/settings", "keywords": "environment account"},
        {"label": t("dashboard.sync_calendars"), "group": t("command.group.actions"), "url": "/sync", "method": "post", "keywords": "ical refresh"},
        {"label": t("stays.add_stay"), "group": t("command.group.actions"), "url": "/reservations?new=1", "keywords": "booking reservation"},
    ]
    destinations = [
        ("nav.properties", "/apartments", "property apartment ubytovani"),
        ("host.business", "/entities", "business operator company billing firma"),
        ("nav.guest_links", "/guest-links", "invitation guest link pin"),
        ("nav.automation", "/automation", "automatic reporting timing"),
        ("host.invoice_settings", "/invoices/settings", "invoice settings faktura"),
        ("settings.nav.archive", "/settings/archived", "restore archived records"),
        ("nav.privacy_requests", "/privacy-requests", "privacy gdpr"),
        ("nav.guide", "/guide", "help guide support"),
    ]
    if auth.current_user(request)["role"] == "admin":
        destinations.extend([
            ("nav.users", "/admin/users", "team accounts roles"),
            ("users.incidents_link", "/admin/incidents", "incidents"),
        ])
    items.extend({"label": t(key), "group": t("command.group.pages"), "url": url,
                  "keywords": keywords} for key, url, keywords in destinations)
    apartments = access.apartments(request)
    for apartment in apartments:
        items.append({
            "label": apartment["internal_name"],
            "meta": t("command.property"),
            "group": t("nav.properties"),
            "url": f"/apartments/{apartment['id']}",
            "tone": int(apartment["id"]) % 10,
            "keywords": f"{apartment['uby_name'] or ''} {apartment['city_en'] or ''}",
        })
        if apartment["permalink_token"]:
            items.append({
                "label": t("command.copy_property_link", property=apartment["internal_name"]),
                "group": t("command.group.actions"),
                "copy": f"{config.PUBLIC_BASE_URL}/l/{guest_slug.link_key(apartment)}",
                "tone": int(apartment["id"]) % 10,
                "keywords": "guest permalink pin",
            })
    reservations = db.query(
        "SELECT r.id, r.apartment_id, r.date_from, r.date_to, r.summary, a.internal_name "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.archived_at IS NULL AND (? IS NULL OR a.owner_user_id = ?) "
        "ORDER BY r.date_from DESC LIMIT 80",
        (owner_user_id, owner_user_id),
    )
    for stay in reservations:
        items.append({
            "label": f"{stay['internal_name']} · {stay['date_from']} – {stay['date_to']}",
            "meta": stay["summary"] or t("command.stay"),
            "group": t("nav.stays"),
            "url": f"/reservations/{stay['id']}",
            "tone": int(stay["apartment_id"]) % 10,
            "keywords": stay["summary"] or "",
        })
    submissions = db.query(
        "SELECT s.id, s.apartment_id, s.created_at, s.state, a.internal_name "
        "FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE (? IS NULL OR a.owner_user_id = ?) ORDER BY s.id DESC LIMIT 40",
        (owner_user_id, owner_user_id),
    )
    for submission in submissions:
        items.append({
            "label": t("reports.detail.title", id=submission["id"]),
            "meta": f"{submission['internal_name']} · {submission['state']}",
            "group": t("nav.reports"),
            "url": f"/submissions/{submission['id']}",
            "tone": int(submission["apartment_id"]) % 10,
            "keywords": submission["created_at"],
        })
    return JSONResponse({"items": items})
