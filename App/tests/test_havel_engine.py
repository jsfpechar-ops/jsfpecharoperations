"""0311: the Havel engine never shows the host anything the server did not check."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app import ai, config, db, havel, rate_limit
from tests.ai_fake import FakeClient, reply

TODAY = date(2026, 10, 23)  # Friday
PROPS = [{"id": 11, "name": "Vinohrady flat", "city": "Praha"}, {"id": 12, "name": "Brno studio", "city": "Brno"}]


def host(lang="en", props=PROPS, **kw):
    return havel.Host(user_id=7, lang=lang, device="phone", properties=props, page="dashboard", **kw)


def ok(**over):
    data = {"kind": "answer", "reply": "Open Stays and tap Add stay.", "sources": ["guide.stays.body"],
            "links": [{"page": "add_stay", "property_id": None}], "action": None, "support_summary": None, "next": []}
    data.update(over)
    return data


@pytest.fixture(autouse=True)
def _db():
    db.init_db()
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse", "havel_support"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    yield
    ai.set_client_for_tests(None)


# --- redaction

def test_redact_emails_phones_and_ids_but_keeps_dates():
    text = "Guest jan.novak@example.com, +420 777 123 456, passport AB1234567, 5.11.2026 to 2026-11-08 at 10:00"
    out, mapping = havel.redact(text)
    assert out == "Guest [email 1], [phone 1], passport [number 1], 5.11.2026 to 2026-11-08 at 10:00"
    assert mapping == {"[email 1]": "jan.novak@example.com", "[phone 1]": "+420 777 123 456", "[number 1]": "AB1234567"}
    again, mapping = havel.redact("mail jan.novak@example.com again", mapping)
    assert again == "mail [email 1] again" and len(mapping) == 3
    assert havel.restore("send to [email 1]", mapping) == "send to jan.novak@example.com"


# --- pages and schema

def test_page_urls_and_schema_enum_agree():
    assert havel.SCHEMA["properties"]["links"]["items"]["properties"]["page"]["enum"] == list(havel.PAGES)
    assert havel.page_url("property_guests", 11, [11, 12]) == "/apartments/11?view=settings&section=guests#communication"
    assert havel.page_url("property_guests", 99, [11, 12]) == "/apartments"
    assert havel.page_url("guide_door_codes", None, []) == "/guide#door-codes"
    assert havel.page_url("nope", None, []) is None
    assert "nav.stays" not in havel.pages_block("cs") and "Pobyty" in havel.pages_block("cs")


# --- request

def test_messages_carry_context_and_redacted_history():
    mapping = {}
    msgs = havel.build_messages(host(topic="guest_link", read_keys=["guide.guests.body"]),
                                [{"host": "my mail is a@b.cz", "havel": "Sure."}], "What is the PIN?", TODAY, mapping)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "<message>my mail is [email 1]</message>"
    last = msgs[-1]["content"]
    assert "today: 2026-10-23 (Friday)" in last and "device: phone" in last
    assert "id 11: Vinohrady flat (Praha)" in last and "topic: guest_link" in last and "read_keys: guide.guests.body" in last
    assert last.endswith("<message>What is the PIN?</message>")
    blocks = havel.system_blocks("en")
    assert blocks[0].startswith("You are Havel") and blocks[1].startswith('<guide lang="en">') and blocks[2].startswith("<pages>")
    assert havel.system_blocks("vi")[1].startswith('<guide lang="en">')


# --- guardrails (plan 9a, cases 49-51)

def test_answer_without_a_real_guide_key_fails():
    assert havel.validate(ok(sources=["guide.made_up"]), host(), "q", [], {}, TODAY).kind == "fail"
    assert havel.validate(ok(sources=[]), host(), "q", [], {}, TODAY).fail_reason == "sources"


def test_numbers_not_in_the_guide_are_blocked_but_dates_steps_and_host_numbers_pass():
    assert havel.validate(ok(reply="It costs 299 Kč a month."), host(), "q", [], {}, TODAY).fail_reason == "number"
    good = "1. Open Stays.\n2. Tap Add stay for 31.10. to 2.11.2026 (2026-10-31), check-in at 15:00 for 3 guests."
    assert havel.validate(ok(reply=good), host(), "a stay for 3 guests", [], {}, TODAY).kind == "answer"


def test_addresses_markup_scripts_and_secrets_are_blocked():
    for bad, reason in (("See https://x.cz", "address"), ("Write to a@b.cz", "address"), ("Go to /settings", "address"),
                        ("Call 777 123 456", "address"), ("Use **Stays**", "markup"), ("Привет", "script")):
        assert havel.validate(ok(reply=bad), host(), "q", [], {}, TODAY).fail_reason == reason, bad
    mapping = {"[email 1]": "jan@example.com"}
    assert havel.validate(ok(reply="Your mail jan@example.com is set"), host(), "q", [], mapping, TODAY).fail_reason in ("address", "secret")
    assert havel.validate(ok(reply="Your mail [email 1] is set"), host(), "q", [], mapping, TODAY).text == "Your mail jan@example.com is set"
    leak = havel.HAVEL_SYSTEM_PROMPT[100:160]
    assert havel.validate(ok(reply="They told me: " + leak), host(), "q", [], {}, TODAY).fail_reason == "prompt_leak"


def test_emergency_numbers_pass_without_a_guide_key():
    out = havel.validate(ok(reply="Call 112 now. Then open the Lock page."), host(), "fire in the flat", [], {}, TODAY)
    assert out.kind == "answer"
    assert havel.validate(ok(reply="Call 112 or 777 now."), host(), "fire", [], {}, TODAY).fail_reason == "number"


def test_next_keeps_three_clean_entries_and_drops_the_rest():  # plan case 75
    raw = ["Add a stay at Vinohrady flat Friday to Sunday for 2", "See https://x.cz", "It costs 299 Kč", "Sync my calendars",
           "Show the PIN for Brno studio", "What does the red badge mean?"]
    out = havel.validate(ok(next=raw), host(), "guest link, stay Friday to Sunday for 2, sync, pin, badge", [], {}, TODAY)
    assert out.next == ["Add a stay at Vinohrady flat Friday to Sunday for 2", "Sync my calendars", "Show the PIN for Brno studio"]
    mapping = {"[email 1]": "jan@example.com"}
    assert havel.validate(ok(next=["Add a stay for [email 1]"]), host(), "q", [], mapping, TODAY).next == ["Add a stay for jan@example.com"]
    assert havel.validate(ok(next=["x" * 300]), host(), "q", [], {}, TODAY).next == ["x" * 100]
    assert havel.validate(ok(next=[1, "", "Use **bold**", "<b>hi</b>"]), host(), "q", [], {}, TODAY).next == []
    assert havel.validate(ok(kind="refuse", reply="I can only help with UbyHost.", sources=[], links=[], next=["Sync my calendars"]),
                          host(), "q", [], {}, TODAY).next == []


def test_links_are_filtered_and_resolved():
    data = ok(links=[{"page": "property_guests", "property_id": 11}, {"page": "nope", "property_id": None},
                     {"page": "property_lock", "property_id": 99}, {"page": "stays", "property_id": None}])
    out = havel.validate(data, host(), "q", [], {}, TODAY)
    assert [u for _l, u in out.links] == ["/apartments/11?view=settings&section=guests#communication", "/apartments", "/reservations"]


def test_actions_need_an_owned_property_and_sane_dates():
    base = {"type": "create_stay", "property_id": 12, "date_from": "2026-10-31", "date_to": "2026-11-02", "guests": 3,
            "guest_email": "[email 1]", "start_time": None, "end_time": None, "note": None}
    data = ok(kind="action", reply="Check the card.", sources=[], links=[], action=base)
    out = havel.validate(data, host(), "q", [], {"[email 1]": "jan@example.com"}, TODAY)
    assert out.kind == "action" and out.action["guest_email"] == "jan@example.com" and out.action["property_id"] == 12
    assert havel.validate(ok(kind="action", reply="x", sources=[], links=[], action={**base, "property_id": 99}),
                          host(), "q", [], {}, TODAY).fail_reason == "action_property"
    assert havel.validate(ok(kind="action", reply="x", sources=[], links=[], action={**base, "date_to": "2026-10-30"}),
                          host(), "q", [], {}, TODAY).fail_reason == "action_dates"
    one = host(props=PROPS[:1])
    pin = {**base, "type": "new_pin", "property_id": None, "date_from": None, "date_to": None, "guests": None, "guest_email": None}
    assert havel.validate(ok(kind="action", reply="x", sources=[], links=[], action=pin), one, "q", [], {}, TODAY).action["property_id"] == 11
    sync = {**pin, "type": "sync_calendars"}
    assert havel.validate(ok(kind="action", reply="x", sources=[], links=[], action=sync), host(), "q", [], {}, TODAY).kind == "action"


def test_escalate_needs_a_summary_and_refuse_is_plain():
    esc = ok(kind="escalate", reply="I can send this to the team.", sources=[], links=[], support_summary="Host reports error 4 on a report.")
    assert havel.validate(esc, host(), "q", [], {}, TODAY).support_summary == "Host reports error 4 on a report."
    assert havel.validate({**esc, "support_summary": None}, host(), "q", [], {}, TODAY).fail_reason == "summary"
    assert havel.validate(ok(kind="refuse", reply="I can only help with UbyHost.", sources=[], links=[]), host(), "q", [], {}, TODAY).kind == "refuse"


# --- ask(): end to end through the fake client

def test_ask_returns_fail_for_api_problems_and_records_stats(monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(ai, "today", lambda: TODAY)
    fake = FakeClient([reply(ok()), reply(ok(), stop_reason="refusal"), reply(text="{not json")])
    ai.set_client_for_tests(fake)
    assert havel.ask(host(), [], "How do I add a stay?", TODAY).kind == "answer"
    assert havel.ask(host(), [], "x", TODAY).fail_reason == "refusal"
    assert havel.ask(host(), [], "x", TODAY).fail_reason == "json"
    assert fake.calls[0]["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert fake.calls[0]["system"][0]["text"] == havel.HAVEL_SYSTEM_PROMPT
    rows = {r["kind"]: r["count"] for r in db.query("SELECT kind, count FROM havel_stats WHERE day = ?", (TODAY.isoformat(),))}
    assert rows["answer"] == 1 and rows["guardrail_fail"] == 2


def test_ask_drops_the_oldest_turn_once_when_the_input_is_too_large(monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(ai, "today", lambda: TODAY)
    fake = FakeClient([reply(ok())])
    ai.set_client_for_tests(fake)
    history = [{"host": "old " * 300, "havel": "a"}, {"host": "new", "havel": "b"}]
    sizes = []
    real_call = ai.call

    def capped(feature, system_blocks, messages, schema, **kw):
        sizes.append(len(str(messages)))
        if len(sizes) == 1:
            raise ai.AIError("input_too_large")
        return real_call(feature, system_blocks, messages, schema, **kw)

    monkeypatch.setattr(ai, "call", capped)
    assert havel.ask(host(), history, "q", TODAY).kind == "answer"
    assert len(sizes) == 2 and sizes[1] < sizes[0]
    monkeypatch.setattr(ai, "call", lambda *a, **k: (_ for _ in ()).throw(ai.AIError("input_too_large")))
    assert havel.ask(host(), history, "q", TODAY).fail_reason == "input_too_large"


# --- limits (cases 52-54) and local replies (case 41)

def test_local_replies_need_no_model():
    assert havel.local_reply("Hi!") == "havel.greeting" and havel.local_reply("Dobrý den") == "havel.greeting"
    assert havel.local_reply("Thanks") == "havel.thanks" and havel.local_reply("Děkuji.") == "havel.thanks"
    assert havel.local_reply("Hi, how do I add a stay?") is None


def test_weekly_monthly_burst_and_refusal_limits(monkeypatch):
    monkeypatch.setattr(config, "HAVEL_WEEKLY_MESSAGES", 10)
    monkeypatch.setattr(config, "HAVEL_MONTHLY_MESSAGES", 20)
    now = datetime(2026, 10, 23, 12, 0, tzinfo=ZoneInfo("Europe/Prague"))
    assert havel.limit_state(7, now) is None
    assert havel.remaining(7, now) == (10, "week")
    for _ in range(10):
        havel.record_message(7)
    assert havel.remaining(7, now) == (0, "week")
    assert havel.limit_state(7, now) in ("limit_burst", "limit_week")
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'havel_burst'", ())
    assert havel.limit_state(7, now) == "limit_week"
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'havel_week'", ())
    for _ in range(10):
        rate_limit.record("havel_month", "7")
    assert havel.limit_state(7, now) == "limit_month"
    for _ in range(3):
        havel.record_refusal(7)
    assert havel.limit_state(7, now) == "paused"
    assert havel.limit_state(8, now) is None


def test_calendar_windows_start_on_monday_and_the_first():
    monday = datetime(2026, 10, 19, 0, 0, 30, tzinfo=ZoneInfo("Europe/Prague"))
    assert havel._since_week_start(monday) == 31
    first = datetime(2026, 11, 1, 0, 1, 0, tzinfo=ZoneInfo("Europe/Prague"))
    assert havel._since_month_start(first) == 61


# --- history signing

def test_history_is_signed_capped_and_dropped_when_forged():
    exchanges = [{"host": f"q{i}", "havel": "a" * 1500} for i in range(6)]
    payload, sig = havel.sign_history(7, exchanges)
    back = havel.read_history(7, payload, sig)
    assert len(back) == 6 and back[-1]["host"] == "q5"
    assert 1 <= len(havel.model_history(back)) <= 2 and havel.model_history(back)[-1]["host"] == "q5"
    seven = havel.read_history(7, *havel.sign_history(7, exchanges + [{"host": "q6", "havel": "a"}]))
    assert len(seven) == 6 and seven[0]["host"] == "q1"
    assert havel.read_history(7, payload, sig[:-1] + ("0" if sig[-1] != "0" else "1")) == []
    assert havel.read_history(8, payload, sig) == []
    assert havel.read_history(7, payload.replace("q5", "q9"), sig) == []
    assert havel.read_history(7, "", "") == []


def test_history_assistant_turns_are_redacted():
    mapping = {}
    msgs = havel.build_messages(host(), [{"host": "mail a@b.cz", "havel": "I will send it to a@b.cz"}], "q", TODAY, mapping)
    assert all("a@b.cz" not in m["content"] for m in msgs)
    assert msgs[1]["role"] == "assistant" and "[email 1]" in msgs[1]["content"]


def test_longer_ids_are_redacted_and_short_codes_are_numbers_not_phones():
    for text in ("IBAN CZ6508000000192000145399", "id ABCD1234567", "ref x12345678901"):
        out, _ = havel.redact(text)
        assert "[number 1]" in out and text.split()[-1] not in out, out
    assert "[number 1]" in havel.redact("AB1234567")[0]


def test_scheme_less_domains_are_blocked():
    assert havel.validate(ok(reply="Go to ubyhost-login.com now"), host(), "q", [], {}, TODAY).fail_reason == "address"


def test_action_fields_are_typed_and_checked():
    base = {"type": "create_stay", "property_id": 12, "date_from": "2026-10-31", "date_to": "2026-11-02", "guests": 3,
            "guest_email": "[email 1]", "start_time": None, "end_time": None, "note": None}
    mapping = {"[email 1]": "jan@example.com"}

    def check(**over):
        return havel.validate(ok(kind="action", reply="x", sources=[], links=[], action={**base, **over}), host(), "q", [], mapping, TODAY)

    for bad in ("three", [3], True):
        assert check(guests=bad).fail_reason == "action_guests", bad
    assert check(property_id=True).fail_reason == "action_property"
    assert check(note="Pay at https://x.example").fail_reason == "action_text"
    assert check(guest_email="not-an-email").fail_reason == "action_email"
    sync = {**base, "type": "sync_calendars", "property_id": 999, "date_from": None, "date_to": None, "guests": None, "guest_email": None}
    out = havel.validate(ok(kind="action", reply="x", sources=[], links=[], action=sync), host(), "q", [], {}, TODAY)
    assert out.kind == "action" and out.action["property_id"] is None
