"""0100: the setup guide's demo stay is never reported, billed or exported,
and the "still waiting for my police login" copy says what the code does.

The demo stay is a real ``reservation`` row inside a real property, marked by
``source = 'demo'`` (demo.DEMO_STAY_SOURCE). Every path that could put its
made-up guests in front of the police, a council, a guest's inbox or a door is
pinned here, against the mock UbyPort server where filing is involved.
"""
from __future__ import annotations

import base64
import json
import secrets
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import (
    auth, config, db, demo, door_codes, filing_watchdog, housebook, host_i18n, invoices,
    mail, property_setup, reporting, stay_fee, stays_export,
)
from app.main import app
from app.routes import guest as guest_routes
from tests.conftest import login_as

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
POLICE = {
    "uby_idub": "100227887699", "uby_mark": "SYNTE", "uby_name": "Synthetic Demo Flat",
    "uby_contact": "host@example.test", "uby_ws_user": "UBY-WS12synt",
}
ADDRESS = {"addr_obec": "Praha", "addr_street": "Synthetic", "addr_house_no": "12",
           "addr_zip": "12000", "addr_okres": "Praha 2"}


class Recorder:
    """Wraps the real client for the mock server and records every batch."""

    def __init__(self, real):
        self.real = real
        self.batches = []

    def submit(self, header, guests):
        self.batches.append(json.dumps(guests, default=str, ensure_ascii=False))
        return self.real.submit(header, guests)


@pytest.fixture
def world(mock_ubyport, monkeypatch):
    db.init_db()
    now = db.utcnow()
    username = f"demo-ex-{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Demo Exclusion", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Synthetic Exclusion s.r.o.", "seat": "Praha", "ico": "12345678",
                                        "contact_email": "host@example.test", "owner_user_id": owner,
                                        "created_at": now})
    apartment_id = db.insert("apartment", {
        "legal_entity_id": entity, "owner_user_id": owner, "internal_name": "Synthetic Exclusion Flat",
        "city_en": "Prague", "permalink_token": f"dx{secrets.token_hex(6)}", "permalink_pin": "246802",
        "automation_mode": "scheduled", "submit_after_hours": 1, "default_purpose": "10",
        "stay_fee_rate_czk": 50, "active": 1, "created_at": now, **ADDRESS, **POLICE,
        "uby_ws_password_enc": db.encrypt_secret("synthetic-password"),
    })
    recorder = {}
    real_client_for = reporting.client_for

    def client_for(apartment, env=None):
        client = Recorder(real_client_for(apartment, env))
        recorder.setdefault("clients", []).append(client)
        return client

    monkeypatch.setattr(reporting, "client_for", client_for)
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"owner": owner, "apartment_id": apartment_id, "recorder": recorder, "client": client,
           "username": username}
    # Leave nothing behind: later files (test_endtoend) read every property.
    db.execute("DELETE FROM submission_claim WHERE guest_id IN (SELECT g.id FROM guest g JOIN reservation r "
               "ON r.id = g.reservation_id WHERE r.apartment_id = ?)", (apartment_id,))
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM alert WHERE apartment_id = ? OR owner_user_id = ?", (apartment_id, owner))
    db.execute("DELETE FROM email_outbox WHERE apartment_id = ? OR reservation_id IN "
               "(SELECT id FROM reservation WHERE apartment_id = ?)", (apartment_id, apartment_id))
    db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{apartment_id}",))
    db.execute("DELETE FROM apartment_slug WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity,))
    db.execute("UPDATE audit SET owner_user_id = NULL WHERE owner_user_id = ?", (owner,))


def _stay(apartment_id, *, source, surname, arrived_days_ago=0, nationality="GBR"):
    now = db.utcnow()
    day = date.today() - timedelta(days=arrived_days_ago)
    completed = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "source": source, "uid": f"{source}-{secrets.token_hex(6)}",
        "date_from": day.isoformat(), "date_to": (day + timedelta(days=2)).isoformat(),
        "status": "active", "expected_guests_override": 1, "registration_completed_at": completed,
        "created_at": now, "updated_at": now,
    })
    guest_id = db.insert("guest", {
        "reservation_id": reservation_id, "surname": surname, "first_name": "Synthetic",
        "birth_date": "01011990", "nationality": nationality, "doc_number": "P1234567",
        "res_street": "Street 1", "res_city": "London", "res_country": "GBR", "purpose": "10",
        "is_lead": 1, "entered_by": "guest", "signature_png": SIGNATURE, "signed_at": now,
        "submit_state": reporting.PENDING, "created_at": now, "updated_at": now,
    })
    return reservation_id, guest_id


def _demo_stay(apartment_id, surname="Demoperson", **kwargs):
    reservation_id, guest_id = _stay(apartment_id, source="demo", surname=surname, **kwargs)
    assert demo.is_demo_stay(db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,)))
    return reservation_id, guest_id


def _state(guest_id):
    return db.query_one("SELECT submit_state, submission_id FROM guest WHERE id = ?", (guest_id,))


def _sent_payloads(world):
    return [batch for client in world["recorder"].get("clients", []) for batch in client.batches]


# --- filing: sweep, host send, resend, completion send, claim, batch ---------


def test_the_sweep_files_the_real_stay_and_never_the_demo_stay(world):
    apartment_id = world["apartment_id"]
    _real, real_guest = _stay(apartment_id, source="manual", surname="Realperson")
    demo_stay, demo_guest = _demo_stay(apartment_id)
    reporting.sweep(owner_user_id=world["owner"])
    # The path works (the real stay reached the mock register)...
    assert _state(real_guest)["submit_state"] == reporting.SENT
    payloads = _sent_payloads(world)
    assert payloads and any("Realperson" in batch for batch in payloads)
    # ...and the demo stay never did, nor was it ever in a batch.
    assert not any("Demoperson" in batch for batch in payloads)
    assert _state(demo_guest)["submit_state"] == reporting.PENDING
    assert _state(demo_guest)["submission_id"] is None
    for row in db.query("SELECT guest_ids FROM submission WHERE apartment_id = ?", (apartment_id,)):
        assert demo_guest not in json.loads(row["guest_ids"])
    assert demo_stay


@pytest.mark.parametrize("flags", [
    {}, {"ignore_automation": True}, {"ignore_schedule": True},
    {"ignore_automation": True, "allow_resend": True},
])
def test_no_collection_ever_offers_the_demo_stay(world, flags):
    _demo_stay_id, demo_guest = _demo_stay(world["apartment_id"])
    for only in (None, [demo_guest]):
        pairs = reporting.collect_sendable(world["apartment_id"], only, **flags)
        assert demo_guest not in [guest["id"] for guest, _ in pairs]


def test_every_send_path_leaves_the_demo_stay_unfiled_and_unclaimed(world):
    apartment_id = world["apartment_id"]
    demo_stay, demo_guest = _demo_stay(apartment_id)
    # A host send, a forced resend and the immediate send on completion.
    assert reporting.submit_for_apartment(apartment_id, only_guest_ids=[demo_guest],
                                          mode="manual", ignore_automation=True) == []
    db.update("guest", demo_guest, {"submit_state": reporting.SENT})
    assert reporting.submit_for_apartment(apartment_id, only_guest_ids=[demo_guest], mode="manual_resend",
                                          ignore_automation=True, allow_resend=True) == []
    db.update("guest", demo_guest, {"submit_state": reporting.PENDING})
    db.update("apartment", apartment_id, {"automation_mode": "immediate"})
    reporting.submit_stay_if_complete(apartment_id, demo_stay)
    assert not _sent_payloads(world)
    assert not db.query_one("SELECT 1 AS n FROM submission_claim WHERE guest_id = ?", (demo_guest,))
    assert _state(demo_guest)["submission_id"] is None
    # A forged pair handed straight to the batch is refused before a
    # submission row or a UbyPort call exists.
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    pair = (db.query_one("SELECT * FROM guest WHERE id = ?", (demo_guest,)),
            db.query_one("SELECT * FROM reservation WHERE id = ?", (demo_stay,)))
    assert reporting.submit_batch(apartment, [pair], mode="manual")["state"] == "noop"
    assert not db.query_one("SELECT 1 AS n FROM submission WHERE apartment_id = ?", (apartment_id,))
    assert not _sent_payloads(world)


def test_the_stay_page_offers_no_send_and_the_routes_refuse_it(world):
    demo_stay, demo_guest = _demo_stay(world["apartment_id"])
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (demo_stay,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (world["apartment_id"],))
    controls = reporting.send_controls(reservation, apartment, reporting.reservation_progress(reservation))
    assert controls["send_enabled"] is False and controls["send_visible"] is False
    assert controls["send_hint_key"] == "hint.demo_stay"
    client = world["client"]
    client.post(f"/reservations/{demo_stay}/submit", data={}, follow_redirects=False)
    client.post("/reservations/submit-ready", data={}, follow_redirects=False)
    client.post(f"/reservations/{demo_stay}/filed-by-hand",
                data={"filed_at": datetime.now().strftime("%Y-%m-%dT%H:%M")}, follow_redirects=False)
    assert _state(demo_guest)["submit_state"] == reporting.PENDING
    assert not _sent_payloads(world)
    page = client.get(f"/reservations/{demo_stay}?lang=en").text
    assert host_i18n.translate("en", "stay.detail.banner.demo") in page
    assert host_i18n.translate("en", "status.demo_preview") in page
    assert 'action="/reservations/%d/submit"' % demo_stay not in page
    assert 'id="file-by-hand"' not in page


# --- deadlines, watchdog, door codes, mail, guest picker ---------------------


def test_no_deadline_alert_watchdog_mail_or_door_code_for_the_demo_stay(world, monkeypatch):
    apartment_id = world["apartment_id"]
    db.update("apartment", apartment_id, {"automation_mode": "manual"})
    # Arrived ten days ago: a real stay this late is at risk everywhere.
    demo_stay, _guest = _demo_stay(apartment_id, arrived_days_ago=10)
    empty_demo = db.insert("reservation", {
        "apartment_id": apartment_id, "source": "demo", "uid": f"demo-{secrets.token_hex(5)}",
        "date_from": (date.today() - timedelta(days=4)).isoformat(),
        "date_to": (date.today() + timedelta(days=1)).isoformat(), "status": "active",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    real_stay, _real_guest = _stay(apartment_id, source="manual", surname="Latereal", arrived_days_ago=10)
    reporting.check_deadlines(owner_user_id=world["owner"])
    flagged = {row["reservation_id"] for row in db.query(
        "SELECT reservation_id FROM alert WHERE apartment_id = ? AND kind = 'deadline' AND resolved_at IS NULL",
        (apartment_id,))}
    assert real_stay in flagged and demo_stay not in flagged
    at_risk = {row["reservation_id"] for row in filing_watchdog.at_risk_stays()}
    assert real_stay in at_risk and demo_stay not in at_risk
    assert empty_demo not in {row["reservation_id"] for row in filing_watchdog.unknown_risk_stays()}
    # Door codes: the eligibility clause and the stay view both skip it.
    db.update("apartment", apartment_id, {"lock_provider": "ttlock", "lock_id": 7, "checkin_hour": 15,
                                           "checkout_hour": 10})
    monkeypatch.setattr(config, "DOOR_CODES_LIVE", True)
    door_real, _g = _stay(apartment_id, source="manual", surname="Doorreal")
    door_demo, _g = _demo_stay(apartment_id, surname="Doordemo")
    clause, today = door_codes._eligible_sql()
    eligible = {row["id"] for row in db.query(
        f"SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE {clause}", (today,))}
    assert door_real in eligible and door_demo not in eligible
    assert door_codes.ensure_row(door_demo) is None
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (door_demo,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert door_codes.view(dict(reservation), dict(apartment)) is None
    # Guest e-mail for a demo stay is never queued; for a real stay it is.
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    common = {"kind": "completion", "to_email": "made.up@example.test", "subject": "x",
              "payload": {"reply_to": "host@example.test"}}
    assert mail.enqueue(idempotency_key=f"dx-{secrets.token_hex(4)}", reservation_id=demo_stay, **common) is None
    assert mail.enqueue(idempotency_key=f"dx-{secrets.token_hex(4)}", reservation_id=real_stay, **common)
    db.execute("DELETE FROM email_outbox WHERE reservation_id IN (?, ?)", (demo_stay, real_stay))


def test_only_the_signed_in_host_reaches_the_demo_stay_from_the_guest_link(world):
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (world["apartment_id"],))
    demo_stay = demo.create_demo_stay(world["apartment_id"])
    assert demo.create_demo_stay(world["apartment_id"]) == demo_stay  # one at a time
    assert demo_stay not in [row["id"] for row in guest_routes._visible_reservations(apartment)]
    assert guest_routes._reservation_for_guest(apartment, demo_stay, None) is None
    assert guest_routes._claimable_reservation(apartment, demo_stay) is None
    token = apartment["permalink_token"]
    stranger = TestClient(app)
    assert stranger.get(f"/l/{token}/{demo_stay}?lang=en", follow_redirects=False).status_code == 404
    assert stranger.get(f"/l/{token}/{demo_stay}/new?lang=en", follow_redirects=False).status_code == 404
    # The host's own browser opens the empty demo stay straight on its form.
    host_page = world["client"].get(f"/l/{token}/{demo_stay}?lang=en", follow_redirects=False)
    assert host_page.status_code == 303 and f"/{demo_stay}/new" in host_page.headers["location"]


# --- money and records: stay fee, invoices, house book, stays export ---------


def test_the_demo_stay_is_left_out_of_fees_invoices_house_book_and_exports(world):
    apartment_id = world["apartment_id"]
    demo_stay, demo_guest = _demo_stay(apartment_id)
    real_stay, real_guest = _stay(apartment_id, source="manual", surname="Feereal")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    period = stay_fee.property_period(apartment, date.today(), live_only=True)
    charged = {line["reservation_id"] for line in period["lines"]}
    assert real_stay in charged and demo_stay not in charged
    assert period["total_czk"] == sum(line["amount_czk"] for line in period["lines"]) > 0
    # An unsigned demo guest does not count as a missing signature either.
    db.update("guest", demo_guest, {"signature_png": None})
    assert stay_fee.unsigned_stays(apartment_id, period["first"], period["last"]) == 0
    db.update("guest", demo_guest, {"signature_png": SIGNATURE})
    book = json.dumps(housebook.housebook_rows(apartment_id=apartment_id), default=str, ensure_ascii=False)
    assert "Feereal" in book and "Demoperson" not in book
    db.update("guest", demo_guest, {"archived_at": db.utcnow()})
    db.update("guest", real_guest, {"archived_at": db.utcnow()})
    archived = [row["_guest_id"] for row in housebook.housebook_archived_rows(apartment_id=apartment_id)]
    assert real_guest in archived and demo_guest not in archived
    db.update("guest", real_guest, {"archived_at": None})
    db.update("guest", demo_guest, {"archived_at": None})
    sql, params = stays_export._export_sql(apartment_id=apartment_id)
    exported = [row["id"] for row in db.query(sql, params)]
    assert real_stay in exported and demo_stay not in exported
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (demo_stay,))
    assert invoices.stay_problem(reservation, date.today()) == "invoice.err.demo_stay"
    real = db.query_one("SELECT * FROM reservation WHERE id = ?", (real_stay,))
    assert invoices.stay_problem(real, date.today()) is None
    # The invoice builder's stay picker lists the real stay only.
    builder = world["client"].get("/invoices/new?lang=en").text
    assert f'value="{real_stay}"' in builder and f'value="{demo_stay}"' not in builder


def test_delete_removes_only_a_demo_stay(world):
    apartment_id = world["apartment_id"]
    demo_stay, demo_guest = _demo_stay(apartment_id)
    real_stay, real_guest = _stay(apartment_id, source="manual", surname="Keepme")
    assert demo.delete_demo_stay(real_stay, apartment_id) is False
    world["client"].post(f"/reservations/{real_stay}/delete-demo", data={}, follow_redirects=False)
    assert db.query_one("SELECT id FROM reservation WHERE id = ?", (real_stay,))
    response = world["client"].post(f"/reservations/{demo_stay}/delete-demo", data={}, follow_redirects=False)
    assert response.status_code == 303
    assert not db.query_one("SELECT id FROM reservation WHERE id = ?", (demo_stay,))
    assert not db.query_one("SELECT id FROM guest WHERE id = ?", (demo_guest,))
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (real_guest,))


# --- the waiting copy matches the filing behaviour ---------------------------


def _strip_login(apartment_id):
    db.update("apartment", apartment_id, {"uby_ws_user": None, "uby_ws_password_enc": None})


def _save_login(apartment_id):
    db.update("apartment", apartment_id, {"uby_ws_user": POLICE["uby_ws_user"],
                                           "uby_ws_password_enc": db.encrypt_secret("synthetic-password")})


@pytest.mark.parametrize("mode", ["scheduled", "immediate"])
def test_automatic_modes_hold_everything_until_the_login_then_send_due_and_late_stays(world, mode):
    """Copy: nothing goes to the police until the login is saved; then every
    finished registration is sent by itself on the next sweep, late ones too."""
    apartment_id = world["apartment_id"]
    db.update("apartment", apartment_id, {"automation_mode": mode})
    _strip_login(apartment_id)
    _due, due_guest = _stay(apartment_id, source="manual", surname="Dueperson")
    _late, late_guest = _stay(apartment_id, source="manual", surname="Lateperson", arrived_days_ago=12)
    # Guests can register meanwhile; the sweep sends nothing and claims nothing.
    results = reporting.submit_for_apartment(apartment_id, mode="auto")
    assert results and results[0]["state"] == "not_configured"
    reporting.sweep(owner_user_id=world["owner"])
    assert not _sent_payloads(world)
    assert _state(due_guest)["submit_state"] == _state(late_guest)["submit_state"] == reporting.PENDING
    assert not db.query_one("SELECT 1 AS n FROM submission WHERE apartment_id = ?", (apartment_id,))
    # The login arrives: the next sweep files both, the late one included.
    _save_login(apartment_id)
    reporting.sweep(owner_user_id=world["owner"])
    assert _state(due_guest)["submit_state"] == reporting.SENT
    assert _state(late_guest)["submit_state"] == reporting.SENT
    # The copy names the sweep interval the scheduler really uses.
    copy = host_i18n.translate("en", "setup_guide.reporting.wait_then_auto", minutes=config.SUBMIT_SWEEP_MINUTES)
    assert f"within about {config.SUBMIT_SWEEP_MINUTES} minutes" in copy and "late ones too" in copy


def test_manual_mode_waits_as_ready_to_report_until_the_host_sends(world):
    """Copy: finished stays wait in Stays as "Ready to report" until Send."""
    apartment_id = world["apartment_id"]
    db.update("apartment", apartment_id, {"automation_mode": "manual"})
    _strip_login(apartment_id)
    stay, guest_id = _stay(apartment_id, source="manual", surname="Manualperson")
    _save_login(apartment_id)
    reporting.sweep(owner_user_id=world["owner"])
    assert _state(guest_id)["submit_state"] == reporting.PENDING and not _sent_payloads(world)
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
    status = reporting.reservation_progress(reservation)["status"]
    assert host_i18n.translate("en", f"status.{status}") == "Ready to report"
    assert "“Ready to report”" in host_i18n.translate("en", "setup_guide.reporting.wait_then_manual")
    assert host_i18n.translate("en", "stay.detail.cta.send") in host_i18n.translate(
        "en", "setup_guide.reporting.wait_then_manual")
    assert host_i18n.translate("cs", f"status.{status}") in host_i18n.translate(
        "cs", "setup_guide.reporting.wait_then_manual")
    reporting.submit_for_apartment(apartment_id, only_guest_ids=[guest_id], mode="manual", ignore_automation=True)
    assert _state(guest_id)["submit_state"] == reporting.SENT


def test_the_guide_shows_the_copy_for_the_property_mode(world):
    apartment_id = world["apartment_id"]
    _strip_login(apartment_id)
    property_setup.start(apartment_id)
    for step in ("calendar", "guest_links", "pin", "try"):
        property_setup.mark(apartment_id, step, "done")
    for mode, key in (("manual", "wait_then_manual"), ("scheduled", "wait_then_auto"), ("immediate", "wait_then_auto")):
        db.update("apartment", apartment_id, {"automation_mode": mode})
        for lang in ("en", "cs"):
            page = world["client"].get(f"/apartments/{apartment_id}?lang={lang}").text.replace("&#39;", "'")
            expected = host_i18n.translate(lang, f"setup_guide.reporting.{key}", minutes=config.SUBMIT_SWEEP_MINUTES)
            assert expected.replace("“", "&#8220;") in page or expected in page, (mode, lang)
            assert host_i18n.translate(lang, "setup_guide.reporting.wait_deadline") in page
            assert 'href="/guide#manual-filing"' in page
