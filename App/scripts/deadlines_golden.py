"""Write go/internal/deadlines/testdata/golden.json from the real Python deadlines.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/deadlines_golden.py

The Go test in go/internal/deadlines/ compares every case. A "now" ending in Z
is an aware UTC instant (Python converts it to Prague time); one without Z is
a naive Prague wall clock (Python uses it as it is).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from app import deadlines  # noqa: E402

OUT = APP.parent / "go" / "internal" / "deadlines" / "testdata" / "golden.json"
PRAGUE = ZoneInfo("Europe/Prague")
STAMP = "%Y-%m-%dT%H:%M:%S"


def _dates() -> list[date]:
    days: set[date] = set()
    for first, last in (
        ("2026-11-02", "2026-11-08"),  # a full week, Monday to Sunday
        ("2026-10-22", "2026-10-27"),  # DST ends Sunday 25 Oct
        ("2026-03-26", "2026-03-31"),  # DST starts Sunday 29 Mar
        ("2026-12-29", "2027-01-04"),  # year boundary
        ("2026-01-29", "2026-02-03"),  # month boundary
        ("2026-02-25", "2026-03-02"),  # February to March
        ("2024-02-27", "2024-03-01"),  # leap day
        ("2026-06-01", "2026-06-02"),  # summer time
    ):
        day = date.fromisoformat(first)
        while day <= date.fromisoformat(last):
            days.add(day)
            day += timedelta(days=1)
    return sorted(days)


def _nows(check_in: date) -> list[str]:
    due = datetime.combine(deadlines.add_working_days(check_in, 3), time(23, 59, 59))
    due_utc = due.replace(tzinfo=PRAGUE).astimezone(timezone.utc)
    out = [(due_utc + timedelta(seconds=s)).strftime(STAMP) + "Z" for s in (
        -4 * 86400, -2 * 86400 - 1, -2 * 86400, -86401, -86400, -3600, -1, 0, 1, 3600,
        47 * 3600, 2 * 86400, 5 * 86400 + 7)]
    midnight = datetime.combine(check_in, time(0, 0))
    out.append((midnight - timedelta(hours=12)).strftime(STAMP) + "Z")
    out.append((midnight + timedelta(hours=22, minutes=30)).strftime(STAMP) + "Z")
    out.append(midnight.strftime(STAMP))  # naive
    out.append((midnight + timedelta(hours=12)).strftime(STAMP))  # naive
    out.append(due.strftime(STAMP))  # naive, exactly at the deadline
    out.append((due + timedelta(seconds=1)).strftime(STAMP))  # naive, one second after
    return out


def _case(check_in: date, text: str) -> dict:
    if text.endswith("Z"):
        now = datetime.strptime(text[:-1], STAMP).replace(tzinfo=timezone.utc)
    else:
        now = datetime.strptime(text, STAMP)
    kind, amount = deadlines.time_left_parts(check_in, now)
    return {
        "check_in": check_in.isoformat(),
        "now": text,
        "local_now": deadlines.local_now(now).strftime(STAMP),
        "hours_left": deadlines.hours_left(check_in, now),
        "urgency": deadlines.urgency(check_in, now),
        "parts": [kind, amount],
        "describe": deadlines.describe_time_left(check_in, now),
    }


def _lines(rows: list) -> str:
    return "[\n" + ",\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n]"


def render() -> str:
    days = _dates()
    sections = {
        "working_days": [{"date": d.isoformat(), "working": deadlines.is_working_day(d)} for d in days],
        "add": [
            {"start": d.isoformat(), "count": n, "result": deadlines.add_working_days(d, n).isoformat()}
            for d in days
            for n in (0, 1, 3, 5)
        ],
        "deadlines": [
            {"check_in": d.isoformat(), "deadline": deadlines.reporting_deadline(d).strftime(STAMP)}
            for d in days
        ],
        "cases": [_case(d, text) for d in days for text in _nows(d)],
    }
    head = {
        "reporting_working_days": deadlines.REPORTING_WORKING_DAYS,
        "urgency_order": deadlines.URGENCY_ORDER,
    }
    body = ",\n".join(f'"{name}": {_lines(rows)}' for name, rows in sections.items())
    return "{\n" + json.dumps(head, sort_keys=True)[1:-1] + ",\n" + body + "\n}\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")
