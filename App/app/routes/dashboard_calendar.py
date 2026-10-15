"""Read-only, owner-scoped reservation data for the dashboard calendar."""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import access, auth, db, demo, reporting

router = APIRouter()


def parse_dates(start: str, end: str) -> tuple[date, date]:
    """Stay dates describe occupied nights: checkout is exclusive."""
    if not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or "") for value in (start, end)):
        raise ValueError("invalid dates")
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first.year < 1900 or last.year > 2101 or last <= first:
        raise ValueError("invalid range")
    return first, last


def parse_range(start: str, end: str) -> tuple[date, date]:
    """Bound data reads without imposing that limit on a manual stay."""
    first, last = parse_dates(start, end)
    if (last - first).days > 370:
        raise ValueError("invalid range")
    return first, last


def overlapping_count(apartment_id: int, start: str, end: str) -> int:
    """Called only after the canonical create handler checks apartment access."""
    return int(db.query_one(
        "SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ? "
        "AND status = 'active' AND archived_at IS NULL "
        "AND date_from < ? AND date_to > ?",
        (apartment_id, end, start),
    )["n"])


def events(owner_user_id: int | None, start: date, end: date, apartment_id: int | None = None):
    sql = (
        "SELECT r.*, a.internal_name, a.automation_mode FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE {db.null_safe_eq('a.owner_user_id')} AND a.active = 1 "
        "AND a.archived_at IS NULL AND r.archived_at IS NULL AND r.status = 'active' "
        "AND r.date_from < ? AND r.date_to > ?"
    )
    params = [owner_user_id, end.isoformat(), start.isoformat()]
    if apartment_id is not None:
        sql += " AND a.id = ?"
        params.append(apartment_id)
    reservations = db.query(sql + " ORDER BY r.date_from, r.date_to, r.id", params)
    guests = reporting.preload_guests(reservations)
    result = []
    for stay in reservations:
        # Do not expose guest identity, credentials, notes, or guest-form tokens.
        progress = reporting.reservation_progress(stay, guests.get(stay["id"], []))
        anchor = reporting.reservation_deadline_anchor(stay, progress["guests"])
        cell = reporting.deadline_cell(progress, anchor)
        status = progress["status"]
        preview = demo.is_demo_stay(stay)
        tone = "neutral"
        if cell["level"] == "overdue" and status not in reporting.FINISHED_STATUSES:
            tone = "overdue"
        elif status in ("failed", "incomplete", "awaiting_verification"):
            tone = "action"
        elif status == "ready" and not preview:
            tone = "ready"
        elif status in reporting.FINISHED_STATUSES:
            tone = "done"
        result.append({
            "id": stay["id"], "propertyId": stay["apartment_id"],
            "property": stay["internal_name"], "label": stay["summary"] or "",
            "start": stay["date_from"], "end": stay["date_to"],
            "guests": len(progress["guests"]), "complete": progress["filled"],
            "expected": progress["expected"], "status": status,
            "tone": tone, "preview": preview, "source": stay["source"],
            "url": f"/reservations/{stay['id']}?return_to=/",
        })
    return result


@router.get("/dashboard/calendar")
def calendar_data(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    try:
        start, end = parse_range(request.query_params.get("from", ""), request.query_params.get("to", ""))
        raw_property = request.query_params.get("property", "")
        apartment_id = int(raw_property) if raw_property else None
        if apartment_id is not None and apartment_id <= 0:
            raise ValueError("invalid property")
    except (ValueError, TypeError):
        return JSONResponse({"error": "invalid_range"}, status_code=422, headers={"Cache-Control": "no-store"})
    properties = [
        {"id": row["id"], "name": row["internal_name"]}
        for row in access.apartments(request, "id, internal_name, active")
        if row["active"]
    ]
    if apartment_id is not None and apartment_id not in {row["id"] for row in properties}:
        return JSONResponse({"error": "not_found"}, status_code=404, headers={"Cache-Control": "no-store"})
    return JSONResponse(
        {"properties": properties, "events": events(access.owner_id(request), start, end, apartment_id)},
        headers={"Cache-Control": "no-store"},
    )
