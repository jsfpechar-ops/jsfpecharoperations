from __future__ import annotations

import re
import secrets
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, cleaning, config, db
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cleaning.sqlite3")
    monkeypatch.setattr(cleaning, "today", lambda: date(2026, 10, 16))
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("cleaner-owner@example.test", "Schedule owner", username="cleaner-owner", role="host")
    other = auth.create_account("cleaner-other@example.test", "Other owner", username="cleaner-other", role="host")
    now = db.utcnow()

    def home(name, user):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual", "checkin_hour": 15, "checkout_hour": 11,
        })
    homes = [home("Riverside / 4", owner), home("Garden / 2", owner)]
    foreign = home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "cleaner-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"owner": owner, "other": other, "homes": homes, "home": homes[0], "foreign": foreign, "client": client}


def stay(home, start="2026-10-17", end="2026-10-20", **extra):
    return db.insert("reservation", {
        "apartment_id": home, "uid": secrets.token_hex(16),
        "date_from": start, "date_to": end, "status": "active", "source": "manual",
        "created_at": db.utcnow(), "updated_at": db.utcnow(), **extra,
    })


def section(html, key):
    return html.split(f'id="cleaning-section-{key}"')[1].split("</section>")[0]


def test_host_page_has_today_and_week_tables_and_no_empty_later(workspace):
    ws = workspace
    stay(ws["home"], "2026-10-10", "2026-10-16")
    stay(ws["home"], "2026-10-16", "2026-10-19")
    response = ws["client"].get("/cleaning?lang=en")
    assert response.status_code == 200
    html = response.text
    today = section(html, "today")
    week = section(html, "week")
    assert "<table" in today and today.count("clickable-row") == 1
    assert "<table" in week and week.count("clickable-row") == 1
    assert "Riverside / 4" in today and "Riverside / 4" in week
    assert 'id="cleaning-section-later"' not in html


def test_cleaning_ten_days_out_lands_in_later(workspace):
    ws = workspace
    stay(ws["home"], "2026-10-20", "2026-10-26")
    html = ws["client"].get("/cleaning?lang=en").text
    assert "No cleaning today." in html
    assert 'id="cleaning-section-week"' not in html
    later = section(html, "later")
    assert later.count("clickable-row") == 1


def test_conflict_missing_hours_and_normal_give_three_badges(workspace, monkeypatch):
    ws = workspace
    stay(ws["home"], "2026-10-10", "2026-10-16")
    stay(ws["home"], "2026-10-16", "2026-10-19")
    stay(ws["homes"][1], "2026-10-10", "2026-10-17")
    original = cleaning.schedule

    def flagged(*args, **kwargs):
        result = original(*args, **kwargs)
        rows = sorted(result["cleanings"], key=lambda item: item["date"])
        rows[0]["conflict"] = True
        rows[1]["timingUnavailable"] = True
        rows[2]["conflict"] = False
        rows[2]["timingUnavailable"] = False
        return result

    monkeypatch.setattr(cleaning, "schedule", flagged)
    html = ws["client"].get("/cleaning?lang=en").text
    assert 'pill p-warn">Check the time' in html
    assert 'pill p-warn">Hours missing' in html
    assert 'pill p-ok">Scheduled' in html


def test_schedule_json_list_html_uses_tables(workspace):
    ws = workspace
    stay(ws["home"], "2026-10-10", "2026-10-16")
    body = ws["client"].get("/cleaning/schedule", params={"from": "2026-10-16", "to": "2026-11-15", "lang": "en"}).json()
    assert "cleaning-section" in body["listHtml"]
    assert re.search(r'id="cleaning-\d+"', body["listHtml"])
    assert "cleaning-card" not in body["listHtml"]


def test_shared_view_keeps_cards_and_has_no_sections(workspace):
    ws = workspace
    stay(ws["home"], "2026-10-10", "2026-10-16")
    _, token = cleaning.new_share(ws["owner"], [ws["home"]])
    page = TestClient(app).get(f"/cleaning/shared/{token}")
    assert page.status_code == 200
    assert "cleaning-card" in page.text
    assert "cleaning-section" not in page.text


def test_phone_week_shows_three_rows_then_show_more_for_the_rest(workspace):
    ws = workspace
    for end in ["2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]:
        stay(ws["home"], "2026-10-10", end)
    stay(ws["home"], "2026-10-25", "2026-10-30")
    html = ws["client"].get("/cleaning?lang=cs").text
    phone = html.split('<div class="cleaning-phone">')[1]
    before_more = phone.split('<details class="cleaning-more"')[0]
    assert before_more.count('class="row"') == 3
    assert '<details class="cleaning-more"' in phone
    assert "Zobrazit další (4)" in phone
