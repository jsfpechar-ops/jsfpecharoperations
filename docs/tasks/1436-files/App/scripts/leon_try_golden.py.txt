"""Write the Leon test-message data and golden cases for go/internal/web/ai from the real Python.

Brief 1436. Run from App/ (no database: the item rows and the stored answers are fed in, ai.call and the
rate-limit helpers are replaced):

    .venv/bin/python scripts/leon_try_golden.py            write the files
    .venv/bin/python scripts/leon_try_golden.py --check    exit 1 and name each stale file

Files written into go/internal/web/ai/:
  leon_prompt.txt            leon.CHARACTER, byte for byte
  leon_guest_i18n.json       the guest strings Leon's fixed replies and the quick-answer lines read (i18n.py)
  leon_facts_catalog.json    guide_facts.FACTS, in order
  testdata/leon_try_golden.json   Python's answers
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("UBYHOST_SECRET_KEY", "leon-golden-secret-0123456789-abcdef")
APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
PKG = APP.parent / "go" / "internal" / "web" / "ai"

from app import ai, db, guide_facts, guest_guide, host_i18n, i18n, leon  # noqa: E402


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def guest_i18n_json() -> str:
    keys = sorted({k for t in i18n.STRINGS.values() for k in t if k.startswith(("leon_", "guide_fact_"))})
    catalog = {lang: {k: t[k] for k in keys if k in t} for lang, t in i18n.STRINGS.items()}
    return json.dumps(catalog, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def row(item_id, kind, state, visibility="everyone", title="", location="", steps="", watch_out="", video_url="", photos=0):
    return {"id": item_id, "apartment_id": 1, "topic": "custom", "kind": kind, "title": title, "location": location, "steps": steps,
            "watch_out": watch_out, "video_url": video_url, "visibility": visibility, "state": state, "source": "host", "sort_order": 0,
            "created_at": "x", "updated_at": "x", "photos": photos}


MUST = [row(1, "checkin", "done", location="Key box by the door", steps="1. Enter code 4711\n2. Take the key\n  3. Lock up", watch_out="Do not slam the <door>", photos=2),
        row(2, "wifi", "done", location="Router in the hall", steps="Network Flat-5G\nPassword on the router"),
        row(3, "heating", "done"), row(4, "checkout", "done", steps="Leave by 11:00"),
        row(5, "emergency", "done", location="Phone 112 for all emergencies", steps="Fire 150\nAmbulance 155\nHost: ask in the app")]
EXTRA = [row(6, "parking", "done", visibility="host", steps="Secret garage code 99999"), row(7, "custom", "done", visibility="booked", title="Pool <fun>", steps="Open 9:00-20:00", video_url="https://v.example/x"),
         row(8, "kitchen_appliances", "missing"), row(9, "bathroom", "check", location="draft text"), row(10, "washing_machine", "skipped")]
SCENARIOS = {
    "not live": [row(1, "checkin", "done"), row(2, "wifi", "done")],
    "live": MUST + EXTRA,
    "live no emergency text": [r for r in MUST if r["kind"] != "emergency"] + [row(5, "emergency", "skipped")],
}
FACT_ROWS = [{"fact": "checkin_from", "value": "15:00"}, {"fact": "pets", "value": "yes"}, {"fact": "smoking", "value": "no"},
             {"fact": "quiet_hours", "value": "22:00-07:00"}, {"fact": "dishwasher", "value": "yes"}, {"fact": "washing_machine", "value": "no"},
             {"fact": "balcony", "value": ""}, {"fact": "step.times", "value": "seen"}]


def patched_db(rows, facts):
    def query(sql, params=()):
        if "FROM guide_item" in sql:
            return [dict(r) for r in rows]
        if "FROM guide_fact" in sql:
            return [dict(r) for r in facts]
        raise AssertionError("unexpected query: " + sql)
    return query


def reply(kind="answer", text="Check-in is from 15:00.", sources=("c1",), summary=None, upset=False):
    return {"kind": kind, "reply": text, "sources": list(sources), "host_summary": summary, "upset": upset}


def cases() -> dict:
    out: dict = {}
    texts = ["", "hello", "mail me at anna.b@example.test or +420 777 123 456", "booking AB1234567 and room 12", "call 777 123 456 now", "x1234-5678y", "a-1-2-3-4",
             "code 12345 and 123456", "id AB-12-34-56", "á123456 and 123456á", "+420 777 123 4567a", "(0049) 123-4567-89", "phone 12 34 56 78 90",
             "1111 2222 3333 4444", "abc123def456", "12-34-56-78", "١٢٣٤٥٦٧٨", "tel.+420777123456."]
    out["redact"] = [{"in": t, "out": leon.redact(t)} for t in texts]
    folds = ["Hello!", "  HI  ", "Dobrý den", "dobry   den!!", "Thank you.", "Thanks a LOT", "danke schön", "Straße", "Ça va?", "hello, where is the wifi", "díky", "ok thanks", "Дякую", "..."]
    out["fold"] = [{"in": t, "fold": leon.fold(t), "small": leon.smalltalk_kind(t)} for t in folds]
    noise = ["?", "123", "😀", "https://x.example/a", "www.x.com", "see https://x.example", "²", "Ⅰ", "_", "a", "中", " ", "12 34", "http://", "-- ?? 77"]
    out["noise"] = [{"in": t, "out": leon.is_noise(t)} for t in noise]
    names = ["Jan Novak", "  Jana   Nováková ", "Firma s.r.o.", "ACME Ltd", "Hotel 5", "", "Beach GmbH", "Anna", "Foo Inc", "Foo Incorporated", "A.S. Holding", "spol. s r. o."]
    out["first_name"] = [{"in": n, "out": leon.host_first_name(n)} for n in names]
    out["named"] = [{"lang": lang, "key": key, "host": n, "out": leon._named(lang, key, n)} for lang in ("en", "cs") for key in ("leon_passed_to_host", "leon_asked_host", "leon_asked_host_sorry") for n in ("Jan Novak", "")]
    out["fixed"] = {lang: {k: leon._fixed(lang, k) for k in ("leon_hi", "leon_thanks", "leon_unclear", "leon_refuse", "leon_about", "leon_emergency", "leon_asked_host_part")} for lang in ("en", "cs")}
    out["too_long"] = {lang: leon._fixed(lang, "leon_too_long", n=leon.MAX_MESSAGE_CHARS) for lang in ("en", "cs")}
    out["schema_compact"] = json.dumps(leon.SCHEMA, separators=(",", ":"), ensure_ascii=False)
    out["constants"] = {"max_tokens": leon.MAX_TOKENS, "max_message": leon.MAX_MESSAGE_CHARS, "max_reply": leon.MAX_REPLY_CHARS, "max_summary": leon.MAX_SUMMARY_CHARS,
                        "try_max": leon.TRY_MAX, "prompt_sha": sha(leon.CHARACTER)}

    real_query = db.query
    out["for_guest"] = []
    try:
        for name, rows in SCENARIOS.items():
            db.query = patched_db(rows, FACT_ROWS)
            cards = guide_facts.for_guest(1, "booked", "en")
            blocks = leon.system_blocks(cards, 'Flat "A" <b>')
            out["for_guest"].append({"name": name, "rows": rows, "facts": FACT_ROWS, "cards": cards,
                                     "guide_block": blocks[1], "system_sha": [sha(b) for b in blocks],
                                     "emergency": {lang: leon.emergency_text(lang, cards) for lang in ("en", "cs")}})
    finally:
        db.query = real_query

    live_cards = out["for_guest"][1]["cards"]
    out["user_turn"] = [{"in": t, "lang": lang, "out": leon.user_turn(t, lang)} for t in ["where is the key?", "a <b> tag", "  spaced  "] for lang in ("en", "cs")]
    base_msg = "What time is check-in? my number is 777 123 456 and code 4711"
    vcases = [
        ("answer", reply()), ("answer many sources", reply(text="Key box by the door. Wifi is Flat-5G.", sources=("c1", "c2", "c1"))),
        ("answer bad source", reply(sources=("c99",))), ("answer no source", reply(sources=())), ("answer source text", reply(sources=("zzz", 5, "c1 "))),
        ("answer empty", reply(text=" ")), ("answer long", reply(text="a" * 801)), ("answer max", reply(text="a" * 800)),
        ("answer url", reply(text="see https://x.example")), ("answer at", reply(text="mail a@b")), ("answer markup", reply(text="use **bold**")),
        ("answer backtick", reply(text="run `x`")), ("answer angle", reply(text="<b>x</b>")),
        ("answer number bad", reply(text="Code is 9999")), ("answer number card", reply(text="Enter code 4711")), ("answer number message", reply(text="You said 123456 earlier", sources=("c1",))),
        ("answer step numbers", reply(text="1. Enter code 4711\n2) Take the key", sources=("c1",))), ("answer step then bad", reply(text="1. Enter code 4711\n9. Take 8 keys", sources=("c1",))),
        ("answer emergency number", reply(text="Call 112 now", sources=("c5",))), ("answer summary", reply(summary="Where is the pool? mail a@b.cz")),
        ("answer summary long", reply(summary="s" * 400)), ("answer upset", reply(upset=True)),
        ("ask_host", reply(kind="ask_host", summary="no wifi card", upset=True)), ("ask_host no summary", reply(kind="ask_host")),
        ("refuse", reply(kind="refuse", summary="x", upset=True)), ("about_me", reply(kind="about_me")), ("unclear", reply(kind="unclear")),
        ("emergency", reply(kind="emergency", summary="Fire in the kitchen")), ("emergency upset false", reply(kind="emergency", upset=False)),
        ("unknown kind", reply(kind="weird", summary="s", upset=True)), ("host_summary not str", {"kind": "ask_host", "reply": "", "sources": [], "host_summary": 5, "upset": 1}),
        ("sources not list", {"kind": "answer", "reply": "Hi 15", "sources": "c1", "host_summary": None, "upset": False}),
        ("sources newline", reply(sources=("c1\n",))), ("sources padded", reply(sources=(" c2 ",), text="Wifi is Flat-5G")),
    ]
    out["validate"] = [{"name": n, "data": d, "guest_text": base_msg, "cards": live_cards, "out": leon.validate(d, live_cards, base_msg)} for n, d in vcases]

    # try_reply, end to end, with the model and the rate-limit helpers replaced
    out["try"] = []
    state = {"count": 0, "blocked": False, "recorded": 0}
    calls: list = []

    def run(name, text, scenario, *, lang="en", host_name="Jan Novak", mult=1, blocked=False, count=0, script=()):
        queue = list(script)
        calls.clear()
        state.update(count=count, blocked=blocked, recorded=0)

        def fake_call(feature, system_blocks, messages, schema, key=None, max_tokens=None):
            calls.append({"feature": feature, "system_sha": [sha(b) for b in system_blocks], "messages": messages, "schema": schema, "key": key, "max_tokens": max_tokens})
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        def record(scope, key):
            state["recorded"] += 1
            state["count"] += 1

        saved = (ai.call, leon.plan_multiplier, leon.rate_limit.blocked, leon.rate_limit._count, leon.rate_limit.record, db.query)
        ai.call, leon.plan_multiplier = fake_call, lambda aid: mult
        leon.rate_limit.blocked = lambda scope, key, max_events, window=0: state["blocked"]
        leon.rate_limit._count = lambda scope, key, window: state["count"]
        leon.rate_limit.record = record
        db.query = patched_db(SCENARIOS[scenario], FACT_ROWS)
        try:
            result = leon.try_reply({"id": 11, "internal_name": 'Flat "A" <b>'}, text, lang=lang, host_name=host_name)
        finally:
            ai.call, leon.plan_multiplier, leon.rate_limit.blocked, leon.rate_limit._count, leon.rate_limit.record, db.query = saved
        out["try"].append({"name": name, "text": text, "scenario": scenario, "lang": lang, "host_name": host_name, "mult": mult, "blocked": blocked, "count": count,
                           "script": [s if not isinstance(s, Exception) else {"error": getattr(s, "reason", "x")} for s in script],
                           "result": result, "recorded": state["recorded"], "calls": list(calls)})

    live = "live"
    run("answer", "What time is check-in?", live, script=[reply()])
    run("answer with summary", "Check-in time and where is the pool?", live, script=[reply(summary="Where is the pool?")])
    run("answer cs", "Kdy je check-in?", live, lang="cs", script=[reply()])
    run("ask host", "Can I bring a horse?", live, script=[reply(kind="ask_host", summary="horse")])
    run("ask host upset", "This is terrible, the heating is broken", live, script=[reply(kind="ask_host", summary="heating", upset=True)])
    run("ask host no name", "Can I bring a horse?", live, host_name="", script=[reply(kind="ask_host", summary="horse")])
    run("guardrail", "What is the door code?", live, script=[reply(text="Code is 9999")])
    run("emergency", "There is a fire!", live, script=[reply(kind="emergency", summary="fire")])
    run("emergency no card", "There is a fire!", "live no emergency text", script=[reply(kind="emergency", summary="fire")])
    run("refuse", "Write my homework", live, script=[reply(kind="refuse")])
    run("about me", "Are you a robot?", live, script=[reply(kind="about_me")])
    run("unclear", "Hmm what", live, script=[reply(kind="unclear")])
    run("ai error", "What time is check-in?", live, script=[ai.AIError("api")])
    run("ai disabled", "What time is check-in?", live, script=[ai.AIDisabled("disabled")])
    run("ai budget", "What time is check-in?", live, script=[ai.AIBudgetError("month")])
    run("paused plan", "What time is check-in?", live, mult=0)
    run("empty", "   ", live)
    run("too long", "x" * 501, live)
    run("too long cs", "x" * 501, live, lang="cs")
    run("max length", "a" * 500, live, script=[reply()])
    run("smalltalk hi", "Hello!", live)
    run("smalltalk thanks cs", "Děkuji", live, lang="cs")
    run("noise", "???", live)
    run("cap", "What time is check-in?", live, blocked=True, count=5)
    run("no guide", "What time is check-in?", "not live")
    run("left", "What time is check-in?", live, count=3, script=[reply()])
    run("redacted", "My email is anna@example.test, phone +420 777 123 456, booking AB1234567: when is check-in?", live, script=[reply()])
    return out


def main(argv: list) -> int:
    check = "--check" in argv
    files = {
        PKG / "leon_prompt.txt": leon.CHARACTER,
        PKG / "leon_guest_i18n.json": guest_i18n_json(),
        PKG / "leon_facts_catalog.json": json.dumps({"facts": [[f, *v] for f, v in guide_facts.FACTS.items()]}, ensure_ascii=False, indent=1) + "\n",
        PKG / "testdata" / "leon_try_golden.json": json.dumps(cases(), ensure_ascii=False, indent=1) + "\n",
    }
    stale = []
    for path, text in files.items():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    for path in stale:
        print("stale:", path.relative_to(APP.parent))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
