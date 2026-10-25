"""0404: the Leon setup wizard: switch on, import, check the cards, try, done."""
from __future__ import annotations

from app import config, db, guest_guide, guest_guide_import
from tests.test_0376_ai_gates import _host_post, ws  # noqa: F401 (fixture)

IMPORT_URLS = {
    "booking_url": "https://www.booking.com/hotel/cz/test-apartment.html",
    "airbnb_url": "https://www.airbnb.com/rooms/123456",
    "next": "leon",
}


def _live(monkeypatch, live: bool):
    def progress(apartment_id):
        return {
            "done": 5 if live else 0, "total": 5, "answered": 5 if live else 0, "cards": 5, "check": 0,
            "must_have_done": 5 if live else 0, "must_have_total": 5, "live": live,
        }
    monkeypatch.setattr(guest_guide, "progress", progress)


def _imports(monkeypatch, on: bool):
    monkeypatch.setattr(guest_guide_import, "enabled", lambda: on)
    monkeypatch.setattr(config, "APIFY_TOKEN", "test-token")


def _switch_on(client, apt_id, **extra):
    return _host_post(client, f"/apartments/{apt_id}/leon", {"action": "on", "terms": "1", **extra})


def test_wizard_is_404_where_leon_is_not_offered(ws, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    for url in ("/leon/setup", "/leon/setup/cards"):
        assert ws["host"].get(f"/apartments/{ws['home']}{url}?lang=en").status_code == 404


def test_unknown_step_is_404(ws):
    assert ws["host"].get(f"/apartments/{ws['home']}/leon/setup/nope?lang=en").status_code == 404


def test_fresh_property_starts_at_switch_on(ws):
    home = ws["home"]
    entry = ws["host"].get(f"/apartments/{home}/leon/setup?lang=en", follow_redirects=False)
    assert entry.status_code == 303 and entry.headers["location"].endswith("/leon/setup/switch_on")
    page = ws["host"].get(f"/apartments/{home}/leon/setup/switch_on?lang=en").text
    assert page.count("ui-btn-primary") == 1
    assert "/guide#leon-terms" in page
    assert 'name="next" value="setup"' in page
    other = ws["host"].get(f"/apartments/{home}/leon/setup/cards?lang=en", follow_redirects=False)
    assert other.status_code == 303 and other.headers["location"].endswith("/leon/setup/switch_on")


def test_switch_on_lands_on_import_when_imports_are_on(ws, monkeypatch):
    home = ws["home"]
    _live(monkeypatch, False)
    _imports(monkeypatch, True)
    r = _switch_on(ws["host"], home, next="setup")
    assert r.status_code == 303 and "/leon/setup?" in r.headers["location"]
    entry = ws["host"].get(f"/apartments/{home}/leon/setup?lang=en", follow_redirects=False)
    assert entry.headers["location"].endswith("/leon/setup/import")
    page = ws["host"].get(f"/apartments/{home}/leon/setup/import?lang=en").text
    assert 'name="booking_url"' in page and 'name="airbnb_url"' in page
    assert 'name="next" value="leon"' in page


def test_switch_on_lands_on_cards_when_imports_are_off(ws, monkeypatch):
    home = ws["home"]
    _live(monkeypatch, False)
    _imports(monkeypatch, False)
    _switch_on(ws["host"], home, next="setup")
    entry = ws["host"].get(f"/apartments/{home}/leon/setup?lang=en", follow_redirects=False)
    assert entry.headers["location"].endswith("/leon/setup/cards")


def test_import_queues_two_links_and_waits(ws, monkeypatch):
    home = ws["home"]
    _live(monkeypatch, False)
    _imports(monkeypatch, True)
    _switch_on(ws["host"], home, next="setup")
    r = _host_post(ws["host"], f"/apartments/{home}/guide/import", dict(IMPORT_URLS))
    assert r.status_code == 303 and "/leon/setup/import" in r.headers["location"]
    assert db.query_one("SELECT COUNT(*) AS n FROM guide_import WHERE apartment_id = ?", (home,))["n"] == 2
    assert "data-leon-import-wait" in ws["host"].get(f"/apartments/{home}/leon/setup/import?lang=en").text


def test_skip_import_goes_to_cards(ws, monkeypatch):
    home = ws["home"]
    _live(monkeypatch, False)
    _switch_on(ws["host"], home)
    r = _host_post(ws["host"], f"/apartments/{home}/leon/setup", {"action": "skip_import"})
    assert r.status_code == 303 and r.headers["location"].endswith("/leon/setup/cards")
    assert 'data-leon-setup-step="cards"' in ws["host"].get(f"/apartments/{home}/leon/setup/cards?lang=en").text


def test_card_from_the_wizard_returns_to_the_wizard(ws, monkeypatch):
    home = ws["home"]
    _live(monkeypatch, False)
    _switch_on(ws["host"], home)
    item = next(r for r in guest_guide.items(home) if r["kind"] not in guest_guide.MUST_HAVE)
    url = f"/apartments/{home}/guide/{item['id']}/skip"
    r = _host_post(ws["host"], url, {"skip": "1", "from": "leon", "then": "next"})
    assert r.status_code == 303
    loc = r.headers["location"]
    assert loc.endswith("/leon/setup/cards") or loc.endswith("?from=leon")
    plain = _host_post(ws["host"], url, {"skip": "1"})
    assert plain.headers["location"].endswith(f"/apartments/{home}/guide")


def test_live_guide_goes_to_try_then_done(ws, monkeypatch):
    home = ws["home"]
    _switch_on(ws["host"], home)
    _live(monkeypatch, True)
    entry = ws["host"].get(f"/apartments/{home}/leon/setup?lang=en", follow_redirects=False)
    assert entry.headers["location"].endswith("/leon/setup/try")
    assert 'value="finish"' in ws["host"].get(f"/apartments/{home}/leon/setup/try?lang=en").text
    r = _host_post(ws["host"], f"/apartments/{home}/leon/setup", {"action": "finish"})
    assert r.headers["location"].endswith("/leon/setup/done")
    assert f"/apartments/{home}/guide/qr" in ws["host"].get(f"/apartments/{home}/leon/setup/done?lang=en").text


def test_leon_settings_redirects_until_switched_on(ws):
    home = ws["home"]
    r = ws["host"].get(f"/apartments/{home}/leon?lang=en", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("/leon/setup")
    _switch_on(ws["host"], home)
    assert ws["host"].get(f"/apartments/{home}/leon?lang=en", follow_redirects=False).status_code == 200


def test_overview_card_opens_the_wizard_until_leon_is_fully_on(ws, monkeypatch):
    home = ws["home"]
    overview = f"/apartments/{home}?view=overview&lang=en"
    _live(monkeypatch, False)
    assert f'href="/apartments/{home}/leon/setup" data-leon-card="off"' in ws["host"].get(overview).text
    _switch_on(ws["host"], home)
    assert f'href="/apartments/{home}/leon/setup" data-leon-card="waiting"' in ws["host"].get(overview).text
    _live(monkeypatch, True)
    assert f'href="/apartments/{home}/leon" data-leon-card="on"' in ws["host"].get(overview).text
