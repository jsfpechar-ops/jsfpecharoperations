"""Write the Go golden files of the guide import port from the real Python code.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt):

    .venv/bin/python scripts/guide_import_golden.py

It writes go/internal/guideimport/testdata/golden.json (trim, prompt, verify,
clean, Apify requests and answers) and go/internal/anthropic/testdata/golden.json
(token estimate, budget math, the exact Anthropic and Mistral request bodies,
answer handling). The Go tests reproduce every case. No database and no network
are used: the script replaces the database reads, the HTTP post and the model
client with fakes. Running it twice leaves git status clean.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

# The model features and keys must be set before app.config is imported.
for name in list(os.environ):
    if name.startswith(("UBYHOST_AI_", "UBYHOST_MISTRAL_", "UBYHOST_ANTHROPIC_", "UBYHOST_APIFY_")):
        del os.environ[name]
os.environ.update({
    "UBYHOST_AI_FEATURES": "guide_import",
    "UBYHOST_ANTHROPIC_API_KEY": "test-key",
    "UBYHOST_MISTRAL_API_KEY": "test-mistral-key",
    "UBYHOST_APIFY_TOKEN": "test-token",
})

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import requests  # noqa: E402

from app import ai, config, db, guest_guide, guest_guide_import as gi, guest_guide_merge as gm  # noqa: E402

GO = APP.parent / "go" / "internal"
OUT_GUIDE = GO / "guideimport" / "testdata" / "golden.json"
OUT_AI = GO / "anthropic" / "testdata" / "golden.json"


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --- trim ---------------------------------------------------------------------

BOOKING_ITEM = {
    "name": "  Apartment   Vltava View ",
    "description": "Quiet flat near the river.\n\nCheck-in from 15:00 at the key box.   WiFi password: Sunrise2024.",
    "checkIn": "15:00 - 22:00",
    "checkOut": "until 11:00",
    "address": {"full": "Dlouhá 12, 110 00 Praha 1, Czechia", "street": "Dlouhá 12"},
    "photos": [{"url": "https://example.test/p1.jpg"}, {"url": "https://example.test/p2.jpg"}],
    "images": ["https://example.test/i1.jpg"],
    "rating": 9.1,
    "reviews": [{"text": "great"}],
}

AIRBNB_ITEM = {
    "title": "Cosy loft with balcony",
    "description": "Bright loft.\tThe key is in the lockbox, code 4821.",
    "subDescription": "Second floor, no lift.",
    "propertyType": "Entire loft",
    "roomType": None,
    "amenities": [
        {"title": "Kitchen", "values": [
            {"title": "Refrigerator", "subtitle": "", "available": True},
            {"title": "Dishwasher", "available": False},
            {"title": "Coffee maker", "subtitle": "Nespresso"},
        ]},
        {"title": "Heating", "values": [{"title": "Central heating"}]},
        {"title": "Kitchen", "values": [{"title": "Refrigerator"}]},
    ],
    "houseRules": [
        {"title": "During your stay", "values": [{"title": "No smoking"}, {"title": "No parties or events"}]},
        {"title": "Checking in and out", "additional": "Check-in after 16:00", "general": [{"title": "Checkout before 10:00"}]},
    ],
    "locationDescriptions": ["Near the metro", {"content": "Tram 22 stops at the door"}],
    "highlights": [{"title": "Self check-in", "subtitle": "Check yourself in with the lockbox."}],
    "address": "Vinohradská 5, Praha",
    "images": [{"url": "https://example.test/a.jpg"}, "https://example.test/b.jpg"],
    "photos": ["https://example.test/c.jpg"],
}

NUMBERS_ITEM = {
    "name": 4.5,
    "description": 100000.0,
    "checkIn": 1e22,
    "checkOut": 0.00001,
    "address": {"full": "", "street": 12345678901234567890},
}

NUMBERS_ITEM_2 = {
    "name": True,
    "description": 1e16,
    "checkIn": 1e15,
    "checkOut": 0.0001,
    "address": {"street": 123456.789},
}

UNICODE_ITEM = {
    "name": "Pokoj s výhledem​ na řeku\x1fx",
    "description": "Ž" * 3 + " příliš žluťoučký kůň \U0001F600 emoji",
    "checkIn": "   ",
    "address": {"full": None, "street": "Ulice 1"},
}


def _big() -> dict:
    # Over 64 KiB once stored: CJK characters are three bytes each.
    text = "中" * 4000
    lines = [f"文{n:03d}" + "字" * 190 for n in range(100)]
    return {
        "title": text, "description": text, "subDescription": text, "propertyType": text, "roomType": text,
        "amenities": lines, "houseRules": lines, "locationDescriptions": lines, "highlights": lines,
        "address": "A" * 400,
    }


def trim_cases() -> list:
    cases = [
        ("booking_sample", "booking", BOOKING_ITEM),
        ("airbnb_sample", "airbnb", AIRBNB_ITEM),
        ("numbers_airbnb", "airbnb", NUMBERS_ITEM),
        ("numbers_booking", "booking", NUMBERS_ITEM),
        ("numbers_booking_2", "booking", NUMBERS_ITEM_2),
        ("unicode_booking", "booking", UNICODE_ITEM),
        ("size_halving_airbnb", "airbnb", _big()),
        ("only_source", "booking", {"rating": 9}),
        ("unknown_source", "other", {"name": "x"}),
        ("not_a_dict", "booking", [1, 2]),
        ("address_empty_string", "booking", {"name": "N", "address": "   "}),
        ("airbnb_scalar_amenities", "airbnb", {"title": "T", "amenities": "Wifi", "highlights": {"available": False, "title": "x"}}),
    ]
    out = []
    for name, source, item in cases:
        data = gi.trim(source, item)
        out.append({
            "name": name, "source": source, "item": item,
            "expect_json": json.dumps(data, ensure_ascii=False),
            "photo_urls_of_trimmed": gi._photo_urls(source, data) if source in ("booking", "airbnb") else [],
            "photo_urls_of_raw_item": gi._photo_urls(source, item) if source in ("booking", "airbnb") and isinstance(item, dict) else [],
        })
    return out


# --- text helpers and the prompt -------------------------------------------------

NORMALISE_INPUTS = [
    "Check-In: 15:00!", "ŠTĚSTÍ  a   radost", "Straße", "İstanbul", "ǅungla", "ﬁne ﬂat", "Ｗｉｆｉ １２３",
    "a​b", "café", "ΣΊΣΥΦΟΣ", "xͅy", "  ", "", "Tel: +420 123-456", "ǈǅ", "Ω ohm",
    "tab\tnew\nline", "snake_case_word", "ᾳ ῼ", "ẞ", "½ cup", "①②③", "ẹ́",
]

NAMES_INPUTS = [
    "Go to Prague by tram. Ask Jan at the desk.",
    "line one\nLine two starts here and Karel helps",
    "the password is Sunrise2024 and WiFi works",
    "visit Český Krumlov: Château de Lyon!",
    "ABC Def Ghi aB Ab1 Xyz",
    "x Øresund Ünal Şişli",
    "end. Start of sentence. Middle Word",
    "ǅungla is tricky and Ａpple too",
]

LANG_DATA = [
    {"description": "Příliš žluťoučký kůň úpěl ďábelské ódy " * 3},
    {"description": "The quick brown fox jumps over the lazy dog " * 3},
    {},
    {"description": "a" * 99 + "ě"},
    {"description": "a" * 98 + "ě"},
    {"description": "12345 !!!"},
    {"name": "Hotel", "amenities": ["Wifi", "Parkování"]},
]

LISTING_DATA = [
    {"name": "  Flat  ", "title": "T", "address": "Street 1", "checkIn": "15:00", "description": "d1\nd2",
     "houseRules": ["No smoking", "  ", " Quiet after 22:00 ", 7, None, True],
     "amenities": ["Wifi"], "highlights": [], "locationDescriptions": ["Metro"], "extra": "ignored"},
    {"description": ["not", "a", "string"], "subDescription": "   ", "name": 5},
    {},
]

EARLIER = [
    {"id": 1, "kind": "checkin", "topic": "arrival", "title": "", "location": "Key box", "steps": "Code 4821", "watch_out": "", "source": "booking"},
    {"id": 2, "kind": "custom", "topic": "rooms", "title": "Sauna", "location": "", "steps": "", "watch_out": "", "source": "airbnb"},
    {"id": 3, "kind": "wifi", "topic": "wifi", "title": "", "location": "", "steps": "Password Sunrise2024", "watch_out": "Slow in the evening", "source": "paste"},
]


def user_turn_cases() -> list:
    out = []
    for source, item in (("booking", BOOKING_ITEM), ("airbnb", AIRBNB_ITEM), ("airbnb", UNICODE_ITEM)):
        data = gi.trim(source, item)
        for earlier in ([], EARLIER):
            lang = gm.language_of(data)
            out.append({"source": source, "data": data, "earlier": earlier, "lang": lang,
                        "out": gm.user_turn(source, data, earlier, lang),
                        "earlier_text": gm._earlier_text(earlier)})
    return out


# --- verify and clean -------------------------------------------------------------

LISTING = {
    "name": "Apartment Vltava",
    "description": "Check-in from 15:00 at the key box, code 4821. WiFi password is Sunrise2024. "
                   "Contact Jan Novak at +420 123 456 789 or jan@example.com. Visit www.example.com for the guide.",
    "checkIn": "15:00 - 22:00",
    "houseRules": ["No smoking inside", "Quiet hours from 22:00 to 07:00"],
}
CORPUS = gm.normalise(gm.listing_text(LISTING) + "\n" + gm._earlier_text([]))


def card(**kw) -> dict:
    base = {"kind": "checkin", "topic": "", "title": "", "location": "At the key box", "steps": "Check in from 15:00.\nUse code 4821.",
            "watch_out": "", "quotes": ["Check-in from 15:00 at the key box, code 4821"]}
    base.update(kw)
    return base


VERIFY_CARDS = [
    ("ok", card()),
    ("ok_crlf_and_spaces", card(steps="  Check in from 15:00.\r\nUse code 4821.  ")),
    ("bad_kind", card(kind="pool")),
    ("kind_not_string", card(kind=5)),
    ("custom_bad_topic", card(kind="custom", topic="nope", title="Pool")),
    ("custom_empty_topic", card(kind="custom", topic="", title="Pool")),
    ("custom_no_title", card(kind="custom", topic="rooms", title=" ")),
    ("custom_ok", card(kind="custom", topic="rooms", title="Quiet hours", location="", steps="Quiet hours from 22:00 to 07:00",
                       quotes=["Quiet hours from 22:00 to 07:00"])),
    ("builtin_title_dropped", card(title="Check in")),
    ("empty", card(location="", steps="")),
    ("length_location", card(location="x" * 501)),
    ("length_steps", card(steps="y" * 4001)),
    ("quotes_missing", card(quotes=[])),
    ("quotes_not_list", card(quotes="Check-in from 15:00")),
    ("quotes_too_many", card(quotes=["Check-in from 15:00 at the key box"] * 5)),
    ("quote_short", card(quotes=["key box"])),
    ("quote_not_in_listing", card(quotes=["Check-in from 17:00 at the key box"])),
    ("quote_long", card(quotes=["Check-in from 15:00 at the key box " * 12])),
    ("quote_casefold_ok", card(quotes=["CHECK-IN FROM 15:00 AT THE KEY BOX"])),
    ("number_not_quoted", card(steps="Check in from 15:00.\nUse code 9999.")),
    ("number_range", card(steps="Quiet hours 22:00-07:00", quotes=["Quiet hours from 22:00 to 07:00"])),
    ("name_not_quoted", card(steps="Ask Maria at the desk.", quotes=["Check-in from 15:00 at the key box, code 4821"])),
    ("name_quoted", card(steps="Ask Jan Novak at the desk.", quotes=["Contact Jan Novak at +420 123 456 789 or jan@example.com"])),
    ("contact_email_not_quoted", card(steps="Mail jan@example.org please", quotes=["Check-in from 15:00 at the key box, code 4821"])),
    ("contact_phone_quoted", card(steps="Call +420 123 456 789", quotes=["Contact Jan Novak at +420 123 456 789 or jan@example.com"])),
    ("contact_phone_not_quoted", card(steps="Call +420 999 888 777", quotes=["Check-in from 15:00 at the key box, code 4821"])),
    ("contact_www", card(steps="See www.example.net", quotes=["Visit www.example.com for the guide"])),
    ("fields_numbers_as_text", card(location=5, steps="Check in from 15:00.", watch_out=None)),
    ("topic_field_missing", {"kind": "wifi", "location": "Router", "steps": "WiFi password is Sunrise2024", "quotes": ["WiFi password is Sunrise2024"]}),
]


def verify_cases() -> list:
    out = []
    for name, c in VERIFY_CARDS:
        work = json.loads(json.dumps(c))
        reason = gm.verify(work, CORPUS)
        out.append({"name": name, "card": c, "corpus": CORPUS, "reason": reason, "card_after": work})
    return out


def clean_cases() -> list:
    ok = card()
    wifi = card(kind="wifi", location="Router", steps="WiFi password is Sunrise2024", quotes=["WiFi password is Sunrise2024"])
    custom_a = card(kind="custom", topic="rooms", title="Quiet hours", location="", steps="Quiet hours from 22:00 to 07:00",
                    quotes=["Quiet hours from 22:00 to 07:00"])
    custom_b = dict(custom_a, title="QUIET HOURS")
    many = [dict(ok, kind="checkin")] + [dict(wifi)] * 2 + ["not a dict", 5, None] + [dict(ok, kind="pool")] * 3
    sets = [
        ("mixed", [ok, wifi, custom_a, custom_b, dict(ok), "x", dict(ok, kind="zzz")]),
        ("twelve_cap", [dict(wifi, kind="wifi")] + [dict(custom_a, title=f"Card {n}") for n in range(20)]),
        ("shapes", many),
        ("empty", []),
    ]
    out = []
    for name, cards in sets:
        work = json.loads(json.dumps(cards))
        kept, dropped = gm.clean(work, CORPUS)
        out.append({"name": name, "cards": cards, "corpus": CORPUS, "kept": kept, "dropped": dropped})
    return out


ATTEMPTS = [None, "", "stale", "merge:json:2", "merge:json:x", "merge:a:b:3", "merge:x:", "merge:x:007", "other:x:2",
            "merge:input_too_large", "merge:api:1", "merge:error:12"]


# --- Apify ------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status: int, content: bytes):
        self.status_code = status
        self.content = content

    def json(self):
        return json.loads(self.content)


def apify_cases() -> dict:
    from urllib.parse import urlencode

    calls = []
    plan = {"resp": None}
    original = gi.requests.post

    def fake_post(endpoint, params=None, headers=None, timeout=None, data=None, allow_redirects=True):
        calls.append({"endpoint": endpoint, "query": urlencode(params), "headers": headers, "timeout": list(timeout),
                      "body": data, "allow_redirects": allow_redirects})
        if plan["resp"] == "network":
            raise requests.ConnectionError("boom")
        return plan["resp"]

    gi.requests.post = fake_post
    try:
        requests_out = []
        for source, url in (("booking", "https://www.booking.com/hotel/cz/vltava-view.html"),
                            ("airbnb", "https://www.airbnb.com/rooms/12345678"),
                            ("booking", 'https://www.booking.com/hotel/cz/q"uote\\.html')):
            plan["resp"] = FakeResponse(200, b'[{"name": "X"}]')
            calls.clear()
            gi._fetch(source, url)
            requests_out.append(dict(calls[0], source=source, url=url))
        big = b'[{"a": "' + b"x" * (4 * 1024 * 1024) + b'"}]'
        cases = [
            ("ok_200", 200, b'[{"name": "X", "n": 1.5, "list": [1, 2]}, {"other": 1}]'),
            ("ok_201", 201, b'[{"name": "X"}]'),
            ("empty_list", 200, b"[]"),
            ("object", 200, b'{"name": "X"}'),
            ("first_not_dict", 200, b"[1]"),
            ("bad_json", 200, b"not json"),
            ("trailing", 200, b'[{"a": 1}] x'),
            ("status_408", 408, b""),
            ("status_500", 500, b"oops"),
            ("status_302", 302, b""),
            ("status_404", 404, b"{}"),
            ("status_429", 429, b"{}"),
            ("too_large", 200, big),
            ("network", "network", b""),
        ]
        fetch = []
        for name, status, body in cases:
            plan["resp"] = "network" if status == "network" else FakeResponse(status, body)
            try:
                item = gi._fetch("booking", "https://www.booking.com/hotel/cz/vltava-view.html")
                result = {"item": item}
            except gi.GuideImportError as exc:
                result = {"error": exc.key}
            entry = {"name": name, "status": status, "result": result}
            if name == "too_large":
                entry["body_kind"] = "big"
            else:
                entry["body"] = body.decode()
            fetch.append(entry)
    finally:
        gi.requests.post = original
    return {"requests": requests_out, "fetch": fetch, "api_base": gi.APIFY_API, "actors": gi.ACTORS,
            "timeout": list(gi.HTTP_TIMEOUT), "max_bytes": 4 * 1024 * 1024}


# --- ai.py: estimate, budget, request bodies, answers ----------------------------------

ESTIMATE_CASES = [
    (["a", "bc"], [{"role": "user", "content": "hello"}]),
    ([], []),
    (["Příliš žluťoučký \U0001F600"], [{"role": "user", "content": 'quote " backslash \\ tab \t nl \n cr \r bell \x07 del \x7f ž   <tag> & é'}]),
    (["x" * 1001], [{"role": "user", "content": "y" * 77}, {"role": "assistant", "content": "z"}]),
    ([gm.SYSTEM_RULES], [{"role": "user", "content": gm.user_turn("booking", gi.trim("booking", BOOKING_ITEM), EARLIER, "en")}]),
]


class FakeLedger:
    def __init__(self, rows):
        self.rows = rows

    def query_one(self, sql, params=()):
        feature = params[0]
        if "key = ?" in sql:
            day, key = params[1], params[2]
            match = [r for r in self.rows if r["feature"] == feature and r["day"] == day and r["key"] == key]
        elif len(params) == 2:
            match = [r for r in self.rows if r["feature"] == feature and r["day"] == params[1]]
        else:
            match = [r for r in self.rows if r["feature"] == feature and params[1] <= r["day"] <= params[2]]
        return {name: sum(r[name] for r in match) for name in
                ("input_tokens", "cache_write_tokens", "cache_read_tokens", "output_tokens")}


def row(day, key="", i=0, w=0, r=0, o=0, feature="guide_import"):
    return {"day": day, "feature": feature, "key": key, "input_tokens": i, "cache_write_tokens": w,
            "cache_read_tokens": r, "output_tokens": o}


BUDGET_CASES = [
    ("empty", {}, [], "7", "2026-11-13"),
    ("small_spend_ok", {}, [row("2026-11-01", "7", i=1_000_000, o=100_000)], "7", "2026-11-13"),
    ("month_spent", {}, [row("2026-11-02", "7", i=60_000_000, o=10_000_000, w=1_000_000, r=5_000_000)], "7", "2026-11-13"),
    ("day_over_allowance", {}, [row("2026-11-13", "7", i=40_000_000)], "7", "2026-11-13"),
    ("earlier_day_does_not_count_as_today", {}, [row("2026-11-12", "7", i=20_000_000)], "7", "2026-11-13"),
    ("key_cap", {"UBYHOST_AI_KEY_DAILY_USD_GUIDE_IMPORT": "0.05"},
     [row("2026-11-13", "7", i=1_000_000), row("2026-11-13", "8", i=100_000)], "7", "2026-11-13"),
    ("key_cap_other_key_ok", {"UBYHOST_AI_KEY_DAILY_USD_GUIDE_IMPORT": "0.05"},
     [row("2026-11-13", "7", i=1_000_000), row("2026-11-13", "8", i=100_000)], "8", "2026-11-13"),
    ("last_day_of_month", {}, [row("2026-11-10", "7", i=30_000_000)], "7", "2026-11-30"),
    ("february_non_leap", {"UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT": "3"}, [row("2027-02-03", "7", i=1_000_000)], "7", "2027-02-28"),
    ("february_leap", {}, [row("2028-02-01", "7", i=2_000_000, o=300_000)], "7", "2028-02-15"),
    ("monthly_zero", {"UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT": "0"}, [], "7", "2026-11-13"),
    ("monthly_bad_value_not_used", {"UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT": "2.5"}, [row("2026-11-04", "7", i=7_000_000)], "7", "2026-11-13"),
    ("other_feature_ignored", {}, [row("2026-11-04", "7", i=900_000_000, feature="havel")], "7", "2026-11-13"),
    ("no_key", {"UBYHOST_AI_KEY_DAILY_USD_GUIDE_IMPORT": "0.05"}, [row("2026-11-13", "7", i=1_000_000)], None, "2026-11-13"),
]


def budget_cases() -> list:
    out = []
    original = db.query_one
    try:
        for name, env, rows, key, day_text in BUDGET_CASES:
            for env_name in ("UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT", "UBYHOST_AI_KEY_DAILY_USD_GUIDE_IMPORT"):
                os.environ.pop(env_name, None)
            os.environ.update(env)
            db.query_one = FakeLedger(rows).query_one
            day = date.fromisoformat(day_text)
            out.append({
                "name": name, "env": env, "rows": rows, "key": key, "day": day_text,
                "month_usd": ai.month_spend_usd("guide_import", day),
                "day_usd": ai.day_spend_usd("guide_import", day),
                "key_usd": ai.key_day_spend_usd("guide_import", key, day) if key is not None else None,
                "allowance": ai.daily_allowance_usd("guide_import", day),
                "fraction": ai.budget_fraction("guide_import", day),
                "state": ai.budget_state("guide_import", key, day),
                "monthly_cap": config.ai_monthly_usd("guide_import"),
                "key_cap": config.ai_key_daily_usd("guide_import"),
            })
    finally:
        db.query_one = original
        for env_name in ("UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT", "UBYHOST_AI_KEY_DAILY_USD_GUIDE_IMPORT"):
            os.environ.pop(env_name, None)
    return out


class FakeMessages:
    def __init__(self, parent):
        self.parent = parent

    def create(self, **kwargs):
        self.parent.calls.append(kwargs)
        reply = self.parent.reply
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeClient:
    def __init__(self):
        self.calls = []
        self.reply = None
        self.messages = FakeMessages(self)


def usage(i=10, w=2, r=3, o=4):
    return SimpleNamespace(input_tokens=i, cache_creation_input_tokens=w, cache_read_input_tokens=r, output_tokens=o)


def anthropic_reply(text, stop="end_turn", blocks=None):
    content = blocks if blocks is not None else [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(usage=usage(), stop_reason=stop, content=content, _request_id="req_1")


def call_outcome(call):
    try:
        return {"ok": call()}
    except ai.AIError as exc:
        return {"error": exc.reason}


def model_cases() -> dict:
    data = gi.trim("booking", BOOKING_ITEM)
    lang = gm.language_of(data)
    system = [gm.SYSTEM_RULES]
    messages = [{"role": "user", "content": gm.user_turn("booking", data, EARLIER, lang)}]
    saved = (ai.budget_state, ai._record, ai._warn_budget)
    ai.budget_state = lambda *a, **k: "ok"
    ai._record = lambda *a, **k: None
    ai._warn_budget = lambda *a, **k: None
    client = FakeClient()
    ai.set_client_for_tests(client)
    out = {"system": system, "messages": messages, "schema": gm.SCHEMA, "key": "7"}
    try:
        client.reply = anthropic_reply('{"cards": []}')
        ai.call("guide_import", system, messages, gm.SCHEMA, key="7")
        out["anthropic_body"] = client.calls[0]
        out["anthropic_two_blocks_body"] = None
        client.calls.clear()
        ai.call("guide_import", ["first", "second"], [{"role": "user", "content": "hi"}], {"type": "object"}, key=None, max_tokens=800)
        out["anthropic_two_blocks_body"] = client.calls[0]
        out["anthropic_two_blocks_input"] = {"system": ["first", "second"], "messages": [{"role": "user", "content": "hi"}],
                                             "schema": {"type": "object"}, "max_tokens": 800}
        answers = [
            ("ok", anthropic_reply('{"cards": [{"kind": "wifi"}], "n": 1.5}')),
            ("ok_whitespace", anthropic_reply('  {"cards": []}\n')),
            ("refusal", anthropic_reply("", stop="refusal")),
            ("max_tokens", anthropic_reply("{}", stop="max_tokens")),
            ("no_text_block", anthropic_reply("", blocks=[SimpleNamespace(type="thinking", text="x")])),
            ("no_blocks", anthropic_reply("", blocks=[])),
            ("empty_text", anthropic_reply("")),
            ("bad_json", anthropic_reply("nope")),
            ("trailing_text", anthropic_reply('{"a": 1} x')),
            ("json_list", anthropic_reply("[1]")),
            ("json_string", anthropic_reply('"x"')),
            ("second_block_text", anthropic_reply("", blocks=[SimpleNamespace(type="thinking", text="x"),
                                                              SimpleNamespace(type="text", text='{"a": 2}')])),
            ("api_error", RuntimeError("boom")),
        ]
        out["anthropic_answers"] = []
        for name, reply in answers:
            client.reply = reply
            result = call_outcome(lambda: ai.call("guide_import", ["s"], [{"role": "user", "content": "u"}], {"type": "object"}, key="1"))
            out["anthropic_answers"].append({"name": name, "result": result})

        # Mistral
        posted = []
        mistral_reply = {"value": None}

        def fake_post(body):
            posted.append(body)
            reply = mistral_reply["value"]
            if isinstance(reply, Exception):
                raise reply
            return reply

        saved_post = ai._mistral_post
        ai._mistral_post = fake_post
        config.AI_PROVIDER = "mistral"
        try:
            good = {"choices": [{"finish_reason": "stop", "message": {"content": '{"cards": []}'}}], "usage": {"prompt_tokens": 5, "completion_tokens": 6}}
            mistral_reply["value"] = good
            ai.call("guide_import", system, messages, gm.SCHEMA, key="7")
            out["mistral_body"] = posted[0]
            posted.clear()
            ai.call("guide_import", ["first", "second"], [{"role": "user", "content": "hi"}], {"type": "object"}, key=None, max_tokens=800)
            out["mistral_two_blocks_body"] = posted[0]
            m_answers = [
                ("ok", good),
                ("length", {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}),
                ("model_length", {"choices": [{"finish_reason": "model_length", "message": {"content": "{}"}}]}),
                ("no_content", {"choices": [{"finish_reason": "stop", "message": {}}]}),
                ("blank_content", {"choices": [{"finish_reason": "stop", "message": {"content": "  "}}]}),
                ("list_content", {"choices": [{"finish_reason": "stop", "message": {"content": [{"type": "text"}]}}]}),
                ("no_choices", {}),
                ("bad_json", {"choices": [{"finish_reason": "stop", "message": {"content": "nope"}}]}),
                ("json_list", {"choices": [{"finish_reason": "stop", "message": {"content": "[1]"}}]}),
                ("post_error", RuntimeError("boom")),
            ]
            out["mistral_answers"] = []
            for name, reply in m_answers:
                mistral_reply["value"] = reply
                result = call_outcome(lambda: ai.call("guide_import", ["s"], [{"role": "user", "content": "u"}], {"type": "object"}, key="1"))
                out["mistral_answers"].append({"name": name, "result": result})
        finally:
            config.AI_PROVIDER = "anthropic"
            ai._mistral_post = saved_post
        # Refusals before any request
        out["too_large"] = call_outcome(lambda: ai.call("guide_import", ["x" * 120_002], [{"role": "user", "content": "u"}], {"type": "object"}))
        out["max_input_tokens"] = config.AI_MAX_INPUT_TOKENS
        out["max_tokens"] = config.AI_MAX_TOKENS
        out["model"] = config.AI_MODEL
        out["mistral_model"] = config.MISTRAL_MODEL
        out["prices"] = config.AI_PRICE_USD_PER_MTOK
    finally:
        ai.set_client_for_tests(None)
        ai.budget_state, ai._record, ai._warn_budget = saved
    return out


def main() -> None:
    guide = {
        "system_rules": gm.SYSTEM_RULES,
        "schema": gm.SCHEMA,
        "kinds": [[k, t] for k, t in guest_guide.KINDS.items()],
        "topics": list(guest_guide.TOPICS),
        "limits": {k: guest_guide.LIMITS[k] for k in ("title", "location", "steps", "watch_out")},
        "stale_running_seconds": int(gi.STALE_RUNNING.total_seconds()),
        "trim": trim_cases(),
        "normalise": [{"in": s, "out": gm.normalise(s)} for s in NORMALISE_INPUTS],
        "names": [{"in": s, "out": gm._names(s)} for s in NAMES_INPUTS],
        "language_of": [{"data": d, "out": gm.language_of(d)} for d in LANG_DATA],
        "listing_text": [{"data": d, "out": gm.listing_text(d)} for d in LISTING_DATA],
        "user_turn": user_turn_cases(),
        "verify": verify_cases(),
        "clean": clean_cases(),
        "attempts": [{"in": s, "out": gm._attempts(s)} for s in ATTEMPTS],
        "apify": apify_cases(),
    }
    write(OUT_GUIDE, guide)
    model = {
        "estimate": [{"system": s, "messages": m, "out": ai.estimate_input_tokens(s, m)} for s, m in ESTIMATE_CASES],
        "budget": budget_cases(),
        "model": model_cases(),
    }
    write(OUT_AI, model)
    print(f"wrote {OUT_GUIDE.relative_to(APP.parent)} and {OUT_AI.relative_to(APP.parent)}")


if __name__ == "__main__":
    main()
