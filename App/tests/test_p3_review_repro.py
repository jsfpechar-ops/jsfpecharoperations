"""Phase 3 review repros (not for merge)."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app import auth, claim, client_ip, config, db, host_i18n, rate_limit
from app.main import app
from tests.conftest import complete_guest_claim
from tests import test_guest_pin as gp
from tests import test_claim_mail as cm


def test_pin_token_lockout_raises_no_alert(monkeypatch):
    """30 wrong PINs from 30 addresses lock every guest out for 24h, host never told."""
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)
    monkeypatch.setattr("app.routes.guest.asyncio.sleep", AsyncMock())
    gp._stay_id()
    apt = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (gp.TOKEN,))
    try:
        db.execute("DELETE FROM rate_limit_event WHERE scope IN ('pin_fail','pin_fail_token')")
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
        for i in range(rate_limit._PIN_TOKEN_MAX_FAILURES):
            TestClient(app, client=(f"10.9.0.{i}", 1)).post(
                f"/l/{gp.TOKEN}/pin", data={"pin": "000000"}, follow_redirects=False)
        assert rate_limit.pin_token_blocked(f"{gp.TOKEN}:{auth.pin_fingerprint(gp.TOKEN, gp.PIN)}")
        ok = TestClient(app, client=("10.9.9.9", 1)).post(
            f"/l/{gp.TOKEN}/pin", data={"pin": gp.PIN}, follow_redirects=False)
        assert ok.status_code == 200 and 'name="pin"' in ok.text  # real guest refused
        alerts = db.query("SELECT kind FROM alert WHERE apartment_id = ?", (apt["id"],))
        print("ALERTS:", [a["kind"] for a in alerts])
        assert alerts == []  # BUG: no host-visible signal of a 24h lockout
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE scope IN ('pin_fail','pin_fail_token')")
        gp._cleanup()


def test_cf_connecting_ip_spoof_bypasses_per_ip_limits(monkeypatch):
    """With CLOUDFLARE_PROXY=1 any RFC1918 peer is trusted; origin hit directly -> spoof."""
    monkeypatch.setattr(config, "CLOUDFLARE_PROXY", True)
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", "")
    client_ip.reset_trusted_proxy_cache()
    current, _p, _f, _a = cm._seed()
    try:
        caddy = TestClient(app, client=("172.18.0.3", 1))
        complete_guest_claim(caddy, cm.TOKEN, current)
        codes = []
        for i in range(60):
            r = caddy.post(f"/l/{cm.TOKEN}/{current}/party", data={"party_size": "2"},
                           headers={"CF-Connecting-IP": f"203.0.113.{i}"}, follow_redirects=False)
            codes.append(r.status_code)
        print("codes", set(codes))
        assert 429 not in codes  # 60 > GUEST_POST_MAX_ATTEMPTS=30
        keys = db.query("SELECT DISTINCT key FROM rate_limit_event WHERE scope='guest_party'")
        assert len(keys) >= 60
    finally:
        client_ip.reset_trusted_proxy_cache()
        db.execute("DELETE FROM rate_limit_event WHERE scope='guest_party'")
        cm._cleanup()


def test_claim_landing_ignores_reachback_bound():
    """W3.5 bound is enforced on /l/t/id but not on /l/t/id/claim."""
    _c, _p, _f, apartment_id = cm._seed()
    today = claim.prague_today()
    now = db.utcnow()
    try:
        old = db.insert("reservation", {
            "apartment_id": apartment_id, "source": "airbnb", "uid": "p3-old",
            "date_from": (today - timedelta(days=2000)).isoformat(),
            "date_to": (today - timedelta(days=1998)).isoformat(),
            "status": "active", "created_at": now, "updated_at": now})
        b = TestClient(app)
        b.cookies.set(host_i18n.LANG_COOKIE, "en")
        assert b.get(f"/l/{cm.TOKEN}/{old}").status_code == 404
        r = b.get(f"/l/{cm.TOKEN}/{old}/claim")
        never = b.get(f"/l/{cm.TOKEN}/987654/claim")
        print(r.status_code, never.status_code)
        assert r.status_code == 200 and never.status_code == 404
        d = (today - timedelta(days=2000))
        assert f"{d.day}. {d.month}. {d.year}" in r.text or d.isoformat() in r.text or str(d.year) in r.text
        # locked stay too
        claim.ensure_row(old); claim.lock_guest_access(old)
        assert b.get(f"/l/{cm.TOKEN}/{old}/claim").status_code == 200
    finally:
        cm._cleanup()


def test_old_device_keeps_access_after_host_release_and_reclaim():
    current, _p, _f, _a = cm._seed()
    try:
        a = TestClient(app); a.cookies.set(host_i18n.LANG_COOKIE, "en")
        complete_guest_claim(a, cm.TOKEN, current, email="wrong@example.test")
        claim.release(current)  # host revokes the wrong claimant
        assert "guest_email" in a.get(f"/l/{cm.TOKEN}/{current}", follow_redirects=True).text
        b = TestClient(app); b.cookies.set(host_i18n.LANG_COOKIE, "en")
        complete_guest_claim(b, cm.TOKEN, current, email="right@example.test")
        # device A never re-confirmed, yet reaches the form again
        r = a.get(f"/l/{cm.TOKEN}/{current}/new", follow_redirects=False)
        print("A /new:", r.status_code)
        assert r.status_code == 200 and "signature" in r.text
    finally:
        cm._cleanup()


def test_confirm_double_win_with_stale_read(monkeypatch):
    current, _p, _f, apartment_id = cm._seed()
    try:
        res = db.query_one("SELECT * FROM reservation WHERE id=?", (current,))
        apt = db.query_one("SELECT * FROM apartment WHERE id=?", (apartment_id,))
        ok, err, secret = claim.start_claim(res, apt, email="g@example.test", party_size=1, lang="en")
        assert ok, err
        stale = claim._row(current)
        assert claim.confirm(res, secret) is True
        real = claim._row
        calls = {"n": 0}
        def fake(rid):
            calls["n"] += 1
            return stale if calls["n"] == 1 else real(rid)
        monkeypatch.setattr(claim, "_row", fake)
        # second "concurrent" confirm whose read happened before the first write
        assert claim.confirm(res, secret) is True  # both win
    finally:
        cm._cleanup()


import pytest as _pytest
@_pytest.mark.parametrize("bad", ["garbage", "2026-02-30", "31.12.2099"])
def test_unparseable_stay_date_bypasses_window(bad):
    from tests import test_host_guest_form as hg
    _o, stay_id = hg._host_stay()
    try:
        client = hg._claimed_guest(stay_id)
        r = hg._save(client, stay_id, stay_from=bad, **hg._complete_guest())
        g = db.query_one("SELECT stay_from, stay_to FROM guest WHERE reservation_id=?", (stay_id,))
        print(bad, r.status_code, dict(g) if g else None)
        assert r.status_code == 303 and g["stay_from"] == bad
    finally:
        hg._cleanup()


def test_garbage_stay_to_escapes_passport_purge():
    from datetime import date
    from app import passport_photos
    from tests import test_host_guest_form as hg
    _o, stay_id = hg._host_stay()
    try:
        client = hg._claimed_guest(stay_id)
        r = hg._save(client, stay_id, stay_to="x", **hg._complete_guest())
        assert r.status_code == 303
        g = db.query_one("SELECT id, stay_to FROM guest WHERE reservation_id=?", (stay_id,))
        rows = db.query(
            "SELECT g.id FROM guest g JOIN reservation r ON r.id=g.reservation_id "
            "WHERE COALESCE(g.stay_to, r.date_to) < ?",
            (passport_photos.stale_cutoff(date(2100, 1, 1)).isoformat(),))
        print(g["stay_to"], [x["id"] for x in rows])
        assert g["id"] not in [x["id"] for x in rows]
    finally:
        hg._cleanup()
