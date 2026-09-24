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


def test_pin_token_lockout_tells_the_host(monkeypatch):
    """30 wrong PINs from 30 addresses lock every guest out for 24h."""
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
        alerts = db.query("SELECT kind, level FROM alert WHERE apartment_id = ?", (apt["id"],))
        kinds = [a["kind"] for a in alerts]
        assert "guest_pin_locked_out" in kinds, kinds
        lock = [a for a in alerts if a["kind"] == "guest_pin_locked_out"][0]
        assert lock["level"] == "critical"
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE scope IN ('pin_fail','pin_fail_token')")
        gp._cleanup()


def test_cf_connecting_ip_spoof_no_longer_bypasses_per_ip_limits(monkeypatch):
    """A private peer cannot name its own address unless it is a configured proxy."""
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
        assert 429 in codes  # 60 > GUEST_POST_MAX_ATTEMPTS=30
        keys = db.query("SELECT DISTINCT key FROM rate_limit_event WHERE scope='guest_party'")
        assert len(keys) == 1  # every attempt counts against the one real peer
    finally:
        client_ip.reset_trusted_proxy_cache()
        db.execute("DELETE FROM rate_limit_event WHERE scope='guest_party'")
        cm._cleanup()


def test_cf_connecting_ip_is_honoured_from_a_configured_proxy(monkeypatch):
    """The trust is not gone, only named: a configured peer still resolves visitors."""
    monkeypatch.setattr(config, "CLOUDFLARE_PROXY", True)
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", "172.18.0.0/16")
    client_ip.reset_trusted_proxy_cache()
    try:
        scope = {"client": ("172.18.0.3", 1)}
        client_ip.apply_visitor_client(scope, {"cf-connecting-ip": "198.51.100.99"})
        assert scope["client"][0] == "198.51.100.99"
    finally:
        client_ip.reset_trusted_proxy_cache()


def test_claim_landing_enforces_the_reachback_bound():
    """W3.5's bound now holds on /l/t/id/claim too, and on a locked stay."""
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
        assert b.get(f"/l/{cm.TOKEN}/{old}/claim").status_code == 404
        assert b.get(f"/l/{cm.TOKEN}/987654/claim").status_code == 404
    finally:
        cm._cleanup()


def test_a_locked_stay_has_no_claim_form():
    current, _p, _f, _a = cm._seed()
    try:
        b = TestClient(app)
        b.cookies.set(host_i18n.LANG_COOKIE, "en")
        claim.ensure_row(current)
        assert b.get(f"/l/{cm.TOKEN}/{current}/claim").status_code == 200
        claim.lock_guest_access(current)
        assert b.get(f"/l/{cm.TOKEN}/{current}/claim").status_code == 404
    finally:
        cm._cleanup()


def test_old_device_loses_access_after_host_release_and_reclaim():
    """A released device must not be let back in by someone else's re-claim.

    The cookie used to name only the stay id, so it kept matching once any
    device claimed again and the released browser walked straight back in.
    """
    from tests import test_host_guest_form as hg

    _owner, stay_id = hg._host_stay()
    try:
        a = hg._claimed_guest(stay_id)
        assert hg._save(a, stay_id, **hg._complete_guest()).status_code == 303
        # A declared party of one is what makes the registration complete, and
        # only a complete registration is gated on the claim cookie.
        db.execute("UPDATE reservation SET declared_guests = 1 WHERE id = ?", (stay_id,))
        assert a.get(f"/l/{hg.TOKEN}/{stay_id}/new").status_code == 200

        claim.release(stay_id)  # host revokes the wrong claimant
        r = a.get(f"/l/{hg.TOKEN}/{stay_id}/new", follow_redirects=False)
        assert r.status_code == 303, "a release must cut the released device off"
        assert "/new" not in r.headers.get("location", "")

        b = hg._claimed_guest(stay_id)  # the right guest confirms
        assert b.get(f"/l/{hg.TOKEN}/{stay_id}/new").status_code == 200
        # B's claim must not hand A's browser its access back.
        assert a.get(f"/l/{hg.TOKEN}/{stay_id}/new", follow_redirects=False).status_code == 303
        # And the released browser cannot write the registration either.
        assert hg._save(a, stay_id, **hg._complete_guest(surname="HIJACKED")).status_code == 303
        stored = db.query_one("SELECT surname FROM guest WHERE reservation_id = ?", (stay_id,))
        assert stored["surname"] == "SMITH"
    finally:
        hg._cleanup()


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
        # second "concurrent" confirm whose read happened before the first write:
        # the secret is already spent, so only the first may win.
        assert claim.confirm(res, secret) is False
    finally:
        cm._cleanup()


import pytest as _pytest
@_pytest.mark.parametrize("bad", ["garbage", "2026-02-30", "31.12.2099"])
def test_unparseable_stay_date_is_refused(bad):
    from app import validation
    from tests import test_host_guest_form as hg
    _o, stay_id = hg._host_stay()
    try:
        client = hg._claimed_guest(stay_id)
        r = hg._save(client, stay_id, stay_from=bad, **hg._complete_guest())
        g = db.query_one("SELECT stay_from, stay_to FROM guest WHERE reservation_id=?", (stay_id,))
        print(bad, r.status_code, dict(g) if g else None)
        assert r.status_code == 422
        assert validation.STAY_DATE_UNREADABLE_MESSAGE in r.text
        assert g is None or g["stay_from"] != bad, "an unreadable date reached the row"
    finally:
        hg._cleanup()


def test_a_legacy_garbage_stay_to_does_not_escape_the_purge():
    """A row written before the form refused bad dates must still lose its photo.

    A garbage stay_to sorts after every ISO cutoff as text, so the sweep used
    to skip the row forever and the passport image outlived its purpose.
    """
    from datetime import date
    from app import passport_photos
    from tests import test_host_guest_form as hg
    from tests import test_retention as ret
    _o, stay_id = hg._host_stay()
    try:
        client = hg._claimed_guest(stay_id)
        assert hg._save(client, stay_id, **hg._complete_guest()).status_code == 303
        guest = db.query_one("SELECT id FROM guest WHERE reservation_id=?", (stay_id,))
        passport_photos.save_photo(guest["id"], ret.PNG_BYTES, "image/png")
        db.execute(
            "UPDATE guest SET stay_to = 'x', passport_photo_at = ? WHERE id = ?",
            (db.utcnow(), guest["id"]))
        assert passport_photos.purge_stale(owner_user_id=None, today=date(2100, 1, 1)) >= 1
        assert not passport_photos.has_photo(guest["id"])
    finally:
        hg._cleanup()
