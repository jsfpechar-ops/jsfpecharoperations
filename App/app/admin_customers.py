"""Bounded, read-only operator customer queries. No guest data or billing writes."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import db, validation

PAGE_SIZE = 25
STATES = ("legacy", "unverified", "disabled", "trial_pending", "trialing",
          "active", "overdue", "canceling", "paused")
STATE_SQL = (
    "CASE WHEN u.signup_at IS NOT NULL AND u.email_verified_at IS NULL AND u.active = 0 "
    "THEN 'unverified' WHEN u.active = 0 THEN 'disabled' "
    "WHEN b.owner_user_id IS NULL THEN 'legacy' ELSE b.status END"
)
FROM_SQL = " FROM user_account u LEFT JOIN billing_account b ON b.owner_user_id = u.id "
FIELDS = (
    "u.id, u.username, u.display_name, u.email, u.active, u.created_at, "
    "u.email_verified_at, u.last_login_at, b.plan, b.billing_interval, "
    "b.trial_started_at, b.trial_ends_at, b.period_start, b.period_end, "
    "b.addon_ttlock, b.addon_whitelabel, b.apartments_billed, "
    + STATE_SQL + " AS customer_state"
)


def filters(q: str = "", state: str = "", plan: str = "") -> dict[str, str]:
    return {"q": q.strip()[:120],
            "state": state if state in (*STATES, "ending") else "",
            "plan": plan if plan in ("standard", "max") else ""}


def _where(values: dict[str, str], today: date) -> tuple[str, list[Any]]:
    clauses = ["u.role = 'host'"]
    params: list[Any] = []
    if values["q"]:
        term = values["q"].lower().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        clauses.append(
            "(LOWER(COALESCE(u.email, '')) LIKE ? ESCAPE '!' OR "
            "LOWER(COALESCE(u.display_name, '')) LIKE ? ESCAPE '!' OR "
            "LOWER(u.username) LIKE ? ESCAPE '!')"
        )
        params.extend(["%" + term + "%"] * 3)
    if values["state"] == "ending":
        clauses.append("u.active = 1 AND b.status = 'trialing' AND b.trial_ends_at >= ? "
                       "AND b.trial_ends_at <= ?")
        params.extend((today.isoformat(), (today + timedelta(days=7)).isoformat()))
    elif values["state"]:
        clauses.append("(" + STATE_SQL + ") = ?")
        params.append(values["state"])
    if values["plan"]:
        clauses.append("b.plan = ?")
        params.append(values["plan"])
    return " AND ".join(clauses), params


def customers(values: dict[str, str], *, after: int = 0, before: int = 0,
              today: date) -> dict[str, Any]:
    """Seek by unique account id; filtering happens before the fixed-size LIMIT."""
    where, params = _where(values, today)
    if before:
        where += " AND u.id > ?"
        params.append(before)
    elif after:
        where += " AND u.id < ?"
        params.append(after)
    ordering = "ASC" if before else "DESC"
    rows = [dict(row) for row in db.query(
        "SELECT " + FIELDS + FROM_SQL + "WHERE " + where
        + " ORDER BY u.id " + ordering + " LIMIT ?", (*params, PAGE_SIZE + 1),
    )]
    more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    if before:
        rows.reverse()
    if rows:
        marks = ", ".join("?" for _ in rows)
        counts = {int(r["owner_user_id"]): int(r["n"]) for r in db.query(
            "SELECT owner_user_id, COUNT(*) AS n FROM apartment "
            f"WHERE active = 1 AND owner_user_id IN ({marks}) GROUP BY owner_user_id",
            tuple(r["id"] for r in rows),
        )}
        for row in rows:
            row["active_properties"] = counts.get(row["id"], 0)
    return {"customers": rows, "older": bool(rows) and (bool(before) or more),
            "newer": bool(rows) and (bool(after) or (bool(before) and more))}


def summary(today: date) -> dict[str, int]:
    """Only aggregate counts cross into Python; never materialize the customer table."""
    counts = {row["customer_state"]: int(row["n"]) for row in db.query(
        "SELECT " + STATE_SQL + " AS customer_state, COUNT(*) AS n"
        + FROM_SQL + "WHERE u.role = 'host' GROUP BY " + STATE_SQL,
    )}
    where, params = _where(filters(state="ending"), today)
    row = db.query_one("SELECT COUNT(*) AS n" + FROM_SQL + "WHERE " + where, params)
    counts["ending"] = int(row["n"])
    return counts


def detail(user_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT " + FIELDS + FROM_SQL + "WHERE u.role = 'host' AND u.id = ?", (user_id,))
    if row is None:
        return None
    customer = dict(row)
    count = db.query_one("SELECT COUNT(*) AS n FROM apartment WHERE owner_user_id = ? AND active = 1",
                         (user_id,))
    customer["active_properties"] = int(count["n"])
    customer["invoices"] = [dict(inv) for inv in db.query(
        "SELECT id, number, issue_date, due_date, total_haler, paid_on, voided, kind "
        "FROM platform_invoice WHERE owner_user_id = ? ORDER BY id DESC LIMIT 10", (user_id,),
    )]
    customer["buyer_prefill"] = buyer_prefill(user_id)
    return customer


def buyer_prefill(user_id: int) -> dict[str, str]:
    """Known operator details for the assign-plan buyer fields (0448 prefill).

    Blanks only: the operator keeps what they typed. Sources are the host's
    legal entity (name, IČO, DIČ, contact e-mail) and the first active
    apartment's address (street + house number, municipality, ZIP).
    """
    entity = db.query_one(
        "SELECT name, ico, dic, contact_email FROM legal_entity "
        "WHERE owner_user_id = ? ORDER BY id LIMIT 1", (user_id,))
    apartment = db.query_one(
        "SELECT addr_street, addr_house_no, addr_obec, addr_zip FROM apartment "
        "WHERE owner_user_id = ? AND active = 1 AND archived_at IS NULL ORDER BY id LIMIT 1",
        (user_id,))
    prefill: dict[str, str] = {}
    if entity:
        prefill.update(buyer_name=(entity["name"] or "").strip(),
                       buyer_ico=(entity["ico"] or "").strip(),
                       buyer_dic=(entity["dic"] or "").strip(),
                       buyer_email=(entity["contact_email"] or "").strip())
    if apartment:
        street = " ".join(part for part in (
            (apartment["addr_street"] or "").strip(),
            (apartment["addr_house_no"] or "").strip()) if part)
        if street:
            prefill["buyer_street"] = street
        if (apartment["addr_obec"] or "").strip():
            prefill["buyer_city"] = apartment["addr_obec"].strip()
        zipcode = validation.normalise_zip(apartment["addr_zip"] or "")
        if zipcode:
            prefill["buyer_zip"] = zipcode
    return prefill
