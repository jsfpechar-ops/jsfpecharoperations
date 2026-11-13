"""Write the Havel data files and the golden cases for go/internal/web/ai from the real Python.

Briefs 1430 to 1434. Run from App/ (no database needed: nothing here reads or writes one):

    .venv/bin/python scripts/havel_golden.py            write the files
    .venv/bin/python scripts/havel_golden.py --check    exit 1 and name each stale file

Files written into go/internal/web/ai/:
  havel_prompt.txt        HAVEL_SYSTEM_PROMPT, byte for byte
  havel_guide.json        guide_i18n.GUIDE_STRINGS (the strings the model reads)
  havel_i18n.json         the host strings the pages read, from havel_i18n_keys.txt
  testdata/havel_golden.json   inputs and the Python answers of the pure functions
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("UBYHOST_SECRET_KEY", "havel-golden-secret-0123456789-abcdef")
APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
PKG = APP.parent / "go" / "internal" / "web" / "ai"

from app import ai, cleaning_i18n, config, guide_i18n, havel, havel_topics, host_i18n  # noqa: E402
from app import security  # noqa: E402
from app.routes import havel as havel_routes  # noqa: E402

TODAY = date(2026, 11, 13)
SECRET = config.secret_key()


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_keys(path: Path) -> list:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def expand(keys: list) -> list:
    out = []
    for key in keys:
        if key.endswith(".*"):
            prefix = key[:-1]
            out.extend(sorted({k for table in host_i18n.STRINGS.values() for k in table if k.startswith(prefix)}))
        elif key == "@pages":  # every label key of havel.PAGES that is not a guide string
            out.extend(sorted({v[1] for v in havel.PAGES.values() if not v[1].startswith("guide.")}))
        else:
            out.append(key)
    return list(dict.fromkeys(out))


def i18n_json() -> str:
    keys = expand(read_keys(PKG / "havel_i18n_keys.txt"))
    catalog = {lang: {k: t[k] for k in keys if k in t} for lang, t in host_i18n.STRINGS.items()}
    for lang in catalog:  # the confirm card's cleaning labels come from cleaning_i18n, not host_i18n
        for word in ("date", "start", "end", "notes"):
            catalog[lang]["cleaning_word." + word] = cleaning_i18n.translator(lang)(word)
    return json.dumps(catalog, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def reply_json(r: havel.Reply) -> dict:
    return {"kind": r.kind, "text": r.text, "links": [list(x) for x in r.links], "action": r.action,
            "support_summary": r.support_summary, "fail_reason": r.fail_reason, "sources": r.sources, "next": r.next}


HOSTS = [
    {"user_id": 7, "lang": "en", "device": "computer",
     "properties": [{"id": 11, "name": "Flat A", "city": "Praha"}, {"id": 12, "name": "Chata", "city": ""}],
     "page": "stays", "topic": "", "read_keys": []},
    {"user_id": 7, "lang": "cs", "device": "phone", "properties": [{"id": 21, "name": "Byt č. 1", "city": "Brno"}],
     "page": "", "topic": "reporting", "read_keys": ["guide.reporting.body"]},
    {"user_id": 8, "lang": "vi", "device": "computer", "properties": [], "page": "guide", "topic": "", "read_keys": []},
]


def host_of(spec: dict) -> havel.Host:
    return havel.Host(**spec)


def cases() -> dict:
    out: dict = {}
    en = havel.guide_strings("en")
    keys = sorted(en)
    key_plain = "guide.stays.body"
    key_num = next(k for k in keys if any(ch.isdigit() for ch in en[k]) and len(en[k]) < 400)
    num_runs = sorted({run for run in __import__("re").findall(r"\d+", en[key_num])})

    # redact / restore
    texts = [
        "", "hello", "mail anna@example.test now", "Anna.B+x@sub.example.co.uk and bob@example.test and anna@example.test",
        "call +420 777 123 456 or 777-123-456", "1.12.2026 at 14:30 and 2026-12-01", "arrival 3. 12. at 9:00",
        "booking ID AB1234567 and 123456 and 12345", "ab12345678 CD1234567 x123456 abcde123456",
        "á123456 and 123456á", "čau +420 777 123 456", "tel 777 123 45 and 12 34 56 78",
        "x1.2.2026y", "á1.2.2026", "price 1234567 CZK, id 7654321x", "no digits here", "a@b.cz", "3:5 and 12:345",
        "visa 12 3456789 and 1234 5678", "١٢٣٤٥٦٧ arabic digits",
    ]
    out["redact"] = []
    for text in texts:
        red, mapping = havel.redact(text)
        out["redact"].append({"in": text, "out": red, "mapping": mapping})
    out["restore"] = []
    for text, mapping in [("see [email 1] and [phone 1]", {"[email 1]": "a@b.cz", "[phone 1]": "123 456 789"}),
                          ("nothing", {"[email 1]": "a@b.cz"}), ("", {"[email 1]": "a"}), ("[email 1][email 1]", {"[email 1]": "x"})]:
        out["restore"].append({"text": text, "mapping": mapping, "out": havel.restore(text, mapping)})

    # local replies
    msgs = ["hi", "Hello!", "  hey  ", "Good morning", "ahoj", "Dobrý den.", "dobry den", "zdravím", "čau", "xin chào",
            "chào!!", "thanks", "Thank you!", "díky", "děkuji", "Super", "cảm ơn", "ok", "okay.", "hi there", "hello how do I add a stay",
            "x" * 41, "hi" + " " * 10 + "!", "thx!!!", "HELLO", "Ahoj ahoj", "hi !", "OK "]
    out["local_reply"] = [{"in": m, "out": havel.local_reply(m)} for m in msgs]

    # history
    hist = [{"host": "q1", "havel": "a1"}, {"host": "č" * 700, "havel": "b" * 1700}]
    payload, sig = havel.sign_history(7, hist * 5)
    out["history"] = {"sign": [{"user": 7, "in": hist * 5, "payload": payload, "sig": sig},
                                {"user": 9, "in": [], "payload": havel.sign_history(9, [])[0], "sig": havel.sign_history(9, [])[1]},
                                {"user": 7, "in": hist[:1], "payload": havel.sign_history(7, hist[:1])[0], "sig": havel.sign_history(7, hist[:1])[1]}]}
    good_p, good_s = havel.sign_history(7, hist[:1])
    read = [("good", 7, good_p, good_s), ("other user", 8, good_p, good_s), ("bad sig", 7, good_p, "0" * 64), ("empty", 7, "", ""),
            ("tampered", 7, good_p.replace("q1", "q2"), good_s)]
    for body in ["not json", '{"a":1}', '[1,"x",{"host":5,"havel":null},{"host":"h","havel":"v"}]', "[" + ",".join(['{"host":"h%d","havel":"v"}' % i for i in range(9)]) + "]"]:
        read.append(("body " + body[:12], 7, body, havel._sig(7, body)))
    out["history"]["read"] = [{"name": n, "user": u, "payload": p, "sig": s, "out": havel.read_history(u, p, s)} for n, u, p, s in read]

    # pages
    out["pages_block"] = {lang: havel.pages_block(lang) for lang in ("en", "cs", "vi", "de")}
    out["guide_block_sha"] = {lang: [sha(havel.guide_block(lang)), len(havel.guide_block(lang))] for lang in ("en", "cs", "vi", "de")}
    out["prompt_sha"] = sha(havel.HAVEL_SYSTEM_PROMPT)
    out["page_ids"] = list(havel.PAGE_IDS)
    out["page_url"] = [{"page": p, "pid": pid, "owned": owned, "out": havel.page_url(p, pid, owned)}
                       for p, pid, owned in [("dashboard", None, []), ("property", 11, [11, 12]), ("property", 99, [11]), ("property_guests", 12, [11, 12]),
                                             ("guide_faq", None, []), ("nope", 1, [1]), ("property_calendars", None, [5])]]
    out["label"] = [{"lang": lang, "key": key, "out": havel.label(lang, key)}
                    for lang in ("en", "cs", "vi", "xx") for key in ("nav.stays", "guide.nav.faq", "guide.stays.body", "missing.key")]

    # host context and messages
    today = TODAY
    out["messages"] = []
    for spec in HOSTS:
        host = host_of(spec)
        history = [{"host": "my mail is a@b.cz", "havel": "ok [email 1]"}, {"host": "second", "havel": "reply"}]
        for message in ["add a stay for 2026-12-01 to 2026-12-04, mail guest@example.test", "plain"]:
            mapping: dict = {}
            messages = havel.build_messages(host, history, message, today, mapping)
            out["messages"].append({"host": spec, "history": history, "message": message, "today": today.isoformat(),
                                    "messages": messages, "mapping": mapping, "context": havel.host_context(host, today)})
    long_hist = [{"host": "x" * 900, "havel": "y" * 1500} for _ in range(5)]
    out["model_history"] = {"in": long_hist, "out": havel.model_history(long_hist)}

    # validate
    h0 = host_of(HOSTS[0])
    message = "my mail anna@example.test phone +420 777 123 456, ref ab123456, 2 guests on 2026-12-01"
    mapping: dict = {}
    havel.build_messages(h0, [{"host": "earlier 77", "havel": "x"}], message, today, mapping)
    history = [{"host": "earlier 77", "havel": "x"}]
    base = {"kind": "answer", "reply": "Open the Stays page.", "sources": [key_plain], "links": [], "action": None,
            "support_summary": None, "next": []}

    def v(**kw):
        d = dict(base)
        d.update(kw)
        return d

    action = {"type": "create_stay", "property_id": 11, "date_from": "2026-12-01", "date_to": "2026-12-04", "guests": 2,
              "guest_email": "[email 1]", "start_time": None, "end_time": None, "note": "late arrival"}
    leak = havel.HAVEL_SYSTEM_PROMPT[100:160]
    data_cases = [
        ("answer ok", v()), ("answer not a dict", "x"), ("bad kind", v(kind="zzz")), ("reply not str", v(reply=5)),
        ("empty reply", v(reply="  ")), ("too long", v(reply="a" * 1501)), ("exactly max", v(reply="a" * 1500, kind="clarify")),
        ("cyrillic", v(reply="Привіт")), ("cjk", v(reply="x 中")), ("url", v(reply="go to https://x.example")),
        ("www", v(reply="see www.x.com")), ("at sign", v(reply="mail me@x")), ("slash word", v(reply="open /stays now")),
        ("domain", v(reply="visit example.com today")), ("phone-like", v(reply="call 1234567 now")),
        ("markup angle", v(reply="use <b>bold</b>")), ("markup bold", v(reply="this is **bold**")), ("markup hash", v(reply="# Title")),
        ("markup backtick", v(reply="run `x`")), ("prompt leak", v(reply="Sure: " + leak + " done")), ("secret email", v(reply="Write to anna@example.test")),
        ("secret phone", v(reply="Call +420 777 123 456")), ("secret number", v(reply="Your ref ab123456 is fine.")), ("no sources", v(sources=[])), ("bad source", v(sources=["nope", 5])),
        ("sources capped", v(sources=[key_plain] * 3 + keys[:12])),
        ("number ok from guide", v(reply="Step " + (num_runs[0] if num_runs else "1"), sources=[key_num])),
        ("number bad", v(reply="It takes 937 days.")), ("number from message", v(reply="You said 2 guests.")),
        ("number from history", v(reply="Earlier you wrote 77.")), ("emergency number", v(reply="Call 112 now.")),
        ("date ok", v(reply="Arrival on 1.12.2026 at 14:30.")), ("numbered steps", v(reply="1. Open Stays\n2. Press Add stay")),
        ("clarify no sources", v(kind="clarify", sources=[])), ("refuse", v(kind="refuse", reply="I can only help with UbyHost.", next=["x"])),
        ("next ok", v(next=["Add a stay", "  Show link  ", "", 5, "has <b>", "call 123456789", "visit x.com", "2 guests", "Пр", "d", "e"])),
        ("next numbers", v(next=["order 55", "date 2026-12-01", "77"])),
        ("links", v(links=[{"page": "stays", "property_id": None}, {"page": "property", "property_id": 11}, {"page": "property", "property_id": 99},
                           {"page": "property", "property_id": 11.0}, {"page": "nope", "property_id": 1}, "x", {"page": "guide_faq", "property_id": None},
                           {"page": "reports", "property_id": None}])),
        ("links on refuse", v(kind="refuse", links=[{"page": "stays", "property_id": None}])),
        ("escalate ok", v(kind="escalate", support_summary="Host cannot find X; email anna@example.test", sources=[])),
        ("escalate no summary", v(kind="escalate", support_summary=" ")), ("escalate long", v(kind="escalate", support_summary="s" * 801)),
        ("escalate not str", v(kind="escalate", support_summary=4)),
        ("action ok", v(kind="action", action=action)), ("action none", v(kind="action", action=None)),
        ("action bad type", v(kind="action", action=dict(action, type="boom"))),
        ("action foreign property", v(kind="action", action=dict(action, property_id=99))),
        ("action no property two props", v(kind="action", action=dict(action, property_id=None))),
        ("action sync foreign", v(kind="action", action={"type": "sync_calendars", "property_id": 99, "date_from": None, "date_to": None, "guests": None,
                                                         "guest_email": None, "start_time": None, "end_time": None, "note": None})),
        ("action bad date", v(kind="action", action=dict(action, date_from="2026-1-1"))),
        ("action end before start", v(kind="action", action=dict(action, date_to="2026-12-01"))),
        ("action no dates", v(kind="action", action=dict(action, date_from=None, date_to=None))),
        ("action bad time", v(kind="action", action=dict(action, type="create_cleaning", start_time="25:00", date_to=None))),
        ("action cleaning ok", v(kind="action", action=dict(action, type="create_cleaning", start_time="10:00", end_time="12:30", date_to=None, guests=None, guest_email=None))),
        ("action cleaning no date", v(kind="action", action=dict(action, type="create_cleaning", date_from=None))),
        ("action guests 0", v(kind="action", action=dict(action, guests=0))), ("action guests 61", v(kind="action", action=dict(action, guests=61))),
        ("action guests str", v(kind="action", action=dict(action, guests="2"))), ("action guests bool", v(kind="action", action=dict(action, guests=True))),
        ("action bad email", v(kind="action", action=dict(action, guest_email="not-an-email"))),
        ("action email real", v(kind="action", action=dict(action, guest_email="guest@example.test"))),
        ("action note markup", v(kind="action", action=dict(action, note="<b>x</b>"))),
        ("action note address", v(kind="action", action=dict(action, note="see https://x.example"))),
        ("action note restored", v(kind="action", action=dict(action, note="mail [email 1]"))),
        ("action show link", v(kind="action", action={"type": "show_guest_link", "property_id": 12, "date_from": None, "date_to": None, "guests": None,
                                                      "guest_email": None, "start_time": None, "end_time": None, "note": None})),
        ("action extra keys", v(kind="action", action=dict(action, evil="x"))),
    ]
    out["validate"] = []
    for name, data in data_cases:
        for hspec in ([HOSTS[0]] if name != "action no property two props" else [HOSTS[0]]) + ([HOSTS[1]] if name.startswith(("action ok", "answer ok", "links")) else []):
            h = host_of(hspec)
            m2: dict = {}
            hist2 = history if hspec is HOSTS[0] else []
            msg2 = message if hspec is HOSTS[0] else "plain"
            havel.build_messages(h, hist2, msg2, today, m2)
            r = havel.validate(data, h, msg2, hist2, m2, today)
            out["validate"].append({"name": name, "host": hspec, "message": msg2, "history": hist2, "today": today.isoformat(),
                                    "data": data, "reply": reply_json(r)})
    # a lone property host: the property id may be left out
    one = host_of(HOSTS[1])
    d = v(kind="action", action=dict(action, property_id=None, guest_email=None))
    r = havel.validate(d, one, "plain", [], {}, today)
    out["validate"].append({"name": "action single property default", "host": HOSTS[1], "message": "plain", "history": [], "today": today.isoformat(),
                            "data": d, "reply": reply_json(r)})

    # ask: what is sent to the model, and the retry on input_too_large
    out["ask"] = []
    calls: list = []

    def run(name, host_spec, hist, message, script):
        calls.clear()
        queue = list(script)

        def fake_call(feature, system_blocks, messages, schema, key=None, max_tokens=None):
            calls.append({"feature": feature, "system_sha": [sha(b) for b in system_blocks], "system_len": [len(b) for b in system_blocks],
                          "messages": messages, "schema": schema, "key": key, "max_tokens": max_tokens})
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        stats: list = []
        old_call, old_stat = ai.call, havel.record_stat
        ai.call, havel.record_stat = fake_call, lambda kind, day=None: stats.append(kind)
        try:
            try:
                r = havel.ask(host_of(host_spec), hist, message, today)
                result = {"reply": reply_json(r)}
            except ai.AIDisabled:
                result = {"raised": "disabled"}
            except ai.AIBudgetError as exc:
                result = {"raised": "budget", "reason": exc.reason}
        finally:
            ai.call, havel.record_stat = old_call, old_stat
        out["ask"].append({"name": name, "host": host_spec, "history": hist, "message": message, "today": today.isoformat(),
                           "script": [s if not isinstance(s, Exception) else {"error": getattr(s, "reason", "x"), "kind": type(s).__name__} for s in script],
                           "calls": list(calls), "stats": stats, **result})

    hist3 = [{"host": "one", "havel": "r1"}, {"host": "two", "havel": "r2"}]
    run("answer", HOSTS[0], hist3, "How do I add a stay?", [v()])
    run("retry", HOSTS[0], hist3, "How do I add a stay?", [ai.AIError("input_too_large"), v()])
    run("retry twice", HOSTS[0], hist3, "How do I add a stay?", [ai.AIError("input_too_large"), ai.AIError("input_too_large")])
    run("no history", HOSTS[1], [], "Jak přidám pobyt?", [ai.AIError("input_too_large")])
    run("api error", HOSTS[0], [], "x question", [ai.AIError("api")])
    run("disabled", HOSTS[0], [], "x question", [ai.AIDisabled("disabled")])
    run("budget month", HOSTS[0], [], "x question", [ai.AIBudgetError("month")])
    run("budget key", HOSTS[2], [], "x question", [ai.AIBudgetError("day")])
    run("guardrail", HOSTS[0], [], "x question", [v(reply="visit https://x.example")])
    out["schema"] = havel.SCHEMA
    out["schema_compact"] = json.dumps(havel.SCHEMA, separators=(",", ":"), ensure_ascii=False)
    out["limits"] = {"max_tokens": havel.MAX_TOKENS, "max_message": havel.MAX_MESSAGE_CHARS, "max_reply": havel.MAX_REPLY_CHARS,
                     "max_summary": havel.MAX_SUMMARY_CHARS, "max_exchanges": havel.MAX_EXCHANGES}

    # topics
    out["topics"] = {"ordered": {nav: [t["id"] for t in havel_topics.ordered(nav)] for nav in ("", "cleaning", "reservations", "submissions", "housebook", "apartments", "dashboard", "zzz")},
                     "answers": [], "read_keys": []}
    for topic in havel_topics.TOPICS:
        for q in topic["questions"]:
            out["topics"]["read_keys"].append({"topic": topic["id"], "q": q["id"], "out": havel_topics.read_keys(topic["id"], q["id"])})
            for lang in ("en", "cs", "vi"):
                out["topics"]["answers"].append({"lang": lang, "topic": topic["id"], "q": q["id"], "out": havel_topics.answer(lang, topic["id"], q["id"])})
    out["topics"]["answers"].append({"lang": "en", "topic": "stays", "q": "nope", "out": havel_topics.answer("en", "stays", "nope")})
    out["topics"]["all"] = havel_topics.TOPICS
    out["topics"]["ids"] = havel_topics.TOPIC_IDS

    # the route helpers
    out["blocks"] = [{"in": t, "out": havel_routes.blocks(t)} for t in ["", "one line", "a\n\nb", "1. first\n2. second\ntext\n3. third", "  7.  spaced  \n 12. x", "100. not a step", "1.no space"]]
    out["clean_id"] = [{"in": t, "out": havel_routes._clean_id(t)} for t in ["stays", "Guest_Link", "a-b c", "x" * 50, "éclair", ""]]
    paths = ["", "/", "/havel", "/stays?x=1", "/a/../b", "/a//b", "//evil.example/x", "///x", "//", "https://evil.example/", "javascript:alert(1)", "/ok#frag", "/ok?a=b#frag",
             "  /padded  ", "/with space", "/tab\there", "back\\slash", "/%2e%2e/x", "/%2f%2fevil", "/a/./b/", "/a/b/..", "/..", "/../..", "/\u00e9t\u00e9?q=\u00fc", "/a%00b", "x", "/havel?topic=wrong&q=error", "/x\\y", "/x?y=\\"]
    out["safe_path"] = [{"in": p, "out": security.safe_local_path(p, "/havel")} for p in paths]
    out["i18n"] = {lang: {k: host_i18n.translate(lang, k) for k in ("havel.intro", "havel.off", "havel.limit_turns", "havel.card.not_prepared")}
                   for lang in ("en", "cs", "vi")}
    out["i18n_param"] = host_i18n.translate("en", "havel.card.not_prepared", reason="R")
    return out


def main(argv: list) -> int:
    check = "--check" in argv
    files = {
        PKG / "havel_prompt.txt": havel.HAVEL_SYSTEM_PROMPT,
        PKG / "havel_guide.json": json.dumps(guide_i18n.GUIDE_STRINGS, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        PKG / "havel_i18n.json": i18n_json(),
        PKG / "testdata" / "havel_golden.json": dump(cases()),
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
