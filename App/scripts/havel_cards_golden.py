"""Write go/internal/web/ai/testdata/havel_cards_golden.json from the real Python.

Brief 1432: the confirm cards (app/havel_actions.py) and the support mail
(mail_notify.build_havel_support). No database: the three database lookups the
card code takes as arguments are stubbed, and guest_slug.link_key is replaced by
the slug the Go side will read.

    .venv/bin/python scripts/havel_cards_golden.py          write the file
    .venv/bin/python scripts/havel_cards_golden.py --check  exit 1 when stale
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

os.environ["UBYHOST_SECRET_KEY"] = "havel-golden-secret-0123456789-abcdef"
os.environ["UBYHOST_PUBLIC_BASE_URL"] = "https://app.example.test/"
os.environ["UBYHOST_OPERATOR_EMAIL"] = "support@example.test"
APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
OUT = APP.parent / "go" / "internal" / "web" / "ai" / "testdata" / "havel_cards_golden.json"

from app import guest_slug, havel_actions, mail_notify  # noqa: E402

TODAY = date(2026, 11, 13)


def row(pid, name, active=1, archived=None, token="tok", pin="1234"):
    return {"id": pid, "internal_name": name, "active": active, "archived_at": archived, "permalink_token": token, "permalink_pin": pin}


ROWS = [row(11, "Flat A"), row(12, "Chata", pin=None), row(13, "", token=None), row(14, "Closed", active=0)]  # archived rows never reach the cards: access.apartments leaves them out


def act(**kw):
    base = {"type": "create_stay", "property_id": 11, "date_from": "2026-12-01", "date_to": "2026-12-04", "guests": 2,
            "guest_email": "guest@example.test", "start_time": None, "end_time": None, "note": "late arrival"}
    base.update(kw)
    return base


ACTIONS = [
    ("stay", act()), ("stay no extras", act(guests=None, guest_email=None, note=None)), ("stay bad email", act(guest_email="nope")),
    ("stay email spaces", act(guest_email="  a@b.cz  ")), ("stay overlap", act(property_id=12)),
    ("stay long note", act(note="n" * 600)), ("stay 366 nights", act(date_to="2027-12-02")), ("stay 365 nights", act(date_to="2027-12-01")),
    ("stay end before start", act(date_to="2026-12-01")), ("stay past window", act(date_from="2025-11-12", date_to="2025-11-14")),
    ("stay last past day", act(date_from="2025-11-13", date_to="2025-11-14")),
    ("stay far future", act(date_from="2028-11-14", date_to="2028-11-16")), ("stay last future day", act(date_from="2028-11-12", date_to="2028-11-14")),
    ("stay no date", act(date_from=None)), ("stay bad date", act(date_from="2026-13-01")), ("stay newline date", act(date_from="2026-12-01\n")),
    ("stay guests 61", act(guests=61)), ("stay guests 60", act(guests=60)), ("stay closed property", act(property_id=14)),
    ("stay archived property is not in the list", act(property_id=15)), ("stay unknown property", act(property_id=99)), ("stay no property", act(property_id=None)),
    ("cleaning", act(type="create_cleaning", date_to=None, guests=None, guest_email=None, start_time="10:00", end_time="12:30", note="windows")),
    ("cleaning no times", act(type="create_cleaning", date_to=None, guests=None, guest_email=None)),
    ("cleaning bad time", act(type="create_cleaning", start_time="25:00", end_time=None)),
    ("cleaning end before start", act(type="create_cleaning", start_time="12:00", end_time="11:00")),
    ("cleaning newline time", act(type="create_cleaning", start_time="10:00\n", end_time="11:00")),
    ("cleaning equal times", act(type="create_cleaning", start_time="10:00", end_time="10:00")),
    ("link", act(type="show_guest_link")), ("link no pin", act(type="show_guest_link", property_id=12)),
    ("link no token", act(type="show_guest_link", property_id=13)), ("pin", act(type="new_pin")), ("pin closed", act(type="new_pin", property_id=14)),
    ("sync", act(type="sync_calendars")), ("sync no feeds", act(type="sync_calendars"), "nofeeds"),
]

FEEDS = {11: 2, 12: 0}
OVERLAPS = {12}


def cards() -> list:
    guest_slug.link_key = lambda r: ("slug-%d" % r["id"]) if r and r["permalink_token"] else ""
    out = []
    for item in ACTIONS:
        name, action = item[0], item[1]
        feeds = {} if len(item) > 2 else FEEDS
        try:
            card = havel_actions.prepare(action, ROWS, TODAY, return_to="/havel?x=1",
                                         overlaps=lambda pid, s, e: 1 if pid in OVERLAPS else 0,
                                         feed_count=lambda pid: feeds.get(pid, 0))
            result = {"card": json.loads(json.dumps(card, default=lambda o: dict(o) if isinstance(o, dict) else str(o)))}
        except havel_actions.NotPrepared as exc:
            result = {"not_prepared": exc.reason}
        out.append({"name": name, "action": action, "no_feeds": len(item) > 2, "today": TODAY.isoformat(), "return_to": "/havel?x=1", **result})
    return out


def mails() -> list:
    out = []
    for kw in [
        dict(account_email="host@example.test", workspace="Anna's flats", lang="cs", page="stays", summary="Cannot find <the> button", note="please & thanks", turns=["first q", "second q"]),
        dict(account_email="host@example.test", workspace="", lang="en", page="", summary="", note="", turns=[]),
        dict(account_email="h@example.test", workspace="  Long   name  " + "x" * 100, lang="vi", page="guide", summary="s", note="n", turns=["a", "b", "c", "d"]),
    ]:
        content = mail_notify.build_havel_support(**kw)
        out.append({"in": kw, "subject": content["subject"], "text": content["text"], "html": content["html"]})
    return out


def main(argv: list) -> int:
    text = json.dumps({"cards": cards(), "mails": mails()}, ensure_ascii=False, indent=1) + "\n"
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("stale:", OUT.relative_to(APP.parent))
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
