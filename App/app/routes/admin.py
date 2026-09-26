"""Host-facing pages: legal entities, apartments and feeds, stays and guests.

The routes that answer with JSON, with a download, or that belong to first-run
onboarding live in ``routes/api.py``, ``routes/exports.py`` and
``routes/onboarding.py``. This router includes them, so the host POST
protection and the registered paths are exactly what they were.
"""

from __future__ import annotations

import json
import secrets
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode, urlparse

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

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
    mail,
    passport_photos,
    payments,
    reporting,
    claim,
    security,
    stay_fee,
    validation,
)
from ..templating import render
from ..ubyport.client import UbyportError, UbyportTransportError
from . import admin_accounts, api, exports, onboarding
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import flash_plural as _flash_plural
from .admin_helpers import form_str as _form_str
from .admin_helpers import guest_form_payload as _guest_form_payload
from .admin_helpers import host_text as _host_text
from .admin_helpers import kept_signature as _kept_signature
from .admin_helpers import plural_param as _plural_param
from .admin_helpers import query_date as _query_date
from .admin_helpers import query_int as _query_int

router = APIRouter(dependencies=[Depends(security.protect_host_post)])
router.include_router(admin_accounts.router)
router.include_router(api.router)
router.include_router(onboarding.router)


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
    return security.safe_local_path(request.query_params.get("return_to"), default)


def _apartment_with_secret(apartment) -> Dict[str, Any]:
    data = dict(apartment)
    data["uby_ws_password"] = db.decrypt_secret(apartment["uby_ws_password_enc"])
    return data


def _apartment_issues(apartment) -> List[validation.Issue]:
    return validation.validate_apartment(_apartment_with_secret(apartment))


# The property form has two jobs, so the readiness checklist has two lists. The
# reporting list is exactly the fields validate_apartment() calls errors: the
# stay-fee and invoice fields the two planned features add are optional by
# design and must never be counted here.
_READINESS_REPORT_FIELDS = (
    ("idub", "uby_idub", "ubyport"),
    ("mark", "uby_mark", "ubyport"),
    ("facility_name", "uby_name", "ubyport"),
    ("house_no", "addr_house_no", "address"),
    ("zip", "addr_zip", "address"),
    ("obec", "addr_obec", "address"),
    ("ws_user", "uby_ws_user", "ubyport"),
    ("password", "uby_ws_password", "ubyport"),
)


def _readiness(apartment, entities, issues, has_stays: bool) -> Dict[str, Any]:
    """What still stands between this property and its two jobs.

    Every item carries the anchor of the field that answers it, so the checklist
    is a set of links rather than a paragraph. Reporting items also carry their
    own validation message, which is what the run-on banner used to say.
    """
    by_field: Dict[str, str] = {}
    for issue in validation.errors_only(issues):
        by_field.setdefault(issue.field, issue.message)
    entity = next((e for e in entities if e["id"] == apartment["legal_entity_id"]), None)
    invite = [
        {
            "key": "name",
            "anchor": "basics",
            "done": bool((apartment["internal_name"] or "").strip()),
        },
        {
            "key": "operator",
            "anchor": "basics",
            "done": bool(entity and (entity["contact_email"] or "").strip()),
        },
        {"key": "stays", "anchor": "calendars", "done": has_stays},
    ]
    report = [
        {
            "key": key,
            "anchor": anchor,
            "done": field not in by_field,
            "message": by_field.get(field),
        }
        for key, field, anchor in _READINESS_REPORT_FIELDS
    ]
    return {
        "invite": invite,
        "report": report,
        "invite_ready": all(item["done"] for item in invite),
    }


def _missing_report_labels(request: Request, issues) -> List[str]:
    """The names of the reporting fields this property still lacks.

    The save confirmation lists them by name, in the same order as the
    readiness checklist, so the flash and the checklist on the page agree.
    """
    missing = {issue.field for issue in validation.errors_only(issues)}
    return [
        _host_text(request, f"apartment.form.readiness.item.{key}")
        for key, field, _anchor in _READINESS_REPORT_FIELDS
        if field in missing
    ]


def _form_return_to(form, default: str) -> str:
    return security.safe_local_path(_form_str(form, "return_to"), default)


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


# --- dashboard -----------------------------------------------------------


@router.get("/")
def dashboard(request: Request):
    if not auth.current_user(request):
        return render(
            request,
            "landing.html",
            {"show_nav": False, "open_alerts": []},
        )
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_user_id = access.owner_id(request)
    apartments = access.apartments(request)
    rows = reporting.dashboard_rows(owner_user_id=owner_user_id)
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
    # Without a feed there is nothing to sync, so the page must offer "connect a
    # calendar" instead of "update calendars".
    feed_count = int(
        db.query_one(
            "SELECT COUNT(*) AS n FROM ical_feed f "
            "JOIN apartment a ON a.id = f.apartment_id "
            "WHERE a.owner_user_id IS ? AND a.archived_at IS NULL AND f.active = 1",
            (owner_user_id,),
        )["n"]
    )
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
            "feed_count": feed_count,
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
        "SELECT e.*, (SELECT COUNT(*) FROM apartment a WHERE "
        "a.legal_entity_id = e.id OR a.data_controller_entity_id = e.id) AS apartments "
        "FROM legal_entity e WHERE e.owner_user_id IS ? AND e.archived_at IS NULL ORDER BY e.name",
        (owner_user_id,),
    )
    archived = db.query(
        "SELECT e.*, (SELECT COUNT(*) FROM apartment a WHERE "
        "a.legal_entity_id = e.id OR a.data_controller_entity_id = e.id) AS apartments "
        "FROM legal_entity e WHERE e.owner_user_id IS ? AND e.archived_at IS NOT NULL "
        "ORDER BY e.archived_at DESC",
        (owner_user_id,),
    )
    edit_entity = None
    edit_id = request.query_params.get("edit")
    if edit_id and edit_id.isdigit():
        edit_entity = access.entity(request, int(edit_id))
    return render(
        request,
        "entities.html",
        {"entities": rows, "archived_entities": archived, "edit_entity": edit_entity},
    )


ENTITY_FIELDS = (
    "name",
    "seat",
    "ico",
    "dic",
    "contact_email",
    "contact_phone",
    "bank_account",
    "bic",
    "registry_entry",
    "invoice_prefix",
)

VAT_STATUSES = ("non_payer", "identified", "payer")


def _entity_bank_payload(request: Request, payload: Dict[str, Any], form):
    """Normalise the bank account and invoice settings. Returns an error or None."""
    ico = (payload.get("ico") or "").strip()
    if ico and not validation.ico_ok(ico):
        return _back(
            "/entities",
            err=host_i18n.translate(
                host_i18n.lang_from_request(request), "entities.ico.invalid"
            ),
        )
    if payload.get("bank_account"):
        try:
            payload["bank_account"], payload["iban"] = payments.normalise_account(
                payload["bank_account"]
            )
        except ValueError:
            return _back(
                "/entities",
                err=host_i18n.translate(
                    host_i18n.lang_from_request(request), "entities.bank.invalid"
                ),
            )
    else:
        payload["iban"] = None
    payload["bic"] = (payload.get("bic") or "").replace(" ", "").upper() or None
    vat = _form_str(form, "vat_status")
    payload["vat_status"] = vat if vat in VAT_STATUSES else "non_payer"
    prefix = "".join(ch for ch in _form_str(form, "invoice_prefix").upper() if ch.isalnum())[:6]
    payload["invoice_prefix"] = prefix or None
    next_no = _form_str(form, "invoice_next_number").strip()
    if next_no.isdigit() and int(next_no) > 0:
        payload["invoice_next_number"] = int(next_no)
        payload["invoice_next_number_year"] = date.today().year
    else:
        payload["invoice_next_number"] = None
        payload["invoice_next_number_year"] = None
    due_raw = _form_str(form, "invoice_due_days")
    due = int(due_raw) if due_raw.isdigit() else 14
    payload["invoice_due_days"] = max(0, min(due, 365))
    return None


@router.post("/entities")
async def create_entity(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    payload = {field: _form_str(form, field) for field in ENTITY_FIELDS}
    if not payload["name"]:
        return _back("/entities", err=_flash(request, "flash.error.name_required"))
    bad_bank = _entity_bank_payload(request, payload, form)
    if bad_bank:
        return bad_bank
    payload["created_at"] = db.utcnow()
    payload["owner_user_id"] = access.owner_id(request)
    entity_id = db.insert("legal_entity", payload)
    apartments = access.apartments(request)
    if not apartments:
        return _back(
            f"/apartments/new?legal_entity_id={entity_id}",
            msg=_flash(request, "flash.entities.added_first", name=payload["name"]),
        )
    return _back("/entities", msg=_flash(request, "flash.entities.added", name=payload["name"]))


@router.post("/entities/{entity_id}")
async def update_entity(entity_id: int, request: Request):
    """These details are what guests see as the data controller, so they have
    to be editable without deleting and recreating the entity."""
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.entity(request, entity_id):
        return _back("/entities", err=_flash(request, "flash.error.no_such_entity"))
    form = await request.form()
    payload = {field: _form_str(form, field) for field in ENTITY_FIELDS}
    if not payload["name"]:
        return _back("/entities", err=_flash(request, "flash.error.name_required"))
    bad_bank = _entity_bank_payload(request, payload, form)
    if bad_bank:
        return bad_bank
    db.update("legal_entity", entity_id, payload)
    return _back("/entities", msg=_flash(request, "flash.entities.saved"))


@router.post("/entities/{entity_id}/archive")
def archive_entity(entity_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entity = access.entity(request, entity_id)
    if not entity:
        return _back("/entities", err=_flash(request, "flash.error.no_such_entity"))
    if entity["archived_at"]:
        return _back("/entities", err=_flash(request, "flash.error.already_archived"))
    used = db.query_one(
        "SELECT COUNT(*) AS n FROM apartment WHERE "
        "(legal_entity_id = ? OR data_controller_entity_id = ?) AND owner_user_id IS ?",
        (entity_id, entity_id, access.owner_id(request)),
    )
    if used and used["n"]:
        return _back(
            "/entities",
            err=_flash(request, "flash.error.entity_has_properties"),
        )
    db.update("legal_entity", entity_id, {"archived_at": db.utcnow()})
    db.audit("entity_archived", f"id={entity_id}")
    return _back("/entities", msg=_flash(request, "flash.entities.archived", name=entity["name"]))


@router.post("/entities/{entity_id}/unarchive")
async def unarchive_entity(entity_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/entities?edit={entity_id}")
    entity = access.entity(request, entity_id)
    if not entity:
        return _back("/entities", err=_flash(request, "flash.error.no_such_entity"))
    if not entity["archived_at"]:
        return _back(return_to, err=_flash(request, "flash.error.not_archived"))
    db.update("legal_entity", entity_id, {"archived_at": None})
    db.audit("entity_unarchived", f"id={entity_id}")
    return _back(return_to, msg=_flash(request, "flash.entities.restored", name=entity["name"]))


@router.post("/entities/{entity_id}/delete")
def delete_entity(entity_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entity = access.entity(request, entity_id)
    if not entity:
        return _back("/entities", err=_flash(request, "flash.error.no_such_entity"))
    if not entity["archived_at"]:
        return _back("/entities", err=_flash(request, "flash.error.archive_entity_first"))
    used = db.query_one(
        "SELECT COUNT(*) AS n FROM apartment WHERE "
        "(legal_entity_id = ? OR data_controller_entity_id = ?) AND owner_user_id IS ?",
        (entity_id, entity_id, access.owner_id(request)),
    )
    if used and used["n"]:
        return _back("/entities", err=_flash(request, "flash.error.detach_properties_first"))
    invoiced = db.query_one(
        "SELECT COUNT(*) AS n FROM invoice WHERE legal_entity_id = ?", (entity_id,)
    )
    if invoiced and invoiced["n"]:
        return _back("/entities", err=_flash(request, "flash.error.entity_has_invoices"))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.audit("entity_deleted", f"id={entity_id}")
    return _back("/entities", msg=_flash(request, "flash.entities.deleted"))


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
    return render(
        request,
        "apartments.html",
        {
            "rows": enriched,
            "archived_rows": archived_rows,
            # With no operator there is nothing the property form can attach to,
            # so the empty state names the operator as the first step instead.
            "has_operator": bool(access.entities(request)),
            "last_sync": db.get_setting("last_ical_sync"),
        },
    )


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
    "guest_message",
    "notes",
)


def _apartment_payload(form) -> Dict[str, Any]:
    payload: Dict[str, Any] = {field: _form_str(form, field) for field in APARTMENT_TEXT_FIELDS}
    payload["guest_message"] = payload["guest_message"][:1000]
    payload["uby_mark"] = payload["uby_mark"].upper()
    payload["addr_zip"] = validation.normalise_zip(payload["addr_zip"])
    payload["legal_entity_id"] = _form_int(form, "legal_entity_id")
    payload["data_controller_entity_id"] = _form_int(
        form, "data_controller_entity_id"
    )
    # A brand-new property starts on Manual: a first-time host should see one
    # send themselves before anything leaves for the police.
    mode = _form_str(form, "automation_mode", "manual")
    payload["automation_mode"] = mode if mode in reporting.AUTOMATION_MODES else "manual"
    payload["submit_after_hours"] = _form_int(form, "submit_after_hours") or 24
    payload["permalink_window_days"] = _form_int(form, "permalink_window_days") or 2
    payload["permalink_reachback_days"] = validation.normalise_reachback_days(
        _form_int(form, "permalink_reachback_days")
    )
    policy = _form_str(form, "passport_photo_policy", "off")
    payload["passport_photo_policy"] = (
        policy if policy in ("off", "required_foreign") else "off"
    )
    # The create form does not render the stay-fee fields, so their presence
    # gates the whole block: otherwise a missing checkbox would turn cash off.
    if "stay_fee_rate_czk" in form:
        fee_policy = _form_str(form, "stay_fee_policy", "on")
        payload["stay_fee_policy"] = fee_policy if fee_policy in ("on", "off") else "on"
        rate_raw = _form_str(form, "stay_fee_rate_czk", "0")
        rate = int(rate_raw) if rate_raw.isdigit() else 0
        payload["stay_fee_rate_czk"] = max(0, min(rate, stay_fee.MAX_RATE_CZK))
        link = _form_str(form, "stay_fee_payment_link", "")
        payload["stay_fee_payment_link"] = (
            link if link.startswith("https://") and len(link) <= 300 else None
        )
        payload["stay_fee_cash"] = 1 if form.get("stay_fee_cash") else 0
    purpose = _form_str(form, "default_purpose", validation.DEFAULT_PURPOSE)
    payload["default_purpose"] = purpose if purpose in validation.PURPOSE_CODES else "10"
    payload["active"] = 1 if form.get("active") else 0
    return payload


def _entity_iban(entity_id) -> str:
    if not entity_id:
        return ""
    row = db.query_one("SELECT iban FROM legal_entity WHERE id = ?", (entity_id,))
    return (row["iban"] or "") if row else ""


@router.post("/apartments")
async def apartment_create(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    payload = _apartment_payload(form)
    if not payload["internal_name"]:
        return _back("/apartments/new", err=_flash(request, "flash.error.name_required"))
    payload["permalink_token"] = auth.new_permalink_token()
    payload["permalink_pin"] = auth.new_permalink_pin()
    payload["created_at"] = db.utcnow()
    payload["owner_user_id"] = access.owner_id(request)
    if payload["legal_entity_id"] and not access.entity(request, payload["legal_entity_id"]):
        return _back("/apartments/new", err=_flash(request, "flash.error.no_such_entity"))
    if payload["data_controller_entity_id"] and not access.entity(
        request, payload["data_controller_entity_id"]
    ):
        return _back("/apartments/new", err=_flash(request, "flash.error.no_such_controller"))
    if payload["data_controller_entity_id"] == payload["legal_entity_id"]:
        payload["data_controller_entity_id"] = None
    password = _form_str(form, "uby_ws_password")
    payload["uby_ws_password_enc"] = db.encrypt_secret(password) if password else None
    apartment_id = db.insert("apartment", payload)
    db.audit("apartment_created", f"id={apartment_id}")
    return _back(
        f"/apartments/{apartment_id}#calendars",
        msg=_flash(request, "flash.apartments.created"),
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
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    feeds = db.query("SELECT * FROM ical_feed WHERE apartment_id = ? ORDER BY id", (apartment_id,))
    entities = access.entities(request)
    issues = _apartment_issues(apartment)
    # A connected calendar or a hand-typed stay both mean guests are on their
    # way, which is all the "Ready to invite guests" list asks about.
    has_stays = any(feed["active"] for feed in feeds) or bool(
        db.query_one(
            "SELECT 1 AS present FROM reservation WHERE apartment_id = ? LIMIT 1",
            (apartment_id,),
        )
    )
    return render(
        request,
        "apartment_form.html",
        {
            "apartment": apartment,
            "entities": entities,
            "feeds": feeds,
            "issues": issues,
            "readiness": _readiness(apartment, entities, issues, has_stays),
            "purposes": codelists.purpose_options("en"),
            "permalink": f"{config.PUBLIC_BASE_URL}/l/{apartment['permalink_token']}",
            "pin": apartment["permalink_pin"] or "",
            "has_password": bool(apartment["uby_ws_password_enc"]),
            "entity_iban": _entity_iban(apartment["legal_entity_id"]),
            "codelist_fetched": codelists.last_fetched(codelists.KIND_COUNTRIES),
        },
    )


@router.post("/apartments/{apartment_id}")
async def apartment_update(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    rejected = _save_apartment_form(apartment_id, request, form)
    if rejected:
        return rejected
    # "Saved." said nothing about whether the property can actually report, so
    # the confirmation names what is still missing, or says there is nothing.
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    missing = _missing_report_labels(request, _apartment_issues(apartment))
    if missing:
        msg = _flash(request, "flash.apartments.saved", fields=", ".join(missing))
    else:
        msg = _flash(request, "flash.apartments.saved_ready")
    return _back(_form_return_to(form, f"/apartments/{apartment_id}"), msg=msg)


def _save_apartment_form(apartment_id: int, request: Request, form) -> Optional[Response]:
    """Persist the property form, or return the redirect that rejects it.

    Split out of ``apartment_update`` because the credentials test has to be
    able to save the values the host just typed before it uses them.
    """
    if not access.apartment(request, apartment_id):
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    payload = _apartment_payload(form)
    if payload["legal_entity_id"] and not access.entity(request, payload["legal_entity_id"]):
        return _back(f"/apartments/{apartment_id}", err=_flash(request, "flash.error.no_such_entity"))
    if payload["data_controller_entity_id"] and not access.entity(
        request, payload["data_controller_entity_id"]
    ):
        return _back(f"/apartments/{apartment_id}", err=_flash(request, "flash.error.no_such_controller"))
    if payload["data_controller_entity_id"] == payload["legal_entity_id"]:
        payload["data_controller_entity_id"] = None
    for key in ("automation_mode", "submit_after_hours", "default_purpose"):
        payload.pop(key, None)
    password = _form_str(form, "uby_ws_password")
    if password:
        payload["uby_ws_password_enc"] = db.encrypt_secret(password)
    pin_raw = _form_str(form, "permalink_pin")
    if pin_raw:
        pin = auth.normalise_permalink_pin(pin_raw)
        if not pin or len(pin) != 6:
            return _back(f"/apartments/{apartment_id}", err=_flash(request, "flash.error.pin_six_digits"))
        payload["permalink_pin"] = pin
    db.update("apartment", apartment_id, payload)
    db.audit("apartment_updated", f"id={apartment_id}")
    return None


@router.post("/apartments/{apartment_id}/regenerate-pin")
async def regenerate_pin(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    pin = auth.new_permalink_pin()
    db.update("apartment", apartment_id, {"permalink_pin": pin})
    db.audit("pin_rotated", f"apartment={apartment_id}")
    # The PIN itself stays out of the flash: ?msg= lands in browser history and
    # access logs, and the guest link card already shows the new PIN.
    return _back(
        _form_return_to(form, "/guest-links"),
        msg=_flash(request, "flash.apartments.pin_rotated"),
    )


@router.post("/apartments/{apartment_id}/regenerate-link")
async def regenerate_link(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
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
        msg=_flash(request, "flash.apartments.guest_link"),
    )


UBYPORT_TEXT_FIELDS = (
    "uby_idub",
    "uby_mark",
    "uby_name",
    "uby_contact",
    "uby_ws_user",
)

# The property form posts these; the bare test button posts none of them. That
# is how the credentials test tells "test what I typed" from "test what is
# saved" without a second route.
UBYPORT_CREDENTIAL_FIELDS = UBYPORT_TEXT_FIELDS + ("uby_ws_password",)


def _posted_credentials(form) -> bool:
    return any(_form_str(form, field) for field in UBYPORT_CREDENTIAL_FIELDS)


def _automation_payload(form) -> Dict[str, Any]:
    payload: Dict[str, Any] = {field: _form_str(form, field) for field in UBYPORT_TEXT_FIELDS}
    payload["uby_mark"] = payload["uby_mark"].upper()
    mode = _form_str(form, "automation_mode", "scheduled")
    payload["automation_mode"] = mode if mode in reporting.AUTOMATION_MODES else "scheduled"
    payload["submit_after_hours"] = _form_int(form, "submit_after_hours") or 24
    purpose = _form_str(form, "default_purpose", validation.DEFAULT_PURPOSE)
    payload["default_purpose"] = purpose if purpose in validation.PURPOSE_CODES else "10"
    return payload


# What the property form calls each field the automation card can report as
# missing. The anchor is the field's own id on that page, so the link lands on
# the input the host has to fill in.
_APARTMENT_FIELD_LABELS: Dict[str, Optional[str]] = {
    "uby_idub": None,
    "uby_mark": "apartment.form.ubyport.mark_label",
    "uby_name": "automation.facility_name",
    "uby_contact": "automation.contact",
    "uby_ws_user": "automation.login",
    "uby_ws_password": "automation.password",
    "addr_okres": "apartment.form.addr.okres",
    "addr_obec": "apartment.form.addr.obec",
    "addr_obec_cast": "apartment.form.addr.obec_cast",
    "addr_street": "apartment.form.addr.street",
    "addr_house_no": "apartment.form.addr.house_no",
    "addr_orient_no": "apartment.form.addr.orient_no",
    "addr_zip": "apartment.form.addr.zip",
    "legal_entity_id": "apartment.form.entity.label",
}

# The two labels that read the same in both languages, so they need no key.
_APARTMENT_FIELD_LITERALS = {"uby_idub": "IDUB"}


def _missing_fields(issues: List[validation.Issue]) -> List[Dict[str, str]]:
    """The validation issues as links the host can act on.

    One entry per field: a name that is both empty and too long is still one
    thing to go and fix.
    """
    missing: List[Dict[str, str]] = []
    for issue in issues:
        if any(item["field"] == issue.field for item in missing):
            continue
        missing.append(
            {
                "field": issue.field,
                "label_key": _APARTMENT_FIELD_LABELS.get(issue.field) or "",
                "label": _APARTMENT_FIELD_LITERALS.get(issue.field, issue.field),
            }
        )
    return missing


def _save_automation_form(apartment_id: int, form) -> None:
    """Persist the automation card.

    Split out of ``automation_update`` because the credentials test on this page
    has to save what the host just typed before it uses it. It is a *different*
    payload from the property form's: the card posts no name, address or entity,
    so saving it through ``_apartment_payload`` would blank them.
    """
    payload = _automation_payload(form)
    password = _form_str(form, "uby_ws_password")
    if password:
        payload["uby_ws_password_enc"] = db.encrypt_secret(password)
    db.update("apartment", apartment_id, payload)
    db.audit("automation_updated", f"id={apartment_id} mode={payload['automation_mode']}")


@router.get("/automation")
def automation_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartments = access.apartments(request)
    rows = []
    for apartment in apartments:
        issues = validation.errors_only(_apartment_issues(apartment))
        rows.append(
            {
                "apartment": apartment,
                "issues": issues,
                "missing": _missing_fields(issues),
                "has_password": bool(apartment["uby_ws_password_enc"]),
            }
        )
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
        return _back("/automation", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    _save_automation_form(apartment_id, form)
    return _back(
        _form_return_to(form, f"/automation#apartment-{apartment_id}"),
        msg=_flash(request, "flash.apartments.settings_saved", name=apartment["internal_name"]),
    )


@router.post("/apartments/{apartment_id}/archive")
def archive_apartment(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    if apartment["archived_at"]:
        return _back(f"/apartments/{apartment_id}", err=_flash(request, "flash.error.already_archived"))
    db.update(
        "apartment",
        apartment_id,
        {"archived_at": db.utcnow(), "active": 0},
    )
    db.audit("apartment_archived", f"id={apartment_id}")
    return _back("/apartments", msg=_flash(request, "flash.apartments.archived", name=apartment["internal_name"]))


@router.post("/apartments/{apartment_id}/unarchive")
async def unarchive_apartment(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/apartments/{apartment_id}")
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    if not apartment["archived_at"]:
        return _back(return_to, err=_flash(request, "flash.error.not_archived"))
    db.update(
        "apartment",
        apartment_id,
        {"archived_at": None, "active": 1},
    )
    db.audit("apartment_unarchived", f"id={apartment_id}")
    return _back(return_to, msg=_flash(request, "flash.apartments.restored"))


@router.post("/apartments/{apartment_id}/feeds")
async def add_feed(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.apartment(request, apartment_id):
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    url = _form_str(form, "url")
    try:
        from ..feed_url import FeedUrlError, validate_calendar_url

        url = validate_calendar_url(url)
    except FeedUrlError as exc:
        return _back(f"/apartments/{apartment_id}", err=_flash(request, exc.key))
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
        return _back(f"/apartments/{apartment_id}", err=_flash(request, "flash.error.feed_added_unreadable"))
    return _back(
        f"/apartments/{apartment_id}",
        msg=_flash_plural(request, "flash.feeds.added", totals["created"]),
    )


@router.post("/feeds/{feed_id}/delete")
def delete_feed(feed_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    feed = access.feed(request, feed_id)
    if not feed:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_calendar"))
    db.execute("DELETE FROM ical_feed WHERE id = ?", (feed_id,))
    return _back(f"/apartments/{feed['apartment_id']}", msg=_flash(request, "flash.feeds.removed"))


@router.post("/sync")
async def sync_now(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, "/")
    owner_user_id = access.owner_id(request)
    totals = icalsync.sync_all(owner_user_id=owner_user_id)
    reporting.check_deadlines(owner_user_id=owner_user_id)
    return _back(
        return_to,
        msg=(
            _flash_plural(
                request,
                "flash.feeds.synced",
                totals["feeds"],
                created=totals["created"],
                updated=totals["updated"],
                cancelled=totals["cancelled"],
            )
        ),
        err=_flash(request, "flash.error.feeds_unreadable") if totals["errors"] else "",
    )


@router.post("/apartments/{apartment_id}/test-connection")
async def test_connection(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/apartments/{apartment_id}")
    # A host pastes the credentials from the police letter and clicks the test.
    # Testing the saved values while the typed ones sat in the form was a
    # silent data loss, so the typed values are saved first and then tested.
    if _form_str(form, "form_source") == "automation":
        # The automation card posts only its own fields, so it has to be saved
        # through its own payload; the property payload would blank the rest.
        if access.apartment(request, apartment_id):
            _save_automation_form(apartment_id, form)
    elif _posted_credentials(form):
        rejected = _save_apartment_form(apartment_id, request, form)
        if rejected:
            return rejected
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    client = reporting.client_for(apartment)
    try:
        available = client.test_availability()
        limit = client.max_batch_size()
    except (UbyportTransportError, UbyportError) as exc:
        db.audit(
            "ubyport_connection_failed",
            f"apartment={apartment_id} endpoint={client.endpoint} error={exc}",
        )
        return _back(return_to, err=_flash(request, "flash.error.connection_failed"))
    # The endpoint and the batch size are developer detail: the host only needs
    # to know the login worked, so the numbers go to the activity log.
    db.audit(
        "ubyport_connection_ok",
        f"apartment={apartment_id} endpoint={client.endpoint} "
        f"available={available} max_batch={limit}",
    )
    return _back(return_to, msg=_flash(request, "flash.apartments.connection_ok"))


@router.post("/apartments/{apartment_id}/refresh-codelists")
async def refresh_codelists(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/apartments/{apartment_id}")
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    try:
        written = codelists.refresh_all(reporting.client_for(apartment))
    except (UbyportTransportError, UbyportError):
        return _back(return_to, err=_flash(request, "flash.error.codelists_refresh"))
    return _back(
        return_to,
        msg=(
            _flash(
                request,
                "flash.apartments.codelists_refreshed",
                countries=written.get("staty", 0),
                purposes=written.get("ucely", 0),
                errors=written.get("chyby", 0),
            )
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
                # The bulk action only reaches stays in a live apartment, so the
                # count has to ignore the rest even though their row is listed.
                "apartment_active": bool(apartment and apartment["active"]),
            }
        )
    ready_send_count = sum(
        1 for item in rows if item["controls"].get("send_enabled") and item["apartment_active"]
    )
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
            # Without a feed there is nothing to sync, so an empty list offers
            # "connect a calendar" rather than sending the host to the properties.
            "feed_count": int(
                db.query_one(
                    "SELECT COUNT(*) AS n FROM ical_feed f "
                    "JOIN apartment a ON a.id = f.apartment_id "
                    "WHERE a.owner_user_id IS ? AND a.archived_at IS NULL AND f.active = 1",
                    (access.owner_id(request),),
                )["n"]
            ),
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
        return _back("/reservations", err=_flash(request, "flash.error.stay_dates_required"))
    if not access.apartment(request, apartment_id):
        return _back("/reservations", err=_flash(request, "flash.error.no_such_apartment"))
    if date_to <= date_from:
        return _back("/reservations", err=_flash(request, "flash.error.dates_order"))
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            # A manual stay has no iCal uid to inherit. The old
            # f"manual-{db.utcnow()}-{date_from}" had one-second resolution, so a
            # double-click on "Create stay" hit the UNIQUE index and the second
            # request died with a 500 after the first had already created it.
            "uid": f"manual-{secrets.token_hex(8)}",
            "date_from": date_from,
            "date_to": date_to,
            "summary": _form_str(form, "summary") or None,
            "expected_guests_override": _form_int(form, "expected_guests"),
            "guest_email": _form_str(form, "guest_email"),
            "host_note": _form_str(form, "host_note"),
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )
    return _back(f"/reservations/{reservation_id}", msg=_flash(request, "flash.reservations.created"))


# --- exports -------------------------------------------------------------
# /reservations.csv and /submissions/receipts.zip are literal siblings of the
# int-typed /reservations/{id} and /submissions/{id} routes, so the export
# router has to be included before those are declared.
router.include_router(exports.router)


@router.post("/reservations/submit-ready")
async def reservations_submit_ready(request: Request):
    """Send every stay that is ready and allowed to go out now."""
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = security.safe_local_path(_form_str(form, "return_to"), "/reservations")
    reservations = db.query(
        "SELECT r.* FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
        "AND a.archived_at IS NULL AND a.owner_user_id IS ?",
        (access.owner_id(request),),
    )
    sent_stays = 0
    sent_guests = 0
    for reservation in reservations:
        apartment = access.apartment_for_reservation(reservation, access.owner_id(request))
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
            err=_flash(request, "flash.error.nothing_ready"),
        )
    return _back(
        return_to,
        msg=_flash_plural(
            request,
            "flash.reservations.sent",
            sent_guests,
            guests=sent_guests,
            stays=_plural_param(request, "flash.reservations.sent.stays", sent_stays),
        ),
    )


@router.get("/reservations/{reservation_id}")
def reservation_detail(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(
        request,
        reservation_id,
        "r.*, a.internal_name, a.permalink_token, a.automation_mode, a.submit_after_hours",
    )
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
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
    check_in = reporting.reservation_deadline_anchor(reservation)
    submissions = db.query(
        # The stay's report list renders four columns; the envelope and the
        # stored receipts are the bulk of the row and neither is shown.
        "SELECT id, created_at, state, pseudo_stamp, "
        "       (receipt_pdf IS NOT NULL AND TRIM(receipt_pdf) != '') AS has_receipt "
        "FROM submission WHERE id IN ("
        "  SELECT DISTINCT submission_id FROM guest WHERE reservation_id = ? AND submission_id IS NOT NULL"
        ") AND apartment_id = ? ORDER BY created_at DESC",
        (reservation_id, reservation["apartment_id"]),
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
            "stay_claim": claim.ensure_row(reservation_id),
            "stay_fee": stay_fee.stay_summary(reservation, apartment),
            "stay_fee_names": {
                g["id"]: f"{g['first_name'] or ''} {g['surname'] or ''}".strip()
                for g in progress["guests"]
            },
            "stay_fee_expected": reporting.expected_guest_count(reservation),
            "stay_invoices": db.query(
                "SELECT * FROM invoice WHERE reservation_id = ? AND owner_user_id IS ? "
                "ORDER BY id DESC",
                (reservation_id, access.owner_id(request)),
            ),
        },
    )


@router.post("/reservations/{reservation_id}")
async def reservation_update(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.reservation(request, reservation_id):
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
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
    if payload.get("status") in ("cancelled", "ignored"):
        row = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
        if row:
            claim.expire_on_cancel(row)
    else:
        current = db.query_one(
            "SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,)
        )
        if current:
            reporting.submit_stay_if_complete(
                current["apartment_id"], reservation_id
            )
    return _back(
        f"/reservations/{reservation_id}", msg=_flash(request, "flash.reservations.saved")
    )


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
    reporting.submit_stay_if_complete(
        reservation["apartment_id"], reservation_id
    )
    if request.headers.get("X-Requested-With") == "fetch":
        return JSONResponse({"ok": True})
    return _back(
        f"/reservations/{reservation_id}", msg=_flash(request, "flash.reservations.saved")
    )


@router.post("/reservations/{reservation_id}/archive")
async def reservation_archive(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    if reservation["archived_at"]:
        return _back(f"/reservations/{reservation_id}", err=_flash(request, "flash.error.already_archived"))
    form = await request.form()
    return_to = _form_return_to(form, _redirect_path_from_referer(request, "/reservations"))
    db.update("reservation", reservation_id, {"archived_at": db.utcnow(), "updated_at": db.utcnow()})
    db.audit("reservation_archived", f"id={reservation_id}")
    target = (
        f"/reservations?range=archive&undo_stay={reservation_id}"
        f"&undo_return={quote(return_to, safe='')}"
    )
    return _back(target, msg=_flash(request, "archive.stay_moved"))


@router.post("/reservations/{reservation_id}/unarchive")
async def reservation_unarchive(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, f"/reservations/{reservation_id}")
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    if not reservation["archived_at"]:
        return _back(return_to, err=_flash(request, "flash.error.not_archived"))
    db.update("reservation", reservation_id, {"archived_at": None, "updated_at": db.utcnow()})
    db.audit("reservation_unarchived", f"id={reservation_id}")
    return _back(return_to, msg=_flash(request, "flash.reservations.restored"))


@router.post("/reservations/{reservation_id}/reopen-guest")
async def reservation_reopen_guest(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    claim.reopen_guest_access(reservation_id)
    db.audit("guest_access_reopened", f"reservation={reservation_id}")
    return _back(f"/reservations/{reservation_id}", msg=_flash(request, "flash.reservations.access_reopened"))


@router.post("/reservations/{reservation_id}/release-claim")
async def reservation_release_claim(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    claim.release(reservation_id)
    db.audit("guest_claim_released", f"reservation={reservation_id}")
    return _back(f"/reservations/{reservation_id}", msg=_flash(request, "flash.reservations.claim_released"))


@router.post("/reservations/{reservation_id}/submit")
async def reservation_submit(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    apartment = access.apartment(request, reservation["apartment_id"])
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress) if apartment else {}
    if not controls.get("send_enabled"):
        return _back(
            f"/reservations/{reservation_id}",
            err=_flash(
                request,
                controls.get("send_hint_key") or "flash.error.not_sendable",
            ),
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
            err=_flash(request, "flash.error.confirm_duplicate_resend"),
        )
    return_to = security.safe_local_path(
        _form_str(form, "return_to"), f"/reservations/{reservation_id}"
    )
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
            return_to,
            err=_flash(request, "flash.error.nothing_sendable"),
        )
    first = results[0]
    if first.get("state") == "noop":
        return _back(
            return_to,
            err=_flash(request, first.get("error_key") or "flash.error.nothing_to_send"),
        )
    if first.get("state") == "not_configured":
        # The list of missing fields is on the property page, already in the
        # host's language; repeating it here in English would undo UX-35.
        return _back(return_to, err=_flash(request, "flash.error.ubyport_not_configured"))
    if first.get("state") == "transport_error":
        db.audit(
            "ubyport_send_failed",
            f"apartment={reservation['apartment_id']} error={first.get('error')}",
        )
        return _back(return_to, err=_flash(request, "flash.error.ubyport_unreachable"))
    sent = sum(r.get("submitted", 0) for r in results)
    failed = sum(r.get("failed", 0) + r.get("blocked", 0) for r in results)
    if failed:
        return _back(
            return_to,
            msg=_flash_plural(request, "flash.reservations.accepted", sent),
            err=_flash_plural(request, "flash.error.rejected", failed),
        )
    return _back(
        return_to, msg=_flash_plural(request, "flash.reservations.reported", sent)
    )


# --- guests --------------------------------------------------------------

def _guest_payload(form) -> Dict[str, Any]:
    payload: Dict[str, Any] = dict(_guest_form_payload(form))
    payload["stay_from"] = _form_str(form, "stay_from") or None
    payload["stay_to"] = _form_str(form, "stay_to") or None
    doc_type = _form_str(form, "doc_type")
    payload["doc_type"] = doc_type if doc_type in validation.DOC_TYPES else None
    return payload


def _guest_signature_from_form(form, existing=None) -> str:
    stored = existing["signature_png"] if existing else None
    return _kept_signature(_form_str(form, "signature"), stored)


def _signature_for_display(guest) -> str:
    """What the hidden signature field may post back, if anything.

    [F33]: a row can hold a value the save paths refuse (one filed before the
    validator existed, or a preview of a rejected submit). Handing it back would
    only re-submit it, so it is shown as blank - which means "keep what is
    stored".
    """
    value = (guest["signature_png"] or "") if guest else ""
    return value if validation.is_valid_signature(value) else ""


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
            "signature_value": _signature_for_display(guest),
            "countries": codelists.nationality_options("en"),
            "purposes": codelists.purpose_options("en"),
            "doc_types": validation.DOC_TYPES,
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
    reservation = access.reservation(
        request, reservation_id, "r.*, a.default_purpose, a.internal_name"
    )
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    return _render_host_guest_form(request, reservation, None, [], editing=False)


@router.post("/reservations/{reservation_id}/guests")
async def guest_create(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
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
    stay_fee.snapshot_rate(reservation_id)
    reporting.submit_stay_if_complete(reservation["apartment_id"], reservation_id)
    return _back(f"/reservations/{reservation_id}", msg=_flash(request, "flash.guests.added"))


@router.get("/guests/{guest_id}")
def guest_edit(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
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
        return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
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
        # The retry budget restarts too, or a record the sweep had given up on
        # would stay given up on even after the host fixed what was wrong.
        payload["submit_attempts"] = 0
    db.update("guest", guest_id, payload)
    db.audit("guest_updated", f"id={guest_id} by=host")
    stay_fee.snapshot_rate(guest["reservation_id"])
    if reservation:
        reporting.clear_stuck_alert_if_recovered(reservation["id"])
        reporting.submit_stay_if_complete(reservation["apartment_id"], reservation["id"])
    # "Saved." left the host guessing how far the stay had got. The count is
    # read back after the update, and a stay with no declared guest count has
    # nothing to count against, so it gets the plain confirmation.
    progress = reporting.reservation_progress(reservation) if reservation else None
    if progress and progress["expected"]:
        msg = _flash(
            request,
            "flash.guests.saved",
            filled=progress["filled"],
            expected=progress["expected"],
        )
    else:
        msg = _flash(request, "flash.guests.saved_plain")
    return _back(f"/guests/{guest_id}", msg=msg)


@router.post("/guests/{guest_id}/stay-fee")
async def guest_stay_fee_decision(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
    form = await request.form()
    decision = _form_str(form, "decision")
    reason = _form_str(form, "reason")[:120]
    if decision not in ("", "exempt", "charge"):
        decision = ""
    if decision == "exempt" and len(reason.strip()) < 3:
        return _back(
            f"/reservations/{guest['reservation_id']}#stay-fee",
            err=host_i18n.translate(
                host_i18n.lang_from_request(request), "stay.fee.reason_required"
            ),
        )
    db.update(
        "guest",
        guest_id,
        {
            "fee_host_decision": decision or None,
            "fee_host_reason": reason or None,
            "updated_at": db.utcnow(),
        },
    )
    db.audit(
        "stay_fee_decision",
        f"guest={guest_id} decision={decision or 'auto'} reason={reason}",
    )
    return _back(
        f"/reservations/{guest['reservation_id']}#stay-fee",
        msg=_flash(request, "flash.stay_fee.saved"),
    )


@router.post("/reservations/{reservation_id}/stay-fee/paid")
async def reservation_stay_fee_paid(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation = access.reservation(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    apartment = access.apartment(request, reservation["apartment_id"])
    form = await request.form()
    action = _form_str(form, "action")
    if action == "paid":
        summary = stay_fee.stay_summary(reservation, apartment)
        db.update(
            "reservation",
            reservation_id,
            {
                "stay_fee_paid_at": db.utcnow(),
                "stay_fee_paid_amount_czk": summary["total_czk"] if summary else 0,
            },
        )
    else:
        db.update(
            "reservation",
            reservation_id,
            {"stay_fee_paid_at": None, "stay_fee_paid_amount_czk": None},
        )
    db.audit(
        "stay_fee_paid" if action == "paid" else "stay_fee_unpaid",
        f"reservation={reservation_id}",
    )
    return _back(
        f"/reservations/{reservation_id}#stay-fee",
        msg=_flash(request, "flash.stay_fee.saved"),
    )


def _shift_month(month: str, delta: int) -> str:
    year, mon = int(month[:4]), int(month[5:7])
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _month_param(request: Request) -> str:
    today = claim.prague_today()
    month = request.query_params.get("month") or today.strftime("%Y-%m")
    try:
        stay_fee.month_bounds(month)
    except ValueError:
        month = today.strftime("%Y-%m")
    return month


@router.get("/stay-fees")
def stay_fees_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    month = _month_param(request)
    rows = stay_fee.month_stays(access.owner_id(request), month)
    totals = {
        "charged_people": sum(r["charged_people"] for r in rows),
        "free_people": sum(r["free_people"] for r in rows),
        "charged_nights": sum(r["charged_nights"] for r in rows),
        "free_nights": sum(r["free_nights"] for r in rows),
        "total_czk": sum(r["summary"]["total_czk"] for r in rows),
        "paid_czk": sum(
            r["summary"]["total_czk"] for r in rows if r["summary"]["paid_at"]
        ),
    }
    return render(
        request,
        "stay_fees.html",
        {
            "nav": "stay_fees",
            "month": month,
            "prev_month": _shift_month(month, -1),
            "next_month": _shift_month(month, 1),
            "rows": rows,
            "totals": totals,
        },
    )


@router.get("/stay-fees.csv")
def stay_fees_csv(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    month = _month_param(request)
    payload = stay_fee.export_csv(access.owner_id(request), month)
    return Response(
        payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="poplatek-z-pobytu-{month}.csv"'
        },
    )


@router.post("/guests/{guest_id}/verify-identity")
async def guest_verify_identity(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
    if not validation.guest_is_reportable(guest["nationality"]):
        return _back(f"/guests/{guest_id}", err=_flash(request, "flash.error.czech_no_verification"))
    if guest["identity_verified_at"]:
        return _back(f"/guests/{guest_id}", msg=_flash(request, "flash.guests.identity_verified"))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (guest["reservation_id"],))
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    form = await request.form()
    return_to = security.safe_local_path(
        str(form.get("return_to") or ""), f"/guests/{guest_id}"
    )
    owner_id = access.owner_id(request)
    reporting.record_host_identity_confirmation(guest_id, owner_id)
    now = db.utcnow()
    if passport_photos.has_photo(guest_id):
        passport_photos.delete_photo(guest_id)
        db.update(
            "guest",
            guest_id,
            {"passport_photo_at": None, "updated_at": now},
        )
    return _back(return_to, msg=_flash(request, "flash.guests.id_check_recorded"))


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
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


@router.post("/guests/{guest_id}/archive")
async def guest_archive(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/housebook", err=_flash(request, "flash.error.no_such_housebook_guest"))
    if guest["submit_state"] == reporting.SENT:
        return _back(
            f"/guests/{guest_id}",
            err=_flash(request, "flash.error.reported_kept"),
        )
    if guest["archived_at"]:
        return _back(f"/guests/{guest_id}", err=_flash(request, "flash.error.already_archived"))
    form = await request.form()
    return_to = security.safe_local_path(str(form.get("return_to") or ""), "/housebook")
    # Archiving hides the record from the house book but keeps it in the
    # database, so the scan of the passport it was checked against must go the
    # same way it does on delete: the photo's only purpose was that check.
    passport_photos.delete_photo(guest_id)
    db.update("guest", guest_id, {"archived_at": db.utcnow(), "updated_at": db.utcnow()})
    db.audit("guest_archived", f"id={guest_id}")
    reservation = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?",
        (guest["reservation_id"],),
    )
    if reservation:
        reporting.submit_stay_if_complete(
            reservation["apartment_id"], guest["reservation_id"]
        )
    return _back(return_to, msg=_flash(request, "flash.housebook.archived"))


@router.post("/guests/{guest_id}/unarchive")
async def guest_unarchive(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    return_to = _form_return_to(form, "/housebook")
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/housebook", err=_flash(request, "flash.error.no_such_housebook_guest"))
    if not guest["archived_at"]:
        return _back(return_to, err=_flash(request, "flash.error.not_archived"))
    db.update("guest", guest_id, {"archived_at": None, "updated_at": db.utcnow()})
    db.audit("guest_unarchived", f"id={guest_id}")
    reservation = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?",
        (guest["reservation_id"],),
    )
    if reservation:
        reporting.submit_stay_if_complete(
            reservation["apartment_id"], guest["reservation_id"]
        )
    return _back(return_to, msg=_flash(request, "flash.housebook.restored"))


@router.post("/guests/{guest_id}/delete")
def guest_delete(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    guest = access.guest(request, guest_id)
    if not guest:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
    if guest["submit_state"] == reporting.SENT:
        return _back(
            f"/guests/{guest_id}",
            err=_flash(request, "flash.error.reported_kept"),
        )
    reservation_id = guest["reservation_id"]
    passport_photos.delete_photo(guest_id)
    db.execute("DELETE FROM guest WHERE id = ?", (guest_id,))
    db.audit("guest_deleted", f"id={guest_id}")
    reservation = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,)
    )
    if reservation:
        reporting.submit_stay_if_complete(
            reservation["apartment_id"], reservation_id
        )
    return _back(f"/reservations/{reservation_id}", msg=_flash(request, "flash.guests.removed"))


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
        return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
    form = await request.form()
    if not form.get("confirm_duplicate"):
        return _back(f"/guests/{guest_id}", err=_flash(request, "flash.error.confirm_duplicate"))
    if reporting.blocked_as_duplicate(guest):
        return _back(
            f"/guests/{guest_id}",
            err=_flash(request, "flash.error.already_reported_duplicate"),
        )
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (guest["reservation_id"],))
    results = reporting.submit_for_apartment(
        reservation["apartment_id"],
        only_guest_ids=[guest_id],
        mode="manual_resend",
        ignore_automation=True,
        allow_resend=True,
    )
    if not results:
        return _back(f"/guests/{guest_id}", err=_flash(request, "flash.error.record_not_sendable"))
    db.audit("guest_resent", f"id={guest_id}")
    result = results[0]
    if result.get("state") == "transport_error":
        return _back(f"/guests/{guest_id}", err=_flash(request, "flash.error.ubyport_unreachable"))
    if result.get("submitted"):
        return _back(f"/guests/{guest_id}", msg=_flash(request, "flash.guests.resent"))
    return _back(f"/guests/{guest_id}", err=_flash(request, "flash.error.resent_rejected"))


# --- submissions ---------------------------------------------------------


@router.get("/submissions")
def submissions_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = db.query(
        # Only what the list renders: s.* would drag every stored receipt PDF
        # (base64) and both SOAP envelopes across for 200 rows.
        "SELECT s.id, s.created_at, s.apartment_id, s.mode, s.guest_ids, s.state, "
        "       s.pseudo_stamp, "
        "       (s.receipt_pdf IS NOT NULL AND TRIM(s.receipt_pdf) != '') AS has_receipt, "
        "       a.internal_name "
        "FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE a.owner_user_id IS ? ORDER BY s.created_at DESC LIMIT 200",
        (access.owner_id(request),),
    )
    receipt_count = sum(1 for row in rows if row["has_receipt"])
    return render(request, "submissions.html", {"rows": rows, "receipt_count": receipt_count})


@router.get("/submissions/{submission_id}")
def submission_detail(submission_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    submission = access.submission(request, submission_id, "s.*, a.internal_name")
    if not submission:
        return _back("/submissions", err=_flash(request, "flash.error.no_such_submission"))
    guest_ids = json.loads(submission["guest_ids"] or "[]")
    guests = []
    if guest_ids:
        marks = ", ".join("?" for _ in guest_ids)
        found = db.query(
            "SELECT g.* FROM guest g "
            "JOIN reservation r ON r.id = g.reservation_id "
            f"WHERE g.id IN ({marks}) AND r.apartment_id = ?",
            [*guest_ids, submission["apartment_id"]],
        )
        # IN (...) does not preserve order and the record errors are positional:
        # record_errors[i] answers for guest_ids[i]. Rebuilding the batch order is
        # what lets the result below come from this submission rather than from
        # the guest's current state.
        by_id = {row["id"]: row for row in found}
        guests = [by_id[guest_id] for guest_id in guest_ids if guest_id in by_id]
    codebook = codelists.error_codebook()
    from ..ubyport import errors as uby_errors

    lang = host_i18n.lang_from_request(request)
    header_messages = [
        f"{code}: {uby_errors.describe(code, codebook, lang)}"
        for code in uby_errors.split_codes(submission["header_errors"])
    ]
    raw_record_errors = json.loads(submission["record_errors"] or "[]")
    record_errors = [error for error in raw_record_errors if str(error).strip(" ;")]
    # guest.submit_state is one current pointer that a later resend moves, so
    # reading it here showed "Accepted" for a record this submission refused.
    # The outcome belongs to the submission, and is read from its own errors.
    rows = []
    for index, guest in enumerate(guests):
        error = raw_record_errors[index] if index < len(raw_record_errors) else ""
        state, messages = uby_errors.classify(
            submission["header_errors"], error, codebook, lang
        )
        if state == "accepted":
            result = "accepted"
        elif "150" in uby_errors.split_codes(error) or any(
            uby_errors.is_duplicate(message) for message in messages
        ):
            result = "duplicate"
        else:
            result = "rejected_final" if state == "not_correctable" else "rejected"
        rows.append({**dict(guest), "result": result, "errors": " | ".join(messages)})
    # A rejected report leads nowhere on its own: the guest data is fixed on the
    # stay, and that is where the batch is sent again. The first guest names it.
    fix_reservation_id = rows[0]["reservation_id"] if rows else None
    return render(
        request,
        "submission_detail.html",
        {
            "submission": submission,
            "guests": rows,
            "header_messages": header_messages,
            "record_errors": record_errors,
            "fix_reservation_id": fix_reservation_id,
        },
    )


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
            "mail_backend": mail.backend_name(),
            "console_mail": mail.recent_console_messages(access.owner_id(request)),
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


