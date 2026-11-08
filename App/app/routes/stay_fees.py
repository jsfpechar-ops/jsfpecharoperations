"""Host-only stay-fee overview and per-property detail."""
from __future__ import annotations

import io
import unicodedata
import zipfile
from datetime import date
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from .. import (
    access,
    auth,
    claim,
    db,
    host_i18n,
    list_filter,
    payments,
    security,
    stay_fee,
    stay_fee_adjustment,
    stay_fee_auto,
    stay_fee_filing,
    stay_fee_rate,
    validation,
)
from ..templating import render, templates
from .. import config as app_config
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter(dependencies=[Depends(security.protect_host_post)])


def _period_key(cadence: str, month: date) -> str:
    """'2026-08' for a monthly property, '2026-Q3' for a quarterly one."""
    if cadence == "quarterly":
        return f"{month.year:04d}-Q{(month.month - 1) // 3 + 1}"
    return stay_fee.month_key(month)


def _fold_place(value) -> str:
    """A place name with case and diacritics removed, so 'Praha 3' matches 'praha 3'."""
    plain = unicodedata.normalize("NFKD", (value or "").strip())
    return "".join(ch for ch in plain if not unicodedata.combining(ch)).casefold()


# 0847: the council fields a property can take over from a sibling in the same municipality.
FEE_COPY_FIELDS = (
    "stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_vs",
    "stay_fee_council_account", "stay_fee_council_iban",
    "stay_fee_authority_name", "stay_fee_authority_address",
    "stay_fee_authority_contact", "stay_fee_authority_databox",
    "stay_fee_payee", "stay_fee_instruction",
    "stay_fee_scope_rule", "stay_fee_scope_reference",
)


def fee_copy_source(apartment, candidates):
    """The first candidate with an active fee in the same municipality, or None."""
    place = _fold_place(apartment["addr_obec"])
    if not place:
        return None
    for candidate in candidates:
        if (
            candidate["id"] != apartment["id"]
            and stay_fee.is_active(candidate)
            and _fold_place(candidate["addr_obec"]) == place
        ):
            return candidate
    return None


def _default_month(today: date) -> date:
    return stay_fee.previous_month(today)


def _ui_period_label(request: Request, cadence: str, month: date) -> str:
    """Host-language period name. The filed PDF keeps the Czech label."""
    lang = host_i18n.resolve_language(request)
    if cadence == "quarterly":
        return host_i18n.translate(
            lang,
            "stay_fees.quarter",
            n=(month.month - 1) // 3 + 1,
            year=month.year,
        )
    return f"{host_i18n.translate(lang, f'month.{month.month}')} {month.year}"


STAY_FEE_STATUSES = (
    ("attention", "stay_fees.needs_setup"),
    ("waiting", "stay_fees.status.in_progress"),
    ("ready", "stay_fees.status.ready"),
    ("saved", "stay_fees.status.saved"),
)


def _row_status(row: dict) -> str:
    if row["unset"]:
        return "attention"
    if row.get("frozen"):
        return "saved"
    issues = row["issues"] or []
    if issues == ["stay_fees.issue.period_running"]:
        return "waiting"
    if issues:
        return "attention"
    return "ready"


def _detail_filter(selected_month: date, today: date, apartment_id: int) -> dict:
    """The detail page uses the same control, month only."""
    view = list_filter.ListFilter(selected_month, None, "", "", selected_month)
    return {
        "month_key": stay_fee.month_key(selected_month),
        **list_filter.context(
            view,
            action=f"/stay-fees/{apartment_id}",
            today=today,
            period_label_key="stay_fees.filter.period",
            properties=(),
            statuses=(),
        ),
    }



@router.post("/stay-fees/{apartment_id}/guest-pay-preview")
async def guest_pay_preview(apartment_id: int, request: Request):
    """Live sample QR for the guest-pay block: what the host typed, nothing is saved."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment or not stay_fee_guest_pay_on():
        return JSONResponse({"ok": False}, status_code=404)
    form = await request.form()
    typed = _form_str(form, "account").strip()
    entity = None
    if apartment["legal_entity_id"]:
        entity = db.query_one(
            "SELECT id, bank_account, iban FROM legal_entity WHERE id = ?",
            (apartment["legal_entity_id"],),
        )
    try:
        rate = int(_form_str(form, "rate") or 0) or None
    except ValueError:
        rate = None
    ctx = guest_pay_operator_context(
        apartment, entity, draft_account=typed, sample_rate=rate,
    )
    return JSONResponse({
        "ok": bool(ctx["has_account"]),
        "invalid": bool(typed) and not ctx["has_account"],
        "account": ctx["account_display"],
        "qr": ctx["preview_qr"],
    })

@router.get("/stay-fees")
def stay_fees_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    today = claim.prague_today()
    owner_id = access.owner_id(request)
    apartments = db.query(
        f"SELECT * FROM apartment WHERE {db.null_safe_eq('owner_user_id')} AND archived_at IS NULL "
        "AND active = 1 ORDER BY internal_name, id",
        (owner_id,),
    )
    view = list_filter.parse(
        request.query_params,
        today=today,
        statuses=[value for value, _ in STAY_FEE_STATUSES],
        default_month=_default_month(today),
        apartment_ids=[row["id"] for row in apartments],
    )
    selected_month = view.month
    rows = []
    for period in stay_fee.owner_periods(owner_id, selected_month):
        apartment = period["apartment"]
        group = stay_fee.report_group(apartment, selected_month, period=period)
        issues = stay_fee.report_issues(group, today)
        if not period.get("frozen") and period.get("first") and stay_fee.unsigned_stays(
            apartment["id"], period["first"], period["last"], period
        ):
            issues.append("stay_fees.issue.unsigned")
        rows.append({
            **period,
            "total_display": stay_fee.format_czk(period["total_czk"]),
            "issues": issues,
            "unset": False,
            # 0203: the pay steps on the list need the same payment data as the report.
            "period_label": _ui_period_label(request, group["cadence"], selected_month),
            "pay": stay_fee.payment_details(group) if period.get("frozen") else None,
            "pay_total_czk": group["total_czk"],
            "pay_total_display": stay_fee.format_czk(group["total_czk"]),
        })
    configured = {row["apartment"]["id"] for row in rows}
    for apartment in apartments:
        if apartment["id"] not in configured:
            rows.append({
                "apartment": apartment, "unset": True, "issues": [],
                "copy_from": fee_copy_source(apartment, apartments),
            })
    for row in rows:
        row["status"] = _row_status(row)
    rows = [
        row for row in rows
        if (view.apartment_id is None or row["apartment"]["id"] == view.apartment_id)
        and (not view.status or row["status"] == view.status)
    ]
    rows.sort(key=lambda row: (row["apartment"]["internal_name"] or "", row["apartment"]["id"]))

    # 0630: step 1 until the period is confirmed, then 2 (send and pay).
    for row in rows:
        if not row.get("unset"):
            row["step"] = (3 if row.get("paid_at") else 2) if row.get("frozen") else 1

    return render(request, "stay_fees.html", {
        "nav": "stay_fees",
        "periods": rows,
        "selected_month": selected_month,
        "has_properties": bool(apartments),
        "stay_fee_emails": stay_fee_auto.emails_enabled(owner_id),
        **_fee_links(_list_return(request)),
        **list_filter.context(
            view,
            action="/stay-fees",
            today=today,
            period_label_key="stay_fees.filter.period",
            properties=apartments,
            statuses=STAY_FEE_STATUSES,
        ),
    })


# 0077: the one normaliser for the stay-fee fields of _stay_fee_fields.html.
# The property save (admin._apartment_payload) uses it, so a field cannot be
# read two different ways.
FEE_ACCOUNT_RAW = "_stay_fee_account_raw"

# 0897: guest pays the stay fee. Phase 0 stores host settings only.
GUEST_RAILS = ("iban", "revolut", "cash")
GUEST_NOTE_MAX = 300
GUEST_LINK_RAW = "_stay_fee_guest_link_raw"
GUEST_LINK_INVALID = "stay_fee_guest_link_invalid"
GUEST_LINK_HOSTS = ("revolut.me", "revolut.com")
GUEST_OPERATOR_ACCOUNT_RAW = "_stay_fee_guest_operator_account_raw"
GUEST_OPERATOR_ACCOUNT_INVALID = "stay_fee_guest_operator_account_invalid"
GUEST_OPERATOR_ACCOUNT_STALE = "stay_fee_guest_operator_account_stale"
GUEST_OPERATOR_SAMPLE_VS = "1234567890"
GUEST_RATE_REQUIRED = "stay_fee_guest_rate_required"


def stay_fee_guest_pay_on() -> bool:
    """The kill switch, read at call time so tests and the template see the same value."""
    return bool(app_config.STAY_FEE_GUEST_PAY)


templates.env.globals["stay_fee_guest_pay_on"] = stay_fee_guest_pay_on


def revolut_link_ok(raw: str) -> bool:
    """https only, host revolut.me or revolut.com (or a subdomain), no userinfo, default port."""
    try:
        parts = urlsplit(raw.strip())
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        return False
    return any(host == base or host.endswith("." + base) for base in GUEST_LINK_HOSTS)


def guest_pay_values(form) -> dict:
    """The guest-pay fields as posted. Rails are a sorted csv of the allowed values."""
    posted = {"iban" if value == "qr" else value for value in form.getlist("stay_fee_guest_rails")}
    rails = sorted(value for value in posted if value in GUEST_RAILS)
    link = _form_str(form, "stay_fee_guest_revolut_link").strip()
    if link and revolut_link_ok(link) and "revolut" not in rails:
        rails.append("revolut")
        rails.sort()
    note = _form_str(form, "stay_fee_guest_cash_note")[:GUEST_NOTE_MAX].strip()
    default_rail = _form_str(form, "stay_fee_guest_default_rail")
    if default_rail == "qr":
        default_rail = "iban"
    if default_rail not in rails:
        default_rail = next((rail for rail in GUEST_RAILS if rail in rails), "")
    values = {
        "stay_fee_guest_default_rail": default_rail,
        "stay_fee_collect": 1 if _form_str(form, "stay_fee_collect") == "1" else 0,
        "stay_fee_guest_rails": ",".join(rails),
        "stay_fee_guest_revolut_link": link or None,
        "stay_fee_guest_cash_note": note or None,
        GUEST_LINK_RAW: link,
    }
    # HTML posts stay_fee_guest_operator_account; apply_guest_operator_account
    # only persists this internal key. Absent means leave the stored account.
    if "stay_fee_guest_operator_account" in form:
        values[GUEST_OPERATOR_ACCOUNT_RAW] = _form_str(form, "stay_fee_guest_operator_account")
    return values


def rate_from_default() -> str:
    """Today in Prague, ISO: the default and the minimum of the "applies from" field."""
    return claim.prague_today().isoformat()


def record_rate_change(apartment_id: int, new_rate, form, *, previous=None) -> None:
    """Store a dated rate row after a save that wrote stay_fee_rate_czk (1028).

    ``stay_fee_rate_from`` (ISO date) picks the first night of the new rate;
    empty, invalid or in the past means today: a rate never applies backwards.
    ``previous`` is the column before the save, kept for the earlier nights.
    An unchanged rate writes nothing.
    """
    today = claim.prague_today()
    new_rate = int(new_rate or 0)
    if previous is not None and int(previous or 0) == new_rate:
        return
    try:
        effective_from = date.fromisoformat(_form_str(form, "stay_fee_rate_from"))
    except ValueError:
        effective_from = today
    stay_fee_rate.record(apartment_id, new_rate, max(effective_from, today),
                         previous=previous, today=today)


def fee_form_values(form) -> dict:
    """Normalised fee fields. The account is left raw under FEE_ACCOUNT_RAW.

    The raw key is absent when an all-empty domestic form would otherwise
    wipe a stored IBAN-only account: the stored account is then kept.
    """
    rate = stay_fee.clamp_rate(_form_str(form, "stay_fee_rate_czk", "0"))
    values = {
        "stay_fee_rate_czk": rate,
        "stay_fee_vs": (
            "".join(ch for ch in _form_str(form, "stay_fee_vs") if ch.isdigit())[:10] or None
        ),
    }
    # 0239: the setup wizard no longer asks the period; a form without it keeps
    # the stored one (new properties start monthly, the database default).
    if "stay_fee_cadence" in form:
        cadence = _form_str(form, "stay_fee_cadence", "monthly")
        values["stay_fee_cadence"] = cadence if cadence in stay_fee.CADENCES else "monthly"
    # 0205: the setup wizard asks only rate, period, symbol and account, and no
    # form offers the payee or the instruction any more. These are written only
    # when the form carries them, so a shorter form never wipes stored values.
    for key, limit in (
        ("stay_fee_authority_name", 200),
        ("stay_fee_authority_address", 200),
        ("stay_fee_authority_contact", 200),
        ("stay_fee_payee", 60),
        ("stay_fee_instruction", 500),
    ):
        if key in form:
            values[key] = _form_str(form, key)[:limit].strip() or None
    if "stay_fee_authority_databox" in form:
        values["stay_fee_authority_databox"] = (
            validation.normalise_databox(_form_str(form, "stay_fee_authority_databox")) or None
        )
    if any(key in form for key in ("account_prefix", "account_number", "account_bank")):
        prefix = _form_str(form, "account_prefix")
        number = _form_str(form, "account_number")
        bank = _form_str(form, "account_bank")
        existing = _form_str(form, "_stay_fee_account_existing")
        if not payments.preserve_iban_only_account(existing, prefix, number, bank):
            values[FEE_ACCOUNT_RAW] = payments.compose_czech_account(prefix, number, bank)
    elif "stay_fee_council_account" in form:
        values[FEE_ACCOUNT_RAW] = _form_str(form, "stay_fee_council_account")
    # 0897: with the kill switch off, nothing is read and stored values stay as they are.
    if app_config.STAY_FEE_GUEST_PAY and "stay_fee_guest_form" in form:
        values.update(guest_pay_values(form))
    return values


def apply_fee_account(values: dict) -> None:
    """Turn the raw account into stored account/IBAN. Raise ValueError when invalid."""
    raw_link = values.pop(GUEST_LINK_RAW, None)
    if raw_link and not revolut_link_ok(raw_link):
        raise ValueError(GUEST_LINK_INVALID)
    raw = values.pop(FEE_ACCOUNT_RAW, None)
    if raw is None:
        return
    if raw.strip():
        values["stay_fee_council_account"], values["stay_fee_council_iban"] = (
            payments.normalise_account(raw)
        )
    else:
        values["stay_fee_council_account"] = None
        values["stay_fee_council_iban"] = None


def fee_account_draft(form) -> dict:
    """The account fields as typed, for the editor after a refused save."""
    return {
        "prefix": _form_str(form, "account_prefix"),
        "number": _form_str(form, "account_number"),
        "bank": _form_str(form, "account_bank"),
        "iban": "",
    }



def guest_pay_rails_need_account(rails_csv: str) -> bool:
    rails = {part for part in (rails_csv or "").split(",") if part}
    return "qr" in rails or "iban" in rails


def _entity_payment_account(entity) -> str:
    if not entity:
        return ""
    if not hasattr(entity, "get"):
        entity = dict(entity)
    if entity.get("iban"):
        return entity["iban"]
    if entity.get("bank_account"):
        return entity["bank_account"]
    return ""


def _as_entity_id(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _operator_id_after_save(apartment, values: dict):
    """The legal entity this save will leave on the property."""
    return _as_entity_id(values.get("legal_entity_id")) or _as_entity_id(
        apartment.get("legal_entity_id")
    )


def _operator_row(entity_id):
    entity_id = _as_entity_id(entity_id)
    if not entity_id:
        return None
    row = db.query_one(
        "SELECT id, bank_account, iban FROM legal_entity WHERE id = ?",
        (entity_id,),
    )
    if row is not None and not hasattr(row, "get"):
        row = dict(row)
    return row


def _account_iban(account: str) -> str:
    if not (account or "").strip():
        return ""
    try:
        return payments.normalise_account(account.strip())[1]
    except ValueError:
        return ""


def _posted_account_is_previous_prefill(apartment, values: dict, posted: str) -> bool:
    """True when the field still holds the previous operator's account.

    The property form always posts the box, prefilled from the operator that
    was on the property when the page rendered. Switching operator in the
    same save must not copy that value onto the new operator.
    """
    target_id = _operator_id_after_save(apartment, values)
    source_id = _as_entity_id(apartment.get("legal_entity_id"))
    if not posted or not source_id or source_id == target_id:
        return False
    posted_iban = _account_iban(posted)
    if not posted_iban:
        return False
    return posted_iban == _account_iban(_entity_payment_account(_operator_row(source_id)))


def _resolved_operator_account(entity, draft_account: str = "") -> tuple[str, str]:
    """Return (display account, iban-or-account for SPAYD) or empty strings when unknown."""
    from .. import payments

    raw = (draft_account or "").strip()
    if raw:
        try:
            _domestic, iban = payments.normalise_account(raw)
            return payments.format_iban(iban), iban
        except ValueError:
            return "", ""
    stored = _entity_payment_account(entity)
    if not stored:
        return "", ""
    if entity and entity.get("iban"):
        return payments.format_iban(stored), stored
    try:
        _domestic, iban = payments.normalise_account(stored)
        return payments.format_iban(iban), iban
    except ValueError:
        return stored, stored


def guest_pay_operator_context(
    apartment,
    entity,
    *,
    draft_account: str = "",
    sample_rate=None,
) -> dict:
    """Host preview for QR/bank-transfer rails: sample QR and the operator account."""
    from .. import payments

    if not hasattr(apartment, "get"):
        apartment = dict(apartment)
    if entity is not None and not hasattr(entity, "get"):
        entity = dict(entity)

    empty = {
        "needs_account": False,
        "has_account": False,
        "account_display": "",
        "preview_qr": "",
        "field_value": "",
        "existing_hidden": "",
    }
    if not stay_fee_guest_pay_on():
        return empty
    existing_hidden = _entity_payment_account(entity)
    shown = (entity.get("bank_account") if entity else "") or existing_hidden
    field_value = (draft_account or shown or "").strip()
    account_display, spayd_account = _resolved_operator_account(entity, draft_account)
    has_account = bool(spayd_account)
    preview_qr = ""
    if has_account:
        rate = int(sample_rate if sample_rate is not None else (apartment.get("stay_fee_rate_czk") or 0)) or 50
        sample_amount = min(max(rate, 1), 50)
        payload = payments.spayd(
            spayd_account,
            sample_amount,
            GUEST_OPERATOR_SAMPLE_VS,
            "Stay fee sample",
        )
        preview_qr = payments.qr_data_uri(payload)
    return {
        "needs_account": True,
        "has_account": has_account,
        "account_display": account_display,
        "preview_qr": preview_qr,
        "field_value": field_value,
        "existing_hidden": existing_hidden,
    }



GUEST_RAILS_REQUIRED = "stay_fee_guest_rails_required"
GUEST_REVOLUT_REQUIRED = "stay_fee_guest_revolut_required"
GUEST_SETUP_FLASH = {
    GUEST_RATE_REQUIRED: "flash.stay_fees.rate_required",
    GUEST_RAILS_REQUIRED: "flash.stay_fees.rails_required",
    GUEST_REVOLUT_REQUIRED: "flash.stay_fees.revolut_required",
}


def _operator_account_on_file(apartment, values: dict) -> bool:
    """A posted account for the operator this save will use, or one already stored."""
    posted = (values.get(GUEST_OPERATOR_ACCOUNT_RAW) or "").strip()
    if posted and not _posted_account_is_previous_prefill(apartment, values, posted):
        return True
    entity_id = _operator_id_after_save(apartment, values)
    if not entity_id:
        return False
    return bool(_entity_payment_account(_operator_row(entity_id)))


def check_guest_pay_setup(apartment, values: dict) -> None:
    """Asking guests to pay needs a fee rate, at least one way to pay, and a link for Revolut."""
    if not app_config.STAY_FEE_GUEST_PAY or not values.get("stay_fee_collect"):
        return
    if not hasattr(apartment, "get"):
        apartment = dict(apartment)
    rate = values.get("stay_fee_rate_czk", apartment.get("stay_fee_rate_czk"))
    try:
        rate = int(rate or 0)
    except (TypeError, ValueError):
        rate = 0
    if rate <= 0:
        raise ValueError(GUEST_RATE_REQUIRED)
    rails = {part for part in (values.get("stay_fee_guest_rails") or "").split(",") if part}
    if not rails:
        raise ValueError(GUEST_RAILS_REQUIRED)
    link = values.get("stay_fee_guest_revolut_link", apartment.get("stay_fee_guest_revolut_link"))
    if "revolut" in rails and not (link or values.get(GUEST_LINK_RAW)):
        raise ValueError(GUEST_REVOLUT_REQUIRED)
    if "iban" in rails and not _operator_account_on_file(apartment, values):
        raise ValueError(GUEST_OPERATOR_ACCOUNT_INVALID)


def apply_guest_operator_account(apartment, form, values: dict, request) -> None:
    """Persist the operator bank account when QR or bank transfer is enabled.

    Writes the account onto the operator this save will leave on the property
    (``values['legal_entity_id']`` when posted), not the operator still on the
    apartment row. A change of payout destination needs a fresh login (same
    rule as POST /entities/{id}/invoice). Re-posting the account already on
    file does not; the property form always sends the field.
    """
    from .. import db

    if not hasattr(apartment, "get"):
        apartment = dict(apartment)

    if not app_config.STAY_FEE_GUEST_PAY or not values.get("stay_fee_collect"):
        values.pop(GUEST_OPERATOR_ACCOUNT_RAW, None)
        return
    rails = values.get("stay_fee_guest_rails")
    if rails is None and "stay_fee_guest_form" in form:
        rails = guest_pay_values(form).get("stay_fee_guest_rails", "")
    if not guest_pay_rails_need_account(rails or ""):
        values.pop(GUEST_OPERATOR_ACCOUNT_RAW, None)
        return
    raw = values.pop(GUEST_OPERATOR_ACCOUNT_RAW, None)
    entity_id = _operator_id_after_save(apartment, values)
    if not entity_id:
        raise ValueError(GUEST_OPERATOR_ACCOUNT_INVALID)
    entity = _operator_row(entity_id)
    if not entity:
        raise ValueError(GUEST_OPERATOR_ACCOUNT_INVALID)
    if raw is None:
        if not _entity_payment_account(entity):
            raise ValueError(GUEST_OPERATOR_ACCOUNT_INVALID)
        return
    if not raw.strip():
        if _entity_payment_account(entity):
            return
        raise ValueError(GUEST_OPERATOR_ACCOUNT_INVALID)
    if _posted_account_is_previous_prefill(apartment, values, raw):
        # Leave the new operator's stored account alone; the typed box is
        # still the previous operator's prefill from page load.
        if not _entity_payment_account(entity):
            raise ValueError(GUEST_OPERATOR_ACCOUNT_INVALID)
        return
    from .invoices import apply_account_payload

    detail = {"bank_account": raw.strip()}
    if not apply_account_payload(detail, {}, entity, accept_parts=False):
        raise ValueError(GUEST_OPERATOR_ACCOUNT_INVALID)
    bank_account, iban = detail["bank_account"], detail["iban"]
    existing = _entity_payment_account(entity)
    if existing:
        try:
            _, existing_iban = payments.normalise_account(existing)
        except ValueError:
            existing_iban = ""
        if existing_iban == iban:
            return
    if not auth.session_is_fresh(request):
        raise ValueError(GUEST_OPERATOR_ACCOUNT_STALE)
    old_account = entity.get("bank_account") or ""
    old_iban = entity.get("iban") or ""
    db.update("legal_entity", entity_id, {"bank_account": bank_account, "iban": iban})
    old_tail = (old_iban or old_account)[-4:] or "none"
    new_tail = (iban or bank_account)[-4:]
    db.audit("guest_operator_account_changed", f"entity={entity_id} old=...{old_tail} new=...{new_tail}")



def fee_return_path(raw, apartment_id: int) -> str:
    """A validated way back to the fee list or this property's fee report, or ''."""
    path = security.safe_local_path(raw, "") if raw else ""
    if not path:
        return ""
    if path.split("?", 1)[0] in ("/stay-fees", f"/stay-fees/{apartment_id}"):
        return path
    return ""


def fee_settings_url(apartment_id: int, return_to: str = "") -> str:
    """The canonical fee editor: property Settings -> Reporting & fees -> Stay fee."""
    url = f"/apartments/{apartment_id}?view=settings&section=reporting"
    back = fee_return_path(return_to, apartment_id)
    if back:
        url += "&return_to=" + quote(back, safe="")
    return url + "#stay-fee-settings"


def fee_operator_url(apartment, return_to: str = "") -> str:
    """Where a missing payer is fixed: the assigned business, else the property's operator choice."""
    if apartment["legal_entity_id"]:
        return f"/entities?edit={apartment['legal_entity_id']}"
    url = f"/apartments/{apartment['id']}?view=settings&section=property"
    back = fee_return_path(return_to, apartment["id"])
    if back:
        url += "&return_to=" + quote(back, safe="")
    return url + "#settings-property"


def _list_return(request: Request) -> str:
    """This fee list with its period and filters (a one-off ?lang= is not kept)."""
    query = urlencode([(k, v) for k, v in request.query_params.multi_items() if k != "lang"])
    return "/stay-fees" + (f"?{query}" if query else "")


def _fee_links(return_to: str) -> dict:
    return {
        "fee_return": return_to,
        "fee_settings_url": fee_settings_url,
        "fee_operator_url": fee_operator_url,
    }


def fee_return_after_save(apartment, return_to: str) -> str:
    """Where a save that came from a fee page lands, or ''.

    A property whose rate is now 0 has no report to open, so its report
    link falls back to the fee list of the same month.
    """
    back = fee_return_path(return_to, apartment["id"])
    if not back:
        return ""
    split = urlsplit(back)
    if split.path != "/stay-fees" and not stay_fee.is_active(apartment):
        month = stay_fee.parse_month(dict(parse_qsl(split.query)).get("month"))
        return f"/stay-fees?month={stay_fee.month_key(month)}" if month else "/stay-fees"
    return back


@router.get("/stay-fees/pdfs.zip")
def stay_fee_pdfs_zip(request: Request):
    """0846: every saved report of one month in one ZIP, the same bytes as each PDF button."""
    guard = auth.require_login(request)
    if guard:
        return guard
    today = claim.prague_today()
    month = stay_fee.parse_month(request.query_params.get("month")) or _default_month(today)
    if month > today.replace(day=1):
        month = _default_month(today)
    apartments = db.query(
        f"SELECT * FROM apartment WHERE {db.null_safe_eq('owner_user_id')} AND archived_at IS NULL "
        "ORDER BY internal_name, id",
        (access.owner_id(request),),
    )
    buffer = io.BytesIO()
    names = set()
    count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for apartment in apartments:
            row = stay_fee_filing.covering(apartment["id"], month)
            if not row:
                continue
            name = f'hlaseni-poplatek-z-pobytu-{row["period_key"]}-{stay_fee.vs_of(apartment)}-{apartment["id"]}.pdf'
            if name in names:
                continue
            names.add(name)
            archive.writestr(name, stay_fee_filing.pdf_bytes(row))
            count += 1
    if not count:
        return _back(f"/stay-fees?month={stay_fee.month_key(month)}", err=_flash(request, "flash.stay_fees.not_saved"))
    db.audit("stay_fee_pdf_zip", f"month={stay_fee.month_key(month)} files={count}")
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="poplatek-z-pobytu-{stay_fee.month_key(month)}.zip"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/stay-fees/{apartment_id}")
def stay_fee_detail(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    today = claim.prague_today()
    default_month = _default_month(today)
    selected_month = stay_fee.parse_month(request.query_params.get("month"))
    if selected_month is None:
        selected_month = default_month
    elif selected_month > today.replace(day=1):
        return RedirectResponse(
            f"/stay-fees/{apartment_id}?month={stay_fee.month_key(default_month)}",
            status_code=303,
        )

    apartment = access.apartment(request, apartment_id)
    if not apartment or (
        not stay_fee.is_active(apartment)
        and not stay_fee_filing.covering(apartment["id"], selected_month)
    ):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))

    correcting = request.query_params.get("correct") == "1"
    sealed = stay_fee_filing.covering(apartment["id"], selected_month) if correcting else None
    if correcting and sealed:
        period = stay_fee.property_period(
            apartment,
            stay_fee_filing.period_anchor(sealed),
            live_only=True,
            cadence=sealed["cadence"],
            rate=stay_fee_filing.correction_rate(apartment, sealed),
        )
    else:
        period = stay_fee.property_period(apartment, selected_month, live_only=correcting)
    group = stay_fee.report_group(
        apartment, selected_month, live_only=correcting, period=period
    )
    frozen = bool(period and period.get("frozen") and not correcting)
    issues: list[str] = []
    if not frozen:
        issues = stay_fee.report_issues(group, today)
        if stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"], period):
            issues.append("stay_fees.issue.unsigned")
        issues = list(dict.fromkeys(issues))
    pay = stay_fee.payment_details(group) if frozen else None
    filing_row = stay_fee_filing.covering(apartment["id"], selected_month) if frozen else None
    send_panel = _send_panel_context(apartment, period, group, filing_row) if filing_row else None
    return render(request, "stay_fee_detail.html", {
        "nav": "stay_fees",
        "apartment": apartment,
        **_detail_filter(selected_month, today, apartment_id),
        "period": period,
        "group": group,
        "ui_period": _ui_period_label(request, group["cadence"], selected_month),
        "issues": issues,
        "pay": pay,
        "others": [],
        "key": _period_key(group["cadence"], selected_month),
        "lines": _guest_lines(apartment, period) if period else [],
        "total_display": stay_fee.format_czk(group["total_czk"]),
        "frozen": frozen,
        "correcting": correcting,
        "filing_version": period.get("version") if period else None,
        "exempt_categories": stay_fee.EXEMPT_CATEGORIES,
        "send_panel": send_panel,
        "filing_row": filing_row,
        **_fee_links(f"/stay-fees/{apartment_id}?month={stay_fee.month_key(selected_month)}"),
    })


def _operator_line(apartment) -> str:
    entity = None
    entity_id = apartment["legal_entity_id"]
    if entity_id:
        entity = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    name = (entity["name"] if entity else "") or (apartment["internal_name"] or "")
    ico = (entity["ico"] if entity else "") or ""
    if ico.strip():
        return f"{name}, IČO {ico.strip()}"
    return name


def _send_panel_context(apartment, period, group, filing_row: dict) -> dict:
    period_label = period["label"] if period else ""
    property_name = apartment["internal_name"] or ""
    subject_cs = f"Ohlášení poplatku z pobytu – {period_label} – {property_name}"
    amount = stay_fee.format_czk(group["total_czk"])
    body_cs = "\n".join([
        _operator_line(apartment),
        period_label,
        f"Částka k úhradě: {amount}. Podrobnosti v příloze.",
    ])
    return {
        "filing_id": filing_row["id"],
        "authority_name": apartment["stay_fee_authority_name"] or "",
        "databox": apartment["stay_fee_authority_databox"] or "",
        "subject_cs": subject_cs,
        "body_cs": body_cs,
    }


def _guest_lines(apartment, period):
    """The property's own guest rows, with the status and the local-resident hint."""
    lines = []
    ids = [line["guest_id"] for line in period["lines"]]
    facts = {}
    if ids:
        marks = ",".join("?" for _ in ids)
        # Display only: birth date, age and nationality are read, never stored on the line.
        for row in db.query(
            "SELECT g.id, g.birth_date_enc, g.nationality, COALESCE(g.stay_from, r.date_from) AS check_in "
            f"FROM guest g JOIN reservation r ON r.id = g.reservation_id WHERE g.id IN ({marks})",
            tuple(ids),
        ):
            birth = validation.parse_birth_date(row["birth_date"] or "")
            check_in = validation.parse_iso_date(row["check_in"])
            facts[row["id"]] = {
                "birth_display": validation.display_birth_date(row["birth_date"]) if row["birth_date"] else "",
                "age_at_check_in": validation.age_on(birth, check_in) if birth and check_in else None,
                "nationality": row["nationality"] or "",
            }
    for line in period["lines"]:
        if "res_country" in line:
            guest = line
        else:
            guest = db.query_one("SELECT * FROM guest WHERE id = ?", (line["guest_id"],))
        local_hint = bool(
            guest
            and (guest["res_country"] or "").upper() == validation.CZECH_CODE
            and _fold_place(guest["res_city"])
            and _fold_place(guest["res_city"]) == _fold_place(apartment["addr_obec"])
            and not line.get("auto_obec_resident")
        )
        if line["status"] == "liable":
            status_key = "stay_fees.status.liable"
        elif line["auto_minor"]:
            status_key = "stay_fees.status.under_18"
        elif line["status"] == "exempt":
            status_key = "stay_fees.status.exempt"
        else:
            status_key = "stay_fees.status.not_subject"
        # 1031: the amount guest_period/property_period computed for this guest (per night
        # rates across a rate change); no second flat-rate calculation here.
        amount = line["amount_czk"]
        lines.append({
            **line,
            **facts.get(line["guest_id"], {"birth_display": "", "age_at_check_in": None, "nationality": ""}),
            "amount_czk": amount,
            "status_key": status_key,
            "amount_display": stay_fee.format_czk(amount),
            "local_hint": local_hint,
            "obec_resident": bool(line.get("auto_obec_resident")),
            "review": bool(line.get("auto_minor") or local_hint),
        })
    return lines


@router.get("/stay-fees/{apartment_id}/pdf")
def stay_fee_pdf_download(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    today = claim.prague_today()
    default_month = _default_month(today)
    selected_month = stay_fee.parse_month(request.query_params.get("month"))
    if selected_month is None:
        selected_month = default_month
    elif selected_month > today.replace(day=1):
        return RedirectResponse(
            f"/stay-fees/{apartment_id}/pdf?month={stay_fee.month_key(default_month)}",
            status_code=303,
        )

    apartment = access.apartment(request, apartment_id)
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(selected_month)}"
    row = stay_fee_filing.covering(apartment["id"], selected_month) if apartment else None
    if not apartment or (not row and not stay_fee.is_active(apartment)):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    if not row:
        return _back(back_path, err=_flash(request, "flash.stay_fees.not_saved"))
    pdf = stay_fee_filing.pdf_bytes(row)
    db.audit(
        "stay_fee_pdf",
        f"apartment_id={apartment['id']} period={row['period_key']} total={row['total_due_czk']}",
    )
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="hlaseni-poplatek-z-pobytu-{row["period_key"]}-'
                f'{stay_fee.vs_of(apartment)}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get("/stay-fees/{apartment_id}/csv")
def stay_fee_csv_download(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    # The register CSV lists every guest's document number.
    if not access.identity_visible(request):
        return _back(
            f"/stay-fees/{apartment_id}",
            err=_flash(request, "flash.error.identity_hidden_export"),
        )

    today = claim.prague_today()
    default_month = _default_month(today)
    selected_month = stay_fee.parse_month(request.query_params.get("month"))
    if selected_month is None:
        selected_month = default_month
    elif selected_month > today.replace(day=1):
        return RedirectResponse(
            f"/stay-fees/{apartment_id}/csv?month={stay_fee.month_key(default_month)}",
            status_code=303,
        )

    apartment = access.apartment(request, apartment_id)
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(selected_month)}"
    row = stay_fee_filing.covering(apartment["id"], selected_month) if apartment else None
    if not apartment or (not row and not stay_fee.is_active(apartment)):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    if not row:
        return _back(back_path, err=_flash(request, "flash.stay_fees.not_saved"))
    data = stay_fee_filing.csv_bytes(row)
    db.audit("stay_fee_csv", f"apartment_id={apartment['id']} period={row['period_key']} sealed=1")
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="evidencni-kniha-{row["period_key"]}-{apartment_id}.csv"'
            ),
            "Cache-Control": "no-store",
        },
    )


def _adjustment_bed_days(form) -> int:
    mode = _form_str(form, "mode")
    if mode == "people":
        people = int(_form_str(form, "people") or "0")
        nights = int(_form_str(form, "nights") or "0")
        if people < 1 or people > 99 or nights < 1 or nights > 366:
            raise ValueError("range")
        return people * nights
    days = int(_form_str(form, "bed_days") or "0")
    if days < 1 or days > 9999:
        raise ValueError("range")
    return days


@router.post("/stay-fees/{apartment_id}/adjustment")
async def stay_fee_adjustment_add(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not stay_fee.is_active(apartment):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    back = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    correcting = _form_str(form, "correct") == "1"
    # A correction must keep the sealed period's cadence and key. The live
    # property cadence can change after filing (monthly → quarterly); using
    # it here would store the row under 2026-Q3 while finalize still reads
    # 2026-08, so the remitted total would omit the adjustment.
    sealed = stay_fee_filing.covering(apartment["id"], month) if correcting else None
    if correcting:
        if not sealed:
            return _back(back, err=_flash(request, "flash.stay_fees.report_blocked"))
        back = f"{back}&correct=1"
        cadence = sealed["cadence"]
        calc_month = stay_fee_filing.period_anchor(sealed)
        period = stay_fee.property_period(
            apartment, calc_month, live_only=True, cadence=cadence,
            rate=stay_fee_filing.correction_rate(apartment, sealed),
        )
        key = stay_fee_filing.period_key(cadence, calc_month)
    else:
        period = stay_fee.property_period(apartment, month)
        if period and period.get("frozen"):
            return _back(back, err=_flash(request, "flash.stay_fees.adjust_frozen"))
        key = stay_fee_filing.period_key(stay_fee.cadence_of(apartment), month)
    direction = _form_str(form, "direction")
    mode = _form_str(form, "mode")
    reason = _form_str(form, "reason").strip()
    if direction not in ("add", "remove") or mode not in ("people", "bed_days") or len(reason) < 3:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_invalid"))
    try:
        days = _adjustment_bed_days(form)
    except ValueError:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_invalid"))
    current = stay_fee_adjustment.net_bed_days(apartment_id, key)
    guest_nights = int((period or {}).get("guest_liable_nights") or 0)
    delta = days if direction == "add" else -days
    if guest_nights + current + delta < 0:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_negative"))
    stay_fee_adjustment.add(
        apartment_id=apartment_id,
        period_key=key,
        direction=direction,
        mode=mode,
        people_count=int(_form_str(form, "people") or "0") if mode == "people" else 0,
        nights=int(_form_str(form, "nights") or "0") if mode == "people" else 0,
        bed_days=days,
        reason=reason[:200],
        created_by=access.owner_id(request),
    )
    db.audit(
        "stay_fee_adjustment",
        f"apartment_id={apartment_id} period={key} direction={direction} days={days}",
    )
    return _back(back, msg=_flash(request, "flash.stay_fees.saved"))


@router.post("/stay-fees/{apartment_id}/adjustment/{adjustment_id}/undo")
async def stay_fee_adjustment_undo(apartment_id: int, adjustment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    row = db.query_one(
        "SELECT * FROM stay_fee_adjustment WHERE id = ? AND apartment_id = ?",
        (adjustment_id, apartment_id),
    )
    back = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    if row and row["filing_id"]:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_sealed"))
    if row and not row["reversed_at"]:
        stay_fee_adjustment.reverse(adjustment_id, access.owner_id(request))
        db.audit("stay_fee_adjustment_undo", f"id={adjustment_id}")
        return _back(back, msg=_flash(request, "flash.stay_fees.saved"))
    return _back(back)


@router.post("/stay-fees/guest-decision")
async def stay_fee_guest_decision(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    form = await request.form()
    apartment_id = _form_str(form, "apartment_id")
    apartment = (
        access.apartment(request, int(apartment_id)) if apartment_id.isdigit() else None
    )
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(
        claim.prague_today()
    )
    back_path = (
        f"/stay-fees/{apartment['id']}?month={stay_fee.month_key(month)}#guests"
        if apartment else "/stay-fees"
    )

    guest_id = _form_str(form, "guest_id")
    guest = access.guest(request, int(guest_id)) if guest_id.isdigit() else None
    reservation = access.reservation(request, guest["reservation_id"]) if guest else None
    if not apartment or not guest or not reservation or reservation["apartment_id"] != apartment["id"]:
        return _back(back_path, err=_flash(request, "flash.error.no_such_guest"))

    decision = _form_str(form, "decision")
    if decision not in ("",) + stay_fee.DECISIONS:
        decision = ""
    reason = _form_str(form, "reason")[:stay_fee.REASON_MAX].strip()
    reference = _form_str(form, "reason_reference")[:200].strip()
    if decision == "exempt":
        if reason not in stay_fee.EXEMPT_CATEGORIES:
            return _back(back_path, err=_flash(request, "flash.stay_fees.reason_required"))
        if reason == "local_rule" and len(reference) < 3:
            return _back(back_path, err=_flash(request, "flash.stay_fees.reason_required"))
    else:
        reason = ""
        reference = ""

    db.update("guest", guest["id"], {
        "fee_host_decision": decision or None,
        "fee_host_reason": (reason if decision == "exempt" else None),
        "fee_host_reason_reference": (reference if decision == "exempt" else None),
        "updated_at": db.utcnow(),
    })
    # The reason stays out of the audit row: the register keeps it, the log does not.
    db.audit("stay_fee_decision", f"guest_id={guest['id']} decision={decision or 'auto'}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.saved"))


@router.post("/stay-fees/{apartment_id}/scope-ruling")
async def stay_fee_scope_ruling(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    rule = _form_str(form, "rule")
    reference = _form_str(form, "reference")[:200].strip()
    if rule not in stay_fee.SCOPE_RULES or len(reference) < 3:
        return _back(back_path, err=_flash(request, "flash.stay_fees.scope_invalid"))
    db.update("apartment", apartment["id"], {
        "stay_fee_scope_rule": rule,
        "stay_fee_scope_reference": reference,
    })
    db.audit("stay_fee_scope", f"apartment_id={apartment['id']} rule={rule}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.saved"))


@router.post("/stay-fees/confirm-ready")
async def stay_fee_confirm_ready(request: Request):
    """0845: seal every listed property's ready period for one month, one tap.

    Same sealing as the job (stay_fee_auto.confirm), which equals the list's
    "Ano, sedí": collected = the calculated amount per guest. A blocked or
    already saved period is skipped, never changed.
    """
    guard = auth.require_login(request)
    if guard:
        return guard
    today = claim.prague_today()
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(today)
    if month > today.replace(day=1):
        month = _default_month(today)
    back_path = fee_return_path(_form_str(form, "return_to"), 0) or "/stay-fees"
    saved = 0
    seen = set()
    for raw in form.getlist("apartment_id"):
        text = str(raw).strip()
        if not text.isdigit() or text in seen:
            continue
        seen.add(text)
        apartment = access.apartment(request, int(text))
        if not stay_fee.is_active(apartment) or apartment["archived_at"] or not apartment["active"]:
            continue
        if stay_fee_auto.confirm(apartment, month, today, audit_event="stay_fee_finalize"):
            saved += 1
    if not saved:
        return _back(back_path, err=_flash(request, "flash.stay_fees.bulk_none"))
    return _back(back_path, msg=_flash(request, "flash.stay_fees.bulk_saved", count=saved))


@router.post("/stay-fees/{apartment_id}/copy-setup")
async def stay_fee_copy_setup(apartment_id: int, request: Request):
    """0847: one tap takes over the fee setup the host was shown on the list."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    back_path = fee_return_path(_form_str(form, "return_to"), apartment_id) or "/stay-fees"
    raw = _form_str(form, "source_id")
    source = access.apartment(request, int(raw)) if raw.isdigit() else None
    has_filing = db.query_one("SELECT id FROM stay_fee_filing WHERE apartment_id = ?", (apartment["id"],))
    if (
        not source
        or source["archived_at"]
        or stay_fee.is_active(apartment)
        or has_filing
        or fee_copy_source(apartment, [source]) is None
    ):
        return _back(back_path, err=_flash(request, "flash.stay_fees.copy_failed"))
    db.update("apartment", apartment["id"], {key: source[key] for key in FEE_COPY_FIELDS})
    db.audit("stay_fee_copy_setup", f"apartment_id={apartment['id']} source_id={source['id']}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.copy_done", name=source["internal_name"] or ""))


@router.post("/stay-fees/{apartment_id}/finalize")
async def stay_fee_finalize(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    today = claim.prague_today()
    apartment = access.apartment(request, apartment_id)
    if not stay_fee.is_active(apartment):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(today)
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    # 0203: the confirm button on the fee list comes back to the list.
    back_path = fee_return_path(_form_str(form, "return_to"), apartment_id) or back_path
    correcting = _form_str(form, "correct") == "1"
    sealed = stay_fee_filing.covering(apartment["id"], month)
    if correcting:
        if not sealed:
            return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
        cadence = sealed["cadence"]
        calc_month = stay_fee_filing.period_anchor(sealed)
    else:
        cadence = stay_fee.cadence_of(apartment)
        calc_month = month
    checked = stay_fee_auto.check(
        apartment, calc_month, today, cadence=cadence,
        rate=stay_fee_filing.correction_rate(apartment, sealed) if correcting else None,
    )
    period, group, issues = checked["period"], checked["group"], checked["issues"]
    if issues:
        return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
    key = stay_fee_filing.period_key(group["cadence"], group["first"])
    if stay_fee_filing.latest(apartment["id"], key) and not correcting:
        return _back(back_path, err=_flash(request, "flash.stay_fees.already_saved"))
    # The total must be calculated the same way it was checked: per night at
    # the dated rates, or a legacy flat period at its sealed rate (1028).
    rate = stay_fee_filing.correction_rate(apartment, sealed) if correcting else None
    collected: dict[int, int] = {}
    if period:
        for line in period["lines"]:
            field = f"collected_{line['guest_id']}"
            raw = _form_str(form, field)
            parsed = stay_fee.parse_czk_int(raw) if raw else None
            if raw and parsed is None:
                return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
            collected[line["guest_id"]] = parsed if parsed is not None else line["amount_czk"]
        if period["lines"] and _form_str(form, "confirm_collected") != "1":
            return _back(back_path, err=_flash(request, "flash.stay_fees.confirm_collected"))
    try:
        stay_fee_filing.save(
            apartment,
            group["first"],
            rate_czk=rate,
            collected=collected,
            issued_on=today,
            cadence=group["cadence"],
            replacing_id=sealed["id"] if correcting else None,
        )
    except ValueError:
        return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
    except db.integrity_errors():
        return _back(back_path, err=_flash(request, "flash.stay_fees.already_saved"))
    db.audit("stay_fee_finalize", f"apartment_id={apartment['id']} period={key}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.period_saved"))



@router.post("/stay-fees/{apartment_id}/paid")
async def stay_fee_mark_paid(apartment_id: int, request: Request):
    """The host confirms the period is sent and paid: closes the pay step."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    back_path = fee_return_path(_form_str(form, "return_to"), apartment_id) or f"/stay-fees?month={stay_fee.month_key(month)}"
    sealed = stay_fee_filing.covering(apartment["id"], month)
    if not sealed:
        return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
    if not sealed["paid_at"]:
        now = db.utcnow()
        db.update("stay_fee_filing", sealed["id"], {"paid_at": now, "sent_at": sealed["sent_at"] or now})
        db.audit("stay_fee_paid", f"apartment_id={apartment['id']} period={sealed['period_key']}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.paid"))


def _filing_for_month(apartment_id: int, month: date, filing_id: int):
    row = db.query_one(
        "SELECT * FROM stay_fee_filing WHERE id = ? AND apartment_id = ? AND superseded_at IS NULL",
        (filing_id, apartment_id),
    )
    if not row:
        return None
    keys = stay_fee_filing.overlap_keys(row["cadence"], month)
    if row["period_key"] not in keys:
        return None
    return row


@router.post("/stay-fees/{apartment_id}/filings/{filing_id}/sent")
async def stay_fee_mark_filing_sent(apartment_id: int, filing_id: int, request: Request):
    """Idempotent: records that the host sent the filing (manual tracking)."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    back = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    row = _filing_for_month(apartment_id, month, filing_id)
    if not row:
        return _back(back, err=_flash(request, "flash.stay_fees.report_blocked"))
    if not row["sent_at"]:
        db.update("stay_fee_filing", row["id"], {"sent_at": db.utcnow()})
        db.audit("stay_fee_sent", f"apartment_id={apartment_id} filing_id={row['id']}")
    return _back(back, msg=_flash(request, "flash.stay_fees.marked_sent"))


@router.post("/stay-fees/{apartment_id}/filings/{filing_id}/paid")
async def stay_fee_mark_filing_paid(apartment_id: int, filing_id: int, request: Request):
    """Idempotent: records payment; also sets sent when missing."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    back = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    row = _filing_for_month(apartment_id, month, filing_id)
    if not row:
        return _back(back, err=_flash(request, "flash.stay_fees.report_blocked"))
    now = db.utcnow()
    if not row["paid_at"]:
        db.update(
            "stay_fee_filing", row["id"],
            {"paid_at": now, "sent_at": row["sent_at"] or now},
        )
        db.audit("stay_fee_paid_detail", f"apartment_id={apartment_id} filing_id={row['id']}")
    return _back(back, msg=_flash(request, "flash.stay_fees.marked_paid"))
