"""0347: Booking and Airbnb listing imports (fetch and store only)."""
from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, guest_guide_import as gi, retention
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "import.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    monkeypatch.setattr(config, "APIFY_TOKEN", "test-token")
    monkeypatch.setattr(config, "APIFY_MONTHLY_RUNS", 40)
    db.init_db()
    owner = auth.create_account("imp-owner@example.test", "Import owner", username="imp-owner", role="host")
    other = auth.create_account("imp-other@example.test", "Other owner", username="imp-other", role="host")
    now = db.utcnow()

    def home(name, user):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual",
        })
    mine = home("Vivus / 3", owner)
    foreign = home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "imp-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "client": client}


BOOKING = "https://www.booking.com/hotel/cz/vivus-3.cs.html?aid=304142&label=gen173nr&sid=abc#hotelTmpl"
AIRBNB = "https://www.airbnb.cz/rooms/53997462?adults=2&source_impression_id=p3_1&check_in=2026-11-01"


def _post(ws, url, home=None):
    return ws["client"].post(
        f"/apartments/{home or ws['home']}/guide/import", data={"url": url}, follow_redirects=False,
    )


def test_good_links_are_rebuilt_without_tracking():
    assert gi.normalise_url(BOOKING) == {"source": "booking", "url": "https://www.booking.com/hotel/cz/vivus-3.cs.html"}
    assert gi.normalise_url(AIRBNB) == {"source": "airbnb", "url": "https://www.airbnb.com/rooms/53997462"}
    assert gi.normalise_url("https://booking.com/hotel/DE/Hotel_Name.html")["url"] == "https://www.booking.com/hotel/de/Hotel_Name.html"
    assert gi.normalise_url("https://www.airbnb.co.uk/rooms/plus/123/")["url"] == "https://www.airbnb.com/rooms/123"
    assert gi.normalise_url("  https://www.airbnb.com/rooms/123  ")["source"] == "airbnb"


@pytest.mark.parametrize("evil", [
    "",
    "not a url",
    "http://www.booking.com/hotel/cz/vivus-3.html",
    "https://www.booking.com@evil.example/hotel/cz/vivus-3.html",
    "https://evil.example/hotel/cz/vivus-3.html",
    "https://www.booking.com.evil.example/hotel/cz/vivus-3.html",
    "https://wwwbooking.com/hotel/cz/vivus-3.html",
    "https://b00king.com/hotel/cz/vivus-3.html",
    "https://www.booking.com:8443/hotel/cz/vivus-3.html",
    "https://127.0.0.1/hotel/cz/vivus-3.html",
    "https://[::1]/rooms/123",
    "https://www.airbnb.evil/rooms/123",
    "https://airbnb.com.evil.example/rooms/123",
    "https://www.airbnb.com/rooms/123?x=1\\@evil.example",
    "https://www.airbnb.com/s/Prague/homes",
    "https://www.airbnb.com/h/short-link",
    "https://www.airbnb.com/rooms/abc",
    "https://www.booking.com/Share-abc123",
    "https://www.booking.com/searchresults.html?ss=Prague",
    "https://www.booking.com/hotel/cz/../../admin.html",
    "https://www.böoking.com/hotel/cz/vivus.html",
    "file:///etc/passwd",
    "https://" + "a" * 2100 + ".booking.com/hotel/cz/x.html",
])
def test_evil_links_are_refused(evil):
    with pytest.raises(gi.GuideImportError) as exc:
        gi.normalise_url(evil)
    assert exc.value.key.startswith("flash.error.guide_import_")


def test_a_request_queues_a_row_and_counts_down(ws):
    assert gi.imports_left(ws["home"]) == 2
    r = _post(ws, BOOKING)
    assert r.status_code == 303 and "msg=" in r.headers["location"]
    rows = gi.imports(ws["home"])
    assert [(x["source"], x["status"], x["url"]) for x in rows] == [
        ("booking", "queued", "https://www.booking.com/hotel/cz/vivus-3.cs.html"),
    ]
    assert gi.imports_left(ws["home"]) == 1
    page = ws["client"].get(f"/apartments/{ws['home']}/guide").text
    assert "Importing" in page and "Imports left for this property: 1." in page


def test_only_one_import_runs_at_a_time(ws):
    _post(ws, BOOKING)
    r = _post(ws, AIRBNB)
    assert "err=" in r.headers["location"] and len(gi.imports(ws["home"])) == 1


def test_one_import_per_listing_for_good(ws):
    _post(ws, AIRBNB)
    db.execute("UPDATE guide_import SET status = 'failed'")
    assert gi.imports_left(ws["home"]) == 2  # a failed run does not use the month up
    _post(ws, AIRBNB)
    db.execute("UPDATE guide_import SET status = 'done' WHERE status = 'queued'")
    r = _post(ws, AIRBNB)
    assert "err=" in r.headers["location"] and "already imported" in r.headers["location"].replace("%20", " ")
    _post(ws, BOOKING)
    db.execute("UPDATE guide_import SET status = 'done' WHERE status = 'queued'")
    assert gi.imports_left(ws["home"]) == 0
    page = ws["client"].get(f"/apartments/{ws['home']}/guide").text
    assert "Imports left for this property: 0." in page and 'name="url"' not in page


def test_the_global_budget(ws, monkeypatch):
    monkeypatch.setattr(config, "APIFY_MONTHLY_RUNS", 1)
    db.execute("INSERT INTO lock_api_usage (month, provider, calls) VALUES (?, 'apify', 1)", (gi._month_key(),))
    with pytest.raises(gi.GuideImportError) as exc:
        gi.request_import(ws["home"], AIRBNB)
    assert exc.value.key == "flash.error.guide_import_budget"


def test_off_without_a_token(ws, monkeypatch):
    monkeypatch.setattr(config, "APIFY_TOKEN", "")
    page = ws["client"].get(f"/apartments/{ws['home']}/guide").text
    assert "Imports are not switched on" in page and 'name="url"' not in page
    r = _post(ws, BOOKING)
    assert "err=" in r.headers["location"] and gi.imports(ws["home"]) == []
    assert gi.process_queue() == 0


def test_a_foreign_property_is_not_found(ws):
    assert _post(ws, BOOKING, home=ws["foreign"]).status_code == 404
    assert gi.imports(ws["foreign"]) == []


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self.content = json.dumps(body).encode()

    def json(self):
        return json.loads(self.content)


def _fake_post(calls, status=201, body=None):
    def post(url, **kw):
        calls.append((url, kw))
        return _Resp(status, body if body is not None else [])
    return post


AIRBNB_ITEM = {
    "id": "53997462", "title": "Flat in Vinohrady", "description": "Quiet  flat.\n\nKeys in the box.",
    "houseRules": {"additional": "Quiet hours 22:00 to 7:00.", "general": [
        {"title": "Checking in and out", "values": [{"title": "Check-in after 15:00", "icon": "x"}, {"title": "Checkout before 10:00", "icon": "x"}]},
    ]},
    "amenities": [{"title": "Kitchen", "values": [
        {"title": "Dishwasher", "available": True, "icon": "x"}, {"title": "Oven", "available": False},
    ]}],
    "host": {"name": "Jana"}, "price": {"amount": 100}, "images": ["https://x"] * 50, "evil": "<script>",
}


def test_the_worker_runs_the_actor_and_stores_only_trimmed_text(ws, monkeypatch):
    calls = []
    monkeypatch.setattr(gi.requests, "post", _fake_post(calls, body=[AIRBNB_ITEM]))
    import_id = gi.request_import(ws["home"], AIRBNB)
    assert gi.process_queue() == 1
    (url, kw), = calls
    assert url == "https://api.apify.com/v2/acts/tri_angle~airbnb-rooms-urls-scraper/run-sync-get-dataset-items"
    assert kw["timeout"] == gi.HTTP_TIMEOUT and kw["allow_redirects"] is False
    assert kw["headers"]["Authorization"] == "Bearer test-token"
    assert json.loads(kw["data"]) == {"startUrls": [{"url": "https://www.airbnb.com/rooms/53997462"}]}
    assert kw["params"]["timeout"] == config.APIFY_TIMEOUT and kw["params"]["maxItems"] == 1
    row = db.query_one("SELECT status, raw_json FROM guide_import WHERE id = ?", (import_id,))
    assert row["status"] == "done"
    data = json.loads(row["raw_json"])
    assert data == {
        "source": "airbnb", "title": "Flat in Vinohrady", "description": "Quiet flat. Keys in the box.",
        "amenities": ["Kitchen", "Dishwasher"],
        "houseRules": ["Quiet hours 22:00 to 7:00.", "Checking in and out", "Check-in after 15:00", "Checkout before 10:00"],
    }
    assert gi.runs_this_month() == 1
    pending = gi.pending_for(ws["home"])
    assert [p["id"] for p in pending] == [import_id] and pending[0]["data"]["title"] == "Flat in Vinohrady"
    gi.mark_used(import_id)
    assert gi.pending_for(ws["home"]) == []
    assert db.query_one("SELECT status, raw_json FROM guide_import WHERE id = ?", (import_id,))["raw_json"] is None


def test_booking_input_address_and_size_cap(ws, monkeypatch):
    item = {"name": "Vivus 3", "description": "x" * 10000, "checkIn": "From 3:00 PM", "checkOut": "Until 10:00 AM",
            "address": {"full": "Vinohradská 1, Praha 3", "country": "CZ"}, "rooms": [{"price": 1}], "image": "u"}
    calls = []
    monkeypatch.setattr(gi.requests, "post", _fake_post(calls, body=[item]))
    gi.request_import(ws["home"], BOOKING)
    gi.process_queue()
    body = json.loads(calls[0][1]["data"])
    assert body["startUrls"] == [{"url": "https://www.booking.com/hotel/cz/vivus-3.cs.html"}] and body["maxItems"] == 1
    data = gi.pending_for(ws["home"])[0]["data"]
    assert data["checkIn"] == "From 3:00 PM" and data["address"] == "Vinohradská 1, Praha 3"
    assert len(data["description"]) == gi.MAX_TEXT and "rooms" not in data and "image" not in data
    big = gi.trim("airbnb", {"title": "t", "description": "z" * 4000,
                             "amenities": [{"title": f"Thing {i} " + "y" * 190} for i in range(500)]})
    assert len(json.dumps(big, ensure_ascii=False).encode()) <= gi.MAX_STORED_BYTES
    assert len(big["amenities"]) <= gi.MAX_LIST_ITEMS


@pytest.mark.parametrize("status,body,code", [
    (408, {"error": {"type": "run-timeout-exceeded"}}, "timeout"),
    (401, {"error": {"type": "token-not-found"}}, "http_401"),
    (201, [], "empty"),
    (201, [{"images": ["x"]}], "empty"),
])
def test_failures_store_a_short_code_and_no_text(ws, monkeypatch, status, body, code):
    monkeypatch.setattr(gi.requests, "post", _fake_post([], status=status, body=body))
    import_id = gi.request_import(ws["home"], AIRBNB)
    gi.process_queue()
    row = db.query_one("SELECT status, error, raw_json FROM guide_import WHERE id = ?", (import_id,))
    assert (row["status"], row["error"], row["raw_json"]) == ("failed", code, None)
    assert "Did not work" in ws["client"].get(f"/apartments/{ws['home']}/guide").text


def test_a_network_error_is_a_failed_row(ws, monkeypatch):
    monkeypatch.setattr(gi.requests, "post", lambda *a, **k: (_ for _ in ()).throw(gi.requests.ConnectionError("down")))
    import_id = gi.request_import(ws["home"], BOOKING)
    gi.process_queue()
    assert db.query_one("SELECT error FROM guide_import WHERE id = ?", (import_id,))["error"] == "network"


def test_the_worker_stops_at_the_global_budget(ws, monkeypatch):
    monkeypatch.setattr(config, "APIFY_MONTHLY_RUNS", 1)
    calls = []
    monkeypatch.setattr(gi.requests, "post", _fake_post(calls, body=[AIRBNB_ITEM]))
    first = gi.request_import(ws["home"], AIRBNB)
    db.execute("UPDATE guide_import SET status = 'failed'")
    second = gi.request_import(ws["home"], BOOKING)
    db.execute("UPDATE guide_import SET status = 'queued' WHERE id = ?", (first,))
    assert gi.process_queue() == 1 and len(calls) == 1
    assert db.query_one("SELECT error FROM guide_import WHERE id = ?", (second,))["error"] == "budget"


def test_retention_drops_raw_text_after_seven_days_and_failed_rows_after_sixty(ws, monkeypatch):
    monkeypatch.setattr(gi.requests, "post", _fake_post([], body=[AIRBNB_ITEM]))
    import_id = gi.request_import(ws["home"], AIRBNB)
    gi.process_queue()
    db.execute("UPDATE guide_import SET created_at = '2026-01-01T10:00:00' WHERE id = ?", (import_id,))
    assert gi.purge(date(2026, 1, 7), dry_run=False, owner_user_id=None) == 0
    assert gi.purge(date(2026, 1, 9), dry_run=True, owner_user_id=None) == 1
    assert db.query_one("SELECT raw_json FROM guide_import WHERE id = ?", (import_id,))["raw_json"]
    assert gi.purge(date(2026, 1, 9), dry_run=False, owner_user_id=None) == 1
    row = db.query_one("SELECT status, raw_json FROM guide_import WHERE id = ?", (import_id,))
    assert (row["status"], row["raw_json"]) == ("expired", None)
    # The row stays, without text, as the record of the one import; a failed row goes.
    failed = db.insert("guide_import", {
        "apartment_id": ws["home"], "source": "booking", "url": "https://www.booking.com/hotel/cz/vivus-3.html", "status": "failed",
        "created_at": "2026-01-01T10:00:00",
    })
    assert gi.purge(date(2026, 3, 5), dry_run=False, owner_user_id=None) == 1
    assert db.query_one("SELECT id FROM guide_import WHERE id = ?", (import_id,))
    assert db.query_one("SELECT id FROM guide_import WHERE id = ?", (failed,)) is None
    assert gi.imports_left(ws["home"]) == 1
    assert "guide_imports" in dict(retention.STEPS)
