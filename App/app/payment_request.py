"""Direct payment requests: a host asks a guest for money.

ubyhost never processes a payment. Rail 'card' is a Stripe payment link on the
host's own connected account (merchant of record, application fee 0); rail
'qr' is a SPAYD QR the guest pays into the host's own bank account — ubyhost is
only the technology provider. This module stores and tracks; it never touches
funds and never calls Stripe (brief 0422+ adds that).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from . import db, payments

REASONS = ("repair", "extra_guest", "late_checkout", "cleaning", "damage", "custom")
RAILS = ("card", "qr")
STATUSES = ("draft", "sent", "awaiting_payment", "paid", "expired", "cancelled")

# Allowed status transitions (brief 0421 §4).
_TRANSITIONS = {
    "draft": {"sent", "cancelled"},
    "sent": {"awaiting_payment", "paid", "expired", "cancelled"},
    "awaiting_payment": {"paid", "expired", "cancelled"},
    "paid": set(),
    "expired": set(),
    "cancelled": set(),
}


def _check(value: str, allowed: tuple, field: str) -> str:
    if value not in allowed:
        raise ValueError(f"{field} must be one of {', '.join(allowed)}")
    return value


def create(
    owner_user_id: int,
    *,
    apartment_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    reason: str,
    amount_czk: int,
    rail: str,
    expires_at: str,
    today: Optional[date] = None,
    guest_email: Optional[str] = None,
    guest_note: Optional[str] = None,
) -> int:
    """Insert a draft request; QR requests get a unique variable symbol."""
    _check(reason, REASONS, "reason")
    _check(rail, RAILS, "rail")
    if not isinstance(amount_czk, int) or amount_czk < 1:
        raise ValueError("amount_czk must be a whole number of CZK, at least 1")
    now = db.utcnow()
    request_id = db.insert(
        "payment_request",
        {
            "owner_user_id": owner_user_id,
            "apartment_id": apartment_id,
            "reservation_id": reservation_id,
            "reason": reason,
            "amount_czk": amount_czk,
            "currency": "CZK",
            "guest_email": guest_email,
            "guest_note": guest_note,
            "rail": rail,
            "status": "draft",
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
        },
    )
    if rail == "qr":
        _assign_variable_symbol(request_id)
    return int(request_id)


def _assign_variable_symbol(request_id: int) -> None:
    """VS = the row's own id, zero-padded to 10 digits (unique by construction)."""
    vs = f"{request_id:010d}"
    changed = db.execute_rowcount(
        "UPDATE payment_request SET variable_symbol = ?, updated_at = ? WHERE id = ?",
        (vs, db.utcnow(), request_id),
    )
    if changed != 1:
        raise RuntimeError(f"payment_request {request_id} vanished before VS assignment")


def get(request_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one("SELECT * FROM payment_request WHERE id = ?", (request_id,))
    return dict(row) if row else None


def for_owner(owner_user_id: int, *, limit: int = 100) -> List[Dict[str, Any]]:
    rows = db.query(
        "SELECT * FROM payment_request WHERE owner_user_id = ?"
        " ORDER BY created_at DESC, id DESC LIMIT ?",
        (owner_user_id, limit),
    )
    return [dict(row) for row in rows]


def set_status(request_id: int, status: str, *, today: date, paid_at: Optional[str] = None) -> bool:
    """Move a request through its lifecycle; illegal jumps raise ValueError."""
    _check(status, STATUSES, "status")
    row = get(request_id)
    if row is None:
        return False
    current = row["status"]
    if status not in _TRANSITIONS[current]:
        raise ValueError(f"payment_request {request_id}: {current} -> {status} is not allowed")
    changed = db.execute_rowcount(
        "UPDATE payment_request SET status = ?, paid_at = COALESCE(?, paid_at),"
        " updated_at = ? WHERE id = ? AND status = ?",
        (status, paid_at, db.utcnow(), request_id, current),
    )
    if changed != 1:
        return False
    db.audit(
        "payment_request_status",
        f"id={request_id} {current}->{status}",
        owner_user_id=row["owner_user_id"],
    )
    return True


def mark_paid(request_id: int, *, today: date, via: str) -> bool:
    """Mark a request paid, recording the rail in the audit note."""
    row = get(request_id)
    if row is None:
        return False
    ok = set_status(request_id, "paid", today=today, paid_at=db.utcnow())
    if ok:
        db.audit(
            "payment_request_paid",
            f"id={request_id} via={via} amount={row['amount_czk']} CZK",
            owner_user_id=row["owner_user_id"],
        )
    return ok


def expire_sweep(today: date) -> int:
    """Expire every sent/awaiting request past its expiry; returns the count."""
    expired = db.query(
        "SELECT id, owner_user_id FROM payment_request"
        " WHERE status IN ('sent', 'awaiting_payment') AND expires_at < ?",
        (today.isoformat(),),
    )
    for row in expired:
        set_status(int(row["id"]), "expired", today=today)
    return len(expired)


def qr_payload(request: Dict[str, Any]) -> tuple:
    """(SPAYD payload, QR PNG bytes) for a QR request, from the owner's IBAN."""
    if request["rail"] != "qr":
        raise ValueError("qr_payload needs a qr-rail request")
    entity = db.query_one(
        "SELECT iban, bank_account FROM legal_entity WHERE owner_user_id = ?",
        (request["owner_user_id"],),
    )
    if entity is None or not (entity["iban"] or entity["bank_account"]):
        raise ValueError("host has no bank account set; QR requests need an IBAN")
    account = entity["iban"] or payments.normalise_account(entity["bank_account"])[1]
    payload = payments.spayd(
        account,
        Decimal(request["amount_czk"]),
        request["variable_symbol"],
        "UbyHost payment request",
    )
    return payload, payments.qr_png_bytes(payload)
