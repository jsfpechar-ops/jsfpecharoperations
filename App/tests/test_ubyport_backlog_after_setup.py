"""A3: a backlog of old stays is filed in one sweep once police settings are complete.

Owner, 2026-11-16: even if hosts add police details late, after the stays
happened, every pending guest must go out as a batch automatically; if that
does not happen there must be a critical alert.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from app import alerts, db, reporting, validation
from tests.test_deadline_cap_filing import _FakeClient, _fresh_db, _stay
from tests.test_send_controls import SIGNATURE

MISSING_IDUB = [validation.Issue("uby_idub", "IDUB is required before anything can be reported.")]


def _settings(monkeypatch, issues):
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: list(issues))


def _client(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client)
    return client


def _guest(reservation_id, n, nationality="GBR"):
    now = db.utcnow()
    return db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": f"Smith{chr(65 + n % 26)}",
            "first_name": "John",
            "birth_date": "01011990",
            "nationality": nationality,
            "doc_number": f"P{n:07d}",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "is_lead": 1 if n % 12 == 0 else 0,
            "entered_by": "host",
            "signature_png": SIGNATURE,
            "signed_at": now,
            "identity_verified_at": now,
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )


def _old_stay(apartment_id, days_ago, uid):
    start = date.today() - timedelta(days=days_ago)
    now = db.utcnow()
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": uid,
            "date_from": start.isoformat(),
            "date_to": (start + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _property(monkeypatch, tmp_path, name, *, police_field=True):
    _fresh_db(monkeypatch, tmp_path, f"{name}.db")
    apartment_id, _res, _ids = _stay(
        "scheduled", date_from=(date.today() - timedelta(days=40)).isoformat(),
        expected=None, guests=0, token=f"tok-a3-{name}",
    )
    if police_field:
        db.update("apartment", apartment_id, {"uby_idub": "ABCDEFGH1234"})
    return apartment_id


def _backlog(apartment_id):
    """36 guests on three stays that ended 7 to 17 days ago."""
    ids = []
    for k, days_ago in enumerate((20, 15, 10)):
        res = _old_stay(apartment_id, days_ago, f"a3-old-{k}")
        ids += [_guest(res, k * 12 + i) for i in range(12)]
    return ids


def _setup_alert(apartment_id):
    return db.query_one(
        "SELECT level, params FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL",
        (f"apartment_setup:{apartment_id}",),
    )


def _states(ids):
    return {
        db.query_one("SELECT submit_state FROM guest WHERE id = ?", (gid,))["submit_state"]
        for gid in ids
    }


def test_incomplete_setup_with_waiting_guests_is_critical(monkeypatch, tmp_path):
    apartment_id = _property(monkeypatch, tmp_path, "crit")
    _backlog(apartment_id)
    _settings(monkeypatch, MISSING_IDUB)
    client = _client(monkeypatch)

    reporting.sweep()

    alert = _setup_alert(apartment_id)
    assert alert["level"] == "critical"
    params = json.loads(alert["params"])
    assert params["variant"] == "pending" and params["count"] == 36
    assert client.batches == []


def test_incomplete_setup_without_waiting_guests_stays_a_warning(monkeypatch, tmp_path):
    apartment_id = _property(monkeypatch, tmp_path, "warn")
    res = _old_stay(apartment_id, 10, "a3-czech")
    _guest(res, 1, nationality="CZE")  # Czech guests owe no police report
    _settings(monkeypatch, MISSING_IDUB)
    _client(monkeypatch)

    reporting.sweep()

    alert = _setup_alert(apartment_id)
    assert alert["level"] == "warning"
    assert "variant" not in json.loads(alert["params"])


def test_a_property_with_no_police_field_keeps_the_warning(monkeypatch, tmp_path):
    """1171 / D1: a host who never entered a police field files elsewhere."""
    apartment_id = _property(monkeypatch, tmp_path, "elsewhere", police_field=False)
    _backlog(apartment_id)
    _settings(monkeypatch, MISSING_IDUB)
    _client(monkeypatch)

    reporting.sweep()

    assert _setup_alert(apartment_id)["level"] == "warning"


def test_backlog_goes_out_in_one_sweep_once_settings_are_complete(monkeypatch, tmp_path):
    apartment_id = _property(monkeypatch, tmp_path, "backlog")
    ids = _backlog(apartment_id)
    _settings(monkeypatch, MISSING_IDUB)
    client = _client(monkeypatch)
    reporting.sweep()
    assert _states(ids) == {reporting.PENDING}

    _settings(monkeypatch, [])  # the host finished the police settings
    reporting.sweep()

    assert client.batches == [32, 4]
    assert _states(ids) == {reporting.SENT}
    assert _setup_alert(apartment_id) is None

    reporting.sweep()  # nothing is sent twice
    assert client.batches == [32, 4]


def test_pending_title_names_the_count():
    row = {
        "kind": "apartment_setup",
        "message": "stored",
        "detail": "",
        "params": json.dumps({"property": "Loft", "variant": "pending", "count": 36}),
    }
    for lang in ("en", "cs"):
        title = alerts.present(dict(row), lang)["display_title"]
        assert "Loft" in title and "36" in title, lang
