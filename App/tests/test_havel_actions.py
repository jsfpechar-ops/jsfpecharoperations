"""0314: confirm cards for Havel's actions."""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

from app import ai, config, db, havel_actions, host_i18n
from tests.ai_fake import FakeClient, reply
from tests.test_submission_retry_cap import USERNAME, host as host  # noqa: F401

TODAY = date(2026, 10, 23)
# Route tests run against the real date.today(), so their stay starts a few days from now.
SOON, LATER = (date.today() + timedelta(days=5)).isoformat(), (date.today() + timedelta(days=7)).isoformat()


def _row(id=11, name="Riverside / 4", active=1, archived=None, pin="482913", token="tok11"):
    return {"id": id, "internal_name": name, "active": active, "archived_at": archived, "permalink_pin": pin,
            "permalink_token": token, "owner_user_id": 1}


def _action(**kw):
    base = {"type": "create_stay", "property_id": 11, "date_from": "2026-10-30", "date_to": "2026-11-01", "guests": 3,
            "guest_email": "guest@example.test", "start_time": None, "end_time": None, "note": None}
    base.update(kw)
    return base


def _prepare(action, rows=None, overlaps=lambda *a: 0, feeds=lambda *a: 1):
    return havel_actions.prepare(action, rows or [_row()], TODAY, return_to="/", overlaps=overlaps, feed_count=feeds)


def test_stay_card_has_facts_fields_and_overlap_flag():
    card = _prepare(_action(), overlaps=lambda *a: 1)
    assert card["action"] == "/reservations" and card["nights"] == 2 and card["guests"] == 3 and card["overlap"]
    assert [f["name"] for f in card["fields"]] == ["apartment_id", "date_from", "date_to", "expected_guests", "guest_email"]
    assert card["property"]["index"] == 1 and card["guest_email"] == "guest@example.test"
    assert _prepare(_action(guest_email="not an e-mail"))["guest_email"] == ""
    assert _prepare(_action(note="Late arrival"))["note"] == "Late arrival"  # the host sees what the form saves


@pytest.mark.parametrize("bad", [
    {"date_from": "2026-11-01", "date_to": "2026-10-30"},
    {"date_from": "2020-01-01", "date_to": "2020-01-03"},
    {"date_from": "2029-01-01", "date_to": "2029-01-03"},
    {"guests": 0},
    {"date_from": "nope"},
])
def test_bad_stay_values_are_not_prepared(bad):
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(**bad))
    assert exc.value.reason == "dates"


def test_property_checks():
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(property_id=99))
    assert exc.value.reason == "property"
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(), rows=[_row(archived="2026-01-01T00:00:00")])
    assert exc.value.reason == "archived"


def test_cleaning_sync_pin_and_link_cards(monkeypatch):
    # The guest slug lives in the database; the unit test uses the permanent token only.
    monkeypatch.setattr(havel_actions.guest_slug, "link_key", lambda a: a["permalink_token"] or "")
    card = _prepare(_action(type="create_cleaning", date_to=None, start_time="10:00", end_time="12:00", note="Towels"))
    assert card["action"] == "/cleaning/events" and card["hidden"] == {"apartment_id": 11}
    assert [f["name"] for f in card["fields"]] == ["scheduled_date", "start_time", "end_time", "notes"]
    with pytest.raises(havel_actions.NotPrepared):
        _prepare(_action(type="create_cleaning", date_to=None, start_time="12:00", end_time="10:00"))
    card = _prepare(_action(type="sync_calendars", property_id=None))
    assert card["action"] == "/sync" and card["hidden"] == {"return_to": "/"}
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(type="sync_calendars", property_id=None), feeds=lambda *a: 0)
    assert exc.value.reason == "no_calendar"
    card = _prepare(_action(type="new_pin"))
    assert card["action"] == "/apartments/11/regenerate-pin" and card["danger"] and card["hidden"] == {}
    card = _prepare(_action(type="show_guest_link"))
    assert card["link"].endswith("/l/tok11") and card["pin"] == "482913" and "confirm" not in card
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(type="show_guest_link"), rows=[_row(token="")])
    assert exc.value.reason == "no_link"


# --- through the route ------------------------------------------------------------------

def _reply(action, text="Here is what I prepared."):
    return reply({"kind": "action", "reply": text, "sources": ["guide.stays.body"], "links": [], "action": action,
                  "support_summary": None})


@pytest.fixture
def ready(host, monkeypatch):
    db.init_db()
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    account = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    pid = db.insert("apartment", {"owner_user_id": account["id"], "internal_name": "Riverside / 4", "active": 1,
                                  "created_at": db.utcnow(), "automation_mode": "manual", "checkin_hour": 15,
                                  "checkout_hour": 11, "permalink_pin": "482913", "permalink_token": "tok-havel"})
    yield host, pid
    ai.set_client_for_tests(None)
    db.execute("DELETE FROM apartment WHERE id = ?", (pid,))


def _send(client, text):
    page = client.get("/havel").text
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
    return client.post("/havel", data={"_csrf": csrf, "message": text, "history": "", "history_sig": "",
                                       "page": "stays", "device": "computer", "topic": "", "q": ""},
                       headers={"X-Havel": "1"})


def test_stay_card_renders_and_posts_to_the_existing_route(ready):
    client, pid = ready
    ai.set_client_for_tests(FakeClient([_reply(_action(property_id=pid, date_from=SOON, date_to=LATER))]))
    res = _send(client, "Add a stay from Friday to Sunday for 3 guests")
    assert res.status_code == 200
    html = res.text
    assert 'data-havel-card="create_stay"' in html and 'action="/reservations"' in html and 'name="_csrf"' in html
    assert any(host_i18n.translate(lang, "havel.card.nights", n=2) in html for lang in ("en", "cs", "vi"))
    assert 'name="expected_guests"' in html and 'value="3"' in html and "Riverside / 4" in html
    assert html.count("ui-btn-primary") >= 1 and "ui-btn-danger" not in html.split('data-havel-card="create_stay"')[1]
    assert "Open the form" not in html


def test_pin_card_is_red_and_link_card_is_read_only(ready):
    client, pid = ready
    ai.set_client_for_tests(FakeClient([_reply(_action(type="new_pin", property_id=pid)),
                                        _reply(_action(type="show_guest_link", property_id=pid))]))
    html = _send(client, "New PIN please").text
    assert f'action="/apartments/{pid}/regenerate-pin"' in html and "ui-btn-danger" in html and "triangle-alert" in html
    html = _send(client, "Show me the guest link").text
    assert "/l/" in html and "482913" in html and "havel-card-form" not in html
    assert 'data-copy="havel-link-' in html


def test_not_prepared_falls_back_to_the_sentence_and_the_form_link(ready):
    client, pid = ready
    ai.set_client_for_tests(FakeClient([_reply(_action(type="sync_calendars", property_id=None))]))
    html = _send(client, "Refresh my calendars").text
    assert "data-havel-card" not in html
    assert "No calendar is connected yet" in html or "není připojený" in html
    assert "Open the form" in html or "Otevřít formulář" in html
