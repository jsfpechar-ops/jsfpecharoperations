from datetime import datetime, timedelta, timezone

from app import alerts, config, db, icalsync, reporting, scheduler


def _db(monkeypatch, tmp_path, name):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / name)
    db.init_db()
    return db.utcnow()


def _apt(now, mode="manual", owner=None):
    return db.insert("apartment", {"internal_name": "A", "automation_mode": mode, "active": 1,
                                    "created_at": now, "owner_user_id": owner})


def _feed(apt, now):
    return db.insert("ical_feed", {"apartment_id": apt, "url": "https://c.example/x.ics",
                                    "active": 1, "created_at": now})


def _res(apt, feed, uid, f, t, now):
    return db.insert("reservation", {"apartment_id": apt, "ical_feed_id": feed, "uid": uid,
                                      "date_from": f, "date_to": t, "status": "active",
                                      "created_at": now, "updated_at": now})


def _cal(events):
    body = "".join(
        f"BEGIN:VEVENT\nDTSTART;VALUE=DATE:{f.replace('-', '')}\nDTEND;VALUE=DATE:{t.replace('-', '')}\n"
        f"UID:{u}\nSUMMARY:Reserved\nEND:VEVENT\n" for u, f, t in events)
    return f"BEGIN:VCALENDAR\nVERSION:2.0\n{body}END:VCALENDAR\n"


def _sync(feed_id):
    return icalsync.sync_feed(db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,)))


# A: job_failed alert has no owner -> invisible to any logged-in host
def test_A_job_failed_invisible_to_owner(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import auth
    from app.main import app
    now = _db(monkeypatch, tmp_path, "a.db")
    uid = auth.create_account("hostadmin", "Secure-Password-123", "H", role="admin", must_change_password=False)
    monkeypatch.setattr(reporting, "check_deadlines", lambda *a, **k: 1 / 0)
    scheduler._job_deadlines()
    assert len(alerts.open_alerts()) == 1                 # exists
    assert alerts.open_alerts(uid) == []                  # but host (even admin) never sees it
    c = TestClient(app)
    assert c.post("/login", data={"username": "hostadmin", "password": "Secure-Password-123"}, follow_redirects=False).status_code == 303
    page = c.get("/?lang=en")
    assert page.status_code == 200
    assert "deadline watch" not in page.text


# B: early arrival recorded on guest -> anchor earlier, but check_deadlines filters on r.date_from
def test_B_early_arrival_deadline_alert_missing(monkeypatch, tmp_path):
    now = _db(monkeypatch, tmp_path, "b.db")
    apt = _apt(now)
    r = _res(apt, None, "b", "2026-10-10", "2026-10-14", now)
    db.insert("guest", {"reservation_id": r, "surname": "X", "first_name": "Y", "nationality": "DEU",
                        "stay_from": "2026-10-05", "stay_to": "2026-10-14", "created_at": now, "updated_at": now})
    when = datetime(2026, 10, 9, 12, 0)
    res = db.query_one("SELECT * FROM reservation WHERE id=?", (r,))
    anchor = reporting.reservation_deadline_anchor(res)
    assert reporting.deadlines.urgency(anchor, when) == "overdue"   # dashboard says overdue
    assert reporting.check_deadlines(when) == 0                      # no alert raised
    assert alerts.open_alerts() == []


# C: stay moves EARLIER; guest who leaves a day early is not moved -> anchor stays on old dates
def test_C_moved_earlier_guest_left_behind(monkeypatch, tmp_path):
    now = _db(monkeypatch, tmp_path, "c.db")
    apt = _apt(now)
    feed = _feed(apt, now)
    r = _res(apt, feed, "mv", "2026-11-20", "2026-11-25", now)
    g = db.insert("guest", {"reservation_id": r, "surname": "X", "first_name": "Y", "nationality": "DEU",
                            "stay_from": "2026-11-20", "stay_to": "2026-11-24",
                            "signature_png": "data:image/png;base64,x", "signed_at": now,
                            "created_at": now, "updated_at": now})
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _u: _cal([("mv", "2026-10-01", "2026-10-06")]))
    _sync(feed)
    guest = db.query_one("SELECT * FROM guest WHERE id=?", (g,))
    assert (guest["stay_from"], guest["stay_to"]) == ("2026-11-20", "2026-11-24")  # left on old dates
    res = db.query_one("SELECT * FROM reservation WHERE id=?", (r,))
    assert res["date_from"] == "2026-10-01"
    assert str(reporting.reservation_deadline_anchor(res)) == "2026-11-20"
    alerts.resolve(f"dates_changed_resign:{r}")
    assert reporting.check_deadlines(datetime(2026, 10, 8, 12, 0)) == 0   # real arrival 1 Oct: overdue, silent


# D: critical "guest signed" alert fires on a stay with no guests at all
def test_D_resign_alert_without_any_guest(monkeypatch, tmp_path):
    now = _db(monkeypatch, tmp_path, "d.db")
    apt = _apt(now)
    feed = _feed(apt, now)
    r = _res(apt, feed, "e", "2099-01-10", "2099-01-12", now)
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _u: _cal([("e", "2099-01-11", "2099-01-13")]))
    _sync(feed)
    row = db.query_one("SELECT * FROM alert WHERE dedupe_key=?", (f"dates_changed_resign:{r}",))
    assert row and row["level"] == "critical"
    assert db.query_one("SELECT COUNT(*) n FROM guest WHERE reservation_id=?", (r,))["n"] == 0


# F: completeness guard counts UIDs that are not candidates
def test_F_guard_defeated_by_unrelated_uids(monkeypatch, tmp_path):
    now = _db(monkeypatch, tmp_path, "f.db")
    apt = _apt(now)
    feed = _feed(apt, now)
    for i in range(10):
        _res(apt, feed, f"old-{i}", "2099-03-01", "2099-03-05", now)
    # feed now returns 10 events, none of them the stored stays (rotated UIDs / wrong listing / past only)
    monkeypatch.setattr(icalsync, "fetch_feed",
                        lambda _u: _cal([(f"new-{i}", "2020-01-01", "2020-01-03") for i in range(10)]))
    stats = _sync(feed)
    assert stats["cancelled"] == 10


# G: exception after fetch/parse -> feed still 'ok', no alert, job reports success
def test_G_mid_sync_exception_is_silent(monkeypatch, tmp_path):
    now = _db(monkeypatch, tmp_path, "g.db")
    apt = _apt(now)
    feed = _feed(apt, now)
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _u: _cal([("s", "2099-03-01", "2099-03-05")]))
    _sync(feed)
    assert db.query_one("SELECT last_status FROM ical_feed WHERE id=?", (feed,))["last_status"] == "ok"

    def boom(*a, **k):
        raise RuntimeError("reconcile blew up")
    monkeypatch.setattr(icalsync, "_existing_reservation", boom)
    scheduler._job_sync_calendars()
    assert db.query_one("SELECT last_status FROM ical_feed WHERE id=?", (feed,))["last_status"] == "ok"
    assert alerts.open_alerts() == []


# H: W1.5 quiet path is never reached by the scheduler; a stay held open by the link never files
def test_H_quiet_window_never_fires_unattended(monkeypatch, tmp_path):
    now = _db(monkeypatch, tmp_path, "h.db")
    apt = _apt(now, mode="scheduled")
    r = _res(apt, None, "h", "2099-01-10", "2099-01-12", now)
    db.execute("UPDATE reservation SET declared_guests = 60 WHERE id=?", (r,))
    stale = (datetime.now(timezone.utc) - timedelta(hours=48)).replace(microsecond=0).isoformat()
    db.insert("guest", {"reservation_id": r, "surname": "X", "created_at": stale, "updated_at": stale})
    # make the guest "complete" for this purpose
    monkeypatch.setattr(reporting, "guest_is_complete", lambda g, res: True)
    reporting.sweep()
    reporting.check_deadlines()
    assert db.query_one("SELECT registration_completed_at c FROM reservation WHERE id=?", (r,))["c"] is None
    # only a direct call (what the test does) completes it
    assert reporting.refresh_registration_completed_at(r)
    # I: and any later touch of a guest row (host edit) un-completes it again
    db.execute("UPDATE guest SET updated_at=? WHERE reservation_id=?", (db.utcnow(), r))
    assert reporting.refresh_registration_completed_at(r) is None


def test_A_control_owned_alert_renders(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import auth
    from app.main import app
    _db(monkeypatch, tmp_path, "a2.db")
    uid = auth.create_account("hostadmin", "Secure-Password-123", "H", role="admin", must_change_password=False)
    scheduler._job_failed("deadlines")
    db.execute("UPDATE alert SET owner_user_id=?", (uid,))
    c = TestClient(app)
    c.post("/login", data={"username": "hostadmin", "password": "Secure-Password-123"}, follow_redirects=False)
    assert "deadline watch" in c.get("/?lang=en").text
