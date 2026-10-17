"""Cleaning schedules: durable booking-derived events and host overrides.

No completion/claim state and no writes to reservations. Both visual and linear
views serialize the same result. Reconciliation is idempotent on every read and
the existing minute worker, including imports and changes made outside the UI.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import auth, config, db

TIME = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def today() -> date:
    return datetime.now(ZoneInfo(config.TIMEZONE)).date()


def parse_date(value: str) -> date:
    if not DATE.fullmatch(value or ""):
        raise ValueError("dates")
    result = date.fromisoformat(value)
    if not 1900 <= result.year <= 2100:
        raise ValueError("dates")
    return result


def parse_time(value: str) -> str | None:
    value = (value or "").strip()
    if value and not TIME.fullmatch(value):
        raise ValueError("times")
    return value or None


def parse_range(start: str, end: str) -> tuple[date, date]:
    first, last = parse_date(start), parse_date(end)
    if not 0 < (last - first).days <= 370:
        raise ValueError("dates")
    return first, last


def properties(owner_id: int | None, ids: list[int] | None = None) -> list[dict]:
    rows = db.query(
        "SELECT a.*, p.instructions AS cleaning_instructions, p.checkout_time, "
        "p.checkin_time, p.code_id, p.pending_code_id "
        "FROM apartment a LEFT JOIN cleaning_property p ON p.apartment_id = a.id "
        f"WHERE {db.null_safe_eq('a.owner_user_id')} "
        "AND a.active = 1 AND a.archived_at IS NULL ORDER BY a.internal_name, a.id",
        (owner_id,),
    )
    return [dict(row) for row in rows if ids is None or row["id"] in ids]


def reconcile(owner_id: int | None = None, *, all_owners: bool = False) -> int:
    scope = "" if all_owners else f"AND {db.null_safe_eq('a.owner_user_id')}"
    args = () if all_owners else (owner_id,)
    rows = db.query(
        "SELECT r.id, r.apartment_id, r.date_to FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.status = 'active' "
        "AND r.archived_at IS NULL AND a.active = 1 AND a.archived_at IS NULL "
        "AND COALESCE(r.source, '') <> 'demo' AND r.date_to >= ? " + scope,
        ((today() - timedelta(days=30)).isoformat(), *args),
    )
    changed = 0
    for stay in rows:
        now = db.utcnow()
        # One short database transaction per stay; never an outbound request.
        with db.immediate() as cur:
            cur.execute(
                "INSERT INTO cleaning_event "
                "(apartment_id, source_reservation_id, source_date, scheduled_date, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (source_reservation_id) DO NOTHING",
                (stay["apartment_id"], stay["id"], stay["date_to"], stay["date_to"], now, now),
            )
            changed += max(0, cur.rowcount)
            cur.execute(
                "UPDATE cleaning_event SET apartment_id = ?, source_date = ?, "
                "scheduled_date = CASE WHEN overridden = 0 THEN ? ELSE scheduled_date END, "
                "state = CASE WHEN state = 'source_cancelled' THEN 'scheduled' ELSE state END, "
                "revision = revision + 1, updated_at = ? WHERE source_reservation_id = ? "
                "AND (apartment_id <> ? OR source_date <> ? OR state = 'source_cancelled')",
                (stay["apartment_id"], stay["date_to"], stay["date_to"], now, stay["id"],
                 stay["apartment_id"], stay["date_to"]),
            )
            changed += max(0, cur.rowcount)
    # A dismissal remains a dismissal when its booking is cancelled and restored.
    changed += db.execute(
        "UPDATE cleaning_event SET state = 'source_cancelled', revision = revision + 1, "
        "updated_at = ? WHERE state = 'scheduled' AND source_reservation_id IS NOT NULL "
        "AND apartment_id IN (SELECT a.id FROM apartment a WHERE 1 = 1 " + scope + ") "
        "AND NOT EXISTS (SELECT 1 FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.id = cleaning_event.source_reservation_id AND r.status = 'active' "
        "AND r.archived_at IS NULL AND a.active = 1 AND a.archived_at IS NULL)",
        (db.utcnow(), *args),
    )
    return changed


def ensure_property(apartment_id: int) -> None:
    db.execute(
        "INSERT INTO cleaning_property (apartment_id, updated_at) VALUES (?, ?) "
        "ON CONFLICT (apartment_id) DO NOTHING", (apartment_id, db.utcnow()),
    )


def event_for(owner_id: int | None, event_id: int) -> dict | None:
    row = db.query_one(
        "SELECT e.* FROM cleaning_event e JOIN apartment a ON a.id = e.apartment_id "
        f"WHERE e.id = ? AND {db.null_safe_eq('a.owner_user_id')} "
        "AND a.active = 1 AND a.archived_at IS NULL",
        (event_id, owner_id),
    )
    return dict(row) if row else None


def save_event(apartment_id: int, values: dict, existing: dict | None = None) -> int:
    day = parse_date(str(values.get("scheduled_date", ""))).isoformat()
    start = parse_time(str(values.get("start_time") or ""))
    end = parse_time(str(values.get("end_time") or ""))
    if bool(start) != bool(end) or (start and end <= start):
        raise ValueError("times")
    notes = str(values.get("notes", "")).strip()
    if len(notes) > 5000:
        raise ValueError("notes")
    payload = {
        "apartment_id": apartment_id, "scheduled_date": day, "start_time": start,
        "end_time": end, "notes_enc": db.encrypt_field(notes) if notes else None,
        "overridden": int(not existing or existing["overridden"] or day != existing["scheduled_date"]),
        "updated_at": db.utcnow(),
    }
    if existing:
        if existing["source_reservation_id"] and apartment_id != existing["apartment_id"]:
            raise ValueError("property")
        if existing["state"] != "scheduled":
            raise ValueError("changed")
        revision = int(values.get("revision", 0))
        payload["revision"] = revision + 1
        if not db.update_if("cleaning_event", existing["id"], payload, {"revision": revision, "state": "scheduled"}):
            raise ValueError("changed")
        return existing["id"]
    payload["created_at"] = payload["updated_at"]
    return db.insert("cleaning_event", payload)


def dismiss(existing: dict, revision: int) -> None:
    if not db.update_if("cleaning_event", existing["id"], {
        "state": "dismissed", "revision": revision + 1, "updated_at": db.utcnow(),
    }, {"revision": revision, "state": "scheduled"}):
        raise ValueError("changed")


def save_settings(apartment_id: int, values: dict) -> None:
    instructions = str(values.get("instructions", "")).strip()
    if len(instructions) > 10000:
        raise ValueError("notes")
    checkout = parse_time(str(values.get("checkout_time", "")))
    checkin = parse_time(str(values.get("checkin_time", "")))
    ensure_property(apartment_id)
    db.execute(
        "UPDATE cleaning_property SET instructions = ?, checkout_time = ?, "
        "checkin_time = ?, updated_at = ? WHERE apartment_id = ?",
        (instructions, checkout, checkin, db.utcnow(), apartment_id),
    )


def _hour(property_row: dict, direction: str) -> str | None:
    explicit = property_row[direction + "_time"]
    hour = property_row[direction + "_hour"]
    return explicit or (f"{int(hour):02d}:00" if hour is not None else None)


def _code(property_row: dict) -> dict:
    active = db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (property_row["code_id"],))
    pending = db.query_one("SELECT state FROM cleaning_code WHERE id = ?", (property_row["pending_code_id"],))
    usable = bool(not auth.staging_no_login() and active and active["state"] == "active" and active["pin_enc"])
    if usable and active["source"] == "ttlock":
        account = db.query_one("SELECT owner_user_id FROM lock_account WHERE id = ?", (active["lock_account_id"],))
        usable = bool(account and account["owner_user_id"] == property_row["owner_user_id"]
                      and property_row["lock_provider"] == "ttlock"
                      and str(property_row["lock_id"]) == active["lock_id"])
    return {
        "value": db.decrypt_field(active["pin_enc"]) if usable else "",
        "source": active["source"] if active else "",
        "pending": pending["state"] if pending else "",
    }


def schedule(owner_id: int | None, first: date, last: date, ids: list[int] | None = None) -> dict:
    reconcile(owner_id)
    homes = properties(owner_id, ids)
    output = {"properties": [{"id": p["id"], "name": p["internal_name"]} for p in homes],
              "events": [], "cleanings": [], "from": first.isoformat(), "to": last.isoformat()}
    for home in homes:
        # Include the next arrival beyond the loaded period. No guest rows or
        # booking summary/notes are loaded into the cleaner representation.
        stays = db.query(
            "SELECT id, date_from, date_to FROM reservation WHERE apartment_id = ? "
            "AND status = 'active' AND archived_at IS NULL AND COALESCE(source, '') <> 'demo' "
            "ORDER BY date_from, date_to, id", (home["id"],),
        )
        code = _code(home)
        checkout_time, checkin_time = _hour(home, "checkout"), _hour(home, "checkin")
        for stay in stays:
            if stay["date_from"] < last.isoformat() and stay["date_to"] > first.isoformat():
                output["events"].append({
                    "id": f"reservation:{stay['id']}", "kind": "booking",
                    "propertyId": home["id"], "property": home["internal_name"],
                    "start": stay["date_from"], "end": stay["date_to"],
                    "label": "", "tone": "neutral", "expected": None, "url": "#cleaning-list",
                })
        events = db.query(
            "SELECT * FROM cleaning_event WHERE apartment_id = ? AND state = 'scheduled' "
            "AND scheduled_date >= ? AND scheduled_date < ? ORDER BY scheduled_date, start_time, id",
            (home["id"], first.isoformat(), last.isoformat()),
        )
        for event in events:
            source = next((r for r in stays if r["id"] == event["source_reservation_id"]), None)
            candidates = [r for r in stays if r["id"] != event["source_reservation_id"] and
                          r["date_from"] >= (source["date_to"] if source else event["scheduled_date"])]
            arrival = candidates[0]["date_from"] if candidates else None
            departure = source["date_to"] if source else None
            warning = False
            if source:
                warning = event["scheduled_date"] < departure
                warning |= bool(event["scheduled_date"] == departure and event["start_time"] and checkout_time
                                and event["start_time"] < checkout_time)
                warning |= bool(arrival and event["scheduled_date"] > arrival)
                warning |= bool(arrival == event["scheduled_date"] and event["end_time"] and checkin_time
                                and event["end_time"] > checkin_time)
                warning |= any(r["id"] != source["id"] and r["date_from"] < departure and
                               r["date_to"] > departure for r in stays)
                warning |= bool(arrival == departure and checkout_time and checkin_time and checkout_time >= checkin_time)
            item = {
                "id": f"cleaning:{event['id']}", "eventId": event["id"], "kind": "cleaning",
                "propertyId": home["id"], "property": home["internal_name"],
                "start": event["scheduled_date"],
                "end": (date.fromisoformat(event["scheduled_date"]) + timedelta(days=1)).isoformat(),
                "date": event["scheduled_date"], "startTime": event["start_time"], "endTime": event["end_time"],
                "checkout": departure, "checkoutTime": checkout_time,
                "nextArrival": arrival, "checkinTime": checkin_time,
                "notes": db.decrypt_field(event["notes_enc"]) if event["notes_enc"] else "",
                "instructions": home["cleaning_instructions"] or "", "code": code["value"],
                "codeSource": code["source"], "codePending": code["pending"],
                "origin": "automatic" if source else "manual", "overridden": bool(event["overridden"]),
                "revision": event["revision"], "conflict": bool(warning), "tone": "neutral",
                "label": "", "expected": None, "url": f"#cleaning-{event['id']}",
            }
            output["events"].append(item)
            output["cleanings"].append(item)
    output["cleanings"].sort(key=lambda e: (e["date"], e["startTime"] or "", e["property"], e["eventId"]))
    return output


def new_share(owner_id: int | None, property_ids: list[int]) -> tuple[int, str]:
    if not property_ids or not set(property_ids) <= {p["id"] for p in properties(owner_id)}:
        raise ValueError("property")
    token = secrets.token_urlsafe(32)
    with db.immediate() as cur:
        cur.execute(
            "INSERT INTO cleaning_share (owner_user_id, token_hash, expires_at, created_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (owner_id, hashlib.sha256(token.encode()).hexdigest(),
             (datetime.now(ZoneInfo("UTC")) + timedelta(days=30)).isoformat(), db.utcnow()),
        )
        share_id = cur.fetchone()[0]
        for property_id in set(property_ids):
            cur.execute("INSERT INTO cleaning_share_property (share_id, apartment_id) VALUES (?, ?)",
                        (share_id, property_id))
    return share_id, token


def shared(token: str) -> tuple[dict, list[int]] | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token or ""):
        return None
    row = db.query_one(
        "SELECT * FROM cleaning_share WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?",
        (hashlib.sha256(token.encode()).hexdigest(), db.utcnow()),
    )
    if not row:
        return None
    ids = [r["apartment_id"] for r in db.query(
        "SELECT apartment_id FROM cleaning_share_property WHERE share_id = ?", (row["id"],),
    )]
    # Recheck ownership and property availability on every request.
    ids = [p["id"] for p in properties(row["owner_user_id"], ids)]
    return (dict(row), ids) if ids else None


def purge(today_value: date, dry_run: bool, owner_id: int | None) -> int:
    cutoff = (today_value - timedelta(days=30)).isoformat()
    scope = "apartment_id IN (SELECT a.id FROM apartment a WHERE (? IS NULL OR a.owner_user_id = ?))"
    notes = db.query_one(
        "SELECT COUNT(*) AS n FROM cleaning_event WHERE notes_enc IS NOT NULL "
        "AND scheduled_date < ? AND " + scope, (cutoff, owner_id, owner_id),
    )["n"]
    shares = db.query_one(
        "SELECT COUNT(*) AS n FROM cleaning_share WHERE expires_at < ? "
        "AND (? IS NULL OR owner_user_id = ?)", (cutoff, owner_id, owner_id),
    )["n"]
    if not dry_run:
        db.execute("UPDATE cleaning_event SET notes_enc = NULL WHERE scheduled_date < ? AND " + scope,
                   (cutoff, owner_id, owner_id))
        db.execute("DELETE FROM cleaning_share WHERE expires_at < ? AND (? IS NULL OR owner_user_id = ?)",
                   (cutoff, owner_id, owner_id))
    # Minimal source/dismissal records survive with the source reservation, so
    # reconciliation cannot resurrect a host's dismissed cleaning.
    return notes + shares
