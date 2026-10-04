"""Shared Jinja environment and the helpers templates are allowed to call."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from markupsafe import Markup, escape

from . import (
    __version__,
    acceptance,
    access,
    alerts,
    analytics,
    auth,
    config,
    deadlines,
    host_i18n,
    i18n,
    onboarding,
    operator,
    reporting,
    security,
    seo,
    validation,
    validation_i18n,
)

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


# One date format for the whole app: a page, an alert and an e-mail must never
# print the same stay differently.
_fmt_date = validation.fmt_date


def _money_czk(haler, quantity=1) -> str:
    """Display stored haler without truncating cents or fractional quantities."""
    amount = (Decimal(str(haler or 0)) / Decimal(str(quantity or 1)) / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return f"{amount:,.2f}".replace(",", "\u00a0").replace(".", ",") + " Kč"


def _weekday(value: Optional[str]) -> str:
    parsed = validation.parse_iso_date(value)
    return parsed.strftime("%a") if parsed else ""


def _nights(date_from: Optional[str], date_to: Optional[str]) -> int:
    start, end = validation.parse_iso_date(date_from), validation.parse_iso_date(date_to)
    return (end - start).days if start and end else 0


def _nights_key(count: int) -> str:
    """One/few/many already lives in ``host_i18n``; this only renames its suffix.

    Czech picks its form from the count and English follows the same rule, so
    the decision is shared rather than written twice. A-13 fixes the guest key
    names, so ``nights.one`` becomes ``night_one``.
    """
    suffix = host_i18n.plural_key("night", count).rpartition(".")[2]
    return {
        "one": "night_one",
        "few": "nights_few",
    }.get(suffix, "nights_many")


@pass_context
def _nights_label(context, date_from: Optional[str], date_to: Optional[str]) -> str:
    """The length of the stay, in words: "1 night" but "3 noci" and "5 nocí"."""
    count = _nights(date_from, date_to)
    request = context.get("request")
    lang = context.get("lang") or (
        host_i18n.lang_from_request(request) if request else host_i18n.DEFAULT_LANGUAGE
    )
    return i18n.translator(lang)(_nights_key(count), n=count)


def _from_json(value: Optional[str]) -> Any:
    try:
        return json.loads(value or "[]")
    except (TypeError, ValueError):
        return []


def _datetime_local(value: Optional[str], seconds: bool = False) -> str:
    """A stored UTC timestamp, in the host's own time zone.

    Every timestamp the app writes comes from ``db.utcnow()``, so a Prague host
    was reading summer times two hours early: a batch that left at 19:37 showed
    as "Sent at 17:37". The value is shown as stored if it cannot be parsed, so
    an odd row stays visible instead of silently blanking out.
    """
    text = (value or "").strip()
    if not text:
        return ""
    width = 19 if seconds else 16
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text[:width].replace("T", " ")
    if parsed.tzinfo is None:
        # Every writer stores UTC, so a naive value is one of ours.
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(ZoneInfo(config.TIMEZONE))
    return local.strftime("%Y-%m-%d %H:%M:%S")[:width]


@pass_context
def _template_translate(context, key: str, **kwargs) -> str:
    request = context.get("request")
    lang = host_i18n.lang_from_request(request) if request else host_i18n.DEFAULT_LANGUAGE
    return host_i18n.translate(lang, key, **kwargs)


@pass_context
def _template_legal_effective(context, doc: str) -> str:
    """"Effective date: ... Version ..." for /terms, /privacy or /dpa (WP24).

    The date is the single ``config.LEGAL_EFFECTIVE_DATE`` and the version is
    the one hosts accept, so the page can never show another number.
    """
    request = context.get("request")
    lang = host_i18n.lang_from_request(request) if request else host_i18n.DEFAULT_LANGUAGE
    return host_i18n.translate(
        lang,
        f"{doc}.effective",
        date=acceptance.effective_date_text(host_i18n.normalise_language(lang)),
        version=acceptance.current_versions()[doc],
    )


@pass_context
def _template_plural(context, base: str, n: int, **kwargs) -> str:
    """A counted string, in the one/few/many form its count needs.

    "3 nocí" and "1 nights" are both wrong, and both come from printing one
    form of a key whatever the number was. Templates call ``tp('key', n)``.
    """
    request = context.get("request")
    lang = host_i18n.lang_from_request(request) if request else host_i18n.DEFAULT_LANGUAGE
    return host_i18n.translate_plural(lang, base, n, **kwargs)


@pass_context
def _template_identity_visible(context, guest_id=None) -> bool:
    """``access.identity_visible`` for templates; see there."""
    request = context.get("request")
    return access.identity_visible(request, guest_id) if request else False


@pass_context
def _template_guest_identifier(context, value, guest_id) -> str:
    """A document or visa number as this request may see it."""
    request = context.get("request")
    if request is None:
        return access.mask_identifier(value)
    return access.identifier_for(request, guest_id, value)


@pass_context
def _template_impersonation_minutes_left(context):
    request = context.get("request")
    return auth.impersonation_minutes_left(request) if request else None


@pass_context
def _template_time_left(context, check_in) -> str:
    """The deadline countdown, in the host's language.

    This is the most load-bearing text on the work queue, so it must not be
    the one English string left on an otherwise Czech page.
    """
    request = context.get("request")
    lang = host_i18n.lang_from_request(request) if request else host_i18n.DEFAULT_LANGUAGE
    kind, amount = deadlines.time_left_parts(check_in)
    key = f"deadline.{kind}"
    if kind in ("arrives_days", "days_left", "overdue_days"):
        # Only these keys ship one/few forms; the hour countdowns are "5 h".
        key = host_i18n.plural_key(key, amount)
    return host_i18n.translate(lang, key, n=amount)


@pass_context
def _template_validation_message(context, message: str) -> str:
    """A validation sentence in the host's language.

    ``validation.py`` writes these in English because that is the language the
    code reads in; the host reads them in the property banner and on the guest
    cards. Translating at the point of display keeps one copy of the sentence.
    """
    request = context.get("request")
    lang = host_i18n.lang_from_request(request) if request else host_i18n.DEFAULT_LANGUAGE
    return validation_i18n.localize(message, lang)


# Portal names are proper nouns the host already reads on the portal itself.
# Only the values UbyHost writes need translating, and an unknown slug falls
# back to the slug so a new portal degrades to something, not to a raw key.
_PORTAL_LABELS = {
    "airbnb": "Airbnb",
    "booking": "Booking.com",
    "agoda": "Agoda",
    "vrbo": "Vrbo",
    "expedia": "Expedia",
    "tripadvisor": "Tripadvisor",
    "trip": "Trip.com",
    "google": "Google Calendar",
    "apple": "Apple Calendar",
}
_SOURCE_KEYS = {"manual": "stays.source.manual", "ical": "stays.source.ical"}
_ENTERED_BY_KEYS = {
    "guest": "stay.detail.guests.entered_by.guest",
    "host": "stay.detail.guests.entered_by.host",
    "import": "stay.detail.guests.entered_by.import",
}


@pass_context
def _source_label(context, reservation) -> str:
    """Where a stay came from, in the host's language.

    ``reservation.summary`` is the portal's own event title ("Reserved"), so it
    cannot label the Source column: the stored ``source`` is the only value
    that means the same thing in both languages.
    """
    source = (reservation["source"] or "").strip()
    if source in _PORTAL_LABELS:
        return _PORTAL_LABELS[source]
    key = _SOURCE_KEYS.get(source)
    if key:
        return _template_translate(context, key)
    return source.replace("_", " ").capitalize()


@pass_context
def _entered_by_label(context, value) -> str:
    """Who typed a guest record, as a word rather than the stored slug."""
    key = _ENTERED_BY_KEYS.get((value or "").strip())
    return _template_translate(context, key) if key else (value or "")


# Ticket Wallet dates: "28 SEP", "Mon", "Mon 28 Sep" in the guest's language.
# Kept here rather than in i18n.py because they are formats, not sentences.
_PASS_MONTHS = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "cs": ("led", "úno", "bře", "dub", "kvě", "čvn", "čvc", "srp", "zář", "říj", "lis", "pro"),
    "de": ("Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"),
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
    "fr": ("janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"),
}
_PASS_WEEKDAYS = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "cs": ("po", "út", "st", "čt", "pá", "so", "ne"),
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "es": ("lun", "mar", "mié", "jue", "vie", "sáb", "dom"),
    "fr": ("lun", "mar", "mer", "jeu", "ven", "sam", "dim"),
}


@pass_context
def _pass_date(context, value: Optional[str], part: str = "dm") -> str:
    """One piece of a stay date for the ticket layout.

    ``dm`` -> "28 Sep" (CSS upper-cases it), ``wd`` -> "Mon",
    ``long`` -> "Mon 28 Sep". An unparseable value returns "" so a broken
    reservation never crashes a guest page.
    """
    parsed = validation.parse_iso_date(value)
    if not parsed:
        return ""
    lang = context.get("lang") if context.get("lang") in _PASS_MONTHS else "en"
    day_month = f"{parsed.day} {_PASS_MONTHS[lang][parsed.month - 1]}"
    weekday = _PASS_WEEKDAYS[lang][parsed.weekday()]
    if part == "wd":
        return weekday
    if part == "long":
        return f"{weekday} {day_month}"
    return day_month


@pass_context
def _report_mode_label(context, mode) -> str:
    """How a transmission was triggered, translated rather than humanised."""
    key = f"reports.mode.{(mode or '').strip()}"
    text = _template_translate(context, key)
    return text if text != key else (mode or "").replace("_", " ").capitalize()


# The legal documents name each other by path — "the Data Processing Agreement
# at /dpa", "contact details on /legal" — which leaves the reader to retype the
# URL. Only these five sibling paths are linkified, so no other slash-word in a
# legal sentence is ever turned into a link, and the anchor text stays exactly
# the path the sentence already prints: the legal copy is untouched and the
# visible label remains the accessible name.
_LEGAL_PATHS = ("/dpa", "/legal", "/privacy", "/subprocessors", "/terms")

_LEGAL_PATH_RE = re.compile(
    r"(^|(?<=[\s(]))("
    + "|".join(re.escape(path) for path in _LEGAL_PATHS)
    + r")(?=$|[\s.,;:)])"
)


def _legal_link(match: "re.Match[str]") -> str:
    prefix, path = match.group(1), match.group(2)
    return f'{prefix}<a href="{path}">{path}</a>'


def _legal_links(value: object) -> Markup:
    """Make the raw legal cross-references in a body clickable.

    The input is escaped first and the markup added second, so a body can never
    inject HTML through this filter.
    """
    return Markup(_LEGAL_PATH_RE.sub(_legal_link, escape(str(value))))


templates.env.filters["date_cz"] = _fmt_date
templates.env.filters["money_czk"] = _money_czk
templates.env.filters["weekday"] = _weekday
templates.env.filters["datetime_local"] = _datetime_local
templates.env.filters["from_json"] = _from_json
templates.env.filters["legal_links"] = _legal_links
templates.env.globals["t"] = _template_translate
templates.env.globals["legal_effective"] = _template_legal_effective
templates.env.globals["bilingual_message"] = host_i18n.bilingual_message
templates.env.globals["identity_visible"] = _template_identity_visible
templates.env.globals["guest_identifier"] = _template_guest_identifier
# WP26: the guest switcher names each language in its own words.
templates.env.globals["guest_endonyms"] = i18n.ENDONYMS
templates.env.globals["impersonation_minutes_left"] = _template_impersonation_minutes_left
templates.env.globals.update(
    app_version=__version__,
    operator=operator.details,
    deployment_tier=config.DEPLOYMENT,
    ubyport_env=config.UBYPORT_ENV,
    public_base_url=config.PUBLIC_BASE_URL,
    turnstile_site_key=config.TURNSTILE_SITE_KEY if config.TURNSTILE_ENABLED else "",
    describe_time_left=_template_time_left,
    validation_message=_template_validation_message,
    urgency=deadlines.urgency,
    reporting_deadline=deadlines.reporting_deadline,
    deadline_anchor=reporting.reservation_deadline_anchor,
    deadline_cell=reporting.deadline_cell,
    purpose_label=validation.purpose_label,
    country_name=validation.country_name,
    format_birth_date=validation.format_birth_date,
    display_birth_date=validation.display_birth_date,
    compose_residence=validation.compose_residence,
    nights=_nights,
    nights_label=_nights_label,
    pass_date=_pass_date,
    source_label=_source_label,
    entered_by_label=_entered_by_label,
    report_mode_label=_report_mode_label,
    tp=_template_plural,
    parse_iso_date=validation.parse_iso_date,
    today=lambda: date.today(),
    now=lambda: datetime.now(),
)


def render(request: Request, name: str, context: Optional[Dict[str, Any]] = None, status_code: int = 200):
    data = dict(context or {})
    data["request"] = request
    data["csrf_token"] = security.csrf_token(request)
    data.setdefault("current_user", auth.current_user(request))
    data.setdefault("workspace_user", auth.workspace_user(request))
    # A visitor who has not chosen a language yet gets Czech on the signed-out
    # pages; inside the app the existing fallback stays in place.
    fallback = (
        host_i18n.DEFAULT_LANGUAGE if data["current_user"]
        else host_i18n.PUBLIC_DEFAULT_LANGUAGE
    )
    # Macros reach the language through the request, not this context.
    request.state.lang = host_i18n.resolve_language(request, default=fallback)
    data["lang"] = request.state.lang
    for key, value in seo.head_links(request).items():
        data.setdefault(key, value)
    workspace = data["workspace_user"]
    if "open_alerts" not in data:
        raw_alerts = (
            alerts.open_alerts(workspace["id"]) if workspace else (
                [] if auth.accounts_exist() else alerts.open_alerts()
            )
        )
        data["open_alerts"] = alerts.present_many(raw_alerts, data["lang"])
    # Navigation must use the workspace's complete, owner-scoped property set,
    # never a filtered route list (which may omit the enabled property).
    data["host_has_stay_fees"] = False
    if workspace and workspace["id"] and data.get("show_nav", True):
        nav_properties = access.apartments(request, "id, internal_name, active, stay_fee_rate_czk")
        data.setdefault("apartments", nav_properties)
        data["host_has_stay_fees"] = any(
            p["active"] and (p["stay_fee_rate_czk"] or 0) > 0 for p in nav_properties
        )
    data.setdefault("flash", request.query_params.get("msg"))
    data.setdefault("flash_error", request.query_params.get("err"))
    data.setdefault("celebration_milestone", None)
    data.setdefault("sent_guest_count", 0)
    data.setdefault("minutes_saved", 0)
    data.setdefault("demo_available", config.UBYPORT_ENV == "mock")
    if workspace and workspace["id"]:
        data.setdefault("onboarding", onboarding.progress(workspace["id"]))
    # WP09: set here, never from a route's context, so only the allowed public
    # templates can ever get a tag (and the matching CSP in main._harden).
    data["umami_tag"] = analytics.tag() if analytics.mark_public_page(request, name) else None
    response = templates.TemplateResponse(request, name, data, status_code=status_code)
    # Arriving on a ?lang= link (the hreflang URLs search engines index) is as
    # much a choice as clicking the switcher, so it survives the next click.
    asked_for = host_i18n.supported_language(request.query_params.get("lang"))
    if asked_for and request.cookies.get(host_i18n.LANG_COOKIE) != asked_for:
        host_i18n.remember_language(response, asked_for)
    return response


def render_guest(request: Request, name: str, context: Optional[Dict[str, Any]] = None, status_code: int = 200):
    """Guest-facing pages never show host alerts."""
    data = dict(context or {})
    data["request"] = request
    data["csrf_token"] = security.csrf_token(request)
    data["open_alerts"] = []
    data["umami_tag"] = None  # permanent rule: guest pages are never measured
    data.setdefault("flash", request.query_params.get("msg"))
    data.setdefault("flash_error", request.query_params.get("err"))
    return templates.TemplateResponse(request, name, data, status_code=status_code)
