"""0303: guide cards in the guest's language: cached per card and language, filled after the response. No network."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app import ai, auth, config, db, guest_guide, guide_token, guide_translate, mail
from app.main import app
from tests.ai_fake import FakeClient, reply
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "translate.sqlite3")
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"guide_translate"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    db.init_db()
    owner = auth.create_account("tr-owner@example.test", "Translate owner", username="tr-owner", role="host")
    home = db.insert("apartment", {
        "owner_user_id": owner, "internal_name": "Translate flat", "active": 1, "created_at": db.utcnow(),
        "automation_mode": "manual", "permalink_token": "translatetok0353", "permalink_window_days": 14,
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (home,)))
    cards = {r["kind"]: r for r in guest_guide.items(home)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(home, cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    guest_guide.save(home, cards["heating"]["id"], {
        "steps": "Zmáčkněte kulaté tlačítko.\nNastavte 22 stupňů.", "location": "Skříň v předsíni"})
    guest_guide.save(home, cards["wifi"]["id"], {"steps": "Síť KOCKA, heslo Mlsna2024"})
    yield {"home": home, "cards": {r["kind"]: r for r in guest_guide.items(home)}, "client": TestClient(app),
           "qr": guide_token.ensure(home)}
    ai.set_client_for_tests(None)


def _german(payload_cards, broken=None):
    out = []
    for card in payload_cards:
        steps = [s.replace("Zmáčkněte kulaté tlačítko.", "Drücken Sie den runden Knopf.")
                  .replace("Nastavte 22 stupňů.", "Stellen Sie 22 Grad ein.") for s in card["steps"]]
        if broken == card["id"]:
            steps = ["Stellen Sie 23 Grad ein." for _ in steps]
        out.append({"id": card["id"], "title": "DE " + card["title"], "location": card["location"].replace(
            "Skříň v předsíni", "Schrank im Flur"), "steps": steps, "watch_out": card["watch_out"]})
    return reply({"cards": out})


def _sent_cards(fake, i=0):
    text = fake.calls[i]["messages"][0]["content"]
    return json.loads(text.split("<cards>\n", 1)[1].split("\n</cards>", 1)[0])


class EchoGerman(FakeClient):
    """Answers each call with a German version of exactly the cards it was sent."""

    def __init__(self, broken=None):
        super().__init__([])
        self.broken = broken

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        text = kwargs["messages"][0]["content"]
        return _german(json.loads(text.split("<cards>\n", 1)[1].split("\n</cards>", 1)[0]), self.broken)


def test_the_first_view_shows_the_original_and_the_second_the_translation(ws):
    fake = EchoGerman()
    ai.set_client_for_tests(fake)
    url = f"/g/{ws['qr']}?lang=de"
    first = ws["client"].get(url).text
    assert "Zmáčkněte kulaté tlačítko." in first and "data-guide-translating" in first
    assert fake.calls, "the fill runs after the response"
    second = ws["client"].get(url).text
    assert "Drücken Sie den runden Knopf." in second and "Schrank im Flur" in second
    assert "Von KI übersetzt" in second and "data-guide-original" in second
    assert "Zmáčkněte kulaté tlačítko." in second, "the original stays one tap away"
    assert "data-guide-translating" not in second
    calls = len(fake.calls)
    ws["client"].get(url)
    assert len(fake.calls) == calls, "cached: no new call"


def test_door_codes_and_wifi_are_never_sent_and_host_cards_never_leave(ws):
    guest_guide.save(ws["home"], ws["cards"]["checkout"]["id"], {"steps": "Klíče do schránky", "visibility": "host"})
    fake = EchoGerman()
    ai.set_client_for_tests(fake)
    ws["client"].get(f"/g/{ws['qr']}?lang=de")
    sent = [card for i in range(len(fake.calls)) for card in _sent_cards(fake, i)]
    ids = {c["id"] for c in sent}
    assert ws["cards"]["wifi"]["id"] not in ids and ws["cards"]["checkout"]["id"] not in ids
    assert all("Mlsna2024" not in str(c) for c in sent)
    assert ws["cards"]["heating"]["id"] in ids


def test_a_translation_that_changes_a_number_is_dropped_and_not_retried(ws):
    fake = EchoGerman(broken=ws["cards"]["heating"]["id"])
    ai.set_client_for_tests(fake)
    url = f"/g/{ws['qr']}?lang=de"
    ws["client"].get(url)
    body = ws["client"].get(url).text
    assert "23 Grad" not in body and "Nastavte 22 stupňů." in body
    calls = len(fake.calls)
    ws["client"].get(url)
    assert len(fake.calls) == calls


def test_an_edit_makes_the_cached_translation_stale(ws):
    ai.set_client_for_tests(EchoGerman())
    url = f"/g/{ws['qr']}?lang=de"
    ws["client"].get(url)
    guest_guide.save(ws["home"], ws["cards"]["heating"]["id"], {"steps": "Zmáčkněte kulaté tlačítko.\nNastavte 21 stupňů."})
    body = ws["client"].get(url).text
    assert "Nastavte 21 stupňů." in body and "22 Grad" not in body
    assert "Stellen Sie 21 Grad ein." not in body
    row = db.query_one("SELECT steps FROM guide_translation WHERE item_id = ? AND lang = 'de'", (ws["cards"]["heating"]["id"],))
    assert "21" in row["steps"], "the second view refreshed the row"


@pytest.mark.parametrize("problem", ["off", "budget", "error"])
def test_off_spent_or_failing_ai_shows_the_original_never_an_error(ws, monkeypatch, problem):
    if problem == "off":
        monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    elif problem == "budget":
        monkeypatch.setattr(config, "ai_monthly_usd", lambda feature: 0.0)
    ai.set_client_for_tests(FakeClient([reply(text="not json")] * 3))
    for _ in range(2):
        response = ws["client"].get(f"/g/{ws['qr']}?lang=de")
        assert response.status_code == 200
        assert "Nastavte 22 stupňů." in response.text and "data-guide-original" not in response.text
    if problem != "error":
        assert "data-guide-translating" not in response.text


def test_rows_go_with_the_card_and_logs_carry_no_text(ws, caplog):
    ai.set_client_for_tests(EchoGerman())
    custom = guest_guide.add_custom(ws["home"], "area", "Pekárna")
    guest_guide.save(ws["home"], custom, {"steps": "Otevírá v 7:00"})
    with caplog.at_level(logging.INFO):
        ws["client"].get(f"/g/{ws['qr']}?lang=de")
    assert db.query_one("SELECT COUNT(*) AS n FROM guide_translation WHERE item_id = ?", (custom,))["n"] == 1
    assert "Pekárna" not in caplog.text and "Zmáčkněte" not in caplog.text
    guest_guide.delete_custom(ws["home"], custom)
    assert db.query_one("SELECT COUNT(*) AS n FROM guide_translation WHERE item_id = ?", (custom,))["n"] == 0


def test_the_validator_keeps_codes_links_and_step_counts():
    original = {"title": "Klíče", "location": "", "steps": ["Kód 4455#", "Viz https://example.test/a"], "watch_out": ""}
    good = {"title": "Keys", "location": "", "steps": ["Code 4455#", "See https://example.test/a"], "watch_out": ""}
    assert guide_translate.valid(original, good)
    assert not guide_translate.valid(original, {**good, "steps": ["Code 4455#"]})
    assert not guide_translate.valid(original, {**good, "steps": ["Code 4456#", "See https://example.test/a"]})
    assert not guide_translate.valid(original, {**good, "steps": ["Code 4455#", "See the website"]})
    assert not guide_translate.valid(original, {**good, "location": "Hall"})


def test_the_host_sees_one_usage_line(ws):
    ai.set_client_for_tests(EchoGerman())
    ws["client"].get(f"/g/{ws['qr']}?lang=de")
    db.execute("INSERT INTO ai_usage (day, feature, key, requests, input_tokens, cache_write_tokens, cache_read_tokens, "
               "output_tokens) VALUES (?, 'leon', ?, 7, 0, 0, 0, 0)", (ai.today().isoformat(), str(ws["home"])))
    client = TestClient(app)
    assert login_as(client, "tr-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    body = client.get(f"/apartments/{ws['home']}/guide").text
    assert "data-guide-usage" in body
    assert "answered this month: 7" in body and "Translated for guests into: DE" in body


def test_the_caps_default_low():
    assert config.ai_monthly_usd("guide_translate") <= 2 and config.ai_key_daily_usd("guide_translate") == 0.05
