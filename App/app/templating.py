"""Shared Jinja environment and the helpers templates are allowed to call."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates

from . import __version__, alerts, auth, config, deadlines, reporting, validation

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


def _fmt_date(value: Optional[str]) -> str:
    parsed = validation.parse_iso_date(value)
    return parsed.strftime("%d.%m.%Y") if parsed else (value or "")


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


templates.env.filters["date_cz"] = _fmt_date
templates.env.filters["weekday"] = _weekday
templates.env.filters["from_json"] = _from_json
templates.env.globals.update(
    app_version=__version__,
    ubyport_env=config.UBYPORT_ENV,
    public_base_url=config.PUBLIC_BASE_URL,
    describe_time_left=deadlines.describe_time_left,
    urgency=deadlines.urgency,
    reporting_deadline=deadlines.reporting_deadline,
    purpose_label=validation.purpose_label,
    country_name=validation.country_name,
    format_birth_date=validation.format_birth_date,
    display_birth_date=validation.display_birth_date,
    compose_residence=validation.compose_residence,
    status_labels=reporting.STATUS_LABELS,
    nights=_nights,
    parse_iso_date=validation.parse_iso_date,
    today=lambda: date.today(),
    now=lambda: datetime.now(),
)


def render(request: Request, name: str, context: Optional[Dict[str, Any]] = None, status_code: int = 200):
    data = dict(context or {})
    data["request"] = request
    data.setdefault("password_is_set", auth.password_is_set())
    data.setdefault("open_alerts", alerts.open_alerts())
    data.setdefault("flash", request.query_params.get("msg"))
    data.setdefault("flash_error", request.query_params.get("err"))
    return templates.TemplateResponse(name, data, status_code=status_code)


def render_guest(request: Request, name: str, context: Optional[Dict[str, Any]] = None, status_code: int = 200):
    """Guest-facing pages never show host alerts."""
    data = dict(context or {})
    data["request"] = request
    data["open_alerts"] = []
    data.setdefault("flash", request.query_params.get("msg"))
    data.setdefault("flash_error", request.query_params.get("err"))
    return templates.TemplateResponse(name, data, status_code=status_code)
