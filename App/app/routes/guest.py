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
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool
from itsdangerous import BadSignature, URLSafeSerializer

import posixpath
import re
from .. import alerts, auth, claim, codelists, config, cookie_inventory, db, door_codes, guest_slug, i18n, incidents, mail, passport_photos, rate_limit, reporting, security, turnstile, validation, validation_i18n
from ..templating import render_guest
from .admin_helpers import guest_form_raw as _guest_form_raw
from .admin_helpers import kept_signature as _kept_signature
from .admin_helpers import stay_dates_from_form as _stay_dates_from_form

router = APIRouter(dependencies=[Depends(security.protect_guest_post)])

# The guest's own language, deliberately not the host's ``ubyhost_lang``: the
# two share a browser, and a guest who switched their form to English used to
# switch the host's whole UI with it.
LANG_COOKIE = "ubyhost_guest_lang"
OWNED_COOKIE = "ubyhost_owned"
CLAIM_COOKIE = "ubyhost_claim"

# Per-(address, link) budget for the guest POSTs that write something. Deliberately
# loose: a guest fixing validation errors saves repeatedly, so this bounds
# hammering rather than pacing a careful person. The PIN and the claim cookie are
# the controls on *who* may post; this only bounds how often.
GUEST_POST_MAX_ATTEMPTS = 30

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
    "The photo has too many pixels. Take it again at the normal camera setting.": (
        "Fotografie má příliš mnoho pixelů. Vyfoťte ji znovu v běžném nastavení fotoaparátu."
    ),
}


# WP26: the same refusals for the other guest languages, keyed the same way.
PASSPORT_UPLOAD_MESSAGES: Dict[str, Dict[str, str]] = {
    "cs": CS_PASSPORT_UPLOAD_MESSAGES,
    "de": {
        "Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).": "Laden Sie ein JPEG-, PNG- oder WebP-Foto Ihrer Reisepass-Datenseite oder ein PDF hoch (zum Beispiel ein Meldeformular mit bis zu 11 Gästen).",
        "The uploaded file looks empty.": "Die hochgeladene Datei scheint leer zu sein.",
        "The PDF is too large. Use a file under 15 MB.": "Das PDF ist zu groß. Verwenden Sie eine Datei unter 15 MB.",
        "The file does not look like a valid PDF.": "Die Datei scheint kein gültiges PDF zu sein.",
        "The photo is too large. Use a file under 5 MB.": "Das Foto ist zu groß. Verwenden Sie eine Datei unter 5 MB.",
        "The file does not look like a valid image.": "Die Datei scheint kein gültiges Bild zu sein.",
        "The photo has too many pixels. Take it again at the normal camera setting.": "Das Foto hat zu viele Pixel. Nehmen Sie es mit der normalen Kameraeinstellung erneut auf.",
    },
    "es": {
        "Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).": "Suba una foto JPEG, PNG o WebP de la página de datos de su pasaporte, o un PDF (por ejemplo, un formulario de registro de hasta 11 huéspedes).",
        "The uploaded file looks empty.": "El archivo subido parece estar vacío.",
        "The PDF is too large. Use a file under 15 MB.": "El PDF es demasiado grande. Use un archivo de menos de 15 MB.",
        "The file does not look like a valid PDF.": "El archivo no parece un PDF válido.",
        "The photo is too large. Use a file under 5 MB.": "La foto es demasiado grande. Use un archivo de menos de 5 MB.",
        "The file does not look like a valid image.": "El archivo no parece una imagen válida.",
        "The photo has too many pixels. Take it again at the normal camera setting.": "La foto tiene demasiados píxeles. Vuelva a hacerla con la configuración normal de la cámara.",
    },
    "fr": {
        "Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).": "Téléversez une photo JPEG, PNG ou WebP de la page d'identité de votre passeport, ou un PDF (par exemple un formulaire d'enregistrement de 11 voyageurs maximum).",
        "The uploaded file looks empty.": "Le fichier téléversé semble vide.",
        "The PDF is too large. Use a file under 15 MB.": "Le PDF est trop volumineux. Utilisez un fichier de moins de 15 Mo.",
        "The file does not look like a valid PDF.": "Le fichier ne semble pas être un PDF valide.",
        "The photo is too large. Use a file under 5 MB.": "La photo est trop volumineuse. Utilisez un fichier de moins de 5 Mo.",
        "The file does not look like a valid image.": "Le fichier ne semble pas être une image valide.",
        "The photo has too many pixels. Take it again at the normal camera setting.": "La photo comporte trop de pixels. Reprenez-la avec le réglage normal de l'appareil photo.",
    },
}

def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(config.secret_key(), salt="ubyhost-guest-owned")


def _claim_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(config.secret_key(), salt="ubyhost-guest-claim")


def _accept_language(request: Request) -> str:
    """What the guest's browser asks for, matched against the guest catalogs.

    Read only when the guest has said nothing themselves. Every browser sends
    this header, ranked by q-value, so a German phone gets German, ``es-MX``
    gets Spanish and a Slovak phone gets Czech. Only the header is read: no IP
    lookup, no outside service, nothing stored. A header naming nothing we
    speak, or no header at all, gets English, because the guest is by
    definition a foreigner (WP26 owner decision).
    """
    return i18n.accept_language_match(request.headers.get("accept-language")) or (
        i18n.DEFAULT_LANGUAGE
    )


def _language(request: Request) -> str:
    """The guest's language: what they asked for, else what their browser asks for.

    A ``?lang=`` on a link, or the switcher's cookie, is the guest saying so,
    and wins. A choice naming a language we do not speak is treated as no
    choice, so the browser's header still decides rather than a Czech default.
    """
    return _chosen_language(request) or _accept_language(request)


def _chosen_language(request: Request) -> Optional[str]:
    """The language the guest actually asked for, or ``None`` if they did not.

    The link wins over the cookie, because a link with ``?lang=`` is the newer
    choice: the switcher writes it and the cookie follows on the response.
    """
    return i18n.supported_language(request.query_params.get("lang")) or (
        i18n.supported_language(request.cookies.get(LANG_COOKIE))
    )


def _mail_language(request: Request) -> str:
    """The language for a message sent to the guest, not rendered for them.

    The same as the page's: the explicit choice, else the browser's header,
    else English. It used to skip the header because the page then fell back
    to Czech; since WP26 nothing falls back to Czech, so the claim mail goes
    out in the language the guest was reading. It is stored on the claim row
    (``reservation_claim.lang``, which already existed), and the reminder and
    the completion receipt read it from there.
    """
    return _language(request)


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
        secure=auth.secure_cookies(),
        path="/",
    )


def _guest_display_name(first_name, surname) -> str:
    """A name fit to show a guest, not the police's shouting caps.

    The record is stored the way UbyPort wants it, all upper case, so a hint
    that read "Copied from JOHN PAUL SMITH" would look like the app was
    shouting at the guest's own family.
    """
    parts = []
    for raw in (first_name, surname):
        part = (raw or "").strip()
        if part:
            parts.append(part.title())
    return " ".join(parts)


def _residence_prefill(request: Request, reservation) -> tuple:
    """The address this device already gave for someone else on this stay.

    Person 2 in a family types the same street, city and country as person 1,
    and that run of typing is the longest one left in the form. The device
    cookie already names the guests this browser filled in, so the address is
    known - it was simply not being used. Only a completed guest is copied
    from: a half-finished record is not something to repeat on someone else's
    behalf.
    """
    owned = set(_owned_ids(request))
    if not owned:
        return {}, None
    rows = db.query(
        "SELECT * FROM guest WHERE reservation_id = ? AND archived_at IS NULL "
        "ORDER BY id DESC",
        (reservation["id"],),
    )
    for row in rows:
        if int(row["id"]) not in owned:
            continue
        if not reporting.guest_is_complete(row, reservation):
            continue
        street = (row["res_street"] or "").strip()
        city = (row["res_city"] or "").strip()
        country = (row["res_country"] or "").strip()
        if not (street and city and country):
            continue
        name = _guest_display_name(row["first_name"], row["surname"])
        return (
            {"res_street": street, "res_city": city, "res_country": country},
            name,
        )
    return {}, None


def _claimed_claims(request: Request) -> Dict[int, int]:
    """The stays this device confirmed, mapped to the claim generation it used.

    The value is ``reservation_claim.token_version``: the counter bumped every
    time a fresh secret is issued and every time the host releases the stay.
    Recording the generation, not just the id, is what lets a release cut a
    device off -- the old browser still names generation N while the stay has
    moved to N+1, so it has to ask for the link again.
    """
    raw = request.cookies.get(CLAIM_COOKIE)
    if not raw:
        return {}
    try:
        value = _claim_serializer().loads(raw)
    except (BadSignature, ValueError, TypeError):
        return {}
    if not isinstance(value, dict):
        # Cookies minted before the generation was recorded named ids only.
        # They carry no claim to check against, so they grant nothing.
        return {}
    held: Dict[int, int] = {}
    for key, generation in value.items():
        try:
            held[int(key)] = int(generation)
        except (TypeError, ValueError):
            continue
    return held


def _claimed_reservation_ids(request: Request) -> List[int]:
    return list(_claimed_claims(request))


def _device_holds_claim(request: Request, reservation_id: int, row) -> bool:
    """True when this device confirmed the claim the stay is in *now*."""
    generation = _claimed_claims(request).get(int(reservation_id))
    return bool(
        generation is not None
        and row
        and claim.is_claimed(row)
        and int(row["token_version"] or 0) == generation
    )


def _remember_claim(response, reservation_id: int, request: Optional[Request] = None) -> None:
    row = claim.ensure_row(int(reservation_id))
    if not row or not claim.is_claimed(row):
        # Nothing to remember: a cookie without a confirmed claim would assert
        # access the stay does not grant.
        return
    held = _claimed_claims(request) if request else {}
    held[int(reservation_id)] = int(row["token_version"] or 0)
    kept = {str(k): held[k] for k in sorted(held)[-40:]}
    response.set_cookie(
        CLAIM_COOKIE,
        _claim_serializer().dumps(kept),
        max_age=60 * 60 * 24 * 60,
        httponly=True,
        samesite="lax",
        secure=auth.secure_cookies(),
        path="/",
    )


def _with_lang(response, lang: str):
    response.set_cookie(
        LANG_COOKIE,
        lang,
        max_age=60 * 60 * 24 * 60,
        samesite="lax",
        secure=auth.secure_cookies(),
        path="/",
    )
    return response


_CLAIM_FRAGMENT = re.compile(r"c=[A-Za-z0-9_-]{16,128}\Z")


def _safe_fragment(value: Optional[str]) -> str:
    """Return the claim secret a fragment carries, or ``""``.

    A fragment is never sent to the server, so it is not part of the redirect
    target the browser posts back; the claim link keeps its one-time secret
    there (``#c=…``) and ``claim.js`` reads it out again. Anything that is not
    a plain claim secret is dropped rather than echoed into a ``Location``.
    """
    if not value or "#" not in value:
        return ""
    fragment = value.split("#", 1)[1]
    if not _CLAIM_FRAGMENT.fullmatch(fragment):
        return ""
    return "#" + fragment


def _safe_return_to(requested: Optional[str], token: str, lang: str) -> str:
    """Only ever bounce back inside this apartment's own permalink.

    A plain ``startswith`` check passes ``/l/{token}/../../somewhere-else``,
    so the path is normalised before it is compared. The claim fragment is
    kept: dropping it is what silently broke the link behind the PIN gate.
    """
    fallback = _guest_link(token) + _lang_q(lang)
    fragment = _safe_fragment(requested)
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
    return urlunsplit(("", "", path, split.query, "")) + fragment


# The child-on-a-parent's-passport check is keyed "note" in validation.py, where
# the column really is called that. The guest form has no "note" box: it has the
# parent's document number. So for the guest the issue is renamed onto the field
# they can see, and the sentence names that box. The rename lives here rather
# than in validation.py because the host form does have a "note" column and must
# keep reading its own wording.
_GUEST_ISSUE_FIELDS = {"note": "parent_doc_number"}
_GUEST_ISSUE_MESSAGES = {
    "note": {
        "en": "Enter the parent's passport or ID number.",
        "cs": "Zadejte číslo pasu nebo průkazu rodiče.",
        "de": "Geben Sie die Pass- oder Ausweisnummer des Elternteils ein.",
        "es": "Introduzca el número de pasaporte o documento de identidad del padre o la madre.",
        "fr": "Saisissez le numéro de passeport ou de carte d'identité du parent.",
    },
}


def _guest_issue(issue, lang: str):
    # Keyed by the field validation.py used, not by its sentence: the sentence
    # has already been through the translation table by the time it gets here,
    # and the field is what stays stable.
    override = _GUEST_ISSUE_MESSAGES.get(issue.field)
    field = _GUEST_ISSUE_FIELDS.get(issue.field, issue.field)
    if override is None:
        return issue
    message = override.get(lang) or override["en"]
    return validation.Issue(field, message, issue.severity)


def _localize_issues(issues, lang: str):
    return [
        _guest_issue(issue, lang)
        for issue in validation_i18n.guest_localize_issues(issues, lang)
    ]


def _live_apartment(column: str, value):
    row = db.query_one(
        f"SELECT * FROM apartment WHERE {column} = ? AND active = 1 "
        "AND archived_at IS NULL",
        (value,),
    )
    if not row:
        return None
    if not row["permalink_pin"]:
        pin = auth.new_permalink_pin()
        db.update("apartment", row["id"], {"permalink_pin": pin})
        return db.query_one("SELECT * FROM apartment WHERE id = ?", (row["id"],))
    return row


def _apartment_by_token(token: str):
    return _live_apartment("permalink_token", token)


def _resolve_key(key: str):
    """Map the ``/l/{key}`` segment to ``(apartment, link key, moved)``.

    ``key`` is either the permanent token, which keeps working for ever, or a
    readable slug (WP19). The link key is what the pages put back into their
    own links: the token for a token visitor, the *current* slug for a slug
    visitor. ``moved`` is true when the key was an earlier slug, or the current
    one in other letter case, so a GET can be redirected to the current one.
    """
    apartment = _apartment_by_token(key)
    if apartment:
        return apartment, key, False
    row = guest_slug.lookup(key)
    if not row:
        return None, key, False
    apartment = _live_apartment("id", int(row["apartment_id"]))
    if not apartment or not apartment["permalink_token"]:
        return None, key, False
    if row["is_current"]:
        link = row["slug"]
    else:
        link = guest_slug.current(int(apartment["id"])) or apartment["permalink_token"]
    return apartment, link, link != key


def _apartment_for_key(key: str):
    return _resolve_key(key)[0] if key else None


def _lock_token(key: str) -> str:
    """The permanent token behind a link key: what every PIN cookie, PIN
    fingerprint, lockout and rate-limit key is built from, so switching
    between ``/l/{token}`` and ``/l/{slug}`` neither asks for the PIN again
    nor starts a fresh failure budget."""
    apartment = _apartment_for_key(key)
    return apartment["permalink_token"] if apartment else key


def _open_link(request: Request, key: str, lang: str):
    """The one resolver every ``/l/{key}`` route starts with.

    Returns ``(apartment, link key, response)``. ``response`` is set when the
    route must answer with it straight away: the "bad link" page (404) for a
    key nothing matches, including a slug with a wrong code, or a 301 to the
    current slug for a GET on an earlier one. A POST on an earlier slug is
    served in place, because a redirect would drop its body.
    """
    apartment, link, moved = _resolve_key(key)
    if not apartment:
        return None, key, _unavailable(request, lang)
    if moved and request.method in ("GET", "HEAD"):
        prefix = f"/l/{key}"
        path = request.url.path
        rest = path[len(prefix):] if path.startswith(prefix) else ""
        target = f"/l/{link}{rest}"
        if request.url.query:
            target += "?" + request.url.query
        response = RedirectResponse(target, status_code=301)
        # A host may rename back to an earlier name. A 301 a browser cached for
        # ever would then point the current slug at an old one and loop.
        response.headers["Cache-Control"] = "no-store"
        return apartment, link, response
    return apartment, link, None


def _pin_page(request: Request, token: str, lang: str, error: str = ""):
    apartment = _apartment_for_key(token)
    lock_token = apartment["permalink_token"] if apartment else token
    failures = rate_limit.pin_failure_count(rate_limit.client_key(request, lock_token))
    context = _shared(request, token, lang, apartment)
    context.update(
        {
            "error": error,
            "require_turnstile": failures >= 3 or _link_challenged(apartment),
            "return_to": request.url.path
            + (("?" + str(request.url.query)) if request.url.query else ""),
        }
    )
    return _with_lang(render_guest(request, "guest/pin.html", context), lang)


def _link_challenged(apartment) -> bool:
    """A link guessed at from many addresses asks every visitor for the check.

    With Turnstile on, a locked link is challenged rather than refused, so one
    person with an old link cannot shut every guest out for a day.
    """
    if not apartment or not turnstile.required():
        return False
    expected = apartment["permalink_pin"] or ""
    token = apartment["permalink_token"]
    return rate_limit.pin_token_blocked(f"{token}:{auth.pin_fingerprint(token, expected)}")


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
    apartment = _apartment_for_key(token)
    if apartment and (
        _host_owns_apartment(request, apartment)
        or auth.pin_session_valid(
            request, apartment["permalink_token"], apartment["permalink_pin"] or ""
        )
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
    can still be finished, but only for ``permalink_reachback_days`` (a year by
    default): without a lower bound an old id answered differently from an id
    that never existed, which told a stranger which reservations belong to the
    apartment. Completed forms outside both windows stay reachable only on a
    device that already confirmed the claim.
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
    reachback = validation.normalise_reachback_days(apartment["permalink_reachback_days"])
    cutoff = (claim.prague_today() - timedelta(days=reachback)).isoformat()
    if (reservation["date_to"] or "") < cutoff:
        return None
    row = claim.ensure_row(reservation["id"])
    if not claim.guest_access_open(reservation, row):
        return None
    if not _registration_complete(reservation):
        return reservation
    if request and _device_holds_claim(request, reservation_id, row):
        return reservation
    return None


def _claimable_reservation(apartment, reservation_id: int):
    """A stay the guest may be asked to confirm, or None.

    Confirming spends the link and grants access to the stay, so the form is held
    to the same bound as the stay page itself: an id outside the apartment's
    reach-back, or one the host locked or cancelled, must answer exactly like an
    id that never existed.
    """
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ? AND apartment_id = ? "
        "AND status = 'active' AND archived_at IS NULL",
        (reservation_id, apartment["id"]),
    )
    if not reservation:
        return None
    reachback = validation.normalise_reachback_days(apartment["permalink_reachback_days"])
    cutoff = (claim.prague_today() - timedelta(days=reachback)).isoformat()
    if (reservation["date_to"] or "") < cutoff:
        return None
    if not claim.guest_access_open(reservation):
        return None
    return reservation


# Reasons where the stay itself cannot be changed from the guest's side, so
# sending them back to the picker would only land them here again.
_NO_RESTART_REASONS = frozenset({"form_locked", "already_filed", "not_yours"})


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
        "form_expired": ("form_expired_title", "form_expired_help"),
        "rate_limited": ("rate_limited_title", "rate_limited_help"),
        "not_yours": ("not_yours_title", "not_yours_help"),
        "already_filed": ("already_filed_title", "already_filed_help"),
        "form_locked": ("form_locked_title", "form_locked_help"),
        "server_error": ("server_error_title", "server_error_help"),
    }
    title_key, body_key = titles.get(reason, titles["bad_link"])
    apartment = _apartment_for_key(token) if token else None
    # "Start again" only helps where starting again can change something. On a
    # locked, already-reported or wrong-device form the picker leads straight
    # back to this page.
    restart_url = (
        _guest_link(token) + _lang_q(lang)
        if token and reason not in _NO_RESTART_REASONS
        else None
    )
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
            "restart_url": restart_url,
            # The invoice link (PLAN_GUEST_INVOICE_FEATURE §3.1 D) belongs on the
            # stay hub and here only, so it never competes on the PIN, claim or
            # form screens. Wired off until that feature ships.
            "show_invoice_link": False,
            "privacy_url": _guest_link(token) + "/privacy" + _lang_q(lang) if token else None,
        }
    )
    return render_guest(
        request,
        "guest/unavailable.html",
        context,
        status_code=status_code,
    )


def error_page(request: Request, kind: str, status_code: int):
    """WP26: the app-wide 404 and 500 pages, for a request under ``/l/``.

    Those used to render the host's error page, in the host's two languages, in
    front of a guest. A guest gets the guest page in their own language
    instead. A server error renders without the apartment: whatever failed may
    be the database, so this page must not need it.
    """
    lang = _language(request)
    if kind == "server":
        return _unavailable(request, lang, "server_error", status_code)
    parts = request.url.path.split("/")
    token = parts[2] if len(parts) > 2 and parts[2] else None
    return _unavailable(request, lang, "bad_link", status_code, token)


def csrf_expired_page(request: Request, token: str = ""):
    """Guest-facing 403 for a form whose CSRF proof is gone.

    Guest pages are served with ``Referrer-Policy: no-referrer``, so there is no
    rendered form to send the visitor back to. The page tells them to reload and
    links to the start of the flow, which issues a fresh token.
    """
    return _unavailable(
        request,
        _language(request),
        "form_expired",
        status_code=403,
        token=(token or request.path_params.get("token") or None),
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
    for code in i18n.enabled_languages():
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
        "notice_version": config.GUEST_NOTICE_VERSION,
        "cookie_inventory": cookie_inventory.COOKIE_INVENTORY,
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


def controller_complete(apartment) -> bool:
    """Whether the configured controller has the identity Art 13 requires.

    LEGAL-GATED: counsel may add fields; keep the rule in this one function.
    """
    controller = _controller(apartment)
    return bool(
        controller.get("name")
        and controller.get("email")
        and (controller.get("ico") or controller.get("seat"))
    )


def _alert_controller_missing(apartment) -> None:
    """Warn the host when the controller identity is incomplete.

    G-D9: this never blocks the guest. The form keeps working; the host gets a
    critical card naming the property.
    """
    if not apartment or controller_complete(apartment):
        return
    alerts.raise_alert(
        "critical",
        "controller_missing",
        "The guest form cannot name who controls the guest's data.",
        "Add the data controller's name, address or IČO and contact e-mail.",
        dedupe_key=f"controller_missing:{apartment['id']}",
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"] if "owner_user_id" in apartment.keys() else None,
        params={"property": apartment["internal_name"] or ""},
    )


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
        "sent": guest["submit_state"] == reporting.SENT,
    }
    if is_mine:
        doc = guest["doc_number"] or ""
        row["summary"] = {
            "nationality": validation.country_name(guest["nationality"], lang),
            "birth_date": validation.display_birth_date(guest["birth_date"])
            or validation.format_birth_date(guest["birth_date"]),
            "doc_number": "" if doc == validation.INPASS else doc,
            "purpose": validation.purpose_label(guest["purpose"], lang),
            "residence": validation.display_residence(
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
    apartment = _apartment_for_key(token)
    if _host_owns_apartment(request, apartment):
        return None
    row = claim.ensure_row(reservation["id"])
    if not claim.guest_access_open(reservation, row):
        return _unavailable(request, lang, "stay_gone", 404, token)
    if not _device_holds_claim(request, reservation["id"], row):
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
    reporting.submit_stay_if_complete(
        reservation["apartment_id"], reservation["id"]
    )


# --- privacy notice ------------------------------------------------------

@router.post("/l/{token}/pin")
async def verify_pin(token: str, request: Request):
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    form = await request.form()
    entered = (form.get("pin") or "").strip()
    expected = apartment["permalink_pin"] or ""
    # Keyed on the permanent token, never on the slug in the URL (WP19).
    lock_token = apartment["permalink_token"]
    pin_key = rate_limit.client_key(request, lock_token)
    pin_lock_key = f"{lock_token}:{auth.pin_fingerprint(lock_token, expected)}"
    link_locked = rate_limit.pin_token_blocked(pin_lock_key)
    if link_locked and not turnstile.required():
        return _pin_page(
            request,
            token,
            lang,
            error=i18n.translator(lang)("pin_locked_out"),
        )
    if (link_locked or rate_limit.pin_failure_count(pin_key) >= 3) and not turnstile.verify(
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
    if not auth.pin_matches(lock_token, entered, expected):
        rate_limit.record_pin_failure(pin_key, pin_lock_key)
        # A lockout spread over many addresses is invisible in the per-IP count,
        # so the host is told the moment the link itself burns its budget: every
        # guest using it is refused for a day until the PIN is rotated.
        if rate_limit.pin_token_blocked(pin_lock_key) and turnstile.required():
            alerts.raise_alert(
                "warning",
                "guest_pin_challenged",
                "Guest link now asks for a security check after repeated wrong PINs.",
                detail="Guests can still open it after the check. Generate a new PIN if the link may have leaked.",
                dedupe_key=f"guest_pin_challenged:{apartment['id']}",
                apartment_id=apartment["id"],
            )
            db.audit(
                "guest_pin_token_challenged",
                detail=f"apartment={apartment['id']}",
                actor="anonymous",
                owner_user_id=apartment["owner_user_id"],
            )
        elif rate_limit.pin_token_blocked(pin_lock_key):
            alerts.raise_alert(
                "critical",
                "guest_pin_locked_out",
                "Guest link locked out for 24 hours after repeated wrong PINs.",
                detail="Every guest using this link is refused until you generate a new PIN.",
                dedupe_key=f"guest_pin_locked_out:{apartment['id']}",
                apartment_id=apartment["id"],
            )
            db.audit(
                "guest_pin_token_locked",
                detail=f"apartment={apartment['id']}",
                actor="anonymous",
                owner_user_id=apartment["owner_user_id"],
            )
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
            # BE-13: a burst across links is a possible-incident signal for the
            # platform admins; it never creates an incident by itself.
            incidents.suggest_review_if_frequent()
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
    auth.attach_pin_session(response, lock_token, expected)
    return _with_lang(response, lang)


# Registered before /l/{token}/{reservation_id}, otherwise "privacy" is parsed
# as a reservation id and the guest gets a validation error instead of a page.
@router.get("/l/{token}/privacy")
def privacy_notice(token: str, request: Request):
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    back_url = _safe_return_to(request.query_params.get("return_to"), token, lang)
    context = _shared(request, token, lang, apartment)
    context.update(
        {
            "controller": _controller(apartment),
            "passport_photo_policy": apartment["passport_photo_policy"] or "off",
            "door_codes": apartment["lock_provider"] == "ttlock",
            "back_url": back_url,
        }
    )
    return _with_lang(render_guest(request, "guest/privacy.html", context), lang)


# --- stay selection ------------------------------------------------------

@router.get("/l/{token}")
def pick_stay(token: str, request: Request):
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    _alert_controller_missing(apartment)
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
                "arriving_today": bool(start and start == today),
                "ongoing": bool(start and end and start <= today < end),
            }
        )
    context = _shared(request, token, lang, apartment)
    context.update({"apartment": apartment, "rows": rows})
    return _with_lang(render_guest(request, "guest/pick.html", context), lang)


@router.get("/l/{token}/{reservation_id}")
def stay_overview(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
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
        if not _device_holds_claim(request, reservation["id"], claim_row):
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
            "claim_email_masked": claim_row["email_masked"] or "",
            "just_saved": request.query_params.get("saved") == "1",
            # "Reported" is a claim about the police, so it may only be made
            # when a form actually went out. ``locked`` is true for any signed,
            # complete form, which made the saved copy unreachable and told a
            # manual-mode guest their record had been reported when it had not.
            "just_reported": (
                request.query_params.get("saved") == "1"
                and any(person["mine"] and person["sent"] for person in people)
            ),
            "door_code": door_codes.view(reservation, apartment),
        }
    )
    return _with_lang(render_guest(request, "guest/stay.html", context), lang)


@router.get("/l/{token}/{reservation_id}/claim")
def claim_landing(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    _alert_controller_missing(apartment)
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
    reservation = _claimable_reservation(apartment, reservation_id)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    if _device_holds_claim(request, reservation_id, claim.ensure_row(reservation_id)):
        # Confirming spends the link, so a device that already confirmed would
        # otherwise land on a spent confirmation form. The cookie is what grants
        # access now; continue to the stay instead of asking the guest again.
        return _with_lang(
            RedirectResponse(
                _guest_link(token, reservation_id) + _lang_q(lang), status_code=303
            ),
            lang,
        )
    context = _shared(request, token, lang, apartment)
    context.update(
        {
            "apartment": apartment,
            "reservation": reservation,
            "claim_error": request.query_params.get("claim_error") == "1",
        }
    )
    return _with_lang(render_guest(request, "guest/confirm.html", context), lang)


def _throttle_guest_post(request: Request, token: str, scope: str, lang: str):
    """Refuse a writing guest POST that has used up its budget.

    Keyed on the peer address *and* the link, so one guest cannot spend another
    guest's allowance and a shared address cannot be exhausted by a single link.
    Returns the response to send, or None to carry on.
    """
    key = rate_limit.client_key(request, f"guest:{_lock_token(token)}")
    if rate_limit.blocked(scope, key, GUEST_POST_MAX_ATTEMPTS):
        return _unavailable(request, lang, "rate_limited", 429, token)
    rate_limit.record(scope, key)
    return None


@router.post("/l/{token}/{reservation_id}/claim/confirm")
async def claim_confirm(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
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
    reservation = _claimable_reservation(apartment, reservation_id)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    form = await request.form()
    secret = (form.get("secret") or "").strip()
    key = rate_limit.client_key(request, f"claim:{apartment['permalink_token']}")
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
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    throttle = _throttle_guest_post(request, token, "guest_party", lang)
    if throttle:
        return throttle
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
        await run_in_threadpool(_set_declared_guests, reservation, count)
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
        # Coarse IP+token throttle on the claim endpoint. It bounds request
        # hammering, not mail volume (the mail caps in claim.py do that), so it
        # is deliberately loose: a guest fumbling the form must not be locked
        # out after a couple of tries.
        key = rate_limit.client_key(request, f"claim:{apartment['permalink_token']}")
        if rate_limit.blocked("claim_start", key, 10):
            return _with_lang(
                RedirectResponse(
                    _guest_link(token, reservation_id) + _lang_q(lang, "&claim_error=rate"),
                    status_code=303,
                ),
                lang,
            )
        rate_limit.record("claim_start", key)
        ok, err, _secret = await run_in_threadpool(
            lambda: claim.start_claim(
                reservation,
                apartment,
                email=email,
                party_size=count,
                # The page is Czech by default; the e-mail is not, unless the guest
                # chose Czech. This value is stored on the claim, so the reminder
                # sent the day before the stay follows the same choice.
                lang=_mail_language(request),
                resend=resend or claim.is_claimed(claim_row),
            )
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
    claim_guard = _require_claim_session(request, reservation, token, lang)
    if claim_guard:
        return _with_lang(claim_guard, lang)
    if count < 1 or count > 60:
        return _with_lang(
            RedirectResponse(
                _guest_link(token, reservation_id) + _lang_q(lang, "&party_error=1"),
                status_code=303,
            ),
            lang,
        )
    await run_in_threadpool(_set_declared_guests, reservation, count)
    return _with_lang(
        RedirectResponse(_guest_link(token, reservation_id) + _lang_q(lang), status_code=303), lang
    )


@router.post("/l/{token}/{reservation_id}/another")
async def add_another_person(token: str, reservation_id: int, request: Request):
    """Raise the declared headcount by one so another guest can fill the form."""
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    throttle = _throttle_guest_post(request, token, "guest_another", lang)
    if throttle:
        return throttle
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
    residence_copied_from: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    # The key the guest is on (token or slug), so the form's own links stay on it.
    token = token or apartment["permalink_token"]
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
            # The name the address was copied from, so the guest knows why the
            # boxes are already full and that they may change them.
            "residence_copied_from": residence_copied_from,
            # The re-render guard for [F33]: only a value the save paths would
            # accept may go back into the hidden signature field. A row written
            # before the validator existed (a junk data URL, or "imported") must
            # not be handed back as if it were a drawn signature.
            "stored_signature": (
                guest["signature_png"]
                if guest and validation.is_valid_signature(guest["signature_png"])
                else ""
            ),
            "country_groups": codelists.country_groups(lang),
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
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    _alert_controller_missing(apartment)
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
    prefill, copied_from = _residence_prefill(request, reservation)
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
                values=prefill,
                residence_copied_from=copied_from,
                token=token,
                back_url=_form_back_url(token, apartment, reservation_id, lang, editing=False),
            ),
        ),
        lang,
    )


@router.get("/l/{token}/{reservation_id}/edit/{guest_id}")
def guest_form_edit(token: str, reservation_id: int, guest_id: int, request: Request):
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
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
                token=token,
            ),
        ),
        lang,
    )


@router.post("/l/{token}/{reservation_id}/save")
async def guest_form_save(token: str, reservation_id: int, request: Request):
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    throttle = _throttle_guest_post(request, token, "guest_save", lang)
    if throttle:
        return throttle
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
        if existing and existing["restricted_at"]:
            # BE-9: a restricted record is read-only until the host lifts it.
            return _with_lang(
                RedirectResponse(
                    _guest_link(token, reservation_id) + _lang_q(lang), status_code=303
                ),
                lang,
            )
        if existing and reporting.guest_form_locked(existing, reservation):
            return _unavailable(request, lang, "form_locked", 403, token)

    child_in_passport = bool(form.get("child_in_passport"))
    # One extractor for the host entry form and this one: the fields are the
    # same, and a field read in only one of them silently drops data from
    # whichever path was forgotten.
    raw = _guest_form_raw(form, apartment)

    # Un-clamped so an over-long name is reported back to the guest instead of
    # being cut mid-word and filed against a passport it no longer matches.
    values = validation.normalise_guest(raw, clamp=False)
    stay_from, stay_to = _stay_dates_from_form(
        form, (reservation["date_from"], reservation["date_to"])
    )
    signature = _kept_signature(form.get("signature"), existing["signature_png"] if existing else None)

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
    # A host may record a guest's real stay outside the booking (an early
    # arrival, a late departure), so the guest's own stored period is part of
    # what they are allowed to re-submit - otherwise the host's own edit would
    # leave the guest unable to save the form again.
    booked_from = validation.parse_iso_date(reservation["date_from"])
    booked_to = validation.parse_iso_date(reservation["date_to"])
    if existing:
        stored_from = validation.parse_iso_date(existing["stay_from"])
        stored_to = validation.parse_iso_date(existing["stay_to"])
        if stored_from:
            booked_from = min(booked_from, stored_from) if booked_from else stored_from
        if stored_to:
            booked_to = max(booked_to, stored_to) if booked_to else stored_to
    issues.extend(
        validation.validate_stay_dates(
            validation.parse_iso_date(stay_from),
            validation.parse_iso_date(stay_to),
            booked_from,
            booked_to,
        )
    )
    issues.extend(validation.validate_stay_date_text(stay_from, stay_to))
    if reporting.expected_guest_count(reservation) is None and not existing:
        if party_size < 1 or party_size > 60:
            issues.append(validation.Issue("party_size", translate("error_party_size")))
    # A guest may not declare their own paper import: that marker is the host's
    # attestation, and accepting it here stored an unsigned record as signed.
    signature_issue = reporting.guest_signature_issue(
        signature, translate, allow_imported=False
    )
    if signature_issue:
        issues.append(signature_issue)
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
                raw_upload = await passport_photos.read_upload_limited(passport_upload)
                # WP08: images are decoded and re-encoded here, so a file that
                # will not decode is refused on the form, not after saving.
                passport_bytes, passport_type = await run_in_threadpool(
                    passport_photos.prepare_upload,
                    raw_upload,
                    passport_upload.content_type or "",
                )
            except ValueError as exc:
                msg = str(exc)
                msg = PASSPORT_UPLOAD_MESSAGES.get(lang, {}).get(msg, msg)
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
            token=token,
        )
        context["values"].update(
            {
                "stay_from": stay_from,
                "stay_to": stay_to,
                "child_in_passport": child_in_passport,
                "parent_doc_number": form.get("parent_doc_number") or "",
                # Echo back only a signature the validator accepts: a hand-built
                # request must not get its blob mirrored into the next render.
                "signature": signature if validation.is_valid_signature(signature) else "",
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
            "notice_version": config.GUEST_NOTICE_VERSION,
            "notice_lang": lang,
            "notice_ack_at": now,
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
    if reporting.guest_correction_resets_attempts(existing):
        # Rule 10.4(5): a correction makes the record sendable again, and a
        # guest fixing their own form is a correction like any other. Without
        # this the sweep kept skipping the row at SUBMISSION_MAX_AUTO_ATTEMPTS
        # for ever while the stranded-records card resolved itself, so the
        # guest was never filed and nothing said so.
        payload["submit_attempts"] = 0

    if existing:
        # Compare-and-set: the sweep may have filed this guest, or may be
        # filing it right now (submission_claim), since `existing` was read.
        if not db.update_if(
            "guest",
            existing["id"],
            payload,
            {"submit_state": existing["submit_state"]},
            extra_where=(
                "NOT EXISTS (SELECT 1 FROM submission_claim "
                "WHERE guest_id = ? AND claimed_at >= ?)"
            ),
            extra_params=(existing["id"], time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS),
        ):
            return _unavailable(request, lang, "already_filed", 403, token)
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
        passport_photos.save_photo(saved_id, passport_bytes, passport_type, prepared=True)
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
    await run_in_threadpool(reporting.submit_stay_if_complete, apartment["id"], reservation_id)
    await run_in_threadpool(door_codes.on_registration_complete, reservation_id)
    await run_in_threadpool(
        lambda: claim.maybe_notify_completion(
            db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,)),
            apartment,
        )
    )

    response = RedirectResponse(
        _guest_link(token, reservation_id) + _lang_q(lang, "&saved=1"), status_code=303
    )
    _remember_owned(response, _owned_ids(request) + [saved_id])
    return _with_lang(response, lang)
