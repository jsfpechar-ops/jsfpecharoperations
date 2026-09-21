"""Guest-facing routes reached through the apartment permalink.

The permalink is the only workable trigger, because an iCal feed carries no
e-mail address to write to. The host pastes one link into the automated
message template on Airbnb or Booking.com; the guest opens it, finds their own
stay among the few that start soon, and fills in the party.

Access control is deliberately narrow: the token identifies the apartment, and
only stays inside the host's visibility window are reachable through it, so an
old guest cannot browse current bookings. A signed cookie remembers which
records this browser created, so one member of a party never sees another
guest's personal data.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlsplit, urlunsplit

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer

import posixpath
import re
from .. import alerts, auth, claim, codelists, config, db, i18n, mail, passport_photos, rate_limit, reporting, security, turnstile, validation
from ..templating import render_guest

router = APIRouter()

LANG_COOKIE = "ubyhost_lang"
OWNED_COOKIE = "ubyhost_owned"
CLAIM_COOKIE = "ubyhost_claim"

CS_VALIDATION_MESSAGES = {
    "Date of birth is required.": "Datum narození je povinné.",
    "Enter the full date as DD/MM/YYYY.": "Zadejte celé datum ve formátu DD/MM/RRRR.",
    "Year must be 1900 or later.": "Rok musí být 1900 nebo pozdější.",
    "Month must be between 01 and 12.": "Měsíc musí být mezi 01 a 12.",
    "Day must be between 01 and 31.": "Den musí být mezi 01 a 31.",
    "That date does not exist - please check day and month.": "Toto datum neexistuje – zkontrolujte den a měsíc.",
    "Date of birth cannot be after your arrival date.": "Datum narození nemůže být po datu příjezdu.",
    "Date of birth cannot be in the future.": "Datum narození nemůže být v budoucnosti.",
    "Surname is required.": "Příjmení je povinné.",
    "Given name looks missing - please check the passport.": "Křestní jméno zřejmě chybí – zkontrolujte pas.",
    "Nationality is required.": "Státní příslušnost je povinná.",
    "Travel document number is required.": "Číslo cestovního dokladu je povinné.",
    "Street and number are required.": "Ulice a číslo jsou povinné.",
    "City is required.": "Město je povinné.",
    "Country is required.": "Země je povinná.",
    "Unknown country code.": "Neznámý kód země.",
    "Unknown purpose-of-stay code.": "Neznámý účel pobytu.",
    "Purpose of stay is required.": "Účel pobytu je povinný.",
    "Remove the | character and any line breaks.": (
        "Odstraňte znak | a všechny konce řádků."
    ),
    "Departure date must be later than the arrival date.": "Datum odjezdu musí být po datu příjezdu.",
    validation.NON_LATIN_MESSAGE: (
        "Zapište latinkou (A–Z) přesně tak, jak je to vytištěno ve dvou strojově "
        "čitelných řádcích na konci vašeho pasu."
    ),
    # Built from the same constants as the English text so the two cannot drift
    # apart when a field limit changes.
    f"Surname must be at most {validation.MAX_SURNAME} characters.": (
        f"Příjmení může mít nejvýše {validation.MAX_SURNAME} znaků. Zkraťte ho, "
        "prosím, podle pasu."
    ),
    f"Given name must be at most {validation.MAX_FIRST_NAME} characters.": (
        f"Jméno může mít nejvýše {validation.MAX_FIRST_NAME} znaků. Uveďte, prosím, "
        "jen první jména z pasu."
    ),
    f"Document number must be at least {validation.MIN_DOC} characters.": (
        f"Číslo dokladu musí mít alespoň {validation.MIN_DOC} znaků."
    ),
    f"Document number must be at most {validation.MAX_DOC} characters.": (
        f"Číslo dokladu může mít nejvýše {validation.MAX_DOC} znaků."
    ),
    f"Visa number must be at most {validation.MAX_VISA} characters.": (
        f"Číslo víza může mít nejvýše {validation.MAX_VISA} znaků."
    ),
    f"Street must be at most {validation.MAX_RESIDENCE_PART} characters.": (
        f"Ulice může mít nejvýše {validation.MAX_RESIDENCE_PART} znaků."
    ),
    f"City must be at most {validation.MAX_RESIDENCE_PART} characters.": (
        f"Město může mít nejvýše {validation.MAX_RESIDENCE_PART} znaků."
    ),
    "Street cannot consist of digits only.": "Ulice nemůže obsahovat jen číslice.",
    "City cannot consist of digits only.": "Město nemůže obsahovat jen číslice.",
    "Home address is too long.": "Adresa bydliště je příliš dlouhá.",
    f"Note must be at most {validation.MAX_NOTE} characters.": (
        f"Poznámka může mít nejvýše {validation.MAX_NOTE} znaků."
    ),
    "For a child recorded in a parent's passport the note must contain "
    "the parent's document number.": (
        "U dítěte zapsaného v pasu rodiče musí poznámka obsahovat číslo dokladu rodiče."
    ),
}

# The nationality message embeds the code the guest typed, so it cannot be a
# dictionary key.
_CS_VALIDATION_PATTERNS = (
    (
        re.compile(r"^'(?P<code>.*)' is not a valid three-letter country code\.$"),
        "„{code}“ není platný třímístný kód země (např. GBR, USA, DEU).",
    ),
)

CS_PASSPORT_UPLOAD_MESSAGES = {
    "Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF "
    "(for example a registration form with up to 11 guests).": (
        "Nahrajte fotografii pasu (JPEG, PNG, WebP) nebo PDF "
        "(např. registrační formulář až pro 11 hostů)."
    ),
    "The uploaded file looks empty.": "Nahraný soubor vypadá prázdně.",
    "The PDF is too large. Use a file under 15 MB.": "PDF je příliš velké. Maximálně 15 MB.",
    "The file does not look like a valid PDF.": "Soubor nevypadá jako platné PDF.",
    "The photo is too large. Use a file under 5 MB.": "Fotografie je příliš velká. Maximálně 5 MB.",
    "The file does not look like a valid image.": "Soubor nevypadá jako platný obrázek.",
}


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(config.SECRET_KEY, salt="ubyhost-guest-owned")


def _claim_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(config.SECRET_KEY, salt="ubyhost-guest-claim")


def _language(request: Request) -> str:
    return i18n.normalise_language(
        request.query_params.get("lang") or request.cookies.get(LANG_COOKIE) or ""
    )


def _owned_ids(request: Request) -> List[int]:
    raw = request.cookies.get(OWNED_COOKIE)
    if not raw:
        return []
    try:
        value = _serializer().loads(raw)
        return [int(v) for v in value] if isinstance(value, list) else []
    except (BadSignature, ValueError, TypeError):
        return []


def _remember_owned(response, guest_ids: List[int]) -> None:
    unique = sorted({int(g) for g in guest_ids})[-40:]
    response.set_cookie(
        OWNED_COOKIE,
        _serializer().dumps(unique),
        max_age=60 * 60 * 24 * 60,
        httponly=True,
        samesite="lax",
        secure=config.PUBLIC_BASE_URL.lower().startswith("https://"),
        path="/",
    )


def _claimed_reservation_ids(request: Request) -> List[int]:
    raw = request.cookies.get(CLAIM_COOKIE)
    if not raw:
        return []
    try:
        value = _claim_serializer().loads(raw)
        return [int(v) for v in value] if isinstance(value, list) else []
    except (BadSignature, ValueError, TypeError):
        return []


def _remember_claim(response, reservation_id: int, request: Optional[Request] = None) -> None:
    known = _claimed_reservation_ids(request) if request else []
    unique = sorted({*known, int(reservation_id)})[-40:]
    response.set_cookie(
        CLAIM_COOKIE,
        _claim_serializer().dumps(unique),
        max_age=60 * 60 * 24 * 60,
        httponly=True,
        samesite="lax",
        secure=config.PUBLIC_BASE_URL.lower().startswith("https://"),
        path="/",
    )


def _with_lang(response, lang: str):
    response.set_cookie(
        LANG_COOKIE,
        lang,
        max_age=60 * 60 * 24 * 60,
        samesite="lax",
        secure=config.PUBLIC_BASE_URL.lower().startswith("https://"),
        path="/",
    )
    return response


def _safe_return_to(requested: Optional[str], token: str, lang: str) -> str:
    """Only ever bounce back inside this apartment's own permalink.

    A plain ``startswith`` check passes ``/l/{token}/../../somewhere-else``,
    so the path is normalised before it is compared.
    """
    fallback = _guest_link(token) + _lang_q(lang)
    raw = security.safe_local_path(requested, "")
    if not raw:
        return fallback
    split = urlsplit(raw)
    if split.scheme or split.netloc:
        return fallback
    path = posixpath.normpath(split.path)
    prefix = _guest_link(token)
    if path != prefix and not path.startswith(prefix + "/"):
        return fallback
    return urlunsplit(("", "", path, split.query, ""))


def _localize_message(message: str) -> str:
    translated = CS_VALIDATION_MESSAGES.get(message)
    if translated:
        return translated
    for pattern, template in _CS_VALIDATION_PATTERNS:
        match = pattern.match(message)
        if match:
            return template.format(**match.groupdict())
    return message


def _localize_issues(issues, lang: str):
    if lang != "cs":
        return issues
    return [
        validation.Issue(issue.field, _localize_message(issue.message), issue.severity)
        for issue in issues
    ]


def _apartment_by_token(token: str):
    row = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ? AND active = 1 "
        "AND archived_at IS NULL",
        (token,),
    )
    if not row:
        return None
    if not row["permalink_pin"]:
        pin = auth.new_permalink_pin()
        db.update("apartment", row["id"], {"permalink_pin": pin})
        return db.query_one("SELECT * FROM apartment WHERE id = ?", (row["id"],))
    return row


def _pin_page(request: Request, token: str, lang: str, error: str = ""):
    failures = rate_limit.pin_failure_count(rate_limit.client_key(request, token))
    apartment = _apartment_by_token(token)
    context = _shared(request, token, lang, apartment)
    context.update(
        {
            "error": error,
            "require_turnstile": failures >= 3,
            "return_to": request.url.path
            + (("?" + str(request.url.query)) if request.url.query else ""),
        }
    )
    return _with_lang(render_guest(request, "guest/pin.html", context), lang)


def _host_owns_apartment(request: Request, apartment) -> bool:
    """Signed-in host filling the guest form for their own property."""
    if not apartment:
        return False
    workspace = auth.workspace_user(request)
    if not workspace:
        return False
    owner = apartment["owner_user_id"]
    return owner is not None and int(owner) == int(workspace["id"])


def _require_pin(request: Request, token: str, lang: str):
    if not config.GUEST_PIN_REQUIRED:
        return None
    apartment = _apartment_by_token(token)
    if apartment and (
        _host_owns_apartment(request, apartment)
        or auth.pin_session_valid(request, token, apartment["permalink_pin"] or "")
    ):
        return None
    return _pin_page(request, token, lang)


def _visible_reservations(apartment) -> List[Any]:
    """Stays a guest may pick: arriving today through the lead window."""
    window = apartment["permalink_window_days"] or 2
    today = claim.prague_today()
    horizon = (today + timedelta(days=window)).isoformat()
    return db.query(
        "SELECT r.* FROM reservation r "
        "LEFT JOIN reservation_claim c ON c.reservation_id = r.id "
        "WHERE r.apartment_id = ? AND r.status = 'active' "
        "AND r.archived_at IS NULL "
        "AND r.date_from >= ? AND r.date_from <= ? "
        "AND c.guest_access_locked_at IS NULL "
        "ORDER BY r.date_from",
        (apartment["id"], today.isoformat(), horizon),
    )


def _can_pick_other_stays(apartment) -> bool:
    """Whether the guest can return to the now-mandatory stay picker."""
    return bool(_visible_reservations(apartment))


def _registration_complete(reservation) -> bool:
    progress = reporting.reservation_progress(reservation)
    expected = progress["expected"]
    return (
        expected is not None
        and progress["filled"] >= expected
        and not progress["incomplete"]
    )


def _reservation_for_guest(apartment, reservation_id: int, request: Optional[Request] = None):
    """Resolve a stay the guest may open.

    The apartment picker only lists the lead window. Stay-specific links also
    keep incomplete, unlocked past registrations reachable so a forgotten form
    can still be finished. Completed forms outside the window stay reachable
    only on a device that already confirmed the claim.
    """
    for reservation in _visible_reservations(apartment):
        if reservation["id"] == reservation_id:
            return reservation
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ? AND apartment_id = ? "
        "AND status = 'active' AND archived_at IS NULL",
        (reservation_id, apartment["id"]),
    )
    if not reservation:
        return None
    row = claim.ensure_row(reservation["id"])
    if not claim.guest_access_open(reservation, row):
        return None
    if not _registration_complete(reservation):
        return reservation
    if request and reservation_id in _claimed_reservation_ids(request) and claim.is_claimed(row):
        return reservation
    return None


def _unavailable(
    request: Request,
    lang: str,
    reason: str = "bad_link",
    status_code: int = 404,
    token: Optional[str] = None,
):
    """The one page a guest lands on when there is nothing to fill in.

    It always says which of the three things happened, because "not found"
    with no explanation is what makes a guest give up and message the host.
    """
    titles = {
        "no_stays": ("no_stays", "no_stays_help"),
        "bad_link": ("bad_link_title", "bad_link_help"),
        "stay_gone": ("stay_gone_title", "stay_gone_help"),
        "not_yours": ("not_yours_title", "not_yours_help"),
        "already_filed": ("already_filed_title", "already_filed_help"),
        "form_locked": ("form_locked_title", "form_locked_help"),
    }
    title_key, body_key = titles.get(reason, titles["bad_link"])
    apartment = _apartment_by_token(token) if token else None
    context = (
        _shared(request, token or "", lang, apartment)
        if token
        else {
            "t": i18n.translator(lang),
            "lang": lang,
            "lang_urls": _lang_urls(request),
            "controller": {},
        }
    )
    context.update(
        {
            "title_key": title_key,
            "body_key": body_key,
            "restart_url": _guest_link(token) + _lang_q(lang) if token else None,
            "privacy_url": _guest_link(token) + "/privacy" + _lang_q(lang) if token else None,
        }
    )
    return render_guest(
        request,
        "guest/unavailable.html",
        context,
        status_code=status_code,
    )


def _guest_link(token: str, reservation_id: Optional[int] = None, suffix: str = "") -> str:
    base = f"/l/{token}"
    if reservation_id:
        base += f"/{reservation_id}"
    return base + suffix


def _lang_q(lang: str, extra: str = "") -> str:
    query = f"?lang={lang}"
    return query + extra if extra else query


def _lang_urls(request: Request, path: str = "") -> Dict[str, str]:
    """Same page in the other language, keeping every other query parameter.

    Dropping the query string here used to swallow flags like saved=1, so
    switching language silently threw away the "details saved" confirmation.
    """
    keep = [(k, v) for k, v in request.query_params.multi_items() if k != "lang"]
    target = path or request.url.path
    out = {}
    for code in i18n.LANGUAGES:
        pairs = "".join(f"&{k}={quote(str(v))}" for k, v in keep)
        out[code] = f"{target}?lang={code}{pairs}"
    return out


def _display_name(apartment) -> str:
    """The property's guest-facing name.

    The host's own name for the apartment, because that is the name the guest
    recognises from the booking. The name registered with the police is only a
    fallback, for records old enough to predate the field. Nothing here reaches
    the police: a report still carries ``uby_name``.
    """
    if not apartment:
        return ""
    return (apartment["internal_name"] or "").strip() or (apartment["uby_name"] or "").strip()


def _facility(apartment) -> str:
    """How the property identifies itself to a guest, including its city."""
    if not apartment:
        return ""
    name = _display_name(apartment)
    city = (apartment["city_en"] or "").strip()
    return ", ".join(part for part in (name, city) if part)


def _shared(request: Request, token: str, lang: str, apartment=None) -> Dict[str, Any]:
    """Context every guest page needs, whatever it is showing."""
    return {
        "token": token,
        "lang": lang,
        "t": i18n.translator(lang),
        "lang_urls": _lang_urls(request),
        "privacy_url": _guest_link(token) + "/privacy" + _lang_q(lang),
        "facility": _facility(apartment),
        "property_name": _display_name(apartment),
        "facility_tone": int(apartment["id"]) % 10 if apartment else 0,
        "controller": _controller(apartment) if apartment else {},
        "host": _host_contact(apartment) if apartment else {},
        "mail_enabled": mail.mail_enabled(),
    }


def _entity_details(entity_id) -> Dict[str, str]:
    if not entity_id:
        return {}
    entity = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    if not entity:
        return {}
    return {
        "name": entity["name"] or "",
        "seat": entity["seat"] or "",
        "ico": entity["ico"] or "",
        "email": (entity["contact_email"] if "contact_email" in entity.keys() else "") or "",
        "phone": (entity["contact_phone"] if "contact_phone" in entity.keys() else "") or "",
    }


def _host_contact(apartment) -> Dict[str, str]:
    """The property manager / operating entity guests contact about a stay."""
    return _entity_details(apartment["legal_entity_id"] if apartment else None)


def _controller(apartment) -> Dict[str, str]:
    """The configured GDPR controller, defaulting to the property manager."""
    if not apartment:
        return {}
    keys = apartment.keys()
    controller_id = (
        apartment["data_controller_entity_id"]
        if "data_controller_entity_id" in keys
        else None
    )
    return _entity_details(controller_id or apartment["legal_entity_id"])


def _person_row(index: int, guest, owned: set, reservation, lang: str) -> Dict[str, Any]:
    is_mine = guest["id"] in owned
    complete = reporting.guest_is_complete(guest, reservation)
    row: Dict[str, Any] = {
        "index": index,
        "id": guest["id"],
        "mine": is_mine,
        "name": f"{guest['first_name']} {guest['surname']}".strip() if is_mine else "",
        "complete": complete,
        "locked": reporting.guest_form_locked(guest, reservation),
    }
    if is_mine:
        doc = guest["doc_number"] or ""
        row["summary"] = {
            "nationality": validation.country_name(guest["nationality"], lang),
            "birth_date": validation.display_birth_date(guest["birth_date"])
            or validation.format_birth_date(guest["birth_date"]),
            "doc_number": "" if doc == validation.INPASS else doc,
            "purpose": validation.purpose_label(guest["purpose"], lang),
            "residence": validation.compose_residence(
                guest["res_street"] or "",
                guest["res_city"] or "",
                guest["res_country"] or "",
                lang,
            ),
        }
    return row


def _form_back_url(token: str, apartment, reservation_id: int, lang: str, editing: bool) -> Optional[str]:
    if editing or db.query_one("SELECT 1 AS x FROM guest WHERE reservation_id = ?", (reservation_id,)):
        return _guest_link(token, reservation_id) + _lang_q(lang)
    if _can_pick_other_stays(apartment):
        return _guest_link(token) + _lang_q(lang)
    return None


def _require_claim_session(request: Request, reservation, token: str, lang: str):
    if not mail.mail_enabled():
        return None
    apartment = _apartment_by_token(token)
    if _host_owns_apartment(request, apartment):
        return None
    row = claim.ensure_row(reservation["id"])
    if not claim.guest_access_open(reservation, row):
        return _unavailable(request, lang, "stay_gone", 404, token)
    if not claim.is_claimed(row) or reservation["id"] not in _claimed_reservation_ids(request):
        return RedirectResponse(
            _guest_link(token, reservation["id"]) + _lang_q(lang), status_code=303
        )
    return None


def _set_declared_guests(reservation, count: int) -> None:
    if reservation["expected_guests_override"]:
        return
    if count < 1 or count > 60:
        return
    db.update(
        "reservation",
        reservation["id"],
        {"declared_guests": count, "updated_at": db.utcnow()},
    )
    reporting.maybe_submit_after_completion(
        reservation["apartment_id"], reservation["id"]
    )


# --- privacy notice ------------------------------------------------------

@router.post("/l/{token}/pin")
async def verify_pin(token: str, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    form = await request.form()
    entered = (form.get("pin") or "").strip()
    pin_key = rate_limit.client_key(request, token)
    if rate_limit.pin_failure_count(pin_key) >= 3 and not turnstile.verify(
        request, form.get("cf-turnstile-response"), "guest_pin"
    ):
        return _pin_page(
            request, token, lang, error=i18n.translator(lang)("security_check_failed")
        )
    if rate_limit.pin_blocked(pin_key):
        return _pin_page(
            request,
            token,
            lang,
            error=i18n.translator(lang)("pin_rate_limited"),
        )
    expected = apartment["permalink_pin"] or ""
    if not auth.pin_matches(token, entered, expected):
        rate_limit.record_pin_failure(pin_key)
        # Slow brute-force attempts without blocking legitimate guests for long.
        failures = rate_limit.pin_failure_count(pin_key)
        if failures >= rate_limit._PIN_MAX_FAILURES:
            alerts.raise_alert(
                "warning",
                "guest_pin_abuse",
                "Guest link temporarily blocked after repeated wrong PINs.",
                detail="Review the message PIN and rotate it if the link may have been shared.",
                dedupe_key=f"guest_pin_abuse:{apartment['id']}",
                apartment_id=apartment["id"],
            )
            db.audit(
                "guest_pin_rate_limited",
                detail=f"apartment={apartment['id']}",
                actor="anonymous",
                owner_user_id=apartment["owner_user_id"],
            )
        if failures > 0:
            await asyncio.sleep(min(2.0, 0.15 * failures))
        return _pin_page(request, token, lang, error=i18n.translator(lang)("pin_wrong"))
    return_to = _safe_return_to(form.get("return_to"), token, lang)
    response = RedirectResponse(return_to, status_code=303)
    auth.attach_pin_session(response, token, expected)
    return _with_lang(response, lang)


# Registered before /l/{token}/{reservation_id}, otherwise "privacy" is parsed
# as a reservation id and the guest gets a validation error instead of a page.
@router.get("/l/{token}/privacy")
def privacy_notice(token: str, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    back_url = _safe_return_to(request.query_params.get("return_to"), token, lang)
    context = _shared(request, token, lang, apartment)
    context.update(
        {
            "controller": _controller(apartment),
            "passport_photo_policy": apartment["passport_photo_policy"] or "off",
            "back_url": back_url,
        }
    )
    return _with_lang(render_guest(request, "guest/privacy.html", context), lang)


# --- stay selection ------------------------------------------------------

@router.get("/l/{token}")
def pick_stay(token: str, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservations = list(_visible_reservations(apartment))
    visible_ids = {row["id"] for row in reservations}
    # A claimed incomplete stay outside the date window stays reachable from
    # the apartment link on the confirmed device, without listing unrelated past stays.
    for claimed_id in _claimed_reservation_ids(request):
        if claimed_id in visible_ids:
            continue
        extra = _reservation_for_guest(apartment, claimed_id, request)
        if extra and not _registration_complete(extra):
            reservations.append(extra)
            visible_ids.add(extra["id"])

    if not reservations:
        return _with_lang(_unavailable(request, lang, "no_stays", 200, token), lang)

    owned = set(_owned_ids(request))
    today = claim.prague_today()
    rows = []
    for reservation in reservations:
        progress = reporting.reservation_progress(reservation)
        yours = any(guest["id"] in owned for guest in progress["guests"])
        start = validation.parse_iso_date(reservation["date_from"])
        end = validation.parse_iso_date(reservation["date_to"])
        rows.append(
            {
                "reservation": reservation,
                "progress": progress,
                "yours": yours,
                "ongoing": bool(start and end and start <= today < end),
            }
        )
    context = _shared(request, token, lang, apartment)
    context.update({"apartment": apartment, "rows": rows})
    return _with_lang(render_guest(request, "guest/pick.html", context), lang)


@router.get("/l/{token}/{reservation_id}")
def stay_overview(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)

    claim_row = claim.ensure_row(reservation["id"])
    if not claim.guest_access_open(reservation, claim_row):
        return _unavailable(request, lang, "stay_gone", 404, token)
    context = _shared(request, token, lang, apartment)
    context.update(
        {
            "apartment": apartment,
            "reservation": reservation,
            "claim": claim_row,
            "can_pick_other": _can_pick_other_stays(apartment),
            "mail_enabled": mail.mail_enabled(),
            "claim_error": request.query_params.get("claim_error") or "",
            "claim_sent": request.query_params.get("claim_sent") == "1",
            "require_turnstile": turnstile.required(),
            "claim_last_sent_at": (
                db.query_one(
                    "SELECT MAX(sent_at) AS sent_at FROM email_outbox "
                    "WHERE reservation_id = ? AND kind IN ('claim', 'claim_resend') "
                    "AND sent_at IS NOT NULL",
                    (reservation["id"],),
                )["sent_at"]
                or ""
            ),
        }
    )
    if mail.mail_enabled() and not _host_owns_apartment(request, apartment):
        if not claim.is_claimed(claim_row):
            return _with_lang(render_guest(request, "guest/claim.html", context), lang)
        if reservation["id"] not in _claimed_reservation_ids(request):
            return _with_lang(render_guest(request, "guest/assigned.html", context), lang)

    progress = reporting.reservation_progress(reservation)
    expected = progress["expected"]
    owned = set(_owned_ids(request))

    people = [
        _person_row(index, guest, owned, reservation, lang)
        for index, guest in enumerate(progress["guests"], start=1)
    ]

    # Empty stay: skip the hub and open the form. The hub is the summary
    # after someone has actually submitted.
    if not people:
        return _with_lang(
            RedirectResponse(_guest_link(token, reservation_id) + "/new" + _lang_q(lang), status_code=303),
            lang,
        )

    remaining = (expected - progress["filled"]) if expected is not None else None
    context = _shared(request, token, lang, apartment)
    context.update(
        {
            "apartment": apartment,
            "reservation": reservation,
            "progress": progress,
            "expected": expected,
            "people": people,
            "remaining": remaining,
            "can_add": remaining is None or remaining > 0,
            "can_raise_party": not reservation["expected_guests_override"],
            "can_pick_other": _can_pick_other_stays(apartment),
            "party_error": request.query_params.get("party_error") == "1",
            "just_saved": request.query_params.get("saved") == "1",
            "just_reported": (
                request.query_params.get("saved") == "1"
                and any(person["mine"] and person["locked"] for person in people)
            ),
        }
    )
    return _with_lang(render_guest(request, "guest/stay.html", context), lang)


@router.get("/l/{token}/{reservation_id}/claim")
def claim_landing(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    if not mail.mail_enabled():
        return _with_lang(
            RedirectResponse(
                _guest_link(token, reservation_id) + _lang_q(lang), status_code=303
            ),
            lang,
        )
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ? AND apartment_id = ? "
        "AND status = 'active' AND archived_at IS NULL",
        (reservation_id, apartment["id"]),
    )
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    context = _shared(request, token, lang, apartment)
    context.update(
        {
            "apartment": apartment,
            "reservation": reservation,
            "claim_error": request.query_params.get("claim_error") == "1",
        }
    )
    return _with_lang(render_guest(request, "guest/confirm.html", context), lang)


@router.post("/l/{token}/{reservation_id}/claim/confirm")
async def claim_confirm(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    if not mail.mail_enabled():
        return _with_lang(
            RedirectResponse(
                _guest_link(token, reservation_id) + _lang_q(lang), status_code=303
            ),
            lang,
        )
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ? AND apartment_id = ? "
        "AND status = 'active' AND archived_at IS NULL",
        (reservation_id, apartment["id"]),
    )
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    form = await request.form()
    secret = (form.get("secret") or "").strip()
    key = rate_limit.client_key(request, f"claim:{token}")
    if rate_limit.blocked("claim_confirm", key, 20):
        return _unavailable(request, lang, "stay_gone", 429, token)
    rate_limit.record("claim_confirm", key)
    if not claim.confirm(reservation, secret):
        return _with_lang(
            RedirectResponse(
                _guest_link(token, reservation_id) + "/claim" + _lang_q(lang, "&claim_error=1"),
                status_code=303,
            ),
            lang,
        )
    response = RedirectResponse(
        _guest_link(token, reservation_id) + _lang_q(lang), status_code=303
    )
    _remember_claim(response, reservation_id, request)
    return _with_lang(response, lang)


@router.post("/l/{token}/{reservation_id}/party")
async def set_party_size(token: str, reservation_id: int, request: Request):
    """Claim the stay with party size and e-mail, or change headcount later."""
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    form = await request.form()
    try:
        count = int((form.get("party_size") or "").strip())
    except ValueError:
        count = 0
    if not mail.mail_enabled():
        if count < 1 or count > 60:
            return _with_lang(
                RedirectResponse(
                    _guest_link(token, reservation_id)
                    + _lang_q(lang, "&party_error=1"),
                    status_code=303,
                ),
                lang,
            )
        _set_declared_guests(reservation, count)
        return _with_lang(
            RedirectResponse(
                _guest_link(token, reservation_id) + _lang_q(lang),
                status_code=303,
            ),
            lang,
        )
    email = (form.get("guest_email") or "").strip()
    claim_row = claim.ensure_row(reservation["id"])
    resend = bool(form.get("resend"))
    if email or not claim.is_claimed(claim_row):
        if turnstile.required() and not turnstile.verify(
            request, form.get("cf-turnstile-response"), "guest_claim"
        ):
            return _with_lang(
                RedirectResponse(
                    _guest_link(token, reservation_id)
                    + _lang_q(lang, "&claim_error=bot"),
                    status_code=303,
                ),
                lang,
            )
        # Strict IP+token cap: three claim attempts / 15 minutes.
        key = rate_limit.client_key(request, f"claim:{token}")
        if rate_limit.blocked("claim_start", key, 3):
            return _with_lang(
                RedirectResponse(
                    _guest_link(token, reservation_id) + _lang_q(lang, "&claim_error=rate"),
                    status_code=303,
                ),
                lang,
            )
        rate_limit.record("claim_start", key)
        ok, err, _secret = claim.start_claim(
            reservation,
            apartment,
            email=email,
            party_size=count,
            lang=lang,
            resend=resend or claim.is_claimed(claim_row),
        )
        if ok:
            extra = "&claim_sent=1"
        elif err == "already_sent":
            # Active provisional hold for this address — show check-email, no new send.
            extra = "&claim_sent=1"
        else:
            extra = f"&claim_error={err or 'bad_email'}"
        return _with_lang(
            RedirectResponse(
                _guest_link(token, reservation_id) + _lang_q(lang, extra),
                status_code=303,
            ),
            lang,
        )
    if count < 1 or count > 60:
        return _with_lang(
            RedirectResponse(
                _guest_link(token, reservation_id) + _lang_q(lang, "&party_error=1"),
                status_code=303,
            ),
            lang,
        )
    _set_declared_guests(reservation, count)
    return _with_lang(
        RedirectResponse(_guest_link(token, reservation_id) + _lang_q(lang), status_code=303), lang
    )


@router.post("/l/{token}/{reservation_id}/another")
async def add_another_person(token: str, reservation_id: int, request: Request):
    """Raise the declared headcount by one so another guest can fill the form."""
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    claim_guard = _require_claim_session(request, reservation, token, lang)
    if claim_guard:
        return _with_lang(claim_guard, lang)
    if reservation["expected_guests_override"]:
        return _with_lang(
            RedirectResponse(_guest_link(token, reservation_id) + _lang_q(lang), status_code=303),
            lang,
        )
    progress = reporting.reservation_progress(reservation)
    current = progress["expected"] or progress["filled"] or 1
    _set_declared_guests(reservation, min(current + 1, 60))
    return _with_lang(
        RedirectResponse(_guest_link(token, reservation_id) + "/new" + _lang_q(lang), status_code=303),
        lang,
    )


# --- guest form ----------------------------------------------------------

def _form_context(
    request: Request,
    apartment,
    reservation,
    guest,
    lang: str,
    issues=None,
    values=None,
    back_url: Optional[str] = None,
) -> Dict[str, Any]:
    token = apartment["permalink_token"]
    progress = reporting.reservation_progress(reservation)
    expected = progress["expected"]
    remaining = (expected - progress["filled"]) if expected is not None else None
    context = _shared(request, token, lang, apartment)
    # This context is also rendered from the POST handler when validation
    # fails, and request.url.path is then .../save - a URL that only answers
    # POST. Point the language links at the form itself instead.
    form_path = (
        _guest_link(token, reservation["id"]) + f"/edit/{guest['id']}"
        if guest
        else _guest_link(token, reservation["id"]) + "/new"
    )
    context["lang_urls"] = _lang_urls(request, form_path)
    context["privacy_url"] = (
        _guest_link(token)
        + "/privacy"
        + _lang_q(lang, f"&return_to={quote(form_path + _lang_q(lang))}")
    )
    context.update(
        {
            "apartment": apartment,
            "reservation": reservation,
            "guest": guest,
            "back_url": back_url,
            "pick_url": _guest_link(token) + _lang_q(lang) if _can_pick_other_stays(apartment) else None,
            "can_pick_other": _can_pick_other_stays(apartment),
            "ask_party_size": expected is None and guest is None,
            "person_number": progress["filled"] + 1 if guest is None else None,
            "expected_people": expected,
            "issues": issues or [],
            "values": values or {},
            "countries": codelists.nationality_options(lang),
            "purposes": codelists.purpose_options(lang),
            "default_purpose": apartment["default_purpose"] or validation.DEFAULT_PURPOSE,
            "inpass": validation.INPASS,
            "remaining": remaining,
            "has_existing_passport_photo": bool(
                guest
                and guest["passport_photo_at"]
                and passport_photos.has_photo(int(guest["id"]))
            ),
            # Show the upload step whenever the property enables it; nationality
            # gating (Czech vs foreign) is handled in the template JavaScript
            # and again on save via guest_needs_passport_photo.
            "require_passport": (
                (apartment["passport_photo_policy"] or "off").strip().lower()
                == "required_foreign"
            ),
        }
    )
    return context


@router.get("/l/{token}/{reservation_id}/new")
def guest_form_new(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    claim_guard = _require_claim_session(request, reservation, token, lang)
    if claim_guard:
        return _with_lang(claim_guard, lang)
    progress = reporting.reservation_progress(reservation)
    expected = progress["expected"]
    remaining = (expected - progress["filled"]) if expected is not None else None
    if remaining is not None and remaining <= 0:
        return _with_lang(
            RedirectResponse(_guest_link(token, reservation_id) + _lang_q(lang), status_code=303),
            lang,
        )
    return _with_lang(
        render_guest(
            request,
            "guest/form.html",
            _form_context(
                request,
                apartment,
                reservation,
                None,
                lang,
                back_url=_form_back_url(token, apartment, reservation_id, lang, editing=False),
            ),
        ),
        lang,
    )


@router.get("/l/{token}/{reservation_id}/edit/{guest_id}")
def guest_form_edit(token: str, reservation_id: int, guest_id: int, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    claim_guard = _require_claim_session(request, reservation, token, lang)
    if claim_guard:
        return _with_lang(claim_guard, lang)
    if guest_id not in _owned_ids(request):
        return _unavailable(request, lang, "not_yours", 403, token)
    guest = db.query_one(
        "SELECT * FROM guest WHERE id = ? AND reservation_id = ?", (guest_id, reservation_id)
    )
    if not guest:
        return _unavailable(request, lang, "stay_gone", 404, token)
    if guest["submit_state"] == reporting.SENT:
        return _unavailable(request, lang, "already_filed", 403, token)
    if reporting.guest_form_locked(guest, reservation):
        return _unavailable(request, lang, "form_locked", 403, token)
    return _with_lang(
        render_guest(
            request,
            "guest/form.html",
            _form_context(
                request,
                apartment,
                reservation,
                guest,
                lang,
                back_url=_form_back_url(token, apartment, reservation_id, lang, editing=True),
            ),
        ),
        lang,
    )


@router.post("/l/{token}/{reservation_id}/save")
async def guest_form_save(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment = _apartment_by_token(token)
    if not apartment:
        return _unavailable(request, lang)
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    claim_guard = _require_claim_session(request, reservation, token, lang)
    if claim_guard:
        return _with_lang(claim_guard, lang)

    form = await request.form()
    translate = i18n.translator(lang)

    guest_id = None
    raw_id = (form.get("guest_id") or "").strip()
    if raw_id.isdigit():
        candidate = int(raw_id)
        if candidate in _owned_ids(request):
            guest_id = candidate

    existing = None
    if guest_id:
        existing = db.query_one(
            "SELECT * FROM guest WHERE id = ? AND reservation_id = ?", (guest_id, reservation_id)
        )
        if existing and existing["submit_state"] == reporting.SENT:
            return _unavailable(request, lang, "already_filed", 403, token)
        if existing and reporting.guest_form_locked(existing, reservation):
            return _unavailable(request, lang, "form_locked", 403, token)

    child_in_passport = bool(form.get("child_in_passport"))
    raw = {
        "surname": form.get("surname") or "",
        "first_name": form.get("first_name") or "",
        "birth_date": form.get("birth_date") or "",
        "nationality": form.get("nationality") or "",
        "doc_number": validation.INPASS if child_in_passport else (form.get("doc_number") or ""),
        "visa_number": form.get("visa_number") or "",
        "res_street": form.get("res_street") or "",
        "res_city": form.get("res_city") or "",
        "res_country": form.get("res_country") or "",
        "purpose": form.get("purpose") or apartment["default_purpose"] or validation.DEFAULT_PURPOSE,
        "note": form.get("note") or "",
    }
    if child_in_passport:
        parent_doc = validation.normalise_document(form.get("parent_doc_number") or "")
        if parent_doc:
            prefix = "Dítě zapsané v pasu rodiče, číslo dokladu rodiče: "
            raw["note"] = (prefix + parent_doc + (" " + raw["note"] if raw["note"] else ""))[:255]

    # Un-clamped so an over-long name is reported back to the guest instead of
    # being cut mid-word and filed against a passport it no longer matches.
    values = validation.normalise_guest(raw, clamp=False)
    stay_from = (form.get("stay_from") or "").strip() or reservation["date_from"]
    stay_to = (form.get("stay_to") or "").strip() or reservation["date_to"]
    signature = (form.get("signature") or "").strip()
    if not signature.startswith("data:image/") and existing and (existing["signature_png"] or "").startswith("data:image/"):
        signature = existing["signature_png"]

    party_raw = (form.get("party_size") or "").strip()
    try:
        party_size = int(party_raw)
    except ValueError:
        party_size = 0

    issues = validation.validate_guest(
        values,
        validation.parse_iso_date(stay_from),
        validation.parse_iso_date(stay_to),
        raw=raw,
    )
    if reporting.expected_guest_count(reservation) is None and not existing:
        if party_size < 1 or party_size > 60:
            issues.append(validation.Issue("party_size", translate("error_party_size")))
    if not signature.startswith("data:image/"):
        issues.append(validation.Issue("signature", translate("signature_missing")))
    if not form.get("legal_ack"):
        issues.append(validation.Issue("legal_ack", translate("legal_ack_missing")))

    passport_upload = form.get("passport_photo")
    passport_bytes = None
    passport_type = None
    if reporting.guest_needs_passport_photo(
        existing
        or {
            "nationality": values["nationality"],
            "reservation_id": reservation_id,
            "entered_by": "guest",
            "identity_verified_at": None,
        },
        apartment,
    ):
        has_existing_photo = (
            existing
            and existing["passport_photo_at"]
            and passport_photos.has_photo(existing["id"])
        )
        if passport_upload and hasattr(passport_upload, "read"):
            try:
                passport_bytes = await passport_photos.read_upload_limited(passport_upload)
                passport_type = passport_photos.validate_upload(
                    passport_bytes, passport_upload.content_type or ""
                )
            except ValueError as exc:
                msg = str(exc)
                if lang == "cs":
                    msg = CS_PASSPORT_UPLOAD_MESSAGES.get(msg, msg)
                issues.append(validation.Issue("passport_photo", msg))
        elif not has_existing_photo:
            issues.append(validation.Issue("passport_photo", translate("passport_photo_missing")))

    issues = _localize_issues(issues, lang)

    if validation.errors_only(issues):
        context = _form_context(
            request,
            apartment,
            reservation,
            existing,
            lang,
            issues=issues,
            values=values,
            back_url=_form_back_url(token, apartment, reservation_id, lang, editing=bool(existing)),
        )
        context["values"].update(
            {
                "stay_from": stay_from,
                "stay_to": stay_to,
                "child_in_passport": child_in_passport,
                "parent_doc_number": form.get("parent_doc_number") or "",
                "signature": signature,
                "party_size": party_raw,
                "legal_ack": form.get("legal_ack") or "",
            }
        )
        return _with_lang(render_guest(request, "guest/form.html", context, status_code=422), lang)

    if reporting.expected_guest_count(reservation) is None and not existing:
        _set_declared_guests(reservation, party_size)

    now = db.utcnow()
    payload = dict(values)
    payload.update(
        {
            "stay_from": stay_from,
            "stay_to": stay_to,
            "signature_png": signature,
            "signed_at": now,
            "filled_at": now,
            "filled_ip": request.client.host if request.client else None,
            "entered_by": "guest",
            "updated_at": now,
            "submit_state": (
                reporting.NOT_REQUIRED
                if not validation.guest_is_reportable(values["nationality"])
                else reporting.PENDING
            ),
            "last_errors": None,
        }
    )

    if existing:
        db.update("guest", existing["id"], payload)
        saved_id = existing["id"]
    else:
        # Two phones can each open /new while one slot is free. /new checks
        # capacity on GET; re-check here so the party cannot overshoot the
        # declared headcount and report a guest nobody expected.
        fresh = reporting.reservation_progress(reservation)
        if fresh["expected"] is not None and fresh["filled"] >= fresh["expected"]:
            return _with_lang(
                RedirectResponse(
                    _guest_link(token, reservation_id) + _lang_q(lang), status_code=303
                ),
                lang,
            )
        is_first = not db.query_one(
            "SELECT 1 AS x FROM guest WHERE reservation_id = ?", (reservation_id,)
        )
        payload.update(
            {"reservation_id": reservation_id, "is_lead": 1 if is_first else 0, "created_at": now}
        )
        saved_id = db.insert("guest", payload)

    if passport_bytes and passport_type:
        passport_photos.save_photo(saved_id, passport_bytes, passport_type)
        db.update(
            "guest",
            saved_id,
            {"passport_photo_at": now, "updated_at": now},
        )

    db.audit(
        "guest_form_saved",
        f"guest={saved_id} reservation={reservation_id}",
        actor="guest",
        owner_user_id=apartment["owner_user_id"],
    )
    claim.maybe_notify_completion(
        db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,)),
        apartment,
    )
    reporting.maybe_submit_after_completion(apartment["id"], reservation_id)

    response = RedirectResponse(
        _guest_link(token, reservation_id) + _lang_q(lang, "&saved=1"), status_code=303
    )
    _remember_owned(response, _owned_ids(request) + [saved_id])
    return _with_lang(response, lang)
