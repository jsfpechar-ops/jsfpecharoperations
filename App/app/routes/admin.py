"""Host-facing routes: dashboard, apartments, reservations, submissions, exports."""
from __future__ import annotations

import base64
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from .. import (
    alerts,
    auth,
    codelists,
    config,
    db,
    deadlines,
    demo,
    housebook,
    icalsync,
    reporting,
    validation,
)
from ..templating import render
from ..ubyport.client import UbyportError, UbyportTransportError

router = APIRouter()


# --- helpers -------------------------------------------------------------

def _back(path: str, msg: str = "", err: str = "") -> RedirectResponse:
    query = []
    if msg:
        query.append(f"msg={quote(msg)}")
    if err:
        query.append(f"err={quote(err)}")
    suffix = ("?" if "?" not in path else "&") + "&".join(query) if query else ""
    return RedirectResponse(path + suffix, status_code=303)


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


def _form_str(form, key: str, default: str = "") -> str:
    value = form.get(key)
    return (value or default).strip() if isinstance(value, str) else default


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


def dashboard_rows(days_ahead: int = 21, days_back: int = 45) -> List[Dict[str, Any]]:
    """Every stay worth looking at, ordered by how urgent it is."""
    start = (date.today() - timedelta(days=days_back)).isoformat()
    end = (date.today() + timedelta(days=days_ahead)).isoformat()
    rows = db.query(
        "SELECT r.*, a.internal_name, a.permalink_token, a.automation_mode "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status = 'active' AND a.active = 1 AND a.archived_at IS NULL "
        "AND r.date_from BETWEEN ? AND ? "
        "ORDER BY r.date_from",
        (start, end),
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
        out.append(
            {
                "reservation": reservation,
                "progress": progress,
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
    apartment_id = demo.seed()
    if not apartment_id:
        return _back("/", err="Demo data is only available on an empty install in mock mode.")
    return _back("/", msg="Demo property loaded. Use “Clear demo data” on Overview when finished.")


@router.post("/demo/reset")
def reset_demo(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not demo.clear():
        return _back("/", err="The built-in demo dataset was not found.")
    return _back("/", msg="Demo data cleared.")


@router.get("/login")
def login_form(request: Request):
    if not auth.password_is_set():
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", {})


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    if not auth.check_login(_form_str(form, "password")):
        db.audit("login_failed", request.client.host if request.client else "")
        return render(request, "login.html", {"error": "Wrong password."}, status_code=401)
    response = RedirectResponse("/", status_code=303)
    auth.attach_session(response, auth.issue_session())
    db.audit("login")
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    auth.clear_session(response)
    return response


# --- dashboard -----------------------------------------------------------

@router.get("/")
def dashboard(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartments = db.query(
        "SELECT * FROM apartment WHERE archived_at IS NULL ORDER BY internal_name"
    )
    rows = dashboard_rows()
    needs_action = [
        row for row in rows
        if row["progress"]["status"] in ("failed", "incomplete", "ready")
        or (
            row["urgency"] == "overdue"
            and row["progress"]["status"] not in ("reported", "not_required")
        )
    ]
    action_ids = {row["reservation"]["id"] for row in needs_action}
    waiting = [
        row for row in rows
        if row["progress"]["status"] == "awaiting_guest"
        and row["reservation"]["id"] not in action_ids
    ]
    assigned_ids = action_ids | {row["reservation"]["id"] for row in waiting}
    upcoming = [
        row for row in rows
        if row["reservation"]["id"] not in assigned_ids
        and row["progress"]["status"] not in ("reported", "not_required")
    ]
    completed = [
        row for row in rows
        if row["progress"]["status"] in ("reported", "not_required")
    ][:8]
    counts = {
        "attention": len(needs_action),
        "awaiting": len(waiting),
        "ready": sum(1 for r in rows if r["progress"]["status"] == "ready"),
        "overdue": sum(1 for r in rows if r["urgency"] == "overdue"
                       and r["progress"]["status"] not in ("reported", "not_required")),
    }
    setup_warnings = []
    for apartment in apartments:
        issues = validation.errors_only(_apartment_issues(apartment))
        if issues:
            setup_warnings.append({"apartment": apartment, "issues": issues})
    return render(
        request,
        "dashboard.html",
        {
            "rows": rows,
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
            "demo_loaded": any(
                apartment["internal_name"] == "Vinohrady Studio (demo)"
                for apartment in apartments
            ),
        },
    )


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
        "WHERE a.active = 1 AND a.archived_at IS NULL ORDER BY a.internal_name"
    )
    rows = [
        {
            "apartment": apartment,
            "issues": validation.errors_only(_apartment_issues(apartment)),
            "permalink": f"{config.PUBLIC_BASE_URL}/l/{apartment['permalink_token']}",
            "pin": apartment["permalink_pin"] or "",
        }
        for apartment in apartments
    ]
    return render(request, "guest_links.html", {"rows": rows})


# --- legal entities ------------------------------------------------------

@router.get("/entities")
def entities(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = db.query(
        "SELECT e.*, (SELECT COUNT(*) FROM apartment a WHERE a.legal_entity_id = e.id) AS apartments "
        "FROM legal_entity e ORDER BY e.name"
    )
    return render(request, "entities.html", {"entities": rows})


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
    db.insert("legal_entity", payload)
    return _back("/entities", msg=f"Added {payload['name']}.")


@router.post("/entities/{entity_id}")
async def update_entity(entity_id: int, request: Request):
    """These details are what guests see as the data controller, so they have
    to be editable without deleting and recreating the entity."""
    guard = auth.require_login(request)
    if guard:
        return guard
    if not db.query_one("SELECT 1 AS x FROM legal_entity WHERE id = ?", (entity_id,)):
        return _back("/entities", err="No such legal entity.")
    form = await request.form()
    payload = {field: _form_str(form, field) for field in ENTITY_FIELDS}
    if not payload["name"]:
        return _back("/entities", err="Name is required.")
    db.update("legal_entity", entity_id, payload)
    return _back("/entities", msg="Saved.")


@router.post("/entities/{entity_id}/delete")
def delete_entity(entity_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    used = db.query_one("SELECT COUNT(*) AS n FROM apartment WHERE legal_entity_id = ?", (entity_id,))
    if used and used["n"]:
        return _back("/entities", err="Detach the apartments from this entity first.")
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    return _back("/entities", msg="Deleted.")


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
        "WHERE a.archived_at IS NULL ORDER BY a.internal_name"
    )
    archived = db.query(
        "SELECT a.*, e.name AS entity_name, "
        "  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1) AS feeds, "
        "  (SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = a.id AND r.status = 'active') AS reservations "
        "FROM apartment a LEFT JOIN legal_entity e ON e.id = a.legal_entity_id "
        "WHERE a.archived_at IS NOT NULL ORDER BY a.archived_at DESC"
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
    return render(
        request,
        "apartment_form.html",
        {
            "apartment": None,
            "entities": db.query("SELECT * FROM legal_entity ORDER BY name"),
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
    "checkin_info",
    "checkout_info",
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
    password = _form_str(form, "uby_ws_password")
    payload["uby_ws_password_enc"] = db.encrypt_secret(password) if password else None
    apartment_id = db.insert("apartment", payload)
    db.audit("apartment_created", f"id={apartment_id}")
    return _back(f"/apartments/{apartment_id}", msg="Apartment created.")


@router.get("/apartments/{apartment_id}")
def apartment_detail(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    feeds = db.query("SELECT * FROM ical_feed WHERE apartment_id = ? ORDER BY id", (apartment_id,))
    return render(
        request,
        "apartment_form.html",
        {
            "apartment": apartment,
            "entities": db.query("SELECT * FROM legal_entity ORDER BY name"),
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
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    form = await request.form()
    payload = _apartment_payload(form)
    password = _form_str(form, "uby_ws_password")
    if password:
        payload["uby_ws_password_enc"] = db.encrypt_secret(password)
    db.update("apartment", apartment_id, payload)
    db.audit("apartment_updated", f"id={apartment_id}")
    return _back(f"/apartments/{apartment_id}", msg="Saved.")


@router.post("/apartments/{apartment_id}/regenerate-link")
def regenerate_link(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
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
        f"/apartments/{apartment_id}",
        msg="New guest link and PIN generated. Update your automated messages on the booking portals.",
    )


@router.post("/apartments/{apartment_id}/archive")
def archive_apartment(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
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
def unarchive_apartment(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    if not apartment["archived_at"]:
        return _back(f"/apartments/{apartment_id}", err="Not archived.")
    db.update(
        "apartment",
        apartment_id,
        {"archived_at": None, "active": 1},
    )
    db.audit("apartment_unarchived", f"id={apartment_id}")
    return _back(f"/apartments/{apartment_id}", msg="Property restored from archive.")


@router.post("/apartments/{apartment_id}/feeds")
async def add_feed(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    url = _form_str(form, "url")
    if not url.lower().startswith(("http://", "https://")):
        return _back(f"/apartments/{apartment_id}", err="The calendar URL must start with http:// or https://")
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
    feed = db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
    if not feed:
        return _back("/apartments", err="No such calendar.")
    db.execute("DELETE FROM ical_feed WHERE id = ?", (feed_id,))
    return _back(f"/apartments/{feed['apartment_id']}", msg="Calendar removed. Existing stays were kept.")


@router.post("/sync")
def sync_now(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    totals = icalsync.sync_all()
    reporting.check_deadlines()
    return _back(
        "/",
        msg=(
            f"Synced {totals['feeds']} calendar(s): {totals['created']} new, "
            f"{totals['updated']} updated, {totals['cancelled']} cancelled."
        ),
        err="Some calendars could not be read." if totals["errors"] else "",
    )


@router.post("/apartments/{apartment_id}/test-connection")
def test_connection(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
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
        return _back(f"/apartments/{apartment_id}", msg=message)
    except (UbyportTransportError, UbyportError) as exc:
        return _back(f"/apartments/{apartment_id}", err=str(exc))


@router.post("/apartments/{apartment_id}/refresh-codelists")
def refresh_codelists(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return _back("/apartments", err="No such apartment.")
    try:
        written = codelists.refresh_all(reporting.client_for(apartment))
    except (UbyportTransportError, UbyportError) as exc:
        return _back(f"/apartments/{apartment_id}", err=f"Could not refresh code lists: {exc}")
    return _back(
        f"/apartments/{apartment_id}",
        msg=(
            f"Code lists refreshed from UbyPort: {written.get('staty', 0)} countries, "
            f"{written.get('ucely', 0)} purposes, {written.get('chyby', 0)} error codes."
        ),
    )


# --- reservations --------------------------------------------------------

RESERVATION_LIMIT = 500

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
    if date_range not in RESERVATION_RANGES:
        # Explicit dates win; otherwise show what is still ahead, because a
        # list that opens on last winter's bookings is useless.
        date_range = "custom" if (date_from or date_to) else "upcoming"
    if date_range == "upcoming":
        date_from, date_to = today, ""
    elif date_range == "past":
        # Departed stays only — a guest checking in today still belongs under Upcoming.
        date_from, date_to = "", (date.today() - timedelta(days=1)).isoformat()
    elif date_range == "all":
        date_from = date_to = ""

    sql = (
        "SELECT r.*, a.internal_name FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE 1 = 1"
    )
    params: List[Any] = []
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
    sql += f" ORDER BY r.date_from ASC, r.date_to ASC, r.id ASC LIMIT {RESERVATION_LIMIT}"
    reservations = db.query(sql, params)
    rows = [
        {"reservation": row, "progress": reporting.reservation_progress(row)}
        for row in reservations
    ]
    return render(
        request,
        "reservations.html",
        {
            "rows": rows,
            "status": status,
            "apartments": db.query("SELECT id, internal_name FROM apartment ORDER BY internal_name"),
            "apartment_id": apartment_id,
            "date_from": date_from,
            "date_to": date_to,
            "date_range": date_range,
            "truncated": len(rows) >= RESERVATION_LIMIT,
            "limit": RESERVATION_LIMIT,
            "has_any": bool(db.query_one("SELECT 1 AS x FROM reservation LIMIT 1")),
            "return_to": quote(
                request.url.path + (f"?{request.url.query}" if request.url.query else ""),
                safe="",
            ),
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


@router.get("/reservations/{reservation_id}")
def reservation_detail(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = db.query_one(
        "SELECT r.*, a.internal_name, a.permalink_token, a.automation_mode, a.submit_after_hours "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (reservation_id,),
    )
    if not reservation:
        return _back("/reservations", err="No such stay.")
    progress = reporting.reservation_progress(reservation)
    guest_rows = []
    for guest in progress["guests"]:
        guest_rows.append(
            {
                "guest": guest,
                "issues": reporting.guest_issues(guest, reservation),
                "complete": reporting.guest_is_complete(guest, reservation),
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
    form = await request.form()
    payload: Dict[str, Any] = {
        "expected_guests_override": _form_int(form, "expected_guests_override"),
        "guest_email": _form_str(form, "guest_email"),
        "host_note": _form_str(form, "host_note"),
        "updated_at": db.utcnow(),
    }
    status = _form_str(form, "status")
    if status in ("active", "cancelled", "ignored"):
        payload["status"] = status
    db.update("reservation", reservation_id, payload)
    return _back(f"/reservations/{reservation_id}", msg="Saved.")


@router.post("/reservations/{reservation_id}/submit")
async def reservation_submit(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    if not reservation:
        return _back("/reservations", err="No such stay.")
    form = await request.form()
    allow_resend = bool(form.get("allow_resend"))
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
    )
    if not results:
        return _back(
            f"/reservations/{reservation_id}",
            err="Nothing was sendable: every guest is either incomplete, already reported, or not reportable.",
        )
    first = results[0]
    if first.get("state") == "not_configured":
        return _back(f"/reservations/{reservation_id}", err=f"UbyPort settings incomplete: {first['error']}")
    if first.get("state") == "transport_error":
        return _back(f"/reservations/{reservation_id}", err=f"Could not reach UbyPort: {first.get('error')}")
    sent = sum(r.get("submitted", 0) for r in results)
    failed = sum(r.get("failed", 0) + r.get("blocked", 0) for r in results)
    if failed:
        return _back(
            f"/reservations/{reservation_id}",
            msg=f"{sent} guest(s) accepted.",
            err=f"{failed} guest(s) were rejected - open the Doručenka for details.",
        )
    return _back(f"/reservations/{reservation_id}", msg=f"{sent} guest(s) reported to UbyPort.")


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
    payload: Dict[str, Any] = dict(validation.normalise_guest(raw))
    payload["stay_from"] = _form_str(form, "stay_from") or None
    payload["stay_to"] = _form_str(form, "stay_to") or None
    return payload


@router.get("/reservations/{reservation_id}/guests/new")
def guest_new(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = db.query_one(
        "SELECT r.*, a.default_purpose, a.internal_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (reservation_id,),
    )
    if not reservation:
        return _back("/reservations", err="No such stay.")
    return render(
        request,
        "guest_form_admin.html",
        {
            "reservation": reservation,
            "guest": None,
            "issues": [],
            "countries": codelists.nationality_options("en"),
            "purposes": codelists.purpose_options("en"),
        },
    )


@router.post("/reservations/{reservation_id}/guests")
async def guest_create(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    if not reservation:
        return _back("/reservations", err="No such stay.")
    form = await request.form()
    payload = _guest_payload(form)
    now = db.utcnow()
    is_first = not db.query_one("SELECT 1 AS x FROM guest WHERE reservation_id = ?", (reservation_id,))
    payload.update(
        {
            "reservation_id": reservation_id,
            "is_lead": 1 if is_first else 0,
            "entered_by": "host",
            "filled_at": now,
            "submit_state": (
                reporting.NOT_REQUIRED
                if not validation.guest_is_reportable(payload["nationality"])
                else reporting.PENDING
            ),
            "created_at": now,
            "updated_at": now,
        }
    )
    guest_id = db.insert("guest", payload)
    db.audit("guest_created", f"id={guest_id} reservation={reservation_id} by=host")
    return _back(f"/reservations/{reservation_id}", msg="Guest added.")


@router.get("/guests/{guest_id}")
def guest_edit(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if not guest:
        return _back("/reservations", err="No such guest.")
    reservation = db.query_one(
        "SELECT r.*, a.default_purpose, a.internal_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (guest["reservation_id"],),
    )
    return render(
        request,
        "guest_form_admin.html",
        {
            "reservation": reservation,
            "guest": guest,
            "issues": reporting.guest_issues(guest, reservation),
            "countries": codelists.nationality_options("en"),
            "purposes": codelists.purpose_options("en"),
        },
    )


@router.post("/guests/{guest_id}")
async def guest_update(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if not guest:
        return _back("/reservations", err="No such guest.")
    form = await request.form()
    payload = _guest_payload(form)
    payload["updated_at"] = db.utcnow()
    if not validation.guest_is_reportable(payload["nationality"]):
        payload["submit_state"] = reporting.NOT_REQUIRED
    elif guest["submit_state"] in (reporting.ERROR, reporting.BLOCKED, reporting.NOT_REQUIRED):
        # Rule 10.4(5): correcting a rejected record must make it sendable again.
        payload["submit_state"] = reporting.PENDING
        payload["last_errors"] = None
    db.update("guest", guest_id, payload)
    db.audit("guest_updated", f"id={guest_id} by=host")
    return _back(f"/guests/{guest_id}", msg="Saved.")


@router.post("/guests/{guest_id}/delete")
def guest_delete(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if not guest:
        return _back("/reservations", err="No such guest.")
    if guest["submit_state"] == reporting.SENT:
        return _back(
            f"/guests/{guest_id}",
            err="This guest was already reported to the police; the record is kept for the house book.",
        )
    reservation_id = guest["reservation_id"]
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
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if not guest:
        return _back("/reservations", err="No such guest.")
    form = await request.form()
    if not form.get("confirm_duplicate"):
        return _back(f"/guests/{guest_id}", err="Confirm you understand the duplicate rules first.")
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (guest["reservation_id"],))
    results = reporting.submit_for_apartment(
        reservation["apartment_id"],
        only_guest_ids=[guest_id],
        mode="manual_resend",
        ignore_automation=True,
        allow_resend=True,
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

@router.get("/submissions")
def submissions_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = db.query(
        "SELECT s.*, a.internal_name FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "ORDER BY s.created_at DESC LIMIT 200"
    )
    return render(request, "submissions.html", {"rows": rows})


@router.get("/submissions/{submission_id}")
def submission_detail(submission_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    submission = db.query_one(
        "SELECT s.*, a.internal_name FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE s.id = ?",
        (submission_id,),
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
            "record_errors": json.loads(submission["record_errors"] or "[]"),
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
    row = db.query_one("SELECT receipt_pdf FROM submission WHERE id = ?", (submission_id,))
    return _pdf_response(row["receipt_pdf"] if row else None, f"dorucenka-{submission_id}.pdf")


@router.get("/submissions/{submission_id}/errors.pdf")
def submission_errors(submission_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    row = db.query_one("SELECT error_pdf FROM submission WHERE id = ?", (submission_id,))
    return _pdf_response(row["error_pdf"] if row else None, f"dorucenka-chyby-{submission_id}.pdf")


@router.get("/submissions/{submission_id}/{which}.xml")
def submission_xml(submission_id: int, which: str, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if which not in ("request", "response"):
        return Response("Unknown document.", status_code=404, media_type="text/plain")
    row = db.query_one(f"SELECT {which}_xml AS body FROM submission WHERE id = ?", (submission_id,))
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
    rows = housebook.housebook_rows(apartment_id, date_from or None, date_to or None)
    return render(
        request,
        "housebook.html",
        {
            "rows": rows,
            "columns": housebook.HOUSEBOOK_COLUMNS,
            "apartments": db.query("SELECT id, internal_name FROM apartment ORDER BY internal_name"),
            "apartment_id": apartment_id,
            "date_from": date_from,
            "date_to": date_to,
            "retention_years": housebook.RETENTION_YEARS,
        },
    )


@router.post("/housebook/import")
async def housebook_import(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    apartment_id = _form_int(form, "apartment_id")
    upload = form.get("csv_file")
    if not apartment_id:
        return _back("/housebook", err="Choose which property the records belong to.")
    if not upload or not getattr(upload, "filename", ""):
        return _back("/housebook", err="Choose a CSV file to import.")
    content = await upload.read()
    if not content:
        return _back("/housebook", err="The file is empty.")
    result = housebook.import_csv(content, apartment_id)
    if result["imported"]:
        detail = f"Imported {result['imported']} record(s)."
        if result["skipped"]:
            detail += f" Skipped {result['skipped']} row(s)."
        if result["errors"]:
            detail += " " + result["errors"][0]
        return _back("/housebook", msg=detail)
    return _back("/housebook", err=result["errors"][0] if result["errors"] else "Nothing imported.")


@router.get("/housebook.csv")
def housebook_download(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = housebook.housebook_rows(
        _query_int(request, "apartment"),
        _query_date(request, "from") or None,
        _query_date(request, "to") or None,
    )
    stamp = datetime.now().strftime("%Y%m%d")
    return Response(
        housebook.housebook_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="domovni-kniha-{stamp}.csv"'},
    )


# --- alerts and settings -------------------------------------------------

@router.post("/alerts/{alert_id}/dismiss")
def dismiss_alert(alert_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    alerts.resolve_by_id(alert_id)
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(referer, status_code=303)


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
            "password_is_set": auth.password_is_set(),
            "codelists": {
                "countries": codelists.last_fetched(codelists.KIND_COUNTRIES),
                "purposes": codelists.last_fetched(codelists.KIND_PURPOSES),
                "errors": codelists.last_fetched(codelists.KIND_ERRORS),
            },
            "audit": db.query("SELECT * FROM audit ORDER BY id DESC LIMIT 50"),
            "poll_minutes": config.ICAL_POLL_MINUTES,
            "sweep_minutes": config.SUBMIT_SWEEP_MINUTES,
            "retention_years": housebook.RETENTION_YEARS,
            "retention_cutoff": housebook.retention_cutoff(),
            "expired_records": len(housebook.expired_guest_ids()),
            "entities_without_contact": db.query(
                "SELECT id, name FROM legal_entity "
                "WHERE contact_email IS NULL OR TRIM(contact_email) = '' ORDER BY name"
            ),
            "apartments_without_entity": db.query(
                "SELECT id, internal_name FROM apartment "
                "WHERE legal_entity_id IS NULL AND active = 1 ORDER BY internal_name"
            ),
        },
    )


@router.post("/settings/purge-expired")
def purge_expired_records(request: Request):
    """Storage limitation: delete what the six-year duty no longer covers."""
    guard = auth.require_login(request)
    if guard:
        return guard
    deleted = housebook.purge_expired()
    if not deleted:
        return _back("/settings", msg="Nothing to delete - no record is past the retention period.")
    return _back("/settings", msg=f"Deleted {deleted} guest record(s) past the retention period.")


@router.post("/settings/password")
async def change_password(request: Request):
    """Locking the app is optional; this is where a host opts in or out."""
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    new = _form_str(form, "new_password")
    if auth.password_is_set() and not auth.check_login(_form_str(form, "current_password")):
        return _back("/settings", err="Current password is wrong.")
    if not new:
        if not auth.password_is_set():
            return _back("/settings", err="Enter a password, or leave the lock off.")
        if not form.get("confirm_unlock"):
            return _back("/settings", err="Confirm that you want to remove the app lock.")
        auth.clear_password()
        response = _back("/settings", msg="Password removed - the app no longer asks for one.")
        auth.clear_session(response)
        return response
    if len(new) < 10:
        return _back("/settings", err="Use at least 10 characters.")
    auth.set_password(new)
    response = _back("/settings", msg="Password set. You will be asked for it from now on.")
    auth.attach_session(response, auth.issue_session())
    return response
