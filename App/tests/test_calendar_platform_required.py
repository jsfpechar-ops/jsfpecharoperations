"""0089: a calendar needs a platform and a valid link, checked on the server."""
from __future__ import annotations

import secrets
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app import auth, db, feed_url, icalsync
from app.main import app
from app.routes import admin as admin_routes
from tests.conftest import login_as

PREFIX = "cal-platform-"
URL = "https://www.airbnb.com/calendar/ical/4242.ics?s=synthetic"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        owner_id = row["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (owner_id,)):
            db.execute("DELETE FROM ical_feed WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM apartment_slug WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _make_host(lang="en"):
    username = f"{PREFIX}{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Calendar Host", role="host", username=username)
    entity_id = db.insert("legal_entity", {"name": "Calendar Operator", "owner_user_id": owner_id, "created_at": db.utcnow()})
    apartment_id = db.insert("apartment", {
        "internal_name": f"Calendar Flat {secrets.token_hex(2)}",
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "permalink_token": f"calp{secrets.token_hex(5)}",
        "permalink_pin": "123456",
        "active": 1,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert login_as(client, username, url=f"/login?lang={lang}", follow_redirects=False).status_code == 303
    return {"client": client, "owner": owner_id, "apartment": apartment_id}


@pytest.fixture
def calls(monkeypatch):
    seen = {"validate": [], "sync": []}

    def validate(url):
        seen["validate"].append(url)
        if "unsafe" in url:
            raise feed_url.FeedUrlError("blocked", "flash.error.feed_host_private")
        return url.strip()

    def sync(apartment_id):
        seen["sync"].append(apartment_id)
        return {"created": 0, "updated": 0, "errors": seen.get("sync_errors", 0)}

    monkeypatch.setattr(feed_url, "validate_calendar_url", validate)
    monkeypatch.setattr(icalsync, "sync_all", sync)
    db.init_db()
    _cleanup()
    yield seen
    _cleanup()


def _feeds(apartment_id):
    return db.query("SELECT * FROM ical_feed WHERE apartment_id = ? ORDER BY id", (apartment_id,))


def _post(host, **data):
    return host["client"].post(f"/apartments/{host['apartment']}/feeds", data=data, follow_redirects=False)


@pytest.mark.parametrize(
    "platform",
    [None, "", "   ", "myspace", "Airbnb"],
    ids=["missing", "blank", "whitespace", "unknown", "readable-not-a-choice"],
)
def test_a_missing_or_unknown_platform_is_refused_before_any_write(calls, platform):
    host = _make_host()
    data = {"url": URL}
    if platform is not None:
        data["label"] = platform
    response = _post(host, **data)
    assert response.status_code == 400
    assert "Choose the platform this calendar comes from." in response.text
    assert f'value="{URL}"' in response.text.replace("&amp;", "&")
    assert _feeds(host["apartment"]) == []
    assert calls["validate"] == []
    assert calls["sync"] == []


def test_other_needs_a_readable_name(calls):
    host = _make_host()
    response = _post(host, label="other", label_other="  ", url=URL)
    assert response.status_code == 400
    assert "Type the platform name." in response.text
    response = _post(host, label="other", label_other="Bad\x07name", url=URL)
    assert response.status_code == 400
    assert "Use up to 80 ordinary characters." in response.text
    response = _post(host, label="other", label_other="x" * 81, url=URL)
    assert response.status_code == 400
    assert _feeds(host["apartment"]) == []
    assert calls["sync"] == []
    ok = _post(host, label="other", label_other="  Holidu  ", url=URL)
    assert ok.status_code == 303
    feed = _feeds(host["apartment"])[0]
    assert feed["label"] == "Holidu"
    assert feed["own_name"] == "Holidu"


@pytest.mark.parametrize("url", ["", "   "], ids=["empty", "whitespace"])
def test_a_blank_link_is_refused_before_any_network_check(calls, url):
    host = _make_host()
    response = _post(host, label="booking", url=url)
    assert response.status_code == 400
    assert "Paste the calendar link." in response.text
    assert calls["validate"] == []
    assert calls["sync"] == []
    assert _feeds(host["apartment"]) == []


def test_an_unsafe_link_is_refused_with_the_draft_kept(calls):
    host = _make_host()
    response = _post(host, label="vrbo", own_name="Garden", url="https://unsafe.example/x.ics")
    assert response.status_code == 400
    page = response.text
    assert 'value="https://unsafe.example/x.ics"' in page
    assert 'value="Garden"' in page
    assert '<option value="vrbo" selected>' in page
    assert 'id="url-error"' in page and "autofocus" in page
    assert _feeds(host["apartment"]) == []
    assert calls["sync"] == []


def test_a_foreign_property_cannot_get_a_calendar(calls):
    owner = _make_host()
    intruder = _make_host()
    response = intruder["client"].post(
        f"/apartments/{owner['apartment']}/feeds",
        data={"label": "airbnb", "url": URL},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert urlparse(response.headers["location"]).path == "/apartments"
    assert _feeds(owner["apartment"]) == []
    assert calls["sync"] == []


def test_a_duplicate_link_is_refused_with_the_property_named(calls):
    host = _make_host()
    assert _post(host, label="airbnb", url=URL).status_code == 303
    again = _post(host, label="booking", url=URL)
    assert again.status_code == 400
    assert "already added to" in again.text
    assert len(_feeds(host["apartment"])) == 1


def test_success_stores_a_readable_platform_and_returns_to_calendars(calls):
    host = _make_host()
    response = _post(host, label="booking", url=URL)
    assert response.status_code == 303
    assert response.headers["location"].endswith("#calendars")
    feed = _feeds(host["apartment"])[0]
    assert feed["label"] == "Booking.com"
    assert feed["own_name"] == "Booking.com"
    assert calls["sync"] == [host["apartment"]]


def test_a_custom_name_is_kept(calls):
    host = _make_host()
    _post(host, label="echalupy", own_name="  Chalupa u lesa ", url=URL)
    feed = _feeds(host["apartment"])[0]
    assert feed["label"] == "e-chalupy"
    assert feed["own_name"] == "Chalupa u lesa"


def test_a_sync_failure_keeps_the_new_feed_and_says_so(calls):
    host = _make_host()
    calls["sync_errors"] = 1
    response = _post(host, label="agoda", url=URL)
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.endswith("#calendars")
    assert "err=" in location
    assert len(_feeds(host["apartment"])) == 1


def test_old_feeds_get_readable_names_without_a_rewrite(calls):
    host = _make_host()
    rows = [
        ("https://admin.booking.com/hotel/ical.html?t=1", "", ""),
        ("https://www.airbnb.com/calendar/ical/9.ics", "  ", None),
        ("https://calendar.example.org/feed.ics", None, None),
        ("https://calendar.example.org/two.ics", "Owner portal", ""),
    ]
    for url, label, own in rows:
        db.insert("ical_feed", {
            "apartment_id": host["apartment"], "url": url, "label": label, "own_name": own,
            "active": 1, "created_at": db.utcnow(),
        })
    for lang, fallback_name, other in (("en", "Calendar", "Other"), ("cs", "Kalendář", "Jiný")):
        page = host["client"].get(f"/apartments/{host['apartment']}?lang={lang}").text
        table = page[page.index("feed-table") : page.index("</table>", page.index("feed-table"))]
        assert "—" not in table
        assert "<strong>Booking.com</strong>" in table
        assert "<strong>Airbnb</strong>" in table
        assert f"<strong>{fallback_name}</strong>" in table
        assert other in table
        assert "<strong>Owner portal</strong>" in table
    stored = [(row["label"], row["own_name"]) for row in _feeds(host["apartment"])]
    assert stored == [(label, own) for _, label, own in rows]


def test_the_add_form_shows_platform_first_and_no_more_options(calls):
    host = _make_host()
    for lang, choose in (("en", "Choose platform"), ("cs", "Vyberte platformu")):
        page = host["client"].get(f"/apartments/{host['apartment']}?lang={lang}").text
        form = page[page.index('id="calendar-add"') : page.index("</form>", page.index('id="calendar-add"'))]
        assert form.index('name="label"') < form.index('name="url"')
        assert f'<option value="" disabled selected>{choose}</option>' in form
        assert "more-options" not in form
        assert 'name="own_name"' in form
        for _key, name in admin_routes.CALENDAR_PLATFORMS:
            if name:
                assert f">{name}</option>" in form


def test_helper_rejects_control_characters_in_the_custom_name():
    values, errors = admin_routes._calendar_platform("airbnb", "", "bad\nname")
    assert errors == {"own_name": "calendar.error.name_invalid"}
    values, errors = admin_routes._calendar_platform("airbnb", "", "")
    assert values == {"label": "Airbnb", "own_name": "Airbnb"} and not errors
