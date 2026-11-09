"""Direct payment rails for the booking site (brief 0996, owner decision 2026-11-07).

The host's rails are the stay-fee guest-pay columns on `apartment` (brief 0897);
the IBAN is the one on the apartment's legal entity. Reads and validates only:
no money moves here and nothing is sent anywhere.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import db

RAILS = ("iban", "revolut", "cash")


def _apartment(apartment_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one(
        "SELECT legal_entity_id, stay_fee_guest_rails, stay_fee_guest_revolut_link,"
        " stay_fee_guest_cash_note, stay_fee_guest_default_rail FROM apartment WHERE id = ?",
        (apartment_id,),
    )
    return dict(row) if row else None


def account_on_file(legal_entity_id: Any) -> str:
    """The host's IBAN or account number, '' when none."""
    if not legal_entity_id:
        return ""
    entity = db.query_one(
        "SELECT iban, bank_account FROM legal_entity WHERE id = ?", (legal_entity_id,)
    )
    return ((entity["iban"] or entity["bank_account"] or "") if entity else "").strip()


def _ticked(apartment: Dict[str, Any]) -> set:
    raw = {part for part in (apartment["stay_fee_guest_rails"] or "").split(",") if part}
    if "qr" in raw:  # legacy: the QR rail is the bank rail
        raw.add("iban")
    return raw


def enabled(apartment_id: int) -> List[str]:
    """Ticked rails that can really be shown to a guest, in RAILS order."""
    from .routes import stay_fees  # lazy: routes import this package

    apartment = _apartment(apartment_id)
    if apartment is None:
        return []
    ticked = _ticked(apartment)
    out = []
    for rail in RAILS:
        if rail not in ticked:
            continue
        if rail == "iban" and not account_on_file(apartment["legal_entity_id"]):
            continue
        if rail == "revolut" and not stay_fees.revolut_link_ok(
            apartment["stay_fee_guest_revolut_link"] or ""
        ):
            continue
        out.append(rail)
    return out


def ready(apartment_id: int) -> bool:
    """At least one direct rail works: the host can publish without Stripe."""
    return bool(enabled(apartment_id))


def setup_view(apartment_id: int) -> Dict[str, Any]:
    """What the "How guests pay" form prints."""
    apartment = _apartment(apartment_id) or {}
    return {
        "ticked": sorted(_ticked(apartment)) if apartment else [],
        "revolut_link": apartment.get("stay_fee_guest_revolut_link") or "",
        "cash_note": apartment.get("stay_fee_guest_cash_note") or "",
        "iban_ok": bool(account_on_file(apartment.get("legal_entity_id"))),
    }


def parse_form(form, apartment_id: int) -> Dict[str, Any]:
    """Form to `apartment` column values. Raises ValueError("pay_none" |
    "pay_revolut" | "pay_iban"); the route turns it into `bsite.err.<code>`."""
    from .routes import stay_fees

    apartment = _apartment(apartment_id)
    if apartment is None:
        raise ValueError("pay_none")
    posted = {value for value in form.getlist("rails") if value in RAILS}
    if not posted:
        raise ValueError("pay_none")
    values: Dict[str, Any] = {"stay_fee_guest_rails": ",".join(sorted(posted))}
    if "revolut" in posted:
        link = str(form.get("revolut_link") or "").strip()
        if not stay_fees.revolut_link_ok(link):
            raise ValueError("pay_revolut")
        values["stay_fee_guest_revolut_link"] = link
    if "iban" in posted and not account_on_file(apartment["legal_entity_id"]):
        raise ValueError("pay_iban")
    if "cash" in posted:
        note = str(form.get("cash_note") or "")[: stay_fees.GUEST_NOTE_MAX].strip()
        values["stay_fee_guest_cash_note"] = note or None
    current = apartment["stay_fee_guest_default_rail"] or ""
    if current == "qr":
        current = "iban"
    if current not in posted:
        values["stay_fee_guest_default_rail"] = next(r for r in RAILS if r in posted)
    return values


def pay_modes(apartment_id: int, owner_user_id: int) -> List[str]:
    """Ways the guest can book: 'stripe' and/or 'direct'."""
    from . import stripe_connect

    modes = []
    account = stripe_connect.account_for_owner(owner_user_id)
    if account is not None and account["onboarding_state"] == "complete":
        modes.append("stripe")
    if ready(apartment_id):
        modes.append("direct")
    return modes


def guest_view(apartment_id: int, booking: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The rails a guest sees on the request page, host's default first.
    VS is the booking id; the QR payload is built here and never stored."""
    from . import payments

    apartment = _apartment(apartment_id)
    if apartment is None:
        return []
    total = int(booking["total_czk"])
    vs = str(int(booking["id"]))
    first = apartment["stay_fee_guest_default_rail"] or ""
    first = "iban" if first == "qr" else first
    order = ([first] if first in RAILS else []) + [r for r in RAILS if r != first]
    live = set(enabled(apartment_id))
    out: List[Dict[str, Any]] = []
    for rail in order:
        if rail not in live:
            continue
        if rail == "iban":
            entity = db.query_one(
                "SELECT iban, bank_account FROM legal_entity WHERE id = ?",
                (apartment["legal_entity_id"],),
            )
            account = entity["iban"] or payments.normalise_account(entity["bank_account"])[1]
            payload = payments.spayd(account, total, vs, f"Stay {vs}")
            out.append({"key": "iban", "iban": payments.format_iban(account),
                        "qr": payments.qr_data_uri(payload), "vs": vs, "amount": total})
        elif rail == "revolut":
            out.append({"key": "revolut", "link": apartment["stay_fee_guest_revolut_link"]})
        else:
            out.append({"key": "cash", "note": apartment["stay_fee_guest_cash_note"] or ""})
    return out
