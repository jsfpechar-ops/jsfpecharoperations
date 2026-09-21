"""Bundled Airbnb-shaped sample calendar for demo mode (works without the mock server)."""
from __future__ import annotations

from datetime import timedelta

from fastapi.responses import Response

from . import deadlines


def sample_airbnb_ics() -> str:
    today = deadlines.local_now().date()
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID;X-RICAL-TZSOURCE=TZINFO:-//Airbnb Inc//Hosting Calendar 0.8.8//EN",
        "CALSCALE:GREGORIAN",
        "VERSION:2.0",
        "X-WR-CALNAME:UbyHost sample calendar",
    ]
    stays = [
        ("arriving-today", today, 4, "Reserved", "0431"),
        ("arrived-yesterday", today - timedelta(days=1), 3, "Reserved", "7788"),
        ("tomorrow", today + timedelta(days=1), 3, "Reserved", "2201"),
        ("two-days", today + timedelta(days=2), 2, "Reserved", "2202"),
        ("next-week", today + timedelta(days=7), 5, "Reserved", "1290"),
        ("czech-visit", today + timedelta(days=9), 2, "Reserved", "3301"),
        ("past-open", today - timedelta(days=8), 3, "Reserved", "4401"),
        ("lock-me", today + timedelta(days=6), 2, "Reserved", "5501"),
        ("far-ahead", today + timedelta(days=45), 4, "Reserved", "6601"),
        ("blocked", today + timedelta(days=3), 2, "Airbnb (Not available)", None),
    ]
    for name, start, nights, summary, phone in stays:
        lines += [
            "BEGIN:VEVENT",
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{start + timedelta(days=nights):%Y%m%d}",
            f"UID:sample-{name}@airbnb.com",
            f"SUMMARY:{summary}",
        ]
        if phone:
            lines.append(
                "DESCRIPTION:Reservation URL: https://www.airbnb.com/hosting/reservations/"
                f"details/HMSAMPLE{phone}\\nPhone Number (Last 4 Digits): {phone}"
            )
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def sample_calendar_response() -> Response:
    body = sample_airbnb_ics().encode("utf-8")
    return Response(
        body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="sample-airbnb.ics"'},
    )
