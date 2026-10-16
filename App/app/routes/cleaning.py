"""Host cleaning CRUD and a separately authorized, read-only team view."""
from __future__ import annotations

from datetime import date, timedelta
from itertools import groupby
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .. import access, auth, cleaning, cleaning_codes, cleaning_i18n, config, db, host_i18n, security, templating

router = APIRouter(dependencies=[Depends(security.protect_host_post)])
PRIVATE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow"}


def _lang(request: Request) -> str:
    return host_i18n.resolve_language(request, default=host_i18n.DEFAULT_LANGUAGE)


def _context(request: Request, **values) -> dict:
    lang = _lang(request)
    weekdays = (("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday") if lang == "en"
                else ("Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"))

    def full_date(value):
        day = date.fromisoformat(value)
        return f"{weekdays[day.weekday()]} {day.day}.{day.month}.{day.year}"

    return {"cleaning_labels": {key: pair[1 if lang == "cs" else 0] for key, pair in cleaning_i18n.WORDS.items()},
            "nav": "cleaning", "ct": cleaning_i18n.translator(lang),
            "cleaning_date": full_date, "lang": lang, **values}


def _groups(payload: dict) -> list:
    return [(day, list(items)) for day, items in groupby(payload["cleanings"], key=lambda item: item["date"])]


def _render(request: Request, name: str, status_code: int = 200, **values):
    response = templating.render(request, name, _context(request, **values), status_code=status_code)
    response.headers.update(PRIVATE)
    return response


def _home(request: Request, property_id: int) -> dict:
    row = access.apartment(request, property_id)
    if not row or not row["active"] or row["archived_at"]:
        raise HTTPException(404)
    return dict(row)


def _event(request: Request, event_id: int) -> dict:
    row = cleaning.event_for(access.owner_id(request), event_id)
    if not row:
        raise HTTPException(404)
    return row


def _period(request: Request):
    first = cleaning.parse_date(request.query_params.get("from") or request.query_params.get("cal_date")
                                or cleaning.today().isoformat())
    end = request.query_params.get("to") or (first + timedelta(days=30)).isoformat()
    return cleaning.parse_range(first.isoformat(), end)


def _payload(request: Request, first: date, last: date, ids=None, read_only=False, owner_id=None):
    owner = access.owner_id(request) if not read_only else owner_id
    allowed = cleaning.properties(owner, ids)
    property_filter = request.query_params.get("property") or request.query_params.get("cal_property")
    selected = int(property_filter) if property_filter else None
    if selected is not None and selected not in {p["id"] for p in allowed}:
        raise HTTPException(404)
    payload = cleaning.schedule(owner, first, last, [selected] if selected else ids)
    if read_only:
        for entry in payload["events"]:
            if entry["kind"] == "booking":
                entry["start"] = max(entry["start"], first.isoformat())
                entry["end"] = min(entry["end"], last.isoformat())
    payload["properties"] = [{"id": p["id"], "name": p["internal_name"]} for p in allowed]
    context = _context(request, groups=_groups(payload), read_only=read_only)
    payload["listHtml"] = templating.templates.get_template("_cleaning_list.html").render(context)
    return payload


def _back(key="saved"):
    return RedirectResponse("/cleaning?" + urlencode({"notice": key}), status_code=303, headers=PRIVATE)


@router.get("/cleaning")
def index(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    try:
        first, last = _period(request)
        payload = _payload(request, first, last)
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid cleaning range") from None
    return _render(request, "cleaning.html", payload=payload, groups=_groups(payload),
                   today=cleaning.today(), apartments=cleaning.properties(access.owner_id(request)),
                   read_only=False, calendar_source="/cleaning/schedule", calendar_cleaning=True,
                   calendar_readonly=False, calendar_date=first.isoformat(),
                   calendar_from=first.isoformat(), calendar_to=last.isoformat(),
                   notice=request.query_params.get("notice", ""))


@router.get("/cleaning/schedule")
def schedule_data(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    try:
        first, last = cleaning.parse_range(request.query_params.get("from", ""), request.query_params.get("to", ""))
        payload = _payload(request, first, last)
    except (ValueError, TypeError):
        return JSONResponse({"error": "dates"}, status_code=422, headers=PRIVATE)
    return JSONResponse(payload, headers=PRIVATE)


def _editor(request: Request, values: dict, event=None, error="", status_code=200):
    return _render(request, "cleaning_edit.html", status_code=status_code, values=values,
                   event=event, error=error, homes=cleaning.properties(access.owner_id(request)))


@router.get("/cleaning/new")
def new_event(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    return _editor(request, {
        "scheduled_date": request.query_params.get("date", cleaning.today().isoformat()),
        "apartment_id": request.query_params.get("property", ""),
    })


@router.post("/cleaning/events")
async def create_event(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    values = dict(await request.form())
    try:
        home = _home(request, int(values.get("apartment_id", 0)))
        cleaning.save_event(home["id"], values)
    except (ValueError, TypeError) as exc:
        return _editor(request, values, error=str(exc) if str(exc) in {"dates", "times", "notes"} else "property",
                       status_code=422)
    return _back()


@router.get("/cleaning/events/{event_id}/edit")
def edit_event(request: Request, event_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    cleaning.reconcile(access.owner_id(request))
    event = _event(request, event_id)
    if event["state"] != "scheduled":
        raise HTTPException(404)
    return _editor(request, {**event, "notes": db.decrypt_field(event["notes_enc"]) if event["notes_enc"] else ""}, event)


@router.post("/cleaning/events/{event_id}")
async def update_event(request: Request, event_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    cleaning.reconcile(access.owner_id(request))
    event = _event(request, event_id)
    values = dict(await request.form())
    try:
        home = _home(request, int(values.get("apartment_id", event["apartment_id"])))
        cleaning.save_event(home["id"], values, event)
    except (ValueError, TypeError) as exc:
        error = str(exc) if str(exc) in {"dates", "times", "notes", "property", "changed"} else "changed"
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"error": error}, status_code=409 if error == "changed" else 422, headers=PRIVATE)
        return _editor(request, values, event, error, 409 if error == "changed" else 422)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": True}, headers=PRIVATE)
    return _back()


@router.post("/cleaning/events/{event_id}/delete")
async def delete_event(request: Request, event_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    values = await request.form()
    try:
        cleaning.dismiss(_event(request, event_id), int(values.get("revision", 0)))
    except (ValueError, TypeError):
        raise HTTPException(409, "Cleaning changed") from None
    return _back("removed")


def _settings(request: Request, home: dict, error="", status_code=200, values=None):
    prop = cleaning.properties(access.owner_id(request), [home["id"]])[0]
    if values is not None:
        prop.update({"cleaning_instructions": values.get("instructions", "")})
    prop["effective_checkout_time"] = cleaning._hour(prop, "checkout")
    prop["effective_checkin_time"] = cleaning._hour(prop, "checkin")
    failed_revoke = db.query_one(
        "SELECT id FROM cleaning_code WHERE apartment_id = ? AND state = 'revoke_failed'", (home["id"],),
    )
    return _render(request, "cleaning_settings.html", status_code=status_code, home=home, prop=prop,
                   code=cleaning._code(prop), error=error, failed_revoke=bool(failed_revoke),
                   codes_disabled=auth.staging_no_login(),
                   homes=cleaning.properties(access.owner_id(request)))


@router.get("/cleaning/properties")
def choose_property(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    homes = cleaning.properties(access.owner_id(request))
    return _render(request, "cleaning_properties.html", homes=homes)


@router.get("/cleaning/properties/{property_id}")
def property_settings(request: Request, property_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    return _settings(request, _home(request, property_id))


@router.post("/cleaning/properties/{property_id}")
async def save_property(request: Request, property_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    home = _home(request, property_id)
    values = dict(await request.form())
    try:
        cleaning.save_settings(property_id, values)
    except ValueError as exc:
        response = _settings(request, home, str(exc), 422, values)
        return response
    return RedirectResponse(f"/cleaning/properties/{property_id}?notice=saved", 303, headers=PRIVATE)


@router.post("/cleaning/properties/{property_id}/code/{action}")
async def code_action(request: Request, property_id: int, action: str):
    guard = auth.require_login(request)
    if guard:
        return guard
    home = _home(request, property_id)
    form = await request.form()
    try:
        if action == "manual":
            cleaning_codes.save_manual(property_id, str(form.get("code", "")))
        elif action == "ttlock":
            cleaning_codes.queue_permanent(home, access.owner_id(request))
        elif action == "remove":
            cleaning_codes.remove(property_id)
        else:
            raise HTTPException(404)
    except ValueError as exc:
        return _settings(request, home, str(exc), 422)
    return RedirectResponse(f"/cleaning/properties/{property_id}?notice=saved", 303, headers=PRIVATE)


def _shares(request: Request, token="", error="", status_code=200):
    owner = access.owner_id(request)
    rows = db.query(
        f"SELECT id, expires_at FROM cleaning_share WHERE {db.null_safe_eq('owner_user_id')} "
        "AND revoked_at IS NULL AND expires_at > ? ORDER BY id DESC", (owner, db.utcnow()),
    )
    # TLS terminates at the proxy; never derive a credential-bearing link
    # from an internal HTTP scheme or an untrusted Host header.
    base_url = (config.PUBLIC_BASE_URL or str(request.base_url)).rstrip("/")
    share_url = f"{base_url}/cleaning/shared/{token}" if token else ""
    return _render(request, "cleaning_shares.html", status_code=status_code,
                   homes=cleaning.properties(owner), shares=rows, share_url=share_url, error=error)


@router.get("/cleaning/shares")
def share_settings(request: Request):
    guard = auth.require_login(request)
    return guard if guard else _shares(request)


@router.post("/cleaning/shares")
async def create_share(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    try:
        if auth.staging_no_login():
            raise ValueError("login_required")
        ids = [int(value) for value in form.getlist("properties")]
        _, token = cleaning.new_share(access.owner_id(request), ids)
    except (TypeError, ValueError) as exc:
        return _shares(request, error="login_required" if str(exc) == "login_required" else "property", status_code=422)
    return _shares(request, token=token)


@router.post("/cleaning/shares/{share_id}/revoke")
def revoke_share(request: Request, share_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    db.execute(
        "UPDATE cleaning_share SET revoked_at = ? WHERE id = ? "
        f"AND {db.null_safe_eq('owner_user_id')}", (db.utcnow(), share_id, access.owner_id(request)),
    )
    return RedirectResponse("/cleaning/shares", 303, headers=PRIVATE)


def _shared_payload(request: Request, token: str):
    link = cleaning.shared(token)
    if not link:
        raise HTTPException(404)
    share, ids = link
    first, last = cleaning.today(), cleaning.today() + timedelta(days=30)
    if "from" in request.query_params or "to" in request.query_params:
        requested_first, requested_last = cleaning.parse_range(
            request.query_params.get("from", ""), request.query_params.get("to", ""),
        )
        first, last = max(first, requested_first), min(last, requested_last)
    return _payload(request, first, last, ids, True, share["owner_user_id"])


@router.get("/cleaning/shared/{token}", name="shared_cleaning")
def external_view(request: Request, token: str):
    try:
        payload = _shared_payload(request, token)
    except (ValueError, TypeError):
        raise HTTPException(422) from None
    context = _context(request, payload=payload, groups=_groups(payload), today=cleaning.today(),
                       apartments=[{"id": p["id"], "internal_name": p["name"], "active": 1}
                                   for p in payload["properties"]], read_only=True,
                       calendar_source=f"/cleaning/shared/{token}/schedule",
                       calendar_cleaning=True, calendar_readonly=True,
                       calendar_date=cleaning.today().isoformat(),
                       calendar_from=payload["from"], calendar_to=payload["to"])
    response = templating.render_guest(request, "cleaning_shared.html", context)
    response.headers.update(PRIVATE)
    return response


@router.get("/cleaning/shared/{token}/schedule")
def external_data(request: Request, token: str):
    try:
        payload = _shared_payload(request, token)
    except (ValueError, TypeError):
        return JSONResponse({"error": "dates"}, 422, headers=PRIVATE)
    return JSONResponse(payload, headers=PRIVATE)
