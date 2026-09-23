"""Shared Jinja environment and the helpers templates are allowed to call."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from . import (
    __version__,
    access,
    alerts,
    auth,
    config,
    deadlines,
    host_i18n,
    onboarding,
    operator,
    reporting,
    security,
    seo,
    validation,
)

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


# One date format for the whole app: a page, an alert and an e-mail must never
# print the same stay differently.
_fmt_date = validation.fmt_date


def _weekday(value: Optional[str]) -> str:
    parsed = validation.parse_iso_date(value)
    return parsed.strftime("%a") if parsed else ""


def _nights(date_from: Optional[str], date_to: Optional[str]) -> int:
    start, end = validation.parse_iso_date(date_from), validation.parse_iso_date(date_to)
    return (end - start).days if start and end else 0


def _from_json(value: Optional[str]) -> Any:
    try:
        return json.loads(value or "[]")
    except (TypeError, ValueError):
        return []


@pass_context
def _template_translate(context, key: str, **kwargs) -> str:
    request = context.get("request")
    lang = host_i18n.lang_from_request(request) if request else host_i18n.DEFAULT_LANGUAGE
    return host_i18n.translate(lang, key, **kwargs)


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
        if amount == 1:
            key += ".one"
        elif 2 <= amount <= 4:
            key += ".few"
    return host_i18n.translate(lang, key, n=amount)


templates.env.filters["date_cz"] = _fmt_date
templates.env.filters["weekday"] = _weekday
templates.env.filters["from_json"] = _from_json
templates.env.globals["t"] = _template_translate
templates.env.globals.update(
    app_version=__version__,
    operator=operator.details,
    deployment_tier=config.DEPLOYMENT,
    ubyport_env=config.UBYPORT_ENV,
    public_base_url=config.PUBLIC_BASE_URL,
    turnstile_site_key=config.TURNSTILE_SITE_KEY if config.TURNSTILE_ENABLED else "",
    describe_time_left=_template_time_left,
    urgency=deadlines.urgency,
    reporting_deadline=deadlines.reporting_deadline,
    deadline_anchor=reporting.reservation_deadline_anchor,
    purpose_label=validation.purpose_label,
    country_name=validation.country_name,
    format_birth_date=validation.format_birth_date,
    display_birth_date=validation.display_birth_date,
    compose_residence=validation.compose_residence,
    nights=_nights,
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
    # The property switcher lives in the sidebar on every host page, so it must not
    # depend on which route remembered to pass its own list. Routes that need the
    # full rows (the dashboard) or the same list for a filter keep passing their own.
    if workspace and workspace["id"] and data.get("show_nav", True) and "apartments" not in data:
        data["apartments"] = access.apartments(request, "id, internal_name")
    data.setdefault("flash", request.query_params.get("msg"))
    data.setdefault("flash_error", request.query_params.get("err"))
    data.setdefault("celebration_milestone", None)
    data.setdefault("sent_guest_count", 0)
    data.setdefault("minutes_saved", 0)
    data.setdefault("demo_available", config.UBYPORT_ENV == "mock")
    if workspace and workspace["id"]:
        data.setdefault("onboarding", onboarding.progress(workspace["id"]))
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
    data.setdefault("flash", request.query_params.get("msg"))
    data.setdefault("flash_error", request.query_params.get("err"))
    return templates.TemplateResponse(request, name, data, status_code=status_code)
