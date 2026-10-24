"""0355: Quick answers, the yes/no facts shown inside guide cards."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, config, db, guest_guide, guide_facts, guide_photos, guide_token, host_i18n, i18n, leon
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "quick.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("quick-owner@example.test", "Quick owner", username="quick-owner", role="host")
    other = auth.create_account("quick-other@example.test", "Other owner", username="quick-other", role="host")
    now = db.utcnow()

    def home(name, user):
        apt_id = db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual",
        })
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
        return apt_id
    mine, foreign = home("Vivus / 3", owner), home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "quick-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "client": client}


def _go_live(apt_id):
    cards = {r["kind"]: r for r in guest_guide.items(apt_id)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apt_id, cards[kind]["id"], {"steps": f"How to {kind}"})


def _rules(apt_id):
    guide_facts.save_step(apt_id, "rules", {
        "pets": "no", "smoking": "no", "parties": "", "quiet_hours_from": "22:00", "quiet_hours_to": "07:00",
    })


def test_every_fact_has_copy_and_a_default_card():
    for fact, (step, kind, card) in guide_facts.FACTS.items():
        assert step in guide_facts.STEPS and card in guest_guide.DEFAULT_KINDS, fact
        for lang in ("en", "cs"):
            assert f"guest_guide.quick.q.{fact}" in host_i18n.STRINGS[lang], (lang, fact)
        keys = [f"guide_fact_{fact}_yes", f"guide_fact_{fact}_no"] if kind == "yesno" else [f"guide_fact_{fact}"]
        for lang in ("en", "cs", "de", "es", "fr", "uk"):
            for key in keys:
                assert key in i18n.STRINGS[lang], (lang, key)
    for step in guide_facts.STEPS:
        assert f"guest_guide.quick.step.{step}" in host_i18n.STRINGS["cs"]


def test_the_wizard_saves_each_step_and_resumes(ws):
    client, base = ws["client"], f"/apartments/{ws['home']}/guide"
    start = client.get(f"{base}/quick", follow_redirects=False)
    assert start.status_code == 303 and start.headers["location"].endswith("/quick/times")
    page = client.get(f"{base}/quick/times").text
    assert "Step 1 of 5" in page and "Arrival and checkout" in page and "Not sure" in page
    assert '<input type="radio" name="late_checkout" value="" checked>' in page  # "Not sure" until answered
    assert 'name="late_checkout" value="yes">' in page and "<select" not in page
    saved = client.post(f"{base}/quick/times", data={
        "checkin_from": "15:00", "checkout_by": "10:00", "late_checkout": "yes", "luggage": "",
    }, follow_redirects=False)
    assert saved.headers["location"].endswith("/quick/rules")
    assert guide_facts.answers(ws["home"]) == {
        "checkin_from": "15:00", "checkout_by": "10:00", "late_checkout": "yes", "step.times": "seen",
    }
    assert client.get(f"{base}/quick", follow_redirects=False).headers["location"].endswith("/quick/rules")
    skipped = client.post(f"{base}/quick/rules", data={"skip": "1", "pets": "no"}, follow_redirects=False)
    assert skipped.headers["location"].endswith("/quick/access")
    assert "pets" not in guide_facts.answers(ws["home"])
    last = client.post(f"{base}/quick/comfort", data={"cot": "yes"}, follow_redirects=False)
    assert last.headers["location"].endswith("/quick/done")


def test_bad_or_unsure_answers_store_nothing(ws):
    apt = ws["home"]
    guide_facts.save_step(apt, "times", {"checkin_from": "25:00", "late_checkout": "maybe"})
    guide_facts.save_step(apt, "rules", {"pets": "yes", "quiet_hours_from": "22:00", "quiet_hours_to": ""})
    assert guide_facts.answers(apt) == {"pets": "yes", "step.times": "seen", "step.rules": "seen"}
    guide_facts.save_step(apt, "rules", {"pets": ""})
    assert "pets" not in guide_facts.answers(apt)
    with pytest.raises(guest_guide.GuideError):
        guide_facts.save_step(apt, "nope", {})


def test_facts_reach_guests_and_leon_inside_their_card(ws):
    apt = ws["home"]
    _rules(apt)
    assert guide_facts.for_guest(apt, "everyone", "en") == []  # not live yet
    _go_live(apt)
    cards = {c["kind"]: c for c in guide_facts.for_guest(apt, "everyone", "en")}
    rules = cards["house_rules"]  # the host has not written it, the facts still show
    assert rules["facts"] == ["No pets.", "No smoking.", "Quiet hours from 22:00 to 07:00."]
    assert rules["steps"] == "" and cards["wifi"]["facts"] == []
    assert "parking" not in cards  # no facts, no text: still hidden
    czech = {c["kind"]: c for c in guide_facts.for_guest(apt, "everyone", "cs")}["house_rules"]
    assert czech["facts"][0] == "Bez zvířat."
    german = {c["kind"]: c for c in guide_facts.for_guest(apt, "everyone", "de")}["house_rules"]
    assert german["facts"][0] == "Keine Haustiere."
    block = leon.guide_block(list(cards.values()), "Vivus")
    assert f"[c{rules['id']}]" in block and "facts: No pets. No smoking. Quiet hours from 22:00 to 07:00." in block
    assert "22:00" in leon._card_corpus(list(cards.values()), [rules["id"]])


def test_the_guest_page_shows_the_fact_lines(ws):
    apt = ws["home"]
    _rules(apt)
    _go_live(apt)
    page = TestClient(app).get(f"/g/{guide_token.ensure(apt)}").text
    assert "No pets. No smoking. Quiet hours from 22:00 to 07:00." in page


def test_the_summary_lists_answers_and_cards_to_write(ws):
    _rules(ws["home"])
    page = ws["client"].get(f"/apartments/{ws['home']}/guide/quick/done").text
    assert "Your guide" in page and "No pets." in page and "Still to write" in page
    assert "Write the next card" in page and "guest_guide." not in page
    listing = ws["client"].get(f"/apartments/{ws['home']}/guide").text
    assert "Start with Quick answers" in listing
    czech = ws["client"].get(f"/apartments/{ws['home']}/guide/quick/done?lang=cs").text
    assert "Váš průvodce" in czech and "Bez zvířat." in czech


def test_another_hosts_property_is_out_of_reach(ws):
    client, base = ws["client"], f"/apartments/{ws['foreign']}/guide"
    assert client.get(f"{base}/quick/times").status_code == 404
    assert client.post(f"{base}/quick/rules", data={"pets": "yes"}).status_code == 404
    assert client.get(f"{base}/quick/done").status_code == 404
    assert client.get(f"/apartments/{ws['home']}/guide/quick/nope").status_code == 404
    assert guide_facts.answers(ws["foreign"]) == {}


def test_a_card_the_host_has_not_written_shows_no_photo(ws, monkeypatch, tmp_path):
    monkeypatch.setattr(guide_photos, "PHOTOS_DIR", tmp_path / "guide_photos")
    out = io.BytesIO()
    Image.new("RGB", (640, 480), (120, 90, 60)).save(out, format="JPEG")
    apt = ws["home"]
    _rules(apt)
    _go_live(apt)
    rules = {r["kind"]: r for r in guest_guide.items(apt)}["house_rules"]  # facts only, not written
    photo = guide_photos.add(apt, rules["id"], out.getvalue(), "image/jpeg")
    token = guide_token.ensure(apt)
    client = TestClient(app)
    page = client.get(f"/g/{token}").text
    assert "No pets. No smoking. Quiet hours from 22:00 to 07:00." in page
    assert f"/photos/{rules['id']}/{photo}" not in page
    assert client.get(f"/g/{token}/photos/{rules['id']}/{photo}").status_code == 404
