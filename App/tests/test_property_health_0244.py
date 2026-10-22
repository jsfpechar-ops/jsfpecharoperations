"""0244: the property health check says what works today, with one fix button per problem."""

from __future__ import annotations

from app import db, property_health, property_setup
from tests.test_guest_links_bilingual import _apartment_id, host  # noqa: F401

APARTMENT = {"id": 7, "internal_name": "Flat", "active": 1}
READY = {"report": [{"key": "idub", "anchor": "ubyport", "done": True}],
         "invite": [{"key": "operator", "anchor": "basics", "done": True},
                    {"key": "controller", "anchor": "basics", "done": True}]}
FEED_OK = [{"active": 1, "last_status": "ok"}]


def _rows(**kwargs):
    defaults = {"feeds": FEED_OK, "readiness": READY, "door_code": None,
                "open_kinds": set(), "guest_used": True, "link_due": False}
    defaults.update(kwargs)
    return {row["key"]: row for row in property_health.checks(
        APARTMENT, defaults["feeds"], defaults["readiness"], defaults["door_code"],
        open_kinds=defaults["open_kinds"], guest_used=defaults["guest_used"], link_due=defaults["link_due"],
    )}


def test_a_healthy_property_needs_nothing():
    rows = _rows()
    assert list(rows) == ["calendar", "guest_link", "police", "business"]
    assert {row["state"] for row in rows.values()} == {"ok"}
    assert all(not row["href"] for row in rows.values())
    assert property_health.to_fix(rows.values()) == []


def test_each_problem_gets_one_button_to_the_exact_setting():
    missing = {"report": [{"key": "zip", "anchor": "address", "done": False}],
               "invite": [{"key": "operator", "anchor": "basics", "done": False}]}
    rows = _rows(feeds=[{"active": 1, "last_status": "error"}], readiness=missing,
                 guest_used=False, link_due=True)
    assert rows["calendar"]["state"] == "bad"
    assert rows["calendar"]["href"] == "/apartments/7?view=bookings#calendars"
    assert rows["guest_link"]["state"] == "warn"
    assert rows["guest_link"]["href"] == "/apartments/7?view=settings&section=guests#communication"
    assert rows["police"]["href"] == "/apartments/7?view=settings&section=property#address"
    assert rows["business"]["href"] == "/apartments/7?view=settings&section=property#operator-picker"
    assert len(property_health.to_fix(rows.values())) == 4


def test_a_refused_police_login_wins_over_complete_details():
    rows = _rows(open_kinds={"ubyport_auth_failed"})
    assert rows["police"]["state"] == "bad"
    assert rows["police"]["text_key"] == "health.police.login"
    assert rows["police"]["href"].endswith("section=reporting#ubyport")


def test_no_calendar_is_a_nudge_and_door_codes_show_only_with_a_lock():
    rows = _rows(feeds=[], guest_used=False, link_due=False, door_code={"enabled": False})
    assert rows["calendar"]["state"] == "warn"
    assert rows["guest_link"]["state"] == "off" and not rows["guest_link"]["href"]
    assert rows["door"]["state"] == "off" and not rows["door"]["href"]
    assert "door" not in _rows()


def test_the_overview_shows_the_health_check(host):  # noqa: F811
    apartment_id = _apartment_id()
    property_setup.set_hidden(apartment_id, False)  # stores a setup state so finish() can mark it
    property_setup.finish(apartment_id)
    for lang, title in (("en", "Health check"), ("cs", "Kontrola nastavení"), ("vi", "Kiểm tra thiết lập")):
        page = host.get(f"/apartments/{apartment_id}?view=overview&lang={lang}").text
        assert title in page, lang
        assert 'data-health-check="police"' in page
        assert 'class="setup-status-tile' not in page
    assert db.query_one("SELECT id FROM apartment WHERE id = ?", (apartment_id,))
