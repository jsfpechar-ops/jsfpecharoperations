"""Host-facing routes: dashboard, apartments, reservations, submissions, exports."""
from __future__ import annotations

import base64
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode, urlparse

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse

from .. import (
    access,
    alerts,
    auth,
    celebrations,
    codelists,
    config,
    db,
    deadlines,
    demo,
    host_i18n,
    housebook,
    icalsync,
    passport_photos,
    reporting,
    stays_import,
    validation,
)
from ..templating import render
from ..ubyport.client import UbyportError, UbyportTransportError
from . import admin_accounts
from .admin_helpers import back as _back
from .admin_helpers import form_str as _form_str

router = APIRouter()
router.include_router(admin_accounts.router)


# --- helpers -------------------------------------------------------------

# A house book with years of history is still well under a megabyte, so this
# is generous for a real import and stops an upload from being read whole into
# memory.


def _ensure_apartment_pin(apartment):
    """Backfill a PIN for apartments created before PIN support existed."""
    if apartment and not apartment["permalink_pin"]:
        pin = auth.new_permalink_pin()
        db.update("apartment", apartment["id"], {"permalink_pin": pin})
        return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment["id"],))
    return apartment


def _safe_return_to(request: Request, default: str) -> str:
    """Accept only local paths so breadcrumbs can preserve list state safely."""
    value = (request.query_params.get("return_to") or "").strip()
    if not value.startswith("/") or value.startswith("//") or "\n" in value or "\r" in value:
        return default
    return value


def _apartment_with_secret(apartment) -> Dict[str, Any]:
    data = dict(apartment)
    data["uby_ws_password"] = db.decrypt_secret(apartment["uby_ws_password_enc"])
    return data


def _apartment_issues(apartment) -> List[validation.Issue]:
    return validation.validate_apartment(_apartment_with_secret(apartment))


def _form_return_to(form, default: str) -> str:
    value = _form_str(form, "return_to")
    if value.startswith("/") and not value.startswith("//") and "\n" not in value and "\r" not in value:
        return value
    return default


def _redirect_path_from_referer(request: Request, default: str = "/") -> str:
    """Use only the path (and query) from Referer when it targets this host."""
    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return default
    parsed = urlparse(referer)
    site_host = (request.headers.get("host") or "").split(":", 1)[0].lower()
    ref_host = (parsed.hostname or "").lower()
    if not site_host or ref_host != site_host:
        return default
    path = parsed.path or default
    if not path.startswith("/") or path.startswith("//"):
        return default
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _form_int(form, key: str) -> Optional[int]:
    raw = _form_str(form, key)
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _query_int(request: Request, key: str) -> Optional[int]:
    """A hand-edited query string must never produce a 500."""
    raw = (request.query_params.get(key) or "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _query_date(request: Request, key: str) -> str:
    raw = (request.query_params.get(key) or "").strip()
    parsed = validation.parse_iso_date(raw)
    return parsed.isoformat() if parsed else ""


def dashboard_rows(
    days_ahead: int = 21, days_back: int = 45, owner_user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Every stay worth looking at, ordered by how urgent it is."""
    start = (date.today() - timedelta(days=days_back)).isoformat()
    end = (date.today() + timedelta(days=days_ahead)).isoformat()
    rows = db.query(
        "SELECT r.*, a.internal_name, a.permalink_token, a.automation_mode "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status = 'active' AND a.active = 1 AND a.archived_at IS NULL "
        "AND r.archived_at IS NULL AND (? IS NULL OR a.owner_user_id = ?) "
        "AND r.date_from BETWEEN ? AND ? "
        "ORDER BY r.date_from",
        (owner_user_id, owner_user_id, start, end),
    )
    out: List[Dict[str, Any]] = []
    for reservation in rows:
        check_in = validation.parse_iso_date(reservation["date_from"])
        progress = reporting.reservation_progress(reservation)
        level = deadlines.urgency(check_in) if check_in else "future"
        # A finished stay with nothing outstanding is noise on a dashboard.
        if progress["status"] in ("reported", "not_required") and level in ("overdue", "ok", "urgent", "soon"):
            if check_in and check_in < date.today() - timedelta(days=3):
                continue
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
        controls = reporting.send_controls(reservation, apartment, progress) if apartment else {}
        out.append(
            {
                "reservation": reservation,
                "progress": progress,
                "controls": controls,
                "urgency": level,
                "check_in": check_in,
                "deadline": deadlines.reporting_deadline(check_in) if check_in else None,
            }
        )
    out.sort(
        key=lambda row: (
            0 if row["progress"]["status"] in ("failed",) else 1,
            deadlines.URGENCY_ORDER.get(row["urgency"], 9),
            row["reservation"]["date_from"],
        )
    )
    return out


# --- setup and login -----------------------------------------------------

@router.post("/demo")
def load_demo(request: Request):
    """Fill an empty install with something to click through."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment_id = demo.seed(access.owner_id(request))
    if not apartment_id:
        return _back("/", err="Demo data is only available before you add your first property.")
    return _back("/", msg="Demo property loaded. Use “Clear demo data” on Overview when finished.")


@router.post("/demo/reset")
def reset_demo(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not demo.clear(access.owner_id(request)):
        return _back("/", err="The built-in demo dataset was not found.")
    return _back("/", msg="Demo data cleared.")


# --- dashboard -----------------------------------------------------------

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
        {"label": t("nav.settings"), "group": t("command.group.pages"), "url": "/settings", "keywords": "environment account"},
        {"label": t("dashboard.sync_calendars"), "group": t("command.group.actions"), "url": "/sync", "method": "post", "keywords": "ical refresh"},
        {"label": t("stays.add_stay"), "group": t("command.group.actions"), "url": "/reservations?new=1", "keywords": "booking reservation"},
    ]
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
                "copy": f"{config.PUBLIC_BASE_URL}/l/{apartment['permalink_token']}",
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

@router.get("/")
def dashboard(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_user_id = access.owner_id(request)
    apartments = access.apartments(request)
    rows = dashboard_rows(owner_user_id=owner_user_id)
    queue = reporting.queue_groups(rows)
    counts = reporting.queue_counts(rows, queue)
    needs_action, waiting = queue["needs_action"], queue["waiting"]
    upcoming, completed = queue["upcoming"], queue["completed"][:8]
    setup_warnings = []
    for apartment in apartments:
        issues = validation.errors_only(_apartment_issues(apartment))
        if issues:
            setup_warnings.append({"apartment": apartment, "issues": issues})
    # dashboard_rows() is already sorted by legal urgency, so the first row that
    # needs work is the one thing worth putting at the top of the page.
    focus = next(iter(needs_action), None) or next(iter(waiting), None)
    milestone, sent_count, minutes_saved = celebrations.celebration_context(owner_user_id)
    return render(
        request,
        "dashboard.html",
        {
            "rows": rows,
            "focus": focus,
            "queue_groups": {
                "needs_action": needs_action,
                "waiting": waiting,
                "upcoming": upcoming,
                "completed": completed,
            },
            "counts": counts,
            "apartments": apartments,
            "setup_warnings": setup_warnings,
            "last_sync": db.get_setting("last_ical_sync"),
            "demo_loaded": any(demo.is_demo_apartment(apartment) for apartment in apartments),
            "celebration_milestone": milestone,
            "sent_guest_count": sent_count,
            "minutes_saved": minutes_saved,
        },
    )


@router.get("/guide")
def guide_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    return render(request, "guide.html")


@router.post("/celebrations/dismiss")
async def dismiss_celebration(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    milestone = int(_form_str(form, "milestone") or "0")
    owner_user_id = access.owner_id(request)
    if owner_user_id and milestone:
        celebrations.acknowledge(owner_user_id, milestone)
    return RedirectResponse(_form_str(form, "return_to") or "/", status_code=303)


# --- guest communication ------------------------------------------------

@router.get("/guest-links")
def guest_links(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartments = db.query(
        "SELECT a.*, e.name AS entity_name, "
        "  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1) AS feeds "
        "FROM apartment a LEFT JOIN legal_entity e ON e.id = a.legal_entity_id "
        "WHERE a.active = 1 AND a.archived_at IS NULL AND a.owner_user_id IS ? "
        "ORDER BY a.internal_name",
        (access.owner_id(request),),
    )
    rows = []
    for apartment in apartments:
        apartment = _ensure_apartment_pin(apartment)
        rows.append(
            {
                "apartment": apartment,
                "issues": validation.errors_only(_apartment_issues(apartment)),
                "permalink": f"{config.PUBLIC_BASE_URL}/l/{apartment['permalink_token']}",
                "pin": apartment["permalink_pin"] or "",
            }
        )
    return render(request, "guest_links.html", {"rows": rows})


# --- legal entities ------------------------------------------------------

@router.get("/entities")
def entities(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_user_id = access.owner_id(request)
    rows = db.query(
        "SELECT e.*, (SELECT COUNT(*) FROM apartment a WHERE a.legal_entity_id = e.id) AS apartments "
        "FROM legal_entity e WHERE e.owner_user_id IS ? AND e.archived_at IS NULL ORDER BY e.name",
        (owner_user_id,),
    )
    archived = db.query(
        "SELECT e.*, (SELECT COUNT(*) FROM apartment a WHERE a.legal_entity_id = e.id) AS apartments "
        "FROM legal_entity e WHERE e.owner_user_id IS ? AND e.archived_at IS NOT NULL "
        "ORDER BY e.archived_at DESC",
        (owner_user_id,),
    )
    edit_entity = None
    edit_id = request.query_params.get("edit")
    if edit_id and edit_id.isdigit():
        edit_entity = db.query_one(
            "SELECT * FROM legal_entity WHERE id = ? AND owner_user_id IS ?",
            (int(edit_id), owner_user_id),
        )
    return render(
        request,
        "entities.html",
        {"entities": rows, "archived_entities": archived, "edit_entity": edit_entity},
    )


ENTITY_FIELDS = ("name", "seat", "ico", "dic", "contact_email", "contact_phone")


@router.post("/entities")
async def create_entity(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    payload = {field: _form_str(form, field) for field in ENTITY_FIELDS}
    if not payload["name"]:
        return _back("/entities", err="Name is required.")
    payload["created_at"] = db.utcnow()
    payload["owner_user_id"] = access.owner_id(request)
    entity_id = db.insert("legal_entity", payload)
    apartments = access.apartments(request)
    if not apartments:
        return _back(
            f"/apartments/new?legal_entity_id={entity_id}",
            msg=f"Added {payload['name']}. Next, add your first property.",
        )
    return _back("/entities", msg=f"Added {payload['name']}.")


@router.post("/entities/{entity_id}")
async def update_entity(entity_id: int, request: Request):
    """These details are what guests see as the data controller, so they have
    to be editable without deleting and recreating the entity."""
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.entity(request, entity_id):
        return _back("/entities", err="No such legal entity.")
    form = await request.form()
    payload = {field: _form_str(form, field) for field in ENTITY_FIELDS}
    if not payload["name"]:
        return _back("/entities", err="Name is required.")
    db.update("legal_entity", entity_id, payload)
    return _back("/entities", msg="Saved.")


@router.post("/entities/{entity_id}/archive")
def archive_entity(entity_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entity = access.entity(request, entity_id)
    if not entity:
        return _back("/entities", err="No such legal entity.")
    if entity["archived_at"]:
        return _back("/entities", err="Already archived.")
    used = db.query_one(
        "SELECT COUNT(*) AS n FROM apartment WHERE legal_entity_id = ? AND owner_user_id IS ?",
        (entity_id, access.owner_id(request)),
    )
    if used and used["n"]:
        return _back(
            "/entities",
            err="Detach or archive the properties linked to this entity first.",
        )
    db.update("legal_entity", entity_id, {"archived_at": db.utcnow()})
    db.audit("entity_archived", f"id={entity_id}")
    return _back("/entities", msg=f"“{entity['name']}” archived.")


@router.post("/entities/{entity_id}/unarchive")
async def unarchive_entity(entity_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/entities?edit={entity_id}")
    entity = access.entity(request, entity_id)
    if not entity:
        return _back("/entities", err="No such legal entity.")
    if not entity["archived_at"]:
        return _back(return_to, err="Not archived.")
    db.update("legal_entity", entity_id, {"archived_at": None})
    db.audit("entity_unarchived", f"id={entity_id}")
    return _back(return_to, msg=f"“{entity['name']}” restored.")


@router.post("/entities/{entity_id}/delete")
def delete_entity(entity_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entity = access.entity(request, entity_id)
    if not entity:
        return _back("/entities", err="No such legal entity.")
    if not entity["archived_at"]:
        return _back("/entities", err="Archive the legal entity before deleting it.")
    used = db.query_one(
        "SELECT COUNT(*) AS n FROM apartment WHERE legal_entity_id = ? AND owner_user_id IS ?",
        (entity_id, access.owner_id(request)),
    )
    if used and used["n"]:
        return _back("/entities", err="Detach the properties from this entity first.")
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.audit("entity_deleted", f"id={entity_id}")
    return _back("/entities", msg="Deleted permanently.")


# --- apartments ----------------------------------------------------------

@router.get("/apartments")
def apartments_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = db.query(
        "SELECT a.*, e.name AS entity_name, "
        "  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1) AS feeds, "
        "  (SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = a.id AND r.status = 'active') AS reservations "
        "FROM apartment a LEFT JOIN legal_entity e ON e.id = a.legal_entity_id "
        "WHERE a.archived_at IS NULL AND a.owner_user_id IS ? ORDER BY a.internal_name",
        (access.owner_id(request),),
    )
    archived = db.query(
        "SELECT a.*, e.name AS entity_name, "
        "  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1) AS feeds, "
        "  (SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = a.id AND r.status = 'active') AS reservations "
        "FROM apartment a LEFT JOIN legal_entity e ON e.id = a.legal_entity_id "
        "WHERE a.archived_at IS NOT NULL AND a.owner_user_id IS ? ORDER BY a.archived_at DESC",
        (access.owner_id(request),),
    )
    enriched = [
        {"apartment": row, "issues": validation.errors_only(_apartment_issues(row))} for row in rows
    ]
    archived_rows = [
        {"apartment": row, "issues": validation.errors_only(_apartment_issues(row))} for row in archived
    ]
    return render(request, "apartments.html", {"rows": enriched, "archived_rows": archived_rows})


@router.get("/apartments/new")
def apartment_new(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    selected_entity_id = _query_int(request, "legal_entity_id")
    entities = access.entities(request)
    if selected_entity_id and not any(entity["id"] == selected_entity_id for entity in entities):
        selected_entity_id = None
    return render(
        request,
        "apartment_form.html",
        {
            "apartment": None,
            "entities": entities,
            "selected_entity_id": selected_entity_id,
            "purposes": codelists.purpose_options("en"),
        },
    )


APARTMENT_TEXT_FIELDS = (
    "internal_name",
    "city_en",
    "addr_okres",
    "addr_obec",
    "addr_obec_cast",
    "addr_street",
    "addr_house_no",
    "addr_orient_no",
    "addr_zip",
    "uby_idub",
    "uby_mark",
    "uby_name",
    "uby_contact",
    "uby_ws_user",
    "notes",
)


def _apartment_payload(form) -> Dict[str, Any]:
    payload: Dict[str, Any] = {field: _form_str(form, field) for field in APARTMENT_TEXT_FIELDS}
    payload["uby_mark"] = payload["uby_mark"].upper()
    payload["addr_zip"] = validation.normalise_zip(payload["addr_zip"])
    payload["legal_entity_id"] = _form_int(form, "legal_entity_id")
    mode = _form_str(form, "automation_mode", "scheduled")
    payload["automation_mode"] = mode if mode in reporting.AUTOMATION_MODES else "scheduled"
    payload["submit_after_hours"] = _form_int(form, "submit_after_hours") or 24
    payload["permalink_window_days"] = _form_int(form, "permalink_window_days") or 3
    purpose = _form_str(form, "default_purpose", validation.DEFAULT_PURPOSE)
    payload["default_purpose"] = purpose if purpose in validation.PURPOSE_CODES else "10"
    payload["active"] = 1 if form.get("active") else 0
    return payload


@router.post("/apartments")
async def apartment_create(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    payload = _apartment_payload(form)
    if not payload["internal_name"]:
        return _back("/apartments/new", err="Give the apartment a name.")
    payload["permalink_token"] = auth.new_permalink_token()
    payload["permalink_pin"] = auth.new_permalink_pin()
    payload["created_at"] = db.utcnow()
    payload["owner_user_id"] = access.owner_id(request)
    if payload["legal_entity_id"] and not access.entity(request, payload["legal_entity_id"]):
        return _back("/apartments/new", err="No such legal entity.")
    password = _form_str(form, "uby_ws_password")
    payload["uby_ws_password_enc"] = db.encrypt_secret(password) if password else None
    apartment_id = db.insert("apartment", payload)
    db.audit("apartment_created", f"id={apartment_id}")
    return _back(
        f"/apartments/{apartment_id}#calendars",
        msg="Property created. Next, paste your Airbnb or Booking.com calendar link.",
    )


@router.get("/apartments/{apartment_id}")
def apartment_detail(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _ensure_apartment_pin(
        access.apartment(request, apartment_id)
    )
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    feeds = db.query("SELECT * FROM ical_feed WHERE apartment_id = ? ORDER BY id", (apartment_id,))
    return render(
        request,
        "apartment_form.html",
        {
            "apartment": apartment,
            "entities": access.entities(request),
            "feeds": feeds,
            "issues": _apartment_issues(apartment),
            "purposes": codelists.purpose_options("en"),
            "permalink": f"{config.PUBLIC_BASE_URL}/l/{apartment['permalink_token']}",
            "pin": apartment["permalink_pin"] or "",
            "has_password": bool(apartment["uby_ws_password_enc"]),
            "codelist_fetched": codelists.last_fetched(codelists.KIND_COUNTRIES),
        },
    )


@router.post("/apartments/{apartment_id}")
async def apartment_update(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    form = await request.form()
    payload = _apartment_payload(form)
    if payload["legal_entity_id"] and not access.entity(request, payload["legal_entity_id"]):
        return _back(f"/apartments/{apartment_id}", err="No such legal entity.")
    for key in ("automation_mode", "submit_after_hours", "default_purpose"):
        payload.pop(key, None)
    password = _form_str(form, "uby_ws_password")
    if password:
        payload["uby_ws_password_enc"] = db.encrypt_secret(password)
    pin_raw = _form_str(form, "permalink_pin")
    if pin_raw:
        pin = auth.normalise_permalink_pin(pin_raw)
        if not pin:
            return _back(f"/apartments/{apartment_id}", err="PIN must be 4 or 6 digits.")
        payload["permalink_pin"] = pin
    return_to = _form_return_to(form, f"/apartments/{apartment_id}")
    db.update("apartment", apartment_id, payload)
    db.audit("apartment_updated", f"id={apartment_id}")
    return _back(return_to, msg="Saved.")


@router.post("/apartments/{apartment_id}/regenerate-pin")
async def regenerate_pin(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    pin = auth.new_permalink_pin()
    db.update("apartment", apartment_id, {"permalink_pin": pin})
    db.audit("pin_rotated", f"apartment={apartment_id}")
    return _back(
        _form_return_to(form, "/guest-links"),
        msg=f"New PIN generated: {pin}",
    )


@router.post("/apartments/{apartment_id}/regenerate-link")
async def regenerate_link(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    db.update(
        "apartment",
        apartment_id,
        {
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
        },
    )
    db.audit("permalink_rotated", f"apartment={apartment_id}")
    return _back(
        _form_return_to(form, "/guest-links"),
        msg="New guest link and PIN generated. Update your automated messages on the booking portals.",
    )


UBYPORT_TEXT_FIELDS = (
    "uby_idub",
    "uby_mark",
    "uby_name",
    "uby_contact",
    "uby_ws_user",
)


def _automation_payload(form) -> Dict[str, Any]:
    payload: Dict[str, Any] = {field: _form_str(form, field) for field in UBYPORT_TEXT_FIELDS}
    payload["uby_mark"] = payload["uby_mark"].upper()
    mode = _form_str(form, "automation_mode", "scheduled")
    payload["automation_mode"] = mode if mode in reporting.AUTOMATION_MODES else "scheduled"
    payload["submit_after_hours"] = _form_int(form, "submit_after_hours") or 24
    purpose = _form_str(form, "default_purpose", validation.DEFAULT_PURPOSE)
    payload["default_purpose"] = purpose if purpose in validation.PURPOSE_CODES else "10"
    return payload


@router.get("/automation")
def automation_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartments = access.apartments(request)
    rows = [
        {
            "apartment": apartment,
            "issues": validation.errors_only(_apartment_issues(apartment)),
            "has_password": bool(apartment["uby_ws_password_enc"]),
        }
        for apartment in apartments
    ]
    return render(
        request,
        "automation.html",
        {
            "rows": rows,
            "purposes": codelists.purpose_options("en"),
        },
    )


@router.post("/automation/{apartment_id}")
async def automation_update(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/automation", err="No such apartment.")
    form = await request.form()
    payload = _automation_payload(form)
    password = _form_str(form, "uby_ws_password")
    if password:
        payload["uby_ws_password_enc"] = db.encrypt_secret(password)
    db.update("apartment", apartment_id, payload)
    db.audit("automation_updated", f"id={apartment_id} mode={payload['automation_mode']}")
    return _back(
        _form_return_to(form, f"/automation#apartment-{apartment_id}"),
        msg=f"Saved settings for {apartment['internal_name']}.",
    )


@router.post("/apartments/{apartment_id}/archive")
def archive_apartment(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    if apartment["archived_at"]:
        return _back(f"/apartments/{apartment_id}", err="Already archived.")
    db.update(
        "apartment",
        apartment_id,
        {"archived_at": db.utcnow(), "active": 0},
    )
    db.audit("apartment_archived", f"id={apartment_id}")
    return _back("/apartments", msg=f"“{apartment['internal_name']}” archived. Its history is kept.")


@router.post("/apartments/{apartment_id}/unarchive")
async def unarchive_apartment(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/apartments/{apartment_id}")
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    if not apartment["archived_at"]:
        return _back(return_to, err="Not archived.")
    db.update(
        "apartment",
        apartment_id,
        {"archived_at": None, "active": 1},
    )
    db.audit("apartment_unarchived", f"id={apartment_id}")
    return _back(return_to, msg="Property restored from archive.")


@router.post("/apartments/{apartment_id}/feeds")
async def add_feed(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.apartment(request, apartment_id):
        return _back("/apartments", err="No such apartment.")
    form = await request.form()
    url = _form_str(form, "url")
    try:
        from ..feed_url import FeedUrlError, validate_calendar_url

        url = validate_calendar_url(url)
    except FeedUrlError as exc:
        return _back(f"/apartments/{apartment_id}", err=str(exc))
    db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": url,
            "label": _form_str(form, "label"),
            "own_name": _form_str(form, "own_name"),
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    totals = icalsync.sync_all(apartment_id)
    if totals["errors"]:
        return _back(f"/apartments/{apartment_id}", err="Calendar added but could not be read - see the alert above.")
    return _back(
        f"/apartments/{apartment_id}",
        msg=f"Calendar added. {totals['created']} stay(s) imported.",
    )


@router.post("/feeds/{feed_id}/delete")
def delete_feed(feed_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    feed = access.feed(request, feed_id)
    if not feed:
        return _back("/apartments", err="No such calendar.")
    db.execute("DELETE FROM ical_feed WHERE id = ?", (feed_id,))
    return _back(f"/apartments/{feed['apartment_id']}", msg="Calendar removed. Existing stays were kept.")


@router.post("/sync")
def sync_now(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_user_id = access.owner_id(request)
    totals = icalsync.sync_all(owner_user_id=owner_user_id)
    reporting.check_deadlines(owner_user_id=owner_user_id)
    return _back(
        "/",
        msg=(
            f"Synced {totals['feeds']} calendar(s): {totals['created']} new, "
            f"{totals['updated']} updated, {totals['cancelled']} cancelled."
        ),
        err="Some calendars could not be read." if totals["errors"] else "",
    )


@router.post("/apartments/{apartment_id}/test-connection")
async def test_connection(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/apartments/{apartment_id}")
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    client = reporting.client_for(apartment)
    try:
        available = client.test_availability()
        limit = client.max_batch_size()
        message = (
            f"UbyPort reachable at {client.endpoint} (available={available}"
            + (f", max batch {limit}" if limit else "")
            + ")."
        )
        return _back(return_to, msg=message)
    except (UbyportTransportError, UbyportError) as exc:
        return _back(return_to, err=str(exc))


@router.post("/apartments/{apartment_id}/refresh-codelists")
async def refresh_codelists(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/apartments/{apartment_id}")
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    try:
        written = codelists.refresh_all(reporting.client_for(apartment))
    except (UbyportTransportError, UbyportError) as exc:
        return _back(return_to, err=f"Could not refresh code lists: {exc}")
    return _back(
        return_to,
        msg=(
            f"Code lists refreshed from UbyPort: {written.get('staty', 0)} countries, "
            f"{written.get('ucely', 0)} purposes, {written.get('chyby', 0)} error codes."
        ),
    )


# --- reservations --------------------------------------------------------

RESERVATION_PAGE_SIZE = 50

# Presets are what a host actually asks for; the two date boxes cover the rest.
RESERVATION_RANGES = ("upcoming", "past", "all")


@router.get("/reservations")
def reservations_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    status = request.query_params.get("status", "active")
    if status not in ("active", "cancelled", "ignored", "all"):
        status = "active"
    apartment_id = _query_int(request, "apartment")
    date_from = _query_date(request, "from")
    date_to = _query_date(request, "to")

    today = date.today().isoformat()
    date_range = request.query_params.get("range", "")
    show_archive = date_range == "archive"
    if date_range not in RESERVATION_RANGES and date_range != "archive":
        # Explicit dates win; otherwise show what is still ahead, because a
        # list that opens on last winter's bookings is useless.
        date_range = "custom" if (date_from or date_to) else "upcoming"
    if date_range == "upcoming":
        date_from, date_to = today, ""
    elif date_range == "past":
        # Departed stays only — a guest checking in today still belongs under Upcoming.
        date_from, date_to = "", (date.today() - timedelta(days=1)).isoformat()
    elif date_range == "all" or date_range == "archive":
        date_from = date_to = ""

    sql = (
        "SELECT r.*, a.internal_name, a.permalink_token, a.automation_mode, a.submit_after_hours "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE a.owner_user_id IS ?"
    )
    params: List[Any] = [access.owner_id(request)]
    if show_archive:
        sql += " AND r.archived_at IS NOT NULL"
    else:
        sql += " AND r.archived_at IS NULL"
    if status != "all":
        sql += " AND r.status = ?"
        params.append(status)
    if apartment_id:
        sql += " AND a.id = ?"
        params.append(apartment_id)
    # A stay counts as inside the window when it overlaps it, so a guest who is
    # in the flat right now still shows under "upcoming".
    if date_from:
        sql += " AND r.date_to >= ?"
        params.append(date_from)
    if date_to:
        if date_range == "past":
            sql += " AND r.date_to <= ?"
        else:
            sql += " AND r.date_from <= ?"
        params.append(date_to)
    total = int(db.query_one(f"SELECT COUNT(*) AS n FROM ({sql})", params)["n"])
    page_count = max(1, (total + RESERVATION_PAGE_SIZE - 1) // RESERVATION_PAGE_SIZE)
    page = max(1, min(_query_int(request, "page") or 1, page_count))
    offset = (page - 1) * RESERVATION_PAGE_SIZE
    sql += " ORDER BY r.date_from ASC, r.date_to ASC, r.id ASC LIMIT ? OFFSET ?"
    reservations = db.query(sql, [*params, RESERVATION_PAGE_SIZE, offset])
    rows = []
    for row in reservations:
        apartment = access.apartment(request, row["apartment_id"])
        progress = reporting.reservation_progress(row)
        rows.append(
            {
                "reservation": row,
                "progress": progress,
                "controls": reporting.send_controls(row, apartment, progress) if apartment else {},
            }
        )
    ready_send_count = reporting.count_sendable_stays([item["reservation"] for item in rows])
    query_params = [(key, value) for key, value in request.query_params.multi_items() if key != "page"]

    def page_url(number: int) -> str:
        return "/reservations?" + urlencode([*query_params, ("page", number)])

    return render(
        request,
        "reservations.html",
        {
            "rows": rows,
            "ready_send_count": ready_send_count,
            "status": status,
            "apartments": access.apartments(request, "id, internal_name"),
            "apartment_id": apartment_id,
            "date_from": date_from,
            "date_to": date_to,
            "date_range": date_range,
            "total": total,
            "page": page,
            "page_count": page_count,
            "page_size": RESERVATION_PAGE_SIZE,
            "previous_page_url": page_url(page - 1) if page > 1 else "",
            "next_page_url": page_url(page + 1) if page < page_count else "",
            "has_any": bool(db.query_one(
                "SELECT 1 AS x FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
                "WHERE a.owner_user_id IS ? LIMIT 1",
                (access.owner_id(request),),
            )),
            "return_to": quote(
                request.url.path + (f"?{request.url.query}" if request.url.query else ""),
                safe="",
            ),
            "show_archive": show_archive,
        },
    )


@router.post("/reservations")
async def reservation_create(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    apartment_id = _form_int(form, "apartment_id")
    date_from = _form_str(form, "date_from")
    date_to = _form_str(form, "date_to")
    if not (apartment_id and date_from and date_to):
        return _back("/reservations", err="Apartment and both dates are required.")
    if not access.apartment(request, apartment_id):
        return _back("/reservations", err="No such apartment.")
    if date_to <= date_from:
        return _back("/reservations", err="The departure date must be after the arrival date.")
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"manual-{db.utcnow()}-{date_from}",
            "date_from": date_from,
            "date_to": date_to,
            "summary": _form_str(form, "summary") or "Manual entry",
            "expected_guests_override": _form_int(form, "expected_guests"),
            "guest_email": _form_str(form, "guest_email"),
            "host_note": _form_str(form, "host_note"),
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )
    return _back(f"/reservations/{reservation_id}", msg="Stay created.")


@router.get("/reservations.csv")
def reservations_export(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    date_from = _query_date(request, "from")
    date_to = _query_date(request, "to")
    if not (date_from and date_to):
        return _back("/reservations", err="Choose a date range for the export.")
    stamp = datetime.now().strftime("%Y%m%d")
    sql, params = stays_import._export_sql(
        date_from=date_from,
        date_to=date_to,
        apartment_id=_query_int(request, "apartment"),
        owner_user_id=access.owner_id(request),
    )
    return StreamingResponse(
        stays_import.iter_export_csv_rows(db.query(sql, params)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="stays-{stamp}.csv"'},
    )

@router.post("/reservations/submit-ready")
async def reservations_submit_ready(request: Request):
    """Send every stay that is ready and allowed to go out now."""
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_str(form, "return_to") or "/reservations"
    reservations = db.query(
        "SELECT r.* FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
        "AND a.archived_at IS NULL AND a.owner_user_id IS ?",
        (access.owner_id(request),),
    )
    sent_stays = 0
    sent_guests = 0
    for reservation in reservations:
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
        if not apartment:
            continue
        progress = reporting.reservation_progress(reservation)
        if not reporting.send_controls(reservation, apartment, progress)["send_enabled"]:
            continue
        guest_ids = [guest["id"] for guest in progress["reportable"] if guest["submit_state"] != reporting.SENT]
        if not guest_ids:
            continue
        results = reporting.submit_for_apartment(
            reservation["apartment_id"],
            only_guest_ids=guest_ids,
            mode="manual_bulk",
            ignore_automation=True,
            verified_by_user_id=access.owner_id(request),
        )
        if not results:
            continue
        batch_sent = sum(r.get("submitted", 0) for r in results)
        if batch_sent:
            sent_stays += 1
            sent_guests += batch_sent
    if not sent_guests:
        return _back(
            return_to,
            err="No stays were ready to send. Complete guest forms for foreign nationals first.",
        )
    return _back(return_to, msg=f"Sent {sent_guests} guest record(s) across {sent_stays} stay(s).")


@router.get("/reservations/{reservation_id}")
def reservation_detail(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = db.query_one(
        "SELECT r.*, a.internal_name, a.permalink_token, a.automation_mode, a.submit_after_hours "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.id = ? AND a.owner_user_id IS ?",
        (reservation_id, access.owner_id(request)),
    )
    if not reservation:
        return _back("/reservations", err="No such stay.")
    progress = reporting.reservation_progress(reservation)
    apartment = access.apartment(request, reservation["apartment_id"])
    send_controls = reporting.send_controls(reservation, apartment, progress) if apartment else {}
    guest_rows = []
    for guest in progress["guests"]:
        guest_rows.append(
            {
                "guest": guest,
                "issues": reporting.guest_issues(guest, reservation),
                "complete": reporting.guest_is_complete(guest, reservation),
                "verified": reporting.guest_identity_verified(guest),
                "has_passport_photo": reporting.guest_has_passport_photo(guest),
                "needs_verification": (
                    validation.guest_is_reportable(guest["nationality"])
                    and not reporting.guest_identity_verified(guest)
                ),
            }
        )
    check_in = validation.parse_iso_date(reservation["date_from"])
    submissions = db.query(
        "SELECT * FROM submission WHERE id IN ("
        "  SELECT DISTINCT submission_id FROM guest WHERE reservation_id = ? AND submission_id IS NOT NULL"
        ") ORDER BY created_at DESC",
        (reservation_id,),
    )
    return render(
        request,
        "reservation_detail.html",
        {
            "reservation": reservation,
            "progress": progress,
            "send_controls": send_controls,
            "guest_rows": guest_rows,
            "check_in": check_in,
            "deadline": deadlines.reporting_deadline(check_in) if check_in else None,
            "urgency_level": deadlines.urgency(check_in) if check_in else "future",
            "submissions": submissions,
            "return_to": _safe_return_to(request, "/reservations"),
            "guest_link": (
                f"{config.PUBLIC_BASE_URL}/l/{reservation['permalink_token']}/{reservation_id}"
            ),
        },
    )


@router.post("/reservations/{reservation_id}")
async def reservation_update(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.reservation(request, reservation_id):
        return _back("/reservations", err="No such stay.")
    form = await request.form()
    payload: Dict[str, Any] = {
        "guest_email": _form_str(form, "guest_email"),
        "host_note": _form_str(form, "host_note"),
        "updated_at": db.utcnow(),
    }
    if "expected_guests_override" in form:
        payload["expected_guests_override"] = _form_int(form, "expected_guests_override")
    status = _form_str(form, "status")
    if status in ("active", "cancelled", "ignored"):
        payload["status"] = status
    db.update("reservation", reservation_id, payload)
    return _back(f"/reservations/{reservation_id}", msg="Saved.")


@router.post("/reservations/{reservation_id}/quick-edit")
async def reservation_quick_edit(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return JSONResponse({"ok": False}, status_code=404)
    form = await request.form()
    payload: Dict[str, Any] = {"updated_at": db.utcnow()}
    if "summary" in form:
        payload["summary"] = _form_str(form, "summary")[:160]
    if "expected_guests_override" in form:
        expected = _form_int(form, "expected_guests_override")
        if expected is not None and not 1 <= expected <= 60:
            return JSONResponse({"ok": False}, status_code=422)
        payload["expected_guests_override"] = expected
    db.update("reservation", reservation_id, payload)
    if request.headers.get("X-Requested-With") == "fetch":
        return JSONResponse({"ok": True})
    return _back(f"/reservations/{reservation_id}", msg="Saved.")


@router.post("/reservations/{reservation_id}/archive")
async def reservation_archive(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err="No such stay.")
    if reservation["archived_at"]:
        return _back(f"/reservations/{reservation_id}", err="Already archived.")
    form = await request.form()
    return_to = _form_return_to(form, _redirect_path_from_referer(request, "/reservations"))
    db.update("reservation", reservation_id, {"archived_at": db.utcnow(), "updated_at": db.utcnow()})
    db.audit("reservation_archived", f"id={reservation_id}")
    lang = host_i18n.lang_from_request(request)
    target = (
        f"/reservations?range=archive&undo_stay={reservation_id}"
        f"&undo_return={quote(return_to, safe='')}"
    )
    return _back(target, msg=host_i18n.translate(lang, "archive.stay_moved"))


@router.post("/reservations/{reservation_id}/unarchive")
async def reservation_unarchive(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/reservations/{reservation_id}")
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err="No such stay.")
    if not reservation["archived_at"]:
        return _back(return_to, err="Not archived.")
    db.update("reservation", reservation_id, {"archived_at": None, "updated_at": db.utcnow()})
    db.audit("reservation_unarchived", f"id={reservation_id}")
    return _back(return_to, msg="Stay restored from archive.")


@router.post("/reservations/{reservation_id}/submit")
async def reservation_submit(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err="No such stay.")
    apartment = access.apartment(request, reservation["apartment_id"])
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress) if apartment else {}
    if not controls.get("send_enabled"):
        return _back(
            f"/reservations/{reservation_id}",
            err=host_i18n.translate(
                host_i18n.lang_from_request(request),
                controls.get("send_hint_key", ""),
            )
            or "This stay cannot be sent right now.",
        )
    form = await request.form()
    # Re-sending an accepted record creates a duplicate, which UbyPort counts
    # against the host and cannot be corrected. The single-guest resend route
    # gates this on an explicit tick; the whole-stay route must not be the
    # cheaper way around it, especially with no CSRF token to lean on.
    allow_resend = bool(form.get("allow_resend"))
    if allow_resend and not form.get("confirm_duplicate"):
        return _back(
            f"/reservations/{reservation_id}",
            err="Confirm you understand the duplicate rules before re-sending accepted records.",
        )
    return_to = _form_str(form, "return_to") or f"/reservations/{reservation_id}"
    guest_ids = [
        guest["id"]
        for guest in db.query("SELECT id FROM guest WHERE reservation_id = ?", (reservation_id,))
    ]
    results = reporting.submit_for_apartment(
        reservation["apartment_id"],
        only_guest_ids=guest_ids,
        mode="manual",
        ignore_automation=True,
        allow_resend=allow_resend,
        verified_by_user_id=access.owner_id(request),
    )
    if not results:
        return _back(
            return_to,
            err="Nothing was sendable: every guest is either incomplete, already reported, or not reportable.",
        )
    first = results[0]
    if first.get("state") == "noop":
        return _back(return_to, err=first.get("error") or "Nothing to send.")
    if first.get("state") == "not_configured":
        return _back(return_to, err=f"UbyPort settings incomplete: {first['error']}")
    if first.get("state") == "transport_error":
        return _back(return_to, err=f"Could not reach UbyPort: {first.get('error')}")
    sent = sum(r.get("submitted", 0) for r in results)
    failed = sum(r.get("failed", 0) + r.get("blocked", 0) for r in results)
    if failed:
        return _back(
            return_to,
            msg=f"{sent} guest(s) accepted.",
            err=f"{failed} guest(s) were rejected - open the Doručenka for details.",
        )
    return _back(return_to, msg=f"{sent} guest(s) reported to UbyPort.")


# --- guests --------------------------------------------------------------

GUEST_TEXT_FIELDS = (
    "surname",
    "first_name",
    "birth_date",
    "nationality",
    "doc_number",
    "visa_number",
    "res_street",
    "res_city",
    "res_country",
    "purpose",
    "note",
)


def _guest_payload(form) -> Dict[str, Any]:
    raw = {field: _form_str(form, field) for field in GUEST_TEXT_FIELDS}
    payload: Dict[str, Any] = dict(validation.normalise_guest(raw, clamp=False))
    payload["stay_from"] = _form_str(form, "stay_from") or None
    payload["stay_to"] = _form_str(form, "stay_to") or None
    return payload


def _guest_signature_from_form(form, existing=None) -> str:
    signature = _form_str(form, "signature")
    if not signature.startswith("data:image/") and existing:
        kept = (existing["signature_png"] or "").strip()
        if kept.startswith("data:image/"):
            return kept
    return signature


def _render_host_guest_form(
    request: Request,
    reservation,
    guest,
    issues,
    *,
    editing: bool,
):
    return render(
        request,
        "guest_form_admin.html",
        {
            "reservation": reservation,
            "guest": guest,
            "issues": issues,
            "editing": editing,
            "countries": codelists.nationality_options("en"),
            "purposes": codelists.purpose_options("en"),
            "has_passport_photo": reporting.guest_has_passport_photo(guest) if guest else False,
            "passport_is_pdf": (
                passport_photos.is_pdf_attachment(int(guest["id"]))
                if guest and reporting.guest_has_passport_photo(guest)
                else False
            ),
            "needs_verification": (
                guest
                and validation.guest_is_reportable(guest["nationality"])
                and not reporting.guest_identity_verified(guest)
            ),
        },
    )


@router.get("/reservations/{reservation_id}/guests/new")
def guest_new(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = db.query_one(
        "SELECT r.*, a.default_purpose, a.internal_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.id = ? AND a.owner_user_id IS ?",
        (reservation_id, access.owner_id(request)),
    )
    if not reservation:
        return _back("/reservations", err="No such stay.")
    return _render_host_guest_form(request, reservation, None, [], editing=False)


@router.post("/reservations/{reservation_id}/guests")
async def guest_create(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err="No such stay.")
    form = await request.form()
    payload = _guest_payload(form)
    signature = _guest_signature_from_form(form)
    preview = {**payload, "signature_png": signature, "entered_by": "host"}
    issues = reporting.guest_issues(preview, reservation)
    if validation.errors_only(issues):
        return _render_host_guest_form(
            request,
            reservation,
            preview,
            issues,
            editing=False,
        )
    now = db.utcnow()
    is_first = not db.query_one("SELECT 1 AS x FROM guest WHERE reservation_id = ?", (reservation_id,))
    identity = {}
    if validation.guest_is_reportable(payload["nationality"]):
        identity = {
            "identity_verified_at": now,
            "identity_verified_by": access.owner_id(request),
        }
    payload.update(
        {
            "reservation_id": reservation_id,
            "is_lead": 1 if is_first else 0,
            "entered_by": "host",
            "signature_png": signature,
            "signed_at": now,
            "filled_at": now,
            "submit_state": (
                reporting.NOT_REQUIRED
                if not validation.guest_is_reportable(payload["nationality"])
                else reporting.PENDING
            ),
            "created_at": now,
            "updated_at": now,
            **identity,
        }
    )
    guest_id = db.insert("guest", payload)
    db.audit("guest_created", f"id={guest_id} reservation={reservation_id} by=host")
    reporting.maybe_submit_after_host_save(reservation["apartment_id"], guest_id)
    return _back(f"/reservations/{reservation_id}", msg="Guest added.")


@router.get("/guests/{guest_id}")
def guest_edit(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err="No such guest.")
    reservation = db.query_one(
        "SELECT r.*, a.default_purpose, a.internal_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (guest["reservation_id"],),
    )
    return _render_host_guest_form(
        request,
        reservation,
        guest,
        reporting.guest_issues(guest, reservation),
        editing=True,
    )


@router.post("/guests/{guest_id}")
async def guest_update(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err="No such guest.")
    reservation = db.query_one(
        "SELECT r.*, a.default_purpose, a.internal_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (guest["reservation_id"],),
    )
    form = await request.form()
    payload = _guest_payload(form)
    signature = _guest_signature_from_form(form, guest)
    preview = {**guest, **payload, "signature_png": signature, "entered_by": "host"}
    issues = reporting.guest_issues(preview, reservation)
    if validation.errors_only(issues):
        return _render_host_guest_form(
            request,
            reservation,
            preview,
            issues,
            editing=True,
        )
    payload["signature_png"] = signature
    if signature.startswith("data:image/") and signature != (guest["signature_png"] or ""):
        payload["signed_at"] = db.utcnow()
    payload["updated_at"] = db.utcnow()
    if validation.guest_is_reportable(payload["nationality"]):
        payload["identity_verified_at"] = db.utcnow()
        payload["identity_verified_by"] = access.owner_id(request)
    if not validation.guest_is_reportable(payload["nationality"]):
        payload["submit_state"] = reporting.NOT_REQUIRED
    elif guest["submit_state"] in (reporting.ERROR, reporting.BLOCKED, reporting.NOT_REQUIRED):
        # Rule 10.4(5): correcting a rejected record must make it sendable again.
        payload["submit_state"] = reporting.PENDING
        payload["last_errors"] = None
    db.update("guest", guest_id, payload)
    db.audit("guest_updated", f"id={guest_id} by=host")
    if reservation:
        reporting.maybe_submit_after_host_save(reservation["apartment_id"], guest_id)
    return _back(f"/guests/{guest_id}", msg="Saved.")


@router.post("/guests/{guest_id}/verify-identity")
async def guest_verify_identity(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err="No such guest.")
    if not validation.guest_is_reportable(guest["nationality"]):
        return _back(f"/guests/{guest_id}", err="Czech guests do not need passport verification.")
    if guest["identity_verified_at"]:
        return _back(f"/guests/{guest_id}", msg="Identity already verified.")
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (guest["reservation_id"],))
    if not reservation:
        return _back("/reservations", err="No such stay.")
    form = await request.form()
    return_to = (form.get("return_to") or f"/guests/{guest_id}").strip()
    if not return_to.startswith("/") or return_to.startswith("//"):
        return_to = f"/guests/{guest_id}"
    owner_id = access.owner_id(request)
    reporting.record_host_identity_confirmation(guest_id, owner_id, on_send=False)
    now = db.utcnow()
    if passport_photos.has_photo(guest_id):
        passport_photos.delete_photo(guest_id)
        db.update(
            "guest",
            guest_id,
            {"passport_photo_at": None, "updated_at": now},
        )
    reporting.maybe_submit_after_verify(reservation["apartment_id"], guest_id)
    return _back(return_to, msg="ID check recorded.")


@router.get("/guests/{guest_id}/passport-photo")
def guest_passport_photo(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest or not reporting.guest_has_passport_photo(guest):
        return Response("Not found.", status_code=404)
    payload = passport_photos.read_photo(guest_id)
    if not payload:
        return Response("Not found.", status_code=404)
    content, media_type = payload
    return Response(
        content,
        media_type=media_type,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/guests/{guest_id}/archive")
async def guest_archive(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/housebook", err="No such guest record.")
    if guest["submit_state"] == reporting.SENT:
        return _back(
            f"/guests/{guest_id}",
            err="This guest was already reported to the police; the record must stay in the house book.",
        )
    if guest["archived_at"]:
        return _back(f"/guests/{guest_id}", err="Already archived.")
    form = await request.form()
    return_to = (form.get("return_to") or "/housebook").strip()
    if not return_to.startswith("/") or return_to.startswith("//"):
        return_to = "/housebook"
    db.update("guest", guest_id, {"archived_at": db.utcnow(), "updated_at": db.utcnow()})
    db.audit("guest_archived", f"id={guest_id}")
    return _back(return_to, msg="House-book entry archived. Restore it from the archive below.")


@router.post("/guests/{guest_id}/unarchive")
async def guest_unarchive(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, "/housebook")
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/housebook", err="No such guest record.")
    if not guest["archived_at"]:
        return _back(return_to, err="Not archived.")
    db.update("guest", guest_id, {"archived_at": None, "updated_at": db.utcnow()})
    db.audit("guest_unarchived", f"id={guest_id}")
    return _back(return_to, msg="House-book entry restored.")


@router.post("/guests/{guest_id}/delete")
def guest_delete(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err="No such guest.")
    if guest["submit_state"] == reporting.SENT:
        return _back(
            f"/guests/{guest_id}",
            err="This guest was already reported to the police; the record is kept for the house book.",
        )
    reservation_id = guest["reservation_id"]
    passport_photos.delete_photo(guest_id)
    db.execute("DELETE FROM guest WHERE id = ?", (guest_id,))
    db.audit("guest_deleted", f"id={guest_id}")
    return _back(f"/reservations/{reservation_id}", msg="Guest removed.")


@router.post("/guests/{guest_id}/resend")
async def guest_resend(guest_id: int, request: Request):
    """Deliberate re-send of one record.

    Kept behind an explicit confirmation because UbyPort treats duplicates as
    uncorrectable errors and repeated unjustified duplicates can cost the host
    their web-service access.
    """
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err="No such guest.")
    form = await request.form()
    if not form.get("confirm_duplicate"):
        return _back(f"/guests/{guest_id}", err="Confirm you understand the duplicate rules first.")
    if reporting.blocked_as_duplicate(guest):
        return _back(
            f"/guests/{guest_id}",
            err=(
                "UbyPort already holds this record, so re-sending cannot be accepted "
                "and would count as another duplicate. The guest is reported - see the "
                "Doručenka."
            ),
        )
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (guest["reservation_id"],))
    results = reporting.submit_for_apartment(
        reservation["apartment_id"],
        only_guest_ids=[guest_id],
        mode="manual_resend",
        ignore_automation=True,
        allow_resend=True,
        verified_by_user_id=access.owner_id(request),
    )
    if not results:
        return _back(f"/guests/{guest_id}", err="Record is not sendable - fix the validation errors first.")
    db.audit("guest_resent", f"id={guest_id}")
    result = results[0]
    if result.get("state") == "transport_error":
        return _back(f"/guests/{guest_id}", err=f"Could not reach UbyPort: {result.get('error')}")
    if result.get("submitted"):
        return _back(f"/guests/{guest_id}", msg="Re-sent and accepted.")
    return _back(f"/guests/{guest_id}", err="Re-sent but UbyPort rejected it again - see the Doručenka.")


@router.get("/guests/{guest_id}/form.pdf")
def guest_form_pdf(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.guest(request, guest_id):
        return _back("/reservations", err="No such guest.")
    try:
        pdf = housebook.registration_form_pdf(guest_id)
    except ValueError:
        return _back("/reservations", err="No such guest.")
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="registration-form-{guest_id}.pdf"'},
    )


# --- submissions ---------------------------------------------------------

@router.get("/submissions/receipts.zip")
def submissions_receipts_zip(request: Request, background_tasks: BackgroundTasks):
    """Bulk-download stored Doručenka PDFs as a zip built on disk."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    date_from = _query_date(request, "from")
    date_to = _query_date(request, "to")
    sql = (
        "SELECT s.* FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE a.owner_user_id IS ? AND s.receipt_pdf IS NOT NULL AND TRIM(s.receipt_pdf) != ''"
    )
    params: List[Any] = [owner_id]
    if date_from:
        sql += " AND date(s.created_at) >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date(s.created_at) <= ?"
        params.append(date_to)
    sql += " ORDER BY s.created_at DESC"
    rows = db.query(sql, params)
    if not rows:
        return _back("/submissions", err="No Doručenka receipts to download yet.")
    if len(rows) > reporting.MAX_RECEIPT_DOWNLOADS:
        return _back(
            "/submissions",
            err=(
                f"Too many receipts ({len(rows)}) for one download. "
                f"Narrow the date filter to {reporting.MAX_RECEIPT_DOWNLOADS} or fewer."
            ),
        )
    import os
    import tempfile

    from starlette.responses import FileResponse

    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        written = reporting.build_receipts_zip(rows, path)
    except Exception:
        os.unlink(path)
        raise
    if not written:
        os.unlink(path)
        return _back("/submissions", err="No Doručenka receipts to download yet.")
    stamp = datetime.now().strftime("%Y%m%d")
    background_tasks.add_task(os.unlink, path)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"dorucenky-{stamp}.zip",
    )


@router.get("/submissions")
def submissions_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = db.query(
        "SELECT s.*, a.internal_name FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE a.owner_user_id IS ? ORDER BY s.created_at DESC LIMIT 200",
        (access.owner_id(request),),
    )
    receipt_count = sum(1 for row in rows if row["receipt_pdf"])
    return render(request, "submissions.html", {"rows": rows, "receipt_count": receipt_count})


@router.get("/submissions/{submission_id}")
def submission_detail(submission_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    submission = db.query_one(
        "SELECT s.*, a.internal_name FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE s.id = ? AND a.owner_user_id IS ?",
        (submission_id, access.owner_id(request)),
    )
    if not submission:
        return _back("/submissions", err="No such submission.")
    guest_ids = json.loads(submission["guest_ids"] or "[]")
    guests = []
    if guest_ids:
        marks = ", ".join("?" for _ in guest_ids)
        guests = db.query(f"SELECT * FROM guest WHERE id IN ({marks})", guest_ids)
    codebook = codelists.error_codebook()
    from ..ubyport import errors as uby_errors

    header_messages = [
        f"{code}: {uby_errors.describe(code, codebook)}"
        for code in uby_errors.split_codes(submission["header_errors"])
    ]
    return render(
        request,
        "submission_detail.html",
        {
            "submission": submission,
            "guests": guests,
            "header_messages": header_messages,
            "record_errors": [
                error for error in json.loads(submission["record_errors"] or "[]")
                if str(error).strip(" ;")
            ],
        },
    )


def _pdf_response(base64_text: Optional[str], filename: str):
    if not base64_text:
        return Response("No document was returned for this submission.", status_code=404,
                        media_type="text/plain")
    try:
        raw = base64.b64decode(base64_text)
    except Exception:
        return Response("Stored document is not valid base64.", status_code=500, media_type="text/plain")
    return Response(
        raw,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submissions/{submission_id}/receipt.pdf")
def submission_receipt(submission_id: int, request: Request):
    """The Doručenka. Rule 10.4(3) and (4): the host must be able to see and save it."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owned = access.submission(request, submission_id)
    row = db.query_one("SELECT receipt_pdf FROM submission WHERE id = ?", (submission_id,)) if owned else None
    return _pdf_response(row["receipt_pdf"] if row else None, f"dorucenka-{submission_id}.pdf")


@router.get("/submissions/{submission_id}/errors.pdf")
def submission_errors(submission_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owned = access.submission(request, submission_id)
    row = db.query_one("SELECT error_pdf FROM submission WHERE id = ?", (submission_id,)) if owned else None
    return _pdf_response(row["error_pdf"] if row else None, f"dorucenka-chyby-{submission_id}.pdf")


@router.get("/submissions/{submission_id}/{which}.xml")
def submission_xml(submission_id: int, which: str, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if which not in ("request", "response"):
        return Response("Unknown document.", status_code=404, media_type="text/plain")
    owned = access.submission(request, submission_id)
    row = (
        db.query_one(f"SELECT {which}_xml AS body FROM submission WHERE id = ?", (submission_id,))
        if owned else None
    )
    return Response((row["body"] if row else "") or "", media_type="application/xml")


# --- house book ----------------------------------------------------------

@router.get("/housebook")
def housebook_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment_id = _query_int(request, "apartment")
    date_from = _query_date(request, "from")
    date_to = _query_date(request, "to")
    owner_user_id = access.owner_id(request)
    rows = housebook.housebook_rows(
        apartment_id, date_from or None, date_to or None, owner_user_id=owner_user_id
    )
    archived_rows = housebook.housebook_archived_rows(
        apartment_id, owner_user_id=owner_user_id
    )
    return render(
        request,
        "housebook.html",
        {
            "rows": rows,
            "archived_rows": archived_rows,
            "columns": housebook.HOUSEBOOK_COLUMNS,
            "apartments": access.apartments(request, "id, internal_name"),
            "apartment_id": apartment_id,
            "date_from": date_from,
            "date_to": date_to,
            "retention_years": housebook.RETENTION_YEARS,
            "max_inspection_pdfs": housebook.MAX_INSPECTION_PDFS,
        },
    )


@router.get("/housebook.csv")
def housebook_download(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    stamp = datetime.now().strftime("%Y%m%d")
    rows = housebook.housebook_rows(
        _query_int(request, "apartment"),
        _query_date(request, "from") or None,
        _query_date(request, "to") or None,
        owner_user_id=access.owner_id(request),
    )
    return StreamingResponse(
        housebook.iter_housebook_csv_rows(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="domovni-kniha-{stamp}.csv"'},
    )


@router.get("/housebook/pdfs.zip")
def housebook_pdfs_download(request: Request, background_tasks: BackgroundTasks):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = housebook.housebook_rows(
        _query_int(request, "apartment"),
        _query_date(request, "from") or None,
        _query_date(request, "to") or None,
        owner_user_id=access.owner_id(request),
    )
    if not rows:
        return _back("/housebook", err="No house-book entries match this filter.")
    if len(rows) > housebook.MAX_INSPECTION_PDFS:
        return _back(
            "/housebook",
            err=(
                f"Too many entries ({len(rows)}) for one download. "
                f"Narrow the date or property filter to {housebook.MAX_INSPECTION_PDFS} or fewer."
            ),
        )
    import os
    import tempfile

    from starlette.responses import FileResponse

    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        housebook.build_housebook_pdfs_zip(rows, path)
    except Exception:
        os.unlink(path)
        raise
    stamp = datetime.now().strftime("%Y%m%d")
    background_tasks.add_task(os.unlink, path)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"domovni-kniha-pdf-{stamp}.zip",
    )


# --- alerts and settings -------------------------------------------------

@router.post("/alerts/{alert_id}/dismiss")
def dismiss_alert(alert_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.alert(request, alert_id):
        return Response("No such alert.", status_code=404)
    alerts.resolve_by_id(alert_id, user_dismissed=True)
    if request.headers.get("x-requested-with") == "fetch":
        return Response(status_code=204)
    return RedirectResponse(_redirect_path_from_referer(request), status_code=303)


ARCHIVED_TYPES = ("all", "stays", "properties", "housebook", "entities")


@router.get("/settings/archived")
def settings_archived_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    item_type = request.query_params.get("type", "all")
    if item_type not in ARCHIVED_TYPES:
        item_type = "all"

    counts = {
        "stays": int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM reservation r "
                "JOIN apartment a ON a.id = r.apartment_id "
                "WHERE r.archived_at IS NOT NULL AND a.owner_user_id IS ?",
                (owner_id,),
            )["n"]
        ),
        "properties": int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM apartment "
                "WHERE archived_at IS NOT NULL AND owner_user_id IS ?",
                (owner_id,),
            )["n"]
        ),
        "housebook": int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM guest g "
                "JOIN reservation r ON r.id = g.reservation_id "
                "JOIN apartment a ON a.id = r.apartment_id "
                "WHERE g.archived_at IS NOT NULL AND a.owner_user_id IS ?",
                (owner_id,),
            )["n"]
        ),
        "entities": int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM legal_entity "
                "WHERE archived_at IS NOT NULL AND owner_user_id IS ?",
                (owner_id,),
            )["n"]
        ),
    }
    counts["all"] = counts["stays"] + counts["properties"] + counts["housebook"] + counts["entities"]

    archived_stays: List[Dict[str, Any]] = []
    archived_properties: List[Dict[str, Any]] = []
    archived_housebook: List[Dict[str, Any]] = []
    archived_entities: List[Dict[str, Any]] = []

    if item_type in ("all", "stays"):
        archived_stays = db.query(
            "SELECT r.*, a.internal_name FROM reservation r "
            "JOIN apartment a ON a.id = r.apartment_id "
            "WHERE r.archived_at IS NOT NULL AND a.owner_user_id IS ? "
            "ORDER BY r.archived_at DESC, r.id DESC",
            (owner_id,),
        )
    if item_type in ("all", "properties"):
        archived_properties = db.query(
            "SELECT a.*, "
            "  (SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = a.id) AS reservations "
            "FROM apartment a "
            "WHERE a.archived_at IS NOT NULL AND a.owner_user_id IS ? "
            "ORDER BY a.archived_at DESC",
            (owner_id,),
        )
    if item_type in ("all", "housebook"):
        archived_housebook = housebook.housebook_archived_rows(owner_user_id=owner_id)
    if item_type in ("all", "entities"):
        archived_entities = db.query(
            "SELECT e.* FROM legal_entity e "
            "WHERE e.archived_at IS NOT NULL AND e.owner_user_id IS ? "
            "ORDER BY e.archived_at DESC",
            (owner_id,),
        )

    return render(
        request,
        "settings_archived.html",
        {
            "item_type": item_type,
            "counts": counts,
            "archived_stays": archived_stays,
            "archived_properties": archived_properties,
            "archived_housebook": archived_housebook,
            "archived_entities": archived_entities,
        },
    )


@router.get("/settings")
def settings_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    return render(
        request,
        "settings.html",
        {
            "endpoint": config.endpoint_for(),
            "codelists": {
                "countries": codelists.last_fetched(codelists.KIND_COUNTRIES),
                "purposes": codelists.last_fetched(codelists.KIND_PURPOSES),
                "errors": codelists.last_fetched(codelists.KIND_ERRORS),
            },
            "audit": db.query(
                "SELECT * FROM audit WHERE owner_user_id IS ? ORDER BY id DESC LIMIT 500",
                (access.owner_id(request),),
            ),
            "audit_count": db.query_one(
                "SELECT COUNT(*) AS n FROM audit WHERE owner_user_id IS ?",
                (access.owner_id(request),),
            )["n"],
            "poll_minutes": config.ICAL_POLL_MINUTES,
            "sweep_minutes": config.SUBMIT_SWEEP_MINUTES,
            "retention_years": housebook.RETENTION_YEARS,
            "retention_cutoff": housebook.retention_cutoff(),
            "expired_records": len(
                housebook.expired_guest_ids(owner_user_id=access.owner_id(request))
            ),
            "entities_without_contact": db.query(
                "SELECT id, name FROM legal_entity "
                "WHERE owner_user_id IS ? AND archived_at IS NULL AND "
                "(contact_email IS NULL OR TRIM(contact_email) = '') ORDER BY name",
                (access.owner_id(request),),
            ),
            "apartments_without_entity": db.query(
                "SELECT id, internal_name FROM apartment "
                "WHERE owner_user_id IS ? AND legal_entity_id IS NULL AND active = 1 "
                "ORDER BY internal_name",
                (access.owner_id(request),),
            ),
            "guest_pin_required": config.GUEST_PIN_REQUIRED,
        },
    )


@router.post("/settings/purge-expired")
def purge_expired_records(request: Request):
    """Storage limitation: delete what the six-year duty no longer covers."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_user_id = access.owner_id(request)
    deleted = housebook.purge_expired(owner_user_id=owner_user_id)
    # A passport image has no six-year basis, so the same button clears the
    # ones left over from stays that ended long ago.
    photos = passport_photos.purge_stale(owner_user_id=owner_user_id)
    parts = []
    if deleted:
        parts.append(f"{deleted} guest record(s) past the retention period")
    if photos:
        parts.append(f"{photos} passport image(s) no longer needed")
    if not parts:
        return _back("/settings", msg="Nothing to delete - no record is past the retention period.")
    return _back("/settings", msg="Deleted " + " and ".join(parts) + ".")
